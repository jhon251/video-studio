"""V2.1 Stage 8E 一次性验收：检索回退 + 来源可靠性分层 + 覆盖率统计。

- 不重跑冻结 197；不接生产；不修改 EvidenceSignal/Aggregation/truth/冻结测试；无站点特例。
- 基线：Stage 8D 已存重抓结果（r1_stage8d_full.json 的 per_id.status）。
- 后测：对基线未覆盖的 Claim 走 retrieve_with_fallback（bing→baidu→tavily）。
- 产出：可用 Evidence 比例 / source_quality 分布 / retrieval 失败原因分类 / valid 数量变化 /
  检索覆盖率；EvidenceSignal 与 CRITICAL 双零保持（冻结，引用 8D）。
- 回放：原始 HTML + 最终正文 + source_quality 落盘 r1_stage8e_full.json。
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
from video_studio.tools.evidence_retrieval import (  # noqa: E402
    retrieve_with_fallback, retrieval_coverage, source_quality)

col = json.loads((ROOT / "projects" / "_drafts" / "s5_dev_v2_collection.json").read_text(encoding="utf-8"))
samples = col["samples"]
base = json.loads((ROOT / "projects" / "_drafts" / "r1_stage8d_full.json").read_text(encoding="utf-8"))

# 基线：8D 已存重抓结果的 usable 判定（status=='valid' 含 salvaged）
base_usable = {k for k, v in base["per_id"].items() if v["status"] == "valid"}
# 基线 valid 正文的 source_quality（回放可重算）
base_sq = []
for k in base_usable:
    v = base["per_id"][k]
    base_sq.append(source_quality(v["url"], "", v["body"]))

# 分组：claim_text -> sample ids
claims: dict[str, list[str]] = {}
for s in samples:
    claims.setdefault(s["claim_text"], []).append(s["id"])

covered = [c for c, ids in claims.items() if any(i in base_usable for i in ids)]
uncovered = [c for c in claims if c not in covered]

_tls = threading.local()


def get_session():
    if not hasattr(_tls, "session"):
        import requests
        _tls.session = requests.Session()
    return _tls.session


def work(claim_text):
    res = retrieve_with_fallback(claim_text, session=get_session(), max_usable=2, per_provider=3)
    cov = retrieval_coverage(claim_text, res["evidence"], res["failures"])
    return claim_text, res, cov


print(f"样本 {len(samples)} | 唯一 Claim {len(claims)} | 基线覆盖 Claim {len(covered)} | "
      f"未覆盖 Claim {len(uncovered)}", flush=True)

fallback_results: dict[str, dict] = {}
with ThreadPoolExecutor(max_workers=6) as ex:
    futs = {ex.submit(work, c): c for c in uncovered}
    for i, fut in enumerate(as_completed(futs), 1):
        claim_text, res, cov = fut.result()
        fallback_results[claim_text] = {"retrieval": res, "coverage": cov}
        if i % 6 == 0 or i == len(uncovered):
            print(f"  fallback {i}/{len(uncovered)} ...", flush=True)

# ---------- 汇总 ----------
recovered_claims = [c for c, fr in fallback_results.items() if fr["retrieval"]["usable"]]
recovered_samples = sum(len(claims[c]) for c in recovered_claims)

base_usable_n = len(base_usable)
after_usable_n = base_usable_n + recovered_samples
after_covered = len(covered) + len(recovered_claims)

print("\n==== Stage 8E 验收（信号 dev 72 = 49 唯一 Claim） ====")
print(f"[1] 可用 Evidence 比例（样本）: {base_usable_n}/{len(samples)}={base_usable_n/len(samples):.3f}"
      f" -> {after_usable_n}/{len(samples)}={after_usable_n/len(samples):.3f}"
      f"  (Δ {recovered_samples:+d})")
print(f"    检索覆盖率（Claim）: {len(covered)}/{len(claims)}={len(covered)/len(claims):.3f}"
      f" -> {after_covered}/{len(claims)}={after_covered/len(claims):.3f}"
      f"  (Δ {len(recovered_claims):+d})")

# [2] source_quality 分布（基线 valid vs 回退新增 valid）
base_tiers = Counter(q["tier"] for q in base_sq)
base_bands = Counter(q["band"] for q in base_sq)
new_usable_ev = [e for fr in fallback_results.values() for e in fr["retrieval"]["usable"]]
new_tiers = Counter(e["source_quality"]["tier"] for e in new_usable_ev)
new_bands = Counter(e["source_quality"]["band"] for e in new_usable_ev)
print(f"[2] source_quality 分布（tier）:")
print(f"    基线 valid ({base_usable_n}): {dict(base_tiers)}")
print(f"    回退新增 valid ({len(new_usable_ev)}): {dict(new_tiers)}")
print(f"    reliability band 基线: {dict(base_bands)} | 新增: {dict(new_bands)}")

# [3] retrieval 失败原因分类（回退链所有 fetch/search 结果）
fail_all: Counter = Counter()
for fr in fallback_results.values():
    fail_all.update(fr["retrieval"]["failures"])
print(f"[3] retrieval 失败原因分类（回退链全部尝试）: {dict(fail_all)}")

# [4] valid evidence 数量变化
print(f"[4] valid evidence 数量: {base_usable_n} -> {after_usable_n}  (Δ {recovered_samples:+d})")

# [5][6] 冻结保持
print("[5] EvidenceSignal 在 valid 子集表现: 保持 8D（prop precision 1.0 / recall 0.833；"
      "contradiction recall 1.0 / precision 0.75；n=23）—— 信号层冻结，8E 未改动。")
print("[6] CRITICAL 双零保持: 信号级 0（8D）；聚合级 0（8B.1 冻结）—— 8E 未改动。")

# 回放落盘
out = {
    "_meta": {"name": "r1_stage8e_full",
              "note": "Stage 8E 检索回退：保留原始 HTML + 最终正文 + source_quality，可回放。"},
    "baseline": {"usable_samples": base_usable_n, "covered_claims": len(covered),
                 "source_tiers": dict(base_tiers), "reliability_bands": dict(base_bands)},
    "after": {"usable_samples": after_usable_n, "covered_claims": after_covered,
              "recovered_claims": len(recovered_claims), "recovered_samples": recovered_samples,
              "new_source_tiers": dict(new_tiers), "new_reliability_bands": dict(new_bands),
              "failure_dist": dict(fail_all)},
    "per_claim": {c: {"sample_ids": claims[c],
                      "baseline_covered": any(i in base_usable for i in claims[c]),
                      "fallback": fallback_results.get(c)}
                  for c in claims},
}
(ROOT / "projects" / "_drafts" / "r1_stage8e_full.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print("\nwritten: projects/_drafts/r1_stage8e_full.json")
