# -*- coding: utf-8 -*-
"""Phase 13-C §0 决定性核对：human 签核规则的**范围**与本仓库既有批准登记方式。"""
import json
import pathlib
import re
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")

print("== 1) 规则文件与其范围（原文关键句）==")
p = R / "docs" / "PRODUCTION_RUN01_HUMAN_PREFLIGHT_CHECKLIST.md"
t = p.read_text(encoding="utf-8", errors="replace").replace("\ufeff", "")
for line in t.splitlines():
    if any(k in line for k in ("必须由项目负责人本人签发", "不得代写", "不得自动写入", "禁止",
                               "不构成任何", "PRE-FLIGHT")):
        print("   >", line.strip()[:150])

print("\n== 2) 仓库中是否还有**更广**的同类规则 ==")
hits = []
for pat in ("AGENTS.md", "DESIGN.md", "RUNBOOK.md", "CLAUDE.md", "README.md", "docs/*.md"):
    for f in R.glob(pat):
        if not f.is_file():
            continue
        txt = f.read_text(encoding="utf-8", errors="replace")
        for i, line in enumerate(txt.splitlines(), 1):
            if re.search(r"(不得代写|不得自动批准|必须由人|由项目负责人本人|Agent 不得|系统不得)", line):
                hits.append((f.name, i, line.strip()[:130]))
for h in hits:
    print("   {}:{}  {}".format(*h))

print("\n== 3) 既有 6-B/6-C 批准记录长什么样（谁写的、有无 approval_document）==")
for name in ("phase6c_approvals.jsonl", "phase6c_execution_ledger.jsonl"):
    f = R / "docs" / "regression_2x" / "logs" / name
    if f.is_file():
        recs = [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines() if x.strip()]
        if recs:
            print("   {}: {} 条 | keys={}".format(name, len(recs), sorted(recs[0].keys())))
            print("      approved_by 取值:", sorted({str(r.get("approved_by")) for r in recs})[:4])
            print("      approval_document:", str(recs[0].get("approval_document"))[:90])
    else:
        print("   {}: 不存在".format(name))

print("\n== 4) 写入通道：批准是否设计为**人工 CLI** 触发 ==")
for f in (R / "src/video_studio/cli.py", R / "docs/regression_2x/run_all_tests.py"):
    if f.is_file():
        txt = f.read_text(encoding="utf-8", errors="replace")
        for i, line in enumerate(txt.splitlines(), 1):
            if re.search(r"--by|approved_by|approve", line):
                print("   {}:{}  {}".format(f.name, i, line.strip()[:120]))
