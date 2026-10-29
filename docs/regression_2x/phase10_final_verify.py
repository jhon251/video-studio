# -*- coding: utf-8 -*-
"""Phase 10 收尾核验：报告 sha256 台账 ↔ 实际文件；登记条目；A/B 与 3 采样判据；回归；不可变。"""
import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")

rep_path = R / "docs" / "regression_2x" / "PHASE10_REPORT.md"
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
print("STATUS 含 Phase 10 条目:", "Phase 10（2026-09-30）数据驱动选题" in st)
print("STATUS 保留 Phase 9/8/7 登记:", "Phase 9（2026-09-30）" in st and "Phase 8（2026-09-30）" in st
      and "差异登记（Phase 7）" in st)
print("CHANGELOG 含 Phase 10 条目:", "## Phase 10 — 数据驱动选题" in cl)

t = json.loads((L / "phase10_retention_3sample.json").read_text(encoding="utf-8"))
print("3 采样判据 v3 median ≥ v2 median:", t["criterion_v3_median_ge_v2"],
      "| 花费 $", t["spent_usd"])
a = json.loads((L / "phase10_topic_ab.json").read_text(encoding="utf-8"))
print("topic A/B 判定:", json.dumps(a["verdict"], ensure_ascii=False))
print("网络:", json.dumps(a["network_requests"], ensure_ascii=False))
suites = json.loads((L / "suites_summary.json").read_text(encoding="utf-8"))
failed = [x["suite"] for x in suites if x["rc"] != 0]
print("回归:", len(suites), "套件 | rc!=0:", failed or "NONE")
im = json.loads((L / "phase10_immutable_check.json").read_text(encoding="utf-8"))
print("不可变核验:", im["verdict"], "| 历史一致性:", im["expect_match"])
snaps = sorted((R / "signals").glob("snapshot_*.json"))
print("快照文件:", [p.name for p in snaps])
