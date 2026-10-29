# -*- coding: utf-8 -*-
"""P16-1 结论固化（含"为什么不能用可调阈值救"的数字证据）。"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
LOGS = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")

rep = json.loads((LOGS / "phase16_negative_filter_report.json").read_text(encoding="utf-8"))
neg, pos = rep["negatives"], rep["positives"]

print("=" * 78)
print("P16-1 结论：FAIL ⇒ 过滤器不接线，P16-3 回退人工短名单")
print("=" * 78)
print("  负例捕获 {} / {} = {:.2%}（阈值 ≥60%）".format(
    rep["results"]["negatives_captured"], rep["results"]["negatives_total"],
    rep["results"]["negative_capture_rate"]))
print("  正例误杀 {} / {} = {:.2%}（阈值 ≤5%，即 ≤1 条）".format(
    rep["results"]["positives_falsely_killed"], rep["results"]["positives_total"],
    rep["results"]["false_kill_rate"]))
print("  各负例类型捕获率:", json.dumps(rep["results"]["negative_capture_by_kind"],
                                        ensure_ascii=False))
print()
print("  关键观察：**误杀率与 P14-2 的门禁失配统计同源**")
print("    P14-2 24 条人工正例中机器判 IRRELEVANT = 13 条（54.2%）；")
print("    本阶段同一 prompt、同一 24 条正例的误杀 = {} 条（{:.2%}）".format(
    rep["results"]["positives_falsely_killed"],
    rep["results"]["false_kill_rate"]))
print("    ⇒ 二者是**同一个统计量**：该 VLM 在本片需求定义下对『切题但非逐元素复现』的正例")
print("      系统性判无关。故『作负例过滤器』与 P14-2『≥90% 一致』**不可能同时成立**。")
print()
print("  逐条置信度与是否误杀（检验『能不能用阈值救』）:")
miss = []
for x in pos:
    if x["deny"]:
        miss.append((x.get("pos_id"), x["machine_reason"]))
print("    误杀条数:", len(miss), "（>1 ⇒ 无论怎么调阈值都无法满足 ≤5%）")
print()
print("  人工负例 vs 构造负例（分开统计，未混为一谈）:")
for k, v in sorted(rep["results"]["negative_capture_by_kind"].items()):
    print("    {:24s} {}/{} = {:.2%}".format(k, v["captured"], v["total"],
                                             v["capture_rate"]))
print()
print("  每条 DENY 均附理由:", rep["gate"]["every_deny_has_reason"])
print("  成本: ${:.4f}（VLM 上限 $1）| API {} 次".format(
    rep["cost"]["spent_usd"], rep["cost"]["api_calls"]))
print()
print("  回退路径（授权书 §2）：P16-3 获取预筛 = **人工短名单（provider 元数据）**，过滤器不接线。")

out = {
    "schema": "phase16-p16-1-conclusion-v1",
    "gate_passed": rep["gate"]["passed"],
    "decision": rep["gate"]["decision"],
    "negative_capture_rate": rep["results"]["negative_capture_rate"],
    "false_kill_rate": rep["results"]["false_kill_rate"],
    "by_kind": rep["results"]["negative_capture_by_kind"],
    "shared_statistic_note": (
        "误杀率与 P14-2 门禁失配同源（同一 prompt/同一 24 正例，机器 IRRELEVANT 均 13 条）"
        "⇒ 『负例过滤器』与『≥90% 一致』互斥，属 KNOWN_ISSUES #73 的同一根因（判据不同源）。"),
    "fallback": "P16-3 预筛回退人工短名单（provider 元数据）；过滤器不接线",
    "threshold_tuning_rejected": True,
    "threshold_tuning_reason": (
        "误杀 {} 条 > 允许 1 条（≤5%×24）；任何『只信高置信度 DENY』的后验阈值调整"
        "均属运行后调参（授权书禁止），故如实 FAIL，不调参救援。").format(
            rep["results"]["positives_falsely_killed"]),
    "cost_usd": rep["cost"]["spent_usd"],
}
p = LOGS / "phase16_p16_1_conclusion.json"
p.write_text(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
print("  结论 ->", p.relative_to(R).as_posix())
