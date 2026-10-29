"""Stage 5 dev 集人工标注落盘（标注先行，之后才允许用于 few-shot/开发）。

样本来源：s5_dev_collection.json（第三轮 Tavily 独立检索）+ 4 条第一轮未使用历史 Evidence。
标准：docs/证据语义回归基准.md 五类语义 + Stage 5 清单口径。
"""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DIRECT = {"D029"}          # 算力/散热成本：YouTube 散热产业（算力/功耗1000瓦/兆元产业）
PARTIAL = {"D001", "D002", "D003", "D006", "D007", "D008", "D009", "D010",
           "D017", "D023", "D026", "D032", "D035", "D036", "D038", "D043",
           "D051", "D052", "D053", "D060"}
CONTEXT = {"D005", "D018", "D024", "D054"}
CONTRADICT = set()

labels = {}
for i in range(1, 62):
    did = f"D{i:03d}"
    if did in DIRECT:
        labels[did] = "DIRECT_SUPPORT"
    elif did in PARTIAL:
        labels[did] = "PARTIAL_SUPPORT"
    elif did in CONTEXT:
        labels[did] = "CONTEXT_ONLY"
    elif did in CONTRADICT:
        labels[did] = "CONTRADICTS"
    else:
        labels[did] = "IRRELEVANT"

out = {
    "_meta": {
        "name": "s5_dev_labels",
        "note": "Stage 5 dev 集人工标注（先行冻结）。dev 与 197 冻结集无重叠（URL 已排除）。"
                "CONTRADICTS=0：第三轮检索未出现对可验证命题的真实否定。",
    },
    "labels": labels,
}
path = ROOT / "projects" / "_drafts" / "s5_dev_labels.json"
path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print("written:", path, "| distribution:", dict(Counter(labels.values())))
