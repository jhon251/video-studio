"""列出关键表结构与行数（只读，供 3-C 设计 report 命令用）。"""
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
con = sqlite3.connect(str(ROOT / "projects" / "video_studio.db"))
con.row_factory = sqlite3.Row
tables = [r["name"] for r in con.execute(
    "select name from sqlite_master where type='table' order by name")]
for t in tables:
    n = con.execute("select count(*) c from {}".format(t)).fetchone()["c"]
    cols = [c["name"] for c in con.execute("pragma table_info({})".format(t))]
    print("--- {} ({} rows)".format(t, n))
    print("    cols:", ", ".join(cols))
con.close()
