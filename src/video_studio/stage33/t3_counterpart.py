"""Stage 12.22 new independent T3 (concrete counterpart) query module.

Maps a beat's visual intent (subject / scene / relation) to 2-3 concrete,
photographable objects or scenes that visually imply the narration meaning.
Reality-calibrated to Commons photo inventory; no fabricated events; no
generic single words. This module ONLY ADDS T3 queries — T1/T2 and the
existing generate_query_tiers are untouched.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

PROMPT_T3 = (
    "你是素材检索词生成器。把节拍的画面意图(主体/场景/关系)映射为 2-3 个真实世界中"
    "可被相机拍到的具体对象或场景，用于照片库检索。\n"
    "硬性规则：\n"
    "1. 每个检索词必须是具体可见的实物/场景名词短语(2-4 个英文单词)，例如岔路口→"
    "\"forked road junction\"、协作机器人→\"robotic arm factory line\"、远程办公→"
    "\"home office desk laptop\"。\n"
    "2. 禁止虚构事件、禁止人物虚构；只描述物体与场景类型。\n"
    "3. 禁止泛化单词(单独的 AI/technology/future/city 之类)。\n"
    "4. 保留旁白语义锚点(具体职业/场所/物品不得丢失)，允许用该含义在现实中最常见的"
    "可见对应物替代抽象概念。\n"
    "5. 输出 JSON: {\"queries\": [\"...\", ...]}，最多 3 个。\n"
    "节拍画面意图：{intent}\n节拍旁白：{narration}")

SCHEMA_T3 = {
    "type": "object",
    "properties": {"queries": {"type": "array",
                               "items": {"type": "string"},
                               "maxItems": 3}},
    "required": ["queries"],
}


def generate_t3_queries(beat_key: str, narration: str, intent: dict, th,
                        cache_path: Path) -> dict:
    """Content-addressed (sha256 narration) cached T3 query generation."""
    key = hashlib.sha256(narration.encode("utf-8")).hexdigest()
    cache = {}
    if cache_path.exists():
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
    if key in cache:
        return {"queries": cache[key]["queries"], "llm_status": "CACHE_HIT"}
    if th is None:
        return {"queries": [], "llm_status": "SKIPPED"}
    user = (PROMPT_T3
            .replace("{intent}", (intent.get("visual_intent") or "")[:200])
            .replace("{narration}", narration[:200]))
    res = th.hardened_call("deepseek-chat", "你是素材检索词生成器。", user,
                           SCHEMA_T3, repair_prompt=user, temperature=0.1)
    data = res.get("data") or {}
    qs = [q.strip() for q in (data.get("queries") or [])
          if isinstance(q, str) and q.strip()][:3]
    cache[key] = {"beat": beat_key, "queries": qs, "status": res.get("status")}
    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=1),
                          encoding="utf-8")
    return {"queries": qs, "llm_status": res.get("status", "UNKNOWN")}


def fetch_t3_candidates(intent_hint: dict, t3_queries: list[str],
                        limit: int = 6) -> dict:
    """Fetch via the FROZEN low-level retrieval; provenance tier=counterpart,
    flagged src_t3_new=True. Dedup left to the caller (merged with base pool)."""
    from video_studio.stage33 import retrieval_v15
    if not t3_queries:
        return {"candidates": [], "attempts": []}
    ret = retrieval_v15.search_with_media_preference(intent_hint, t3_queries, limit=limit)
    cands = []
    for c in ret["candidates"]:
        c = dict(c)
        c["tier"] = "counterpart"
        c["src_t3_new"] = True
        cands.append(c)
    return {"candidates": cands, "attempts": ret.get("attempts", [])}
