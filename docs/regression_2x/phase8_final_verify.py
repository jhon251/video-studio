# -*- coding: utf-8 -*-
"""Phase 8 收尾核验：报告 sha256 台账 ↔ 实际文件；登记条目；回归摘要。"""
import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
rep = (R / "docs" / "regression_2x" / "PHASE8_REPORT.md").read_text(encoding="utf-8")

ledger = {}
for line in rep.splitlines():
    if line.startswith("| ") and line.count("|") >= 3 and "`" in line:
        parts = [p.strip() for p in line.strip("|").split("|")]
        if len(parts) >= 2:
            first = parts[0]
            if "`" in first:                      # 取第一个反引号片段作为路径
                name = first.split("`")[1].strip()
            else:
                name = first.strip()
            h = parts[1].strip("` ")
            if len(h) == 64 and all(c in "0123456789abcdef" for c in h):
                ledger[name] = h

files = ["config/script_style_guide.md", "docs/regression_2x/phase8_style_v2_snapshot.md",
         "src/video_studio/agents/script/agent.py", "src/video_studio/agents/structure/agent.py",
         "tests/creator_style_v3_test.py", "tests/strip_v2_test.py", "tests/pipeline_mock.py",
         "docs/regression_2x/logs/phase8_ab_v2.json",
         "docs/regression_2x/logs/phase8_ab_v3.json",
         "docs/regression_2x/logs/phase8_ab_crosscheck.json"]
bad = []
for f in files:
    h = hashlib.sha256((R / f).read_bytes()).hexdigest()
    rec = ledger.get(f)
    if rec is None:
        bad.append((f, "报告台账缺条目"))
    elif rec != h:
        bad.append((f, "{} != {}".format(rec[:12], h[:12])))
print("报告 sha256 台账条目数:", len(ledger))
print("台账 ↔ 实际文件:", "NONE 不一致" if not bad else bad)

st = (R / "STATUS.md").read_text(encoding="utf-8")
cl = (R / "CHANGELOG.md").read_text(encoding="utf-8")
print("STATUS 含 Phase 8 条目:", "Phase 8（2026-09-30）Creator Style v3" in st)
print("STATUS 含 Phase 7 差异登记:", "差异登记（Phase 7）" in st)
print("CHANGELOG 含 Phase 8 条目:", "## Phase 8 — Creator Style v3" in cl)
print("CHANGELOG 含 Phase 7 差异登记:", "登记差异（Phase 7）" in cl)

s = json.loads((R / "docs" / "regression_2x" / "logs" / "suites_summary.json").read_text(
    encoding="utf-8"))
failed = [x["suite"] for x in s if x["rc"] != 0]
print("回归摘要: {} 套件 | rc!=0: {}".format(len(s), failed or "NONE"))
im = json.loads((R / "docs" / "regression_2x" / "logs" / "phase8_immutable_check.json").read_text(
    encoding="utf-8"))
print("不可变核验:", im["verdict"], "| 期望一致项:", im["immutable_match_expect"])
