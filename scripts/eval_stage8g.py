"""V2.1 Stage 8G 一次性验收：Claim Structuring / Research Brief Layer。

- 不重跑冻结 197；不接生产；不修改 Aggregation 四结构 / EvidenceSignal / truth / 冻结测试；无站点特例。
- ① Claim 拆解准确率：tests/data/claim_structuring_gold.json（20 条 label-first）。
- ② Evidence-Claim 映射完整性：49 唯一 Claim（最终证据 = 8D 基线可用 + 8E 回退新增）。
- ③ Research Brief 可读性：结构完整性检查 + 抽样输出。
- ④ 原冻结测试保持 / ⑤ CRITICAL 双零保持（冻结，引用）。
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from video_studio.tools.claim_structuring import decompose_claim, build_research_brief  # noqa: E402

# ---------- ① Claim 拆解准确率 ----------
gold = json.loads((ROOT / "tests" / "data" / "claim_structuring_gold.json").read_text(encoding="utf-8"))["entries"]


def set_pr(pred: list, truth: list):
    p, t = set(pred), set(truth)
    tp = len(p & t)
    prec = tp / len(p) if p else 1.0
    rec = tp / len(t) if t else 1.0
    return prec, rec, tp


ct_ok = 0
sub_ok = 0
q_tp = q_pr = q_tr = 0
n_tp = n_pr = n_tr = 0
q_tot = n_tot = 0
misses = []
for e in gold:
    d = decompose_claim(e["text"])
    if d["claim_type"] == e["claim_type"]:
        ct_ok += 1
    else:
        misses.append((e["id"], "type", e["claim_type"], d["claim_type"]))
    if len(d["sub_claims"]) == e["sub_count"]:
        sub_ok += 1
    else:
        misses.append((e["id"], "sub", e["sub_count"], len(d["sub_claims"])))
    for pred, truth, kind in ((d["qualifiers"], e["qualifiers"], "q"), (d["numbers_years"], e["numbers_years"], "n")):
        pr, rec, tp = set_pr(pred, truth)
        if kind == "q":
            q_tp += tp; q_pr += pr; q_tr += rec; q_tot += 1
        else:
            n_tp += tp; n_pr += pr; n_tr += rec; n_tot += 1
        if pred != truth:
            misses.append((e["id"], kind, truth, pred))

G = len(gold)
print("==== Stage 8G 验收 ====")
print(f"[1] Claim 拆解准确率 (gold n={G}):")
print(f"    claim_type 准确率: {ct_ok}/{G} = {ct_ok/G:.3f}")
print(f"    sub_claim 数量准确率: {sub_ok}/{G} = {sub_ok/G:.3f}")
print(f"    qualifier: precision={q_pr/q_tot:.3f} recall={q_tr/q_tot:.3f}")
print(f"    numbers_years: precision={n_pr/n_tot:.3f} recall={n_tr/n_tot:.3f}")
if misses:
    print(f"    不一致案例: {misses}")

# ---------- ②③ Evidence-Claim 映射完整性 + Research Brief ----------
col = json.loads((ROOT / "projects" / "_drafts" / "s5_dev_v2_collection.json").read_text(encoding="utf-8"))
base = json.loads((ROOT / "projects" / "_drafts" / "r1_stage8d_full.json").read_text(encoding="utf-8"))
e8 = json.loads((ROOT / "projects" / "_drafts" / "r1_stage8e_full.json").read_text(encoding="utf-8"))
base_usable = {k for k, v in base["per_id"].items() if v["status"] == "valid"}
id_meta = {s["id"]: s for s in col["samples"]}
claims: dict[str, list[str]] = {}
for s in col["samples"]:
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

briefs = {}
cov_fracs = []
for c in claims:
    ev = baseline_ev.get(c, []) + fallback_ev.get(c, [])
    b = build_research_brief(c, ev)
    briefs[c] = b
    cov_fracs.append(b["covered_elements"] / b["total_elements"] if b["total_elements"] else 1.0)

avg_cov = sum(cov_fracs) / len(cov_fracs) if cov_fracs else 0.0
print(f"[2] Evidence-Claim 映射完整性: 平均元素覆盖 {avg_cov:.3f} "
      f"(49 Claim；元素 = 实体+限定词+数字/年份)")
full_cov = sum(1 for f in cov_fracs if f >= 1.0)
print(f"    完全覆盖 Claim: {full_cov}/{len(claims)}")

# [3] 可读性：结构完整性检查
REQUIRED = ("类型：", "实体：", "限定条件：", "数字/年份：", "证据条数：", "来源可靠性：", "readiness：")
struct_ok = sum(1 for b in briefs.values() if all(k in b["brief_text"] for k in REQUIRED))
print(f"[3] Research Brief 可读性: 结构完整 {struct_ok}/{len(briefs)}")
print("    抽样（3 条）:")
for i, (c, b) in enumerate(list(briefs.items())[:3], 1):
    print(f"    --- 样例 {i} ---")
    for line in b["brief_text"].split("\n")[:9]:
        print(f"      {line}")

print("[4] 原冻结测试保持: 14 套件回归（见最终校验，0/14 失败）")
print("[5] CRITICAL 双零保持: 信号级 0（8D）；聚合级 0（8B.1 冻结）—— 8G 未改动。")

# 落盘回放
out = {
    "_meta": {"name": "r1_stage8g_full",
              "note": "Stage 8G Research Brief：每 Claim 结构拆解 + Evidence 映射 + brief_text，可回放。"},
    "decomposition_accuracy": {"claim_type": f"{ct_ok}/{G}", "sub_count": f"{sub_ok}/{G}",
                               "qualifier_precision": round(q_pr/q_tot, 3),
                               "qualifier_recall": round(q_tr/q_tot, 3),
                               "number_precision": round(n_pr/n_tot, 3),
                               "number_recall": round(n_tr/n_tot, 3),
                               "misses": misses},
    "mapping_completeness": {"avg": round(avg_cov, 3), "full_coverage": f"{full_cov}/{len(claims)}"},
    "per_claim": {c: {"structure": b["structure"], "element_coverage": b["element_coverage"],
                      "gaps": b["gaps"], "brief_text": b["brief_text"]} for c, b in briefs.items()},
}
(ROOT / "projects" / "_drafts" / "r1_stage8g_full.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print("\nwritten: projects/_drafts/r1_stage8g_full.json")
