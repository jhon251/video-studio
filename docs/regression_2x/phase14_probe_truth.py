# -*- coding: utf-8 -*-
"""P14-2 真值来源结构勘查（只读）：确认可用字段、规模与可配对性。"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")

print("=" * 78)
print("A. logs/visual_relevance.json")
print("=" * 78)
vr = json.loads((L / "visual_relevance.json").read_text(encoding="utf-8"))
print("top keys:", sorted(vr.keys()))
sr = vr.get("scene_results") or []
print("scene_results:", len(sr))
if sr:
    print("scene[0] keys:", sorted(sr[0].keys()))
    cr = sr[0].get("candidate_results") or []
    print("candidate_results[0] keys:", sorted(cr[0].keys()) if cr else None)
    if cr:
        print("cand[0] sample:", json.dumps(cr[0], ensure_ascii=False)[:600])
    # requirement 字段
    for k in ("requirement", "visual_requirement"):
        if k in sr[0]:
            print("requirement keys:", sorted((sr[0][k] or {}).keys()))
            print("requirement sample:", json.dumps(sr[0][k], ensure_ascii=False)[:800])
from collections import Counter
dec = Counter()
per_scene = {}
for s in sr:
    for c in (s.get("candidate_results") or []):
        dec[c.get("decision")] += 1
        per_scene.setdefault(s.get("scene_id"), Counter())[c.get("decision")] += 1
print("decision 分布:", dict(dec))
print("按景:", {k: dict(v) for k, v in list(per_scene.items())[:6]})

print()
print("=" * 78)
print("B. phase6b_m2_review_ledger_v9.jsonl（人工否决负例）")
print("=" * 78)
p = L / "phase6b_m2_review_ledger_v9.jsonl"
lines = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
print("entries:", len(lines))
print("keys:", sorted(lines[0].keys()) if lines else None)
for x in lines[:4]:
    print("  ", json.dumps({k: x.get(k) for k in
                            ("finding_id", "scene_id", "asset_id", "decision",
                             "decided_by", "reason", "note")}, ensure_ascii=False)[:300])

print()
print("=" * 78)
print("C. phase5d_mmt_truth.json（6 景 MATCH/MISMATCH）")
print("=" * 78)
mt = json.loads((L / "phase5d_mmt_truth.json").read_text(encoding="utf-8"))
print("top keys:", sorted(mt.keys()))
sc = mt.get("scenes") or []
print("scenes:", len(sc))
for s in sc:
    print("  ", json.dumps({k: s.get(k) for k in
                            ("scene_id", "verdict", "expected_domain", "reason")},
                           ensure_ascii=False)[:300])
    print("      narration:", str(s.get("narration_text"))[:120])
