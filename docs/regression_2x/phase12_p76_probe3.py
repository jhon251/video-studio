# -*- coding: utf-8 -*-
"""Phase 12 只读核对（四）：S13–S16 提案、candidate_evaluations 结构、索引 attribution 字段值。"""
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")
idx = json.loads((L / "asset_index.json").read_text(encoding="utf-8"))
print("== 索引 8 资产的 license/attribution/provenance/license_gate_applies ==")
for a in idx["candidates"]:
    print("  {}".format(a["asset_id"]))
    print("     licence={!r} class={} gate={} restricted={}".format(
        a.get("license"), a.get("license_class"), a.get("license_gate_applies"),
        a.get("license_restricted")))
    print("     attribution={!r}".format(a.get("attribution")))
    print("     provenance={} role={} provider={} source_id={}".format(
        json.dumps(a.get("provenance"), ensure_ascii=False)[:110], a.get("role_in_master"),
        a.get("provider"), a.get("source_id")))
prop = json.loads((L / "visual_binding_proposals.json").read_text(encoding="utf-8"))
print("\n== 全部 21 提案的 scene/decision/license_decision ==")
for p in prop["proposals"]:
    print("  {:22s} {} {:<14s} lic={:<14s} bindable={} acq={}".format(
        p.get("proposal_id"), p.get("scene_id"), str(p.get("decision")),
        str(p.get("license_decision")), len(p.get("bindable_candidates") or []),
        p.get("acquisition_required")))
print("\n== HITL 提案的评估结构（S01）==")
p01 = next(p for p in prop["proposals"] if p.get("scene_id") == "S01")
ev = (p01.get("candidate_evaluations") or [])
print(" 评估数:", len(ev), "| 首条 keys:", sorted(ev[0].keys()) if ev else None)
for e in ev[:6]:
    print("  ", json.dumps(e, ensure_ascii=False)[:220])
print("\n bindable_candidates:", json.dumps(p01.get("bindable_candidates"), ensure_ascii=False)[:160])
print(" integrity_decision:", p01.get("integrity_decision"), "| relevance:", p01.get("relevance_decision"))
print(" proposal keys:", sorted(p01.keys()))
