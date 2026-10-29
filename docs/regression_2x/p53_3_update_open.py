# -*- coding: utf-8 -*-
"""Phase 53：把「回归未决项」登记更新为**已收敛**（最终回归 94/94）。"""
from __future__ import annotations

import collections
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
P = R / "docs" / "regression_2x" / "logs" / "p53_3_regression_open_items.json"
sys.stdout.reconfigure(encoding="utf-8")

d = json.loads(P.read_text(encoding="utf-8"),
               object_pairs_hook=collections.OrderedDict)
d["final_regression"] = {
    "rc0": 94, "suites_total": 94, "failed": [], "elapsed_s": 2644.5,
    "conclusion": "**94/94 全绿** —— 两项未决均已收敛",
}
o1 = d["open_item_1_caption_overlap_scoping"]
o1["status"] = "**已修**；回归内 PASS"
o2 = d["open_item_2_mm_quality_db_isolation"]
o2["status"] = "**已收敛（无需改代码）**"
o2["true_root_cause"] = (
    "**两个回归并发运行**：先前的「干净回归」(92/94) 与 F9 的回归 (pwsh-2081) "
    "**时间窗重叠** ⇒ 两个 runner 同时在写库 ⇒ 只读断言被**对方**打破。"
    "本次 F9 回归在**完全独占**条件下运行 ⇒ `mm_quality_test` PASS "
    "⇒ **证实该项不是产品缺陷，而是「并发回归互相干扰」**。")
o2["revised_recommendation"] = (
    "纪律层「我回归期间不写库」是**必要但不充分**：还必须保证"
    "**同一时刻只有一个回归在跑**（**runner 层互斥**），"
    "否则**两个 runner 会互相打破对方的只读断言**。"
    "本轮已用两次回归（92/94 并发 vs 94/94 独占）实证这一点。")
P.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
print("已更新未决项登记：最终回归 {} / {}".format(
    d["final_regression"]["rc0"], d["final_regression"]["suites_total"]))
print("  未决 1：", o1["status"])
print("  未决 2：", o2["status"])
print("  未决 2 真因：并发回归互相干扰（非产品缺陷）")
