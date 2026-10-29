"""Dump full error text of BLOCKED/FAILED tasks for the latest Phase-2 acceptance project."""
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
print("project:", pid)
for r in con.execute("select task_id,task_type,status,retry_count,max_retries,error,model_used,"
                     "cost_usd from tasks where project_id=? and status in ('FAILED','BLOCKED')",
                     (pid,)):
    d = dict(r)
    print("\n=== {} {} (retry {}/{}) model={} cost={}".format(
        d["task_id"], d["task_type"], d["retry_count"], d["max_retries"], d["model_used"],
        d["cost_usd"]))
    print((d["error"] or "(no error)")[:1200])
print("\n=== 相关事件（TASK_FAILED/TASK_BLOCKED）===")
for r in con.execute("select type,actor,payload from events where project_id=? and type in"
                     " ('TASK_FAILED','TASK_BLOCKED') order by ts", (pid,)):
    d = dict(r)
    print("  {:14s} {:12s} {}".format(d["type"], str(d["actor"]), str(d["payload"])[:300]))
con.close()
