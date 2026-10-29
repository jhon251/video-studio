# -*- coding: utf-8 -*-
"""P36-1：**九拍节表**（先出节表再出文）。

每拍 = {事件, 出场人物, 留下的钩子问题}；**钩子问题必须被下一拍的段首直接承接**。
落盘 `logs/phase36_beatsheet.json`。
"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")

BEATS = [
    {"id": "B1", "title": "1977：一份没有签字的证明",
     "event": ("1977 年 Appel 和 Haken 宣布证出四色定理。他们必须把无穷多种地图归约成"
               "有限多种构型，再让程序一种一种跑过去——归约是纸笔的硬活，检查是机器的活。"),
     "cast": ["Appel", "Haken"],
     "hook": "这份证明站得住，靠的是程序跑完没报错——可它没有一个人类的签字。"},
    {"id": "B2", "title": "凭什么信：问题成立",
     "event": ("期刊找不到人签『我全看过了』，稿子压了很久。数学的可信度一向靠同行"
               "逐步跟着走完；这里这一条第一次落空。"),
     "cast": ["（期刊与审稿人，匿名）"],
     "hook": "那么『凭什么信』这道题，第一次不是修辞，而是真的空在那儿。"},
    {"id": "B3", "title": "Tymoczko：把地基换掉",
     "event": ("1979 年哲学家 Thomas Tymoczko 把四色定理当成哲学事件：接受它，等于承认"
               "证明的规矩里可以划掉『人能一步步跟着走完』。"),
     "cast": ["Thomas Tymoczko"],
     "hook": "可要是这条规矩真能划掉，数学还剩下什么在撑着？"},
    {"id": "B4", "title": "单群反驳：僵局",
     "event": ("1980 年 Detlefsen 和 Luker 反驳：数学史上本就有谁也读不完的证明，"
               "有限单群分类就是几百位数学家的论文拼起来的，靠分工与互相引用撑着。"),
     "cast": ["Detlefsen", "Luker"],
     "hook": "两边谁也说服不了谁——那么这条线往前走，会出现第一份被完全验证的证明吗？"},
    {"id": "B5", "title": "开普勒猜想：99% 是什么东西",
     "event": ("1998 年 Thomas Hales 证出开普勒猜想，同样计算机辅助。审稿人没法完全确认，"
               "Hales 转述为大约『99% 确定』——是审稿人事后的说法，不是审稿报告原话。"),
     "cast": ["Thomas Hales"],
     "hook": "99% 听着接近满分，可数学要的是没有洞——那剩下的 1% 后来怎么了？"},
    {"id": "B6", "title": "Hales 的十六年：顶点",
     "event": ("Hales 没有停在『反正大家接受了』：他带项目把证明写成机器可完全检查的形式"
               "（Flyspeck），2014 年完成。从 99% 到完全形式化，中间隔了十六年。"),
     "cast": ["Thomas Hales"],
     "hook": ("十六年不是学术毅力故事——它逼出一个更根本的问题："
               "要机器检查，人得先把话说成机器听得懂的。"),
     },
    {"id": "B7", "title": "Lean 折进 LTE：机器开始接活儿",
     "event": ("形式化的工具最常被提到的是 Lean 与它的数学库 mathlib（**不单独成段**）。"
               "2020 年 Peter Scholze 把自己的新结果公开交给 Lean 验证（Liquid Tensor "
               "Experiment），2022 年 Kevin Buzzard 宣布完成。这一次是人类数学家主动"
               "请机器挑刺。"),
     "cast": ["Peter Scholze", "Kevin Buzzard", "Lean", "mathlib",
              "Liquid Tensor Experiment"],
     "hook": "请机器挑刺，是审查工具变强了——可要是机器开始自己写证明呢？"},
    {"id": "B8", "title": "AlphaGeometry：反转",
     "event": ("2024 年 DeepMind 的 AlphaGeometry 发表在《Nature》，做 2000–2022 年"
               "IMO 几何题（关键是图里那条没人告诉你的辅助线）。同年 AlphaProof 与 "
               "AlphaGeometry 2 在赛后用官方题目做 IMO 2024，六题做出四题。"
               "两次实验严格区分；银牌是按分数换算的说法，不是进场参赛。"),
     "cast": ["DeepMind", "AlphaGeometry", "AlphaProof", "IMO", "Nature"],
     "hook": "机器从检查者变成了出题者——那『凭什么信』这一问，还问得动吗？"},
    {"id": "B9", "title": "三代封条 + CTA（冷收）",
     "event": ("封条换过三代：先是人读过头，然后是机器跑得完，现在是机器自己写得出来。"
               "同一个结论摆在那里，信它的理由换了三回。这个转向要是走完，"
               "剩下的活儿并不轻松。"),
     "cast": [],
     "hook": ("冷收 + 片尾 CTA：「你要是手上有不一样的一手材料，发出来，比点赞有用。」"),
     },
]

# ---- 报幕式段首黑名单（授权书 §1①「同族」）----
ANNOUNCE_BLACKLIST = [
    "换个场景", "最能说明", "现在最常被提到", "接下来", "下面", "最后说", "再说一个",
    "回到", "说回", "我们来看", "让我们", "先说", "另外一件事", "同一时间", "同一年",
    "值得注意的是", "首先要说", "值得一提的是",
]
# 澄清拍（授权书 §1②：降级为插入语或押后，正文每段至多 1 处且须顺嘴）
CLARIFY_MARKERS = ["指的纯粹是", "严格说", "准确说", "这里要说明", "需要说明的是",
                   "也就是说", "换句话说", "顺带说", "得说清楚"]


def main() -> int:
    sheet = {
        "schema": "p36-beatsheet-v1",
        "stage": "Phase 36 P36-1 九拍节表（先出节表再出文）",
        "spine_question": "凭什么信（一份没人读过的证明，凭什么算证明）",
        "rule": ("每拍末句必须是**钩子问题**（问题/反常/未决），"
                 "且**必须被下一拍段首直接承接**；末拍（B9）除外，冷收 + CTA。"),
        "beats": BEATS,
        "announce_blacklist": ANNOUNCE_BLACKLIST,
        "clarify_markers": CLARIFY_MARKERS,
        "structural_rules": [
            "① 全文禁止报幕式段首（黑名单 + 同族）",
            "② 澄清拍降级为插入语或押后；正文每段至多 1 处且须顺嘴",
            "③ Lean/mathlib **不单独成段**，作为 LTE 情节要素带出",
            "④ 每段末句必须是钩子；末段除外（冷收 + CTA）",
        ],
        "fact_base": "v5.2（Phase 35）为事实底账；数字/实体 ⊆ v5.2 ∪ 历史并集",
    }
    L.mkdir(parents=True, exist_ok=True)
    (L / "phase36_beatsheet.json").write_text(
        json.dumps(sheet, ensure_ascii=False, indent=1), encoding="utf-8")
    print("九拍节表：")
    for b in BEATS:
        print("  {} {} | 人物: {} ".format(b["id"], b["title"], "、".join(b["cast"]) or "—"))
        print("      钩子: {}".format(b["hook"][:78]))
    print()
    print("报幕黑名单 {} 条 | 澄清标记 {} 条".format(
        len(ANNOUNCE_BLACKLIST), len(CLARIFY_MARKERS)))
    print("-> " + str((L / "phase36_beatsheet.json").relative_to(R)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
