# -*- coding: utf-8 -*-
"""修正 P16-2 登记位置：把登记件移出 `media/`（`media/registered/` → `registered_materials/`）。

原因（如实登记）：`media/` 会被 AssetIndex 扫描；把新文件放进 `media/` 改变了
**冻结的 P7-2 索引状态**，使 `tests/asset_candidate_test.py::10`（断言"8 个视觉候选 =
6 项目 + 2 H5"）失败。为**不修改既有测试、不改变冻结索引状态**，登记件改放项目根下
`registered_materials/`（仍属"本地登记"，仍可由 Phase 16 候选池以绝对路径引用）。

登记台账同步更新（append 说明，不抹除历史记录）。
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
src_dir = proj / "media" / "registered"
dst_dir = proj / "registered_materials"
dst_dir.mkdir(parents=True, exist_ok=True)

moved = []
if src_dir.is_dir():
    for f in sorted(src_dir.iterdir()):
        if not f.is_file():
            continue
        dst = dst_dir / f.name
        shutil.move(str(f), str(dst))
        moved.append({"filename": dst.name, "sha256": hashlib.sha256(
            dst.read_bytes()).hexdigest(), "bytes": dst.stat().st_size,
            "new_path": str(dst)})
    # 移除空目录
    try:
        src_dir.rmdir()
    except OSError:
        pass

print("已迁移登记件:", len(moved))
for m in moved:
    print("  {} {} -> {}".format(m["sha256"][:12], m["filename"], m["new_path"]))

# 更新登记台账（保留历史，追加变更说明）
lp = L / "phase16_local_registry.json"
led = json.loads(lp.read_text(encoding="utf-8"))
for r in led.get("registered") or []:
    old = pathlib.Path(r["registered_path"])
    new = dst_dir / r["filename"]
    if new.is_file():
        r["registered_path"] = str(new)
        r["relative_path"] = "registered_materials/{}".format(r["filename"])
led["media_dir"] = "projects/{}/registered_materials/".format(PID)
led.setdefault("amendments", []).append({
    "amendment": "登记位置由 media/registered/ 迁至 registered_materials/",
    "reason": ("media/ 会被 AssetIndex 扫描；放入新文件会改变**冻结的 P7-2 索引状态**，"
               "致 tests/asset_candidate_test.py::10（断言 8 个视觉候选 = 6 项目 + 2 H5）失败。"
               "为不改既有测试、不动冻结状态，登记件改放项目根 registered_materials/。"),
    "moved": moved,
    "note": "登记语义不变：仍为本地登记，许可/署名逐字沿用 Phase 12 覆盖层记录，零推断",
})
lp.write_text(json.dumps(led, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
print("台账已更新 ->", lp.relative_to(R).as_posix())

# 校验 media/ 是否恢复为原来的 6 个项目图像
imgs = [f for f in (proj / "media").rglob("*") if f.is_file()
        and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]
print()
print("media/ 图像文件数（应为 6）:", len(imgs))
for f in sorted(imgs):
    print("  ", f.relative_to(proj / "media").as_posix())
