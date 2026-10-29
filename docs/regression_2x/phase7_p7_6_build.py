# -*- coding: utf-8 -*-
"""P7-6 阶段脚本：落盘 `visual_binding_proposals.json` + `visual_coverage_report.json`
（**唯一写文件处**；只产出提案，**零执行**）。

用法: python docs/regression_2x/phase7_p7_6_build.py
"""
import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core import visual_binding as VB                              # noqa: E402
from video_studio.ops import visual_binding as OPS                             # noqa: E402

P_OUT = pathlib.Path(OPS.DEFAULT_OUT)
C_OUT = pathlib.Path(OPS.DEFAULT_COVERAGE_OUT)
SNAP = {
    "final_master": R / "output/phase6g_exec_h5/20260929_151026/out/H5_rp-0ebebb71f99c.mp4",
    "dcv2_master": R / "output/phase6g_sandbox/20260929_102445/out/"
                   "dcv2_master_20260929_102445.mp4",
    "baseline_zip": R / "docs/regression_2x/baseline/6.x-final-baseline.zip",
    "ledger": R / "docs/regression_2x/logs/phase6g_exec_ledger.jsonl",
    "register": R / "docs/regression_2x/logs/phase6g_rebuild_proposal_register.jsonl",
    "material_plan": R / "docs/regression_2x/phase6e_materials/phase6e_material_plan.json",
    "p7_1": R / "docs/regression_2x/logs/visual_requirements.json",
    "p7_2": R / "docs/regression_2x/logs/asset_index.json",
    "p7_3": R / "docs/regression_2x/logs/asset_diversity.json",
    "p7_4": R / "docs/regression_2x/logs/visual_relevance.json",
    "p7_5": R / "docs/regression_2x/logs/visual_acquisition.json",
    "execution_py": R / "src/video_studio/ops/execution.py",
    "materials_py": R / "src/video_studio/core/materials.py",
    "direction_py": R / "src/video_studio/core/direction.py",
    "content_identity_py": R / "src/video_studio/orchestration/content_identity.py",
    "crop_recheck_py": R / "src/video_studio/orchestration/crop_recheck.py",
}


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


before = {k: sha(v) for k, v in SNAP.items()}
a = OPS.build()
b = OPS.build()
if a["proposals"]["artifact_hash"] != b["proposals"]["artifact_hash"] or \
        a["coverage"]["artifact_hash"] != b["coverage"]["artifact_hash"]:
    print("FAIL-CLOSED: 两次 simulation  artifact_hash 不一致", file=sys.stderr)
    sys.exit(2)
assert all(not p["execution"]["executed"] for p in a["proposals"]["proposals"]), "禁止执行"
assert a["coverage"]["working_timeline"]["authoritative"] is False, "working timeline 必须非权威"
P_OUT.write_text(json.dumps(a["proposals"], ensure_ascii=False, indent=1), encoding="utf-8")
C_OUT.write_text(json.dumps(a["coverage"], ensure_ascii=False, indent=1), encoding="utf-8")
after = {k: sha(v) for k, v in SNAP.items()}
s05 = next(p for p in a["proposals"]["proposals"] if p["scene_id"] == "S05")
summary = {
    "proposals_artifact": str(P_OUT.relative_to(R)), "proposals_file_sha256": sha(P_OUT),
    "proposals_artifact_hash": a["proposals"]["artifact_hash"],
    "coverage_artifact": str(C_OUT.relative_to(R)), "coverage_file_sha256": sha(C_OUT),
    "coverage_artifact_hash": a["coverage"]["artifact_hash"],
    "actions": a["proposals"]["counts"], "coverage": a["coverage"]["counts"],
    "s05": {"previous_asset_id": s05["previous_asset_id"], "candidate_id": s05["candidate_id"],
            "decision": s05["decision"], "coverage": s05["coverage"]},
    "working_timeline": {"changed_scenes": [r["scene_id"] for r in
                                            a["coverage"]["working_timeline"]["rows"]
                                            if r["changed"]],
                         "authoritative": a["coverage"]["working_timeline"]["authoritative"]},
    "immutable_snapshot_identical": before == after,
    "immutable_changed": [k for k in before if before[k] != after[k]],
}
print(json.dumps(summary, ensure_ascii=False, indent=1))
sys.exit(0 if summary["immutable_snapshot_identical"] else 1)
