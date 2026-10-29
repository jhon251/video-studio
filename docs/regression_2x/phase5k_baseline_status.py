# -*- coding: utf-8 -*-
"""5-K：从证据包生成基线状态文件（明示"回归未全绿"，防止被误引用为已验收）。

用法: python docs/regression_2x/phase5k_baseline_status.py
产出: docs/regression_2x/baseline/baseline_status_5.x-post-final-maintenance-baseline.json
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
R2 = ROOT / "docs" / "regression_2x"
ev = json.loads((R2 / "logs" / "phase5k_evidence.json").read_text(encoding="utf-8"))
bl = ev["baselines"]
b = ev["full_regression_batch"]
s = ev["suites_summary"]
t = ev["targeted_regression"]
st = {
    "tag": "5.x-post-final-maintenance-baseline",
    "frozen_at": ev["generated_at"],
    "zip_sha256": bl["new"]["zip_sha256"],
    "file_count": bl["new"]["file_count"],
    "verify_baseline": bl["new"]["verdict"],
    "missing_in_tree": bl["new"]["missing_in_tree"],
    "drift_vs_tree": bl["new"]["drift_vs_tree"],
    "previous_baseline": {"tag": "5.x-final-baseline", "zip_sha256": bl["final_zip_sha256"],
                          "entries": bl["final_zip_entries"], "untouched": bl["final_zip_unchanged"]},
    "regression_status": {
        "verdict": "NOT_ALL_GREEN",
        "targeted": t["ratio"],
        "batch_items": b["items"], "batch_as_expected": b["as_expected"],
        "batch_red": b["unexpected"],
        "suites_total": s["suites"], "suites_rc0": s["rc0"], "suites_red": s["failed"],
        "readonly_battery_subset": "{}/{}".format(ev["battery_readonly_subset"]["rc0"],
                                                  ev["battery_readonly_subset"]["total"]),
        "e2e_mechanical": "rc=0 但结果为 A/B=MAXROUNDS、C=BLOCKED（冻结时代为 3/3 SETTLED）",
        "root_cause": "红项根因 = 授权 item ③（采纳真实默认配置，移除内联 llm.mock）的副作用，"
                      "或环境网络（Wikimedia TLS 超时）；与 ①②④ 的代码改动无关（守卫/反证见 "
                      "tests/maintenance_fixes_test.py M2/M3/M4/M5/M8）",
        "registered_known_issues": ["#56", "#57", "#59", "#60", "#61", "#62", "#63", "#64"],
        "cost_usd_real_api_today": ev["cost_probe"]["total_cost_usd"],
    },
    "frozen_evidence_logs_restored": ev["logs_restore"]["verdict"],
    "note": "本基线按 5-K 授权 item ⑨ 冻结；**不满足**项目既有『电池全绿才冻结』的 DoD 前置条件，"
            "差异已在此文件、PHASE5K_REPORT.md 与 CHANGELOG 5-K 条目中显式标注，"
            "不得作为『全绿验收基线』引用。",
}
out = R2 / "baseline" / "baseline_status_5.x-post-final-maintenance-baseline.json"
out.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({"tag": st["tag"], "zip_sha256": st["zip_sha256"][:16],
                  "verify": st["verify_baseline"],
                  "regression": st["regression_status"]["verdict"],
                  "batch": "{}/{}".format(st["regression_status"]["batch_as_expected"],
                                          st["regression_status"]["batch_items"]),
                  "suites": "{}/{}".format(st["regression_status"]["suites_rc0"],
                                           st["regression_status"]["suites_total"])},
                 ensure_ascii=False))
print("->", out)
