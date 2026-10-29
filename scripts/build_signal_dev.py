"""Stage 7 独立信号测试集（label-first）：dev v2 样本 + 信号级 truth 标注。

信号 truth 标注规则（全部先行落盘）：
- IRRELEVANT → topic=F, proposition=F, s/o/p=F, cand=F, scope=context
- CONTEXT_ONLY → topic=T, proposition=F, s/o/p=F, cand=F
- DIRECT → topic=T, proposition=T, s/o/p=T, cand=F
- CONTRADICTS → topic=T, proposition=T, s/o/p=T, cand=T, scope=人工逐条标注
- PARTIAL → 人工逐条标注（topic/proposition/s/o/p/cand）
限定词/数字项的 truth = 规则侧原文存在性 oracle（自动，不入 truth 文件）。
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
dev = json.loads((ROOT / "projects" / "_drafts" / "s5_dev_v2_collection.json").read_text(encoding="utf-8"))["samples"]

SCOPE = {  # CONTRADICTS 样本否定落点（人工逐条）
    "DC-01": "predicate", "DC-02": "predicate", "DC-03": "predicate",
    "DC-04": "object", "DC-05": "predicate", "DC-06": "predicate",
    "DC-07": "predicate", "DC-08": "number",
}
PARTIAL_SIGNALS = {  # PARTIAL 样本人工逐条：id -> (topic, prop, s, o, p, cand)
    "D001": (1, 0, 1, 0, 0, 0), "D002": (1, 0, 1, 0, 0, 0), "D003": (1, 0, 1, 0, 0, 0),
    "D006": (1, 1, 1, 1, 1, 0), "D007": (1, 1, 1, 1, 1, 0), "D008": (1, 0, 1, 0, 0, 0),
    "D009": (1, 1, 1, 1, 1, 0), "D010": (1, 1, 1, 1, 1, 0), "D017": (1, 1, 1, 1, 1, 0),
    "D023": (1, 1, 1, 1, 1, 0), "D026": (1, 0, 1, 0, 0, 0), "D032": (1, 1, 1, 1, 0, 0),
    "D035": (1, 1, 1, 1, 1, 0), "D036": (1, 1, 1, 1, 1, 0), "D038": (1, 1, 1, 1, 1, 0),
    "D043": (1, 1, 1, 0, 1, 0), "D051": (1, 0, 1, 0, 0, 0), "D052": (1, 1, 1, 1, 0, 0),
    "D053": (1, 1, 1, 1, 1, 0),
}

labels = {}
for s in dev:
    sid, truth = s["id"], s["truth"]
    if truth == "IRRELEVANT":
        labels[sid] = {"topic": False, "prop": False, "s": False, "o": False, "p": False,
                       "cand": False, "scope": "context"}
    elif truth == "CONTEXT_ONLY":
        labels[sid] = {"topic": True, "prop": False, "s": False, "o": False, "p": False,
                       "cand": False, "scope": "context"}
    elif truth == "DIRECT_SUPPORT":
        labels[sid] = {"topic": True, "prop": True, "s": True, "o": True, "p": True,
                       "cand": False, "scope": "context"}
    elif truth == "CONTRADICTS":
        labels[sid] = {"topic": True, "prop": True, "s": True, "o": True, "p": True,
                       "cand": True, "scope": SCOPE[sid]}
    elif truth == "PARTIAL_SUPPORT":
        t, pr, ss, oo, pp, cc = PARTIAL_SIGNALS[sid]
        labels[sid] = {"topic": bool(t), "prop": bool(pr), "s": bool(ss), "o": bool(oo),
                       "p": bool(pp), "cand": bool(cc), "scope": "context"}

out = {
    "_meta": {"name": "evidence_signal_dev",
              "note": "Stage 7 信号级独立测试集：dev v2 全部 72 样本；truth 为信号级标注（先行落盘）。"
                      "限定词/数字项的 truth 由规则侧原文存在性 oracle 提供（不入本文件）。"
                      "与冻结 197 无重叠。"},
    "labels": labels,
}
(ROOT / "tests" / "data" / "evidence_signal_dev.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
from collections import Counter
print("written. samples:", len(labels))
print("cand=true 样本:", sum(1 for v in labels.values() if v["cand"]))
print("topic=false 样本:", sum(1 for v in labels.values() if not v["topic"]))
