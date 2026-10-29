"""Aggregate Phase 1 API usage across all real-LLM projects (event ledger based)."""
import json
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
con = sqlite3.connect(str(ROOT / "projects" / "video_studio.db"))
con.row_factory = sqlite3.Row

names = {"p_314efdfbbeb2": "A 黑洞(成功)", "p_f2587e967ba8": "A 首次尝试(模式校验失败)",
         "p_e7a8b8020fb1": "B 脑机接口", "p_8f054c227bd4": "C 60秒科普(修复后)"}
grand_calls = grand_tok = 0
grand_cost = 0.0
rows = []
for pid, label in names.items():
    calls = []
    for r in con.execute("select payload from events where project_id=? and type='LLM_CALL'", (pid,)):
        try:
            calls.append(json.loads(r["payload"]))
        except (json.JSONDecodeError, TypeError):
            pass
    tok = sum(int(c.get("total_tokens") or 0) for c in calls)
    cost = sum(float(c.get("cost_usd") or 0) for c in calls)
    lat = [int(c.get("latency_ms") or 0) for c in calls]
    models = {}
    for c in calls:
        models[c.get("model")] = models.get(c.get("model"), 0) + 1
    tasks = con.execute("select count(*) n, sum(case when status='SUCCEEDED' then 1 else 0 end) ok,"
                        " sum(case when status in ('FAILED','BLOCKED') then 1 else 0 end) bad"
                        " from tasks where project_id=?", (pid,)).fetchone()
    rows.append((label, pid, len(calls), tok, cost, models, tasks["n"], tasks["ok"], tasks["bad"],
                 min(lat) if lat else 0, max(lat) if lat else 0))
    grand_calls += len(calls)
    grand_tok += tok
    grand_cost += cost
print("{:24s} {:22s} {:>5s} {:>8s} {:>10s} {:>5s} {:>4s} {:>4s} {:>7s} {:>7s}".format(
    "项目", "pid", "调用", "tokens", "费用$", "任务", "成功", "失败", "最小ms", "最大ms"))
for r in rows:
    print("{:24s} {:22s} {:5d} {:8d} {:10.4f} {:5d} {:4d} {:4d} {:7d} {:7d}".format(
        r[0], r[1], r[2], r[3], r[4], r[6], r[7], r[8], r[9], r[10]))
    print("    模型分布: {}".format(r[5]))
print("\n合计: {} 次调用 | {} tokens | ${:.4f}".format(grand_calls, grand_tok, grand_cost))

print("\n=== 账户余额（用于交叉核对真实花费）===")
import os
import urllib.request
for ln in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if ln.strip().startswith("DEEPSEEK_API_KEY="):
        os.environ["DEEPSEEK_API_KEY"] = ln.split("=", 1)[1].strip()
try:
    req = urllib.request.Request("https://api.deepseek.com/user/balance",
                                 headers={"Authorization": "Bearer " + os.environ["DEEPSEEK_API_KEY"]})
    with urllib.request.urlopen(req, timeout=60) as r:
        print(" ", json.loads(r.read().decode()))
except Exception as e:  # noqa: BLE001
    print("  余额查询失败:", e)

print("\n=== 失败/重试事件 ===")
for pid, label in names.items():
    for r in con.execute("select type,actor,payload from events where project_id=? and type in"
                         " ('TASK_FAILED','TASK_RETRYING','TASK_BLOCKED') order by ts", (pid,)):
        d = dict(r)
        print("  [{}] {:14s} {:12s} {}".format(label[:10], d["type"], str(d["actor"]),
                                               str(d["payload"])[:150]))
con.close()
