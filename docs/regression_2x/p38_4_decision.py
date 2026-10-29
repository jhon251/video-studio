# -*- coding: utf-8 -*-
"""Phase 38 §3：**终局决策树登记**（在案，不再展期）+ v6.3 处方/门禁小结。"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")

rec = {
    "schema": "p38-final-decision-tree-v1",
    "stage": "Phase 38 v6.3 去文青（监理逐句处方套用）+ 比喻配额门",
    "generated_at_note": "登记在案，不再展期（授权书 §3）",
    "prescriptions": {
        "applied": 8, "missed": 0, "llm_cost_usd": 0.0,
        "note": "纯机械字面替换，无生成；未命中 0 条",
    },
    "quota_gate": {
        "test": "tests/metaphor_quota_test.py",
        "result": "3 PASS / 3 FAIL",
        "fails": [
            {"id": "M1b", "what": "黑名单近义变体残留",
             "detail": "「像把一整片沙漠筛成几堆沙」仍在 P01；"
                       "授权书 §1 把「沙漠筛沙」列入**黑名单词条**，"
                       "但 §0 处方 1 的替换文本只改了该句**后半**，未给前半的替换文本",
             "conflict": "处方 §0-1 与黑名单 §1 自相矛盾",
             "not_self_corrected_because": "禁止自由发挥 / 只许机械替换 ⇒ 未擅自改写监理未指定的字"},
            {"id": "M2", "what": "白名单名目数 6 > 5",
             "detail": "监理第 7 条**列了 6 个名目**（封条 / 公共标准件 / 请机器挑刺 / "
                       "水果摊橘子 / 割肉级别 / 手指头酸），第 1 节却写「白名单 ≤5」",
             "conflict": "清单与阈值自相矛盾",
             "not_self_corrected_because": "删减任一白名单项都超出处方授权"},
            {"id": "M4", "what": "非白名单明喻 1 处",
             "detail": "同上 M1b 的同一句（沙漠筛沙）被明喻探测命中",
             "conflict": "M1b 的派生结果",
             "not_self_corrected_because": "同上"},
        ],
    },
    "other_gates_v63": {
        "数字/实体守恒": "PASS（0 新增；派生「1%」已登记）",
        "fact_risks": "PASS（15 条）",
        "元叙述黑名单": "PASS（0）",
        "报幕式段首": "PASS（0）",
        "句中切分": "PASS（0）",
        "钩子链": "PASS（8/8，BROKEN=0）",
        "n_gram_vs_reference": "PASS（0）",
        "mean_sentence_len": "28.07（软门 28，**超 0.07**；处方替换本身增加了字数）",
        "长度": "3,459 字 ⇒ 保守 706s / 实测口径 649s（判定用实测口径，见 P37 交底）",
        "信号 k": "PASS（未落地 1 ≤3；密度 0.0089 ≤0.03）",
    },
    "final_decision_tree": {
        "branch_A": {"if": "v6.3 通过（用户回「文本通过」）",
                     "then": "P36-4/5：段落级 TTS → 静音吸附切景（句中切分=0）→ "
                             "全门渲染（no_picture/DQ-2 share+间距/DQ-3/一致性门）→ "
                             "登记第四部交付级候选 → 材料包 v4 + 全量回归"},
        "branch_B": {"if": "v6.3 仍不对味",
                     "then": "本题材文本**冻结**（候选线保留），二选一：",
                     "B1": "人工执笔（项目所有者口述要点，AI 仅排版与事实核对）",
                     "B2": "换题材（从 signals 快照挑故事性强的），五轮工艺经验继承"},
        "no_extension": True,
    },
    "budget": {"llm_usd": 0.0, "note": "本轮纯机械，无 LLM 调用；网络 0（池 17 张已裁定接受）"},
}
(L / "phase38_final_decision_tree.json").write_text(
    json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
print("处方 {} 条已套用（未命中 0）｜ LLM $0".format(rec["prescriptions"]["applied"]))
print("比喻配额门：{}".format(rec["quota_gate"]["result"]))
for f in rec["quota_gate"]["fails"]:
    print("  {} {} ⇒ {}".format(f["id"], f["what"], f["conflict"]))
print()
print("终局决策树已登记：A = 通过则配音渲染；B = 冻结本篇（B1 人工执笔 / B2 换题材）")
print("-> " + str((L / "phase38_final_decision_tree.json").relative_to(R)))
