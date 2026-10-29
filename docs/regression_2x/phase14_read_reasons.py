# -*- coding: utf-8 -*-
"""读出 P14-2 评测报告里模型给出的理由（诊断失配根因）。"""
from __future__ import annotations

import json
import pathlib
import sys
from collections import Counter

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
rep = json.loads((R / "docs/regression_2x/logs/phase14_eval_report.json")
                 .read_text(encoding="utf-8"))
print("truth sha256 :", rep["truth"]["sha256"][:16], "…")
print("pair_count   :", rep["truth"]["pair_count"],
      "| meets_min_pairs:", rep["truth"]["meets_min_pairs"])
print("prompt       :", rep["pairs"][0].get("machine_reason") is not None)
print("provider     :", rep["provider"]["model"], "| available", rep["provider"]["available"])
print("agreement    : {:.2%}  gate passed: {}".format(
    rep["results"]["agreement"], rep["gate"]["passed"]))
print()
print("machine label 分布:", dict(Counter(p["machine_label"] for p in rep["pairs"])))
print("（人工正例 24 / 负例 3）")
print()
print("=" * 78)
print("逐对：人工 vs 机器 + 模型理由")
print("=" * 78)
for p in rep["pairs"]:
    mark = "OK " if p["agree"] else "XX "
    print("{}{:10s} {} {} | 机器={}".format(
        mark, p["human_label"], p["scene_id"], p["asset_key12"], p["machine_label"]))
    print("      模型理由:", str(p.get("machine_reason"))[:140])
