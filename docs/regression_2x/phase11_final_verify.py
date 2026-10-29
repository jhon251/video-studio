# -*- coding: utf-8 -*-
"""Phase 11 收尾核验：报告台账 ↔ 实际文件；登记条目；回测判据；回归；不可变；config 零改动。"""
import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")

rep_path = R / "docs" / "regression_2x" / "PHASE11_REPORT.md"
ledger = {}
for line in rep_path.read_text(encoding="utf-8").splitlines():
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
print("STATUS 含 Phase 11 条目:", "Phase 11（2026-09-30）标题与封面候选工程" in st)
print("STATUS 保留 Phase 7–10 登记:", all(k in st for k in ("Phase 10（2026-09-30）",
                                                          "Phase 9（2026-09-30）",
                                                          "Phase 8（2026-09-30）",
                                                          "差异登记（Phase 7）")))
print("CHANGELOG 含 Phase 11 条目:", "## Phase 11 — 标题与封面候选工程" in cl)

cfg = hashlib.sha256((R / "config" / "config.json").read_bytes()).hexdigest()
ex = hashlib.sha256((R / "config" / "config.example.json").read_bytes()).hexdigest()
print("config.json 零改动:", cfg.startswith("7b03424846f1"), "| config.example.json:",
      ex.startswith("d5e838509d0c"))

ab = json.loads((L / "phase11_title_ab.json").read_text(encoding="utf-8"))
print("回测判据①:", ab["criterion_1_all_gates_pass"]["pass"], "PASS /",
      ab["criterion_1_all_gates_pass"]["candidates"], "| 数字可溯 100%:",
      ab["criterion_1_all_gates_pass"]["number_traceability_100pct"],
      "| 手法数:", len(ab["criterion_1_all_gates_pass"]["techniques"]))
print("判据② 能力增量:", ab["criterion_2_vs_legacy"]["capability_increment"],
      "| 判据④ execution=manual:", ab["criterion_4_ab_plan"]["execution_is_manual"],
      "| 判据③:", ab["criterion_3_manual_spot_check"]["status"][:14])
print("成本:", ab["cost_usd_total"], "（上限", ab["cost_limit_usd"], "）")
suites = json.loads((L / "suites_summary.json").read_text(encoding="utf-8"))
print("回归:", len(suites), "套件 | rc!=0:", [x["suite"] for x in suites if x["rc"] != 0] or "NONE")
im = json.loads((L / "phase11_immutable_check.json").read_text(encoding="utf-8"))
print("不可变核验:", im["verdict"], "| 钉定一致性:", im["expect_match"])
