"""visual_intent (Stage 12.1): shot-level Visual Intent generation.

Turns a narration segment into a structured "what should the viewer see"
description — NOT a paraphrase of the narration. Uses Stage 9 B hardened
structured output (real LLM; no template substitution).

Fields (per preflight design):
  shot_id, narration_segment, core_claim, visual_intent, visual_subject,
  visual_action, visual_context, time_period, asset_type_hint, avoid_types,
  query_seed (derived by query_generator, NOT set here).

Deterministic fallback on LLM failure keeps a traceable marker (never faked).
Not used by CV-2 / V1 / sanitizer / any frozen component.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

SCHEMA_VISUAL_INTENT = {
    "type": "object",
    "properties": {
        "core_claim": {"type": "string"},
        "visual_intent": {"type": "string"},
        "visual_subject": {"type": "string"},
        "visual_action": {"type": "string"},
        "visual_context": {"type": "string"},
        "time_period": {"type": "string"},
        "asset_type_hint": {"type": "string"},
        "avoid_types": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["core_claim", "visual_intent", "visual_subject",
                 "visual_action", "visual_context", "asset_type_hint", "avoid_types"],
}

PROMPT_INTENT = (
    "你是视频视觉策划。给定一段旁白，输出一个 JSON 对象描述【这一镜观众应该看到什么画面】，"
    "而不是复述旁白内容。只输出 JSON，禁止 Markdown、禁止解释。字段（严格用这些名字）：\n"
    "  \"core_claim\": 字符串（这一镜要表达的核心论断）\n"
    "  \"visual_intent\": 字符串（完整描述画面：谁/什么、在做什么、在什么场景）\n"
    "  \"visual_subject\": 字符串（画面主体，具象可检索，如\"现代办公室/城市天际线/早期计算机\"）\n"
    "  \"visual_action\": 字符串（画面中正在发生的动作）\n"
    "  \"visual_context\": 字符串（场景/环境）\n"
    "  \"time_period\": 字符串（如 \"historical/current/near-future/future\"）\n"
    "  \"asset_type_hint\": 字符串（IMAGE/DOCUMENT/VECTOR/VIDEO，期望的素材类型）\n"
    "  \"avoid_types\": 字符串数组（希望回避的类型，如 [\"DOCUMENT\",\"SCREENSHOT\"]；"
    "注意：历史文献段可以 asset_type_hint=DOCUMENT，不必回避）\n"
    "现实性校准（Stage 12.6，必须遵守）：\n"
    "  - 画面必须是【真实世界可拍摄】的场景（摄影师能拍到、图库真实存在的照片），"
    "禁止 CGI/概念图/抽象数据流/全息界面/发光图标等图库中不存在的意象；\n"
    "  - 若旁白讲未来/近未来，描述其【当下最接近的真实对应物】："
    "2035 智能城市→当代城市天际线或交通控制中心；人机协作→真实工厂协作机器人工位；"
    "AI 理解物理世界→实验室机器人操作真实物体；\n"
    "  - visual_intent 结构固定为：主体 + 核心关系/动作 + 场景；保留语义锚点（future/smart/historical 等），"
    "不得泛化到失真（future city ≠ city）；\n"
    "  - 历史段优先真实历史照片或原始档案文献（asset_type_hint=DOCUMENT）。\n"
    "  - 核心主体优先（Stage 12.9）：当旁白同时包含核心主体与历史类比（如\"人类社会…比工业革命更深刻\"），"
    "画面必须跟随旁白的核心主体（人类社会/城市/社会场景），历史类比只能作背景参照，"
    "不得让类比反客为主成为画面主题；\n"
    "旁白：{narration}")


def generate(shot_id: str, narration: str, th) -> dict:
    """Generate Visual Intent. th = text_hardening module (already inited).

    Stage 12.9 stability: content-addressed cache (same narration+prompt ->
    same stored intent, llm_status=CACHE_HIT) + temperature 0.0 to minimize
    first-draw drift. No shot mapping, no keyword rules.
    """
    from video_studio.stage33 import intent_stability
    user = PROMPT_INTENT.replace("{narration}", narration[:400])
    cached = intent_stability.get_cached(narration, user)
    if cached is not None:
        rec = dict(cached)
        rec["shot_id"] = shot_id  # cache is content-addressed; only label updates
        rec["llm_status"] = "CACHE_HIT"
        rec["cache"] = {"hit": True, "key": rec.get("cache", {}).get("key", "")}
        return rec
    res = th.hardened_call("deepseek-chat", "你是视频视觉策划。", user,
                           SCHEMA_VISUAL_INTENT,
                           repair_prompt=user, temperature=0.0)
    intent = res.get("data")
    rec = {
        "shot_id": shot_id,
        "narration_segment": narration,
        "core_claim": (intent or {}).get("core_claim", ""),
        "visual_intent": (intent or {}).get("visual_intent", ""),
        "visual_subject": (intent or {}).get("visual_subject", ""),
        "visual_action": (intent or {}).get("visual_action", ""),
        "visual_context": (intent or {}).get("visual_context", ""),
        "time_period": (intent or {}).get("time_period", ""),
        "asset_type_hint": (intent or {}).get("asset_type_hint", "IMAGE"),
        "avoid_types": (intent or {}).get("avoid_types", []),
        "llm_status": res["status"],
        "fallback": res.get("fallback", False),
        "attempts": res.get("attempts"),
    }
    key = intent_stability.store(narration, user, rec)
    rec["cache"] = {"hit": False, "key": key}
    return rec
