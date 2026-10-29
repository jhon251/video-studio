# -*- coding: utf-8 -*-
"""Phase 10 只读提取：3 采样聚合明细 + topic A/B 明细（供报告）。"""
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")
t = json.loads((L / "phase10_retention_3sample.json").read_text(encoding="utf-8"))
print("== 3 采样聚合 ==")
for arm, d in t["arms"].items():
    print(" [{}] mech={} llm={} cost={}".format(arm, d["mechanical_score"], d["llm_status"],
                                                d["cost_usd_total"]))
    print("      cta codes:", d.get("mechanical_cta_codes"))
    for item, blk in (d["aggregation"] or {}).items():
        print("      {:16s} median={} range={} agreement={} samples={}".format(
            item, blk["median"], blk["range"], blk["agreement"], blk["samples"]))
print(" 判据 v3 median>=v2 median:", t["criterion_v3_median_ge_v2"], "| 花费", t["spent_usd"])
a = json.loads((L / "phase10_topic_ab.json").read_text(encoding="utf-8"))
print("\n== topic A/B ==")
print(" 快照:", json.dumps(a["snapshot"], ensure_ascii=False))
print(" 网络:", json.dumps(a["network_requests"], ensure_ascii=False))
for lab, d in a["arms"].items():
    print(" [{}] status={} proposals={} cost={}".format(lab, d["task_status"],
                                                        d["criteria"]["proposals"],
                                                        d["cost_usd"]))
    for p in d["payload"]["proposals"][:2]:
        print("      -", str(p.get("title"))[:46], "| refs=", p.get("signal_refs"),
              "| why_now=", str(p.get("why_now"))[:56])
    print("      criteria:", json.dumps(d["criteria"], ensure_ascii=False)[:260])
print(" 判定:", json.dumps(a["verdict"], ensure_ascii=False), "| 花费", a["spent_usd"])
