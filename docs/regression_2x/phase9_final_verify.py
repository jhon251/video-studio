# -*- coding: utf-8 -*-
"""Phase 9 收尾核验：报告 sha256 台账 ↔ 实际文件；登记条目；回测判据；回归摘要；不可变。"""
import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")

rep_txt = (R / "docs" / "regression_2x" / "PHASE9_REPORT.md").read_text(encoding="utf-8")
ledger = {}
for line in rep_txt.splitlines():
    if line.startswith("| ") and line.count("|") >= 3 and "`" in line:
        parts = [p.strip() for p in line.strip("|").split("|")]
        if len(parts) >= 2:
            first = parts[0]
            name = first.split("`")[1].strip() if "`" in first else first.strip()
            h = parts[1].strip("` ")
            if len(h) == 64 and all(c in "0123456789abcdef" for c in h):
                ledger[name] = h
bad = []
for f, h in ledger.items():
    p = R / f
    if not p.is_file():
        bad.append((f, "文件不存在"))
        continue
    actual = hashlib.sha256(p.read_bytes()).hexdigest()
    if actual != h:
        bad.append((f, "{} != {}".format(h[:12], actual[:12])))
print("报告 sha256 台账条目数:", len(ledger))
print("台账 ↔ 实际文件:", "NONE 不一致" if not bad else bad)

st = (R / "STATUS.md").read_text(encoding="utf-8")
cl = (R / "CHANGELOG.md").read_text(encoding="utf-8")
print("STATUS 含 Phase 9 条目:", "Phase 9（2026-09-30）retention-critic" in st)
print("STATUS 保留 Phase 8/Phase 7 登记:", "Phase 8（2026-09-30）" in st and "差异登记（Phase 7）" in st)
print("CHANGELOG 含 Phase 9 条目:", "## Phase 9 — retention-critic" in cl)

s = json.loads((L / "phase9_backtest_summary.json").read_text(encoding="utf-8"))
print("判据① :", s["criterion_1_ok"], "| 判据② :", s["criterion_2_ok"],
      "| 判据④ 基线:", s["criterion_4_prod_baseline"], "| 成本 $", s["total_cost_usd"])
print("二次运行 命中/一致:", s["second_run_all_cache_hit"], s["second_run_all_identical"])
v = json.loads((L / "phase9_retention_variance.json").read_text(encoding="utf-8"))
print("采样方差: v2", v["arms"]["v2"]["hook_scores"], "v3", v["arms"]["v3"]["hook_scores"],
      "| 配对达成率", v["criterion2_met_rate"])
suites = json.loads((L / "suites_summary.json").read_text(encoding="utf-8"))
failed = [x["suite"] for x in suites if x["rc"] != 0]
print("回归:", len(suites), "套件 | rc!=0:", failed or "NONE")
im = json.loads((L / "phase9_immutable_check.json").read_text(encoding="utf-8"))
print("不可变核验:", im["verdict"], "| 历史一致性项:", im["expect_match"])
