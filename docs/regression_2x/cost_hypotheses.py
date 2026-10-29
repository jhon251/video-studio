"""Phase 1.1: test the two remaining cost-gap hypotheses.

H1 peak/off-peak band misclassification (2x factor)
H2 reasoning/thinking tokens billed but missing from my cost formula

Usage: python docs/regression_2x\cost_hypotheses.py
"""
import datetime as dt
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
from video_studio.llm.router import DEFAULT_PRICING, compute_cost, price_band  # noqa: E402

con_db = ROOT / "projects" / "video_studio.db"
import sqlite3  # noqa: E402
con = sqlite3.connect(str(con_db))
con.row_factory = sqlite3.Row

print("=== H1: 逐调用时间 → UTC 时段，并按两种时段重算费用 ===")
rows = []
for p in ("p_314efdfbbeb2", "p_e7a8b8020fb1", "p_8f054c227bd4"):
    for r in con.execute("select ts,payload from events where project_id=? and type='LLM_CALL'", (p,)):
        d = json.loads(r["payload"])
        rows.append((float(r["ts"]), d))
con.close()


def band_of(ts):
    utc = dt.datetime.fromtimestamp(ts, dt.timezone.utc)
    return utc, ("peak" if utc.weekday() < 5 and (1 <= utc.hour < 4 or 6 <= utc.hour < 10)
                 else "off_peak")


bands = {}
for ts, d in rows:
    utc, b = band_of(ts)
    bands[b] = bands.get(b, 0) + 1
print("  时段分布（按我的规则）:", bands)
if rows:
    utc0 = band_of(min(r[0] for r in rows))[0]
    utc1 = band_of(max(r[0] for r in rows))[0]
    print("  最早 {} / 最晚 {} (UTC)".format(utc0.isoformat(), utc1.isoformat()))


def cost_with_band(d, band):
    model = d.get("model")
    table = DEFAULT_PRICING.get(model)
    if not table:
        return 0.0, "unknown"
    p = table[band]
    hit = int(d.get("cache_hit_tokens") or 0)
    miss = int(d.get("cache_miss_tokens") or 0)
    out = int(d.get("completion_tokens") or 0)
    return (hit * p["cache_hit"] + miss * p["cache_miss"] + out * p["output"]) / 1e6, band


cur = sum(float(d.get("cost_usd") or 0) for _, d in rows)
alt = sum(cost_with_band(d, "peak" if d.get("price_band") == "off_peak" else "off_peak")[0]
          for _, d in rows)
print("  台账现值 ${:.4f} | 若时段判断整体反了 ${:.4f}（×2 关系）".format(cur, alt))

print("\n=== H1b: reasoning tokens 是否在 completion_tokens 之内 ===")
tot_reason = sum(int(d.get("reasoning_tokens") or 0) for _, d in rows)
tot_comp = sum(int(d.get("completion_tokens") or 0) for _, d in rows)
print("  台账合计 completion_tokens={} reasoning_tokens={} prompt_tokens={}".format(
    tot_comp, tot_reason, sum(int(d.get("prompt_tokens") or 0) for _, d in rows)))
if tot_reason > tot_comp:
    print("  → reasoning 超出 completion：说明 completion 未含 reasoning，费用被低估")
else:
    print("  → reasoning ⊆ completion：公式未漏算 reasoning")

print("\n=== H2: 真实调用一次，打印完整 usage（v4-pro，少量 token）===")
for ln in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if ln.strip().startswith("DEEPSEEK_API_KEY="):
        os.environ["DEEPSEEK_API_KEY"] = ln.split("=", 1)[1].strip()
body = json.dumps({"model": "deepseek-v4-pro",
                   "messages": [{"role": "user", "content": "1+1=? 只回答数字"}],
                   "max_tokens": 256}).encode()
req = urllib.request.Request("https://api.deepseek.com/chat/completions", data=body,
                             headers={"Authorization": "Bearer " + os.environ["DEEPSEEK_API_KEY"],
                                      "Content-Type": "application/json"})
t0 = time.perf_counter()
with urllib.request.urlopen(req, timeout=120) as r:
    payload = json.loads(r.read().decode())
el = (time.perf_counter() - t0) * 1000
print("  latency {:.0f}ms".format(el))
print("  usage:", json.dumps(payload.get("usage"), ensure_ascii=False))
u = payload.get("usage", {})
ct = int(u.get("completion_tokens") or 0)
rt = int((u.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0)
print("  completion_tokens={} reasoning_tokens={} → reasoning {} completion".format(
    ct, rt, "⊆" if rt <= ct else "⊄"))
print("  该次调用我的计费=${:.6f}（v4-pro, {}）".format(
    compute_cost("deepseek-v4-pro", {"completion_tokens": ct,
                                     "cache_hit_tokens": u.get("prompt_cache_hit_tokens", 0),
                                     "cache_miss_tokens": u.get("prompt_cache_miss_tokens",
                                                                u.get("prompt_tokens", 0))})[0],
    price_band()))
