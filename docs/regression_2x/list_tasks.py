"""列出项目的任务（id/类型/状态/版本），便于 redo 时取 id。

用法: python docs/regression_2x/list_tasks.py <pid>
"""
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
pid = sys.argv[1]
con = sqlite3.connect(str(ROOT / "projects" / "video_studio.db"))
con.row_factory = sqlite3.Row
for r in con.execute("select task_id, task_type, status, version, rowid from tasks "
                     "where project_id=? order by rowid", (pid,)):
    print("{:16s} {:22s} {:12s} v{}".format(r["task_id"], r["task_type"], r["status"],
                                            r["version"]))
con.close()
