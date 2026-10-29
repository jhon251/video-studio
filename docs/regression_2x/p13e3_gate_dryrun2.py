# -*- coding: utf-8 -*-
"""P13E-3 ② 第二段干跑：v2 注入路径 + 真实 cues 的 G-SUB 门（只读，用仓库自身代码）。"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core import integrity as IG          # noqa: E402
from video_studio.core import narration as N           # noqa: E402
from video_studio.core import captions as CAP          # noqa: E402
from video_studio.core.strip import strip_claims as _sc  # noqa: E402

PID = "p_96efdc03e1aa"
P = R / "projects" / PID
cfg = json.loads((R / "config" / "config.json").read_text(encoding="utf-8"))
script = json.loads((R / "output" / "phase13e_script_sandbox" /
                     "script_dcv2_derived_v1.json").read_text(encoding="utf-8"))
voice = json.loads((P / "artifacts" / "a_e99273b936c0.json").read_text(encoding="utf-8"))
segs = script["segments"]

voice2 = dict(voice)
voice2["audio_time_base_s"] = 978.656
plan2 = N.narration_plan(script, voice2, config=cfg)
windows = plan2["segments"]

# 复刻 agent.py L627-634 的 _gate_cues 构造
cues = CAP.build_cues(
    [{"narration": _sc(s.get("narration", "")), "duration_s": s.get("duration_s")}
     for s in segs if _sc(s.get("narration", "")).strip()],
    windows=(windows or None))
print("cues:", len(cues))
print("cue[0]:", json.dumps(cues[0], ensure_ascii=False)[:200])
print("cue[-1]:", json.dumps(cues[-1], ensure_ascii=False)[:200])

sa = N.subtitle_alignment(cues, plan2, IG.gate_policy(cfg))
print()
print("subtitle_alignment:", json.dumps(sa, ensure_ascii=False, indent=1))

print()
print("=== pre_render_gate v2 WITH real cues ===")
g = IG.pre_render_gate(segs, voice2, 978.656, IG.gate_policy(cfg),
                       narration_duration_s=961.656, narration_plan=plan2, cues=cues,
                       narration_padding_s=None)
print("blocked:", g["blocked"])
for k, v in (g["metrics"] or {}).items():
    print("   ", k, "=>", (v or {}).get("state"))
for r in g["reasons"]:
    print("   -", r[:300])

print()
print("=== 成片总时长（v2 路径）===")
tl = plan2["audio_time_base_s"]
print("audio_time_base_s = timeline_total_s =", tl)
print("旁白音轨实测               :", voice["narration_duration_s"])
print("apad 需补齐                 :", round(tl - float(voice["narration_duration_s"]), 3))
print("授权 apad_allowed_s        :", plan2["padding_policy"]["apad_allowed_s"])
_pad = max(float(plan2["audio_time_base_s"]) - float(voice["narration_duration_s"]), 0.0)
print("check_narration_padding    :",
      json.dumps(N.check_narration_padding(_pad, plan2), ensure_ascii=False))
print("契约 978.7±1 ⇒",
      "PASS" if abs(tl - 978.7) <= 1.0 else "FAIL", f"(Δ={round(tl-978.7,3)})")
