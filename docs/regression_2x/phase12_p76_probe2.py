# -*- coding: utf-8 -*-
"""Phase 12 只读核对（三）：索引候选（资产宇宙）+ 五景 HITL 提案 + 覆盖明细。"""
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")

idx = json.loads((L / "asset_index.json").read_text(encoding="utf-8"))
cands = idx["candidates"]
print("== 索引候选（资产宇宙）:", len(cands), "==")
print(" 首条 keys:", sorted(cands[0].keys()))
for a in cands:
    print("  {:26s} lic={:14s} class={:16s} sha={} src={}".format(
        str(a.get("asset_id")), str(a.get("license"))[:14], str(a.get("license_class"))[:16],
        str(a.get("sha256"))[:10], str(a.get("source_url") or a.get("origin") or "")[:44]))
print(" counts:", json.dumps(idx.get("counts"), ensure_ascii=False)[:200])
print(" metadata_sources:", json.dumps(idx.get("metadata_sources"), ensure_ascii=False)[:200])
print(" external_cache:", json.dumps(idx.get("external_cache"), ensure_ascii=False)[:220])

prop = json.loads((L / "visual_binding_proposals.json").read_text(encoding="utf-8"))
print("\n== 五景 HITL 提案 ==")
for p in prop["proposals"]:
    if p.get("license_decision") not in ("NOT_APPLICABLE", None) or \
            p.get("decision") in ("HITL_REQUIRED", "UNSUPPORTED", "REPLACE"):
        print("  {} scene={} decision={} lic_dec={} reason={}".format(
            p.get("proposal_id"), p.get("scene_id"), p.get("decision"),
            p.get("license_decision"), str(p.get("decision_reason"))[:90]))
        for ev in (p.get("candidate_evaluations") or [])[:3]:
            print("       cand={} lic={} class={} bindable={}".format(
                ev.get("candidate_id"), str(ev.get("license"))[:16],
                ev.get("license_class"), ev.get("bindable")))
print(" coverage_counts:", json.dumps(prop.get("coverage_counts"), ensure_ascii=False))
print(" candidate_states:", json.dumps(prop.get("candidate_states"), ensure_ascii=False)[:220])

cov = json.loads((L / "visual_coverage_report.json").read_text(encoding="utf-8"))
print("\n== 覆盖明细 ==")
for s in cov["scene_coverages"]:
    if s.get("scene_id") in ("S01", "S05", "S13", "S14", "S15", "S16"):
        print("  {}: {} | keys={}".format(s.get("scene_id"),
                                          json.dumps({k: v for k, v in s.items()
                                                      if k not in ("answers",)},
                                                     ensure_ascii=False)[:200],
                                          sorted(s.keys())[:8]))
print(" hitl:", json.dumps(cov.get("hitl"), ensure_ascii=False)[:300])
print(" counts_by_action:", json.dumps(cov.get("counts_by_action"), ensure_ascii=False))
