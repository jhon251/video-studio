# -*- coding: utf-8 -*-
"""P33-3 前置：导出 v4.1 40 段旁白 + 时长/哈希，供人工核对与合成规划。只读。"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
A = json.loads((R / "output/phase27_script_sandbox/script_p27_v41_40seg.json")
               .read_text(encoding="utf-8"))
B = json.loads((R / "output/phase21_script_sandbox/script_dcv2_p21_40seg.json")
               .read_text(encoding="utf-8"))
V = json.loads((R / "output/phase20_voice_sandbox/voice_output_40seg_v21.json")
               .read_text(encoding="utf-8"))

segs = A["segments"]
out = {
    "schema": "p33-v41-narration-export-v1",
    "total_duration_s_declared": A.get("total_duration_s"),
    "segments": [{"index": i, "scene_id": s.get("scene_id"),
                  "parent_scene_id": s.get("parent_scene_id"),
                  "narration": s.get("narration"),
                  "chars": len(s.get("narration") or ""),
                  "declared_duration_s": s.get("duration_s"),
                  "declared_actual_tts_s": s.get("actual_tts_duration_s"),
                  "audio_window_s": s.get("audio_window_s"),
                  "narration_sha256": s.get("narration_sha256"),
                  "pause_budget_s": s.get("pause_budget_s"),
                  "text_unchanged": s.get("text_unchanged"),
                  "visual_hint": s.get("visual_hint")}
                 for i, s in enumerate(segs)],
}
p = R / "output" / "p33_probe"
p.mkdir(parents=True, exist_ok=True)
(p / "v41_narration.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                      encoding="utf-8")

# 时长来源核对：v4.1 声明时长 是否等于 旧(21/40段)音频切片时长
vsegs = V["segments"]
print("v4.1 段数", len(segs), "| 旧 voice 段数", len(vsegs))
print()
print("{:<8} {:>6} {:>12} {:>14} {:>14}".format(
    "scene", "chars", "declared_s", "old_voice_s", "audio_window_s"))
n = 0
for i, s in enumerate(segs):
    dv = float(s.get("duration_s") or 0)
    ov = float((vsegs[i].get("duration_s") if i < len(vsegs) else 0) or 0)
    eq = abs(dv - ov) < 0.05
    n += eq
    if i < 12 or not eq:
        print("{:<8} {:>6} {:>12.3f} {:>14.3f} {:>14} {}".format(
            str(s.get("scene_id")), len(s.get("narration") or ""), dv, ov,
            str(s.get("audio_window_s")), "==" if eq else "!="))
print()
print("声明时长 == 旧 voice 实测时长的段数: {}/{}".format(n, len(segs)))
print("v4.1 Σchars =", sum(len(s.get('narration') or '') for s in segs))
print("旧 40 段 Σchars =", sum(len(s.get('narration') or '') for s in B['segments']))
print()
print("-> " + str((p / "v41_narration.json").relative_to(R)))
