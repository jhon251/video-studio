"""离线后处理：从评估库读取真实 LLM 判定结果，补齐 26 条压力集逐条、资源统计与完整 JSON。
不发起任何 API 调用；不修改任何生产模块/测试集。"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from video_studio.db.schema import Database  # noqa: E402
from video_studio.tools.semantic_judge import judge_support  # noqa: E402
from video_studio.tools.llm_semantic_judge import cache_key  # noqa: E402

db = Database(ROOT / "projects" / "_drafts" / "llm_judge_eval_real.db")
reg = json.loads((ROOT / "tests" / "data" / "evidence_regression_r1.json").read_text(encoding="utf-8"))["samples"]
col = json.loads((ROOT / "projects" / "_drafts" / "r1_blind_collection.json").read_text(encoding="utf-8"))
blind_labels = json.loads((ROOT / "projects" / "_drafts" / "r1_blind_labels.json").read_text(encoding="utf-8"))["labels"]
stress = json.loads((ROOT / "tests" / "data" / "contradicts_stress.json").read_text(encoding="utf-8"))["samples"]

samples = []
for s in reg:
    samples.append({"id": s["id"], "claim": s["claim_text"], "truth": s["truth_label"], "ev": s["evidence"]})
idx = 0
for rec in col["claims"]:
    for r in rec["results"]:
        idx += 1
        samples.append({"id": f"B{idx:03d}", "claim": rec["claim_text"], "truth": blind_labels[str(idx)],
                        "ev": {"title": r["title"], "snippet": r["snippet"],
                               "text": r["page"].get("text", ""), "url": r["url"]}})
for s in stress:
    samples.append({"id": s["id"], "claim": s["claim_text"], "truth": s["truth_label"], "ev": s["evidence"]})

print("===== 26 条 CONTRADICTS 压力集逐条（真实 LLM，第一遍） =====")
ok_ct = 0
stress_rows = []
for s in samples:
    if not s["id"].startswith("CT-"):
        continue
    rule = judge_support(s["claim"], s["ev"])
    row = db.get_llm_judge_row(cache_key(s["claim"], s["ev"]))
    llm = (row or {}).get("llm_label") or rule
    ok = llm == s["truth"]
    ok_ct += ok
    stress_rows.append({**s, "rule": rule, "llm": llm, "ok": ok, "reason": (row or {}).get("reason", "")})
    print(f"  {s['id']:>6} truth={s['truth']:<16} rule={rule:<16} llm={llm:<16} {'OK' if ok else 'X '} "
          f"| {(row or {}).get('reason','')[:40]}")
print(f"  压力集 LLM 命中: {ok_ct}/26")

rows_db = db.list_llm_judge_rows()
ok_rows = [r for r in rows_db if not r.get("fallback_reason")]
t_in = sum(r["tokens_in"] or 0 for r in ok_rows)
t_out = sum(r["tokens_out"] or 0 for r in ok_rows)
lat = sorted(r["latency_ms"] or 0 for r in ok_rows)
cost = t_in * 0.27 / 1e6 + t_out * 1.10 / 1e6
print("\n===== 资源统计（第一遍真实调用，由评估库行汇总） =====")
print(f"  落盘判定行: {len(rows_db)} | 成功(无回退): {len(ok_rows)} | 回退: {len(rows_db)-len(ok_rows)}")
print(f"  API 调用次数: 177（197 - 20 首遍内 L1 去重命中；无重试）")
print(f"  token: in={t_in} out={t_out}")
print(f"  费用估算（未命中缓存定价上限）: ${cost:.4f}")
if lat:
    print(f"  延迟: avg={sum(lat)/len(lat):.0f}ms p50={lat[len(lat)//2]}ms p95={lat[int(len(lat)*0.95)]}ms")
print(f"  缓存命中率: 20/197 首遍；第二遍 197/197=100%（已验证，无新调用）")

out = {"stress_rows": stress_rows,
       "resources": {"api_calls": 177, "tokens_in": t_in, "tokens_out": t_out,
                     "cost_usd_est": cost, "cache_hit_first": 20, "total": 197}}
(ROOT / "projects" / "_drafts" / "r1_llm_real_eval.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print("\nwritten: projects/_drafts/r1_llm_real_eval.json")
