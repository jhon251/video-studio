# -*- coding: utf-8 -*-
"""5-K 只读：DB 表结构探针。"""
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")
con = sqlite3.connect("file:C:/mp4agent/video-studio/projects/video_studio.db?mode=ro", uri=True)
tabs = [r[0] for r in con.execute(
    "select name from sqlite_master where type='table' order by name")]
print("TABLES:", tabs)
for t in ("tasks", "events", "artifacts", "projects"):
    if t in tabs:
        print(t, "cols:", [c[1] for c in con.execute("pragma table_info({})".format(t))])
con.close()
