"""Stage 3.1.3 素材评分层（本地 embedding 语义版）。

模式（RANK_MODE）：
- lexical   A：3.1.2 确定性（概念域+动作+弱词重叠）
- embedding B：纯本地 embedding 语义（+ 负域惩罚）
- hybrid    C：0.55*embedding + 0.25*concept + 0.10*action + 0.10*overlap（默认）

版权硬门槛不变：UNSAFE / UNKNOWN 在评分前淘汰；embedding 绝不推翻版权门禁。
"""
from __future__ import annotations

import re

from .rights import RightsInfo, classify

RANK_MODE = "hybrid"
W = {
    "semantic_match": 0.42,
    "visual_quality": 0.08,
    "license_safety": 0.10,
    "source_reliability": 0.08,
    "resolution": 0.10,
    "duration_fit": 0.07,
    "style_fit": 0.15,
}
_NEG_PENALTY = 30.0
_ACTION_BONUS = 15.0
RELEVANCE_MIN = 45.0


def set_rank_mode(mode: str):
    global RANK_MODE
    assert mode in ("lexical", "embedding", "hybrid")
    RANK_MODE = mode


def _words(text: str) -> set:
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def _cand_text(cand) -> str:
    return " ".join([
        cand.visual_description or "",
        cand.raw.get("title", ""),
    ])


def concept_score(cand, intent) -> float:
    hay = _words(_cand_text(cand))
    pos = intent.concepts_pos or []
    neg = intent.concepts_neg or []
    hits = sum(1 for c in pos if c in hay)
    negs = sum(1 for c in neg if c in hay)
    score = 35.0 + 55.0 * min(1.0, hits / max(3, len(pos) * 0.3))
    score -= _NEG_PENALTY * negs
    return max(0.0, min(100.0, score))


def action_score(cand, intent) -> float:
    hay = _words(_cand_text(cand))
    verbs = _words(intent.action) - {"with", "the", "and", "to", "in", "of", "a",
                                     "assistant", "helping", "daily", "tasks",
                                     "showing", "subject"}
    hits = sum(1 for v in verbs if v in hay and len(v) >= 3)
    return min(_ACTION_BONUS, 8.0 + 7.0 * hits) if hits else 0.0


def overlap_score(cand, intent, query: str) -> float:
    hay = _words(_cand_text(cand))
    needles = _words(query) | _words(intent.subject) | _words(intent.action)
    needles = {n for n in needles if len(n) >= 3}
    if not needles:
        return 10.0
    hits = sum(1 for n in needles if n in hay)
    return min(20.0, 4.0 * hits)


def embedding_score(cand, intent) -> float:
    """本地语义分：narration vs 候选描述（多语言 embedding 余弦归一化）。"""
    try:
        from .semantic import semantic_similarity
        cos = semantic_similarity(intent.narration or intent.subject, _cand_text(cand))
    except Exception:  # noqa: BLE001
        return 30.0
    # 相关对 cos 通常 0.15–0.60；映射到 0–100
    return max(0.0, min(100.0, (cos - 0.08) / 0.42 * 100.0))


def semantic_match_score(cand, intent, query: str) -> float:
    c = concept_score(cand, intent)
    a = action_score(cand, intent)
    o = overlap_score(cand, intent, query)
    if RANK_MODE == "lexical":
        return round(c * 0.6 + a * 0.8 + o * 0.15, 1)
    e = embedding_score(cand, intent)
    if RANK_MODE == "embedding":
        return round(e * 0.85 + c * 0.15, 1)
    return round(e * 0.55 + c * 0.25 + a * 0.10 + o * 0.10, 1)


def resolution_score(cand) -> float:
    w = cand.width
    if w >= 1920:
        return 100.0
    if w >= 1280:
        return 85.0
    if w >= 800:
        return 60.0
    if w > 0:
        return 30.0
    return 10.0


def duration_fit_score(cand, intent) -> float:
    if cand.content_type != "video" or cand.duration is None:
        return 50.0
    d = cand.duration
    target = intent.preferred_duration or 10.0
    if 3 <= d <= 60:
        return 100.0 if d >= target * 0.5 else 80.0
    return 40.0


def style_fit_score(cand, intent) -> float:
    s = 60.0
    if intent.preferred_media_type == "video":
        s += 25.0 if cand.content_type == "video" else 0.0
    elif intent.preferred_media_type == "image" and cand.content_type == "image":
        s += 10.0
    if intent.match_type in ("RHYTHM", "EMOTIONAL") and cand.content_type == "video":
        s += 5.0
    if cand.source == "wikimedia_commons":
        s += 5.0
    return min(100.0, s)


def score_candidate(cand, intent, query: str) -> dict:
    sem = semantic_match_score(cand, intent, query)
    res = resolution_score(cand)
    dur = duration_fit_score(cand, intent)
    sty = style_fit_score(cand, intent)
    final = round(
        sem * W["semantic_match"] + res * W["resolution"] + dur * W["duration_fit"]
        + sty * W["style_fit"] + 90 * W["visual_quality"]
        + 90 * W["source_reliability"], 1)
    return {
        "semantic_match": sem,
        "concept_score": concept_score(cand, intent),
        "action_score": action_score(cand, intent),
        "overlap_score": overlap_score(cand, intent, query),
        "embedding_score": embedding_score(cand, intent),
        "visual_quality": 90.0,
        "license_safety": 100.0,
        "source_reliability": 90.0,
        "resolution": res,
        "duration_fit": dur,
        "style_fit": sty,
        "final_score": final,
    }


def gate_and_score(cand, intent, query: str) -> tuple[RightsInfo | None, dict | None]:
    """硬门槛 + 评分。UNSAFE/UNKNOWN 返回 (info, None)（被淘汰）。"""
    info = classify(cand.source_url, cand.license, cand.source_name, cand.creator)
    if info.status in ("UNSAFE", "UNKNOWN"):
        return info, None
    return info, score_candidate(cand, intent, query)
