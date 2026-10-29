"""V2.1 Stage 8C 一次性验收（上游证据可用性专项；不重跑冻结 197；不接生产）。

- A 正文质量：tests/text_quality_test.py（18/18 gold）+ 本脚本对信号 dev 72 的正文有效率分布。
- B proposition recall：信号 dev 72（truth 已有），分 valid 子集 vs 全部，并拆分"信号能力不足 vs 输入正文不可用"。
- C 数字解析：tests/numeric_parser_test.py（9/9）。
- D contradiction：信号 dev 72 的 cand recall/precision，分 valid 子集，拆不可用正文损失。
- E CRITICAL：topic=false 且 cand=true 必须为 0。
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
from video_studio.tools.evidence_text_quality import quality  # noqa: E402

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


db_path = ROOT / "projects" / "_drafts" / "llm_judge_s8c.db"
if db_path.exists():
    db_path.unlink()
cache_db = ThreadLocalDb(db_path)
l1: dict = {}

col = json.loads((ROOT / "projects" / "_drafts" / "s5_dev_v2_collection.json").read_text(encoding="utf-8"))
labels = json.loads((ROOT / "tests" / "data" / "evidence_signal_dev.json").read_text(encoding="utf-8"))["labels"]
samples = [{"id": s["id"], "claim": s["claim_text"], "truth_sig": labels[s["id"]],
            "ev": s["evidence"]} for s in col["samples"]]


def work(s):
    q = quality(s["ev"].get("text", ""))
    sig = extract_signals(s["claim"], s["ev"], router, cache_db=cache_db, l1_cache=l1)
    return {**s, "quality": q["status"], "sig": sig}


with ThreadPoolExecutor(max_workers=4) as ex:
    rows = [ex.submit(work, s).result() for s in samples]

# ---------- A ----------
qdist = Counter(r["quality"] for r in rows)
print(f"A. 正文质量（信号 dev 72）: {dict(qdist)} | 正文有效率 {qdist['valid']}/{len(rows)}="
      f"{qdist['valid']/len(rows):.3f}")

# ---------- B ----------
def prop_metrics(subset):
    n = len(subset)
    tp = sum(1 for r in subset if r["truth_sig"]["prop"] and r["sig"]["proposition_relevance"])
    pr = sum(1 for r in subset if r["truth_sig"]["prop"])
    pp = sum(1 for r in subset if r["sig"]["proposition_relevance"])
    prec = tp / pp if pp else None
    rec = tp / pr if pr else None
    return prec, rec, tp, n
valid = [r for r in rows if r["quality"] == "valid"]
for name, sub in (("全部", rows), ("valid 子集", valid)):
    prec, rec, tp, n = prop_metrics(sub)
    print(f"B. proposition ({name} n={n}): precision={prec if prec is None else round(prec,3)} "
          f"recall={rec if rec is None else round(rec,3)}")
loss = [r for r in rows if r["truth_sig"]["prop"] and not r["sig"]["proposition_relevance"]]
loss_cause = Counter("正文不可用" if r["quality"] != "valid" else "信号能力不足" for r in loss)
print(f"   proposition 漏判 {len(loss)} 条，按原因: {dict(loss_cause)}")

# ---------- D ----------
def cand_metrics(subset):
    cand_true = [r for r in subset if r["truth_sig"]["cand"]]
    tp = sum(1 for r in cand_true if r["sig"]["contradiction_candidate"])
    cand_pred = [r for r in subset if r["sig"]["contradiction_candidate"]]
    recall = tp / len(cand_true)
    prec = tp / len(cand_pred) if cand_pred else None
    return recall, prec, len(cand_true)
for name, sub in (("全部", rows), ("valid 子集", valid)):
    rec, prec, n_true = cand_metrics(sub)
    print(f"D. contradiction ({name} n={len(sub)}): recall={rec:.3f} precision="
          f"{prec if prec is None else round(prec,3)}（truth cand={n_true}）")
cand_loss = [r for r in rows if r["truth_sig"]["cand"] and not r["sig"]["contradiction_candidate"]]
cand_cause = Counter("正文不可用" if r["quality"] != "valid" else "信号能力不足" for r in cand_loss)
print(f"   contradiction 漏判 {len(cand_loss)} 条，按原因: {dict(cand_cause)}")

# ---------- E ----------
crit = [r for r in rows if not r["truth_sig"]["topic"] and r["sig"]["contradiction_candidate"]]
print(f"E. CRITICAL（topic=false 且 cand=true）: {len(crit)}")
print(f"   参考：8B.1 聚合 CRITICAL 双零 = 0（已报告，本阶段未重跑聚合）")

print(f"\n资源: API 调用 {client.calls} | token {client.tokens_in}/{client.tokens_out} | "
      f"费用 ${client.tokens_in*PRICE_IN + client.tokens_out*PRICE_OUT:.4f}")
fb = Counter((r["sig"].get("fallback_reason") or "ok") for r in rows)
print(f"fallback: {dict(fb)}")

(ROOT / "projects" / "_drafts" / "r1_stage8c_eval.json").write_text(
    json.dumps({"quality_dist": dict(qdist),
                "prop_loss_cause": dict(loss_cause),
                "cand_loss_cause": dict(cand_cause),
                "resources": {"calls": client.calls, "tokens_in": client.tokens_in,
                              "tokens_out": client.tokens_out,
                              "cost_usd_est": client.tokens_in * PRICE_IN + client.tokens_out * PRICE_OUT}},
               ensure_ascii=False, indent=2), encoding="utf-8")
print("\nwritten: projects/_drafts/r1_stage8c_eval.json")
