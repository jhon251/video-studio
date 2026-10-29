"""语义判定开发对照脚本：跑 50 样本，输出逐条 判定 vs 真值 + 特征，供规则迭代。"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from video_studio.tools.semantic_judge import judge_support  # noqa: E402

data = json.loads((ROOT / "tests" / "data" / "evidence_regression_r1.json").read_text(encoding="utf-8"))
hits = Counter()
cat_hits = Counter()
cat_total = Counter()
fails = []
for s in data["samples"]:
    got = judge_support(s["claim_text"], s["evidence"])
    truth = s["truth_label"]
    cat_total[s["category"]] += 1
    if got == truth:
        hits["hit"] += 1
        cat_hits[s["category"]] += 1
    else:
        hits["miss"] += 1
        fails.append((s["id"], s["category"], truth, got))

print(f"总计: {hits['hit']}/50 命中")
print("分类命中:")
for c in ("TRUE_DIRECT", "TRUE_PARTIAL", "TRUE_IRRELEVANT", "TRUE_CONTRADICT",
          "PSEUDO_CONTRADICT", "CONTEXT_ONLY", "KEYWORD_OVERLAP_IRRELEVANT"):
    print(f"  {c}: {cat_hits.get(c,0)}/{cat_total.get(c,0)}")
print("\n未命中样本:")
for sid, cat, truth, got in fails:
    print(f"  {sid} [{cat}] truth={truth} got={got}")
