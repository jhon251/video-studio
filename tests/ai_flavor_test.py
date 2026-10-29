# -*- coding: utf-8 -*-
"""Phase 23 测试：AI 味信号层（`core/ai_flavor.py`）—— 确定性、离线、零 LLM。

覆盖：信号计算 / 中文数字归一 / 数字保真 / 实体保真（含**描述性引语不误判**）/
n-gram 守卫（含"抄参照即命中"）/ retention 机械层 / 综合分方向性（正向偏离）。
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import ai_flavor as AF                                    # noqa: E402

FAILS, N = [], [0]


def check(name, cond, detail=None):
    N[0] += 1
    if cond:
        print("PASS ", name)
    else:
        print("FAIL ", name, "|", detail)
        FAILS.append(name)


AI_TEXT = ("换句话说，这个问题的关键在于形式化程度。值得注意的是，其实并不是规模的问题"
           "而是标准的问题：首先，我们需要重新理解证明；其次，我们需要接受机器的角色；"
           "最后，我们需要反思数学共同体的定义。为什么呢？因为标准本身在变。"
           "严格来说，必须指出，某种意义上这构成了一次让步。")
HUMAN_TEXT = ("这萝卜咋没见你吃啊。我不爱吃萝卜。为啥不爱吃。萝卜有营养。"
              "我辛辛苦苦给你做的，你不吃啊。行不行。哦对哦。孩子嘛缺心少肺。"
              "很快会忘。哪有完整的情绪啊。哇哇哇。")
REF = "很多父母和孩子沟通更像是在驯化动物\n诶\n这萝卜咋没见你吃啊\n我不爱吃萝卜\n"

# ---------- 1. 信号方向性 ----------
sa, sh = AF.analyze(AI_TEXT), AF.analyze(HUMAN_TEXT)
check("1 AI 文本推进词密度 > 人味文本",
      sa["advance_marker_density"] > sh["advance_marker_density"],
      (sa["advance_marker_density"], sh["advance_marker_density"]))
check("1b AI 文本命中「不是A而是B」构式", sa["not_a_but_b_count"] >= 1)
check("1c AI 文本命中设问自答", sa["rhetorical_qa_count"] >= 1)
check("1d AI 文本命中限定语堆叠", sa["hedge_stack_count"] >= 1)
check("1e AI 文本冒号+展开 > 人味文本", sa["colon_expand_rate"] > sh["colon_expand_rate"])
check("1f 人味文本无推进词", sh["advance_marker_count"] == 0, sh["advance_marker_hits"])
check("1g analyze 的 ai_flavor_score 为 None（需参照均值）", sa["ai_flavor_score"] is None)

# ---------- 2. 中文数字归一 ----------
for cn, want in (("十", 10), ("二十三", 23), ("一百", 100), ("两千", 2000), ("三万", 30000)):
    check("2 中文数字归一 {} == {}".format(cn, want), AF._cn_num(cn) == want,
          AF._cn_num(cn))
nums = AF.numbers("1977 年和 二十 个字与 99%")
check("2b numbers 抽取阿拉伯+中文",
      "1977" in nums["arabic"] and "20" in nums["chinese_normalized"], nums)

# ---------- 3. 数字保真 ----------
nf = AF.number_fidelity("1977 年是 99%", "1977 年是 99%，共 20 人")
check("3 数字丢失 ⇒ 记入 missing_in_v4",
      ("20" in nf["missing_in_v4"]) and nf["extra_in_v4"] == [], nf)
nf2 = AF.number_fidelity("1977 年 99% 和 20 人", "1977 年是 99%，共 20 人")
check("3b 数字齐全 ⇒ preserved True", nf2["preserved"] is True, nf2)
nf3 = AF.number_fidelity("1977 年 2024 年", "1977 年")
check("3c 新增数字 ⇒ preserved False", nf3["preserved"] is False and "2024" in nf3["extra_in_v4"])

# ---------- 4. 实体保真（含描述性引语不误判）----------
ent = AF.ner_entities("Tymoczko 在《哲学杂志》上写了「被读完并被理解」这句话，四色定理很重要")
check("4 拉丁实体被识别", any("Tymoczko" == x for x in ent["latin"]), ent["latin"])
check("4b 含专名后缀的引号内容被识别",
      any("哲学杂志" in x for x in ent["cjk_org"]) or "哲学杂志" in ent["quoted"], ent)
check("4c **纯中文描述性引语不被当实体**（关键修正）",
      "被读完并被理解" not in ent["all"], ent["all"])
ef = AF.entity_fidelity("Tymoczko 说了话", "Tymoczko 在《哲学杂志》上说了话")
check("4d 实体丢失 ⇒ preserved False", ef["preserved"] is False, ef["lost_in_v4"])

# ---------- 5. n-gram 守卫 ----------
ng_same = AF.longest_common_ngram("这萝卜咋没见你吃啊我不爱吃萝卜", REF, n=8)
check("5 抄参照 ⇒ 守卫命中", ng_same["violated"] is True, ng_same)
ng_diff = AF.longest_common_ngram("完全不相干的另一段文字内容在这里出现", REF, n=8)
check("5b 不抄 ⇒ 守卫不命中", ng_diff["violated"] is False, ng_diff)
check("5c 空文本安全", AF.longest_common_ngram("", REF)["violated"] is False)

# ---------- 6. retention 机械层 ----------
script = {"segments": [{"narration": "a", "emotion_beat": "x"},
                       {"narration": "b", "emotion_beat": "y"}],
          "hook_map": [{"at_segment": 1}, {"at_segment": 2}],
          "cta_plan": [{"at_segment": 2}]}
r = AF.retention_score(script, None)
check("6 retention 全覆盖 == 1.0", abs(r["score"] - 1.0) < 1e-9, r)
check("6b hook 越界不计入", AF.retention_score(
    {"segments": [{"narration": "a"}], "hook_map": [{"at_segment": 9}],
     "cta_plan": []}, None)["hooks_in_range"] == 0)

# ---------- 7. 综合分：正向偏离（优于参照不扣分）----------
refs = [AF.analyze(HUMAN_TEXT), AF.analyze(REF)]
s_ai = AF.compare_to_reference(AF.analyze(AI_TEXT), refs)
s_h = AF.compare_to_reference(AF.analyze(HUMAN_TEXT), refs)
check("7 AI 文本分 > 人味文本分", s_ai["ai_flavor_score"] > s_h["ai_flavor_score"],
      (s_ai["ai_flavor_score"], s_h["ai_flavor_score"]))
check("7b 正向偏离无负值（优于参照不扣分）",
      all(v >= 0 for v in s_h["positive_deviation"].values()), s_h["positive_deviation"])
check("7c 权重表与'越高越好'清单一致",
      set(AF.SCORE_WEIGHTS) >= {"sentence_len_cv", "advance_marker_density"}
      and "sentence_len_cv" in AF.HIGHER_IS_BETTER)
check("7d script_text 拼接 8 段", AF.script_text(
    {"segments": [{"narration": "x"}, {"narration": "y"}]}) == "x\n\ny")

print()
print("结果: {}/{} 通过".format(N[0] - len(FAILS), N[0]))
if FAILS:
    print("失败项:", FAILS)
sys.exit(1 if FAILS else 0)
