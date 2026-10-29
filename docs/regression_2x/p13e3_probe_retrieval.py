# -*- coding: utf-8 -*-
"""检查候选 retrieval 载荷（哪个含 S05/S11 绑定、候选路径形态、material_mode）。"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
P = R / "projects" / "p_96efdc03e1aa"
sys.stdout.reconfigure(encoding="utf-8")

ids = ["a_a32ee7dc5760", "a_71f77918bc8a", "a_a93b3fef723a", "a_609ea7b3c895",
       "a_3d1181dcdaad", "a_0e584f6b4098", "a_64423d97f9bf", "a_8ff5eb3d88c0"]
for aid in ids:
    p = P / "artifacts" / (aid + ".json")
    if not p.is_file():
        print(aid, "MISSING")
        continue
    j = json.loads(p.read_text(encoding="utf-8"))
    cands = j.get("candidates") or []
    print("=" * 70)
    print(aid, "| keys:", sorted(j.keys()))
    print("  material_mode:", j.get("material_mode"),
          "| candidates_total:", j.get("candidates_total"),
          "| material_provided:", j.get("material_provided"),
          "| external_requested:", j.get("external_requested"))
    print("  candidates:", len(cands))
    for c in cands[:4]:
        print("    -", json.dumps({k: c.get(k) for k in
                                   ("name", "path", "provider", "match_score", "asset_id",
                                    "license", "license_class", "media_type")},
                                  ensure_ascii=False))
    # S05/S11 绑定线索
    txt = json.dumps(j, ensure_ascii=False)
    for probe in ("65377b888b778226", "1e9d2ab4e64ef982", "Russell", "S05", "S11", "binding"):
        if probe in txt:
            print("   contains:", probe)

print()
print("=== 既有 media/ 目录 ===")
md = P / "media"
for f in sorted(md.rglob("*")):
    if f.is_file():
        print("   ", f.relative_to(md).as_posix(), f.stat().st_size)
