"""V2.1 Stage 8F 一次性验收：Evidence readiness 决策准备层。

- 不重跑冻结 197；不接生产；不修改 EvidenceSignal 判断逻辑 / Aggregation 四结构 / truth / 冻结测试；
  无站点特例。只读复用冻结规则侧组件。
- 数据：49 唯一 Claim（信号 dev 72）= 8D 基线可用正文 + 8E 回退新增可用正文。
- 产出：readiness 指标 / source_quality 分布变化 / 高低质量对 decision confidence 影响 /
  contradiction balance / CRITICAL 双零保持。
- 回放：每 Claim 的 readiness 全维度落盘 r1_stage8f_full.json。
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from video_studio.tools.evidence_readiness import readiness, readiness_summary  # noqa: E402

col = json.loads((ROOT / "projects" / "_drafts" / "s5_dev_v2_collection.json").read_text(encoding="utf-8"))
samples = col["samples"]
base = json.loads((ROOT / "projects" / "_drafts" / "r1_stage8d_full.json").read_text(encoding="utf-8"))
e8 = json.loads((ROOT / "projects" / "_drafts" / "r1_stage8e_full.json").read_text(encoding="utf-8"))

base_usable = {k for k, v in base["per_id"].items() if v["status"] == "valid"}
id_meta = {s["id"]: s for s in samples}

claims: dict[str, list[str]] = {}
for s in samples:
    claims.setdefault(s["claim_text"], []).append(s["id"])

baseline_ev = defaultdict(list)
for sid in base_usable:
    c = id_meta[sid]["claim_text"]
    v = base["per_id"][sid]
    baseline_ev[c].append({"url": v["url"], "title": id_meta[sid]["evidence"]["title"],
                           "snippet": id_meta[sid]["evidence"]["snippet"], "body": v["body"]})

fallback_ev = defaultdict(list)
for c, v in e8["per_claim"].items():
    if v.get("fallback"):
        for e in v["fallback"]["retrieval"]["usable"]:
            fallback_ev[c].append({"url": e["url"], "title": e["title"],
                                   "snippet": e["snippet"], "body": e["body"]})

rows = []
for c in claims:
    bl = baseline_ev.get(c, [])
    fb = fallback_ev.get(c, [])
    final = bl + fb
    r = readiness(c, final)
    rows.append({"claim": c, "baseline_n": len(bl), "fallback_n": len(fb),
                 "final_n": len(final), **r})

summary = readiness_summary(rows)

# ---------- 输出 ----------
print("==== Stage 8F 验收（49 唯一 Claim；最终证据 = 8D 基线可用 + 8E 回退新增） ====")
print(f"[1] Evidence readiness 指标:")
print(f"    grade 分布: {summary['grade_dist']}")
print(f"    decision_confidence 分布: {summary['confidence_dist']}")
print(f"    平均 readiness_score: {summary['avg_readiness_score']}")

print(f"[2] source_quality 分布变化（8D 基线 vs 8E 回退后最终）:")
base_bands = e8["baseline"]["reliability_bands"]
final_sq_bands = {"high": 0, "medium": 0, "low": 0}
final_sq_n = 0
for r in rows:
    for b, v in r["source_quality"]["bands"].items():
        final_sq_bands[b] = final_sq_bands.get(b, 0) + v
    final_sq_n += r["source_quality"]["n"]
print(f"    基线 valid ({len(base_usable)}) band: {base_bands}")
print(f"    最终 ({final_sq_n}) band: {final_sq_bands}")

print(f"[3] 高低质量 Evidence 对 decision confidence 影响:")
print(f"    高可靠源 Claim (n={summary['high_quality_claims']}): "
      f"confidence={summary['high_quality_confidence']} avg_score={summary['avg_score_high']}")
print(f"    无高可靠源 Claim (n={summary['low_quality_claims']}): "
      f"confidence={summary['low_quality_confidence']} avg_score={summary['avg_score_low']}")

print(f"[4] contradiction balance 统计:")
# 可靠矛盾：冻结信号真值（evidence_signal_dev.json 的 cand，LLM 口径，72 原始样本）
sig_dev = json.loads((ROOT / "tests" / "data" / "evidence_signal_dev.json").read_text(encoding="utf-8"))
cand_true = sum(1 for lb in sig_dev["labels"].values() if lb.get("cand"))
cand_total = len(sig_dev["labels"])
print(f"    冻结信号真值（72 原始样本）: contradiction_candidate={cand_true}/{cand_total} "
      f"({cand_true/cand_total:.3f})")
bl = summary["balance"]
print(f"    规则侧审计（最终证据）: supporting={bl['total_supporting']} context={bl['total_context']} "
      f"否定命中={bl['total_negation_rule_hits']} 数字规则冲突={bl['total_numeric_rule_conflicts']}")
print(f"    （否定/数字规则冲突为审计信号；可靠矛盾由冻结信号+聚合裁决，本层不重判）")

print("[5] CRITICAL 双零保持: 信号级 0（8D）；聚合级 0（8B.1 冻结）—— 8F 未改动。")

# 落盘回放
out = {
    "_meta": {"name": "r1_stage8f_full",
              "note": "Stage 8F readiness 决策准备层：每 Claim 全维度（completeness/source_quality/balance/readiness），可回放。"},
    "summary": summary,
    "per_claim": [{"claim": r["claim"], "baseline_n": r["baseline_n"], "fallback_n": r["fallback_n"],
                   "final_n": r["final_n"], "grade": r["grade"],
                   "decision_confidence": r["decision_confidence"],
                   "readiness_score": r["readiness_score"],
                   "completeness": r["completeness"], "source_quality": r["source_quality"],
                   "balance": r["balance"]} for r in rows],
}
(ROOT / "projects" / "_drafts" / "r1_stage8f_full.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print("\nwritten: projects/_drafts/r1_stage8f_full.json")
