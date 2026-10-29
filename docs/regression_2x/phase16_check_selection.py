# -*- coding: utf-8 -*-
"""检查 Phase 16 干跑的选材结果：池使用分布（预示 DQ-2/DQ-3 走向）。"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import sys
from collections import defaultdict

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
fix = json.loads((R / "output/phase16_p16_5_sandbox/fixture.json").read_text(encoding="utf-8"))
pid = fix["sandbox_project_id"]
con = sqlite3.connect("file:" + (R / "projects" / "video_studio.db").as_posix() + "?mode=ro",
                      uri=True)
con.row_factory = sqlite3.Row
for r in con.execute("select payload from events where project_id=? and type='MATERIAL_TIMELINE'",
                     (pid,)):
    j = json.loads(r["payload"])
    print("scenes:", j.get("scene_count"), "| with_asset:", j.get("scenes_with_asset"),
          "| assembly:", j.get("assembly_class"), j.get("material_assembly"))
    by = defaultdict(list)
    print()
    print("{:>4} {:>9} {:>10} {}".format("景", "时长s", "素材", "名称"))
    for d in j.get("decisions") or []:
        sa = d.get("selected_asset") or {}
        by[sa.get("asset_id") or "-"].append(d.get("scene_id"))
        print("{:>4} {:>9} {:>10} {}".format(
            d.get("scene_id"), d.get("hold_s") or "-", (sa.get("asset_id") or "-")[-6:],
            str(sa.get("name"))[:52]))
    print()
    print("复用分布（asset -> 景数）:")
    for a, ss in sorted(by.items(), key=lambda kv: -len(kv[1])):
        print("  {:>8} x{}  {}".format(a[-8:], len(ss), ",".join(ss)))
    print()
    print("唯一素材数:", len(by), "| 总景数:", len(j.get("decisions") or []))
con.close()
