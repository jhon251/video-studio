# -*- coding: utf-8 -*-
"""核对 P14-2 两次独立运行的逐对差异（temperature=0 下的端点非确定性）。"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
rep = json.loads((R / "docs/regression_2x/logs/phase14_eval_report.json")
                 .read_text(encoding="utf-8"))
print("当前报告（第 2 次独立运行，已清缓存）")
print("  agreement:", rep["results"]["agreement"],
      "| agree:", rep["results"]["agree"], "/", rep["results"]["pairs_total"])
print("  confusion:", json.dumps(rep["results"]["confusion"], ensure_ascii=False))
print()
print("第 1 次运行（已记录于阶段报告）: agreement 0.1111 = 3/27")
print("  confusion: RELEVANT: {IRRELEVANT 16, PARTIAL 7, RELEVANT 1} | IRRELEVANT: {IRRELEVANT 2, PARTIAL 1}")
print()
print("逐对机器标签（第 2 次）:")
for p in rep["pairs"]:
    print("  {} {} {} | 人工={} 机器={}".format(
        "OK" if p["agree"] else "XX", p["scene_id"], p["asset_key12"],
        p["human_label"], p["machine_label"]))
print()
print("=> 两次唯一差异对（按第 1 次记录推断）：S05/6c3fc5af91ed 由 PARTIAL → ？")
print("   （第2次该对机器标签 =",
      [p["machine_label"] for p in rep["pairs"]
       if p["scene_id"] == "S05" and p["asset_key12"] == "6c3fc5af91ed"], "）")
