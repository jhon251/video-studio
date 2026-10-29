"""V2.1 Stage 8B.1 一次性验收（label-first 已落盘；一次运行；只报告）。

dev = 50 Claim（s8_pool_truth.json 为真值） + 11 构造样本（s8_dev2_samples.json）。
信号：Stage 7 extractor（语义未变）。聚合：claim_aggregation（四项结构修复版）。
"""
import json
import sqlite3
import sys
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
from video_studio.tools.evidence_pool import Pool  # noqa: E402
from video_studio.tools.evidence_signal import extract_signals  # noqa: E402
from video_studio.tools.claim_aggregation import aggregate_claim  # noqa: E402

PRICE_IN, PRICE_OUT = 0.27 / 1e6, 1.10 / 1e6
config = json.loads((ROOT / "config" / "config.yongsheng.json").read_text(encoding="utf-8"))


class CountingClient:
    def __init__(self, inner):
        self.inner, self.calls, self.tokens_in, self.tokens_out, self.errors = inner, 0, 0, 0, 0

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
        self.tokens_in += p_in
        self.tokens_out += max(int(r.get("tokens", 0) or 0) - p_in, 0)
        return r


client = CountingClient(DeepSeekClient(config["llm"]["deepseek"]))
router = Router(config["llm"], client)

import threading  # noqa: E402
_tls = threading.local()


class ThreadLocalDb:
    def __init__(self, path):
        self.path = path

    def _conn(self):
        if not hasattr(_tls, "conn") or getattr(_tls, "path", None) != self.path:
            _tls.conn = Database(self.path)
            _tls.path = self.path
        return _tls.conn

    def get_llm_judge_row(self, key):
        return self._conn().get_llm_judge_row(key)

    def put_llm_judge_row(self, rec):
        self._conn().put_llm_judge_row(rec)


class PoolView:
    def __init__(self, cid, clusters):
        self.claim_id, self.clusters = cid, clusters

    def stats(self):
        tiers = Counter(cl["source_tier"] for cl in self.clusters)
        n = len(self.clusters)
        return {"candidate_count": n, "cluster_count": n, "url_dedup_rate": 0.0,
                "content_dedup_collapse": 0.0, "duplicate_clusters": 0, "avg_members": 1.0,
                "total_dup_count": 0,
                "syndicated_clusters": sum(1 for c in self.clusters if c["syndicated"]),
                "independent_clusters": n,
                "independent_weight_sum": sum(c["independent_weight"] for c in self.clusters),
                "source_tiers": dict(tiers), "unknown_rate": tiers.get("unknown", 0) / n if n else 0.0}


db_path = ROOT / "projects" / "_drafts" / "llm_judge_s8b1.db"
if db_path.exists():
    db_path.unlink()
cache_db = ThreadLocalDb(db_path)
l1: dict = {}

_db = sqlite3.connect(str(ROOT / "projects" / "video_studio.db"))
_db.row_factory = sqlite3.Row
claims_text = {r["claim_id"]: r["text"] for r in _db.execute(
    "SELECT claim_id, text FROM claims WHERE project_id='p_f2215875dd49'")}

pools_data = json.loads((ROOT / "projects" / "_drafts" / "s8_claim_pools.json").read_text(encoding="utf-8"))
pool_truth = json.loads((ROOT / "projects" / "_drafts" / "s8_pool_truth.json").read_text(encoding="utf-8"))["labels"]
dev2 = json.loads((ROOT / "projects" / "_drafts" / "s8_dev2_samples.json").read_text(encoding="utf-8"))["samples"]

cases = []          # (cid, claim_text, pool_view, truth)
for cid, d in sorted(pools_data["pools"].items()):
    cases.append((cid, claims_text[cid], PoolView(cid, d["clusters"]), pool_truth[cid]["pool_truth"]))
for s in dev2:
    pool = Pool(s["id"], s["pool"])
    cases.append((s["id"], s["claim_text"], pool, s["truth"]))

tasks = []
for cid, claim_text, pool, _t in cases:
    for cl in pool.clusters:
        tasks.append((cid, claim_text, cl))
signals: dict = {}


def work(t):
    cid, claim_text, cl = t
    ev = {"url": cl.get("representative_url"), "title": cl.get("title", ""),
          "snippet": cl.get("snippet", ""), "text": cl.get("text", "")}
    return cid, cl["cluster_id"], extract_signals(claim_text, ev, router,
                                                  cache_db=cache_db, l1_cache=l1)


with ThreadPoolExecutor(max_workers=4) as ex:
    for cid, cl_id, sig in ex.map(work, tasks):
        signals.setdefault(cid, {})[cl_id] = sig

results = {}
for cid, claim_text, pool, truth in cases:
    results[cid] = aggregate_claim(claim_text, pool, signals.get(cid, {}))

# ---------- 指标 ----------
rows = [{"cid": cid, "truth": truth, "pred": results[cid]["state"],
         "r": results[cid]} for cid, _c, _p, truth in cases]
n = len(rows)
ok = sum(r["pred"] == r["truth"] for r in rows)
print(f"1. Claim-level accuracy: {ok}/{n} = {ok/n:.3f}")
print(f"   预测分布: {dict(Counter(r['pred'] for r in rows))}")
print(f"   真值分布: {dict(Counter(r['truth'] for r in rows))}")


def pr(state):
    tp = sum(1 for r in rows if r["truth"] == state and r["pred"] == state)
    pred = sum(1 for r in rows if r["pred"] == state)
    truth_n = sum(1 for r in rows if r["truth"] == state)
    return (tp / pred if pred else None), (tp / truth_n if truth_n else None)


for i, s in enumerate(("DIRECT_SUPPORT", "CONTRADICTS", "PARTIAL_SUPPORT",
                       "CONTEXT_ONLY", "NO_SUFFICIENT_EVIDENCE", "IRRELEVANT"), start=2):
    p_, r_ = pr(s)
    print(f"{i}. {s}: precision={p_ if p_ is None else round(p_,3)} "
          f"recall={r_ if r_ is None else round(r_,3)}")
crit_d = [r["cid"] for r in rows if r["truth"] in ("IRRELEVANT",)
          and r["pred"] == "DIRECT_SUPPORT"]
crit_c = [r["cid"] for r in rows if r["truth"] in ("IRRELEVANT",)
          and r["pred"] == "CONTRADICTS"]
print(f"8. CRITICAL: IRRELEVANT→DIRECT={len(crit_d)} {crit_d} | "
      f"IRRELEVANT→CONTRADICTS={len(crit_c)} {crit_c}")
num_contra = [r for r in rows if r["r"]["contradiction_records"]
              and any(x["scope"] == "number" for x in r["r"]["contradiction_records"])]
num_ok = sum(1 for r in num_contra if r["pred"] == "CONTRADICTS" and r["truth"] == "CONTRADICTS")
print(f"9. numeric conflict precision: {num_ok}/{len(num_contra)}")
temporal = [r for r in rows if r["r"]["conflict_records"]
            and any("时间" in x["resolution"] or x["scope"] == "temporal"
                    for x in r["r"]["conflict_records"])]
print(f"10. temporal conflict 消解案例: {[(r['cid'], r['truth'], r['pred']) for r in temporal]}")
qual = [r for r in rows if r["r"]["conflict_records"]
        and any(x["scope"] == "qualifier" for x in r["r"]["conflict_records"])]
print(f"11. qualifier conflict 消解案例: {[(r['cid'], r['truth'], r['pred']) for r in qual]}")
anch = sum(1 for r in rows if r["r"]["anchor_count"] > 0)
print(f"12. Anchor 满足率: {anch}/{n}")
comp_ok = [r["cid"] for r in rows if r["r"]["complementary_used"]
           and r["pred"] == "DIRECT_SUPPORT" and r["truth"] == "DIRECT_SUPPORT"]
print(f"13. complementary evidence 成功: {comp_ok}")
nse_n = sum(1 for r in rows if r["pred"] == "NO_SUFFICIENT_EVIDENCE")
print(f"14. NO_SUFFICIENT_EVIDENCE 触发率: {nse_n}/{n}")
prop0 = sum(1 for r in rows if r["r"]["relevant_clusters"] == 0)
print(f"15. proposition evidence = 0 的 Claim: {prop0}")
print(f"16. source independence: 有命题证据 claim 平均 union_weight "
      f"{sum(r['r']['union_weight'] for r in rows if r['r']['relevant_clusters']>0)/max(1,sum(1 for r in rows if r['r']['relevant_clusters']>0)):.2f}")
print(f"17. 误合并/漏合并影响: duplicate_clusters={sum(r['r']['duplicate_impact']['duplicate_clusters'] for r in rows)}")
print("18. 每类错误逐条根因：")
for r in rows:
    if r["pred"] != r["truth"]:
        print(f"   {r['cid']} truth={r['truth']} pred={r['pred']} reasons={r['r']['reasons']} "
              f"uncovered={r['r']['uncovered']} anchor={r['r']['anchor_count']} "
              f"conflicts={r['r']['conflict_keys']} contra={len(r['r']['contradiction_records'])}")

print(f"\n资源: API 调用 {client.calls} | token {client.tokens_in}/{client.tokens_out} | "
      f"费用 ${client.tokens_in*PRICE_IN + client.tokens_out*PRICE_OUT:.4f}")
fb = Counter((s.get("fallback_reason") or "ok") for sigs in signals.values() for s in sigs.values())
print(f"fallback: {dict(fb)}")

(ROOT / "projects" / "_drafts" / "r1_stage8b1_eval.json").write_text(
    json.dumps({"rows": rows,
                "results": {cid: {k: v for k, v in r.items() if k != "coverage_matrix"}
                            for cid, r in results.items()},
                "resources": {"calls": client.calls, "tokens_in": client.tokens_in,
                              "tokens_out": client.tokens_out,
                              "cost_usd_est": client.tokens_in * PRICE_IN + client.tokens_out * PRICE_OUT}},
               ensure_ascii=False, indent=2, default=str), encoding="utf-8")
print("\nwritten: projects/_drafts/r1_stage8b1_eval.json")
