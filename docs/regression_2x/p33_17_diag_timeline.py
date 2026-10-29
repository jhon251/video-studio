# -*- coding: utf-8 -*-
"""P33 定论：直接调用生产 `_build_material_timeline`，看它用我的输入算出多少总时长。"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.agents.editing import agent as AG                              # noqa: E402
from video_studio.core import materials as MAT                                   # noqa: E402
from video_studio.core import narration as NAR                                   # noqa: E402

SC = json.loads((R / "output/phase33_script_sandbox/script_p33_v41_40seg.json")
                .read_text(encoding="utf-8"))
VO = json.loads((R / "output/phase33_voice/voice_output_v41.json")
                .read_text(encoding="utf-8"))
VO2 = dict(VO)
VO2["audio"] = "media/voice/narration_v41.mp3"
VO2["segments"] = [{**s, "audio": "media/voice/" + s["audio"]} for s in VO["segments"]]

plan = NAR.narration_plan(SC, VO2)
print("narration_plan: base={} Σactual={} pause={} trail={}".format(
    plan["audio_time_base_s"], plan["actual_total_narration_s"],
    plan["pause_budget_s"], plan["trailing_pad_s"]))
ws = plan["segments"]
print("plan 首 3:", [(w["actual_s"], w["pause_s"]) for w in ws[:3]])
print("plan 末:", {k: ws[-1][k] for k in ("actual_s", "pause_s", "start_s", "end_s")})
print("Σ(actual+pause) =", round(sum(w["actual_s"] + w["pause_s"] for w in ws), 3))
print()

tl = AG.EditingAgent._build_material_timeline(
    SC, [], [], policy=MAT.policy_from_config(None), material_provided=False,
    segment_durations=[w["actual_s"] for w in ws],
    pause_budget_s=plan["pause_budget_s"], trailing_pad_s=plan["trailing_pad_s"])
tot = sum(float(s["end_s"]) - float(s["start_s"]) for s in tl)
print("生产函数 Σ窗口 = {:.3f}".format(tot))
print("首 3 窗口:", [(s["scene_id"], round(s["start_s"], 3), round(s["end_s"], 3))
                     for s in tl[:3]])
print("末 3 窗口:", [(s["scene_id"], round(s["start_s"], 3), round(s["end_s"], 3))
                     for s in tl[-3:]])
print("末景 end 是否 = cursor+2:", tl[-1]["end_s"])
print()
print("对照：脚本声明 time_base =", NAR.script_time_base_s(SC))
print("      新时基（我的 timebase_v41）= 700.592")
print("      渲染产物 Σ窗口 = 687.592")
