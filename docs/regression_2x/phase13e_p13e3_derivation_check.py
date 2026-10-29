# -*- coding: utf-8 -*-
"""P13E-3 步 1：**纯派生前提核验** —— v9 脚本 21 段能否逐字映射到 DCv2 remapping 的 21 窗（不改一字）。"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sqlite3
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
DB = R / "projects" / "video_studio.db"
sys.stdout.reconfigure(encoding="utf-8")

con = sqlite3.connect("file:" + DB.as_posix() + "?mode=ro", uri=True)
con.row_factory = sqlite3.Row
row = con.execute("select path from artifacts where artifact_id='a_49b58fb3dc01'").fetchone()
con.close()
script_path = pathlib.Path(row["path"])
script = json.loads(script_path.read_text(encoding="utf-8"))
segs = script.get("segments") or []
print("v9 脚本:", script_path.name, "| sha256:", hashlib.sha256(script_path.read_bytes()).hexdigest()[:16],
      "| 段数:", len(segs))
print("  段字段:", sorted(segs[0].keys()) if segs else None)
print("  段 scene_id:", [s.get("scene_id") for s in segs][:8], "…")
print("  段时长合计: %.1f s" % sum(float(s.get("duration_s") or 0) for s in segs))

plan = json.loads((L / "phase6f_rebuild_plan_v2.json").read_text(encoding="utf-8"))
rm = plan["remapping_21_segments"]
print("\nDCv2 remapping: 条数", len(rm), "| scene_ids:", [e.get("scene_id") for e in rm][:8], "…")
print("  合计 new 窗口: %.1f s" % sum(float(e["new_timeline_window_s"][1]) -
                                     float(e["new_timeline_window_s"][0]) for e in rm))

ids_v9 = [str(s.get("scene_id")) for s in segs]
ids_dc = [str(e.get("scene_id")) for e in rm]
same_order = ids_v9 == ids_dc
print("\n== 逐字映射可行性 ==")
print("  段序与 remapping 段序**完全一致**:", same_order)
if not same_order:
    print("  v9 独有:", [i for i in ids_v9 if i not in ids_dc],
          "| DCv2 独有:", [i for i in ids_dc if i not in ids_v9])
# 文本逐字对照（按 scene_id 配对）
by_v9 = {str(s.get("scene_id")): s for s in segs}
mismatch = []
for e in rm:
    sid = str(e.get("scene_id"))
    a = by_v9.get(sid) or {}
    if not a:
        mismatch.append({"scene_id": sid, "issue": "v9 无对应段"})
        continue
    txt = str(a.get("narration") or "")
    if not txt.strip():
        mismatch.append({"scene_id": sid, "issue": "v9 段旁白为空"})
    dur_old = float(a.get("duration_s") or 0)
    dur_new = float(e["new_timeline_window_s"][1]) - float(e["new_timeline_window_s"][0])
    tts = float(e.get("actual_tts_duration_s") or 0)
    # 事实来源为 TTS 音频：DCv2 窗口 = TTS 时长 + pause 预算（允许差异），但文本必须逐字不变
    ok_window = abs(dur_new - (tts + float(e.get("pause_budget_s") or 0))) <= 0.01
    if not ok_window:
        mismatch.append({"scene_id": sid, "issue": "DCv2 窗口 ≠ TTS+pause",
                         "dur_new": round(dur_new, 3), "tts": tts,
                         "pause": e.get("pause_budget_s")})
print("  逐字映射问题数:", len(mismatch), mismatch[:3])
print("  结论:", "PURE_DERIVATION_POSSIBLE（无需改写任何文本）" if (same_order and not mismatch)
      else "**需改写文本/结构 ⇒ 按授权 (a) STOP 并报告**")
out = {"same_order": same_order, "mismatch": mismatch, "segments": len(segs),
       "remapping": len(rm), "v9_total_s": round(sum(float(s.get("duration_s") or 0)
                                                    for s in segs), 1),
       "dcv2_total_s": round(sum(float(e["new_timeline_window_s"][1]) -
                                float(e["new_timeline_window_s"][0]) for e in rm), 1)}
(L / "phase13e_p13e3_derivation_check.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
print("产物: phase13e_p13e3_derivation_check.json")
