# -*- coding: utf-8 -*-
"""定案校验：P13E-3 ② 沙箱项目的最终注册状态（只读）。"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
PID = "p_e4c65c1c58ed"
sys.stdout.reconfigure(encoding="utf-8")

con = sqlite3.connect("file:" + (R / "projects" / "video_studio.db").as_posix() + "?mode=ro",
                      uri=True)
con.row_factory = sqlite3.Row

print("=== 沙箱项目产物类型分布 ===")
for r in con.execute("select type, count(*) n from artifacts where project_id=? group by type "
                     "order by type", (PID,)):
    print("  {:28s} {}".format(r["type"], r["n"]))

types = [r["type"] for r in con.execute(
    "select distinct type from artifacts where project_id=?", (PID,))]
print()
print("  render_output 已登记 :", "render_output" in types)
print("  attribution  已登记 :", "attribution" in types)

print()
print("=== 渲染任务终态 ===")
for r in con.execute("select task_id, task_type, agent_role, status, retry_count, "
                     "substr(coalesce(error,''),1,180) err from tasks "
                     "where project_id=? and agent_role='editing'", (PID,)):
    print("  {} {} status={} retries={}".format(r["task_id"], r["task_type"], r["status"],
                                                r["retry_count"]))
    print("    error:", r["err"])

print()
print("=== 门禁阻断事件（human_visible）===")
for r in con.execute("select type, actor, human_visible, substr(payload,1,200) p from events "
                     "where project_id=? and type in ('TASK_BLOCKED','TASK_FAILED')", (PID,)):
    print("  {} actor={} human_visible={}".format(r["type"], r["actor"], r["human_visible"]))
    print("    ", r["p"][:190])

print()
print("=== 最终状态文件关键字段 ===")
st = json.loads((L / "phase13e_p13e3_final_state.json").read_text(encoding="utf-8"))
ex = st["executed"]
print("  status           :", ex["status"])
print("  candidate        :", ex["sandbox"]["candidate"])
print("  candidate_bytes  :", ex["sandbox"]["candidate_bytes"])
print("  candidate_sha256 :", ex["sandbox"]["candidate_sha256"][:24], "…")
print("  render_wall_s    :", ex["sandbox"]["render_wall_clock_s"])
print("  motion applied   :", len(ex["motion"]["applied_scenes"]), "景 | fallback:",
      len(ex["motion"]["fallback"]))
print("  duration         :", ex["gates"]["duration_contract"]["measured_s"], "s")
print("  loudness         :", ex["gates"]["loudness"]["independent_measure"])
print("  PI pre/post block:", ex["gates"]["pi_pre_render"]["blocked"],
      ex["gates"]["pi_post_render"]["blocked"],
      "| promote_blocked:", ex["gates"]["pi_post_render"]["promote_blocked"])
print("  corr             :", ex["gates"]["per_scene_corr"]["passed"], "/",
      ex["gates"]["per_scene_corr"]["total"],
      "| failed:", ex["gates"]["per_scene_corr"]["failed"],
      "| thresholds_relaxed:", ex["gates"]["per_scene_corr"]["thresholds_relaxed"])
print("  motion_verified  :", ex["gates"]["motion_verified"]["verified"], "/",
      ex["gates"]["motion_verified"]["enabled_scenes"])
print("  subtitle         :", ex["gates"]["subtitle_alignment"])
print("  regression       :", ex["regression"]["suites_total"], "套件 /",
      ex["regression"]["rc0"], "rc=0 / failed:", ex["regression"]["failed"])
print("  immutability     :", ex["immutability"]["verdict"])
print("  registration     :", json.dumps(ex["registration"], ensure_ascii=False))
con.close()
