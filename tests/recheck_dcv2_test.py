# -*- coding: utf-8 -*-
"""6-G §4 —— `pi_recheck` 口径对齐的**防回归测试**（冻结阈值未改 + DCv2 对齐 + 向后兼容）。

用法: python tests/recheck_dcv2_test.py
"""
import hashlib
import json
import pathlib
import sys

R = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import captions as core_captions              # noqa: E402
from video_studio.core import execution as EX                        # noqa: E402
from video_studio.core import integrity as core_integrity            # noqa: E402
from video_studio.ops import execution as OPX                        # noqa: E402

L = R / "docs" / "regression_2x" / "logs"
P2 = json.loads((L / "phase6f_rebuild_plan_v2.json").read_text(encoding="utf-8"))
N0 = json.loads((L / "phase6g_n0_dcv2_master.json").read_text(encoding="utf-8"))
B1 = json.loads((L / "phase6g_exec_batch1.json").read_text(encoding="utf-8"))
FF, FP = str(R / "bin" / "ffmpeg.exe"), str(R / "bin" / "ffprobe.exe")
sb = R / B1["sandbox"]
PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name, "" if ok else str(detail)[:200]))


# ---------------- A. 冻结阈值**未被修改**（防"放宽门禁"）
dp, gp = core_integrity.DEFAULT_POLICY, core_integrity.DEFAULT_GATE_POLICY
check("A1 PI 阈值冻结未改（drift 5.0 / 覆盖 0.90 / 静音比 0.10 / orphan 0.02）",
      dp["max_segment_drift_s"] == 5.0 and dp["min_narration_coverage"] == 0.9
      and dp["max_silence_ratio"] == 0.10 and dp["max_orphan_share"] == 0.02,
      {k: dp[k] for k in ("max_segment_drift_s", "min_narration_coverage",
                          "max_silence_ratio", "max_orphan_share")})
check("A2 门禁策略未改（block_on_unknown=True / 未新增绕过开关）",
      gp["block_on_unknown"] is True and gp["gate_enabled"] is True
      and gp["post_render_enabled"] is True and gp.get("post_gate_disabled") is None)
check("A3 执行门禁仍要求人工审批（无审批 ⇒ BLOCKED_UNAPPROVED）",
      EX.gate_execution({"proposal_id": "x", "action": "split_scene",
                         "affected_scope": {"scenes": ["S01"], "window": [0, 10]}},
                        [], None)["code"] == "BLOCKED_UNAPPROVED")

# ---------------- B. DCv2 上下文：recheck 采用 DCv2 口径
chain = P2["remapping_21_segments"]
tl = [{"scene_id": c["scene_id"], "start_s": c["new_timeline_window_s"][0],
       "end_s": c["new_timeline_window_s"][1]} for c in chain]
cw = [{"scene_id": c["scene_id"], "start_s": c["new_audio_window_s"][0],
       "end_s": c["new_audio_window_s"][1]} for c in chain]
art = {"script_output": str(sb / "artifacts" / "script_output.json"),
       "voice_output": str(sb / "artifacts" / "voice_output.json")}
script = json.loads(pathlib.Path(art["script_output"]).read_text(encoding="utf-8"))
cues = core_captions.build_cues(
    [{"narration": s["narration"], "duration_s": s.get("duration_s")}
     for s in script["segments"] if str(s.get("narration", "")).strip()],
    windows=[{"start_s": w["start_s"], "end_s": w["end_s"]} for w in cw])
film_rel = B1["stages"][-1]["output"]["path"]
base = {"config": {"tools": {"ffmpeg": {"path": FF, "ffprobe": FP}}}, "root": str(R),
        "film": str(R / film_rel), "artifacts": art, "cues": cues, "timeline_duration_s": 978.656,
        "timeline": [dict(e) for e in tl]}
ctx2 = OPX.attach_dcv2_time_base(base, timeline=tl, caption_windows=cw,
                                 production_duration_s=978.656,
                                 source="tests/recheck_dcv2_test.py")
r2 = OPX.pi_recheck(ctx2, {"proposal_id": "T-DCV2", "action": "add_visual_aid",
                           "affected_scope": {"scenes": ["S05"], "window": [181.776, 221.862]}},
                    {"outputs": [{"path": film_rel}]})
check("B1 DCv2 上下文：pi_gate_outcome == PASS", r2["pi_gate_outcome"] == "PASS", r2["pi_gate_outcome"])
check("B2 PI-6 槽位 = DCv2 权威链自洽性（G-SEG）且 PASS",
      r2["pi_metrics"]["PI-6"]["state"] == "PASS", r2["pi_metrics"]["PI-6"])
check("B3 旧 declared↔actual 漂移**保留单列**且标为 PLANNING_DRIFT（非阻断）",
      bool(r2.get("pi_legacy_declared_drift"))
      and "PI-6-legacy-declared-drift" in r2["pi_legacy_declared_drift"]
      and "PLANNING_DRIFT" in r2["pi_metrics"] and r2["planning_drift_blocking"] is False
      and r2["pi_contract"].startswith("audio_time_base_v2"),
      {"legacy": r2.get("pi_legacy_declared_drift"), "contract": r2["pi_contract"],
       "planning_drift": r2["pi_metrics"].get("PLANNING_DRIFT")})
check("B4 非阻断诊断不进入 pi_failed",
      "PI-6-legacy-declared-drift" not in r2["pi_failed"], r2["pi_failed"])
check("B5 pre/post 门禁均未阻断", r2["pre_render_gate"]["blocked"] is False
      and r2["post_render_gate"]["blocked"] is False,
      {"pre": r2["pre_render_gate"], "post": r2["post_render_gate"]})

# ---------------- C. 向后兼容：legacy 上下文行为与修改前一致（仍按旧口径 BLOCKED）
r1 = OPX.pi_recheck(base, {"proposal_id": "T-LEGACY", "action": "split_scene",
                           "affected_scope": {"scenes": [], "window": None}},
                    {"outputs": [{"path": film_rel}]})
check("C1 legacy 上下文仍按旧口径 BLOCKED（PI-6 declared 漂移）",
      r1["pi_gate_outcome"] == "BLOCKED" and r1["pi_failed"] == ["PI-6"]
      and r1["pi_contract"].startswith("timeline_authoritative_v1"),
      {"outcome": r1["pi_gate_outcome"], "failed": r1["pi_failed"], "contract": r1["pi_contract"]})
check("C2 legacy 上下文不含 DCv2 诊断键（痕迹分离）",
      "PI-6-legacy-declared-drift" not in r1 and "PLANNING_DRIFT" not in r1["pi_metrics"])

print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print("失败项:", FAIL)
sys.exit(1 if FAIL else 0)
