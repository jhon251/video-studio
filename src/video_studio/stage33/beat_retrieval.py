"""beat_retrieval (Stage 12.8): 3-tier query recovery for beat-level retrieval.

Problem (12.7): beat granularity narrows intents/queries -> niche full-text
queries -> Commons relevance noise -> 10/13 beats gate_rejected_all.

Fix: up to 3 query tiers per beat, merged before Gate -> V1 -> CV-2:
  T1 precise      — the beat's own queries (from query_generator, unchanged)
  T2 relaxed      — same subject + core relation, scene-specific details dropped
  T3 counterpart  — real-world visible counterpart of the concept

Guardrails (prompt-level, no hard rules):
  - beat narration text is NEVER changed (this module only widens retrieval)
  - no fabricated events; no generic single-word queries like "AI"
  - anchors preserved: "future city" must not degrade to "city"
  - HONEST_EMPTY stays allowed — widening is not forced retention

retrieval_v15 / gate / V1 / CV-2 are called, never modified.
"""
from __future__ import annotations

import json

SCHEMA_TIERS = {
    "type": "object",
    "properties": {
        "relaxed": {"type": "array", "items": {"type": "string"}},
        "counterpart": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["relaxed", "counterpart"],
}

PROMPT_TIERS = (
    "你是素材检索词优化器。一个视频节拍已有一组【精准检索词】，但在真实照片图库命中不佳。"
    "请生成另外两层检索词。只输出 JSON，禁止 Markdown、禁止解释。字段：\n"
    "  \"relaxed\": 字符串数组（1-2 个语义放宽词：保留【主体+核心关系】，去掉过于具体的事件/场景细节，"
    "如 \"collaborative robot assembly line\" → \"collaborative robot\"；但不得泛化到失真，"
    "\"future city\" 不得变成 \"city\"，\"smart city\" 必须保留 smart）\n"
    "  \"counterpart\": 字符串数组（1-2 个真实可见对应物词：概念/抽象描述在现实中被拍到的对应场景，"
    "如 \"AI understanding physical world\" → \"robot arm laboratory\"；\"city data network\" → \"city night aerial\"）\n"
    "规则：全部为 2-5 个英文单词的名词短语；禁止虚构事件；禁止宽泛单词（如单独的 \"AI\"、\"technology\"）；"
    "保留原词的语义锚点（future/smart/historical/dartmouth 等不得丢失）。\n"
    "节拍画面：{intent}\n节拍旁白：{narration}\n精准检索词：{queries}")


def generate_query_tiers(beat_narration: str, intent: dict, precise_queries: list[str],
                         th) -> dict:
    """T2/T3 from one LLM call; T1 = the beat's own queries (unchanged)."""
    tiers = {"precise": list(precise_queries), "relaxed": [], "counterpart": []}
    llm_status = "SKIPPED"
    if th is not None:
        user = (PROMPT_TIERS
                .replace("{intent}", (intent.get("visual_intent") or "")[:160])
                .replace("{narration}", beat_narration[:160])
                .replace("{queries}", json.dumps(precise_queries, ensure_ascii=False)))
        res = th.hardened_call("deepseek-chat", "你是素材检索词优化器。", user,
                               SCHEMA_TIERS, repair_prompt=user, temperature=0.2)
        llm_status = res.get("status", "UNKNOWN")
        data = res.get("data") or {}
        for k in ("relaxed", "counterpart"):
            tiers[k] = [q.strip() for q in (data.get(k) or [])
                        if isinstance(q, str) and q.strip()][:2]
    return {"tiers": tiers, "llm_status": llm_status}


def retrieve_beat_candidates(intent: dict, tiers: dict, limit: int = 8) -> dict:
    """Run retrieval_v15 per tier (unmodified), merge with tier provenance."""
    from video_studio.stage33 import retrieval_v15
    merged: list[dict] = []
    seen: set[str] = set()
    tier_trace = []
    for tier_name in ("precise", "relaxed", "counterpart"):
        qs = tiers.get(tier_name) or []
        if not qs:
            tier_trace.append({"tier": tier_name, "queries": [], "n_results": 0})
            continue
        ret = retrieval_v15.search_with_media_preference(intent, qs, limit=limit)
        n_new = 0
        for c in ret["candidates"]:
            if c["title"] and c["title"] not in seen:
                seen.add(c["title"])
                c = dict(c)
                c["tier"] = tier_name
                merged.append(c)
                n_new += 1
        tier_trace.append({"tier": tier_name, "queries": qs,
                           "attempts": ret["attempts"], "n_results": len(ret["candidates"]),
                           "n_new": n_new})
    return {"merged": merged, "tier_trace": tier_trace}
