# -*- coding: utf-8 -*-
"""Phase 18 收尾校验（只读）：交付物齐备性 + 关键结论复核。"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")

D = [("诊断模块(P18-1 bank)", R / "src/video_studio/core/corr_diagnostics.py"),
     ("VLM 存在性任务", R / "src/video_studio/tools/vlm_judge.py"),
     ("P18-1 修复验证", L / "phase18_p18_1_present_fix.json"),
     ("P18-2 v3 变体", L / "phase18_p18_2_v3_variants.json"),
     ("P18-2b 多分辨率", L / "phase18_p18_2b_multires_bank.json"),
     ("P18-3 VLM 评测", L / "phase18_p18_3_vlm_presence.json"),
     ("P18-3 仲裁层", L / "phase18_p18_3_arbitration.json"),
     ("tests", R / "tests/corr_metric_diagnostics_test.py"),
     ("阶段报告", R / "docs/regression_2x/PHASE18_REPORT.md")]
miss = []
for n, p in D:
    if p.is_file():
        print("  OK   {:22s} {:>8,}B sha={}…".format(
            n, p.stat().st_size, hashlib.sha256(p.read_bytes()).hexdigest()[:12]))
    else:
        miss.append(n)
        print("  MISS", n)
print("  缺失:", miss or "无")
print()
a = json.loads((L / "phase18_p18_1_present_fix.json").read_text(encoding="utf-8"))
print("P18-1: 旧在屏 {}/5 -> 修复 {}/5 | 反门 >=0.30 的 {} | 结论: {}".format(
    a["on_screen_old"], a["on_screen_new"], a["negatives_at_or_above_threshold"],
    a["verdict"]))
b = json.loads((L / "phase18_p18_2b_multires_bank.json").read_text(encoding="utf-8"))
best = max(b["variants"].items(), key=lambda kv: (kv[1]["pos_pass"], -kv[1]["neg_false_pass"]))
print("P18-2: 最佳 {} 正门 {}/5 反门 {}/55 | adopted={}".format(
    best[0], best[1]["pos_pass"], best[1]["neg_false_pass"], b["adopted"] or "NONE"))
c = json.loads((L / "phase18_p18_3_vlm_presence.json").read_text(encoding="utf-8"))
print("P18-3: 一致 {}/{} = {} | false-present {} | 门禁通过 {}".format(
    c["results"]["agree"], c["results"]["total"], c["results"]["agreement"],
    c["results"]["false_present"], c["gate"]["passed"]))
print("        成本 ${:.4f}（上限 ${:.2f}）".format(
    c["cost"]["spent_usd"], c["cost"]["budget_usd"]))
d = json.loads((L / "phase18_p18_3_arbitration.json").read_text(encoding="utf-8"))
print("P18-3 仲裁:", json.dumps(d["summary"], ensure_ascii=False))
k = (R / "docs" / "KNOWN_ISSUES.md").read_text(encoding="utf-8")
print("KNOWN_ISSUES #74:", "## 74." in k, "| #73 仍 OPEN 且已标注与 #74 关系:",
      ("与 #74 的关系" in k))
s = (R / "STATUS.md").read_text(encoding="utf-8").splitlines()
print("STATUS 首块:", s[2][:78] if len(s) > 2 else "")
