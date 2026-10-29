# -*- coding: utf-8 -*-
"""P49-2 辅助：查看 RENDER_ARBITRATION 事件字段粒度 + events 表结构。"""
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
cols = [c[1] for c in con.execute("pragma table_info(events)")]
print("events 列:", cols)
order = "rowid"
r = con.execute("select * from events where type='RENDER_ARBITRATION' "
                "order by rowid limit 1").fetchone()
if r:
    print(json.dumps({k: str(r[k])[:260] for k in r.keys()},
                     ensure_ascii=False, indent=1))
print()
n = con.execute("select count(*) from events where type='RENDER_ARBITRATION'"
                ).fetchone()[0]
print("RENDER_ARBITRATION 事件总数:", n)
print()
# 关键问题：payload 里是否有**逐景** VLM 明细
allp = [json.loads(x["payload"] or "{}") for x in con.execute(
    "select payload from events where type='RENDER_ARBITRATION'")]
keys = set()
for p in allp:
    keys |= set(p.keys())
print("所有 RENDER_ARBITRATION payload 的键集合:", sorted(keys))
detail = [p for p in allp if any(
    isinstance(p.get(k), (list, dict)) and p.get(k) for k in
    ("scenes", "detail", "per_scene", "judgements", "results"))]
print("含逐景明细的事件数:", len(detail))
