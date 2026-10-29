# -*- coding: utf-8 -*-
"""挑选候选文件真实存在比例最高的 retrieval 产物（只读）。"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
P = R / "projects" / "p_96efdc03e1aa"
MD = P / "media"
sys.stdout.reconfigure(encoding="utf-8")

ids = ["a_71f77918bc8a", "a_a93b3fef723a", "a_609ea7b3c895",
       "a_3d1181dcdaad", "a_64423d97f9bf", "a_8ff5eb3d88c0"]
for aid in ids:
    p = P / "artifacts" / (aid + ".json")
    if not p.is_file():
        continue
    j = json.loads(p.read_text(encoding="utf-8"))
    cands = j.get("candidates") or []
    present = [c for c in cands if (MD / str(c.get("path") or "")).is_file()]
    tot = j.get("candidates_total")
    print("{:16s} mode={:32s} cand={:>3} total={:>3} present={:>3} missing={:>3}".format(
        aid, str(j.get("material_mode")), len(cands), tot or 0,
        len(present), len(cands) - len(present)))
    for c in present:
        print("      OK  ", c.get("path"), "|", str(c.get("name"))[:60])
