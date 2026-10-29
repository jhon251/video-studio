# -*- coding: utf-8 -*-
"""汇总 P13E-3 ② 复验报告的要点（只读）。"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
rep = json.loads((R / "docs/regression_2x/logs/phase13e_p13e3_render.json")
                 .read_text(encoding="utf-8"))

print("=== 时长 ===")
print(json.dumps(rep["duration_contract"], ensure_ascii=False, indent=1))

print()
print("=== 响度 ===")
print("contract:", json.dumps(rep["loudness"]["contract"], ensure_ascii=False))
print("independent:", json.dumps(rep["loudness"]["independent_measure"], ensure_ascii=False))

print()
print("=== PI 门 ===")
print("pre  states:", json.dumps(rep["pi_gates"]["pre_render"]["states"], ensure_ascii=False))
print("pre  blocked:", rep["pi_gates"]["pre_render"]["blocked"],
      "| reasons:", rep["pi_gates"]["pre_render"]["reasons"])
print("post states:", json.dumps(rep["pi_gates"]["post_render"]["states"], ensure_ascii=False))
print("post blocked:", rep["pi_gates"]["post_render"]["blocked"],
      "| promote_blocked:", rep["pi_gates"]["post_render"]["promote_blocked"])
print("post reasons:", rep["pi_gates"]["post_render"]["reasons"])

print()
print("=== 字幕 ===")
print(json.dumps(rep["subtitle_alignment"]["v2_alignment"], ensure_ascii=False, indent=1))
print("orphans:", json.dumps({k: v for k, v in rep["subtitle_alignment"]["orphans"].items()
                              if k != "block_list"}, ensure_ascii=False))

print()
print("=== 逐景运动实证 ===")
print("{:>4} {:>6} {:>9} {:>7} {:>8} {:>10} {:>7}".format(
    "景", "运动", "窗口长", "corr", "≥0.30", "10vs90差", "verified"))
for s in rep["motion_verification"]["scenes"]:
    print("{:>4} {:>6} {:>9.2f} {:>7} {:>8} {:>10} {:>7}".format(
        s["scene_id"], "YES" if s["motion_enabled"] else "-", s["duration_s"],
        s["corr_asset_vs_frame90"], s["corr_ge_0_30"],
        s["frame_diff_10_vs_90"], s["motion_verified"]))
print()
print("summary:", json.dumps(rep["motion_verification"]["summary"], ensure_ascii=False, indent=1))

print()
print("=== DQ 只读复核 ===")
for k, v in rep["dq_readonly"].items():
    print(k, "=> state:", (v or {}).get("state"),
          "|", json.dumps({kk: vv for kk, vv in (v or {}).items()
                           if kk in ("scene_rate", "reuse_total", "scenes", "mean_hold_s",
                                     "max_hold_s", "holds_over_threshold",
                                     "share_over_threshold", "distinct_assets", "findings")},
                          ensure_ascii=False)[:400])
print()
print("DQ-3 freezedetect 并列:", json.dumps(
    {k: v for k, v in rep["dq3_freezedetect"].items() if k != "block_list"},
    ensure_ascii=False, indent=1))

print()
print("=== 冻结块前 12 ===")
for b in rep["dq3_freezedetect"]["block_list"][:12]:
    print("  ", json.dumps(b, ensure_ascii=False))

print()
print("=== 结论字段 ===")
for k in ("verdict", "blocked_error", "timeline_source", "disclaimer"):
    if k in rep:
        print(k, ":", str(rep[k])[:600])
