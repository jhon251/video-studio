# -*- coding: utf-8 -*-
"""Phase 39：**v6.4 = 语域对齐**（监理处方 + §0 规则自检；纯机械替换，LLM $0）。

§0 新规则（入册 style_target v1.1）：
  · 学术概念首现 ⇒ **学术口吻**（精确陈述 + 年份/人物/头衔给足分量）；
    家常类比只作**跟随解释**（"说得家常点，就是……"），**不得作为出场方式**、
    **不得自我解构**（删「看着挺家常」「新鲜事」类元评论；「新鲜事」限过渡句）。
  · 过渡/态度/反应句 ⇒ **大白话**（保留）。
  · 两语域**不得同段内连续对撞**（学术陈述后紧跟自嘲式降维 = 违规）。
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import ai_flavor as AF                                   # noqa: E402

V63 = R / "output/p36_script/v6_3_fulltext.json"
V64 = R / "output/p36_script/v6_4_fulltext.json"
L = R / "docs" / "regression_2x" / "logs"

# ---- 处方 1：段5 开头整段替换（本片 P05）----
RX1_OLD = ("第一份被完全验证的证明，还得再等，这条线先绕到一堆橘子上。"
           "开普勒猜想说的是球怎么堆才最密。水果摊上堆橘子，怎么码放最省地方，"
           "这事看着挺家常。1611 年它被提出来，几百年里大家都觉得是对的。"
           "可没人证得出来。")
RX1_NEW = ("第一份被完全验证的证明，还得再等。这个坎，很快在另一个老问题身上又出现了"
           "一遍。开普勒猜想，1611 年提出：一堆球，怎么堆才最密。说得家常一点，就是"
           "水果摊上码橘子，怎么码最省地方。几百年里大家都觉得它是对的，可没人证得出来。")

# ---- 处方 2：段7（P07）学术口吻 + 头衔给足 ----
RX2_OLD = ("他是 Peter Scholze，手上那份东西是一份刚做出来的人类风格证明，"
           "里面堆着不少「显然」；")
RX2_NEW = ("来的人叫 Peter Scholze，菲尔兹奖得主。他手上是一份刚做出来的证明，"
           "人类风格的证明，里面堆着不少「显然」；")

# ---- 处方 4：§0 自检发现的违规处（**逐条登记**）----
# 违规 A：P07「2020 年，数学界出了件新鲜事」——「新鲜事」为**元评论**，
#         且此处**不是过渡句开头**（本段首句即学术事件首现）⇒ 判违规，删除元评论。
SELF_A_OLD = "2020 年，数学界出了件新鲜事：一位顶尖数学家主动把自己的证明送上了机器。"
SELF_A_NEW = "2020 年，一位顶尖数学家主动把自己的证明送上了机器。"
# 违规 B：P05「水果摊上堆橘子……看着挺家常」——已在处方 1 中由监理新句消除
#         （改为「说得家常一点，就是……」的**跟随解释**）⇒ 无需另改。
# 违规 C：P03「数学跟别的学科不太一样。」属**过渡句** ⇒ 大白话，合规，不动。


def sents(t):
    return [s.strip() for s in re.split(r"(?<=[。！？])", t) if s.strip()]


def main() -> int:
    d = json.loads(V63.read_text(encoding="utf-8"))
    ps = {p["id"]: p for p in d["paragraphs"]}
    applied, missed = [], []
    RX = [("1", "P05", RX1_OLD, RX1_NEW, "段5 开头整段替换（学术首现 + 跟随式家常解释）"),
          ("2", "P07", RX2_OLD, RX2_NEW, "段7 学术口吻 + 菲尔兹奖头衔给足"),
          ("4A", "P07", SELF_A_OLD, SELF_A_NEW, "§0 自检：删元评论「新鲜事」"),
          # 违规 D（§0 自检）：处方 2 已把身份精确为「菲尔兹奖得主」，
          # 但段末仍留着**笼统降维**的「一位顶尖数学家」⇒ 同段内头衔与泛称重复
          # （且与「给足分量」相悖）。按 §0「只动违规处」改为回指代词，不删事实。
          ("4D", "P07", "记住这件事：一位顶尖数学家，主动请机器来挑自己的刺。",
           "记住这件事：他主动请机器来挑自己的刺。",
           "§0 自检：头衔已给足 ⇒ 段末泛称改回指代词")]
    for tag, pid, old, new, why in RX:
        t = ps[pid]["text"]
        if old in t:
            ps[pid]["text"] = t.replace(old, new, 1)
            applied.append({"rx": tag, "para": pid, "why": why,
                            "old": old[:50], "new": new[:50]})
        else:
            missed.append({"rx": tag, "para": pid, "old": old[:70]})

    # ---- §0 自检：语域对撞探测（学术陈述后紧跟自嘲式降维）----
    # 探测面：同段内「正式概念句」后**紧邻**「降维词」（看着挺/挺家常/说白了/新鲜事/其实）
    DOWNGRADE = ["看着挺", "挺家常", "说白了", "新鲜事", "也谈不上", "没什么"]
    REGISTER_FORMAL = ["定理", "猜想", "证明", "形式化", "验证", "归约", "构型",
                       "认识论", "可检视", "共同体", "定义问题"]
    collision = []
    for p in d["paragraphs"]:
        ss = sents(p["text"])
        for i in range(len(ss) - 1):
            if any(f in ss[i] for f in REGISTER_FORMAL) and any(
                    dg in ss[i + 1] for dg in DOWNGRADE):
                collision.append({"para": p["id"], "formal": ss[i][:40],
                                  "downgrade": ss[i + 1][:40]})
    d["schema"] = "script-output-v4-p39-v64"
    d["_meta"] = dict(d.get("_meta") or {})
    d["_meta"].update({
        "version": "v6.4",
        "revision_basis": "Phase 39 授权书：语域对齐（§0 规则入册 style_target v1.1 + 监理处方）",
        "prescriptions_applied": applied, "prescriptions_missed": missed,
        "register_selfcheck": {"downgrade_words": DOWNGRADE,
                               "formal_words": REGISTER_FORMAL,
                               "collisions": collision,
                               "rule": "学术陈述后紧跟自嘲式降维 = 违规"},
        "style_target_version": "v1.1（语域对齐节）",
        "style_target_sha256": "3B8F7B6937E5157EE8FE63D9E4DE3B4DDCA133ACB9FF27EEAD3FD7692A27C736",
        "zero_llm": True,
    })
    V64.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")

    text = "\n".join(p["text"] for p in d["paragraphs"])
    a = AF.analyze(text)
    chars = len(re.sub(r"\s", "", text))
    print("处方/自检套用 {} 条 | 未命中 {} 条".format(len(applied), len(missed)))
    for x in applied:
        print("  OK  {} {} | {}".format(x["rx"], x["para"], x["why"]))
    for x in missed:
        print("  MISS {} {} | {}".format(x["rx"], x["para"], x["old"][:64]))
    print()
    print("语域对撞探测：{} 处".format(len(collision)))
    for c in collision:
        print("    ! {} | 正式: {} | 降维: {}".format(
            c["para"], c["formal"][:30], c["downgrade"][:30]))
    print()
    print("v6.4: {} 字 | 保守 {:.0f}s / 实测口径 {:.0f}s | mean={:.2f} | 推进词={}".format(
        chars, chars / 4.9, chars / 5.33, a["mean_sentence_len"],
        a["advance_marker_count"]))
    print("-> " + str(V64.relative_to(R)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
