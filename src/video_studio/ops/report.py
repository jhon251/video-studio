"""3.x Phase 3-C：只读项目报告（`run.py report <project_id>`）。

设计约束（授权要求）：
  · **只读**：数据库以 `file:<path>?mode=ro` URI 打开（SQLite 层面禁止任何写入）；
    不调用调度器（`run_cycle`）、不创建/修改任务与产物、不写任何文件、不访问网络、不产生 LLM 调用。
  · 展示：任务状态、产物、事件、失败原因、成本（LLM 估算）、外部素材用量、响度与验证结果。
  · **成本口径**：LLM 金额是"token × 价目表"的**估算**（客户端没有账单接口），一律标注"估算/非账单"；
    外部素材只报**用量**（Wikimedia 免费，不是计费）。
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ..core.audio import LOUDNESS_CONTRACT

# 关键产物类型（报告里单独列出最新一条）
KEY_ARTIFACTS = ("render_output", "attribution", "voice_output", "subtitle", "qa_report",
                 "compliance_output", "audio_plan", "retrieval_candidates", "script_output")


def readonly_connection(db_path: str | Path) -> sqlite3.Connection:
    """以**只读模式**打开数据库（写入会抛 `sqlite3.OperationalError`）。"""
    uri = "file:{}?mode=ro".format(Path(db_path).as_posix())
    con = sqlite3.connect(uri, uri=True)
    con.row_factory = sqlite3.Row
    return con


def _fetch(con, sql: str, args: tuple = ()) -> list[dict]:
    return [dict(r) for r in con.execute(sql, args)]


def _one(con, sql: str, args: tuple = ()):
    row = con.execute(sql, args).fetchone()
    return dict(row) if row else None


def _art(con, pid: str, type_: str) -> dict | None:
    """最新一条该类型产物（含解析后的 payload，读文件失败时 payload=None）。"""
    rows = _fetch(con, "select * from artifacts where project_id=? and type=? "
                       "order by created_at desc limit 1", (pid, type_))
    if not rows:
        return None
    a = rows[0]
    try:
        a["payload"] = json.loads(Path(a["path"]).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        a["payload"] = None
    return a


def build_report(db_path: str | Path, project_id: str, project_dir: Path | None = None,
                 recent_events: int = 8) -> dict:
    """收集只读报告数据（不打印、不写文件）。项目不存在时返回 {"found": False}。"""
    con = readonly_connection(db_path)
    try:
        project = _one(con, "select * from projects where project_id=?", (project_id,))
        if project is None:
            return {"found": False, "project_id": project_id}

        tasks = _fetch(con, "select task_id, task_type, agent_role, status, version, error, "
                            "cost_usd, model_used, requires_approval, approval, created_at, "
                            "updated_at from tasks where project_id=? order by created_at",
                       (project_id,))
        by_status: dict[str, int] = {}
        for t in tasks:
            by_status[t["status"]] = by_status.get(t["status"], 0) + 1
        problems = [t for t in tasks if t["status"] in ("FAILED", "BLOCKED", "NEEDS_REVIEW")
                    or t.get("error")]
        problems.sort(key=lambda t: t["updated_at"] or 0, reverse=True)

        arts = _fetch(con, "select type, count(*) c, sum(size) bytes from artifacts "
                           "where project_id=? group by type order by c desc", (project_id,))
        key_arts = {}
        for t in KEY_ARTIFACTS:
            a = _art(con, project_id, t)
            if a:
                key_arts[t] = a

        ev_counts = _fetch(con, "select type, count(*) c from events where project_id=? "
                                "group by type order by c desc", (project_id,))
        ev_fail = _fetch(con, "select ts, task_id, type, payload from events where project_id=? "
                              "and type in ('TASK_FAILED','TASK_BLOCKED','COMPLIANCE_BLOCK',"
                              "'CLAIM_GATE_BLOCKED','SKEPTIC_FLAGGED','CONFLICT_DETECTED') "
                              "order by ts desc limit ?", (project_id, recent_events))
        for e in ev_fail:
            try:
                e["error"] = (json.loads(e["payload"]) or {}).get("error")
            except (json.JSONDecodeError, TypeError):
                e["error"] = None

        # ---- 成本（LLM，估算）----
        cost = {"estimate": True, "note": "客户端无账单接口：以下为 token×价目表的估算，非真实账单",
                "task_cost_usd_sum": round(sum(float(t.get("cost_usd") or 0) for t in tasks), 6),
                "by_model": {}}
        for t in tasks:
            if float(t.get("cost_usd") or 0) > 0:
                m = t.get("model_used") or "unknown"
                cost["by_model"][m] = round(cost["by_model"].get(m, 0.0)
                                            + float(t["cost_usd"]), 6)
        llm_rows = _fetch(con, "select payload from events where project_id=? and type='LLM_CALL'",
                          (project_id,))
        tin = tout = 0
        for r in llm_rows:
            try:
                p = json.loads(r["payload"]) or {}
            except (json.JSONDecodeError, TypeError):
                continue
            u = p.get("usage") or p
            tin += int(u.get("prompt_tokens") or u.get("tokens_in") or 0)
            tout += int(u.get("completion_tokens") or u.get("tokens_out") or 0)
        cost.update({"llm_call_events": len(llm_rows), "tokens_in": tin, "tokens_out": tout})

        # ---- 外部素材用量（非计费）----
        material = {"billing": False,
                    "note": "Wikimedia Commons 免费、无 key：以下为**用量**（请求/下载/字节），非金额"}
        retr = key_arts.get("retrieval_candidates")
        if retr and retr.get("payload"):
            p = retr["payload"]
            material["material_mode"] = p.get("material_mode")
            material["mode_reason"] = p.get("material_mode_reason")
            material["candidates_total"] = p.get("candidates_total")
            material["external_verified"] = p.get("external_verified")
            material["external_rejected"] = len(p.get("external_rejected") or [])
            material["external_requested"] = p.get("external_requested")
            ext = p.get("external_provider") or {}
            material["provider"] = {"name": ext.get("name"), "configured": ext.get("configured"),
                                    "error": ext.get("error")}
            stats = ext.get("stats") or {}
            material["provider_stats"] = {
                k: stats.get(k) for k in
                ("requests", "requests_failed", "searched", "fetched", "rejected",
                 "downloaded_bytes", "cache_hits", "retries", "rate_limited", "search_ms",
                 "download_ms", "auth_mode", "token_present", "skipped_non_image",
                 "last_query") if k in stats}
            material["license_classes"] = stats.get("license_classes")
            material["query_shaping"] = stats.get("query_shaping")
        if project_dir is not None:
            ext = Path(project_dir) / "media" / "external"
            files = [f for f in ext.glob("*") if f.is_file() and f.name != ".index.json"] \
                if ext.is_dir() else []
            material["cached_files"] = len(files)
            material["cached_bytes"] = sum(f.stat().st_size for f in files)

        # ---- 成片：素材用量 + 响度 + 验证 ----
        render = key_arts.get("render_output")
        film = {}
        if render and render.get("payload"):
            d = render["payload"]
            tl = d.get("material_timeline") or []
            used = [s["selected_asset"] for s in tl if s.get("selected_asset")]
            film = {
                "output": d.get("output"), "duration_s": d.get("video_duration_s"),
                "render_task": render.get("task_id"),
                "scene_count": d.get("scene_count"), "scenes_with_asset": d.get("scenes_with_asset"),
                "distinct_assets": len({a.get("asset_id") for a in used}),
                "material_mode": d.get("material_mode"),
                "narration_state": d.get("narration_state"),
                "duration_contract": d.get("duration_contract"),
                "video_duration_ok": d.get("video_duration_ok"),
                "audio_loudness": d.get("audio_loudness"),
                "appears_in_film": {s["scene_id"]: s.get("appears_in_film") for s in tl},
                "material_verification": d.get("material_verification"),
                "assembly": (d.get("material_assembly") or {}).get("assembly_class")
                if isinstance(d.get("material_assembly"), dict) else d.get("material_assembly"),
            }
        att = key_arts.get("attribution")
        attribution = {}
        if att and att.get("payload"):
            p = att["payload"]
            attribution = {"entry_count": p.get("entry_count"),
                           "distinct_assets": len(p.get("distinct_assets") or []),
                           "license_classes_used": p.get("license_classes_used"),
                           "restricted_or_unknown_in_film": p.get("restricted_or_unknown_in_film"),
                           "credits_file": p.get("credits_file")}
        verdicts = {}
        for t in ("qa_report", "compliance_output"):
            a = key_arts.get(t)
            if a and a.get("payload"):
                verdicts[t] = a["payload"].get("verdict")
        voice = key_arts.get("voice_output")
        narration = {}
        if voice and voice.get("payload"):
            p = voice["payload"]
            narration = {"status": p.get("status"), "complete": p.get("complete"),
                         "segments": p.get("segments_summary") or len(p.get("segments") or []),
                         "duration_s": p.get("narration_duration_s"),
                         "provider": p.get("provider")}

        return {
            "found": True,
            "project": project,
            "tasks": {"total": len(tasks), "by_status": by_status,
                      "needs_review": [t["task_id"] for t in tasks
                                       if t["status"] == "NEEDS_REVIEW"],
                      "pending": [t["task_id"] for t in tasks if t["status"] == "PENDING"]},
            "problems": problems[:12],
            "artifacts": arts,
            "artifacts_total": sum(a["c"] for a in arts),
            "key_artifacts": {k: {"artifact_id": v["artifact_id"], "path": v["path"],
                                  "sha256": v["sha256"], "size": v["size"],
                                  "summary": (v.get("summary") or "")[:120]}
                              for k, v in key_arts.items()},
            "events": {"by_type": ev_counts, "recent_failures": ev_fail},
            "cost": cost,
            "material": material,
            "film": film,
            "attribution": attribution,
            "verdicts": verdicts,
            "narration": narration,
            "loudness_contract": LOUDNESS_CONTRACT,
        }
    finally:
        con.close()


def _h(title: str) -> str:
    return "\n=== {} ===".format(title)


def format_report(rep: dict, recent_events: int = 8) -> str:
    """把报告数据渲染成人可读文本（纯函数，不访问 DB）。"""
    if not rep.get("found"):
        return "项目不存在: {}".format(rep.get("project_id"))
    p, out = rep["project"], []
    out.append("项目 {} | {} | 状态 {} | 创建 {}".format(
        p["project_id"], p.get("name") or "-", p.get("status") or "-",
        p.get("created_at")))
    out.append("目标: {}".format((p.get("goal") or "")[:150]))

    t = rep["tasks"]
    out.append(_h("任务（{} 个）".format(t["total"])))
    out.append("  " + "  ".join("{}={}".format(k, v) for k, v in
                                sorted(t["by_status"].items(), key=lambda kv: -kv[1])))
    if t["needs_review"]:
        out.append("  待人工审批: {}".format(", ".join(t["needs_review"][:8])))
    if t["pending"]:
        out.append("  未派发: {} 个（如前 8: {}）".format(
            len(t["pending"]), ", ".join(t["pending"][:8])))

    out.append(_h("失败/阻断原因（最近 {} 条）".format(recent_events)))
    if not rep["problems"] and not rep["events"]["recent_failures"]:
        out.append("  （无）")
    for row in rep["problems"][:6]:
        out.append("  [{}] {} {} v{} | {}".format(
            row["status"], row["task_id"], row["task_type"], row.get("version"),
            str(row.get("error") or "")[:160]))
    for e in rep["events"]["recent_failures"][:6]:
        out.append("  事件 {} {} {} | {}".format(e["type"], e["task_id"], int(float(e["ts"])),
                                                str(e.get("error") or "")[:140]))

    out.append(_h("产物（{} 个文件）".format(rep["artifacts_total"])))
    for a in rep["artifacts"][:10]:
        out.append("  {:26s} x{:<5d} {:>12,} bytes".format(a["type"], a["c"], a["bytes"] or 0))
    for k, v in rep["key_artifacts"].items():
        out.append("  [{}] {} ({:,} B, sha {}…)".format(
            k, Path(v["path"]).name, v["size"] or 0, (v["sha256"] or "")[:12]))

    c = rep["cost"]
    out.append(_h("成本（LLM，**估算**）"))
    out.append("  {}".format(c["note"]))
    out.append("  任务行 cost_usd 合计 ≈ ${:.6f} | LLM_CALL 事件 {} 次 | tokens in {:,} / out {:,}"
               .format(c["task_cost_usd_sum"], c["llm_call_events"], c["tokens_in"],
                       c["tokens_out"]))
    if c["by_model"]:
        out.append("  按模型: " + ", ".join("{}≈${:.6f}".format(k, v)
                                            for k, v in sorted(c["by_model"].items())))

    m = rep["material"]
    out.append(_h("外部素材用量（**非计费**）"))
    out.append("  {}".format(m["note"]))
    if "material_mode" in m:
        out.append("  mode={} | 验收候选 {} / 被拒 {} | 原因: {}".format(
            m.get("material_mode"), m.get("external_verified"), m.get("external_rejected"),
            str(m.get("mode_reason") or "")[:110]))
    prov = m.get("provider") or {}
    st = m.get("provider_stats") or {}
    if prov.get("name"):
        out.append("  provider={} configured={} error={}".format(
            prov.get("name"), prov.get("configured"), prov.get("error")))
    if st:
        out.append("  请求 {}（失败 {}）/ 搜索 {} / 命中 {} / 拒绝 {} / 下载 {:,} B / "
                   "缓存命中 {} / 重试 {} / 限流 {} / 耗时 search={}ms download={}ms".format(
                       st.get("requests"), st.get("requests_failed"), st.get("searched"),
                       st.get("fetched"), st.get("rejected"), st.get("downloaded_bytes") or 0,
                       st.get("cache_hits"), st.get("retries"), st.get("rate_limited"),
                       st.get("search_ms"), st.get("download_ms")))
    if m.get("license_classes"):
        out.append("  候选许可类别: {}".format(m["license_classes"]))
    qs = m.get("query_shaping") or {}
    if qs:
        out.append("  查询阶梯: mode={} queries={} attempts={}".format(
            qs.get("mode"), qs.get("queries"),
            [{"q": a.get("query"), "items": a.get("items")}
             for a in (qs.get("attempts") or [])]))
    if "cached_files" in m:
        out.append("  本地缓存: {} 个文件 / {:,} 字节（media/external）".format(
            m["cached_files"], m["cached_bytes"]))

    f = rep["film"]
    out.append(_h("成片与验证"))
    if not f:
        out.append("  （无 render_output：项目未产出成片）")
    else:
        out.append("  成片 {} | 时长 {}s | 镜头 {}/{} 有素材 | 不同素材 {} | 装配 {}".format(
            Path(str(f.get("output"))).name if f.get("output") else "-", f.get("duration_s"),
            f.get("scenes_with_asset"), f.get("scene_count"), f.get("distinct_assets"),
            f.get("assembly")))
        dc = f.get("duration_contract") or {}
        out.append("  时长契约: video_ok={} | timeline={}s narration={}s delta={}s".format(
            f.get("video_duration_ok"), dc.get("timeline_duration_s"),
            dc.get("narration_duration_s"), dc.get("delta_s")))
        al = f.get("audio_loudness") or {}
        if al:
            ct = al.get("contract") or {}
            out.append("  响度: ok={} | 实测 I={} LUFS TP={} dBTP | 目标 {}±{} LU / TP ≤ {} | "
                       "Δ={} LU | 校正 {} 次".format(
                           al.get("ok"), al.get("measured_lufs"),
                           al.get("measured_true_peak_dbtp"), ct.get("target_lufs"),
                           ct.get("tolerance_lu"), ct.get("max_true_peak_dbtp"),
                           al.get("delta_lu"), al.get("corrections")))
            if al.get("reasons"):
                out.append("    不达标原因: {}".format("; ".join(al["reasons"])[:180]))
        mv = f.get("material_verification") or {}
        if mv:
            out.append("  抽帧核验: 方法={} 检查 {} 镜 / 失败 {} 镜{}".format(
                mv.get("method"), len(mv.get("checked_scenes") or []),
                len(mv.get("failed_scenes") or []),
                "（" + str(mv.get("skipped"))[:60] + "）" if mv.get("skipped") else ""))
        out.append("  上屏: " + ", ".join("{}={}".format(k, v)
                                          for k, v in (f.get("appears_in_film") or {}).items()))
    if rep["narration"]:
        n = rep["narration"]
        out.append("  旁白: status={} complete={} 段={} 时长={}s provider={}".format(
            n.get("status"), n.get("complete"), n.get("segments"), n.get("duration_s"),
            n.get("provider")))
    if rep["attribution"]:
        a = rep["attribution"]
        out.append("  署名台账: {} 条 / {} 个素材 / 许可类别 {} / 受限或未知 {}".format(
            a.get("entry_count"), a.get("distinct_assets"), a.get("license_classes_used"),
            a.get("restricted_or_unknown_in_film")))
    if rep["verdicts"]:
        out.append("  质检结论: " + ", ".join("{}={}".format(k, v)
                                              for k, v in rep["verdicts"].items()))
    out.append("")
    out.append("（只读报告：未修改任何状态、未触发任何任务）")
    return "\n".join(out)

# ---- 多模态质量咨询（只读；R4 + R6 落地）----


def format_mm_advisory(quality_json_paths):
    """只读多模态质量咨询：读取多个冻结 Quality JSON（逐项目），返回人读咨询节文本。

    quality_json_paths: str（逗号分隔多路径）或 list。
    不修改任何评估/判定/生产状态；结论仅供人工审阅。
    按项目分组展示 v2 全量 32 例 / 3 项目评估结果，含：
    - 每镜头最终层判定（4-B/5-A/5-D observed verdicts）
    - 层间冲突显式呈现（4-B MATCH vs 5A/5D MISMATCH）
    - 纯色底 fail-closed（零视觉证据）显式呈现
    - 汇总行（域一致 / MISMATCH / UNKNOWN 计数）
    """
    if isinstance(quality_json_paths, str):
        quality_json_paths = [x.strip() for x in quality_json_paths.split(',') if x.strip()]
    all_cases = []
    project_groups = []
    for qp in quality_json_paths:
        fp = Path(qp)
        if not fp.is_file():
            continue
        try:
            d = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        cases = d.get("cases") or []
        pid = d.get("project_id") or "?"
        if not cases:
            continue
        project_groups.append({"project_id": pid, "cases": cases, "source_file": fp.name})
        all_cases.extend(cases)
    if not all_cases:
        return None

    total = len(all_cases)
    status_counts = {"OK": 0, "VIOLATION": 0, "UNRESOLVED": 0}
    verdict_counts = {"MATCH": 0, "MISMATCH": 0, "UNKNOWN": 0}
    conflict_cases = []
    no_evidence_cases = []

    for c in all_cases:
        st = c.get("status", "?")
        if st in status_counts:
            status_counts[st] += 1
        layers = c.get("layers") or {}
        verdicts = {}
        for l in ("4b", "5a", "5d"):
            ev = layers.get(l) or {}
            obs = ev.get("observed") or {}
            v = obs.get("verdict")
            if v:
                verdicts[l] = v
                if v in verdict_counts:
                    verdict_counts[v] += 1
        has_match = "MATCH" in verdicts.values()
        has_mismatch = "MISMATCH" in verdicts.values()
        if has_match and has_mismatch:
            conflict_cases.append({"case_id": c.get("case_id", "?"), "verdicts": verdicts,
                                   "content_label": c.get("content_label", "")})
        if not verdicts and st == "UNRESOLVED":
            no_evidence_cases.append({"case_id": c.get("case_id", "?"),
                                      "content_label": c.get("content_label", "")})

    out = []
    out.append(_h("多模态质量咨询（只读；人工决策依据，非自动阻断）"))
    out.append(f"  覆盖: {total} 例 / {len(project_groups)} 项目")
    out.append(f"  层判定汇总: MATCH={verdict_counts['MATCH']} | MISMATCH={verdict_counts['MISMATCH']} | "
               f"UNKNOWN={verdict_counts['UNKNOWN']} | 无证据(UNRESOLVED)={status_counts.get('UNRESOLVED', 0)}")
    out.append(f"  状态: OK={status_counts.get('OK', 0)} | VIOLATION={status_counts.get('VIOLATION', 0)} | "
               f"UNRESOLVED={status_counts.get('UNRESOLVED', 0)}")
    out.append("  阈值: 未触碰 | UNKNOWN 为合法最终结果")

    for pg in project_groups:
        cases = pg["cases"]
        pid = pg["project_id"]
        out.append(f"  ── {pid} ({len(cases)} 例) ──")
        pg_conflicts = [c for c in conflict_cases if c["case_id"] in
                        {cc.get("case_id") for cc in cases}]
        pg_no_evid = [c for c in no_evidence_cases if c["case_id"] in
                      {cc.get("case_id") for cc in cases}]
        if pg_conflicts:
            out.append("    ⚠️ 层间冲突（需人工裁决）:")
            for c in pg_conflicts:
                vd = c["verdicts"]
                out.append(f"      {c['case_id']}: 4B={vd.get('4b', '?')} / "
                           f"5A={vd.get('5a', '?')} / 5D={vd.get('5d', '?')} → 需人工确认")
        if pg_no_evid:
            out.append("    ⚠️ 零视觉证据（层拒绝发证）:")
            for c in pg_no_evid:
                out.append(f"      {c['case_id']}")
        for c in cases:
            layers = c.get("layers") or {}
            verdicts = {}
            for l in ("4b", "5a", "5d"):
                ev = layers.get(l) or {}
                obs = ev.get("observed") or {}
                v = obs.get("verdict")
                if v:
                    verdicts[l] = v
            marker = ("✅" if c.get("status") == "OK" and verdicts.get("5a") == "MATCH"
                      else "❌" if "MISMATCH" in verdicts.values()
                      else "❓" if c.get("status") == "UNRESOLVED"
                      else "·")
            vd_str = " / ".join(f"{l}={v}" for l, v in sorted(verdicts.items())) if verdicts else "(no evidence)"
            out.append(f"    {marker} {c.get('case_id', '?')} [{c.get('content_label', '?')}] "
                       f"status={c.get('status', '?')} | {vd_str}")

    out.append("  R6 top-1 一致性: 仅展示，非判据（样本小，见 #47）")
    out.append("  （只读咨询：人工决策依据，非自动阻断；不触发任何生产动作）")
    return chr(10).join(out)
