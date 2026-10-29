"""阶段 2 盲测评估：对冻结版 semantic_judge 跑盲测集，输出混淆矩阵与全部要求的指标。

labels 先行落盘（r1_blind_labels.json），本脚本只读；不改任何规则。"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from video_studio.tools.semantic_judge import (  # noqa: E402
    judge_support, _claim_profile, _qualifier_requirements, _extract_numbers, CN_NUM_RE)

col = json.loads((ROOT / "projects" / "_drafts" / "r1_blind_collection.json").read_text(encoding="utf-8"))
labels = json.loads((ROOT / "projects" / "_drafts" / "r1_blind_labels.json").read_text(encoding="utf-8"))["labels"]

samples = []
for rec in col["claims"]:
    for r in rec["results"]:
        samples.append({
            "claim_text": rec["claim_text"],
            "evidence": {"title": r["title"], "snippet": r["snippet"],
                         "text": r["page"].get("text", ""), "url": r["url"]},
        })
assert len(samples) == 121, len(samples)

LEVELS = ["DIRECT_SUPPORT", "PARTIAL_SUPPORT", "CONTEXT_ONLY", "IRRELEVANT", "CONTRADICTS"]
matrix = {t: Counter() for t in LEVELS}     # matrix[truth][got]
misses = []
for i, s in enumerate(samples, 1):
    truth = labels[str(i)]
    got = judge_support(s["claim_text"], s["evidence"])
    matrix[truth][got] += 1
    if got != truth:
        misses.append((i, truth, got, s["claim_text"][:30], s["evidence"]["title"][:40],
                       s["evidence"]["url"][:60]))

# ---------- 五类 precision / recall ----------
print(f"总样本数: {len(samples)}")
print("\nconfusion matrix (行=truth, 列=predicted):")
header = "truth\\pred " + "".join(f"{l[:4]:>8}" for l in LEVELS)
print(header)
for t in LEVELS:
    row = "".join(f"{matrix[t][p]:>8}" for p in LEVELS)
    print(f"{t[:16]:<16}{row}")
print("\n五类 precision / recall:")
for l in LEVELS:
    tp = matrix[l][l]
    truth_total = sum(matrix[l].values())
    pred_total = sum(matrix[t][l] for t in LEVELS)
    p = tp / pred_total if pred_total else None
    r = tp / truth_total if truth_total else None
    print(f"  {l:<16} truth={truth_total:>3} pred={pred_total:>3} "
          f"precision={p if p is None else round(p,3)} recall={r if r is None else round(r,3)}")

# ---------- 关键指标 ----------
def prec(level):
    tp = matrix[level][level]
    pred = sum(matrix[t][level] for t in LEVELS)
    return tp / pred if pred else None

print("\n关键指标:")
print(f"  CONTRADICTS precision: {prec('CONTRADICTS')}（盲测集真实 CONTRADICTS=0，"
      f"此值实际反映'误报率'：误判为 CONTRADICTS 共 {sum(matrix[t]['CONTRADICTS'] for t in LEVELS)} 条）")
print(f"  DIRECT_SUPPORT precision: {prec('DIRECT_SUPPORT')}")
print(f"  IRRELEVANT precision: {prec('IRRELEVANT')}")

# ---------- CRITICAL 级错误 ----------
crit_irr_direct = matrix["IRRELEVANT"]["DIRECT_SUPPORT"]
crit_irr_contra = matrix["IRRELEVANT"]["CONTRADICTS"]
print(f"\nCRITICAL 级错误: 无关Evidence→DIRECT_SUPPORT = {crit_irr_direct} 条；"
      f"无关Evidence→CONTRADICTS = {crit_irr_contra} 条")

# ---------- 错误分桶 ----------
err_qual, err_qtype, err_kw, err_cnnum, err_as_contra = 0, 0, 0, 0, 0
for i, truth, got, ct, title, url in misses:
    s = samples[i - 1]
    prof = _claim_profile(s["claim_text"])
    ev = s["evidence"]
    ev_plain = ev["title"] + ev["snippet"] + ev["text"]
    if got == "CONTRADICTS":
        err_as_contra += 1
    if prof["question"] or prof["step_def"]:
        err_qtype += 1
    if _qualifier_requirements(s["claim_text"]):
        err_qual += 1
    if truth in ("IRRELEVANT", "CONTEXT_ONLY") and got in ("DIRECT_SUPPORT", "PARTIAL_SUPPORT"):
        err_kw += 1
    if CN_NUM_RE.search(s["claim_text"]) or CN_NUM_RE.search(ev_plain):
        err_cnnum += 1

print("\n错误分桶（未命中样本中的归类，桶间可重叠）:")
print(f"  误判为 CONTRADICTS 数量: {err_as_contra}")
print(f"  问句/定义句误判数量: {err_qtype}")
print(f"  关键限定词相关错误数量: {err_qual}")
print(f"  纯关键词重叠误判（无关→支持）数量: {err_kw}")
print(f"  中文数字相关错误数量: {err_cnnum}")

print(f"\n未命中明细（共 {len(misses)} 条）:")
for i, truth, got, ct, title, url in misses:
    print(f"  [{i}] truth={truth} got={got} | claim={ct} | {title} | {url}")

# 判定结果落盘（供审计）
out = {"confusion_matrix": {t: dict(matrix[t]) for t in LEVELS},
       "misses": [{"idx": i, "truth": t, "got": g, "claim": c, "title": ti, "url": u}
                  for i, t, g, c, ti, u in misses]}
(ROOT / "projects" / "_drafts" / "r1_blind_eval.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print("\nwritten: projects/_drafts/r1_blind_eval.json")
