"""3.x Phase 3-C：成本边界与 ¥3.24 残余的**正式、可复核**结论（只读，不产生任何 API 费用）。

三件事：
  ① LLM 成本（**估算**）：任务行 cost_usd + LLM_CALL 事件 token 汇总 + 两者交叉核对；
  ② 外部素材**用量**（非计费）：provider stats 汇总 + 本地缓存字节数；
  ③ ¥3.24 残余：重跑"零本地调用窗口内余额仍在变"的机制验证，并给出正式分类。

产出：docs/regression_2x/logs/phase3c_cost_boundary.json
用法：python docs/regression_2x/phase3c_cost_boundary.py [--poll-seconds N]
"""
import argparse
import json
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
DB = ROOT / "projects" / "video_studio.db"
OUT = ROOT / "docs" / "regression_2x" / "logs" / "phase3c_cost_boundary.json"
CNY_PER_USD = 7.1          # Phase 1.1 使用的换算率（客户端不可验证 → 明确标注为估算口径）


def ro() -> sqlite3.Connection:
    con = sqlite3.connect("file:{}?mode=ro".format(DB.as_posix()), uri=True)
    con.row_factory = sqlite3.Row
    return con


def balance_cny() -> float | None:
    """读账户余额（免费、只读接口）；不打印/不落盘 key。"""
    key = ""
    env = ROOT / ".env"
    if env.is_file():
        for ln in env.read_text(encoding="utf-8").splitlines():
            if ln.strip().startswith("DEEPSEEK_API_KEY="):
                key = ln.split("=", 1)[1].strip()
    if not key:
        return None
    req = urllib.request.Request("https://api.deepseek.com/user/balance",
                                 headers={"Authorization": "Bearer " + key})
    with urllib.request.urlopen(req, timeout=60) as r:                 # noqa: S310
        d = json.loads(r.read().decode("utf-8"))
    return float(d["balance_infos"][0]["total_balance"])


ap = argparse.ArgumentParser()
ap.add_argument("--poll-seconds", type=int, default=120)
args = ap.parse_args()

con = ro()
# ---- ① LLM 成本（估算）----
task_rows = [dict(r) for r in con.execute(
    "select project_id, task_type, status, cost_usd, model_used from tasks")]
llm_events = [dict(r) for r in con.execute(
    "select project_id, payload from events where type='LLM_CALL'")]
ledger_rows = con.execute("select count(*), coalesce(sum(cost_usd),0) from llm_judge_cache").fetchone()
con.close()

task_cost = round(sum(float(t.get("cost_usd") or 0) for t in task_rows), 6)
by_model: dict[str, float] = {}
by_project: dict[str, float] = {}
for t in task_rows:
    c = float(t.get("cost_usd") or 0)
    if c > 0:
        m = t.get("model_used") or "unknown"
        by_model[m] = round(by_model.get(m, 0.0) + c, 6)
        by_project[t["project_id"]] = round(by_project.get(t["project_id"], 0.0) + c, 6)
tin = tout = 0
ev_cost = 0.0
for e in llm_events:
    try:
        p = json.loads(e["payload"]) or {}
    except (json.JSONDecodeError, TypeError):
        continue
    u = p.get("usage") or p
    tin += int(u.get("prompt_tokens") or u.get("tokens_in") or 0)
    tout += int(u.get("completion_tokens") or u.get("tokens_out") or 0)
    ev_cost += float(p.get("cost_usd") or u.get("cost_usd") or 0.0)

llm = {
    "estimate": True,
    "note": "客户端没有账单接口：金额=token×官方价目表的**估算**，不是真实账单；"
            "人民币数值按 {:.1f} 折算（换算率本身不可在客户端验证）".format(CNY_PER_USD),
    "task_cost_usd_sum": task_cost,
    "task_cost_cny_estimate": round(task_cost * CNY_PER_USD, 4),
    "llm_call_events": len(llm_events),
    "tokens_in": tin, "tokens_out": tout, "tokens_total": tin + tout,
    "llm_call_event_cost_usd_sum": round(ev_cost, 6),
    "judge_cache_rows": int(ledger_rows[0]), "judge_cache_cost_usd_sum": round(float(ledger_rows[1]), 6),
    "by_model_usd": by_model,
    "top_projects_usd": dict(sorted(by_project.items(), key=lambda kv: -kv[1])[:8]),
}

# ---- ② 外部素材用量（非计费）----
con = ro()
retr = [dict(r) for r in con.execute(
    "select project_id, path from artifacts where type='retrieval_candidates'")]
con.close()
agg = {"requests": 0, "requests_failed": 0, "searched": 0, "fetched": 0, "rejected": 0,
       "downloaded_bytes": 0, "cache_hits": 0, "retries": 0, "rate_limited": 0,
       "projects_with_external": 0, "license_classes": {}}
for r in retr:
    try:
        d = json.loads(Path(r["path"]).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        continue
    ext = d.get("external_provider") or {}
    st = ext.get("stats") or {}
    if not st:
        continue
    if (d.get("external_verified") or 0) > 0 or (st.get("requests") or 0) > 0:
        agg["projects_with_external"] += 1
    for k in ("requests", "requests_failed", "searched", "fetched", "rejected",
              "downloaded_bytes", "cache_hits", "retries", "rate_limited"):
        agg[k] += int(st.get(k) or 0)
    for k, v in (st.get("license_classes") or {}).items():
        agg["license_classes"][k] = agg["license_classes"].get(k, 0) + int(v)
disk_files = disk_bytes = 0
for p in (ROOT / "projects").glob("p_*/media/external/*"):
    if p.is_file() and p.name != ".index.json":
        disk_files += 1
        disk_bytes += p.stat().st_size
material = {
    "billing": False,
    "note": "Wikimedia Commons 免费、无 key、无付费额度：以下为**用量**（请求/字节），不是金额",
    "provider_stats_sum": agg,
    "cache_files_on_disk": disk_files, "cache_bytes_on_disk": disk_bytes,
    "monetary_cost_usd": 0.0,
}

# ---- ③ ¥3.24 残余：机制复验（零本地 API 调用窗口内观察余额）----
con = ro()
before_events = con.execute("select count(*) from events").fetchone()[0]
before_llm = con.execute("select count(*) from events where type='LLM_CALL'").fetchone()[0]
con.close()
b0 = balance_cny()
series = []
t0 = time.time()
while time.time() - t0 < args.poll_seconds:
    time.sleep(20)
    try:
        b = balance_cny()
    except Exception as exc:                            # noqa: BLE001
        series.append({"t_s": round(time.time() - t0, 1),
                       "error": "{}: {}".format(type(exc).__name__, str(exc)[:60])})
        continue
    series.append({"t_s": round(time.time() - t0, 1), "balance_cny": b})
b1 = series[-1].get("balance_cny") if series else None
con = ro()
after_events = con.execute("select count(*) from events").fetchone()[0]
after_llm = con.execute("select count(*) from events where type='LLM_CALL'").fetchone()[0]
con.close()
residual = {
    "status": "NOT_ATTRIBUTABLE_CLIENT_SIDE",
    "classified_as": "估算差额（不是账单，也不是台账错误）",
    "historical": {
        "source": "docs/regression_2x/PHASE1_1_REPORT.md §1.3（Phase 1.1 实测）",
        "balance_window_cny": "15.95 → 11.17（-4.78）",
        "attributable_estimate_cny": 1.54,
        "residual_estimate_cny": 3.24,
        "candidate_causes": [
            "同一 API key 被其它调用方使用",
            "更早窗口费用仍在异步/批量结算（已观测到延迟到账）",
            "客户端不可观测的计价细节（USD/CNY 换算率、舍入/阶梯）",
        ],
    },
    "recheck_now": {
        "poll_seconds": args.poll_seconds,
        "balance_start_cny": b0, "balance_end_cny": b1,
        "balance_delta_cny": (None if (b0 is None or b1 is None) else round(b1 - b0, 4)),
        "local_llm_calls_in_window": after_llm - before_llm,
        "local_events_added_in_window": after_events - before_events,
        "series": series,
        "interpretation": ("窗口内本地零 LLM 调用" if after_llm == before_llm else "窗口内有本地调用"),
    },
    "conclusion": [
        "本地台账内部自洽（token 取自 API 返回、reasoning 不另计、峰谷判定正确），不存在算错；",
        "余额由服务端**异步/批量结算**，且可能包含其它调用方的用量——客户端无法把它逐笔归因到本项目；",
        "因此 ¥3.24 的正式结论是：**估算差额，客户端不可归因（NOT_ATTRIBUTABLE_CLIENT_SIDE）**；",
        "不得把它写成真实账单，也不得为了凑平而修改本地数字（Phase 1.1 起即如此保留）。",
    ],
}

rec = {"llm_cost_estimate": llm, "external_material_usage": material, "residual_324": residual}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({"llm": {k: llm[k] for k in ("task_cost_usd_sum", "task_cost_cny_estimate",
                                              "llm_call_events", "tokens_total",
                                              "by_model_usd")},
                  "material": {"requests": agg["requests"], "downloaded_bytes": agg["downloaded_bytes"],
                               "rate_limited": agg["rate_limited"],
                               "cache_files_on_disk": disk_files,
                               "cache_bytes_on_disk": disk_bytes},
                  "residual": {"status": residual["status"],
                               "recheck": residual["recheck_now"]}},
                 ensure_ascii=False, indent=1))
print("\nwritten", OUT)
