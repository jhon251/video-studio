"""V2.1 阶段 4 真实 LLM 评估驱动（197 冻结样本：50 回归 + 121 盲测 + 26 压力）。

- 不修改任何生产模块/测试集；仅评估与统计。
- 第一遍冷跑真实 DeepSeek；第二遍验证缓存（100% 命中，不再调用）。
- 输出：Rule/LLM/Final 三准确率（分集）、最终标签混淆矩阵（分集+合并）、
  DIRECT/CONTRADICTS/IRRELEVANT precision+recall、Rule→LLM 改对/改错清单、
  压力集逐条、调用次数/token/延迟/缓存命中率/费用估算。
"""
import json
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from video_studio.core.env import load_env  # noqa: E402
load_env(ROOT / ".env")
from video_studio.db.schema import Database  # noqa: E402
from video_studio.llm.router import DeepSeekClient, Router  # noqa: E402
from video_studio.tools.semantic_judge import judge_support  # noqa: E402
from video_studio.tools.llm_semantic_judge import judge_llm  # noqa: E402

LEVELS = ["DIRECT_SUPPORT", "PARTIAL_SUPPORT", "CONTEXT_ONLY", "IRRELEVANT", "CONTRADICTS"]
# DeepSeek deepseek-chat 定价（$/1M token，作为费用估算上限：全部按未命中缓存计）
PRICE_IN = 0.27 / 1e6
PRICE_OUT = 1.10 / 1e6

config = json.loads((ROOT / "config" / "config.yongsheng.json").read_text(encoding="utf-8"))


class CountingClient:
    """评估侧计数代理：统计真实 API 调用次数与 token（不改生产代码）。"""

    def __init__(self, inner: DeepSeekClient):
        self.inner = inner
        self.calls = 0
        self.tokens_in = 0
        self.tokens_out = 0
        self.errors = 0

    @property
    def available(self):
        return self.inner.available

    def complete(self, model, system, user, max_tokens):
        self.calls += 1
        try:
            r = self.inner.complete(model, system, user, max_tokens)
        except Exception:
            self.errors += 1
            raise
        p_in = int(r.get("prompt_tokens", 0) or 0)
        p_out = max(int(r.get("tokens", 0) or 0) - p_in, 0)
        self.tokens_in += p_in
        self.tokens_out += p_out
        return r


client = CountingClient(DeepSeekClient(config["llm"]["deepseek"]))
router = Router(config["llm"], client)
db_path = ROOT / "projects" / "_drafts" / "llm_judge_eval_real.db"
if db_path.exists():
    db_path.unlink()          # 清掉上一轮降级运行的回退缓存行（键相同会误命中）
Database(db_path)             # 主线程建表

import threading  # noqa: E402
_tls = threading.local()


class ThreadLocalDb:
    """评估侧：每线程独立 SQLite 连接（WAL 多连接安全），不改生产代码。"""

    def __init__(self, path):
        self.path = path

    def _conn(self):
        if not hasattr(_tls, "conn"):
            _tls.conn = Database(self.path)
        return _tls.conn

    def get_llm_judge_row(self, key):
        return self._conn().get_llm_judge_row(key)

    def put_llm_judge_row(self, rec):
        self._conn().put_llm_judge_row(rec)


db = ThreadLocalDb(db_path)

reg = json.loads((ROOT / "tests" / "data" / "evidence_regression_r1.json").read_text(encoding="utf-8"))["samples"]
col = json.loads((ROOT / "projects" / "_drafts" / "r1_blind_collection.json").read_text(encoding="utf-8"))
blind_labels = json.loads((ROOT / "projects" / "_drafts" / "r1_blind_labels.json").read_text(encoding="utf-8"))["labels"]
stress = json.loads((ROOT / "tests" / "data" / "contradicts_stress.json").read_text(encoding="utf-8"))["samples"]

sets: dict = {"regression50": [], "blind121": [], "stress26": []}
for s in reg:
    sets["regression50"].append({"id": s["id"], "claim": s["claim_text"], "truth": s["truth_label"],
                                 "ev": s["evidence"]})
idx = 0
for rec in col["claims"]:
    for r in rec["results"]:
        idx += 1
        sets["blind121"].append({"id": f"B{idx:03d}", "claim": rec["claim_text"],
                                 "truth": blind_labels[str(idx)],
                                 "ev": {"title": r["title"], "snippet": r["snippet"],
                                        "text": r["page"].get("text", ""), "url": r["url"]}})
for s in stress:
    sets["stress26"].append({"id": s["id"], "claim": s["claim_text"], "truth": s["truth_label"],
                             "ev": s["evidence"]})


def evaluate(l1: dict) -> dict:
    rows = []

    def work(s):
        rule = judge_support(s["claim"], s["ev"])
        res = judge_llm(s["claim"], s["ev"], router, rule, cache_db=db, l1_cache=l1)
        return {**s, "rule": rule, "llm": res["llm_label"], "final": res["support_level"],
                "res": res}

    with ThreadPoolExecutor(max_workers=4) as ex:
        for set_name, samples in sets.items():
            for s in samples:
                rows.append(ex.submit(work, s).result())

    out = {"rows": rows, "per_set": {}, "combined": {}}
    for set_name in sets:
        subset = [r for r in rows if r["id"].startswith(set_name[:2]) or True]
        # 按 id 归属分集
    by_set = {"regression50": [r for r in rows if r["id"].startswith("RS-")],
              "blind121": [r for r in rows if r["id"].startswith("B")],
              "stress26": [r for r in rows if r["id"].startswith("CT-")]}
    for name, subset in by_set.items():
        out["per_set"][name] = aggregate(subset)
    out["combined"] = aggregate(rows)
    out["client"] = {"calls": client.calls, "tokens_in": client.tokens_in,
                     "tokens_out": client.tokens_out, "errors": client.errors,
                     "cost_usd_est": client.tokens_in * PRICE_IN + client.tokens_out * PRICE_OUT}
    out["cache_hit"] = sum(1 for r in rows if r["res"].get("cache_hit"))
    out["fallback"] = Counter((r["res"].get("fallback_reason") or "ok") for r in rows)
    return out


def aggregate(rows):
    n = len(rows)
    rule_ok = sum(r["rule"] == r["truth"] for r in rows)
    llm_ok = sum(r["llm"] == r["truth"] for r in rows)
    final_ok = sum(r["final"] == r["truth"] for r in rows)
    conf = Counter((r["truth"], r["final"]) for r in rows)
    fixes, breaks = [], []
    for r in rows:
        if r["rule"] != r["truth"] and r["llm"] == r["truth"]:
            fixes.append(r)
        if r["rule"] == r["truth"] and r["llm"] != r["truth"]:
            breaks.append(r)
    lat = sorted(r["res"].get("latency_ms", 0) for r in rows if r["res"].get("latency_ms"))
    return {"n": n, "rule_acc": rule_ok / n, "llm_acc": llm_ok / n, "final_acc": final_ok / n,
            "conf": conf, "fixes": fixes, "breaks": breaks,
            "precision": {l: prec_recall(rows, l)[0] for l in LEVELS},
            "recall": {l: prec_recall(rows, l)[1] for l in LEVELS},
            "lat": {"avg": sum(lat) / len(lat) if lat else None,
                    "p50": lat[len(lat) // 2] if lat else None,
                    "p95": lat[int(len(lat) * 0.95)] if lat else None}}


def prec_recall(rows, level):
    tp = sum(1 for r in rows if r["truth"] == level and r["final"] == level)
    pred = sum(1 for r in rows if r["final"] == level)
    truth_n = sum(1 for r in rows if r["truth"] == level)
    return (tp / pred if pred else None), (tp / truth_n if truth_n else None)


p1 = evaluate(l1={})
p2 = evaluate(l1={})

for label, p in (("第一遍（冷）", p1), ("第二遍（缓存）", p2)):
    print(f"\n{'='*70}\n{label}  client.calls={p['client']['calls']} "
          f"cache_hit={p['cache_hit']}/{p['combined']['n']}")
    for name in ("regression50", "blind121", "stress26", "combined"):
        a = p["per_set"].get(name) or p["combined"]
        print(f"--- {name} n={a['n']} ---")
        print(f"  Rule {a['rule_acc']:.3f} | LLM {a['llm_acc']:.3f} | Final {a['final_acc']:.3f}")
        print(f"  precision: " + " ".join(
            f"{l}={a['precision'][l] if a['precision'][l] is None else round(a['precision'][l],3)}"
            for l in ("DIRECT_SUPPORT", "CONTRADICTS", "IRRELEVANT")))
        print(f"  recall:    " + " ".join(
            f"{l}={a['recall'][l] if a['recall'][l] is None else round(a['recall'][l],3)}"
            for l in ("DIRECT_SUPPORT", "CONTRADICTS", "IRRELEVANT")))
        print(f"  Rule→LLM 改对 {len(a['fixes'])} 条 | 改错 {len(a['breaks'])} 条")
        print(f"  延迟 avg={a['lat']['avg']}ms p50={a['lat']['p50']}ms p95={a['lat']['p95']}ms")

print("\n\n===== 合并混淆矩阵（truth × final，第一遍） =====")
print("truth\\final   " + "".join(f"{l[:4]:>8}" for l in LEVELS))
conf = p1["combined"]["conf"]
for t in LEVELS:
    print(f"{t[:14]:<14}" + "".join(f"{conf[(t, p)]:>8}" for p in LEVELS))

print("\n===== Rule→LLM 改错清单（Rule 正确、LLM 改错） =====")
seen = set()
for r in p1["combined"]["breaks"]:
    key = (r["id"], r["truth"], r["rule"], r["llm"])
    if key in seen:
        continue
    seen.add(key)
    print(f"  {r['id']} truth={r['truth']} rule={r['rule']} llm={r['llm']} | "
          f"claim={r['claim'][:36]} | {(r['ev'].get('title') or '')[:34]} | {(r['ev'].get('url') or '')[:50]}")

print("\n===== Rule→LLM 改对清单（Rule 错误、LLM 改对） =====")
seen = set()
for r in p1["combined"]["fixes"]:
    key = (r["id"], r["truth"], r["rule"], r["llm"])
    if key in seen:
        continue
    seen.add(key)
    print(f"  {r['id']} truth={r['truth']} rule={r['rule']} llm={r['llm']} | "
          f"claim={r['claim'][:36]} | {(r['ev'].get('title') or '')[:34]} | {(r['ev'].get('url') or '')[:50]}")

print("\n===== 26 条 CONTRADICTS 压力集逐条（第一遍） =====")
for r in p1["per_set"]["stress26"]["rows"]:
    print(f"  {r['id']} [{r['ev'].get('scenario', '?')}] truth={r['truth']} rule={r['rule']} "
          f"llm={r['llm']} final={r['final']} {'OK' if r['final'] == r['truth'] else 'X'}")

print(f"\n===== 资源统计（第一遍） =====")
print(f"  API 调用次数: {p1['client']['calls']}（含重试） | 客户端错误: {p1['client']['errors']}")
print(f"  token: in={p1['client']['tokens_in']} out={p1['client']['tokens_out']}")
print(f"  费用估算（按未命中缓存定价上限）: ${p1['client']['cost_usd_est']:.4f}")
print(f"  回退分布: {dict(p1['fallback'])}")
print(f"  缓存命中率: {p1['cache_hit']}/{p1['combined']['n']}")

out = {"pass1": {k: (dict(v) if isinstance(v, Counter) else v) for k, v in p1.items() if k != "rows"},
       "pass1_rows": p1["rows"]}
(ROOT / "projects" / "_drafts" / "r1_llm_real_eval.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
print("\nwritten: projects/_drafts/r1_llm_real_eval.json")
