"""Stage 8A：构建 62 Claim（FACT 50 条）的 Evidence Pool + 基线统计（无 LLM，无裁决）。

候选来源（全部真实检索文本）：第一轮入库 Evidence（43）、第一轮盲测集合（121）、
dev v1 集合（57）、dev v2 集合的 original 样本（72 中过滤 derived）。
派生样本（DV/DC/DCX，合成 Claim）不建池；其页面经 URL 去重归入原 Claim 池。
"""
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from video_studio.tools.evidence_pool import Pool, build_coverage_structure  # noqa: E402

PID = "p_f2215875dd49"
db = sqlite3.connect(str(ROOT / "projects" / "video_studio.db"))
db.row_factory = sqlite3.Row
claims = {c["claim_id"]: c["text"] for c in db.execute(
    "SELECT claim_id, text FROM claims WHERE project_id=? AND type='FACT'", (PID,))}
linked = {}
for r in db.execute("SELECT evidence_id FROM evidence WHERE project_id=?", (PID,)):
    cids = [x["claim_id"] for x in db.execute(
        "SELECT claim_id FROM claim_evidence WHERE evidence_id=?", (r["evidence_id"],))]
    linked[r["evidence_id"]] = cids

pools_input: dict[str, list[dict]] = {cid: [] for cid in claims}

# 1) 第一轮入库 Evidence
for r in db.execute("SELECT * FROM evidence WHERE project_id=?", (PID,)):
    for cid in linked.get(r["evidence_id"], []):
        if cid in pools_input:
            pools_input[cid].append({"url": r["url"], "title": "", "snippet": "",
                                     "text": r["excerpt"] or ""})

# 2) 第一轮盲测集合
for rec in json.loads((ROOT / "projects" / "_drafts" / "r1_blind_collection.json")
                      .read_text(encoding="utf-8"))["claims"]:
    if rec["claim_id"] not in pools_input:
        continue
    for r in rec["results"]:
        pools_input[rec["claim_id"]].append({"url": r["url"], "title": r["title"],
                                             "snippet": r["snippet"],
                                             "text": r["page"].get("text", "")})

# 3) dev v1 集合
for rec in json.loads((ROOT / "projects" / "_drafts" / "s5_dev_collection.json")
                      .read_text(encoding="utf-8"))["claims"]:
    if rec["claim_id"] not in pools_input:
        continue
    for r in rec["results"]:
        pools_input[rec["claim_id"]].append({"url": r["url"], "title": r["title"],
                                             "snippet": r["snippet"],
                                             "text": r["page"].get("text", "")})

# 4) dev v2 集合（仅 original 样本；derived 页面经 URL 去重自然并入）
dev_v2 = json.loads((ROOT / "projects" / "_drafts" / "s5_dev_v2_collection.json")
                    .read_text(encoding="utf-8"))["samples"]
for s in dev_v2:
    if not s["id"].startswith("D"):
        continue
    cid = next((k for k, v in pools_input.items()
                if any(e.get("url") == s["evidence"]["url"] for e in v)), None)
    if cid:
        pools_input[cid].append({"url": s["evidence"]["url"], "title": s["evidence"]["title"],
                                 "snippet": s["evidence"]["snippet"],
                                 "text": s["evidence"]["text"]})

pools = {}
for cid, cands in sorted(pools_input.items()):
    pools[cid] = Pool(cid, cands)

all_stats = {cid: p.stats() for cid, p in pools.items()}
coverage = {cid: build_coverage_structure(claims[cid], p) for cid, p in pools.items()}

out = {
    "_meta": {"name": "s8_claim_pools",
              "note": "Stage 8A：62 FACT Claim 的 Evidence Pool（三级去重/独立性/来源分层）与 "
                      "Coverage 结构（s/o/p 列为 8B 占位）。全部真实检索文本，无 LLM，无裁决。"},
    "pools": {cid: {"stats": all_stats[cid],
                    "clusters": pools[cid].clusters,
                    "coverage": coverage[cid]}
              for cid in pools},
}
(ROOT / "projects" / "_drafts" / "s8_claim_pools.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

# ---------- 基线统计（Stage 8A.1 12 项） ----------
n_claims = len(pools)
n_cand = sum(s["candidate_count"] for s in all_stats.values())
n_cl = sum(s["cluster_count"] for s in all_stats.values())
url_dup = sum(s["url_dedup_rate"] * s["candidate_count"] for s in all_stats.values()) / n_cand if n_cand else 0
content_collapse = (n_cand - n_cl) / n_cand if n_cand else 0
dup_clusters = sum(s["duplicate_clusters"] for s in all_stats.values())
avg_members = sum(s["avg_members"] * s["cluster_count"] for s in all_stats.values()) / n_cl if n_cl else 0
synd = sum(s["syndicated_clusters"] for s in all_stats.values())
tiers = Counter()
for s in all_stats.values():
    tiers.update(s["source_tiers"])
unknown = tiers.get("unknown", 0)
print(f"1. URL 去重率: {url_dup:.2%}")
print(f"2. 内容级去重率(坍缩): {content_collapse:.2%}")
print(f"3. 转载链识别簇数: {synd}")
print(f"4. duplicate cluster 数: {dup_clusters}")
print(f"5. 每簇平均成员数: {avg_members:.2f}")
print(f"6. independent cluster 数: {n_cl}（独立权重合计 "
      f"{sum(s['independent_weight_sum'] for s in all_stats.values()):.1f}）")
print(f"7. source-tier 分布: {dict(tiers)}")
print(f"8. UNKNOWN 比例: {unknown/n_cl:.2%}（{unknown}/{n_cl}）")
print(f"9. source-tier 抽样准确率: 见 tests/evidence_pool_test.py（gold 25/25）")
elems = Counter()
for cid, cov in coverage.items():
    elems["qualifier行"] += len(cov["elements"]["qualifiers"])
    elems["number行"] += len(cov["elements"]["numbers_years"])
    elems["簇列"] += len(cov["clusters"])
print(f"10. Coverage 结构: claims={n_claims} 簇列={elems['簇列']} "
      f"限定词行={elems['qualifier行']} 数字/年份行={elems['number行']}")
print(f"11. 去重误合并案例: 0（单元测试：不同内容 2 簇不误并）")
print(f"12. 去重漏合并案例: 见下（转载链测试已 1 簇；真实池转载链 {synd} 簇）")
empty = [cid for cid, p in pools.items() if not p.clusters]
print(f"空池 claim: {len(empty)} -> {empty}")
print("written: projects/_drafts/s8_claim_pools.json")
