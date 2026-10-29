"""4.x Phase 4-A：只读质量/成本指标（metrics）。

口径（与 3-C 的成本边界文档一致，禁止混算）：
  · `llm`：**估算**（token×价目表；客户端无账单接口）——事件内成本与任务行成本分列，不合并成"账单"；
  · `material`：外部素材**用量**（请求/下载字节/限流/缓存），**不是金额**（Wikimedia 免费）；
  · `quality`：候选有效率、上屏率、时长/响度契约、旁白完整性；
  · `semantics`：4-B 验证器的三态计数（MATCH/MISMATCH/UNKNOWN）；
  · `human`：人工介入（待审批任务、审批事件、阻断/失败任务数）。

只读保证：数据库以 `mode=ro` 打开；只读产物 JSON 文件；**不调用引擎**、不派发任务、不写任何东西。
**确定性**：输出不含时间戳、列表按固定键排序 → 同一数据两次运行**逐字节一致**（可复核）。
"""
from __future__ import annotations

import json
from pathlib import Path

from ..core.semantics import load_lexicon, verify_scenes
from .report import _art, _fetch, _one, readonly_connection


def _num(x) -> float:
    try:
        return float(x or 0)
    except (TypeError, ValueError):
        return 0.0


def project_metrics(db_path: str | Path, project_id: str,
                    project_dir: Path | None = None, lexicon: dict | None = None) -> dict:
    """单个项目的指标（只读）。项目不存在 → {"found": False}。"""
    con = readonly_connection(db_path)
    try:
        project = _one(con, "select project_id, name, goal, status from projects where project_id=?",
                       (project_id,))
        if project is None:
            return {"found": False, "project_id": project_id}
        tasks = _fetch(con, "select task_id, task_type, status, cost_usd, model_used from tasks "
                            "where project_id=?", (project_id,))
        by_status: dict[str, int] = {}
        for t in tasks:
            by_status[t["status"]] = by_status.get(t["status"], 0) + 1
        llm_rows = _fetch(con, "select payload from events where project_id=? and type='LLM_CALL'",
                          (project_id,))
        ev = _fetch(con, "select type, count(*) c from events where project_id=? group by type",
                    (project_id,))
        ev_by_type = {r["type"]: r["c"] for r in ev}
        retr = _art(con, project_id, "retrieval_candidates")
        render = _art(con, project_id, "render_output")
        att = _art(con, project_id, "attribution")
        script = _art(con, project_id, "script_output")
        voice = _art(con, project_id, "voice_output")
    finally:
        con.close()

    tin = tout = 0
    ev_cost = 0.0
    for r in llm_rows:
        try:
            p = json.loads(r["payload"]) or {}
        except (json.JSONDecodeError, TypeError):
            continue
        u = p.get("usage") or p
        tin += int(u.get("prompt_tokens") or u.get("tokens_in") or 0)
        tout += int(u.get("completion_tokens") or u.get("tokens_out") or 0)
        ev_cost += _num(p.get("cost_usd") or u.get("cost_usd"))
    by_model: dict[str, float] = {}
    for t in tasks:
        c = _num(t.get("cost_usd"))
        if c > 0:
            m = t.get("model_used") or "unknown"
            by_model[m] = round(by_model.get(m, 0.0) + c, 6)

    material: dict = {"billing": False}
    if retr and retr.get("payload"):
        p = retr["payload"]
        stats = ((p.get("external_provider") or {}).get("stats") or {})
        material.update({
            "mode": p.get("material_mode"),
            "external_requested": p.get("external_requested"),
            "candidates_total": p.get("candidates_total"),
            "external_verified": p.get("external_verified"),
            "external_rejected": len(p.get("external_rejected") or []),
            "requests": stats.get("requests"), "requests_failed": stats.get("requests_failed"),
            "downloaded_bytes": stats.get("downloaded_bytes"), "rate_limited": stats.get("rate_limited"),
            "retries": stats.get("retries"), "cache_hits": stats.get("cache_hits"),
            "license_classes": stats.get("license_classes"),
            "query_shaping_mode": (stats.get("query_shaping") or {}).get("mode"),
        })

    timeline: dict = {}
    on_screen: dict = {}
    contracts: dict = {}
    narration: dict = {}
    semantic_items: list[dict] = []
    if render and render.get("payload"):
        d = render["payload"]
        tl = d.get("material_timeline") or []
        used = [s["selected_asset"] for s in tl if s.get("selected_asset")]
        with_asset = len(used)
        distinct = len({a.get("asset_id") for a in used})
        timeline = {"scenes": len(tl), "scenes_with_asset": with_asset,
                    "distinct_assets": distinct,
                    "reuse_ratio": (round(1 - distinct / with_asset, 4) if with_asset else None),
                    "fallback_scenes": len(tl) - with_asset}
        appears = [s.get("appears_in_film") for s in tl if s.get("appears_in_film") is not None]
        corrs = [(s.get("film_evidence") or {}).get("corr_expected") for s in tl]
        corrs = [c for c in corrs if isinstance(c, (int, float))]
        on_screen = {"verified_true": sum(1 for a in appears if a is True),
                     "verified_false": sum(1 for a in appears if a is False),
                     "verdicts": len(appears),
                     "rate": (round(sum(1 for a in appears if a is True) / len(appears), 4)
                              if appears else None),
                     "corr_min": (min(corrs) if corrs else None),
                     "corr_mean": (round(sum(corrs) / len(corrs), 4) if corrs else None)}
        dc = d.get("duration_contract") or {}
        al = d.get("audio_loudness") or {}
        ct = al.get("contract") or {}
        contracts = {
            "duration_ok": d.get("video_duration_ok"),
            "timeline_s": dc.get("timeline_duration_s"), "video_s": d.get("video_duration_s"),
            "duration_delta_s": (None if d.get("video_duration_s") is None
                                 or dc.get("timeline_duration_s") is None
                                 else round(_num(d.get("video_duration_s"))
                                            - _num(dc.get("timeline_duration_s")), 3)),
            "loudness_ok": al.get("ok"), "lufs": al.get("measured_lufs"),
            "true_peak_dbtp": al.get("measured_true_peak_dbtp"),
            "loudness_delta_lu": al.get("delta_lu"), "loudness_corrections": al.get("corrections"),
            "loudness_target_lufs": ct.get("target_lufs"),
            "loudness_tolerance_lu": ct.get("tolerance_lu"),
        }
        segs = ((script or {}).get("payload") or {}).get("segments") or []
        for i, s in enumerate(tl):
            a = s.get("selected_asset") or {}
            seg = segs[i] if i < len(segs) else {}
            semantic_items.append({
                "scene_id": s.get("scene_id"),
                "query_text": s.get("retrieval_query") or seg.get("narration") or "",
                "narration": seg.get("narration"),
                "asset_name": a.get("name"),
                "asset": {"asset_id": a.get("asset_id"), "name": a.get("name"),
                          "provider": a.get("provider"),
                          "license_class": a.get("license_class"),
                          "appears_in_film": s.get("appears_in_film")},
            })
    if voice and voice.get("payload"):
        vp = voice["payload"]
        narration = {"state": vp.get("status"), "complete": vp.get("complete"),
                     "segments": len(vp.get("segments") or []),
                     "duration_s": vp.get("narration_duration_s"), "provider": vp.get("provider")}

    semantics: dict = {}
    if semantic_items:
        r = verify_scenes(semantic_items, lexicon=lexicon or load_lexicon())
        semantics = {"counts": r["counts"], "scene_count": r["scene_count"],
                     "version": r["version"], "lexicon_sha256": r["lexicon_sha256"],
                     "mismatch_scenes": [s["scene_id"] for s in r["scenes"]
                                         if s["verdict"] == "MISMATCH"],
                     "unknown_scenes": [s["scene_id"] for s in r["scenes"]
                                        if s["verdict"] == "UNKNOWN"]}

    att_summary = {}
    if att and att.get("payload"):
        ap = att["payload"]
        att_summary = {"entries": ap.get("entry_count"),
                       "license_classes_used": ap.get("license_classes_used"),
                       "restricted_or_unknown": ap.get("restricted_or_unknown_in_film")}

    return {
        "found": True, "schema": "metrics-v1", "project": project,
        "llm": {"estimate": True, "note": "token×价目表估算；无账单接口",
                "task_cost_usd_sum": round(sum(_num(t.get("cost_usd")) for t in tasks), 6),
                "llm_call_events": len(llm_rows), "tokens_in": tin, "tokens_out": tout,
                "llm_event_cost_usd_sum": round(ev_cost, 6), "by_model": dict(sorted(by_model.items()))},
        "material": {k: material[k] for k in sorted(material)},
        "timeline": timeline, "on_screen": on_screen, "contracts": contracts,
        "narration": narration, "semantics": semantics, "attribution": att_summary,
        "human": {"tasks_total": len(tasks), "by_status": dict(sorted(by_status.items())),
                  "needs_review": by_status.get("NEEDS_REVIEW", 0),
                  "blocked": by_status.get("BLOCKED", 0), "failed": by_status.get("FAILED", 0),
                  "events_needs_review": ev_by_type.get("TASK_NEEDS_REVIEW", 0),
                  "events_review_decided": ev_by_type.get("REVIEW_DECIDED", 0),
                  "events_claim_reviewed": ev_by_type.get("CLAIM_REVIEWED", 0)},
        "artifacts": {"render_output": (render or {}).get("artifact_id"),
                      "attribution": (att or {}).get("artifact_id"),
                      "retrieval_candidates": (retr or {}).get("artifact_id")},
    }


def corpus_metrics(db_path: str | Path, base_dir: Path, limit: int = 0,
                   lexicon: dict | None = None) -> dict:
    """全库汇总（只读）：只统计有 render_output 的项目，逐项目指标 + 合计（排序确定 → 输出确定）。"""
    con = readonly_connection(db_path)
    try:
        pids = [r["project_id"] for r in con.execute(
            "select distinct project_id from artifacts where type='render_output' "
            "order by project_id")]
    finally:
        con.close()
    if limit:
        pids = pids[-int(limit):]
    rows = []
    for pid in pids:
        m = project_metrics(db_path, pid, project_dir=base_dir / pid, lexicon=lexicon)
        if m.get("found"):
            rows.append(m)
    agg = {"projects": len(rows), "scenes": 0, "scenes_with_asset": 0, "distinct_assets": 0,
           "on_screen_true": 0, "on_screen_verdicts": 0, "mismatch": 0, "match": 0, "unknown": 0,
           "duration_ok": 0, "loudness_ok": 0, "loudness_measured": 0,
           "downloaded_bytes": 0, "rate_limited": 0, "requests": 0,
           "llm_cost_usd_estimate": 0.0, "llm_calls": 0}
    for m in rows:
        agg["scenes"] += m["timeline"].get("scenes") or 0
        agg["scenes_with_asset"] += m["timeline"].get("scenes_with_asset") or 0
        agg["distinct_assets"] += m["timeline"].get("distinct_assets") or 0
        agg["on_screen_true"] += m["on_screen"].get("verified_true") or 0
        agg["on_screen_verdicts"] += m["on_screen"].get("verdicts") or 0
        sc = (m["semantics"].get("counts") or {})
        agg["match"] += sc.get("MATCH", 0)
        agg["mismatch"] += sc.get("MISMATCH", 0)
        agg["unknown"] += sc.get("UNKNOWN", 0)
        agg["duration_ok"] += 1 if m["contracts"].get("duration_ok") else 0
        if m["contracts"].get("loudness_ok") is not None:
            agg["loudness_measured"] += 1
            agg["loudness_ok"] += 1 if m["contracts"].get("loudness_ok") else 0
        agg["downloaded_bytes"] += int(m["material"].get("downloaded_bytes") or 0)
        agg["rate_limited"] += int(m["material"].get("rate_limited") or 0)
        agg["requests"] += int(m["material"].get("requests") or 0)
        agg["llm_cost_usd_estimate"] = round(
            agg["llm_cost_usd_estimate"] + m["llm"]["task_cost_usd_sum"], 6)
        agg["llm_calls"] += m["llm"]["llm_call_events"]
    agg["on_screen_rate"] = (round(agg["on_screen_true"] / agg["on_screen_verdicts"], 4)
                             if agg["on_screen_verdicts"] else None)
    agg["semantic_mismatch_rate"] = (round(agg["mismatch"] / (agg["match"] + agg["mismatch"]
                                                              + agg["unknown"]), 4)
                                     if (agg["match"] + agg["mismatch"] + agg["unknown"]) else None)
    return {"found": True, "schema": "metrics-v1-corpus", "aggregate": agg,
            "projects": [{"project_id": m["project"]["project_id"],
                          "scenes": m["timeline"].get("scenes"),
                          "semantics": m["semantics"].get("counts"),
                          "loudness_ok": m["contracts"].get("loudness_ok")} for m in rows]}


def _scene_inputs(con, project_id: str) -> list[dict]:
    """装配 4-B 验证器所需的逐镜头输入（只读）：匹配口径文本 + 旁白 + 所选素材。"""
    render = _art(con, project_id, "render_output")
    script = _art(con, project_id, "script_output")
    segs = ((script or {}).get("payload") or {}).get("segments") or []
    tl = ((render or {}).get("payload") or {}).get("material_timeline") or []
    items = []
    for i, s in enumerate(tl):
        a = s.get("selected_asset") or {}
        seg = segs[i] if i < len(segs) else {}
        items.append({
            "scene_id": s.get("scene_id"),
            "query_text": s.get("retrieval_query") or seg.get("narration") or "",
            "narration": seg.get("narration"),
            "asset_name": a.get("name"),
            "asset": {"asset_id": a.get("asset_id"), "name": a.get("name"),
                      "provider": a.get("provider"),
                      "license_class": a.get("license_class"),
                      "appears_in_film": s.get("appears_in_film")},
        })
    return items


def _art_by_id(con, artifact_id: str) -> dict | None:
    """按 artifact_id 取产物（只读；含 payload）。用于把判定**钉在某一版历史产物**上
    （append-only：旧产物仍在，4-C 替换后可对 3-A 那一版复核真值表）。"""
    row = _one(con, "select * from artifacts where artifact_id=?", (artifact_id,))
    if not row:
        return None
    try:
        row["payload"] = json.loads(Path(row["path"]).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        row["payload"] = None
    return row


def semantic_report(db_path: str | Path, project_id: str, lexicon: dict | None = None,
                    artifact_id: str | None = None) -> dict:
    """单项目的 4-B 语义核验报告（只读；含逐镜头规则 ID、理由与信号）。

    `artifact_id` 给定时，判定针对**该版 render_output**（而非最新一版）——用于把历史真值表钉住。
    """
    con = readonly_connection(db_path)
    try:
        project = _one(con, "select project_id, name, status from projects where project_id=?",
                       (project_id,))
        if project is None:
            return {"found": False, "project_id": project_id}
        if artifact_id:
            render = _art_by_id(con, artifact_id)
            script = _art(con, project_id, "script_output")
            segs = ((script or {}).get("payload") or {}).get("segments") or []
            tl = ((render or {}).get("payload") or {}).get("material_timeline") or []
            items = []
            for i, s in enumerate(tl):
                a = s.get("selected_asset") or {}
                seg = segs[i] if i < len(segs) else {}
                items.append({"scene_id": s.get("scene_id"),
                              "query_text": s.get("retrieval_query") or seg.get("narration") or "",
                              "narration": seg.get("narration"), "asset_name": a.get("name"),
                              "asset": {"asset_id": a.get("asset_id"), "name": a.get("name"),
                                        "provider": a.get("provider"),
                                        "license_class": a.get("license_class"),
                                        "appears_in_film": s.get("appears_in_film")}})
        else:
            items = _scene_inputs(con, project_id)
    finally:
        con.close()
    rep = verify_scenes(items, lexicon=lexicon or load_lexicon())
    rep["found"] = True
    rep["project"] = project
    if artifact_id:
        rep["pinned_artifact"] = artifact_id
    return rep


def format_metrics(m: dict) -> str:
    """人可读渲染（纯函数）。"""
    if not m.get("found"):
        return "项目不存在: {}".format(m.get("project_id"))
    if m.get("schema") == "metrics-v1-corpus":
        a = m["aggregate"]
        lines = ["全库指标（{} 个含成片的项目）".format(a["projects"]),
                 "  镜头 {}（有素材 {}）/ 不同素材 {} | 上屏 {}/{}（rate={}）".format(
                     a["scenes"], a["scenes_with_asset"], a["distinct_assets"],
                     a["on_screen_true"], a["on_screen_verdicts"], a["on_screen_rate"]),
                 "  语义核验：MATCH={} MISMATCH={} UNKNOWN={}（mismatch_rate={}）".format(
                     a["match"], a["mismatch"], a["unknown"], a["semantic_mismatch_rate"]),
                 "  时长契约通过 {}/{} | 响度达标 {}/{}（已测 {}）".format(
                     a["duration_ok"], a["projects"], a["loudness_ok"], a["projects"],
                     a["loudness_measured"]),
                 "  外部素材用量：请求 {} / 下载 {:,} B / 限流 {}".format(
                     a["requests"], a["downloaded_bytes"], a["rate_limited"]),
                 "  LLM 成本**估算**：${:.6f}（{} 次 LLM_CALL）".format(
                     a["llm_cost_usd_estimate"], a["llm_calls"])]
        return "\n".join(lines)
    p = m["project"]
    c, t, o, mat, nar = m["contracts"], m["timeline"], m["on_screen"], m["material"], m["narration"]
    sem = m["semantics"] or {}
    lines = [
        "项目 {} | {} | 状态 {}".format(p["project_id"], p.get("name") or "-", p.get("status")),
        "  质量：镜头 {}（有素材 {}）/ 不同素材 {} | 上屏 {}/{}（rate={}）| corr min={} mean={}".format(
            t.get("scenes"), t.get("scenes_with_asset"), t.get("distinct_assets"),
            o.get("verified_true"), o.get("verdicts"), o.get("rate"),
            o.get("corr_min"), o.get("corr_mean")),
        "  契约：时长 ok={}（timeline={}s video={}s Δ={}s）| 响度 ok={} I={} LUFS TP={} dBTP "
        "Δ={} LU 校正 {} 次".format(
            c.get("duration_ok"), c.get("timeline_s"), c.get("video_s"), c.get("duration_delta_s"),
            c.get("loudness_ok"), c.get("lufs"), c.get("true_peak_dbtp"),
            c.get("loudness_delta_lu"), c.get("loudness_corrections")),
        "  旁白：state={} complete={} 段={} 时长={}s".format(
            nar.get("state"), nar.get("complete"), nar.get("segments"), nar.get("duration_s")),
        "  语义核验（v1，离线三态）：{} | MISMATCH={} | UNKNOWN={} | lexicon {}".format(
            sem.get("counts"), sem.get("mismatch_scenes"), sem.get("unknown_scenes"),
            (sem.get("lexicon_sha256") or "")[:12]),
        "  外部素材：mode={} 候选={} 通过={} 被拒={} 请求={} 下载={:,} B 限流={}".format(
            mat.get("mode"), mat.get("candidates_total"), mat.get("external_verified"),
            mat.get("external_rejected"), mat.get("requests"),
            int(mat.get("downloaded_bytes") or 0), mat.get("rate_limited")),
        "  LLM 成本**估算**：${:.6f}（任务行）| 事件 {} 次 / tokens in {} out {} | 按模型 {}".format(
            m["llm"]["task_cost_usd_sum"], m["llm"]["llm_call_events"], m["llm"]["tokens_in"],
            m["llm"]["tokens_out"], m["llm"]["by_model"] or "{}"),
        "  人工：待审 {} / 阻断 {} / 失败 {} | 审批事件 {} 次".format(
            m["human"]["needs_review"], m["human"]["blocked"], m["human"]["failed"],
            m["human"]["events_review_decided"]),
        "（只读指标：未修改任何状态、未触发任务）",
    ]
    return "\n".join(lines)
