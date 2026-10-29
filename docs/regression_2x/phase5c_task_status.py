# -*- coding: utf-8 -*-
"""5-C helper: print status of given task ids (read-only)."""
import json
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")

DB = r"projects/video_studio.db"
ids = sys.argv[1:]
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
out = []
for tid in ids:
    r = con.execute(
        "select task_id, task_type, status, version, project_id, error, updated_at "
        "from tasks where task_id=?",
        (tid,),
    ).fetchone()
    out.append(dict(r) if r else {"task_id": tid, "missing": True})
print(json.dumps(out, ensure_ascii=False, indent=2))
