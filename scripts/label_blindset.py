"""阶段 2 盲测：人工 truth label 落盘（先标注、后判定，labels 先行于 eval）。

标注依据（docs/证据语义回归基准.md 标准）：主体/谓词/对象/关键限定词一致性；
问句/定义句/叙事句不可判反驳；关键词重叠≠支持；数字/年份/机构等限定词必须背书。
样本全部来自 projects/_drafts/r1_blind_collection.json（Tavily 第二轮独立检索，未修改文本）。
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 人工标注（索引 = 标注视图中的 [n]）
DIRECT = {37, 56, 57, 81}
PARTIAL = {1, 2, 3, 4, 10, 11, 26, 27, 28, 29, 35, 36, 38, 39, 40, 41, 42, 43,
           49, 50, 51, 52, 66, 67, 96, 97, 98, 99, 102, 113, 114, 115, 119, 120}
CONTEXT = {5, 6, 7, 8, 9, 44, 45, 46, 78, 79, 80, 91, 107, 109}
CONTRADICT = set()

labels = {}
for i in range(1, 122):
    if i in DIRECT:
        labels[str(i)] = "DIRECT_SUPPORT"
    elif i in PARTIAL:
        labels[str(i)] = "PARTIAL_SUPPORT"
    elif i in CONTEXT:
        labels[str(i)] = "CONTEXT_ONLY"
    elif i in CONTRADICT:
        labels[str(i)] = "CONTRADICTS"
    else:
        labels[str(i)] = "IRRELEVANT"

out = {
    "_meta": {
        "name": "blind_set_r1_second_search",
        "source": "projects/_drafts/r1_blind_collection.json（Tavily 第二轮独立检索，与第一轮同查询）",
        "note": "人工 truth label 先行落盘，semantic_judge 规则在本阶段全程冻结；"
                "CONTRADICTS 标注为 0 条：第二轮检索结果中未出现对可验证命题的真实否定",
    },
    "labels": labels,
}
path = ROOT / "projects" / "_drafts" / "r1_blind_labels.json"
path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
from collections import Counter
print("labels written:", path)
print("distribution:", dict(Counter(labels.values())))
