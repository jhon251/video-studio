# -*- coding: utf-8 -*-
"""Phase 10 只读提取（二）：3 采样聚合的覆盖与一致性明细。"""
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")
t = json.loads((L / "phase10_retention_3sample.json").read_text(encoding="utf-8"))
for arm, d in t["arms"].items():
    print("[{}] mech={} cost={} cta_codes={}".format(arm, d["mechanical_score"],
                                                    d["cost_usd_total"],
                                                    d.get("mechanical_cta_codes")))
    for item, blk in (d["aggregation"] or {}).items():
        print("   {:16s} median={} range={} agree={} scored={}/{} coverage={}".format(
            item, blk["median"], blk["range"], blk["agreement"], blk.get("scored_samples"),
            len(blk.get("samples") or []), blk.get("sample_coverage")))
        if blk.get("coverage_note") and blk.get("scored_samples") != len(blk.get("samples") or []):
            print("        note:", blk["coverage_note"])
print("总花费:", t["spent_usd"], "| 判据:", t["criterion_v3_median_ge_v2"])
