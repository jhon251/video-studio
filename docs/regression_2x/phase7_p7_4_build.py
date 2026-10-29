# -*- coding: utf-8 -*-
"""P7-4 阶段脚本：构建并落盘 `visual_relevance.json`（**唯一写文件处**）。

用法: python docs/regression_2x/phase7_p7_4_build.py
产出: docs/regression_2x/logs/visual_relevance.json（确定性；同输入同字节）
"""
import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core import visual_relevance as VR                              # noqa: E402
from video_studio.ops import visual_relevance as OPS                              # noqa: E402

OUT = pathlib.Path(OPS.DEFAULT_OUT)
SNAP = {
    "final_master": R / "output/phase6g_exec_h5/20260929_151026/out/H5_rp-0ebebb71f99c.mp4",
    "dcv2_master": R / "output/phase6g_sandbox/20260929_102445/out/"
                   "dcv2_master_20260929_102445.mp4",
    "baseline_zip": R / "docs/regression_2x/baseline/6.x-final-baseline.zip",
    "ledger": R / "docs/regression_2x/logs/phase6g_exec_ledger.jsonl",
    "register": R / "docs/regression_2x/logs/phase6g_rebuild_proposal_register.jsonl",
    "material_plan": R / "docs/regression_2x/phase6e_materials/phase6e_material_plan.json",
    "p7_1_artifact": R / "docs/regression_2x/logs/visual_requirements.json",
    "p7_2_artifact": R / "docs/regression_2x/logs/asset_index.json",
    "p7_3_artifact": R / "docs/regression_2x/logs/asset_diversity.json",
    "direction_py": R / "src/video_studio/core/direction.py",
    "materials_py": R / "src/video_studio/core/materials.py",
    "execution_py": R / "src/video_studio/ops/execution.py",
    "content_identity_py": R / "src/video_studio/orchestration/content_identity.py",
    "crop_recheck_py": R / "src/video_studio/orchestration/crop_recheck.py",
}


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


before = {k: sha(v) for k, v in SNAP.items()}
a = OPS.build()
b = OPS.build()
if a["artifact_hash"] != b["artifact_hash"]:
    print("FAIL-CLOSED: 两次构建 artifact_hash 不一致", file=sys.stderr)
    sys.exit(2)
errs = VR.validate_artifact(a)
if errs:
    print("FAIL-CLOSED: artifact 校验失败 {}".format(errs[:5]), file=sys.stderr)
    sys.exit(2)
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(a, ensure_ascii=False, indent=1), encoding="utf-8")
after = {k: sha(v) for k, v in SNAP.items()}
ag = a["aggregate"]
summary = {
    "artifact": str(OUT.relative_to(R)), "file_sha256": sha(OUT), "bytes": OUT.stat().st_size,
    "artifact_hash": a["artifact_hash"],
    "scenes": ag["scene_count"], "candidates": ag["candidate_count"],
    "pairs": ag["pairs_evaluated"], "decision_counts": ag["decision_counts"],
    "scenes_with_relevant_candidate": ag["scenes_with_relevant_candidate"],
    "relevant_by_evidence_kind": ag["relevant_by_evidence_kind"],
    "current_asset_decisions": ag["current_asset_decisions"],
    "visual_judge_available": a["visual_judge_capability"]["available_for_p7_4"],
    "immutable_snapshot_identical": before == after,
    "immutable_changed": [k for k in before if before[k] != after[k]],
}
print(json.dumps(summary, ensure_ascii=False, indent=1))
sys.exit(0 if summary["immutable_snapshot_identical"] else 1)
