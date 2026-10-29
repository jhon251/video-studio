# -*- coding: utf-8 -*-
"""Phase 8 只读核验：历史基线与不可变快照（含 Phase 7 产物）零改动 + 本阶段产物 sha256 台账。"""
import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")

IMMUTABLE = {
    "final_master_6G": R / "output/phase6g_exec_h5/20260929_151026/out/H5_rp-0ebebb71f99c.mp4",
    "dcv2_master": R / "output/phase6g_sandbox/20260929_102445/out/"
                   "dcv2_master_20260929_102445.mp4",
    "baseline_zip": R / "docs/regression_2x/baseline/6.x-final-baseline.zip",
    "baseline_manifest": R / "docs/regression_2x/baseline/"
                         "baseline_manifest_6.x-final-baseline.json",
    "execution_ledger": L / "phase6g_exec_ledger.jsonl",
    "proposal_register": L / "phase6g_rebuild_proposal_register.jsonl",
    "frozen_material_plan": R / "docs/regression_2x/phase6e_materials/phase6e_material_plan.json",
    "p7_1": L / "visual_requirements.json",
    "p7_2": L / "asset_index.json",
    "p7_3": L / "asset_diversity.json",
    "p7_4": L / "visual_relevance.json",
    "p7_5": L / "visual_acquisition.json",
    "p7_6_proposals": L / "visual_binding_proposals.json",
    "p7_6_coverage": L / "visual_coverage_report.json",
}
EXPECT = {  # 关键项：与历史登记值一致（其余记录当前值供台账）
    "final_master_6G": "3b61dafda11c1b9d22381833a00645670ec8b4f25b8fccca813bb7ac63cee0be",
    "baseline_zip": "bffe9b0d4024626d166683f7c582a767711cec168193d20ab3cb5a4df4ce29e1",
}
PRODUCED = {
    "v3_guide": R / "config/script_style_guide.md",
    "v2_snapshot": R / "docs/regression_2x/phase8_style_v2_snapshot.md",
    "script_agent": R / "src/video_studio/agents/script/agent.py",
    "structure_agent": R / "src/video_studio/agents/structure/agent.py",
    "v3_test": R / "tests/creator_style_v3_test.py",
    "strip_test": R / "tests/strip_v2_test.py",
    "pipeline_mock": R / "tests/pipeline_mock.py",
    "ab_v2": L / "phase8_ab_v2.json",
    "ab_v3": L / "phase8_ab_v3.json",
    "ab_crosscheck": L / "phase8_ab_crosscheck.json",
    "upgrade_doc": R / "docs/CREATOR_STYLE_V3_UPGRADE.md",
    "phase8_report": R / "docs/regression_2x/PHASE8_REPORT.md",
    "status_md": R / "STATUS.md",
    "changelog_md": R / "CHANGELOG.md",
}


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


report = {"schema": "phase8-immutable-check-v1", "immutable": {}, "produced": {},
          "immutable_match_expect": {}, "verdict": ""}
for k, p in IMMUTABLE.items():
    if not p.is_file():
        report["immutable"][k] = "MISSING"
        continue
    h = sha(p)
    report["immutable"][k] = h
    if k in EXPECT:
        report["immutable_match_expect"][k] = (h == EXPECT[k])
for k, p in PRODUCED.items():
    report["produced"][k] = sha(p) if p.is_file() else "MISSING"
ok = all(report["immutable_match_expect"].values()) if report["immutable_match_expect"] else False
report["verdict"] = "IMMUTABLE_OK" if ok else "IMMUTABLE_MISMATCH"
out = L / "phase8_immutable_check.json"
out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
for k, v in report["immutable"].items():
    flag = ""
    if k in EXPECT:
        flag = "  <= 期望一致" if v == EXPECT[k] else "  <= **与期望不一致**"
    print("  {:24s} {}{}".format(k, str(v)[:16] + "…", flag))
print("verdict:", report["verdict"], "| 产物台账 ->", out.relative_to(R))
sys.exit(0 if ok else 1)
