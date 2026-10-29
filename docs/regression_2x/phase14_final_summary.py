# -*- coding: utf-8 -*-
"""P14-2 两份报告的最终摘要（只读）。"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
for n in ("phase14_eval_report.json", "phase14_eval_diag_anchor.json"):
    j = json.loads((R / "docs/regression_2x/logs" / n).read_text(encoding="utf-8"))
    r = j["results"]
    print("=" * 74)
    print(n)
    print("  report_kind :", j.get("report_kind", "GATE（门禁口径）"))
    print("  prompt      :", j["pairs"][0]["cache_key"] and j.get("policy") and
          "version 见 pairs", "|", j["pairs"][0].get("truth_provenance") and "")
    print("  agreement   :", r["agreement"], "| agree", r["agree"], "/", r["pairs_total"])
    print("  confusion   :", json.dumps(r["confusion"], ensure_ascii=False))
    print("  FP(人IRR→机REL):", len(r["human_irrelevant_to_machine_relevant"]),
          "| 正例误判:", len(r["human_relevant_to_machine_irrelevant"]),
          "| 非二值:", len(r["non_matching"]))
    print("  spent       : ${:.4f} | api {} | cache {}".format(
        j["cost"]["spent_usd"], j["cost"]["api_calls"], j["cost"]["cache_hits"]))
    print("  gate passed :", j["gate"]["passed"], "|", j["gate"]["decision"])
    print("  truth pairs :", j["truth"]["pair_count"], "| meets_min:",
          j["truth"]["meets_min_pairs"])
