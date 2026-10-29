# -*- coding: utf-8 -*-
"""检查沙箱项目干跑事件：装配类别/时间轴/门禁口径（只读）。"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
PID = sys.argv[1] if len(sys.argv) > 1 else "p_732bb1b11c1c"

con = sqlite3.connect("file:" + (R / "projects" / "video_studio.db").as_posix() + "?mode=ro",
                      uri=True)
con.row_factory = sqlite3.Row
print("=== events for", PID, "===")
for r in con.execute("select type, actor, task_id, payload, ts from events "
                     "where project_id=? order by ts", (PID,)):
    d = dict(r)
    pay = d["payload"] or ""
    try:
        pj = json.loads(pay)
    except Exception:
        pj = {"raw": pay[:200]}
    interesting = d["type"] in ("MATERIAL_TIMELINE", "TASK_BLOCKED", "TASK_FAILED",
                                "TASK_SUCCEEDED", "TASK_CREATED", "ARTIFACT_CREATED")
    if not interesting:
        continue
    print("-", d["type"], "|", d["actor"], "|", d["task_id"])
    if d["type"] == "MATERIAL_TIMELINE":
        print("   scene_count:", pj.get("scene_count"),
              "scenes_with_asset:", pj.get("scenes_with_asset"),
              "assembly_class:", pj.get("assembly_class"),
              "material_assembly:", pj.get("material_assembly"))
        print("   assets_used:", pj.get("assets_used"))
        print("   fallback_states:", json.dumps(pj.get("fallback_states"), ensure_ascii=False))
        print("   insufficiency:", json.dumps(pj.get("insufficiency_classes"), ensure_ascii=False))
    elif d["type"] in ("TASK_BLOCKED", "TASK_FAILED"):
        print("   error:", str(pj.get("error"))[:500])
con.close()

# 从干跑中重建时间轴总量（与 agent 同公式）
print()
print("=== 时间轴核算（v2 路径）===")
from video_studio.core import narration as N  # noqa: E402
sys.path.insert(0, str(R / "src"))
