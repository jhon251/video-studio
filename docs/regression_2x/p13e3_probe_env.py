# -*- coding: utf-8 -*-
"""P13E-3 ② 环境勘查（只读）：既有产物/voice 载荷/脚本/依赖可用性。零写入。"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
PID = "p_96efdc03e1aa"
sys.stdout.reconfigure(encoding="utf-8")

con = sqlite3.connect("file:" + (R / "projects" / "video_studio.db").as_posix() + "?mode=ro", uri=True)
con.row_factory = sqlite3.Row

print("=== artifacts of interest (script_output / voice_output / retrieval_candidates) ===")
rows = [dict(r) for r in con.execute(
    "select artifact_id, task_id, type, path, size, created_at from artifacts "
    "where project_id=? and type in ('script_output','voice_output','retrieval_candidates',"
    "'visual_plan_output') order by created_at", (PID,))]
for r in rows:
    print(r["created_at"], r["type"], r["artifact_id"], r["task_id"], r["size"], r["path"])

print()
print("=== voice_output payload summary ===")
for r in rows:
    if r["type"] != "voice_output":
        continue
    p = pathlib.Path(r["path"])
    if not p.is_file():
        print("MISSING FILE", p)
        continue
    j = json.loads(p.read_text(encoding="utf-8"))
    keys = sorted(j.keys())
    print("---", r["artifact_id"], "keys:", keys)
    print("   complete:", j.get("complete"), "| audio:", j.get("audio"),
          "| audio_time_base_s:", j.get("audio_time_base_s"))
    segs = j.get("segments") or []
    print("   segments:", len(segs))
    if segs:
        print("   seg[0] keys:", sorted(segs[0].keys()))
        print("   seg[0]:", json.dumps(segs[0], ensure_ascii=False)[:300])
    ps = j.get("payload") or {}
    if ps:
        print("   payload.audio:", ps.get("audio"), "| payload keys:", sorted(ps.keys())[:15])

print()
print("=== tasks for project ===")
for r in con.execute("select task_id, task_type, agent_role, status, created_at, "
                     "dependencies, artifacts from tasks where project_id=? "
                     "order by created_at", (PID,)):
    d = dict(r)
    print(d["task_id"], d["task_type"], d["agent_role"], d["status"],
          "deps=", json.loads(d["dependencies"] or "[]"),
          "arts=", json.loads(d["artifacts"] or "[]"))

print()
print("=== derived DCv2 script ===")
sp = R / "output" / "phase13e_script_sandbox" / "script_dcv2_derived_v1.json"
sj = json.loads(sp.read_text(encoding="utf-8"))
print("path:", sp, "| keys:", sorted(sj.keys()))
segs = sj.get("segments") or []
print("segments:", len(segs), "| total_duration_s:", sj.get("total_duration_s"))
if segs:
    print("seg[0]:", json.dumps({k: v for k, v in segs[0].items() if k != "narration"},
                                ensure_ascii=False)[:400])
    print("seg[0] keys:", sorted(segs[0].keys()))
    print("all scene_ids:", [s.get("scene_id") for s in segs])
con.close()
