# -*- coding: utf-8 -*-
"""P7-2 阶段脚本：构建并落盘 `asset_index.json`（**唯一写文件处**）。

按项目既有 `ops/` 契约（maintenance guard M8d/M8e）：ops 模块严格只读，产物落盘由本阶段脚本负责。

用法: python docs/regression_2x/phase7_p7_2_build.py
产出: docs/regression_2x/logs/asset_index.json（确定性；同输入同字节）
"""
import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.ops import asset_index as OPS                                  # noqa: E402
from video_studio.tools import asset_index_builder as AIB                        # noqa: E402

OUT = pathlib.Path(OPS.DEFAULT_OUT)
SNAP = {
    "final_master": R / "output/phase6g_exec_h5/20260929_151026/out/H5_rp-0ebebb71f99c.mp4",
    "ledger": R / "docs/regression_2x/logs/phase6g_exec_ledger.jsonl",
    "register": R / "docs/regression_2x/logs/phase6g_rebuild_proposal_register.jsonl",
    "baseline_zip": R / "docs/regression_2x/baseline/6.x-final-baseline.zip",
    "material_plan": R / "docs/regression_2x/phase6e_materials/phase6e_material_plan.json",
    "direction_py": R / "src/video_studio/core/direction.py",
    "materials_py": R / "src/video_studio/core/materials.py",
    "content_identity_py": R / "src/video_studio/orchestration/content_identity.py",
    "crop_recheck_py": R / "src/video_studio/orchestration/crop_recheck.py",
    "p7_1_artifact": R / "docs/regression_2x/logs/visual_requirements.json",
}


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


before = {k: sha(v) for k, v in SNAP.items()}
art_a = OPS.build()
art_b = OPS.build()
if art_a["artifact_hash"] != art_b["artifact_hash"]:
    print("FAIL-CLOSED: 两次构建 artifact_hash 不一致", file=sys.stderr)
    sys.exit(2)
errs = AIB.validate_index(art_a)
if errs:
    print("FAIL-CLOSED: AssetIndex 校验失败 {}".format(errs[:5]), file=sys.stderr)
    sys.exit(2)
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(art_a, ensure_ascii=False, indent=1), encoding="utf-8")
after = {k: sha(v) for k, v in SNAP.items()}
rel = art_a["relationships"]
summary = {
    "artifact": str(OUT.relative_to(R)), "file_sha256": sha(OUT), "bytes": OUT.stat().st_size,
    "artifact_hash": art_a["artifact_hash"], "counts": art_a["counts"],
    "relationships": {"exact_duplicate_groups": len(rel["exact_duplicate_groups"]),
                      "perceptual_families": len(rel["perceptual_families"]),
                      "families_with_multiple_sha": sum(
                          1 for f in rel["perceptual_families"] if f["distinct_sha256"] > 1),
                      "transform_relations": len(rel["transform_relations"]),
                      "suspect_links": len(rel["suspect_links"]),
                      "independent_asset_ids": len(rel["independent_asset_ids"]),
                      "mirror_invariance": rel["mirror_invariance"]["status"]},
    "external_cache": art_a["external_cache"],
    "immutable_snapshot_identical": before == after,
    "immutable_changed": [k for k in before if before[k] != after[k]],
}
print(json.dumps(summary, ensure_ascii=False, indent=1))
sys.exit(0 if summary["immutable_snapshot_identical"] else 1)
