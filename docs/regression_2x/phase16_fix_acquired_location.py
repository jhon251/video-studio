# -*- coding: utf-8 -*-
"""修正 P16-3 获取件位置：`media/external/` → `acquired_materials/`（项目根外挂目录）。

原因（如实登记）：`OPS.build()` 的 `DEFAULT_PROJECT_MEDIA` 指向
`projects/p_96efdc03e1aa/media`，而 `tests/asset_candidate_test.py::10` 断言该索引为
**8 个视觉候选（6 项目 + 2 H5）**——这是**冻结的 P7-2 索引状态**。
把新获取件留在 `media/` 会改变该冻结状态并使测试失败。

为**不改既有测试、不动冻结索引状态**：获取件迁至项目根 `acquired_materials/`，
并写独立登记台账（含 P16-3 全部记录与许可/署名 provenance）。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
PID = "p_96efdc03e1aa"
sys.stdout.reconfigure(encoding="utf-8")

proj = R / "projects" / PID
acq = json.loads((L / "phase16_acquisition_ledger.json").read_text(encoding="utf-8"))
dest_dir = proj / "acquired_materials"
dest_dir.mkdir(parents=True, exist_ok=True)

# 新获取件（P16-3）：按台账 downloaded_path 定位
NEW = ["301ff850be9c", "33b360a5363c", "5144139591a0", "a3f0e27204cd"]
moved = []
for x in acq.get("fetched") or []:
    dp = x.get("downloaded_path")
    if not dp:
        continue
    src = proj / "media" / dp
    if not src.is_file():
        continue
    sha = hashlib.sha256(src.read_bytes()).hexdigest()
    if sha[:12] not in NEW:
        continue
    dst = dest_dir / src.name
    shutil.move(str(src), str(dst))
    moved.append({
        "sha256": sha, "sha12": sha[:12], "filename": dst.name,
        "path": str(dst), "bytes": dst.stat().st_size,
        "scene_id": x.get("scene_id"), "source_id": x.get("source_id"),
        "name": x.get("name"), "source_url": x.get("source_url"),
        "license": x.get("license"), "license_class": x.get("license_class"),
        "license_cleared": x.get("license_cleared"), "attribution": x.get("attribution"),
    })
    print("迁移 {} {} -> {}".format(sha[:12], src.name, dst))

# 登记台账
reg = {
    "schema": "phase16-acquired-registry-v1",
    "stage": "Phase 16 P16-3 受治理获取件登记",
    "project_id": PID,
    "dir": "projects/{}/acquired_materials/".format(PID),
    "reason_not_in_media": ("把获取件留在 media/ 会改变**冻结的 P7-2 索引状态**"
                            "（asset_candidate_test::10 断言 8 个视觉候选）；"
                            "为不改测试、不动冻结状态，改放项目根 acquired_materials/。"),
    "registered": moved, "registered_count": len(moved),
    "provider": acq.get("provider"),
    "network_requests": acq.get("network_requests"),
    "request_ledger": acq.get("request_ledger"),
    "zero_inference": "许可/署名逐字沿用 provider 元数据与下载后校验结果",
}
rp = L / "phase16_acquired_registry.json"
rp.write_text(json.dumps(reg, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
print()
print("获取件登记台账 ->", rp.relative_to(R).as_posix(), "| 件数:", len(moved))

# media/ 现状
imgs = [f for f in (proj / "media").rglob("*") if f.is_file()
        and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]
print("media/ 图像文件数（应为 6）:", len(imgs))
for f in sorted(imgs):
    print("  ", f.relative_to(proj / "media").as_posix())
