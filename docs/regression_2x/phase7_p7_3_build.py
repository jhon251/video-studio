# -*- coding: utf-8 -*-
"""P7-3 阶段脚本：构建并落盘 `asset_diversity.json`（**唯一写文件处**）。

用法: python docs/regression_2x/phase7_p7_3_build.py
产出: docs/regression_2x/logs/asset_diversity.json（确定性；同输入同字节）
"""
import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core import asset_diversity as AD                              # noqa: E402
from video_studio.ops import asset_diversity as OPS                              # noqa: E402

OUT = pathlib.Path(OPS.DEFAULT_OUT)
SNAP = {
    "final_master": R / "output/phase6g_exec_h5/20260929_151026/out/H5_rp-0ebebb71f99c.mp4",
    "ledger": R / "docs/regression_2x/logs/phase6g_exec_ledger.jsonl",
    "register": R / "docs/regression_2x/logs/phase6g_rebuild_proposal_register.jsonl",
    "baseline_zip": R / "docs/regression_2x/baseline/6.x-final-baseline.zip",
    "material_plan": R / "docs/regression_2x/phase6e_materials/phase6e_material_plan.json",
    "p7_1_artifact": R / "docs/regression_2x/logs/visual_requirements.json",
    "p7_2_artifact": R / "docs/regression_2x/logs/asset_index.json",
    "direction_py": R / "src/video_studio/core/direction.py",
    "materials_py": R / "src/video_studio/core/materials.py",
}


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


before = {k: sha(v) for k, v in SNAP.items()}
a = OPS.build()
b = OPS.build()
if a["artifact_hash"] != b["artifact_hash"]:
    print("FAIL-CLOSED: 两次构建 artifact_hash 不一致", file=sys.stderr)
    sys.exit(2)
errs = AD.validate_report(a)
if errs:
    print("FAIL-CLOSED: 报告校验失败 {}".format(errs[:5]), file=sys.stderr)
    sys.exit(2)
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(a, ensure_ascii=False, indent=1), encoding="utf-8")
after = {k: sha(v) for k, v in SNAP.items()}
primary = next(s for s in a["scopes"] if s["scope"] == a["primary_scope"])
summary = {
    "artifact": str(OUT.relative_to(R)), "file_sha256": sha(OUT), "bytes": OUT.stat().st_size,
    "artifact_hash": a["artifact_hash"], "primary_scope": a["primary_scope"],
    "scopes": {s["scope"]: {"scene_count": s["B_scene_level"]["scene_count"],
                            "unique_assets": s["A_asset_level"]["unique_assets"],
                            "unique_perceptual_families":
                                s["A_asset_level"]["unique_perceptual_families"],
                            "unique_source_families":
                                s["A_asset_level"]["unique_source_families"],
                            "max_asset_reuse": s["A_asset_level"]["max_asset_reuse"],
                            "scene_asset_reuse_rate":
                                s["B_scene_level"]["scene_asset_reuse_rate"],
                            "asset_hhi": s["C_concentration"]["asset_hhi"],
                            "source_family_hhi": s["C_concentration"]["source_family_hhi"]}
               for s in a["scopes"]},
    "semantic_coverage": {"visual_goal_coverage":
                              primary["E_semantic_coverage"]["visual_goal_coverage"],
                          "query_coverage": primary["E_semantic_coverage"]["query_coverage"],
                          "semantic_core_coverage":
                              primary["E_semantic_coverage"]["semantic_core_coverage"]},
    "immutable_snapshot_identical": before == after,
    "immutable_changed": [k for k in before if before[k] != after[k]],
}
print(json.dumps(summary, ensure_ascii=False, indent=1))
sys.exit(0 if summary["immutable_snapshot_identical"] else 1)
