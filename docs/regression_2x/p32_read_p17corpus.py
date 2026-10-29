# -*- coding: utf-8 -*-
"""P32-2 前置：读取 P17 metric-v2 实验语料（正集/负集条目与失败项）。只读。"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
d = json.loads((R / "docs/regression_2x/logs/phase17_metric_v2_experiment.json")
               .read_text(encoding="utf-8"))
print("keys:", list(d.keys()))
print("definition:", json.dumps(d["definition"], ensure_ascii=False))
print("summary:", json.dumps(d["summary"], ensure_ascii=False))
print()
print("=== positives ({} 条) ===".format(len(d["positives"])))
for x in d["positives"]:
    print("  {:<6} corr_full {:>7} corr_bank {:>7} pass_v2={:<5} {}".format(
        x.get("scene_id"), x.get("corr_full"), x.get("corr_bank"), x.get("pass_v2"),
        json.dumps({k: v for k, v in x.items()
                    if k not in ("scene_id", "corr_full", "corr_bank", "pass_v2",
                                 "pass_original", "corr_v2")}, ensure_ascii=False)[:150]))
print()
neg = d["negatives_constructed"]
print("=== negatives ({} 条) ===".format(len(neg)))
print("  键样例:", sorted(neg[0].keys()))
fp = [x for x in neg if x.get("pass_v2")]
print("  **v2 误通过条目（{} 条）**:".format(len(fp)))
for x in fp:
    print("   ", json.dumps(x, ensure_ascii=False)[:400])
print()
print("  负例 other 字段分布（前 12）:")
for x in neg[:12]:
    print("    {} other={} corr_full={} corr_bank={}".format(
        x.get("scene_id"), str(x.get("other"))[:40], x.get("corr_full"), x.get("corr_bank")))
