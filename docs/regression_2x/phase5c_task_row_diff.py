# -*- coding: utf-8 -*-
"""5-C 排查：列出快照 DB 与现库之间**被就地改写**的任务行，以及具体变化列（只读）。"""
import json
import pathlib
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
SNAP = ROOT / "docs" / "regression_2x" / "snapshots" / "5.x-phase5b-20260916.db"
LIVE = ROOT / "projects" / "video_studio.db"
PROJ = "p_f4b466a4a024"


def ro(path):
    con = sqlite3.connect("file:{}?mode=ro".format(pathlib.Path(path).as_posix()), uri=True)
    con.row_factory = sqlite3.Row
    return con


s, l = ro(SNAP), ro(LIVE)
cols = [r[1] for r in s.execute("pragma table_info(tasks)")]
s_rows = {r["task_id"]: dict(r) for r in s.execute("select * from tasks")}
l_rows = {r["task_id"]: dict(r) for r in l.execute("select * from tasks")}
changed = []
for tid, sv in s_rows.items():
    lv = l_rows.get(tid)
    if lv is None:
        continue
    diffs = {}
    for c in cols:
        if sv[c] != lv[c]:
            diffs[c] = {"before": sv[c], "after": lv[c]}
    if diffs:
        changed.append({"task_id": tid, "task_type": sv["task_type"], "project_id": sv["project_id"],
                        "status_before": sv["status"], "status_after": lv["status"],
                        "version": sv["version"], "diff_columns": sorted(diffs),
                        "diffs": diffs})
print("changed task rows:", len(changed))
for c in changed:
    print("\n==", c["task_id"], c["task_type"], c["project_id"], "v", c["version"],
          c["status_before"], "->", c["status_after"])
    for col, d in c["diffs"].items():
        print("   ", col, ":", json.dumps(d["before"], ensure_ascii=False)[:160], "->",
              json.dumps(d["after"], ensure_ascii=False)[:160])
print("\nchanged for this project:",
      [c["task_id"] for c in changed if c["project_id"] == PROJ])
print("changed for other projects:",
      [(c["task_id"], c["project_id"]) for c in changed if c["project_id"] != PROJ])
s.close()
l.close()
