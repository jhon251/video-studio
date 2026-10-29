# -*- coding: utf-8 -*-
"""5-E 报告素材提取：把校准报告里的边界/敏感性/top-k 证据压缩打印（只读）。"""
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
d = json.loads((ROOT / "docs" / "regression_2x" / "logs" / "phase5e_quality.json")
               .read_text(encoding="utf-8-sig"))

print("== 每个用例的边界距离（模型证据 vs 阈值） ==")
for c in d["cases"]:
    for layer in ("5a", "5d"):
        bd = (c.get("boundary") or {}).get(layer) or {}
        if not bd:
            continue
        obs = (c["layers"][layer].get("observed") or {})
        def s(v):
            return "-" if v is None else str(v)
        print("  {:<42} {:<3} {:<9} sim-min={:<10} |margin|-thr={:<11} vote-min={:<9} "
              "stab-min={:<10} top1={}".format(
                  c["case_id"], layer, s(obs.get("verdict")), s(bd.get("sim_above_min_sim")),
                  s(bd.get("margin_above_threshold")), s(bd.get("vote_above_min_frac")),
                  s(bd.get("stability_above_min")), s(bd.get("expected_in_top1"))))

print("\n== 敏感性命中（只看 5-A/5-D，按用例） ==")
for r in d["sensitivity"]["rows"]:
    if not r["flip_count"]:
        continue
    print("  {:<42} {:<3} base={:<9} flips={}".format(
        r["case_id"], r["layer"], r["base_verdict"],
        json.dumps(r["flips"], ensure_ascii=False)))

print("\n== 各层 top-k / 相似度（S04/S05/S06 相关用例） ==")
for c in d["cases"]:
    if not any(s in c["case_id"] for s in ("S04", "S05", "S06")):
        continue
    for layer in ("5a", "5d"):
        e = c["layers"].get(layer) or {}
        m = e.get("metrics") or {}
        if not m:
            continue
        print("  {:<42} {:<3} 期望域={:<16} top-k={}".format(
            c["case_id"], layer, m.get("expected_domain"),
            [(x.get("domain"), x.get("sim")) for x in (m.get("top_k") or [])][:3]))

print("\n== 证据等级字段统计 ==")
print(json.dumps(d["evidence_classes"]["field_counts"], ensure_ascii=False))
print("\n== 指标 ==")
for k, v in d["metrics"].items():
    print("  {:<3} 用例={:<3} 违例={} 未解决={} UNKNOWN={} MATCH={} MISMATCH={} MATCH精确率={} "
          "MISMATCH召回={} MATCH召回={} 误判MATCH={} 弱证据UNKNOWN={}".format(
              k, v["cases_with_expectation"], v["violation_count"],
              v["cases_with_expectation"] - v["resolved"], v["unknown_count"], v["match_count"],
              v["mismatch_count"], v["match_precision_on_truth"], v["mismatch_recall_on_truth"],
              v["match_recall_on_truth"], v["false_match_on_mismatch_cases"],
              v["unknown_on_match_cases"]))
