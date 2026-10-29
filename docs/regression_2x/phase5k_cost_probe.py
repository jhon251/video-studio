# -*- coding: utf-8 -*-
"""5-K 只读：今天新建的回归项目及其真实成本/任务数（证据用）。

用法: python docs/regression_2x/phase5k_cost_probe.py [days]
产出: docs/regression_2x/logs/phase5k_cost_probe.json
"""
import json
import sqlite3
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
LOGS = ROOT / "docs" / "regression_2x" / "logs"
since = time.time() - float(sys.argv[1] if len(sys.argv) > 1 else 1) * 86400

con = sqlite3.connect("file:{}?mode=ro".format((ROOT / "projects" / "video_studio.db").as_posix()),
                      uri=True)
rows = []
for pid, name, created in con.execute(
        "select project_id, name, created_at from projects order by created_at desc limit 60"):
    try:
        ts = float(created)
    except (TypeError, ValueError):
        continue
    if ts < since:
        continue
    n = con.execute("select count(*) from tasks where project_id=?", (pid,)).fetchone()[0]
    ok = con.execute("select count(*) from tasks where project_id=? and status='SUCCEEDED'",
                     (pid,)).fetchone()[0]
    cost = con.execute("select coalesce(sum(cost_usd),0) from tasks where project_id=?",
                       (pid,)).fetchone()[0]
    models = [r[0] for r in con.execute(
        "select distinct model_used from tasks where project_id=? and model_used is not null",
        (pid,))]
    art = con.execute("select count(*) from artifacts where project_id=?", (pid,)).fetchone()[0]
    rows.append({"project_id": pid, "name": name, "created_at": created, "tasks": n,
                 "succeeded": ok, "artifacts": art, "cost_usd": round(float(cost or 0), 5),
                 "models": sorted(models)})
con.close()
out = {"since": since, "projects": rows,
       "total_cost_usd": round(sum(r["cost_usd"] for r in rows), 5),
       "real_model_used": any(m.startswith(("deepseek-flash", "deepseek-v4")) for r in rows
                              for m in r["models"])}
(LOGS / "phase5k_cost_probe.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                              encoding="utf-8")
print("projects (last {}d): {}".format(sys.argv[1] if len(sys.argv) > 1 else 1, len(rows)))
for r in rows:
    print("  {:18s} {:22s} tasks={:3d} ok={:3d} art={:3d} cost=${:.5f} models={}".format(
        r["project_id"], str(r["name"])[:22], r["tasks"], r["succeeded"], r["artifacts"],
        r["cost_usd"], ",".join(r["models"])[:60]))
print("total cost: ${:.5f}".format(out["total_cost_usd"]))
print("json ->", LOGS / "phase5k_cost_probe.json")
