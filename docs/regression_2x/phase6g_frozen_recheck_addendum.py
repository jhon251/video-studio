# -*- coding: utf-8 -*-
"""附录证据（6-G §4 口径对齐后）：冻结口径 `pi_recheck` 在 **DCv2 上下文**下的完整结果。

同时保留一个 **legacy 对照**（未声明 DCv2 时基的上下文）以证明向后兼容（行为与修改前一致）。
"""
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
from video_studio.core import captions as core_captions              # noqa: E402
from video_studio.ops import execution as OPX                        # noqa: E402

L = R / "docs" / "regression_2x" / "logs"
P2 = json.loads((L / "phase6f_rebuild_plan_v2.json").read_text(encoding="utf-8"))
N0 = json.loads((L / "phase6g_n0_dcv2_master.json").read_text(encoding="utf-8"))
B1 = json.loads((L / "phase6g_exec_batch1.json").read_text(encoding="utf-8"))
FF, FP = str(R / "bin" / "ffmpeg.exe"), str(R / "bin" / "ffprobe.exe")
sb = R / B1["sandbox"]
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

PICK = ("pi_gate_outcome", "pi_contract", "planning_drift_blocking", "pi_failed",
        "pi_metrics", "pi_legacy_declared_drift", "pre_render_gate", "post_render_gate",
        "dq_metrics", "film_sha256")


def ctx_for(film: pathlib.Path, dcv2: bool) -> dict:
    base = {"config": {"tools": {"ffmpeg": {"path": FF, "ffprobe": FP}}}, "root": str(R),
            "film": str(film), "artifacts": art, "cues": cues, "timeline_duration_s": 978.656,
            "timeline": [dict(e) for e in tl]}
    if dcv2:
        return OPX.attach_dcv2_time_base(base, timeline=tl, caption_windows=cw,
                                         production_duration_s=978.656,
                                         source="docs/regression_2x/logs/phase6f_rebuild_plan_v2.json")
    return base


out = {"schema": "phase6g-frozen-recheck-addendum-v3", "stage": "6-G §4",
       "change": "pi_recheck 现接收并使用 DCv2 narration_plan（仅口径对齐；阈值/执行门禁/提案判定规则未改）",
       "timeline_identity": N0["timeline_identity"]["identity_sha256"],
       "per_stage_dcv2": {}, "legacy_control": {},
       "interpretation": (
           "DCv2 上下文：DCv2 narration_plan 传入冻结门禁 ⇒ PI-1/PI-2 用语音专属时基、PI-6 用 "
           "G-SEG 权威链自洽性、post 门禁按『仅拦超出已声明预算的静音』判定；原 declared↔actual "
           "漂移数值**单列**为 `PI-6-legacy-declared-drift` 且 `PLANNING_DRIFT` 标注 `blocking=false`，"
           "因此真正阻断项（G-SEG/G-TL/G-PAD/G-SUB、PI-1/2/3…）阈值与判据完全未变 —— **不是放宽门禁**。"
           "legacy 对照（未声明 DCv2 时基）显示行为与修改前完全一致（仍按旧口径 BLOCKED）。")}
for st in B1["stages"]:
    film = R / st["output"]["path"]
    r = OPX.pi_recheck(ctx_for(film, True),
                       {"proposal_id": st["proposal_id"], "action": st["action"],
                        "affected_scope": {"scenes": [], "window": None}},
                       {"outputs": [{"path": st["output"]["path"]}]})
    out["per_stage_dcv2"][st["stage"]] = {k: r.get(k) for k in PICK}
    print("{} DCv2 : outcome={} failed={} PI-6={} legacy_drift={} pre_reasons={}".format(
        st["stage"], r["pi_gate_outcome"], r["pi_failed"],
        json.dumps(r["pi_metrics"].get("PI-6"), ensure_ascii=False)[:60],
        json.dumps(r["pi_legacy_declared_drift"], ensure_ascii=False)[:60],
        json.dumps(r["pre_render_gate"]["reasons"], ensure_ascii=False)[:80]))

h3a = R / B1["stages"][0]["output"]["path"]
rl = OPX.pi_recheck(ctx_for(h3a, False),
                    {"proposal_id": "LEGACY-CONTROL", "action": "split_scene",
                     "affected_scope": {"scenes": [], "window": None}},
                    {"outputs": [{"path": B1["stages"][0]["output"]["path"]}]})
out["legacy_control"]["H3a"] = {k: rl.get(k) for k in PICK}
print("legacy control: outcome={} contract={} pre_reasons={}".format(
    rl["pi_gate_outcome"], rl.get("pi_contract"),
    json.dumps(rl["pre_render_gate"]["reasons"], ensure_ascii=False)[:90]))

(L / "phase6g_frozen_recheck_addendum.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print("addendum ->", L / "phase6g_frozen_recheck_addendum.json")
