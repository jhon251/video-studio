"""V2.1 Creator Style Layer v2（叙事逻辑驱动 · 去模板腔；规范见 config/script_style_guide.md v2）。

- Style 只改"如何表达"，不改"事实是什么"（Truth/Evidence 优先）。
- v2 变更（相对 8K v1）：
  1. 移除固定口头禅包装（hook_wrap / body_intro / body_closer 一律删除，不再每段套同一模板）；
  2. 语域化调整（四风格仅通过"结尾落点 + 观点强度"区分，不重写正文）；
  3. 结论按 claim 成熟度内容感知生成（不再"综合现有证据…"统一句式）；
  4. 新增 style_qa()：AI 味自检（10 项），供生成后自动 QA。
- 结构/引用/事实零改动：apply_style 不改 evidence_refs / fact_refs / claims / 数字 / 实体 / 限定词。
"""

from __future__ import annotations

import re
from collections import Counter

STYLE_PROFILES: dict[str, dict] = {
    "academic": {
        "name": "严谨学术",
        "opinion_strength": 0.5,
        "closing": "这是现有证据能给出的最诚实的判断。",
    },
    "casual": {
        "name": "轻松科普",
        "opinion_strength": 0.6,
        "closing": "说穿了，这件事，还早得很。",
    },
    "sharp": {
        "name": "犀利锐评",
        "opinion_strength": 0.9,
        "closing": "别信什么“几年后一定实现”，证据就摆在这。",
    },
    "gentle": {
        "name": "温和启发",
        "opinion_strength": 0.3,
        "closing": "这些急不来，但方向是清楚的。",
    },
}

# 观点强度（用于结论段的强弱口径；不改事实）
_STRENGTH_CONCLUSION = [
    (0.7, "结论可以给得直接一点：{q}"),
    (0.4, "按现有证据，{q}"),
    (0.0, "{q}——不过，这件事还没有标准答案。"),
]


def adjust_profile(profile: dict, feedback: dict) -> dict:
    """人工反馈调整接口（保留 v1 接口；改参数返回新 profile）。"""
    p = dict(profile)
    if "opinion_strength" in feedback:
        p["opinion_strength"] = max(0.0, min(1.0, float(feedback["opinion_strength"])))
    if "closing" in feedback:
        p["closing"] = feedback["closing"]
    if "name" in feedback:
        p["name"] = feedback["name"]
    return p


def _conclusion_by_strength(question: str, strength: float) -> str:
    for threshold, tpl in _STRENGTH_CONCLUSION:
        if strength >= threshold:
            return tpl.format(q=question)
    return _STRENGTH_CONCLUSION[-1][1].format(q=question)


def _question_of(draft: dict) -> str:
    for p in draft["paragraphs"]:
        if p["role"] == "conclusion" and p["text"]:
            return p["text"].strip()
    return ""


def apply_style(draft: dict, brief: dict, style_key: str, final: bool = True) -> dict:
    """v2：只做语域调整，不重写正文；保留情绪标签/引用/[EDIT]/[待补]/参考来源。

    - hook / body / fact / gap：文本原样（叙事层已生成内容感知表达）。
    - final=True 时（整片最后一章），仅在最后一个 conclusion 段落追加风格收束语（每片一次）。
    """
    profile = STYLE_PROFILES[style_key]
    paras = list(draft["paragraphs"])
    if final:
        last_conc = None
        for p in paras:
            if p["role"] == "conclusion":
                last_conc = p
        if last_conc is not None:
            last_conc["text"] = f"{last_conc['text']} {profile['closing']}"
    refs = draft.get("references", [])
    return {"style": style_key,
            "profile": {"name": profile["name"], "opinion_strength": profile["opinion_strength"]},
            "paragraphs": paras, "references": refs,
            "draft_text": _render_styled(style_key, profile, paras, refs)}


def _render_styled(style_key: str, profile: dict, paragraphs: list[dict],
                   references: list[dict]) -> str:
    lines = [f"【风格化脚本 · {profile['name']}】（观点强度 {profile['opinion_strength']:.1f}）", ""]
    for p in paragraphs:
        emo_bar = "▮" * p["intensity"] + "▯" * (5 - p["intensity"])
        lines.append(f"【{p['beat']}｜情绪 {p['emotion']} {emo_bar}】")
        lines.append(p["text"])
        if p["role"] == "hook":
            lines.append("  [EDIT: 可替换为更口语化的开场]")
        if p["role"] == "gap":
            lines.append("  [待补: 以上元素需补调研]")
        lines.append("")
    lines.append("【参考来源】")
    for r in references:
        lines.append(f"[{r['index']}] ({r['source_tier'] or '?'}) {r['title'][:40]} {r['url']}")
    lines.append("\n[本稿为风格化草案，供人工审核编辑；未自动生成视频/发布/接入 TTS/剪辑。]")
    return "\n".join(lines)


def apply_all_styles(draft: dict, brief: dict) -> dict:
    return {k: apply_style(draft, brief, k) for k in STYLE_PROFILES}


# ---------------- AI 味自检（style_qa，生成后强制执行） ----------------
_TICS = ("咱们聊聊", "其实啊", "是不是有点意思", "你有没有想过", "你可能没想到",
         "值得注意的是", "换句话说", "这意味着", "可以说", "从某种意义上来说",
         "综合来看", "归根结底", "简单来说", "综合现有证据", "进入下一部分",
         "没想过的答案", "是不是很有意思", "这是不是很神奇", "你是不是也觉得")
_FORCED_QUESTION = re.compile(r"如果.{0,12}这件事成立，它会怎样改变我们的判断")
_EMPTY_SUMMARY = ("呼应开场，落回核心命题", "总而言之", "综上所述")


def style_qa(paragraphs: list[dict]) -> dict:
    """AI 味自检（10 项）。返回 {violations, score, tic_hits, citation_count}；不改任何内容。"""
    texts = [p.get("text", "") for p in paragraphs]
    joined = "\n".join(texts)
    violations = []

    def v(item, detail=""):
        violations.append({"item": item, "detail": detail})

    # 1/5. 连续重复句式（相邻 3 段同开头）
    heads = [t[:8] for t in texts if t]
    for i in range(len(heads) - 2):
        if heads[i] and heads[i] == heads[i + 1] == heads[i + 2]:
            v("连续重复句式/无意义排比", heads[i])

    # 2. 相同过渡句重复
    trans = Counter(t[:16] for t in texts if t and ("——" in t or "：" in t))
    for t, c in trans.items():
        if c >= 3:
            v("过渡句机械重复", f"{t}×{c}")

    # 3. 机械章节模板
    for t in texts:
        if t.startswith(("接下来我们来看", "下面我们继续", "首先，", "其次，")):
            v("机械章节化", t[:24])

    # 4. 无意义反问
    for t in texts:
        if _FORCED_QUESTION.search(t):
            v("无信息价值反问", t[:30])
        if t.count("？") >= 2 and ("神奇" in t or "有意思" in t):
            v("无意义反问", t[:30])

    # 6. 空泛总结
    for t in texts:
        for s in _EMPTY_SUMMARY:
            if s in t:
                v("空泛总结", t[:30])

    # 7. 疑似凑时长重复（同一四字词 ≥4 次）
    word = Counter(re.findall(r"[\u4e00-\u9fff]{4,12}", joined))
    for w, c in word.items():
        if c >= 4 and w not in ("人工智能", "大语言模型", "脑机接口", "具身智能"):
            v("疑似凑时长重复", f"{w}×{c}")

    # 8. AI 套话
    for tic in _TICS:
        if tic in joined:
            v("AI 套话", tic)

    # 9. 不像人说话（套话密度）
    tic_hits = sum(joined.count(t) for t in _TICS)
    if tic_hits >= 3:
        v("不像人说话（套话过多）", f"套话命中 {tic_hits} 次")

    # 10. Evidence 改动迹象（引用标注计数异常：应等于 fact_refs 总数，由调用方比对）
    cite_n = len(re.findall(r"\[(\d+)\]", joined))
    score = max(0, 10 - len(violations))
    return {"violations": violations, "score": score,
            "tic_hits": tic_hits, "citation_count": cite_n}
