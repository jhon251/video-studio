# -*- coding: utf-8 -*-
"""P14-2 selection_override 决定勘查（只读）：能否恢复 (scene, asset) 逐对人工标签。"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import sys
from collections import Counter

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
con = sqlite3.connect("file:" + (R / "projects" / "video_studio.db").as_posix() + "?mode=ro",
                      uri=True)
con.row_factory = sqlite3.Row

rows = [dict(r) for r in con.execute(
    "select decision_id, project_id, node, made_by, state, rationale, artifact_snapshot "
    "from decisions where node='selection_override' limit 12")]
print("selection_override samples:", len(rows))
for d in rows:
    print("-" * 70)
    print("id={} state={} by={}".format(d["decision_id"], d["state"], d["made_by"]))
    print("  rationale:", str(d["rationale"])[:300])
    snap = d["artifact_snapshot"]
    try:
        j = json.loads(snap) if isinstance(snap, str) else snap
    except Exception:                                                       # noqa: BLE001
        j = snap
    print("  snapshot type:", type(j).__name__,
          "| ", json.dumps(j, ensure_ascii=False)[:600] if j is not None else None)

print()
print("=== made_by 分布（selection_override）===")
for r in con.execute("select made_by, count(*) n from decisions where "
                     "node='selection_override' group by made_by order by n desc"):
    print("  {:28s} {}".format(str(r["made_by"]), r["n"]))

print()
print("=== 是否存在携带 asset/scene 的结构（全表扫描关键词）===")
n = 0
for d in con.execute("select decision_id, node, artifact_snapshot from decisions "
                     "where artifact_snapshot like '%scene_id%' limit 10"):
    n += 1
    print("  {} {} | {}".format(d["decision_id"], d["node"],
                                str(d["artifact_snapshot"])[:300]))
print("  rows containing 'scene_id':", n)
con.close()
