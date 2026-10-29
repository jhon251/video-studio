# -*- coding: utf-8 -*-
"""P32-2 必答项（精确）：P31 沙箱的 RENDER_ARBITRATION 事件载荷 + 仲裁门控逻辑。只读。"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
con = sqlite3.connect("file:" + (R / "projects" / "video_studio.db").as_posix()
                      + "?mode=ro", uri=True)
con.row_factory = sqlite3.Row
print("=== p_aafdd21cbb9d 的 RENDER_ARBITRATION 全部事件 ===")
for r in con.execute("select ts, payload from events where project_id=? and "
                     "type='RENDER_ARBITRATION' order by ts", ("p_aafdd21cbb9d",)):
    print("  ts={}".format(r["ts"]))
    print("  " + json.dumps(json.loads(r["payload"]), ensure_ascii=False, indent=1)[:1200])
print()
print("=== p_aafdd21cbb9d 的 TASK_BLOCKED 事件 ===")
for r in con.execute("select ts, payload from events where project_id=? and "
                     "type='TASK_BLOCKED' order by ts", ("p_aafdd21cbb9d",)):
    p = json.loads(r["payload"])
    print("  ts={} error={}".format(r["ts"], str(p.get("error"))[:600]))
