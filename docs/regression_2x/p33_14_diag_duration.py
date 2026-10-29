# -*- coding: utf-8 -*-
"""P33 诊断：成片时长 687.59 vs 新时基 700.592 的差异定位。"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import narration as NAR                                    # noqa: E402

SANDBOX = R / "output" / "phase33_p33_4_sandbox"
VOICE = R / "output/phase33_voice/voice_output_v41.json"
SCRIPT = R / "output/phase33_script_sandbox/script_p33_v41_40seg.json"

sc = json.loads(SCRIPT.read_text(encoding="utf-8"))
vo = json.loads(VOICE.read_text(encoding="utf-8"))
print("=== 脚本声明 ===")
print("script_time_base_s      =", NAR.script_time_base_s(sc))
print("total_duration_s        =", sc.get("total_duration_s"))
print("Σ duration_s            =", round(sum(float(s.get('duration_s') or 0)
                                             for s in sc['segments']), 3))
print()
print("=== 由 voice 产物复算 ===")
plan = NAR.narration_plan(sc, vo)
print("audio_time_base_s       =", plan["audio_time_base_s"])
print("Σactual                 =", plan["actual_total_narration_s"])
print("pause_budget_s          =", plan["pause_budget_s"])
print("trailing_pad_s          =", plan["trailing_pad_s"])
ws = plan["segments"]
print("Σ(actual+pause)         =", round(sum(w["actual_s"] + w["pause_s"] for w in ws), 3))
print("末段 end_s              =", ws[-1]["end_s"])
print()
print("=== voice 产物字段核对 ===")
print("segments_total          =", vo.get("segments_total"), len(vo["segments"]))
print("narration_duration_s    =", vo.get("narration_duration_s"))
print("Σ duration_s (voice)    =", round(sum(float(s.get('duration_s') or 0)
                                             for s in vo['segments']), 3))
print("前 3 段:", [(s["scene_id"], s["duration_s"], s.get("status")) for s in vo["segments"][:3]])
print("末 3 段:", [(s["scene_id"], s["duration_s"], s.get("status")) for s in vo["segments"][-3:]])
print()
print("=== 逐段差异（脚本 duration_s vs voice duration_s）===")
bad = 0
for a, b in zip(sc["segments"], vo["segments"]):
    da, db = float(a.get("duration_s") or 0), float(b.get("duration_s") or 0)
    if abs(da - db) > 0.01:
        bad += 1
        if bad <= 8:
            print("  {} script={:.3f} voice={:.3f} Δ={:+.3f}".format(
                a.get("scene_id"), da, db, da - db))
print("  不一致段数:", bad, "/", len(sc["segments"]))
