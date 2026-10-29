# -*- coding: utf-8 -*-
"""P7-1 阶段脚本：构建并落盘 `visual_requirements.json`（**唯一写文件处**）。

按项目既有 `ops/` 契约（maintenance guard M8d/M8e）：`ops/` 模块严格只读，
产物落盘由本阶段脚本负责（与 6-G 各阶段脚本同构）。

用法: python docs/regression_2x/phase7_p7_1_build.py
产出: docs/regression_2x/logs/visual_requirements.json（确定性；同输入同字节）
"""
import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.ops import visual_requirement as OPS                          # noqa: E402
from video_studio.tools import visual_requirement_builder as VB                 # noqa: E402

OUT = pathlib.Path(OPS.DEFAULT_OUT)
SNAP = {
    "final_master": R / "output/phase6g_exec_h5/20260929_151026/out/H5_rp-0ebebb71f99c.mp4",
    "ledger": R / "docs/regression_2x/logs/phase6g_exec_ledger.jsonl",
    "register": R / "docs/regression_2x/logs/phase6g_rebuild_proposal_register.jsonl",
    "baseline_zip": R / "docs/regression_2x/baseline/6.x-final-baseline.zip",
    "material_plan": R / "docs/regression_2x/phase6e_materials/phase6e_material_plan.json",
}


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


before = {k: sha(v) for k, v in SNAP.items()}

art_a = OPS.build()                                  # 第一次构建（内存）
art_b = OPS.build()                                  # 第二次构建（确定性比对）
if art_a["artifact_hash"] != art_b["artifact_hash"]:
    print("FAIL-CLOSED: 两次构建 artifact_hash 不一致", file=sys.stderr)
    sys.exit(2)
errs = VB.validate_artifact(art_a)
if errs:
    print("FAIL-CLOSED: artifact 校验失败 {}".format(errs[:5]), file=sys.stderr)
    sys.exit(2)

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(art_a, ensure_ascii=False, indent=1), encoding="utf-8")

after = {k: sha(v) for k, v in SNAP.items()}
rep = {
    "artifact": str(OUT.relative_to(R)),
    "file_sha256": sha(OUT), "bytes": OUT.stat().st_size,
    "artifact_hash": art_a["artifact_hash"],
    "counts": art_a["counts"],
    "determinism": {"two_builds_same_hash": True,
                    "verified_by": "ops verify（独立进程）已在验收脚本中复核"},
    "immutable_snapshot_identical": before == after,
    "immutable_changed": [k for k in before if before[k] != after[k]],
}
print(json.dumps({k: rep[k] for k in ("artifact", "file_sha256", "artifact_hash", "counts",
                                     "immutable_snapshot_identical", "immutable_changed")},
                 ensure_ascii=False, indent=1))
sys.exit(0 if rep["immutable_snapshot_identical"] else 1)
