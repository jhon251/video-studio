# -*- coding: utf-8 -*-
"""P13E-3 ② 渲染门禁**权威干跑**（只读：调用仓库自身 narration_plan / pre_render_gate）。

目的：在启动数小时后台渲染之前，用**生产代码本体**判定夹具能否通过渲染前硬门。
不写任何产物、不渲染。
"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core import integrity as IG          # noqa: E402
from video_studio.core import narration as N           # noqa: E402
from video_studio.core import motion as M              # noqa: E402

PID = "p_96efdc03e1aa"
P = R / "projects" / PID
cfg = json.loads((R / "config" / "config.json").read_text(encoding="utf-8"))

script = json.loads((R / "output" / "phase13e_script_sandbox" /
                     "script_dcv2_derived_v1.json").read_text(encoding="utf-8"))
voice = json.loads((P / "artifacts" / "a_e99273b936c0.json").read_text(encoding="utf-8"))
plan_v2_path = json.loads((R / "docs" / "regression_2x" / "logs" /
                           "phase6f_rebuild_plan_v2.json").read_text(encoding="utf-8"))
rm = plan_v2_path["remapping_21_segments"]

segs = script["segments"]
print("=" * 78)
print("A. 事实核对")
print("=" * 78)
print("派生脚本 total_duration_s (metadata):", script.get("total_duration_s"))
print("派生脚本 Σ duration_s          :", round(sum(float(s["duration_s"]) for s in segs), 3))
print("派生脚本 min duration_s        :", min(float(s["duration_s"]) for s in segs))
tts = [float(s["actual_tts_duration_s"]) for s in segs]
print("派生脚本 Σ actual_tts_duration_s:", round(sum(tts), 3))
print("派生脚本 Σ pause_budget_s      :", round(sum(float(s["pause_budget_s"]) for s in segs), 3))
print("voice 产物 segments            :", len(voice["segments"]))
print("voice 自报 narration_duration_s:", voice.get("narration_duration_s"))
vt = [float(s["duration_s"]) for s in voice["segments"]]
print("voice Σ segments[].duration_s  :", round(sum(vt), 3))
print("voice status 全 SUCCESS         :",
      all(s.get("status") == "SUCCESS" for s in voice["segments"]))
print("audio_time_base_s 字段存在      :", "audio_time_base_s" in voice)

print()
print("新旧时基逐段对比（DCv2 窗口 vs 旧 TTS 时长）")
print(f"{'seg':>3} {'scene':>5} {'new_win':>9} {'new_pause':>9} {'tts_new':>9} "
      f"{'old_win':>9} {'tts_old':>9} {'Δwin':>7} {'Δtts':>7}")
dw = dt = 0.0
for i, (s, w) in enumerate(zip(segs, rm)):
    nw = float(w["new_timeline_window_s"][1]) - float(w["new_timeline_window_s"][0])
    ow = float(w["old_timeline_window_s"][1]) - float(w["old_timeline_window_s"][0])
    a = float(s["actual_tts_duration_s"])
    o = vt[i]
    dw += nw - ow
    dt += a - o
    print(f"{i:>3} {s['scene_id']:>5} {nw:>9.3f} {float(s['pause_budget_s']):>9.2f} {a:>9.3f} "
          f"{ow:>9.3f} {o:>9.3f} {nw-ow:>7.2f} {a-o:>7.2f}")
print(f"ΣΔ new_vs_old 窗口: {dw:.3f} | Σ new actual vs 旧 TTS: {dt:.3f}")

print()
print("=" * 78)
print("B. v2 权威对象（仓库自身 narration_plan）")
print("=" * 78)
plan = N.narration_plan(script, voice, config=cfg)
print("declared_time_base_s      :", plan["declared_time_base_s"])
print("audio_time_base_s         :", plan["audio_time_base_s"])
print("actual_total_narration_s  :", plan["actual_total_narration_s"])
print("measured_narration_track_s:", plan["measured_narration_track_s"])
print("concat_consistent         :", plan["concat_consistent"])
print("complete                  :", plan["complete"])
print("pause_budget_s            :", plan["pause_budget_s"], "trailing:", plan["trailing_pad_s"])
print("apad_allowed_s            :", plan["padding_policy"]["apad_allowed_s"])
print("planning_drift delta_s    :", plan["planning_drift"]["delta_s"],
      "max_abs_cum_drift:", plan["planning_drift"]["max_abs_cumulative_drift_s"])
print("G-TL (timeline=declared)  :", N.timeline_audio_consistency(
    N.script_time_base_s(script), plan, IG.gate_policy(cfg)))

print()
print("=" * 78)
print("C. 情形①：v1（voice 无 audio_time_base_s ⇒ 生产路径走 v1）")
print("=" * 78)
# v1 timeline：Σ duration_s (min 3) + 末尾 2s
tl_v1 = sum(max(float(s["duration_s"]), 3.0) for s in segs) + 2.0
print("v1 timeline_total_s       :", round(tl_v1, 3))
print("v1 → 成片时长            :", round(tl_v1, 3), "| 契约 978.7±1 ⇒",
      "PASS" if abs(tl_v1 - 978.7) <= 1.0 else "FAIL")
g1 = IG.pre_render_gate(segs, voice, tl_v1, IG.gate_policy(cfg),
                        narration_duration_s=961.656,
                        narration_plan=None, cues=None)
print("pre_render_gate v1 blocked:", g1["blocked"])
for r in g1["reasons"]:
    print("   -", r[:220])

print()
print("=" * 78)
print("D. 情形②：v2（把 audio_time_base_s 注入 voice 产物 ⇒ 启用 v2 契约）")
print("=" * 78)
voice2 = dict(voice)
voice2["audio_time_base_s"] = 978.656
plan2 = N.narration_plan(script, voice2, config=cfg)
g2 = IG.pre_render_gate(segs, voice2, 978.656, IG.gate_policy(cfg),
                        narration_duration_s=961.656,
                        narration_plan=plan2, cues=None)
print("declared_time_base_s      :", plan2["declared_time_base_s"])
print("audio_time_base_s         :", plan2["audio_time_base_s"])
print("G-TL vs timeline 978.656  :", N.timeline_audio_consistency(978.656, plan2,
                                                                    IG.gate_policy(cfg)))
print("pre_render_gate v2 blocked:", g2["blocked"])
for k, v in (g2["metrics"] or {}).items():
    print("   ", k, "=>", (v or {}).get("state"))
for r in g2["reasons"]:
    print("   -", r[:220])

print()
print("=" * 78)
print("E. 情形③：v2 + 脚本 duration_s 改为 TTS 时长（=audio_window_s 长度）")
print("=" * 78)
script3 = json.loads(json.dumps(script))
for s in script3["segments"]:
    s["duration_s"] = round(float(s["actual_tts_duration_s"]), 3)
script3["total_duration_s"] = round(sum(float(s["duration_s"])
                                        for s in script3["segments"]), 3)
print("Σ duration_s (TTS)        :", script3["total_duration_s"])
print("script_time_base_s        :", N.script_time_base_s(script3))
plan3 = N.narration_plan(script3, voice2, config=cfg)
g3 = IG.pre_render_gate(script3["segments"], voice2, 978.656, IG.gate_policy(cfg),
                        narration_duration_s=961.656,
                        narration_plan=plan3, cues=None)
print("G-TL                      :", N.timeline_audio_consistency(978.656, plan3,
                                                                    IG.gate_policy(cfg)))
print("pre_render_gate v2b blocked:", g3["blocked"])
for k, v in (g3["metrics"] or {}).items():
    print("   ", k, "=>", (v or {}).get("state"))
for r in g3["reasons"]:
    print("   -", r[:220])

print()
print("=" * 78)
print("F. 运动层（enabled=true）")
print("=" * 78)
mcfg, msrc = M.resolve_config(cfg, root=R)
print("resolve_config:", {k: v for k, v in mcfg.items() if k != "note"}, "| src:", msrc)
scenes = [{"scene_id": s["scene_id"],
           "duration_s": max(round(float(s["duration_s"]), 3), 0.5),
           "hook": False} for s in segs]
mp = M.build_plan(scenes, out_w=1920, out_h=1080, fps=25)
print("plan counts:", mp.get("counts"))
print("plan policy:", json.dumps(mp.get("policy"), ensure_ascii=False)[:400])
en = [p for p in mp["scenes"] if p.get("enabled")]
print("enabled scenes:", [p["scene_id"] for p in en])
print("≈frames:", 978.656 * 25)
