"""列出事件类型分布与失败类事件样例（只读，供 3-C report 设计用）。"""
import json
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
con = sqlite3.connect("file:{}?mode=ro".format((ROOT / "projects" / "video_studio.db").as_posix()),
                      uri=True)
con.row_factory = sqlite3.Row
print("=== 事件类型分布（全库）")
for r in con.execute("select type, count(*) c from events group by type order by c desc limit 25"):
    print("  {:28s} {}".format(r["type"], r["c"]))
print("\n=== 失败类事件样例")
for r in con.execute("select ts, project_id, task_id, type, substr(payload,1,160) p from events "
                     "where type in ('TASK_FAILED','TASK_BLOCKED','CLAIM_GATE_BLOCKED',"
                     "'HUMAN_REQUIRED','TASK_RETRY') order by ts desc limit 6"):
    print("  {} {} {} {}\n     {}".format(r["ts"], r["project_id"], r["task_id"], r["type"],
                                          r["p"]))
print("\n=== 任务状态分布")
for r in con.execute("select status, count(*) c from tasks group by status order by c desc"):
    print("  {:14s} {}".format(r["status"], r["c"]))
print("\n=== 产物类型（前 20）")
for r in con.execute("select type, count(*) c from artifacts group by type order by c desc limit 20"):
    print("  {:26s} {}".format(r["type"], r["c"]))
con.close()
