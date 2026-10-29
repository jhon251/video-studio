"""Report a real-run project's LLM call ledger, failures/retries and cost (from DB events)."""
import json
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
pid = sys.argv[1]
con = sqlite3.connect(str(ROOT / "projects" / "video_studio.db"))
con.row_factory = sqlite3.Row

print("=== 失败/重试/阻塞事件 |", pid, "===")
rows = [dict(r) for r in con.execute(
    "select type,actor,task_id,payload,ts from events where project_id=? and type in "
    "('TASK_FAILED','TASK_RETRYING','TASK_BLOCKED','LLM_CALL') order by ts", (pid,))]
for d in rows:
    if d["type"] != "LLM_CALL":
        print("  {:16s} {:14s} {}".format(d["type"], str(d["actor"]), str(d["payload"])[:220]))

print("\n=== LLM_CALL 台账 ===")
n = 0
tot = 0.0
tok = 0
for d in rows:
    if d["type"] != "LLM_CALL":
        continue
    try:
        p = json.loads(d["payload"])
    except (json.JSONDecodeError, TypeError):
        continue
    n += 1
    tot += float(p.get("cost_usd") or 0)
    tok += int(p.get("total_tokens") or 0)
    print("  {:2d} {:16s} tier={} tok={:6d} lat={:7d}ms att={} band={:8s} ${:.6f}".format(
        n, str(p.get("model")), p.get("tier"), p.get("total_tokens") or 0,
        p.get("latency_ms") or 0, p.get("attempts"), str(p.get("price_band")),
        float(p.get("cost_usd") or 0)))
print("  合计: {} 次调用 | {} tokens | ${:.6f}".format(n, tok, tot))

print("\n=== 任务台账（模型/费用/重试）===")
for r in con.execute("select task_type,status,model_used,cost_usd,retry_count,error from tasks"
                     " where project_id=? order by created_at", (pid,)):
    d = dict(r)
    print("  {:16s} {:10s} {:16s} ${:.6f} retry={} {}".format(
        d["task_type"], d["status"], str(d["model_used"]), float(d["cost_usd"] or 0),
        d["retry_count"], (d["error"] or "")[:80]))
con.close()
