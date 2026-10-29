"""t1_visual_query (Stage 12.13): T1 query-expression refinement.

Fixes the 12.12-diagnosed bottleneck: Commons full-text match != visual match.
The original T1 phrases are often narrative/too-specific ("smart home bedroom
morning light") -> 0 bitmap hits -> the frozen relaxation ladder falls through
to unconstrained full-text and the pool top fills with document scans.

This module REWRITES the T1 expression (never the beat narration, never the
visual intent semantics) into 2-3 short English noun phrases that state the
VISIBLE subject + scene + core relation, calibrated to what actually exists
as real photographs on Commons. Generic rules only — no keyword blacklist,
no shot/主题 hardcode, no threshold changes.

Called BEFORE the frozen beat_retrieval.generate_query_tiers; T2/T3 fallback
tiers are still produced by the frozen module from these refined T1 queries.
Falls back to the original T1 verbatim on any LLM failure.
"""
from __future__ import annotations

import json

SCHEMA_REFINE = {
    "type": "object",
    "properties": {
        "queries": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["queries"],
}

PROMPT_REFINE = (
    "你是图库检索词修复器。一个视频节拍的原检索词在真实照片图库（Wikimedia Commons，"
    "按文件名和文件描述全文匹配）命中不佳：要么过于叙事化没有真实照片能命中，"
    "要么命中了只提到关键词的无关文件。请把检索词重写为 2-3 个【真实照片图库大概率存在对应照片】"
    "的英文短名词短语。只输出 JSON，禁止 Markdown、禁止解释。字段：\n"
    "  \"queries\": 字符串数组，每个 2-4 个英文单词\n"
    "规则：\n"
    "  1. 每个短语表达【画面中实际可见的主体 + 场景 + 核心关系】，是相机能拍到的东西；\n"
    "  2. 抽象/理论/未来/历史概念必须转换为其现实中真实存在的可见对应物"
    "（如 \"smart home morning\" → \"smart speaker bedroom\"；\"human machine coexistence\" → "
    "\"humanoid robot person\"），但禁止虚构具体事件或一次性场面；\n"
    "  3. 保留原意的关键语义锚点（future/smart/historical/dartmouth 等），不得泛化到失真；\n"
    "  4. 不要 2 个以下字母的词，不要宽泛单词（如单独 \"AI\"、\"technology\"）；\n"
    "  5. 用真实照片库常见的措辞（ Commons 上城市/办公室/工厂/学校/街道/设备照片最多，"
    "清晨卧室灯光这类罕见场面改为可拍到的具体物体）。\n"
    "视觉主体：{subject}\n视觉动作：{action}\n视觉场景：{context}\n时期：{period}\n"
    "原检索词：{queries}\n节拍旁白：{narration}")


def refine_t1(intent: dict, original_t1: list[str], narration: str, th) -> dict:
    """Return {"queries", "source", "llm_status"}. source: refined|fallback_original."""
    subject = (intent.get("visual_subject") or "").strip()
    action = (intent.get("visual_action") or "").strip()
    context = (intent.get("visual_context") or "").strip()
    period = (intent.get("time_period") or "").strip()
    if not original_t1:
        return {"queries": [], "source": "fallback_original", "llm_status": "SKIPPED"}
    if th is None:
        return {"queries": list(original_t1), "source": "fallback_original",
                "llm_status": "SKIPPED"}
    user = (PROMPT_REFINE
            .replace("{subject}", subject[:120])
            .replace("{action}", action[:120])
            .replace("{context}", context[:120])
            .replace("{period}", period[:40])
            .replace("{queries}", json.dumps(original_t1, ensure_ascii=False))
            .replace("{narration}", narration[:160]))
    res = th.hardened_call("deepseek-chat", "你是图库检索词修复器。", user,
                           SCHEMA_REFINE, repair_prompt=user, temperature=0.1)
    if res.get("status") == "SUCCESS" and res.get("data"):
        qs = [q.strip() for q in res["data"].get("queries", [])
              if isinstance(q, str) and q.strip()][:3]
        if qs:
            return {"queries": qs, "source": "refined", "llm_status": res.get("status")}
    return {"queries": list(original_t1), "source": "fallback_original",
            "llm_status": res.get("status", "UNKNOWN")}
