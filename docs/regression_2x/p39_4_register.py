# -*- coding: utf-8 -*-
"""Phase 39 §3：登记 style_target v1.1（语域对齐节入册，sha 更新）+ v6.4 门禁小结。

决策树沿用（Phase 38 已登记，不再展期）。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
ST = R / "config" / "style_target_wangxiao_v1.md"
sys.stdout.reconfigure(encoding="utf-8")

sha = hashlib.sha256(ST.read_bytes()).hexdigest()
rec = {
    "schema": "p39-style-target-v11-register-v1",
    "stage": "Phase 39 语域对齐（v6.4 终稿候选）",
    "style_target": {
        "file": "config/style_target_wangxiao_v1.md",
        "version": "v1.1", "sha256": sha,
        "added_section": "机制 ⑧：语域对齐（该学术处学术、该大白话处大白话）",
        "rules": [
            "学术概念首现 ⇒ 学术口吻（精确陈述 + 年份/人物/头衔给足分量）",
            "家常类比只作**跟随解释**（说得家常点，就是……），不得作为出场方式",
            "不得自我解构：删「看着挺家常」「新鲜事」类元评论（新鲜事限过渡句）",
            "过渡/态度/反应句 ⇒ 大白话（保留）",
            "两语域不得同段内连续对撞（学术陈述后紧跟自嘲式降维 = 违规）",
            "例外：概念句后紧跟精确陈述时，前置轻类比可保留（四色定理听着像个智力游戏）",
        ],
    },
    "prescriptions_applied": {
        "count": 4, "missed": 0, "llm_cost_usd": 0.0,
        "items": [
            {"rx": "1", "para": "P05", "what": "段5 开头整段替换（学术首现 + 跟随式家常解释）"},
            {"rx": "2", "para": "P07", "what": "学术口吻 + 菲尔兹奖头衔给足（守恒并集有据：v4.1 原文）"},
            {"rx": "4A", "para": "P07", "what": "§0 自检：删元评论「新鲜事」"},
            {"rx": "4D", "para": "P07", "what": "§0 自检：头衔已给足 ⇒ 段末泛称「一位顶尖数学家」改回指代词"},
        ],
    },
    "register_selfcheck": {
        "collisions": 0,
        "rule": "学术陈述后紧跟自嘲式降维 = 违规",
        "discretionary_note": (
            "P01「像把一整片沙漠筛成几堆沙——说白了，天底下所有地图，不管多花，都能归进这么几类」："
            "监理处方 1 把「说白了…」**并入了该句逗号后**，形成「类比喻 + 自评式降维」同一句。"
            "严格按 §0「不得自我解构」可判违规，但把「说白了」移到句首属**重新定位监理处方文本**，"
            "超出「只许机械替换」授权 ⇒ **未自行改动**，提交监理裁定。"),
    },
    "gates_v64": {
        "数字/实体守恒": "PASS（0 新增；派生「1%」已登记）",
        "fact_risks": "PASS（15）",
        "元叙述黑名单": "PASS（0）",
        "报幕式段首": "PASS（0）",
        "句中切分": "PASS（0）",
        "钩子链": "PASS（8/8，BROKEN=0）",
        "n_gram_vs_reference": "PASS（0）",
        "mean_sentence_len": "PASS（27.84 ≤ 28）",
        "长度": "3,461 字 ⇒ 保守 706s / 实测口径 649s（判定用实测口径）",
        "信号 k": "PASS（未落地 1 ≤3；密度 0.0088 ≤0.03）",
        "比喻配额门": "**3 FAIL（非本方引入）**：M1b 沙漠筛沙残留 / M2 白名单名目 6>5 / M4 明喻 1",
    },
    "unresolved_from_p38": [
        {"id": "P38-C1", "what": "处方 §0-1 与黑名单 §1 自相矛盾（沙漠筛沙：仅给了后半替换文本）",
         "need": "请给出前半替换文本，或确认保留"},
        {"id": "P38-C2", "what": "白名单清单 6 项 vs 阈值「≤5」自相矛盾",
         "need": "请裁定放宽到 ≤6，或指定删除哪一项"},
    ],
    "decision_tree": "沿用 Phase 38 登记（A 通过→TTS/切景/渲染/第四部候选；"
                     "B 不对味→冻结本篇，人工执笔或换题材；不再展期）",
    "budget": {"llm_usd": 0.0, "network": 0},
}
(L / "phase39_style_target_v11.json").write_text(
    json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
print("style_target v1.1 sha256 =", sha)
print("处方套用 {} 条（未命中 0）| 语域对撞 {} 处 | LLM $0".format(
    rec["prescriptions_applied"]["count"], rec["register_selfcheck"]["collisions"]))
print("比喻配额门仍 3 FAIL（P38 两处冲突未裁定）")
print("-> " + str((L / "phase39_style_target_v11.json").relative_to(R)))
