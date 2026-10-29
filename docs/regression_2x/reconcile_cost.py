"""Phase 1.1 cost reconciliation: quantify UNLEDGERED API calls from the judge tools.

The three judge tools (evidence_signal / llm_semantic_judge / sufficiency_judge) call
router.client.complete(...) directly, bypassing Router.complete -> no LLM_CALL event, no cost row.
They persist rows in llm_judge_cache (tokens_in/tokens_out/cost_usd/latency_ms).

This script sums those rows for the Phase 1 real-run window and compares with the ledger.
"""
import json
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
con = sqlite3.connect(str(ROOT / "projects" / "video_studio.db"))
con.row_factory = sqlite3.Row

print("=== llm_judge_cache 结构 ===")
cols = [r[1] for r in con.execute("PRAGMA table_info(llm_judge_cache)")]
print(cols)
n = con.execute("select count(*) c from llm_judge_cache").fetchone()["c"]
print("总行数:", n)
if n:
    r = con.execute("select * from llm_judge_cache order by rowid desc limit 1").fetchone()
    print("样例行:", {k: str(r[k])[:80] for k in cols})

# 真实运行窗口：Phase 1 四个项目的 created_at 区间
pids = ("p_314efdfbbdfeb2", "p_314efdfbbeb2", "p_f2587e967ba8", "p_e7a8b8020fb1", "p_8f054c227bd4")
ts = []
for p in pids:
    row = con.execute("select created_at from projects where project_id=?", (p,)).fetchone()
    if row:
        ts.append(float(row["created_at"]))
if ts:
    lo, hi = min(ts) - 120, max(ts) + 3600
    print("\nPhase 1 窗口: {} .. {} (epoch)".format(round(lo), round(hi)))
    rows = [dict(r) for r in con.execute(
        "select * from llm_judge_cache where created_at >= ? and created_at <= ?", (lo, hi))]
    print("窗口内 judge 缓存行数:", len(rows))
    tin = sum(int(r.get("tokens_in") or 0) for r in rows)
    tout = sum(int(r.get("tokens_out") or 0) for r in rows)
    cost = sum(float(r.get("cost_usd") or 0) for r in rows)
    hit = sum(1 for r in rows if r.get("cache_hit"))
    print("  tokens_in={} tokens_out={} tokens_total={} cost_usd列合计={:.6f} cache_hit行={}".format(
        tin, tout, tin + tout, cost, hit))
    from collections import Counter
    print("  模型分布:", dict(Counter(r.get("model") for r in rows)))
    print("  prompt_version:", dict(Counter(str(r.get("prompt_version")) for r in rows)))

print("\n=== 全表非窗口行（其它时期）===")
if n:
    rows_all = [dict(r) for r in con.execute("select * from llm_judge_cache")]
    if ts:
        rows_all = [r for r in rows_all if not (lo <= float(r.get("created_at") or 0) <= hi)]
    print("行数:", len(rows_all),
          "| tokens:", sum(int(r.get("tokens_in") or 0) + int(r.get("tokens_out") or 0)
                           for r in rows_all),
          "| cost 列:", round(sum(float(r.get("cost_usd") or 0) for r in rows_all), 6))

print("\n=== 台账（LLM_CALL）对照 ===")
tot_calls = tot_tok = 0
tot_cost = 0.0
for p in ("p_314efdfbbeb2", "p_e7a8b8020fb1", "p_8f054c227bd4"):
    for r in con.execute("select payload from events where project_id=? and type='LLM_CALL'", (p,)):
        try:
            d = json.loads(r["payload"])
        except (json.JSONDecodeError, TypeError):
            continue
        tot_calls += 1
        tot_tok += int(d.get("total_tokens") or 0)
        tot_cost += float(d.get("cost_usd") or 0)
print("ledger: {} 次 / {} tokens / ${:.6f}".format(tot_calls, tot_tok, tot_cost))
con.close()
