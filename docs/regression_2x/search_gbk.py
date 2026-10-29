"""Search the whole DB for the observed GBK/UnicodeDecodeError (transient CLI error)."""
import sys
import sqlite3
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
con = sqlite3.connect(str(ROOT / "projects" / "video_studio.db"))
con.row_factory = sqlite3.Row

n = 0
print("=== events 中含 gbk/UnicodeDecode ===")
for r in con.execute("select project_id,task_id,type,actor,payload from events "
                     "where payload like '%gbk%' or payload like '%UnicodeDecode%'"):
    d = dict(r)
    n += 1
    print("  {} {} {} {} :: {}".format(d["project_id"], d["task_id"], d["type"], d["actor"],
                                       str(d["payload"])[:180]))
print("命中:", n)

print("\n=== tasks.error 中含 gbk/UnicodeDecode ===")
for r in con.execute("select project_id,task_type,status,error from tasks "
                     "where error like '%gbk%' or error like '%UnicodeDecode%'"):
    d = dict(r)
    print("  {} {} {} :: {}".format(d["project_id"], d["task_type"], d["status"],
                                    str(d["error"])[:200]))

print("\n=== changelog/decisions 表是否记录 ===")
tabs = [r[0] for r in con.execute("select name from sqlite_master where type='table'")]
print("tables:", tabs)
con.close()
