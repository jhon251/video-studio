# -*- coding: utf-8 -*-
"""查看 Phase 16 选材记录里的素材字段（定位可用路径）。"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
pid = "p_32aded38172b"
con = sqlite3.connect("file:" + (R / "projects" / "video_studio.db").as_posix() + "?mode=ro",
                      uri=True)
con.row_factory = sqlite3.Row
for r in con.execute("select payload from events where project_id=? and type='MATERIAL_TIMELINE'",
                     (pid,)):
    j = json.loads(r["payload"])
    for d in j.get("decisions") or []:
        if d.get("scene_id") == "S02":
            sa = d.get("selected_asset") or {}
            print("keys:", sorted(sa.keys()))
            print(json.dumps(sa, ensure_ascii=False, indent=1))
con.close()
