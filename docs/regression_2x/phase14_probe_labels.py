# -*- coding: utf-8 -*-
"""P14-2 人工标签盘点（只读）：把 A–F 各来源的**逐对**人工标签清点出来，并统计可用规模。"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import sys
from collections import Counter

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")

vr = json.loads((L / "visual_relevance.json").read_text(encoding="utf-8"))
sr = vr["scene_results"]

print("=" * 78)
print("A. visual_relevance.json —— 逐候选完整证据（非 NA 部分）")
print("=" * 78)
for s in sr:
    for c in (s.get("candidate_results") or []):
        if c.get("decision") == "NOT_ASSESSABLE":
            continue
        ev = c.get("evidence") or []
        print("{} {} {} | decision={} rule={}".format(
            c["scene_id"], c["asset_id"], c["requirement_id"][:14],
            c["decision"], c["decision_rule"]))
        print("    assessability:", json.dumps(c.get("assessability"), ensure_ascii=False)[:160])
        print("    confidence:", c.get("confidence"))
        for e in ev[:2]:
            print("    evidence:", json.dumps(e, ensure_ascii=False)[:340])
        print("    negative_conflicts:", json.dumps(c.get("negative_conflicts"),
                                                     ensure_ascii=False)[:200])

print()
print("=" * 78)
print("A2. 一个 NA 候选的完整形态（供 P14-3 目标参考）")
print("=" * 78)
for s in sr:
    for c in (s.get("candidate_results") or []):
        if c.get("decision") == "NOT_ASSESSABLE":
            print(json.dumps(c, ensure_ascii=False, indent=1)[:1500])
            raise SystemExit(0)
