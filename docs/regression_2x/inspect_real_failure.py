"""Inspect the failed real-run project: full task errors + events schema/content."""
import json
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
con = sqlite3.connect(str(ROOT / "projects" / "video_studio.db"))
con.row_factory = sqlite3.Row

print("=== events 表结构 ===")
print([r[1] for r in con.execute("PRAGMA table_info(events)")])
print("=== tasks 表结构（部分）===")
print([r[1] for r in con.execute("PRAGMA table_info(tasks)")])

pid = [dict(r)["project_id"] for r in con.execute(
    "select project_id from projects order by created_at desc limit 1")][0]
print("\n最新项目:", pid)

print("\n=== 该项目的失败任务与完整错误 ===")
for r in con.execute("select task_id,task_type,status,version,retry_count,error,model_used,cost_usd"
                     " from tasks where project_id=? and status in ('FAILED','BLOCKED')", (pid,)):
    d = dict(r)
    print(json.dumps({k: (str(v)[:600] if v is not None else None) for k, v in d.items()},
                     ensure_ascii=False, indent=1))

print("\n=== 该项目的事件（前 20 条）===")
cols = [r[1] for r in con.execute("PRAGMA table_info(events)")]
for r in con.execute("select * from events where project_id=? order by rowid limit 20", (pid,)):
    d = dict(r)
    print("  " + json.dumps({k: str(d.get(k))[:160] for k in cols if k != "project_id"},
                            ensure_ascii=False))
con.close()
