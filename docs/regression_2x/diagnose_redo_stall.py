"""Diagnose the post-redo stall: do downstream tasks still depend on the OLD (blocked) task?"""
import json
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
pid = sys.argv[1]
con = sqlite3.connect(str(ROOT / "projects" / "video_studio.db"))
con.row_factory = sqlite3.Row
tasks = [dict(r) for r in con.execute("select * from tasks where project_id=?", (pid,))]
by_id = {t["task_id"]: t for t in tasks}

print("=== render 任务的所有版本 ===")
for t in tasks:
    if t["task_type"] == "render":
        print("  {} version={} status={} deps={}".format(
            t["task_id"], t["version"], t["status"], t["dependencies"]))

print("\n=== PENDING 任务及其依赖状态 ===")
for t in tasks:
    if t["status"] != "PENDING":
        continue
    deps = json.loads(t["dependencies"]) if isinstance(t["dependencies"], str) else t["dependencies"]
    detail = []
    for d in deps or []:
        dt = by_id.get(d)
        detail.append("{}={}".format(d, dt["status"] if dt else "MISSING"))
    print("  {:16s} deps: {}".format(t["task_type"], ", ".join(detail) or "(无)"))
con.close()
