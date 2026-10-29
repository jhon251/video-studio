# -*- coding: utf-8 -*-
"""P14-2 需求与素材索引原文件勘查（只读）：visual_requirements.json / asset_index.json。"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")

print("=" * 78)
print("visual_requirements.json")
print("=" * 78)
vrq = json.loads((L / "visual_requirements.json").read_text(encoding="utf-8"))
print("top keys:", sorted(vrq.keys()))
reqs = vrq.get("requirements") or vrq.get("scene_requirements") or []
if isinstance(reqs, dict):
    print("requirements is dict, len:", len(reqs))
    k0 = next(iter(reqs))
    print("req[{}] =".format(k0), json.dumps(reqs[k0], ensure_ascii=False, indent=1)[:1600])
else:
    print("requirements len:", len(reqs))
    if reqs:
        print("req[0] =", json.dumps(reqs[0], ensure_ascii=False, indent=1)[:1600])

print()
print("=" * 78)
print("asset_index.json")
print("=" * 78)
ai = json.loads((L / "asset_index.json").read_text(encoding="utf-8"))
print("top keys:", sorted(ai.keys()))
for key in ("assets", "candidates", "entries", "items"):
    lst = ai.get(key)
    if isinstance(lst, list):
        print("{}: len={}".format(key, len(lst)))
        for c in lst:
            print("   ", json.dumps({k: c.get(k) for k in
                                     ("asset_id", "sha256", "path", "bytes", "width",
                                      "height", "decode_status", "media_type",
                                      "name", "relative_path")}, ensure_ascii=False)[:320])
        break
