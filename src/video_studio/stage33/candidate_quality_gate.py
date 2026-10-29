"""candidate_quality_gate (Stage 12.1): light semantic theme-match gate.

Judges "does this candidate carry the current Visual Intent?" — blocks obvious
topic pollution (literal-AI but off-theme) BEFORE V1/CV-2. NOT a keyword
blacklist; NOT visual aesthetics. Reuses Stage 9 B hardened LLM.

Output per candidate: candidate_id, theme_match(bool), reason, keep/reject.
Deterministic fallback: if the gate LLM fails, candidate is KEPT (conservative)
and marked gate_status=FALLBACK_KEEP — never silently dropped.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

SCHEMA_GATE = {
    "type": "object",
    "properties": {
        "theme_match": {"type": "boolean"},
        "reason": {"type": "string"},
    },
    "required": ["theme_match", "reason"],
}

PROMPT_GATE = (
    "你是素材主题对齐判断器。给定镜头的视觉意图和一个候选素材标题，判断该素材是否【承担】这个视觉意图"
    "（即画面主题相关，可用于这一镜）。只输出 JSON，禁止 Markdown、禁止解释。字段：\n"
    "  \"theme_match\": true/false\n"
    "  \"reason\": 字符串（一句理由）\n"
    "判断标准：素材画面主题与 visual_intent 是否一致；字面含 AI/neural/network 但主题无关（如风灾结构损伤论文、"
    "军事 PDA 论文）应判 false；历史文献在讲历史时可以是 true。\n"
    "视觉意图：{intent}\n候选素材标题：{title}\n候选描述：{desc}")


def judge(th, intent_text: str, candidate: dict) -> dict:
    title = candidate.get("title", "")
    desc = (candidate.get("visual_description") or candidate.get("title") or "")[:200]
    user = PROMPT_GATE.replace("{intent}", intent_text[:300]).replace("{title}", title[:200]).replace("{desc}", desc)
    res = th.hardened_call("deepseek-chat", "你是素材主题对齐判断器。", user,
                           SCHEMA_GATE, repair_prompt=user, temperature=0.1)
    if res.get("status") == "SUCCESS" and res.get("data"):
        d = res["data"]
        return {"candidate_id": candidate.get("title"),
                "theme_match": bool(d.get("theme_match", True)),
                "reason": d.get("reason", ""),
                "keep": bool(d.get("theme_match", True)),
                "gate_status": "LLM_OK",
                "attempts": res.get("attempts")}
    # deterministic fallback: KEEP (conservative), observable
    return {"candidate_id": candidate.get("title"),
            "theme_match": None, "reason": "gate LLM failed -> conservative keep",
            "keep": True, "gate_status": "FALLBACK_KEEP",
            "attempts": res.get("attempts")}
