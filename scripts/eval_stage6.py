"""V2.1 Stage 6 评估：dev 验证 + dev-only 四项消融 + 冻结 197 一次性验收。

- dev 消融：LLM 只调用一次/样本，用捕获的结构化字段本地重放 4 个开关变体（不重复调用 API）。
- 冻结验收：一次运行；对比 Rule / 4b / S5 / S6；完整指标与逐条错误清单。
- 只报告，不调参。
"""
import hashlib
import json
import re
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
from video_studio.tools.semantic_judge import judge_support  # noqa: E402
from video_studio.tools.llm_semantic_judge import cache_key as key_v1  # noqa: E402
import video_studio.tools.sufficiency_judge as SJ  # noqa: E402

LEVELS = ["DIRECT_SUPPORT", "PARTIAL_SUPPORT", "CONTEXT_ONLY", "IRRELEVANT", "CONTRADICTS"]
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


def load_dev():
    col = json.loads((ROOT / "projects" / "_drafts" / "s5_dev_v2_collection.json").read_text(encoding="utf-8"))
    labels = json.loads((ROOT / "projects" / "_drafts" / "s5_dev_v2_labels.json").read_text(encoding="utf-8"))["labels"]
    return [{"id": s["id"], "claim": s["claim_text"], "truth": s["truth"],
             "ev": s["evidence"]} for s in col["samples"]]


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


# S5 旧键（PROMPT_VERSION=sufficiency-judge-v1）
def key_s5_old(claim, ev):
    def norm(s):
        return re.sub(r"\s+", "", s or "")
    raw = "\x00".join([norm(claim), norm(ev.get("title", "")), norm(ev.get("snippet", "")),
                       norm((ev.get("text") or "")[:600]), "sufficiency-judge-v1",
                       "deepseek-chat"])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def aggregate(rows):
    n = len(rows)
    rule_acc = sum(r["rule"] == r["truth"] for r in rows) / n
    final_acc = sum(r["final"] == r["truth"] for r in rows) / n
    conf = Counter((r["truth"], r["final"]) for r in rows)
    pr = {}
    for l in LEVELS:
        tp = sum(1 for r in rows if r["truth"] == l and r["final"] == l)
        pred = sum(1 for r in rows if r["final"] == l)
        truth_n = sum(1 for r in rows if r["truth"] == l)
        pr[l] = ((tp / pred if pred else None), (tp / truth_n if truth_n else None))
    safety = {"irr_to_direct": sum(1 for r in rows if r["truth"] == "IRRELEVANT"
                                   and r["final"] == "DIRECT_SUPPORT"),
              "irr_to_contra": sum(1 for r in rows if r["truth"] == "IRRELEVANT"
                                   and r["final"] == "CONTRADICTS")}
    misses = [r for r in rows if r["final"] != r["truth"]]
    return {"n": n, "rule_acc": rule_acc, "final_acc": final_acc, "conf": conf, "pr": pr,
            "safety": safety, "misses": misses, "rows": rows}


def old_rule_claim_type(claim_text):
    """③ 消融用：Stage 5 旧口径（fiction→NARRATIVE；指/指的是→DEFINITION 封死）。"""
    prof = SJ._claim_profile(claim_text)
    if prof["question"]:
        return "QUESTION"
    if prof["step_def"] or ("指" in claim_text and any(
            m in claim_text for m in ("指的是", "是指", "所谓", "称为", "定义为"))):
        return "DEFINITION"
    if SJ._contrast_construction(claim_text):
        return "CONTRAST"
    if prof["rhetorical"]:
        return "RHETORICAL"
    if prof["fiction"]:
        return "NARRATIVE"
    return None


def dev_run_and_ablate(samples):
    """dev-only：每样本调用一次 LLM，用捕获字段重放 5 个开关变体。"""
    variants = {
        "ALL_ON": dict(SJ.DEFAULT_FLAGS),
        "OFF_decouple": {**SJ.DEFAULT_FLAGS, "decouple_contradict": False},
        "OFF_verify": {**SJ.DEFAULT_FLAGS, "verify_s4s5": False},
        "OFF_t2s": {**SJ.DEFAULT_FLAGS, "t2s": False},
    }
    results = {k: [] for k in variants}
    results["OFF_types"] = []
    captured = {}

    def work(s):
        rule = judge_support(s["claim"], s["ev"])
        quals = SJ._qualifier_requirements(SJ.t2s(s["claim"]))
        nums = [raw for _, _, raw in SJ._extract_numbers_corrected(SJ.t2s(s["claim"]))]
        nums += re.findall(r"(19|20)\d{2}", SJ.t2s(s["claim"]))
        system, user = SJ.build_prompt_v2(s["claim"], s["ev"], quals, nums)
        tier_cfg = (router.config.get("tiers", {}) or {}).get("F", {})
        model = tier_cfg.get("model", "deepseek-chat")
        res = client.complete(model, system, user, tier_cfg.get("max_tokens", 512))
        llm = SJ._extract_json(res.get("text", ""))
        SJ.validate_json(llm, SJ.OUTPUT_SCHEMA)
        return s, rule, llm

    with ThreadPoolExecutor(max_workers=4) as ex:
        captured = [(s, rule, llm) for s, rule, llm in ex.map(work, samples)]

    # 变体重放（纯确定性，主线程顺序执行，避免 monkeypatch 竞态）
    for s, rule, llm in captured:
        for vname in ("ALL_ON", "OFF_decouple", "OFF_verify", "OFF_t2s"):
            d = SJ._decide_v6(s["claim"], s["ev"], rule, llm, variants[vname])
            results[vname].append({**s, "rule": rule, "final": d["level"]})
    orig = SJ.rule_claim_type
    SJ.rule_claim_type = old_rule_claim_type
    try:
        for s, rule, llm in captured:
            d = SJ._decide_v6(s["claim"], s["ev"], rule, llm, SJ.DEFAULT_FLAGS)
            results["OFF_types"].append({**s, "rule": rule, "final": d["level"]})
    finally:
        SJ.rule_claim_type = orig

    print("\n===== dev72 四项消融（LLM 每样本仅调用一次，变体为确定性重放） =====")
    base = aggregate(results["ALL_ON"])["final_acc"]
    print(f"  ALL_ON dev 准确率: {base:.3f}")
    for vname in ("OFF_decouple", "OFF_verify", "OFF_types", "OFF_t2s"):
        a = aggregate(results[vname])
        print(f"  {vname}: {a['final_acc']:.3f}（Δ={a['final_acc']-base:+.3f}）")
    return aggregate(results["ALL_ON"])


def frozen_run(samples):
    cache_db = ThreadLocalDb(ROOT / "projects" / "_drafts" / "llm_judge_s6_frozen.db")
    p = ROOT / "projects" / "_drafts" / "llm_judge_s6_frozen.db"
    if p.exists():
        p.unlink()
    l1 = {}

    def work(s):
        rule = judge_support(s["claim"], s["ev"])
        res = SJ.judge_v2(s["claim"], s["ev"], router, rule, cache_db=cache_db, l1_cache=l1)
        return {**s, "rule": rule, "final": res["support_level"], "res": res}

    with ThreadPoolExecutor(max_workers=4) as ex:
        rows = [ex.submit(work, s).result() for s in samples]
    return rows


dev_a = dev_run_and_ablate(load_dev())
frozen_rows = frozen_run(load_frozen())
subsets = {"regression50": [r for r in frozen_rows if r["id"].startswith("RS-")],
           "blind121": [r for r in frozen_rows if r["id"].startswith("B")],
           "stress26": [r for r in frozen_rows if r["id"].startswith("CT-")]}
frozen_a = aggregate(frozen_rows)

print("\n===== 冻结 197 一次性验收（Stage 6，ALL_ON） =====")
for name, sub in [("regression50", subsets["regression50"]), ("blind121", subsets["blind121"]),
                  ("stress26", subsets["stress26"]), ("frozen197", frozen_rows)]:
    a = aggregate(sub)
    print(f"--- {name} n={a['n']} ---")
    print(f"  Rule {a['rule_acc']:.3f} | Stage6 {a['final_acc']:.3f}")
    for l in ("DIRECT_SUPPORT", "CONTRADICTS", "IRRELEVANT"):
        p_, r_ = a["pr"][l]
        print(f"  {l:<16} precision={p_ if p_ is None else round(p_,3)} "
              f"recall={r_ if r_ is None else round(r_,3)}")
    print(f"  CRITICAL: IRRELEVANT→DIRECT={a['safety']['irr_to_direct']} "
          f"IRRELEVANT→CONTRADICTS={a['safety']['irr_to_contra']}")

print("\n===== 合并混淆矩阵（truth × Stage6 final） =====")
print("truth\\final   " + "".join(f"{l[:4]:>8}" for l in LEVELS))
for t in LEVELS:
    print(f"{t[:14]:<14}" + "".join(f"{frozen_a['conf'][(t, p)]:>8}" for p in LEVELS))

# 三/四标签对比
db4b = Database(ROOT / "projects" / "_drafts" / "llm_judge_eval_real.db")
db5 = Database(ROOT / "projects" / "_drafts" / "llm_judge_s5_frozen.db")
acc = {"rule": 0, "v4b": 0, "s5": 0, "s6": 0}
for r in frozen_rows:
    if r["rule"] == r["truth"]:
        acc["rule"] += 1
    r4 = db4b.get_llm_judge_row(key_v1(r["claim"], r["ev"]))
    if (r4 or {}).get("llm_label") == r["truth"]:
        acc["v4b"] += 1
    r5 = db5.get_llm_judge_row(key_s5_old(r["claim"], r["ev"]))
    if (r5 or {}).get("llm_label") == r["truth"]:
        acc["s5"] += 1
    if r["final"] == r["truth"]:
        acc["s6"] += 1
print(f"\n===== 四标签对比（冻结 197） =====")
print(f"  Rule {acc['rule']}/197={acc['rule']/197:.3f} | 4b {acc['v4b']}/197={acc['v4b']/197:.3f} | "
      f"S5 {acc['s5']}/197={acc['s5']/197:.3f} | S6 {acc['s6']}/197={acc['s6']/197:.3f}")

print(f"\n===== 逐条错误清单（Stage6 未命中 {len(frozen_a['misses'])} 条） =====")
for m in frozen_a["misses"]:
    print(f"  {m['id']} truth={m['truth']} rule={m['rule']} final={m['final']} | "
          f"claim={m['claim'][:36]} | {(m['ev'].get('title') or '')[:30]} | "
          f"{(m['ev'].get('url') or '')[:46]} | {m['res'].get('reason','')[:60]}")

print(f"\n===== 资源统计 =====")
print(f"  API 调用: {client.calls} | token in/out: {client.tokens_in}/{client.tokens_out} | "
      f"费用估算: ${client.tokens_in*PRICE_IN + client.tokens_out*PRICE_OUT:.4f}")
fallback = Counter((r["res"].get("fallback_reason") or "ok") for r in frozen_rows)
print(f"  fallback: {dict(fallback)}")
lat = sorted(r["res"].get("latency_ms", 0) for r in frozen_rows if r["res"].get("latency_ms"))
if lat:
    print(f"  延迟 avg={sum(lat)/len(lat):.0f}ms p50={lat[len(lat)//2]}ms p95={lat[int(len(lat)*0.95)]}ms")
print(f"  dev/frozen 分差: {abs(dev_a['final_acc'] - frozen_a['final_acc']):.3f}")
print(f"  缓存命中率: 0（单遍运行，机制已由 4b 二遍验证）")

def _ser(a):
    out = {}
    for k, v in a.items():
        if k == "rows":
            continue
        if isinstance(v, Counter):
            out[k] = {f"{t}->{p}": n for (t, p), n in v.items()} if k == "conf" else dict(v)
        elif isinstance(v, list):
            out[k] = v
        else:
            out[k] = v
    return out


out = {"frozen": _ser(frozen_a),
       "resources": {"calls": client.calls, "tokens_in": client.tokens_in,
                     "tokens_out": client.tokens_out,
                     "cost_usd_est": client.tokens_in * PRICE_IN + client.tokens_out * PRICE_OUT}}
(ROOT / "projects" / "_drafts" / "r1_stage6_eval.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
print("\nwritten: projects/_drafts/r1_stage6_eval.json")
