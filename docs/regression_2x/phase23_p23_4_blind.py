# -*- coding: utf-8 -*-
"""P23-4 盲测包：v3 / v4 打乱并排 + 参照文本并列（真值 = 项目所有者）。"""
from __future__ import annotations

import hashlib
import json
import pathlib
import random
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import ai_flavor as AF                                    # noqa: E402

STYLE = R / "config" / "style_target_wangxiao_v1.md"
REFS = sorted((R / "config" / "human_style_refs").glob("*.txt"))
v3 = json.loads((L / "phase8_ab_v3.json").read_text(encoding="utf-8"))["script"]
v4 = json.loads((L / "phase23_v4_script.json").read_text(encoding="utf-8"))
rounds = json.loads((L / "phase23_rewrite_rounds.json").read_text(encoding="utf-8"))
ref_sigs = [AF.analyze(p.read_text(encoding="utf-8")) for p in REFS]

# 打乱：确定性（固定种子）⇒ 可复现；对照由 hash 记录，不在此文件明文亮明
rng = random.Random(23)
order = ["A", "B"]
rng.shuffle(order)
mapping = {order[0]: "v3", order[1]: "v4"}
texts = {"A": AF.script_text(v3 if mapping["A"] == "v3" else v4),
         "B": AF.script_text(v3 if mapping["B"] == "v3" else v4)}
sig = {k: AF.analyze(t) for k, t in texts.items()}
for k in sig:
    sig[k]["ai_flavor_score"] = AF.compare_to_reference(sig[k], ref_sigs)["ai_flavor_score"]
    sig[k]["retention"] = AF.retention_score(v3 if mapping[k] == "v3" else v4, None)

pack = {
    "schema": "phase23-blind-pack-v1",
    "stage": "Phase 23 P23-4 用户盲测验收（真值 = 项目所有者）",
    "instructions": {
        "q1": "哪一版更像目标机制（说书机制：从具体事实切入 / 态度外露 / 抽象概念紧跟世俗类比 / "
              "口语连接松弛 / 数据给人话翻译 / 故事线推进优先 / 保留留存骨架）？",
        "q2": "哪一版人味更重（更不像 AI 写的）？",
        "q3": "请圈出**仍有 AI 味**的句子（可写明「A 第 N 句」「B 第 N 句」或直接引句）。",
        "answer_format": "q1: A|B|持平；q2: A|B|持平；q3: 句子列表",
    },
    "criterion_frozen": {
        "pass": ("q1 与 q2 **都判 v4 或持平** + 机器信号同向（v4 ai_flavor 低于 v3）"
                 "+ 圈出句子**逐条处置**（信号可覆盖的修掉，覆盖不了的登记信号盲区 KNOWN_ISSUES）"),
        "fail": "未达标 ⇒ 带清单迭代一轮；仍不达标 ⇒ STOP 并转「人工执笔兜底路线」提案",
    },
    "texts": texts,
    "machine_signals": sig,
    "reference_texts": [{"path": str(p.relative_to(R)).replace("\\", "/"),
                         "text": p.read_text(encoding="utf-8")} for p in REFS],
    "style_target": {"path": str(STYLE.relative_to(R)).replace("\\", "/"),
                     "sha256": hashlib.sha256(STYLE.read_bytes()).hexdigest()},
    "machine_result": {
        "v3_ai_flavor": rounds["v3_baseline"]["ai_flavor_score"],
        "v4_ai_flavor": rounds["rounds"][-1]["ai_flavor_score"],
        "direction_consistent": bool(
            rounds["rounds"][-1]["ai_flavor_score"] < rounds["v3_baseline"]["ai_flavor_score"]),
        "v3_retention": rounds["v3_baseline"]["retention"]["score"],
    },
    "answer_key_sha256": hashlib.sha256(
        json.dumps(mapping, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest(),
    "_mapping_sha256_only": ("明文对照已由 answer_key_sha256 封存，验收后再公布对应关系；"
                             "本文件不直接泄露 A/B 对应 v3/v4 以免污染盲测。"),
    "provenance": rounds["provenance"],
    "limitation": rounds["limitation"],
}
# 明文对照写入**单独**文件（验收时使用）
(L / "phase23_blind_pack.json").write_text(
    json.dumps(pack, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
(L / "phase23_blind_answer_key.json").write_text(
    json.dumps({"mapping": mapping, "seeded": 23,
                "note": "验收前请勿查看；用于公布 A/B 与 v3/v4 的对应关系"},
               ensure_ascii=False, indent=1), encoding="utf-8")

print("盲测包 ->", (L / "phase23_blind_pack.json").relative_to(R).as_posix())
print("对照表 ->", (L / "phase23_blind_answer_key.json").relative_to(R).as_posix())
print()
print("机器侧结论：v3 ai_flavor {:.4f} → v4 {:.4f}（同向: {}）".format(
    rounds["v3_baseline"]["ai_flavor_score"], rounds["rounds"][-1]["ai_flavor_score"],
    pack["machine_result"]["direction_consistent"]))
print("参照文本并列: {} 份".format(len(REFS)))
print()
print("=" * 78)
print("【请做盲测】A 与 B 已打乱，请回答：")
print("  q1 哪版更像目标机制（说书机制）？  A / B / 持平")
print("  q2 哪版人味更重？                A / B / 持平")
print("  q3 圈出仍有 AI 味的句子（可写「A 第N句」）")
print("=" * 78)
for k in ("A", "B"):
    print()
    print("--- {} （前 240 字）---".format(k))
    print(texts[k][:240])
