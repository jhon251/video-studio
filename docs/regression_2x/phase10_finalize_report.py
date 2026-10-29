# -*- coding: utf-8 -*-
"""Phase 10 收尾：刷新报告中 topic_signals.py / cli.py 的 sha256，并写入最终回归数字。"""
import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
rep = R / "docs" / "regression_2x" / "PHASE10_REPORT.md"
s = rep.read_text(encoding="utf-8")
for rel in ("src/video_studio/tools/topic_signals.py", "src/video_studio/cli.py",
            "src/video_studio/agents/topic/agent.py", "src/video_studio/ops/retention.py",
            "src/video_studio/core/retention.py", "src/video_studio/agents/script/agent.py",
            "config/script_style_guide.md", "tests/topic_signals_test.py",
            "docs/regression_2x/logs/phase10_retention_3sample.json",
            "docs/regression_2x/logs/phase10_topic_ab.json",
            "config/topic_signals.example.json"):
    h = hashlib.sha256((R / rel).read_bytes()).hexdigest()
    for line in s.splitlines():
        if line.startswith("| ") and "`{}`".format(rel) in line:
            parts = line.strip("|").split("|")
            old = parts[1].strip().strip("` ")
            if old != h:
                s = s.replace(line, line.replace(old, h))
                print("  刷新 {}: {} -> {}".format(rel, old[:12], h[:12]))
# 最终回归数字
s = s.replace("| **完整既有回归** | **见下方回归快照**（Phase 9 口径 72 套件 + 本阶段新增 1 套件） |",
              "| **完整既有回归** | **73 套件 / 73 rc=0 / FAILED: []**（Phase 9 口径 72 套件 + 本阶段新增 "
              "`topic_signals_test`；期间 M5d/L7b 因 config 改写一度转红，复原后恢复全绿——见 §1.1） |")
rep.write_text(s, encoding="utf-8")
suites = json.loads((R / "docs" / "regression_2x" / "logs" / "suites_summary.json").read_text(
    encoding="utf-8"))
print("回归:", len(suites), "套件 | rc!=0:", [x["suite"] for x in suites if x["rc"] != 0] or "NONE")
print("报告含 73/73 表述:", "73 套件 / 73 rc=0" in rep.read_text(encoding="utf-8"))
