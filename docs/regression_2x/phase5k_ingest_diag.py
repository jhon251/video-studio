# -*- coding: utf-8 -*-
"""5-K 诊断（只读）：run_ingest_test 失败项目的任务链停点。

用法: python docs/regression_2x/phase5k_ingest_diag.py <project_id>
产出: stdout + docs/regression_2x/logs/phase5k_ingest_diag.json
"""
import json
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
DB = ROOT / "projects" / "video_studio.db"
LOGS = ROOT / "docs" / "regression_2x" / "logs"
pid = sys.argv[1] if len(sys.argv) > 1 else "p_943fff2250e5"

con = sqlite3.connect("file:{}?mode=ro".format(DB.as_posix()), uri=True)
con.row_factory = sqlite3.Row

tables = [r[0] for r in con.execute("select name from sqlite_master where type='table' order by name")]
out = {"project_id": pid, "tables": tables}

tcols = [c[1] for c in con.execute("pragma table_info(tasks)")]
out["tasks_columns"] = tcols
key = "task_id"
sel = [c for c in (key, "task_type", "agent_role", "status", "dependencies", "retry_count",
                   "error", "requires_approval", "approval", "model_used", "cost_usd",
                   "updated_at") if c in tcols]
rows = [dict(r) for r in con.execute(
    "select {} from tasks where project_id=? order by {}".format(", ".join(sel), key), (pid,))]
rows = [{("id" if k == key else k): v for k, v in r.items()} for r in rows]
for r in rows:
    r["type"] = r.pop("task_type", None)
    r["attempts"] = r.get("retry_count")
out["task_count"] = len(rows)
by_status = {}
for r in rows:
    by_status.setdefault(r["status"], []).append(r["type"])
out["by_status"] = {k: {"n": len(v), "types": sorted(set(v))} for k, v in by_status.items()}
out["non_succeeded"] = [r for r in rows if r["status"] != "SUCCEEDED"]
print("project", pid, "tasks", len(rows))
print("columns:", ", ".join(tcols))
for k, v in sorted(out["by_status"].items()):
    print("  {:12s} n={:3d} {}".format(k, v["n"], ", ".join(v["types"])[:120]))
print("\n非 SUCCEEDED 明细（最多 20 条）:")
for r in out["non_succeeded"][:20]:
    print("  {:8s} {:22s} attempts={} deps={} approval={} err={} updated={}".format(
        str(r["id"])[:8], str(r["type"]), r["attempts"], str(r.get("dependencies"))[:36],
        str(r.get("approval"))[:24], str(r.get("error"))[:60], r["updated_at"]))
for t in ("events", "changelog", "artifacts"):
    if t in tables:
        cols = [c[1] for c in con.execute("pragma table_info({})".format(t))]
        if "project_id" in cols:
            n = con.execute("select count(*) from {} where project_id=?".format(t), (pid,)).fetchone()[0]
            out["{}_rows".format(t)] = n
            print("{} rows: {}".format(t, n))
if "events" in tables:
    cols = [c[1] for c in con.execute("pragma table_info(events)")]
    sel = [c for c in ("event_id", "ts", "type", "actor", "task_id", "payload")
           if c in cols]
    q = "select {} from events where project_id=? order by rowid desc limit 25".format(", ".join(sel))
    ev = [[str(x)[:200] for x in r] for r in con.execute(q, (pid,))]
    out["recent_events"] = ev
    print("\n最近事件（≤25）:")
    for e in ev:
        print("   ", " | ".join(e))
con.close()
(LOGS / "phase5k_ingest_diag.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                               encoding="utf-8")
print("\njson ->", LOGS / "phase5k_ingest_diag.json")
