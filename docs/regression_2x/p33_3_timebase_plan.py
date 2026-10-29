# -*- coding: utf-8 -*-
"""P33-3 规划：按实测语速预估 v4.1 新时基（不消耗网络）。"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
A = json.loads((R / "output/phase27_script_sandbox/script_p27_v41_40seg.json")
               .read_text(encoding="utf-8"))
V = json.loads((R / "output/phase20_voice_sandbox/voice_output_40seg_v21.json")
               .read_text(encoding="utf-8"))

# 实测（本次探针）：49 字 -> 8.544 s
CPS = 49 / 8.544
# 旧片实测语速（对照）
old_chars = sum(len(s.get("narration") or "") for s in
                json.loads((R / "output/phase21_script_sandbox/script_dcv2_p21_40seg.json")
                           .read_text(encoding="utf-8"))["segments"])
old_dur = sum(float(s.get("duration_s") or 0) for s in V["segments"])
old_cps = old_chars / old_dur

segs = A["segments"]
chars = sum(len(s.get("narration") or "") for s in segs)
speech = chars / CPS
pauses = sum(float(s.get("pause_budget_s") or 0) for s in segs)
print("v4.1 段数 {} | 总字符 {}".format(len(segs), chars))
print("本次探针语速  {:.3f} 字/秒".format(CPS))
print("旧片实测语速  {:.3f} 字/秒（{} 字 / {:.1f}s）".format(old_cps, old_chars, old_dur))
print()
print("按本次语速预估：")
print("  纯语音 ≈ {:.1f}s".format(speech))
print("  暂停   ≈ {:.1f}s（Σ pause_budget_s，注意该值本身可疑）".format(pauses))
print("  合计   ≈ {:.1f}s".format(speech + pauses + 2.0))
print()
print("旧时基 977.884s（声明）→ 新时基预估 ≈ {:.0f}s（缩短 ≈ {:.0f}s）".format(
    speech + pauses + 2.0, 977.884 - (speech + pauses + 2.0)))
print()
print("pause_budget_s 取值分布:", sorted({s.get("pause_budget_s") for s in segs}))
