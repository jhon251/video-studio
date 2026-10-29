"""Phase 2-C 可追溯性证据生成器：逐镜头决策记录 + 与成片证据一致性核对。

数据来源（全部是真实产物）：
  · 真实 LLM 项目（默认 p_ab2b352e06b8）的 render_output.material_timeline / scene_evidence
  · 故障矩阵四个项目（logs/phase2c_fault_matrix.json）：正常命中 / 无候选 / 低匹配 / 不可用

输出：
  · logs/phase2c_traceability.json  （机器可读）
  · logs/phase2c_traceability.md    （人工可读表 + 一致性结论）

用法：python docs/regression_2x/phase2c_trace.py [real_project_id]
"""
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"C:\mp4agent\video-studio")
LOGS = ROOT / "docs" / "regression_2x" / "logs"
REQUIRED_FIELDS = ("scene_id", "original_requirement", "candidates", "selected_asset",
                   "insufficiency_class", "fallback_state", "fallback_reason",
                   "selection_reason", "needs_hitl", "allowed_in_final_render",
                   "start_s", "end_s", "entered_timeline")
PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(("PASS  " if ok else "FAIL  ") + name + (" | " + str(detail)[:200] if detail else ""))


def db():
    con = sqlite3.connect(str(ROOT / "projects" / "video_studio.db"))
    con.row_factory = sqlite3.Row
    return con


def latest_render(pid):
    con = db()
    r = con.execute("select path from artifacts where project_id=? and type='render_output' "
                    "order by created_at desc limit 1", (pid,)).fetchone()
    con.close()
    return json.loads(Path(r["path"]).read_text(encoding="utf-8")) if r else None


def timeline_event(pid):
    con = db()
    r = con.execute("select payload from events where project_id=? and type='MATERIAL_TIMELINE' "
                    "order by ts desc limit 1", (pid,)).fetchone()
    con.close()
    return json.loads(r["payload"]) if r else None


def probe(path):
    p = subprocess.run([str(ROOT / "bin" / "ffprobe.exe"), "-v", "error", "-print_format", "json",
                        "-show_format", "-show_streams", str(path)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return json.loads(p.stdout or "{}")


def trace_project(res, label, pid, expectations):
    """核对一个项目的逐镜头可追溯记录与成片证据。

    expectations: {"must_states": {state: 最少镜头数}, "require_normal_frame_proof": bool,
                   "require_degraded_evidence": bool}
    """
    d = latest_render(pid)
    ev = timeline_event(pid)
    if d is None:
        # 阻断项目：追溯记录在 render 前的 MATERIAL_TIMELINE 事件里
        check("{}: 阻断项目有 render 前追溯记录".format(label), bool(ev and ev.get("decisions")))
        check("{}: 事件记录装配级分类为 ASSEMBLY_BLOCKED".format(label),
              (ev or {}).get("assembly_class") == "ASSEMBLY_BLOCKED",
              (ev or {}).get("assembly_class"))
        res["projects"].append({"label": label, "project": pid, "blocked": True,
                                "event_decisions": (ev or {}).get("decisions"),
                                "assembly_class": (ev or {}).get("assembly_class")})
        return
    tl = d.get("material_timeline") or []
    evd = {e["scene_id"]: e for e in tl}
    check("{}: 每个镜头都有完整决策记录".format(label),
          all(set(REQUIRED_FIELDS) <= set(s) for s in tl), len(tl))
    check("{}: 每个镜头都有候选与分数（或明确无候选）".format(label),
          all(isinstance(s.get("candidates"), list) for s in tl))
    check("{}: fallback_reason 与 selection_reason 均非空".format(label),
          all(s.get("fallback_reason") and s.get("selection_reason") for s in tl))
    check("{}: 正常命中镜头都带 asset_id/path/sha256/bytes".format(label),
          all((s["selected_asset"] or {}).get("sha256") and (s["selected_asset"] or {}).get("path")
              and (s["selected_asset"] or {}).get("bytes")
              for s in tl if s["fallback_state"] == "LOCAL_INGEST"))
    check("{}: 占位镜头 selected_asset 必须为 null（未伪造素材）".format(label),
          all(s["selected_asset"] is None for s in tl
              if s["fallback_state"] == "SOLID_COLOR_CARD"))
    mv = d.get("material_verification") or {}
    check("{}: 成片抽帧核验已执行（非 SKIPPED）".format(label), not mv.get("skipped"),
          mv.get("skipped"))
    check("{}: 核验未发现『分配素材未上屏』".format(label), not mv.get("failed_scenes"),
          mv.get("failed_scenes"))
    check("{}: appears_in_film 与抽帧证据一致".format(label),
          all((s.get("appears_in_film") is None and (s.get("film_evidence") or {}).get("match") is None)
              or s.get("appears_in_film") == (s.get("film_evidence") or {}).get("match")
              for s in tl))
    for state, min_n in (expectations.get("must_states") or {}).items():
        got = [s for s in tl if s["fallback_state"] == state]
        check("{}: 至少 {} 个镜头为 {}".format(label, min_n, state), len(got) >= min_n, len(got))
    normal = [s for s in tl if s["fallback_state"] == "LOCAL_INGEST" and s.get("appears_in_film")]
    degraded = [s for s in tl if s["fallback_state"] != "LOCAL_INGEST"]
    deg_with_asset = [s for s in degraded if s.get("selected_asset") and s.get("appears_in_film")]
    deg_placeholder = [s for s in degraded if not s.get("selected_asset")
                       and s["scene_id"] in (mv.get("placeholder_verified") or [])]
    if expectations.get("require_normal_frame_proof"):
        check("{}: 至少 1 个正常素材被抽帧证实上屏".format(label), bool(normal),
              [s["scene_id"] for s in normal[:3]])
    if expectations.get("require_degraded_evidence"):
        check("{}: 至少 1 个降级镜头有真实证据（降级素材上屏 或 占位被证实）".format(label),
              bool(deg_with_asset or deg_placeholder),
              {"asset_on_screen": [s["scene_id"] for s in deg_with_asset],
               "placeholder_verified": [s["scene_id"] for s in deg_placeholder]})
    if expectations.get("expect_no_degraded"):
        check("{}: 本项目无降级镜头（全部正常命中）".format(label), not degraded,
              [s["scene_id"] for s in degraded])
    video = d.get("output")
    info = probe(video) if video and Path(video).is_file() else {}
    dec = subprocess.run([str(ROOT / "bin" / "ffmpeg.exe"), "-v", "error", "-i", str(video),
                          "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8",
                         errors="replace") if video else None
    res["projects"].append({
        "label": label, "project": pid, "blocked": False,
        "video": {"path": video, "bytes": Path(video).stat().st_size if video else None,
                  "duration_s": (info.get("format") or {}).get("duration"),
                  "streams": len(info.get("streams") or []),
                  "decode_rc": dec.returncode if dec else None},
        "assembly": d.get("material_assembly"), "insufficiency_summary": d.get("insufficiency_summary"),
        "material_verification": mv,
        "scenes": [{k: s.get(k) for k in REQUIRED_FIELDS + ("appears_in_film", "film_evidence",
                                                            "insufficiency_class",
                                                            "fallback_action")} for s in tl]})


def main():
    real_pid = sys.argv[1] if len(sys.argv) > 1 else "p_ab2b352e06b8"
    res = {"real_project": real_pid, "projects": [], "checks": {}}
    print("=== 真实 LLM 项目（12 镜头）===")
    trace_project(res, "real_12scene", real_pid,
                  {"must_states": {"LOCAL_INGEST": 12}, "require_normal_frame_proof": True,
                   "require_degraded_evidence": False, "expect_no_degraded": True})
    fm = LOGS / "phase2c_fault_matrix.json"
    if fm.is_file():
        for case in json.loads(fm.read_text(encoding="utf-8")):
            print("\n=== 故障矩阵 {} ===".format(case["case"]))
            if case["case"].startswith("A"):
                exp = {"must_states": {"LOCAL_INGEST": 1, "SOLID_COLOR_CARD": 1},
                       "require_normal_frame_proof": True, "require_degraded_evidence": True}
            elif case["case"].startswith("C"):
                exp = {"must_states": {"THEME_FALLBACK": 1, "SOLID_COLOR_CARD": 1},
                       "require_normal_frame_proof": False, "require_degraded_evidence": True}
            else:
                exp = {"must_states": {}}
            trace_project(res, case["case"], case["project"], exp)
    res["checks"] = {"pass": PASS, "fail": FAIL}
    (LOGS / "phase2c_traceability.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    md = ["# Phase 2-C 可追溯性证据（自动生成）", "",
          "核对项：{} 通过 / {} 失败".format(len(PASS), len(FAIL)), ""]
    if FAIL:
        md += ["## 失败项", ""] + ["- " + f for f in FAIL] + [""]
    md += ["## 通过项", ""] + ["- " + p for p in PASS] + [""]
    md += ["## 逐镜头决策（真实项目）", ""]
    real = next((p for p in res["projects"] if p["label"] == "real_12scene"), None)
    if real and not real.get("blocked"):
        md += ["| 镜头 | 窗口(s) | 诊断 | 动作 | 素材 | 分数 | HITL | 可渲染 | 上屏(证据) | 原因 |",
               "|---|---|---|---|---|---|---|---|---|---|"]
        for s in real["scenes"]:
            cands = s.get("candidates") or []
            score = cands[0].get("match_score") if cands else None
            md.append("| {} | {}-{} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
                s["scene_id"], s["start_s"], s["end_s"], s["insufficiency_class"],
                s["fallback_state"], (s.get("selected_asset") or {}).get("name") or "—", score,
                s["needs_hitl"], s["allowed_in_final_render"],
                "{} (corr={})".format(s["appears_in_film"], (s.get("film_evidence") or {}).get("corr"))
                if s.get("appears_in_film") is not None else "占位已证实" if s["fallback_state"]
                == "SOLID_COLOR_CARD" else "—",
                str(s.get("fallback_reason"))[:60]))
    md += ["", "## 各项目结论", ""]
    for p in res["projects"]:
        if p.get("blocked"):
            md.append("- **{}**（阻断）：assembly_class={}；追溯记录见 render 前 `MATERIAL_TIMELINE` 事件"
                      .format(p["label"], p.get("assembly_class")))
        else:
            v = p["video"]
            md.append("- **{}**：assembly={}；成片 {} bytes / {}s / {} 流 / decode_rc={}；"
                      "抽帧核验 checked={} placeholder={} failed={}".format(
                          p["label"], p.get("assembly"), v["bytes"], v["duration_s"], v["streams"],
                          v["decode_rc"], (p.get("material_verification") or {}).get("checked_scenes"),
                          (p.get("material_verification") or {}).get("placeholder_verified"),
                          (p.get("material_verification") or {}).get("failed_scenes")))
    (LOGS / "phase2c_traceability.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
    if FAIL:
        print("失败项:", FAIL)
    print("记录:", LOGS / "phase2c_traceability.md")
    return 0 if not FAIL else 1


if __name__ == "__main__":
    sys.exit(main())
