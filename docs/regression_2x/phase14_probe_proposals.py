# -*- coding: utf-8 -*-
"""勘查 phase6g_rebuild_proposals.json：是否含人工指定的替代素材（可作正例标签）。"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")

cands = [L / "phase6g_rebuild_proposals.json"]
print("候选文件:", [c.name for c in cands])
for c in cands:
    j = json.loads(c.read_text(encoding="utf-8"))
    print()
    print("=" * 74)
    print(c.name, "| top keys:", sorted(j.keys())[:30])
    for k in ("forbidden_material", "proposals", "per_scene", "scenes", "binding"):
        if k in j:
            print("--", k, "=>", json.dumps(j[k], ensure_ascii=False)[:1200])
