# -*- coding: utf-8 -*-
"""P16-2 前置：Phase 12 许可覆盖层逐条 + H5 候选素材可登记性（只读）。"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")

ov = json.loads((L / "license_overlay_v1.json").read_text(encoding="utf-8"))
print("=" * 78)
print("Phase 12 许可覆盖层 entries（逐条）")
print("=" * 78)
print("counts:", json.dumps(ov.get("counts"), ensure_ascii=False))
print("allowed classes:", json.dumps(ov.get("license_classes_allowed"), ensure_ascii=False))
for e in ov.get("entries") or []:
    print("-" * 74)
    print("  asset_id      :", e.get("asset_id"))
    print("  asset_sha256  :", str(e.get("asset_sha256"))[:24], "…")
    print("  license       :", e.get("license"), "| class:", e.get("license_class"),
          "| cleared:", e.get("license_cleared"), "| blocking:", e.get("license_blocking"))
    print("  attribution   :", str(e.get("attribution"))[:120])
    print("  conflict      :", e.get("conflict"))
    for k in ("source_url", "provider", "usage_restrictions", "provenance", "note"):
        if e.get(k):
            print("  {:14s}: {}".format(k, str(e[k])[:140]))

print()
print("=" * 78)
print("phase12_coverage_after.json")
print("=" * 78)
cov = json.loads((L / "phase12_coverage_after.json").read_text(encoding="utf-8"))
for k, v in cov.items():
    print("  {:28s} {}".format(k, json.dumps(v, ensure_ascii=False)[:300]))

print()
print("=" * 78)
print("H5 候选素材：文件 + sha + 是否有许可记录")
print("=" * 78)
h5 = R.parent / "h5_asset_candidates"
import hashlib                                                            # noqa: E402
known = {}
for e in ov.get("entries") or []:
    if e.get("asset_sha256"):
        known[e["asset_sha256"]] = e
for f in sorted(h5.rglob("*")):
    if not f.is_file() or f.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
        continue
    sha = hashlib.sha256(f.read_bytes()).hexdigest()
    e = known.get(sha)
    print("  {:62s} {:>9,}B sha={}".format(
        f.relative_to(h5).as_posix(), f.stat().st_size, sha[:12]))
    print("       许可记录: {}".format(
        "有 -> {} / {} / {}".format(e.get("license"), e.get("license_class"),
                                    e.get("attribution")) if e else "**无**"))
