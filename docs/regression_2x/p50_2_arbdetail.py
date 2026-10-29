# -*- coding: utf-8 -*-
"""Phase 50 / P50-3① 验证：`RENDER_ARBITRATION_DETAIL` 是否落账且字段可用于逐笔核验。"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
con = sqlite3.connect("file:" + (R / "projects/video_studio.db").as_posix()
                      + "?mode=ro", uri=True)
con.row_factory = sqlite3.Row
fx = json.loads((R / "output/phase36_p36_4_sandbox/fixture.json")
                .read_text(encoding="utf-8"))
pid = fx["sandbox_project_id"]
print("sandbox:", pid)
rows = list(con.execute(
    "select payload from events where project_id=? "
    "and type='RENDER_ARBITRATION_DETAIL'", (pid,)))
print("RENDER_ARBITRATION_DETAIL 事件数:", len(rows))
for r in rows:
    d = json.loads(r["payload"] or "{}")
    print("  景数 {} | 字段 {}".format(d.get("scene_count"),
                                      ",".join(d.get("fields") or [])[:90]))
    for rec in (d.get("records") or []):
        v = rec.get("vlm") or {}
        print("    {} | 处置={} | 终态={} | model={} | presence={} | cache={} | err={}".format(
            rec.get("scene_id"), rec.get("arbitration"), rec.get("final"),
            v.get("model"), v.get("presence"), v.get("cache_hit"),
            v.get("error_code")))
