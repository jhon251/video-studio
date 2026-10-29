"""V2.1 Stage 8D 一次性验收（合并版）：证据正文可用性 + EvidenceSignal 在 valid 子集上的保持。

- 不重跑冻结 197；不接生产；不修改 EvidenceSignal 语义 / 聚合四结构 / fact_check / semantic_judge。
- A 正文可用性：修复后 BingSearchProvider().fetch 重抓 72 URL → extract_body → quality，
  与 Stage 8C 已存 fetch 文本（同一新链重判）对比：正文有效率/JS shell/空/编码错误解决率/valid 比例。
- B EvidenceSignal 保持：仅对可用正文子集（valid 或 salvaged）重跑 extract_signals，
  报告 proposition / contradiction 的 precision/recall，以及 CRITICAL（topic=false 且 cand=true）双零。
- C 回放：原始 HTML 与最终正文均落盘 projects/_drafts/r1_stage8d_full.json。
"""
import json
import sys
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from video_studio.core.env import load_env  # noqa: E402
load_env(ROOT / ".env")
from video_studio.db.schema import Database  # noqa: E402
from video_studio.llm.router import DeepSeekClient, Router  # noqa: E402
from video_studio.tools.evidence_signal import extract_signals  # noqa: E402
from video_studio.tools.evidence_text_quality import extract_body  # noqa: E402
from video_studio.tools.search_provider import BingSearchProvider  # noqa: E402

PRICE_IN, PRICE_OUT = 0.27 / 1e6, 1.10 / 1e6
config = json.loads((ROOT / "config" / "config.yongsheng.json").read_text(encoding="utf-8"))

col = json.loads((ROOT / "projects" / "_drafts" / "s5_dev_v2_collection.json").read_text(encoding="utf-8"))
labels = json.loads((ROOT / "tests" / "data" / "evidence_signal_dev.json").read_text(encoding="utf-8"))["labels"]
samples = col["samples"]


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


def get_provider() -> BingSearchProvider:
    if not hasattr(_tls, "provider"):
        _tls.provider = BingSearchProvider()
    return _tls.provider


db_path = ROOT / "projects" / "_drafts" / "llm_judge_s8d.db"
if db_path.exists():
    db_path.unlink()
cache_db = ThreadLocalDb(db_path)
l1: dict = {}


def final_status(res: dict) -> str:
    return "valid" if res.get("salvaged") else res["status"]


def usable(res: dict) -> bool:
    return res["status"] == "valid" or res.get("salvaged") is True


# ---------- 基线（Stage 8C 已存 fetch 文本，同一新链重判） ----------
base_status = {}
for s in samples:
    stored = s["evidence"].get("text", "") or ""
    base_status[s["id"]] = final_status(extract_body(stored))


# ---------- 后测：重抓 + extract_body ----------
def refetch(s):
    url = s["evidence"].get("url", "")
    try:
        page = get_provider().fetch(url)
    except Exception as e:  # noqa: BLE001
        return s, "", {"status": "empty", "text": "", "salvaged": False, "rationale": f"fetch err {type(e).__name__}"}
    raw = page.text or ""
    res = extract_body(raw)
    return s, raw, res


rows = []
with ThreadPoolExecutor(max_workers=6) as ex:
    futs = [ex.submit(refetch, s) for s in samples]
    for i, fut in enumerate(as_completed(futs), 1):
        s, raw, res = fut.result()
        rows.append({"id": s["id"], "claim": s["claim_text"], "truth_sig": labels[s["id"]],
                     "url": s["evidence"].get("url", ""), "raw_html": raw,
                     "body": res["text"], "status": final_status(res),
                     "salvaged": res.get("salvaged"), "base_status": base_status[s["id"]],
                     "title": s["evidence"].get("title", ""),
                     "snippet": s["evidence"].get("snippet", "")})
        if i % 12 == 0 or i == len(samples):
            print(f"  re-fetch {i}/{len(samples)} ...", flush=True)

N = len(rows)
after_dist = Counter(r["status"] for r in rows)
base_dist = Counter(base_status.values())
print("\n==== Stage 8D-A 正文可用性（信号 dev 72） ====")
print(f"基线（Stage 8C 已存）: {dict(base_dist)}")
print(f"后测（修复 fetch + extract_body）: {dict(after_dist)}")

base_usable = sum(1 for v in base_status.values() if v == "valid")
after_usable = sum(1 for r in rows if usable(r))
print(f"[1] 正文有效率: {base_usable}/{N}={base_usable/N:.3f} -> {after_usable}/{N}={after_usable/N:.3f} "
      f"(Δ {after_usable-base_usable:+d})")

shell_ids = [r["id"] for r in rows if r["base_status"] == "js_shell"]
shell_resolved = sum(1 for i in shell_ids if usable(next(r for r in rows if r["id"] == i)))
print(f"[2] JS shell 解决率: {shell_resolved}/{len(shell_ids)}")

empty_ids = [r["id"] for r in rows if r["base_status"] == "empty"]
empty_resolved = sum(1 for i in empty_ids if usable(next(r for r in rows if r["id"] == i)))
print(f"[3] 空正文解决率: {empty_resolved}/{len(empty_ids)}")

enc_ids = [r["id"] for r in rows if r["base_status"] == "encoding_error"]
enc_resolved = sum(1 for i in enc_ids if usable(next(r for r in rows if r["id"] == i)))
print(f"[4] 编码错误解决率: {enc_resolved}/{len(enc_ids)}")

print(f"[5] valid 比例（后测）: {after_dist['valid']}/{N}={after_dist['valid']/N:.3f} "
      f"| low_content={after_dist['low_content']}")

# ---------- B：EvidenceSignal 仅对可用正文子集重跑 ----------
valid_rows = [r for r in rows if usable(r)]


def work_signal(r):
    ev = {"title": r["title"], "snippet": r["snippet"], "text": r["body"], "url": r["url"]}
    sig = extract_signals(r["claim"], ev, router, cache_db=cache_db, l1_cache=l1)
    return {**r, "sig": sig}


with ThreadPoolExecutor(max_workers=4) as ex:
    sig_rows = [ex.submit(work_signal, r).result() for r in valid_rows]

print(f"\n==== Stage 8D-B EvidenceSignal 保持（可用正文子集 n={len(sig_rows)}） ====")


def prop_metrics(subset):
    tp = sum(1 for r in subset if r["truth_sig"]["prop"] and r["sig"]["proposition_relevance"])
    pr = sum(1 for r in subset if r["truth_sig"]["prop"])
    pp = sum(1 for r in subset if r["sig"]["proposition_relevance"])
    return (tp / pp if pp else None), (tp / pr if pr else None), tp, len(subset)


prec, rec, tp, n = prop_metrics(sig_rows)
print(f"[6] proposition: precision={prec if prec is None else round(prec,3)} "
      f"recall={rec if rec is None else round(rec,3)} (n={n}, truth prop 漏判 "
      f"{sum(1 for r in sig_rows if r['truth_sig']['prop'] and not r['sig']['proposition_relevance'])})")


def cand_metrics(subset):
    cand_true = [r for r in subset if r["truth_sig"]["cand"]]
    tp = sum(1 for r in cand_true if r["sig"]["contradiction_candidate"])
    cand_pred = [r for r in subset if r["sig"]["contradiction_candidate"]]
    return (tp / len(cand_true) if cand_true else None), (tp / len(cand_pred) if cand_pred else None), len(cand_true)


c_rec, c_prec, c_n = cand_metrics(sig_rows)
print(f"    contradiction: recall={c_rec if c_rec is None else round(c_rec,3)} "
      f"precision={c_prec if c_prec is None else round(c_prec,3)} (truth cand={c_n})")

crit = [r for r in sig_rows if not r["truth_sig"]["topic"] and r["sig"]["contradiction_candidate"]]
print(f"[7] CRITICAL（信号级 topic=false 且 cand=true，可用子集）: {len(crit)}")
print(f"    CRITICAL（聚合级双零，冻结 8B.1 未重跑）: 0（保持，见 8B.1 报告）")

# ---------- 回放落盘（原始 HTML + 最终正文） ----------
out = {
    "_meta": {"name": "r1_stage8d_full",
              "note": "Stage 8D 72 信号 dev 重抓：保留原始 HTML 与最终正文，可回放。"},
    "availability": {"base_dist": dict(base_dist), "after_dist": dict(after_dist),
                     "valid_rate_base": base_usable / N, "valid_rate_after": after_usable / N,
                     "js_shell_resolved": f"{shell_resolved}/{len(shell_ids)}",
                     "empty_resolved": f"{empty_resolved}/{len(empty_ids)}",
                     "encoding_resolved": f"{enc_resolved}/{len(enc_ids)}"},
    "signal_subset": {"n": len(sig_rows), "prop_precision": prec, "prop_recall": rec,
                      "cand_precision": c_prec, "cand_recall": c_rec, "critical": len(crit)},
    "resources": {"calls": client.calls, "tokens_in": client.tokens_in, "tokens_out": client.tokens_out,
                  "cost_usd_est": client.tokens_in * PRICE_IN + client.tokens_out * PRICE_OUT},
    "per_id": {r["id"]: {"url": r["url"], "base_status": r["base_status"], "status": r["status"],
                          "salvaged": r["salvaged"], "raw_html": r["raw_html"], "body": r["body"],
                          "sig": r.get("sig")} for r in rows},
}
(ROOT / "projects" / "_drafts" / "r1_stage8d_full.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n资源: API 调用 {client.calls} | token {client.tokens_in}/{client.tokens_out} | "
      f"费用 ${client.tokens_in*PRICE_IN + client.tokens_out*PRICE_OUT:.4f}")
print("written: projects/_drafts/r1_stage8d_full.json")
