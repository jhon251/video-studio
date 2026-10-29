"""V2.1 Stage 8J：Narrative / Script Generation Layer（隔离实现，未接生产链）。

- 输入：Script Blueprint（8I）+ Research Brief（8G）；输出：可审核 Draft Script（叙事稿）。
- 不自动配音/剪辑/视频生成/发布；不改 Evidence 链 / truth 判断。
- 确定性：
  ① Narrative Framework 设计（结论先行/问题探索/步骤递进/正反对照/故事叙述）；
  ② Hook 类型生成（数字冲击/反转/提问/悬念/故事，按 Claim 特征选型）；
  ③ 情绪曲线规划（每段情绪标签 + 强度 1-5）；
  ④ Paragraph 级 Claim-Evidence 绑定（每段标注 Claim 元素 + 证据 [n]）；
  ⑤ 人工编辑友好 Draft Script（【段落】+ 情绪标签 + [n] + [EDIT] + [待补]）。
"""

from __future__ import annotations

_FRAMEWORKS = {
    "结论前置": {"name": "结论先行式",
                 "beats": [("hook", "冲击开场"), ("conclusion_first", "先给结论"),
                           ("body", "证据论证"), ("conclusion", "收束回应")],
                 "emotions": {"hook": ("惊讶", 5), "conclusion_first": ("笃定", 4),
                              "body": ("专注", 3), "conclusion": ("释然", 4)}},
    "问题切入": {"name": "问题探索式",
                 "beats": [("hook", "悬念提问"), ("body", "探索过程"), ("conclusion", "余韵收束")],
                 "emotions": {"hook": ("好奇", 4), "body": ("疑问", 3), "conclusion": ("释然", 4)}},
    "三步递进": {"name": "步骤递进式",
                 "beats": [("hook", "总起"), ("body", "逐步拆解"), ("conclusion", "整体合流")],
                 "emotions": {"hook": ("好奇", 3), "body": ("专注", 3), "conclusion": ("笃定", 4)}},
    "对立展开": {"name": "正反对照式",
                 "beats": [("hook", "抛出对立"), ("body", "两方碰撞"), ("conclusion", "给出判断")],
                 "emotions": {"hook": ("紧张", 4), "body": ("专注", 3), "conclusion": ("释然", 4)}},
    "故事线": {"name": "故事叙述式",
               "beats": [("hook", "情境开场"), ("body", "发展转折"), ("conclusion", "落点回味")],
               "emotions": {"hook": ("好奇", 4), "body": ("共鸣", 4), "conclusion": ("余韵", 4)}},
}
_DEFAULT_FRAMEWORK = "问题切入"

# 平台叙事差异：视频号只保留 2 拍（hook + 落点），其余全框架
_PLATFORM_BEAT_CAP = {"shipinhao": 2, "bilibili": 4, "youtube": 4, "gongzhonghao": 4}
_PLATFORM_LABEL = {"shipinhao": "视频号", "bilibili": "B站", "youtube": "YouTube",
                   "gongzhonghao": "公众号"}


def choose_hook_types(struct: dict, hcq: dict) -> list[dict]:
    """② Hook 类型生成（主选 + 备选，按 Claim 特征；v2 去模板腔）。"""
    types: list[dict] = []
    nums = struct.get("numbers_years", [])
    flags = struct.get("flags", {})
    if nums:
        types.append({"type": "数字冲击", "template": f"先看一个数字：{nums[0]}。",
                      "rationale": "存在数字/年份"})
    if flags.get("negation") or flags.get("rhetorical"):
        types.append({"type": "反转", "template": f"多数人对{'、'.join(struct.get('entities', ['它'])[:2])}的印象，可能正好相反。",
                      "rationale": "否定/修辞句式"})
    if struct.get("claim_type") == "QUESTION":
        types.append({"type": "提问", "template": hcq.get("question", ""),
                      "rationale": "疑问句式"})
    if flags.get("fiction"):
        types.append({"type": "故事", "template": f"从一个虚构设定说起：{struct.get('claim_text', '')[:40]}。",
                      "rationale": "虚构叙事"})
    if not types:
        types.append({"type": "悬念", "template": hcq.get("hook", ""), "rationale": "默认悬念"})
    return types[:2]


def narrative_framework(direction: str) -> dict:
    """① Narrative Framework 设计（按叙事方向选框架 + 情绪曲线）。"""
    fw = _FRAMEWORKS.get(direction, _FRAMEWORKS[_DEFAULT_FRAMEWORK])
    return {"direction": direction, "framework": fw["name"], "beats": fw["beats"],
            "emotions": fw["emotions"]}


def _beat_for_role(fw: dict, role: str) -> tuple[str, str, int]:
    """section role → (beat 名, 情绪, 强度)。"""
    role_map = {"hook": "hook", "intro": "hook", "body": "body", "gap": "body",
                "conclusion": "conclusion", "conclusion_first": "conclusion_first"}
    rk = role_map.get(role, "body")
    for beat, label in fw["beats"]:
        if beat == rk:
            emo, it = fw["emotions"].get(beat, ("专注", 3))
            return label, emo, it
    return "正文", "专注", 3


# 内容感知的正文引入语（按 claim 成熟度标记 + 内容哈希取变体；不在各章重复同一句式）
_LEAD_IN = [
    ("已实现商业化", ["这件事，今天已经做到了。", "这件事，其实已经落地了。"]),
    ("已商业化", ["这件事，今天已经做到了。", "这件事，其实已经落地了。"]),
    ("接近商业化", ["这一步，已经走到门口了。", "这一步，就差临门一脚了。"]),
    ("工程化早期", ["这一块，还在很早期的阶段。", "这一块，说实话还很早期。"]),
    ("实验到工程化", ["这一块，刚刚从实验室往外走。", "这一块，正从实验室往外搬。"]),
    ("工程化阶段", ["这一块，正在从实验走向工程。", "这一块，正在往工程化走。"]),
    ("尚无可靠路线", ["这里，没有现成的答案。", "这里，暂时没有可靠的路线。"]),
]
_DEFAULT_LEAD = "回到事实本身。"

# 内容感知的段落收束（同上：成熟度 + 变体）
_CLOSING = [
    ("已实现商业化", ["但做到，和做到 JARVIS 那个程度，是两回事。",
                    "做到，和做到可靠，是两回事。"]),
    ("已商业化", ["但做到，和做到 JARVIS 那个程度，是两回事。",
                "做到，和做到可靠，是两回事。"]),
    ("接近商业化", ["摸到门口，和走进门，还有段路。", "走到门口，和进门，是两码事。"]),
    ("工程化早期", ["这一项，还差得远。", "这一项，离成熟还很远。"]),
    ("实验到工程化", ["这一项，才刚起步。", "这一项，只是开了个头。"]),
    ("工程化阶段", ["这一项，正在往成熟走。", "这一项，还在路上。"]),
    ("尚无可靠路线", ["到这里，答案其实已经清楚了。", "到这里，结论已经清楚了。"]),
]
_DEFAULT_CLOSING = "这一层，先聊到这。"


def _maturity(claim_text: str, table: list[tuple[str, list[str]]], default: str) -> str:
    for marker, variants in table:
        if marker in claim_text:
            h = sum(ord(c) for c in claim_text)
            return variants[h % len(variants)]
    return default


def _body_paragraph(sc: str, struct: dict, refs: list[str], url_to_idx: dict) -> str:
    """段落级 Claim-Evidence 绑定（v2：内容感知引入语 + 子命题原文 + 证据编号）。"""
    lead = _maturity(sc, _LEAD_IN, _DEFAULT_LEAD)
    cite = "、".join(f"[{url_to_idx.get(u, '?')}]" for u in refs)
    text = f"{lead} {sc}"
    if cite:
        text += f"（证据 {cite}）"
    return text


def _hcq_from_blueprint(blueprint: dict) -> dict:
    hook_sec = next((s for s in blueprint["sections"] if s["role"] == "hook"), None)
    conc_sec = next((s for s in blueprint["sections"] if s["role"] == "conclusion"), None)
    return {"hook": (hook_sec["points"][0] if hook_sec and hook_sec["points"] else ""),
            "conflict": (hook_sec["points"][1] if hook_sec and len(hook_sec["points"]) > 1 else ""),
            "question": (conc_sec["points"][0] if conc_sec and conc_sec["points"] else "")}


def build_narrative_draft(blueprint: dict, brief: dict, platform: str) -> dict:
    """Blueprint + Brief → 平台叙事 Draft Script（段落级绑定 + 情绪曲线）。"""
    struct = brief["structure"]
    hcq = _hcq_from_blueprint(blueprint)
    direction = blueprint.get("narrative", "问题切入")
    fw = narrative_framework(direction)
    hooks = choose_hook_types(struct, hcq)
    url_to_idx = blueprint["url_to_index"]

    paragraphs = []
    # 开场：hook 段落（主 hook 类型）
    beat, emo, it = _beat_for_role(fw, "hook")
    paragraphs.append({"role": "hook", "beat": beat, "emotion": emo, "intensity": it,
                       "text": hooks[0]["template"],
                       "claims": [], "evidence_refs": []})
    if len(hooks) > 1:
        paragraphs.append({"role": "hook_alt", "beat": beat, "emotion": emo, "intensity": max(1, it - 1),
                           "text": f"备选开场：{hooks[1]['template']}",
                           "claims": [], "evidence_refs": []})

    # 结论先行：若框架含 conclusion_first，先给结论段
    if any(b[0] == "conclusion_first" for b in fw["beats"]):
        beat, emo, it = _beat_for_role(fw, "conclusion_first")
        paragraphs.append({"role": "conclusion_first", "beat": beat, "emotion": emo, "intensity": it,
                           "text": f"先说结论：{struct.get('claim_text', '')[:60]}。",
                           "claims": ["core"], "evidence_refs": []})

    # 主体：每个 blueprint body section → 一个段落（绑定证据）
    body_sections = [s for s in blueprint["sections"] if s["role"] == "body"]
    for i, sec in enumerate(body_sections, 1):
        beat, emo, it = _beat_for_role(fw, "body")
        sc = sec["points"][0] if sec["points"] else struct.get("claim_text", "")
        text = _body_paragraph(sc, struct, sec["evidence_refs"], url_to_idx)
        paragraphs.append({"role": "body", "beat": beat, "emotion": emo, "intensity": it,
                           "text": text, "claims": ["core"],
                           "evidence_refs": sec["evidence_refs"]})
        for f in sec.get("facts", []):
            paragraphs.append({"role": "fact", "beat": "事实引用", "emotion": "专注", "intensity": 2,
                               "text": f"事实核查：{f['fact']} → [{f['ref_index']}]",
                               "claims": [], "evidence_refs": []})

    # 存疑/待补
    gap_sec = next((s for s in blueprint["sections"] if s["role"] == "gap"), None)
    if gap_sec:
        paragraphs.append({"role": "gap", "beat": "存疑待补", "emotion": "疑问", "intensity": 3,
                           "text": f"目前还缺：{'、'.join(gap_sec['points'])}（需补调研，切勿凭空断言）",
                           "claims": [], "evidence_refs": []})

    # 结论（v2：按 claim 成熟度内容感知收束，不再"呼应开场，落回核心命题"统一句式）
    beat, emo, it = _beat_for_role(fw, "conclusion")
    closing = _maturity(struct.get("claim_text", ""), _CLOSING, _DEFAULT_CLOSING)
    paragraphs.append({"role": "conclusion", "beat": beat, "emotion": emo, "intensity": it,
                       "text": closing,
                       "claims": [], "evidence_refs": []})

    # 平台叙事差异：视频号按 beat cap 精简（hook + 1 body + 落点）
    cap = _PLATFORM_BEAT_CAP[platform]
    if cap < 4:
        kept = []
        body_n = 0
        for p in paragraphs:
            if p["role"] in ("body", "fact"):
                body_n += 1
                if body_n > cap - 2:
                    continue
            kept.append(p)
        paragraphs = kept

    return {"platform": platform, "framework": fw,
            "hook_types": hooks, "paragraphs": paragraphs,
            "references": blueprint["references"],
            "draft_text": _render_draft(platform, fw, hooks, paragraphs, blueprint["references"])}


def _render_draft(platform: str, fw: dict, hooks: list[dict], paragraphs: list[dict],
                  references: list[dict]) -> str:
    label = _PLATFORM_LABEL[platform]
    lines = [f"【叙事稿 · {label}】",
             f"叙事框架：{fw['framework']}（{fw['direction']}）",
             f"Hook 类型：{' / '.join(h['type'] for h in hooks)}", ""]
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
    lines.append("\n[本稿为叙事草案，供人工审核编辑；未自动配音/剪辑/生成视频/发布。]")
    return "\n".join(lines)


def build_all_narrative_drafts(blueprint: dict, brief: dict) -> dict:
    """四平台叙事 Draft Script。"""
    return {p: build_narrative_draft(blueprint, brief, p)
            for p in ("shipinhao", "bilibili", "youtube", "gongzhonghao")}
