"""query_generator (Stage 12.1): Intent -> concise English search query.

Two-step, deterministic and traceable:
  1) compose a query seed from intent fields (subject + action + context)
  2) (optional LLM) condense the seed into 1-3 SHORT ENGLISH search phrases
     (Commons full-text search works poorly with long Chinese sentences —
     observed: 40+ char Chinese query returns 0 pages).

Falls back to short English from asset_type_hint when no LLM needed/available.
Every query is traceable shot_id -> visual_intent -> query.
No random query, no keyword blacklist.
"""
from __future__ import annotations

SCHEMA_QUERY = {
    "type": "object",
    "properties": {
        "queries": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["queries"],
}

PROMPT_QUERY = (
    "你是素材检索词生成器。给定镜头的视觉主体/动作/场景，生成 2-3 个【简短的英文检索词】（每个 2-5 个英文单词），"
    "用于在真实照片图库（Wikimedia Commons）检索素材。只输出 JSON，禁止 Markdown、禁止解释。字段：\n"
    "  \"queries\": 字符串数组（英文名词短语，主体 + 核心关系 + 场景，"
    "如 \"modern office workers automation\"）\n"
    "现实性校准（Stage 12.6，必须遵守）：\n"
    "  - 每个查询以【可见名词】为核心（能被相机拍到的具体事物/场景），"
    "不要虚构事件性/一次性叙事短语（如 \"robot grasping apple fail\" 这类细节无法命中真实照片）；\n"
    "  - 概念化描述转为最接近的真实对应场景："
    "\"data streams reorganizing future city\" → \"smart city aerial\" 或 \"digital city\"；"
    "人机协作叙事 → \"human robot collaboration\" 或 \"industrial robot human\"；\n"
    "  - 但不得泛化到失真：\"future city\" 不得退化为 \"city\"，必须保留 future/smart/digital 等语义锚点；\n"
    "  - 历史主题直接命名历史主体或地点（如 \"dartmouth college campus\"、\"1950s university conference\"、"
    "\"industrial revolution factory\"）。\n"
    "注意：不要输出中文，不要输出完整句子，用名词短语。\n"
    "视觉主体：{subject}\n视觉动作：{action}\n视觉场景：{context}\n时期：{period}")


def _condense(subject, action, context):
    """Deterministic short-English fallback from raw fields (heuristic)."""
    seed = " ".join([subject, action, context]).strip()
    # crude but deterministic: keep only ASCII word tokens, cap length
    words = [w for w in seed.split() if all(ord(c) < 128 for c in w)]
    return " ".join(words[:8]) if words else "office technology"


def generate_queries(intent: dict, th=None, max_queries: int = 3) -> list[str]:
    subject = (intent.get("visual_subject") or "").strip()
    action = (intent.get("visual_action") or "").strip()
    context = (intent.get("visual_context") or "").strip()
    period = (intent.get("time_period") or "").strip()

    # LLM path: condense to short English (recommended; Commons search needs it)
    if th is not None:
        user = (PROMPT_QUERY
                .replace("{subject}", subject[:120])
                .replace("{action}", action[:120])
                .replace("{context}", context[:120])
                .replace("{period}", period[:40]))
        res = th.hardened_call("deepseek-chat", "你是素材检索词生成器。", user,
                               SCHEMA_QUERY, repair_prompt=user, temperature=0.1)
        if res.get("status") == "SUCCESS" and res.get("data"):
            qs = [q.strip() for q in res["data"].get("queries", [])
                  if q and q.strip()][:max_queries]
            if qs:
                return qs

    # deterministic fallback: short English from ASCII tokens
    seed = _condense(subject, action, context)
    out = []
    if subject and any(ord(c) < 128 for c in subject):
        out.append(" ".join([w for w in subject.split() if all(ord(c) < 128 for c in w)][:5]))
    if seed and seed not in out:
        out.append(seed)
    if period and period.lower() in ("historical", "future", "near-future"):
        out.append(f"{period} { (out[0] if out else 'technology') }")
    return out[:max_queries] if out else ["office technology"]
