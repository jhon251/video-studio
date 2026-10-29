# -*- coding: utf-8 -*-
"""Phase 12 只读提取：前后覆盖计数、provenance 样例、未匹配记录（供报告）。"""
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")
c = json.loads((L / "phase12_coverage_after.json").read_text(encoding="utf-8"))
print("臂 A 兼容:", json.dumps(c["arm_a_no_overlay"]["backward_compatible"], ensure_ascii=False))
print("臂 A 计数:", json.dumps(c["arm_a_counts"], ensure_ascii=False))
print("臂 B 计数:", json.dumps(c["arm_b_with_overlay"]["counts"], ensure_ascii=False))
print("臂 B 哈希:", c["arm_b_with_overlay"]["proposals_artifact_hash"][:16])
print("解锁:", c["scenes_unlocked"], "| 仍 HITL:", c["scenes_still_hitl"], "| S05:", c["s05_replace_kept_as_proposal"])
s01 = next(x for x in c["five_scenes"] if x["scene_id"] == "S01")
print("S01 provenance:", json.dumps(s01["license_provenance"], ensure_ascii=False)[:420])
inv = json.loads((L / "phase12_license_sources.json").read_text(encoding="utf-8"))
print("三态:", inv["counts"], "| 记录总数:", inv["records_total"], "| 未匹配:", inv["unmatched_records"])
for a in inv["assets"]:
    print("  {:24s} {:12s} state={:10s} class={:16s} changed={}".format(
        a["asset_id"], str(a["index_license"])[:12], a["state"], a["license_class"],
        a["changes_index_license"]))
ov = json.loads((L / "license_overlay_v1.json").read_text(encoding="utf-8"))
print("覆盖层 hash:", ov["artifact_hash"], "| 未匹配记录:", len(ov["unmatched_records"]))
for u in ov["unmatched_records"][:4]:
    print("  未匹配:", u["source_type"], u["locator"][:40], "| license=", u["license_text"],
          "| scene=", u["scene_id"])
