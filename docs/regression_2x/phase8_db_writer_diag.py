# -*- coding: utf-8 -*-
"""Phase 8 只读诊断：最近写入的 tasks/projects 归属（判断是否由回归套件造成）。"""
import json
import pathlib
import sqlite3
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
con = sqlite3.connect("file:" + (R / "projects" / "video_studio.db").as_posix() + "?mode=ro",
                      uri=True)
con.row_factory = sqlite3.Row
con.execute("PRAGMA query_only=ON")
print("== 最近 12 个 task ==")
for r in con.execute("select task_id, project_id, task_type, status, created_at from tasks "
                     "order by created_at desc limit 12"):
    print("   {} | {} | {:18s} | {:10s} | {}".format(r["task_id"][:18], r["project_id"],
                                                    r["task_type"], r["status"],
                                                    r["created_at"]))
print("\n== 最近 8 个 project ==")
cols = [x[1] for x in con.execute("PRAGMA table_info(projects)")]
tcol = next((c for c in cols if "time" in c or c in ("created_at", "ts")), cols[-1])
for r in con.execute("select * from projects order by {} desc limit 8".format(tcol)):
    d = dict(r)
    print("   {} | {}".format(d.get("project_id"),
                              json.dumps({k: d[k] for k in list(d)[:6] if k != "project_id"},
                                         ensure_ascii=False)[:120]))
print("\n== 近 24h 新增 task 的 task_type 分布 ==")
rows = con.execute("select task_type, count(*) n from tasks where created_at >= "
                   "datetime('now','-1 day') group by task_type order by n desc").fetchall()
print("   ", json.dumps({r["task_type"]: r["n"] for r in rows}, ensure_ascii=False))
con.close()
