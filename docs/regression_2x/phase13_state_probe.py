# -*- coding: utf-8 -*-
"""Phase 13 §1 核对：S05 REPLACE 提案哈希 + Phase 12 覆盖层一致性 + 权威时间线谱系。"""
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")

prop = json.loads((L / "visual_binding_proposals.json").read_text(encoding="utf-8"))
s05 = next(p for p in prop["proposals"] if p["scene_id"] == "S05")
print("== S05 REPLACE 提案（P7-6 登记）==")
print("  proposal_id:", s05["proposal_id"])
print("  deterministic_hash:", s05["deterministic_hash"])
print("  decision:", s05["decision"], "| license_decision:", s05["license_decision"],
      "| relevance:", s05.get("relevance_decision"), "| reuse:", s05.get("reuse_decision"))
print("  previous_asset_id:", s05.get("previous_asset_id"), "| candidate_id:", s05.get("candidate_id"))
print("  bindable:", [c.get("asset_id") for c in s05.get("bindable_candidates") or []])
print("  h5_provenance:", json.dumps((prop.get("policy") or {}).get("h5_provenance", {}).get("S05"),
                                  ensure_ascii=False)[:200])
print("  coverage:", json.dumps(s05.get("coverage"), ensure_ascii=False)[:150])
print("  artifact_hash:", prop["artifact_hash"])

ov = json.loads((L / "license_overlay_v1.json").read_text(encoding="utf-8"))
idx = {c["asset_id"]: c for c in json.loads((L / "asset_index.json").read_text(
    encoding="utf-8"))["candidates"]}
print("\n== 覆盖层中的 Russell 页候选 ==")
for e in ov["entries"]:
    c = idx[e["asset_id"]]
    if "Russell" in str(c.get("path")) or e["asset_id"] == "ast-92ca33138ffe64f4":
        print("  {} path={}".format(e["asset_id"], str(c.get("path"))[-58:]))
        print("     索引 license={!r} class={} -> join state={} class={}".format(
            c.get("license"), c.get("license_class"), e["state"], e["license_class"]))
        print("     attribution={!r}".format(str(e["attribution"])[:110]))
        print("     source_of_record={}".format(json.dumps(e["source_of_record"], ensure_ascii=False)[:110]))

print("\n== 权威时间线谱系 ==")
cov = json.loads((L / "visual_coverage_report.json").read_text(encoding="utf-8"))
sc = cov.get("scene_coverages") or []
print("  P7-6 覆盖报告场景数:", len(sc), "| schema:", cov.get("schema"),
      "| 来源:", json.dumps(cov.get("sources"), ensure_ascii=False)[:220])
h5 = L / "phase6g_exec_h5.json"
j = json.loads(h5.read_text(encoding="utf-8"))
print("  phase6g_exec_h5 keys:", sorted(j.keys())[:14])
tl = j.get("working_timeline") or j.get("timeline") or {}
segs = tl.get("segments") if isinstance(tl, dict) else None
print("  H5 时间线段数:", len(segs) if segs else "n/a",
      "| file:", str(j.get("film", {}).get("file") if isinstance(j.get("film"), dict) else "")[:70])
