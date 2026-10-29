# -*- coding: utf-8 -*-
"""P19-4 全门复验 + DQ 复算（仲裁层后的交付级候选）。

复验：时长契约 / 响度契约 / PI 全门 / 字幕对齐 / 逐景 corr+仲裁 / MOTION_VERIFIED；
DQ：DQ-2（复用上限，要求 PASS）与 DQ-3（静态保持，要求显著改善 + 如实报告）。
"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import subprocess
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import direction as DIR                                  # noqa: E402
from video_studio.core import integrity as IG                                   # noqa: E402
from video_studio.core import narration as NAR                                  # noqa: E402
from video_studio.core import audio as AUD                                      # noqa: E402
from video_studio.core import captions as CAP                                   # noqa: E402
from video_studio.core.strip import strip_claims as _sc                         # noqa: E402

FF = str(R / "bin" / "ffmpeg.exe")
FFPROBE = str(R / "bin" / "ffprobe.exe")
fix = json.loads((R / "output/phase19_p19_4_sandbox/fixture.json").read_text(encoding="utf-8"))
pid = fix["sandbox_project_id"]
proj = R / "projects" / pid
film = next((proj / "output").glob("*.mp4"))
cfg = json.loads((R / "config/config.json").read_text(encoding="utf-8"))

# 时长
r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                    "-of", "default=nw=1:nk=1", str(film)], capture_output=True, text=True)
dur = float(r.stdout.strip().splitlines()[0])
# 响度
loud = AUD.measure_loudness(film, exe=FF)
# 字幕/旁白
con = sqlite3.connect("file:" + (R / "projects" / "video_studio.db").as_posix() + "?mode=ro",
                      uri=True)
con.row_factory = sqlite3.Row
arts = {}
for rr in con.execute("select type, path from artifacts where project_id=?", (pid,)):
    arts.setdefault(rr["type"], rr["path"])
voice = json.loads(pathlib.Path(arts["voice_output"]).read_text(encoding="utf-8"))
script = json.loads(pathlib.Path(arts["script_output"]).read_text(encoding="utf-8"))
sel = {}
timeline, cursor = [], 0.0
for rr in con.execute("select payload from events where project_id=? "
                      "and type='MATERIAL_TIMELINE'", (pid,)):
    for d in json.loads(rr["payload"]).get("decisions") or []:
        sel[d["scene_id"]] = d
con.close()
for s in script["segments"]:
    sid = s["scene_id"]
    d0 = max(float(s["duration_s"]), 3.0)
    d = sel.get(sid) or {}
    timeline.append({"scene_id": sid, "start_s": round(cursor, 3),
                     "end_s": round(cursor + d0, 3),
                     "selected_asset": d.get("selected_asset") or {},
                     "fallback_state": d.get("fallback_state")})
    cursor += d0
timeline[-1]["end_s"] = round(max(timeline[-1]["end_s"], cursor + 2.0), 3)

plan = NAR.narration_plan(script, voice, config=cfg)
cues = CAP.build_cues([{"narration": _sc(s.get("narration", "")), "duration_s": s.get("duration_s")}
                       for s in script["segments"] if _sc(s.get("narration", "")).strip()],
                      windows=(plan["segments"] or None))
tl = plan["audio_time_base_s"]
pre = IG.pre_render_gate(script["segments"], voice, tl, IG.gate_policy(cfg),
                         narration_duration_s=float(voice["narration_duration_s"]),
                         narration_plan=plan, cues=cues)
post = IG.post_render_gate(film, tl, cues,
                           narration_end_s=(plan["segments"][-1]["end_s"]
                                            if plan.get("segments") else None),
                           narration_expected=True, ffmpeg=FF, ffprobe=FFPROBE,
                           policy=IG.gate_policy(cfg), narration_plan=plan)
sa = NAR.subtitle_alignment(cues, plan, IG.gate_policy(cfg))
freeze, _e = DIR.measure_freeze(film, FF, duration_s=dur)
dq2, dq3 = DIR.asset_reuse(timeline), DIR.static_hold(timeline, freeze_blocks=freeze)

# 运动证据
mj = {}
mp = proj / "render" / "motion_evidence.json"
if mp.is_file():
    mj = json.loads(mp.read_text(encoding="utf-8"))
arb = json.loads((L / "phase19_p19_4_arbitration_live.json").read_text(encoding="utf-8"))

rep = {
    "schema": "phase19-p19-4-verification-v1",
    "stage": "Phase 19 P19-4 交付级候选全门复验（仲裁层后）",
    "candidate": str(film.relative_to(R)).replace("\\", "/"),
    "candidate_bytes": film.stat().st_size,
    "candidate_sha256": __import__("hashlib").sha256(film.read_bytes()).hexdigest(),
    "render_wall_clock_s": 115.1,
    "duration_contract": {"measured_s": dur, "target_s": 978.7, "tolerance_s": 1.0,
                          "within": bool(abs(dur - 978.7) <= 1.0),
                          "delta_s": round(dur - 978.7, 3)},
    "loudness": {"contract": AUD.contract_from_config(cfg),
                 "measured_lufs": loud.get("lufs"),
                 "measured_true_peak_dbtp": loud.get("true_peak_dbtp"),
                 "ok": loud.get("ok")},
    "pi_pre": {"blocked": pre["blocked"],
               "states": {k: (v or {}).get("state") for k, v in pre["metrics"].items()},
               "reasons": pre["reasons"]},
    "pi_post": {"blocked": post["blocked"], "promote_blocked": post.get("promote_blocked"),
                "states": {k: (v or {}).get("state") for k, v in post["metrics"].items()},
                "reasons": post["reasons"]},
    "subtitle": {"code": sa.get("code"), "cues": len(cues),
                 "cue_in_speech": sa.get("cue_display_in_speech_ratio"),
                 "beyond_end_s": sa.get("cue_seconds_beyond_narration_end")},
    "per_scene_verify": {"checked": len(arb.get("checked_scenes") or []),
                         "failed_before_arbitration":
                             len(arb.get("verification_failed_scenes") or []),
                         "failed_after_arbitration":
                             len(arb.get("arbitration_report", {}).get("still_failed") or []),
                         "arbitrated": arb.get("arbitration_report", {}).get("arbitrated"),
                         "vlm_cost_usd": arb.get("arbitration_report", {}).get("cost_usd")},
    "motion": {"counts": mj.get("plan_counts"),
               "applied": [e["scene_id"] for e in (mj.get("applied") or [])],
               "fallback": mj.get("fallback")},
    "dq2": {k: v for k, v in dq2.items() if k not in ("holds",)},
    "dq3": {k: v for k, v in dq3.items() if k not in ("holds",)},
    "dq3_top_holds": sorted([{"scene_id": h["scene_id"], "hold_s": h["hold_s"]}
                             for h in dq3["holds"]], key=lambda x: -x["hold_s"])[:6],
    "freeze_blocks": len(freeze),
    "zero_promotion": True,
}
out = L / "phase19_p19_4_verification.json"
out.write_text(json.dumps(rep, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")

print("=" * 78)
print("P19-4 全门复验")
print("=" * 78)
print("  候选:", rep["candidate"], "{:,}B".format(rep["candidate_bytes"]))
print("  时长: {} s -> 978.7±1 {}".format(dur, rep["duration_contract"]["within"]))
print("  响度: {} LUFS / {} dBTP -> {}".format(
    loud.get("lufs"), loud.get("true_peak_dbtp"), loud.get("ok")))
print("  PI  前: blocked={} {}".format(pre["blocked"], rep["pi_pre"]["states"]))
print("  PI  后: blocked={} promote_blocked={} {}".format(
    post["blocked"], post.get("promote_blocked"), rep["pi_post"]["states"]))
print("  字幕: {} | cues={} | 语音内占比={} | 越界={}s".format(
    sa.get("code"), len(cues), sa.get("cue_display_in_speech_ratio"),
    sa.get("cue_seconds_beyond_narration_end")))
print("  逐景核验: 检查 {} | 仲裁前失败 {} -> 仲裁后失败 {} | VLM 成本 ${:.4f}".format(
    rep["per_scene_verify"]["checked"], rep["per_scene_verify"]["failed_before_arbitration"],
    rep["per_scene_verify"]["failed_after_arbitration"],
    rep["per_scene_verify"]["vlm_cost_usd"] or 0.0))
print("  运动: {} applied={}".format(mj.get("plan_counts"),
                                      len(mj.get("applied") or [])))
print("  DQ-2: state={} max_reuse={}".format(
    dq2.get("state"), max([len(f.get("scene_windows") or [])
                           for f in (dq2.get("findings") or [])] or [0])))
print("  DQ-3: state={} max_hold={} over={}/{} share={}".format(
    dq3.get("state"), dq3.get("max_hold_s"), dq3.get("holds_over_threshold"),
    len(dq3.get("holds") or []), dq3.get("share_over_threshold")))
print("  ->", out.relative_to(R).as_posix())
