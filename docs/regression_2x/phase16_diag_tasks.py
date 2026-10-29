# -*- coding: utf-8 -*-
"""诊断 Phase 16 沙箱任务状态（只读）。"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
fix = json.loads((R / "output/phase16_p16_5_sandbox/fixture.json").read_text(encoding="utf-8"))
pid = fix["sandbox_project_id"]
con = sqlite3.connect("file:" + (R / "projects" / "video_studio.db").as_posix() + "?mode=ro",
                      uri=True)
con.row_factory = sqlite3.Row
print("project:", pid)
for r in con.execute("select task_id, task_type, agent_role, status, dependencies, artifacts, "
                     "substr(coalesce(error,''),1,300) err from tasks where project_id=? "
                     "order by created_at", (pid,)):
    d = dict(r)
    print("- {} {} role={} status={}".format(d["task_id"], d["task_type"], d["agent_role"],
                                             d["status"]))
    print("    deps:", d["dependencies"], "| arts:", d["artifacts"])
    if d["err"]:
        print("    err:", d["err"][:280])
con.close()
