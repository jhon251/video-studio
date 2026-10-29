"""Inspect claims state for the latest real-run project (why is the claim gate still closed?)."""
import json
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
con = sqlite3.connect(str(ROOT / "projects" / "video_studio.db"))
con.row_factory = sqlite3.Row

pid = [dict(r)["project_id"] for r in con.execute(
    "select project_id from projects order by created_at desc limit 1")][0]
print("最新项目:", pid)

print("\n=== claims 表结构 ===")
print([r[1] for r in con.execute("PRAGMA table_info(claims)")])

from collections import Counter
rows = [dict(r) for r in con.execute("select * from claims where project_id=?", (pid,))]
print("\nclaims 总数:", len(rows), "| 状态分布:", dict(Counter(r.get("status") for r in rows)))
for r in rows[:6]:
    print("  ", json.dumps({k: str(r[k])[:90] for k in r if k != "project_id"}, ensure_ascii=False))

print("\n=== 任务状态分布 ===")
print(dict(Counter(dict(r)["status"] for r in con.execute(
    "select status from tasks where project_id=?", (pid,)))))

print("\n=== 最近 25 条事件 ===")
for r in con.execute("select type,actor,task_id,payload from events where project_id=?"
                     " order by ts desc limit 25", (pid,)):
    d = dict(r)
    print("  {:22s} {:12s} {}".format(str(d["type"]), str(d["actor"]), str(d["payload"])[:110]))
con.close()
