"""V2.1 Stage 7：EvidenceSignal 前置验收（④ 一次性运行：信号 dev 72 + 冻结 197）。

- 只测信号，不测聚合；不实现 Pool/Coverage/聚合；不接生产链。
- 指标：topic/prop/s/o/p 各字段准确率；s2&s3 对 topic=false 样本的假阳率；
  contradiction recall/precision；scope 准确率；LLM 限定词/数字打分与规则 oracle 的一致率；
  CRITICAL（topic=false 且 cand=true）；资源统计。
"""
import json
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
from video_studio.tools.evidence_signal import extract_signals  # noqa: E402

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


def load_signal_dev():
    col = json.loads((ROOT / "projects" / "_drafts" / "s5_dev_v2_collection.json").read_text(encoding="utf-8"))
    labels = json.loads((ROOT / "tests" / "data" / "evidence_signal_dev.json").read_text(encoding="utf-8"))["labels"]
    return [{"id": s["id"], "claim": s["claim_text"], "truth": s["truth"],
             "truth_sig": labels[s["id"]], "ev": s["evidence"]} for s in col["samples"]]


def load_frozen():
    reg = json.loads((ROOT / "tests" / "data" / "evidence_regression_r1.json").read_text(encoding="utf-8"))["samples"]
    col = json.loads((ROOT / "projects" / "_drafts" / "r1_blind_collection.json").read_text(encoding="utf-8"))
    labels = json.loads((ROOT / "projects" / "_drafts" / "r1_blind_labels.json").read_text(encoding="utf-8"))["labels"]
    stress = json.loads((ROOT / "tests" / "data" / "contradicts_stress.json").read_text(encoding="utf-8"))["samples"]
    out = []
    for s in reg:
        out.append({"id": s["id"], "claim": s["claim_text"], "truth": s["truth_label"], "ev": s["evidence"]})
    i = 0
    for rec in col["claims"]:
        for r in rec["results"]:
            i += 1
            out.append({"id": f"B{i:03d}", "claim": rec["claim_text"], "truth": labels[str(i)],
                        "ev": {"title": r["title"], "snippet": r["snippet"],
                               "text": r["page"].get("text", ""), "url": r["url"]}})
    for s in stress:
        out.append({"id": s["id"], "claim": s["claim_text"], "truth": s["truth_label"], "ev": s["evidence"]})
    return out


def run(samples, db_path):
    if Path(db_path).exists():
        Path(db_path).unlink()
    cache_db = ThreadLocalDb(db_path)
    l1 = {}

    def work(s):
        return {**s, "sig": extract_signals(s["claim"], s["ev"], router, cache_db=cache_db, l1_cache=l1)}

    with ThreadPoolExecutor(max_workers=4) as ex:
        return [ex.submit(work, s).result() for s in samples]


def eval_dev(rows):
    n = len(rows)
    f = {"topic": 0, "prop": 0, "s": 0, "o": 0, "p": 0}
    for r in rows:
        g = r["sig"]
        t = r["truth_sig"]
        if g["topic_relevance"] == t["topic"]:
            f["topic"] += 1
        if g["proposition_relevance"] == t["prop"]:
            f["prop"] += 1
        if g["subject_match"] == t["s"]:
            f["s"] += 1
        if g["object_match"] == t["o"]:
            f["o"] += 1
        if g["predicate_match"] == t["p"]:
            f["p"] += 1
    topic_false = [r for r in rows if not r["truth_sig"]["topic"]]
    s2s3_fp = [r for r in topic_false if r["sig"]["subject_match"] and r["sig"]["object_match"]
               and r["sig"]["predicate_match"]]
    cand_true = [r for r in rows if r["truth_sig"]["cand"]]
    cand_recall = sum(1 for r in cand_true if r["sig"]["contradiction_candidate"]) / len(cand_true)
    cand_fp = [r for r in rows if not r["truth_sig"]["cand"] and r["sig"]["contradiction_candidate"]]
    cand_prec = len(cand_true) / (len(cand_true) + len(cand_fp))
    scope_ok = sum(1 for r in cand_true if r["sig"]["contradiction_scope"] == r["truth_sig"]["scope"])
    crit = [r for r in topic_false if r["sig"]["contradiction_candidate"]]
    return {"n": n, "field_acc": {k: v / n for k, v in f.items()},
            "s2s3_fp_on_topicfalse": len(s2s3_fp),
            "topic_false_n": len(topic_false),
            "cand_recall": cand_recall, "cand_precision": cand_prec,
            "scope_acc": scope_ok / len(cand_true),
            "critical_cand_on_topicfalse": len(crit)}


def eval_frozen(rows):
    n = len(rows)
    irr = [r for r in rows if r["truth"] == "IRRELEVANT"]
    cont = [r for r in rows if r["truth"] == "CONTRADICTS"]
    s2s3_fp = [r for r in irr if r["sig"]["subject_match"] and r["sig"]["object_match"]
               and r["sig"]["predicate_match"]]
    cand_recall = sum(1 for r in cont if r["sig"]["contradiction_candidate"]) / len(cont)
    cand_fp = [r for r in rows if r["truth"] != "CONTRADICTS" and r["sig"]["contradiction_candidate"]]
    cand_prec = len(cont) / (len(cont) + len(cand_fp))
    crit = [r for r in irr if r["sig"]["contradiction_candidate"]]
    topic_fp = [r for r in irr if r["sig"]["topic_relevance"]]
    # LLM 打分 vs 规则 oracle 一致率
    agree = tot = 0
    for r in rows:
        g = r["sig"]
        for k, v in (g.get("qualifier_match") or {}).items():
            tot += 1
            agree += bool((g.get("llm_qualifier") or {}).get(k)) == bool(v)
        for k, v in (g.get("numeric_match") or {}).items():
            tot += 1
            agree += bool((g.get("llm_numbers") or {}).get(k)) == bool(v)
    return {"n": n, "irrelevant_n": len(irr), "s2s3_fp_on_irrelevant": len(s2s3_fp),
            "cand_recall": cand_recall, "cand_precision": cand_prec,
            "cand_fp_list": [(r["id"], r["truth"]) for r in cand_fp],
            "critical_cand_on_irrelevant": len(crit),
            "topic_fp_on_irrelevant": len(topic_fp),
            "llm_oracle_agree": agree / tot if tot else None, "oracle_items": tot}


print("===== Stage 7 前置验收 =====")
dev_rows = run(load_signal_dev(), ROOT / "projects" / "_drafts" / "llm_judge_s7_dev.db")
d = eval_dev(dev_rows)
print("\n--- 信号 dev 72 ---")
print(f"  字段准确率: { {k: round(v, 3) for k, v in d['field_acc'].items()} }")
print(f"  s2&s3 假阳（topic=false 上）: {d['s2s3_fp_on_topicfalse']}/{d['topic_false_n']}")
print(f"  contradiction recall={d['cand_recall']:.3f} precision={d['cand_precision']:.3f} "
      f"scope_acc={d['scope_acc']:.3f}")
print(f"  CRITICAL（topic=false 且 cand=true）: {d['critical_cand_on_topicfalse']}")

frozen_rows = run(load_frozen(), ROOT / "projects" / "_drafts" / "llm_judge_s7_frozen.db")
fz = eval_frozen(frozen_rows)
print("\n--- 冻结 197（信号级，一次性） ---")
print(f"  s2&s3 假阳（IRRELEVANT-truth {fz['irrelevant_n']} 上）: {fz['s2s3_fp_on_irrelevant']}")
print(f"  contradiction recall={fz['cand_recall']:.3f} precision={fz['cand_precision']:.3f}")
print(f"  cand 误报清单: {fz['cand_fp_list']}")
print(f"  CRITICAL（IRRELEVANT-truth 且 cand=true）: {fz['critical_cand_on_irrelevant']}")
print(f"  topic 假阳（IRRELEVANT-truth 上）: {fz['topic_fp_on_irrelevant']}")
print(f"  LLM 打分 vs 规则 oracle 一致率: {fz['llm_oracle_agree']}（{fz['oracle_items']} 项）")

lat = sorted(r["sig"].get("latency_ms", 0) for r in dev_rows + frozen_rows if r["sig"].get("latency_ms"))
print(f"\n--- 资源 ---")
print(f"  API 调用: {client.calls} | token in/out: {client.tokens_in}/{client.tokens_out} | "
      f"费用: ${client.tokens_in*PRICE_IN + client.tokens_out*PRICE_OUT:.4f}")
print(f"  延迟 avg={sum(lat)/len(lat):.0f}ms p50={lat[len(lat)//2]}ms p95={lat[int(len(lat)*0.95)]}ms")
fb = Counter((r["sig"].get("fallback_reason") or "ok") for r in frozen_rows)
print(f"  fallback: {dict(fb)}")

out = {"dev": d, "frozen": fz,
       "resources": {"calls": client.calls, "tokens_in": client.tokens_in,
                     "tokens_out": client.tokens_out,
                     "cost_usd_est": client.tokens_in * PRICE_IN + client.tokens_out * PRICE_OUT}}
(ROOT / "projects" / "_drafts" / "r1_stage7_eval.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
print("\nwritten: projects/_drafts/r1_stage7_eval.json")
