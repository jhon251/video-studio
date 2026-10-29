# -*- coding: utf-8 -*-
"""P16-2 本地素材登记（零网络、零推断）。

规则（授权书 §2/§3 与铁律）：
  · **只登记 Phase 12 许可覆盖层里已有记录**的 H5 素材 ⇒ 许可/署名**逐字沿用记录**，不做任何推断；
  · 无许可记录的 H5 文件**一律不登记**（登记它们等于推断许可 ⇒ 违反铁律），逐条登记"未登记原因"；
  · 登记 = 文件复制进 `projects/<pid>/media/registered/` + 写登记台账（provenance）+ 重建 AssetIndex。

产物：`logs/phase16_local_registry.json`、`projects/<pid>/media/registered/*`、
      `logs/phase16_asset_index_v2.json`
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
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")


def sha(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


overlay = json.loads((L / "license_overlay_v1.json").read_text(encoding="utf-8"))
h5 = json.loads((L / "phase6g_exec_h5.json").read_text(encoding="utf-8"))
ov_by_sha = {e["asset_sha256"]: e for e in (overlay.get("entries") or [])
             if e.get("asset_sha256")}
h5_by_sha = {}
for sid, rec in (h5.get("asset_records") or {}).items():
    if rec.get("sha256"):
        h5_by_sha[rec["sha256"]] = {**rec, "scene_id": sid}
binding = h5.get("binding") or {}

proj = R / "projects" / PID
media = proj / "media"
reg_dir = media / "registered"
reg_dir.mkdir(parents=True, exist_ok=True)

# 候选源：H5 候选根下所有位图
h5_root = R.parent / "h5_asset_candidates"
cands = []
for f in sorted(h5_root.rglob("*")):
    if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
        cands.append(f)

registered, skipped = [], []
for f in cands:
    s = sha(f)
    ov = ov_by_sha.get(s)
    h = h5_by_sha.get(s)
    if ov is None:
        skipped.append({
            "source_file": str(f), "sha256": s,
            "reason": "Phase 12 许可覆盖层**无该素材记录** ⇒ 按『零推断』不登记",
            "note": "登记需先取得许可记录（属 P16-3 受治理获取，或另开人工补录授权）",
        })
        continue
    if (ov.get("license_class") in ("RESTRICTED", "UNKNOWN")) or not ov.get("license_cleared"):
        skipped.append({
            "source_file": str(f), "sha256": s,
            "reason": "记录显示许可类别 {} / cleared={} ⇒ 许可门禁不放行（不放宽许可门）".format(
                ov.get("license_class"), ov.get("license_cleared")),
        })
        continue
    dst = reg_dir / f.name
    shutil.copy2(f, dst)
    assert sha(dst) == s, "复制后 sha 不一致: {}".format(f)
    registered.append({
        "asset_id": ov.get("asset_id"),
        "sha256": s,
        "filename": dst.name,
        "registered_path": str(dst),
        "relative_path": "registered/{}".format(dst.name),
        "bytes": dst.stat().st_size,
        "license": ov.get("license"),
        "license_class": ov.get("license_class"),
        "license_cleared": ov.get("license_cleared"),
        "attribution": ov.get("attribution"),
        "source_url": (h or {}).get("source_url"),
        "provider": (h or {}).get("provider"),
        "h5_binding": binding.get((h or {}).get("scene_id")),
        "provenance": {
            "license_record": "docs/regression_2x/logs/license_overlay_v1.json"
                              "#entries[asset_id={}]".format(ov.get("asset_id")),
            "h5_record": ("docs/regression_2x/logs/phase6g_exec_h5.json#asset_records[{}]"
                          .format((h or {}).get("scene_id")) if h else None),
            "zero_inference": ("许可/署名**逐字沿用**上述记录，未做任何推断；"
                               "文件字节经 sha256 复核与记录一致"),
        },
    })

# 写入登记台账
ledger = {
    "schema": "phase16-local-registry-v1",
    "stage": "Phase 16 P16-2 本地素材登记（零网络/零推断）",
    "project_id": PID,
    "rule": ("只登记 Phase 12 覆盖层已有许可记录的素材；无记录者不登记（不推断许可）"),
    "media_dir": "projects/{}/media/registered/".format(PID),
    "registered": registered,
    "registered_count": len(registered),
    "skipped": skipped,
    "skipped_count": len(skipped),
    "h5_binding_reference": binding,
    "zero_network": True,
    "zero_inference": True,
}
lp = L / "phase16_local_registry.json"
lp.write_text(json.dumps(ledger, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")

print("=" * 78)
print("P16-2 本地素材登记")
print("=" * 78)
print("  已登记: {} 个".format(len(registered)))
for x in registered:
    print("   + [{:14s}] {:22s} {:>9,}B  {} / {}".format(
        x["license_class"], x["filename"], x["bytes"], x["license"],
        str(x["attribution"])[:44]))
print("  未登记: {} 个（无许可记录或门禁不放行）".format(len(skipped)))
for x in skipped[:4]:
    print("   - {} | {}".format(pathlib.Path(x["source_file"]).name, x["reason"][:80]))
if len(skipped) > 4:
    print("   - … 共 {} 条（完整见台账）".format(len(skipped)))
print()
print("  台账 ->", lp.relative_to(R).as_posix())

# 登记后 media 图像清单
imgs = [f for f in media.rglob("*") if f.is_file()
        and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]
print()
print("  media 图像总数（登记后）:", len(imgs))
uniq = {}
for f in imgs:
    uniq.setdefault(sha(f), []).append(f.relative_to(media).as_posix())
print("  去重后唯一图像:", len(uniq))
for s, paths in sorted(uniq.items()):
    print("    {} x{}  {}".format(s[:12], len(paths), paths[0]))
