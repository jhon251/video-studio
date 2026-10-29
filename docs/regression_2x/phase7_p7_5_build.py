# -*- coding: utf-8 -*-
"""P7-5 阶段脚本：构建并落盘 `visual_acquisition.json`（**唯一写文件处**）。

用法: python docs/regression_2x/phase7_p7_5_build.py
产出: docs/regression_2x/logs/visual_acquisition.json（确定性；DRY_RUN，零下载）
"""
import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core import visual_acquisition as VA                              # noqa: E402
from video_studio.ops import visual_acquisition as OPS                              # noqa: E402

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
    "p7_4_artifact": R / "docs/regression_2x/logs/visual_relevance.json",
    "execution_py": R / "src/video_studio/ops/execution.py",
    "materials_py": R / "src/video_studio/core/materials.py",
    "direction_py": R / "src/video_studio/core/direction.py",
    "content_identity_py": R / "src/video_studio/orchestration/content_identity.py",
    "crop_recheck_py": R / "src/video_studio/orchestration/crop_recheck.py",
}


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


before = {k: sha(v) for k, v in SNAP.items()}
a = OPS.build(mode=VA.DRY_RUN)                       # DRY_RUN：零下载
b = OPS.build(mode=VA.DRY_RUN)
if a["artifact_hash"] != b["artifact_hash"]:
    print("FAIL-CLOSED: 两次 DRY_RUN artifact_hash 不一致", file=sys.stderr)
    sys.exit(2)
errs = VA.validate_plan(a)
if errs:
    print("FAIL-CLOSED: plan 校验失败 {}".format(errs[:5]), file=sys.stderr)
    sys.exit(2)
assert not any(r.get("status") == VA.BOUND for r in a["requests"]), "BOUND 禁止"
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(a, ensure_ascii=False, indent=1), encoding="utf-8")
after = {k: sha(v) for k, v in SNAP.items()}
summary = {
    "artifact": str(OUT.relative_to(R)), "file_sha256": sha(OUT), "bytes": OUT.stat().st_size,
    "artifact_hash": a["artifact_hash"], "mode": a["mode"], "dry_run": a["dry_run"],
    "counts": a["counts"], "budget_ok": a["budget_check"]["ok"],
    "budget_usage": a["budget_check"]["usage"],
    "requests": [{"request_id": r["request_id"], "scene_id": r["scene_id"],
                  "reason": r["reason"]["code"], "fetchable": r["fetchable"]}
                 for r in a["requests"]],
    "provider": a["provider_policy"]["provider"],
    "live_fetch_default": a["provider_policy"]["live_fetch_default"],
    "immutable_snapshot_identical": before == after,
    "immutable_changed": [k for k in before if before[k] != after[k]],
}
print(json.dumps(summary, ensure_ascii=False, indent=1))
sys.exit(0 if summary["immutable_snapshot_identical"] else 1)
