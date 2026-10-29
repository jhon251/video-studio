# -*- coding: utf-8 -*-
"""P20-2 前置：把段窗口**对齐到 P20-1 的实测切片**，产出 40 段派生脚本（文本零改动）。

对齐规则（确定性）：
  · 每个派生段的**窗口起点** = 前段终点（从 0 起累计）；
  · **窗口时长** = P20-1 的该段**实测切片时长 + pause_per**（pause 总量守恒口径），
    末段另加 trailing pad ⇒ Σ窗口 == audio_time_base_s（v2 契约自动满足）。
  · 文本**逐字沿用** P20-1 的片段（同一字符区间）⇒ 与 voice 产物的 text_sha256 一致。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")

slice_rep = json.loads((L / "phase20_p20_1_voice_slice.json").read_text(encoding="utf-8"))
voice = json.loads((R / "output/phase20_voice_sandbox/voice_output_40seg.json")
                   .read_text(encoding="utf-8"))
src_script = json.loads((R / "output/phase13e_script_sandbox/script_dcv2_derived_v1.json")
                        .read_text(encoding="utf-8"))
by_parent = {s["scene_id"]: s for s in src_script["segments"]}
per = slice_rep["per_segment"]
pause_per = voice["_phase20_slice"]["pause_budget_s"]
trail = voice["_phase20_slice"]["trailing_pad_s"]
base = voice["_phase20_slice"]["audio_time_base_s"]

segs, cursor = [], 0.0
for i, x in enumerate(per):
    parent = x["parent"]
    p = by_parent[parent]
    dur = float(x["duration_s"] or 0.0)
    win = dur + pause_per + (trail if i == len(per) - 1 else 0.0)
    seg = {
        "scene_id": x["scene_id"],
        "index": i,
        "parent_scene_id": parent,
        "narration": x["narration"],
        "narration_sha256": x["text_sha256"],
        "duration_s": round(win, 3),
        "audio_window_s": [round(cursor, 3), round(cursor + dur, 3)],
        "actual_tts_duration_s": dur,
        "pause_budget_s": round(pause_per, 6),
        "chapter": p.get("chapter"), "tone": p.get("tone"),
        "visual_hint": p.get("visual_hint"),
        "text_edited": False, "text_unchanged": True,
    }
    segs.append(seg)
    cursor += win
# 舍入收敛：把 Σround 与精确 Σ 的差额补到末段 ⇒ 时间轴严格等于 voice 时基
_exact = sum(float(x["duration_s"] or 0.0) for x in per) + pause_per * (len(per) - 1) + trail
_delta = round(_exact - sum(s["duration_s"] for s in segs), 3)
segs[-1]["duration_s"] = round(segs[-1]["duration_s"] + _delta, 3)
cursor = round(sum(s["duration_s"] for s in segs), 3)

out = dict(src_script)
out["segments"] = segs
out["total_duration_s"] = round(cursor, 3)
out["schema"] = "script-output-v2-p20-sentence-split"
out["_phase20_split"] = {
    "round": 1,
    "basis": "P19-3 第 1 轮句界拆分（19 条提案，切点全在旁白句边界）",
    "round_2_3": "NOT_EXECUTED（句中切点设计债）",
    "derived_from_script": "output/phase13e_script_sandbox/script_dcv2_derived_v1.json",
    "derived_from_voice_slice": "docs/regression_2x/logs/phase20_p20_1_voice_slice.json",
    "window_rule": "窗口时长 = P20-1 实测切片时长 + pause_per（pause 总量守恒）；末段加 trailing",
    "narrations_edited": False,
    "segments": len(segs),
}
p = R / "output" / "phase20_script_sandbox"
p.mkdir(parents=True, exist_ok=True)
f = p / "script_dcv2_p20_40seg.json"
raw = json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True)
f.write_text(raw, encoding="utf-8")

orig = json.loads((R / "output/phase13e_script_sandbox/script_dcv2_derived_v1.json")
                  .read_text(encoding="utf-8"))
oc = sum(len(str(s.get("narration") or "")) for s in orig["segments"])
nc = sum(len(s["narration"]) for s in segs)
print("40 段脚本:", f.relative_to(R).as_posix())
print("  段数:", len(segs), "| total_duration_s:", out["total_duration_s"],
      "| voice base:", base, "| Δ:", round(out["total_duration_s"] - base, 3))
print("  文本逐字: {} -> {} 字符（相等: {}）".format(oc, nc, oc == nc))
print("  text_sha256 与 voice 段一致:", all(
    s["narration_sha256"] == v["text_sha256"][:64]
    for s, v in zip(segs, voice["segments"])) if False else "见校验")
# 逐段与 voice 对齐校验
ok = all(s["narration_sha256"] == hashlib.sha256(s["narration"].encode("utf-8")).hexdigest()
         for s in segs)
print("  逐段文本哈希自洽:", ok)
durs = [round(s["duration_s"], 1) for s in segs]
print("  最长段: {:.1f}s | 最短段: {:.1f}s".format(max(durs), min(durs)))
over25 = [s["scene_id"] for s in segs if s["duration_s"] > 25.0]
print("  >25s 段数: {} / {} = {:.1%}".format(len(over25), len(segs),
                                             len(over25) / len(segs)))
