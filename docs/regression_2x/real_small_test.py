"""Phase 1.1 minimal real-LLM test: real API + accounting end-to-end, 2-3 calls only.

Usage: python docs/regression_2x/real_small_test.py
"""
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
PROMPT = "3.x Phase 1.1 真实小测：做一期介绍潮汐锁定的短视频。"


def cli(*args):
    p = subprocess.run([sys.executable, "run.py", "--config", "config/config.real.json", *args],
                       cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


rc, out = cli("init", PROMPT, "--name", "test_small_real")
print("init ->", out.strip())
pid = re.search(r"p_[0-9a-f]+", out).group(0)
rc, out = cli("plan", pid)
print("plan ->", out.strip())

for i in range(6):
    rc, out = cli("run", pid)
    print("run{} -> {}".format(i + 1, out.strip().splitlines()[-1][:60]))
    con = sqlite3.connect(str(ROOT / "projects" / "video_studio.db"))
    n = con.execute("select count(*) c from events where project_id=? and type='LLM_CALL'",
                    (pid,)).fetchone()[0]
    con.close()
    if n >= 3:
        break

con = sqlite3.connect(str(ROOT / "projects" / "video_studio.db"))
con.row_factory = sqlite3.Row
calls = []
for r in con.execute("select payload from events where project_id=? and type='LLM_CALL'", (pid,)):
    calls.append(json.loads(r["payload"]))
tasks = [dict(r) for r in con.execute(
    "select task_type,status,model_used,cost_usd,retry_count,error from tasks where project_id=?",
    (pid,))]
con.close()

mock_calls = [c for c in calls if c.get("mock")]
cost = sum(float(c.get("cost_usd") or 0) for c in calls)
tok = sum(int(c.get("total_tokens") or 0) for c in calls)
task_cost = sum(float(t["cost_usd"] or 0) for t in tasks)
print("\n=== 真实小测结果 ===")
for c in calls:
    print("  {:16s} tier={} tok={:6d} lat={:6d}ms att={} band={:8s} ${:.6f}".format(
        str(c.get("model")), c.get("tier"), c.get("total_tokens") or 0,
        c.get("latency_ms") or 0, c.get("attempts"), str(c.get("price_band")),
        float(c.get("cost_usd") or 0)))
print("调用 {} 次 | tokens {} | 台账 ${:.6f} | 任务行累计 ${:.6f}".format(
    len(calls), tok, cost, task_cost))
print("MockLLM 调用 {} 次（应为 0）| 模型: {}".format(
    len(mock_calls), sorted({str(c.get("model")) for c in calls})))
fails = []
if len(calls) < 2:
    fails.append("真实调用少于 2 次")
if mock_calls:
    fails.append("出现 MockLLM 调用（应为 0）")
if cost <= 0:
    fails.append("台账费用为 0（真实调用应产生费用）")
if task_cost <= 0:
    fails.append("任务行费用未写回")
if not any(t["status"] == "SUCCEEDED" for t in tasks):
    fails.append("没有任务成功")
errs = [t for t in tasks if t["status"] in ("FAILED", "BLOCKED")]
print("失败/阻塞任务:", [(t["task_type"], t["status"], (t["error"] or "")[:60]) for t in errs] or "无")
print("\nVERDICT:", "PASS" if not fails else "FAIL " + str(fails))
(ROOT / "docs" / "regression_2x" / "logs" / "real_small_test.json").write_text(
    json.dumps({"project": pid, "calls": calls, "cost_usd": cost, "task_cost_usd": task_cost,
                "tokens": tok, "fails": fails, "verdict": "PASS" if not fails else "FAIL"},
               ensure_ascii=False, indent=1), encoding="utf-8")
sys.exit(1 if fails else 0)
