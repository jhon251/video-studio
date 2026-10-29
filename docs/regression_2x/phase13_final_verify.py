# -*- coding: utf-8 -*-
"""Phase 13 最终核验：报告台账 ↔ 文件、登记条目、逐项判定、回归、不可变、config 零改动。"""
import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")
ledger = {}
for line in (R / "docs" / "regression_2x" / "PHASE13_REPORT.md").read_text(
        encoding="utf-8").splitlines():
    if line.startswith("| ") and line.count("|") >= 3 and "`" in line:
        parts = [p.strip() for p in line.strip("|").split("|")]
        if len(parts) >= 2:
            first = parts[0]
            name = first.split("`")[1].strip() if "`" in first else first.strip()
            h = parts[1].strip("` ")
            if len(h) == 64 and all(c in "0123456789abcdef" for c in h):
                ledger[name] = h
bad = [(f, "hash") for f, h in ledger.items()
       if not (R / f).is_file() or hashlib.sha256((R / f).read_bytes()).hexdigest() != h]
print("报告台账条目数:", len(ledger), "| 不一致:", bad or "NONE")
st = (R / "STATUS.md").read_text(encoding="utf-8")
cl = (R / "CHANGELOG.md").read_text(encoding="utf-8")
print("STATUS 含 Phase 13 逐项判定:", "P13-1 DONE" in st and "P13-4 PENDING" in st
      and "P13-5 PENDING" in st)
print("STATUS 保留 Phase 7–12:", all(k in st for k in ("Phase 12（2026-09-30）", "Phase 11（2026-09-30）",
                                                       "Phase 10（2026-09-30）", "Phase 9（2026-09-30）",
                                                       "Phase 8（2026-09-30）", "差异登记（Phase 7）")))
print("CHANGELOG 含 Phase 13:", "## Phase 13 — 运动层生产接线" in cl)
cfg = hashlib.sha256((R / "config" / "config.json").read_bytes()).hexdigest()
print("config.json 零改动:", cfg.startswith("7b03424846f1"),
      "| render_motion 未进 config.json:",
      "render_motion" not in (R / "config" / "config.json").read_text(encoding="utf-8"))
v = json.loads((L / "phase13_motion_render_verify.json").read_text(encoding="utf-8"))
print("P13-3 summary:", json.dumps(v["summary"], ensure_ascii=False))
suites = json.loads((L / "suites_summary.json").read_text(encoding="utf-8"))
print("回归:", len(suites), "套件 | rc!=0:", [x["suite"] for x in suites if x["rc"] != 0] or "NONE")
im = json.loads((L / "phase13_immutable_check.json").read_text(encoding="utf-8"))
print("不可变:", im["verdict"], "| 钉定一致性:", im["expect_match"])
