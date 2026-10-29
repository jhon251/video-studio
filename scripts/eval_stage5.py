"""V2.1 Stage 5 评估：dev 验证（含 S1–S7 拒绝计数与消融）+ 冻结 197 一次性验收。

- Rule = semantic_judge（冻结）；Stage4b = 4b LLM 标签（读 4b 评估库）；Stage5 = sufficiency_judge。
- 安全方向错误检查：IRRELEVANT→DIRECT / IRRELEVANT→CONTRADICTS 必须为 0。
- 只报告，不调参；失败即停止。
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
from video_studio.tools.llm_semantic_judge import cache_key as cache_key_v1  # noqa: E402
from video_studio.tools.sufficiency_judge import judge_v2  # noqa: E402

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


# ---------- 载入样本 ----------
def load_dev():
    col = json.loads((ROOT / "projects" / "_drafts" / "s5_dev_collection.json").read_text(encoding="utf-8"))
    labels = json.loads((ROOT / "projects" / "_drafts" / "s5_dev_labels.json").read_text(encoding="utf-8"))["labels"]
    out, i = [], 0
    for rec in col["claims"]:
        for r in rec["results"]:
            i += 1
            out.append({"id": f"D{i:03d}", "claim": rec["claim_text"], "truth": labels[f"D{i:03d}"],
                        "ev": {"title": r["title"], "snippet": r["snippet"],
                               "text": r["page"].get("text", ""), "url": r["url"]}})
    return out


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


def run_set(name, samples, cache_db, l1):
    rows = []

    def work(s):
        rule = judge_support(s["claim"], s["ev"])
        res = judge_v2(s["claim"], s["ev"], router, rule, cache_db=cache_db, l1_cache=l1)
        return {**s, "rule": rule, "llm": res["support_level"], "res": res}

    with ThreadPoolExecutor(max_workers=4) as ex:
        for s in samples:
            rows.append(ex.submit(work, s).result())
    return rows


def aggregate(rows, tag):
    n = len(rows)
    rule_acc = sum(r["rule"] == r["truth"] for r in rows) / n
    llm_acc = sum(r["llm"] == r["truth"] for r in rows) / n
    conf = Counter((r["truth"], r["llm"]) for r in rows)
    fixes = [r for r in rows if r["rule"] != r["truth"] and r["llm"] == r["truth"]]
    breaks = [r for r in rows if r["rule"] == r["truth"] and r["llm"] != r["truth"]]
    pr = {}
    for l in LEVELS:
        tp = sum(1 for r in rows if r["truth"] == l and r["llm"] == l)
        pred = sum(1 for r in rows if r["llm"] == l)
        truth_n = sum(1 for r in rows if r["truth"] == l)
        pr[l] = ((tp / pred if pred else None), (tp / truth_n if truth_n else None))
    s_counts = {f"s{i}": sum(1 for r in rows if r["res"].get("checklist") and
                             r["res"]["checklist"].get(f"s{i}") is False) for i in range(1, 8)}
    binding = {f"s{i}": 0 for i in range(1, 8)}
    for r in rows:
        chk = r["res"].get("checklist")
        if chk and chk.get("level") == "PARTIAL_SUPPORT":
            false_items = [f"s{i}" for i in range(1, 8) if chk.get(f"s{i}") is False]
            if len(false_items) == 1:
                binding[false_items[0]] += 1
    safety = {"irr_to_direct": sum(1 for r in rows if r["truth"] == "IRRELEVANT"
                                   and r["llm"] == "DIRECT_SUPPORT"),
              "irr_to_contra": sum(1 for r in rows if r["truth"] == "IRRELEVANT"
                                   and r["llm"] == "CONTRADICTS")}
    return {"name": tag, "n": n, "rule_acc": rule_acc, "llm_acc": llm_acc, "conf": conf,
            "fixes": fixes, "breaks": breaks, "pr": pr, "s_counts": s_counts,
            "binding": binding, "safety": safety, "rows": rows}


def report(a):
    print(f"\n--- {a['name']} n={a['n']} ---")
    print(f"  Rule {a['rule_acc']:.3f} | Stage5 Final {a['llm_acc']:.3f}")
    for l in ("DIRECT_SUPPORT", "CONTRADICTS", "IRRELEVANT"):
        p, r = a["pr"][l]
        print(f"  {l:<16} precision={p if p is None else round(p,3)} "
              f"recall={r if r is None else round(r,3)}")
    print(f"  S1–S7 拒绝计数: {a['s_counts']}")
    print(f"  单项绑定(唯一未过项)计数: {a['binding']}")
    print(f"  安全: IRRELEVANT→DIRECT={a['safety']['irr_to_direct']} "
          f"IRRELEVANT→CONTRADICTS={a['safety']['irr_to_contra']}")
    print(f"  Rule→LLM 改对 {len(a['fixes'])} / 改错 {len(a['breaks'])}")


dev_path = ROOT / "projects" / "_drafts" / "llm_judge_s5_dev.db"
frozen_path = ROOT / "projects" / "_drafts" / "llm_judge_s5_frozen.db"
for p in (dev_path, frozen_path):
    if p.exists():
        p.unlink()

# ---------- dev 验证（开发集，先跑） ----------
dev_rows = run_set("dev", load_dev(), ThreadLocalDb(dev_path), {})
dev_a = aggregate(dev_rows, "dev61")
report(dev_a)

# ---------- 冻结 197 一次性验收 ----------
frozen_rows = run_set("frozen", load_frozen(), ThreadLocalDb(frozen_path), {})
subsets = {"regression50": [r for r in frozen_rows if r["id"].startswith("RS-")],
           "blind121": [r for r in frozen_rows if r["id"].startswith("B")],
           "stress26": [r for r in frozen_rows if r["id"].startswith("CT-")]}
for name, sub in subsets.items():
    report(aggregate(sub, name))
frozen_a = aggregate(frozen_rows, "frozen197")
report(frozen_a)

print("\n===== 合并混淆矩阵（truth × Stage5 final，冻结 197） =====")
print("truth\\final   " + "".join(f"{l[:4]:>8}" for l in LEVELS))
for t in LEVELS:
    print(f"{t[:14]:<14}" + "".join(f"{frozen_a['conf'][(t, p)]:>8}" for p in LEVELS))

# ---------- 三标签对比（Rule / Stage4b / Stage5，冻结 197） ----------
db4b = Database(ROOT / "projects" / "_drafts" / "llm_judge_eval_real.db")
v4b_ok = s5_ok = rule_ok = 0
diff_v4b_s5 = 0
for r in frozen_rows:
    row = db4b.get_llm_judge_row(cache_key_v1(r["claim"], r["ev"]))
    v4b = (row or {}).get("llm_label") or r["rule"]
    if v4b == r["truth"]:
        v4b_ok += 1
    if r["llm"] == r["truth"]:
        s5_ok += 1
    if r["rule"] == r["truth"]:
        rule_ok += 1
    if v4b != r["llm"]:
        diff_v4b_s5 += 1
print(f"\n===== 三标签对比（冻结 197） =====")
print(f"  Rule {rule_ok}/197={rule_ok/197:.3f} | Stage4b LLM {v4b_ok}/197={v4b_ok/197:.3f} | "
      f"Stage5 Final {s5_ok}/197={s5_ok/197:.3f} | 4b≠S5 标签 {diff_v4b_s5} 条")

print(f"\n===== 资源统计 =====")
print(f"  API 调用: {client.calls} | token in/out: {client.tokens_in}/{client.tokens_out} | "
      f"费用估算: ${client.tokens_in*PRICE_IN + client.tokens_out*PRICE_OUT:.4f}")
lat = sorted(r["res"].get("latency_ms", 0) for r in dev_rows + frozen_rows
             if r["res"].get("latency_ms"))
if lat:
    print(f"  延迟 avg={sum(lat)/len(lat):.0f}ms p50={lat[len(lat)//2]}ms p95={lat[int(len(lat)*0.95)]}ms")
print(f"  dev 与 frozen 分差: {abs(dev_a['llm_acc'] - frozen_a['llm_acc']):.3f}")

def _serializable(a):
    out = {}
    for k, v in a.items():
        if isinstance(v, Counter):
            out[k] = {f"{t}->{p}": n for (t, p), n in v.items()} if k == "conf" else dict(v)
        elif isinstance(v, list):
            out[k] = v
        else:
            out[k] = v
    return out


out = {"dev": _serializable(dev_a), "frozen": _serializable(frozen_a),
       "resources": {"calls": client.calls, "tokens_in": client.tokens_in,
                     "tokens_out": client.tokens_out,
                     "cost_usd_est": client.tokens_in * PRICE_IN + client.tokens_out * PRICE_OUT}}
(ROOT / "projects" / "_drafts" / "r1_stage5_eval.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
print("\nwritten: projects/_drafts/r1_stage5_eval.json")
