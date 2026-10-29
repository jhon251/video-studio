"""Metadata / SEO Agent：标题、简介、标签、章节等元数据方案（多平台）。

Phase 11（P11-2）**加法**升级：标题候选工程 —— 从"禁止标题党"改为
**「吸睛手法最大化 ∩ 失实红线零违反」**，规范见 `config/metadata_style_guide.md`
（**不并入** `script_style_guide.md`，避免职责混淆）。
- 新增 `title_candidates[]`（5 候选，各带 technique/引用/数字出处/风险披露）与 `ab_plan`；
- 既有 `platforms[]`（各平台标题/简介/标签/章节）**逐字保留**（加法，不改不删）；
- **不自动发布、不自动 A/B**（`ab_plan.execution` 恒为 `manual`），系统只出方案。
"""
from __future__ import annotations

from pathlib import Path

from ..base import Agent, register

METADATA_GUIDE_PATH = Path(__file__).resolve().parents[4] / "config" / "metadata_style_guide.md"


def _load_metadata_guide() -> str:
    try:
        return METADATA_GUIDE_PATH.read_text(encoding="utf-8")
    except OSError:
        return ""


OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "platforms": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "platform": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "tags": {"type": "array"},
                    "chapters": {"type": "array"},
                },
                "required": ["platform", "title"],
            },
        },
        # ---- P11-2（加法）：标题候选工程 ----
        "title_candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "候选标题正文，B 站 ≤40 字"},
                    "technique": {
                        "type": "string",
                        "enum": ["curiosity_gap", "specificity", "stakes", "expectation_break",
                                 "identity_callout", "process_promise"],
                        "description": "吸睛手法（metadata_style_guide §一 白名单）",
                    },
                    "evidence_refs": {"type": "array",
                                      "description": "支撑该标题的脚本段落下标（0-based）"},
                    "number_sources": {"type": "array",
                                       "description": "标题中每个数字的出处段落下标（0-based）；"
                                                      "标题无数字时可为空"},
                    "why_win": {"type": "string", "description": "为什么这条更可能被点开"},
                    "disappointment_risk": {
                        "type": "string",
                        "description": "哪类观众会失望、为什么仍算不失实（红线自查）"},
                },
                "required": ["text", "technique", "evidence_refs", "why_win",
                             "disappointment_risk"],
            },
        },
        "ab_plan": {
            "type": "object",
            "properties": {
                "platform": {"type": "string"},
                "variants": {"type": "array", "description": "≥2 个候选标题文本（人工执行 A/B）"},
                "metric": {"type": "string"},
                "execution": {"type": "string", "enum": ["manual"]},
                "note": {"type": "string"},
            },
            "required": ["platform", "variants", "metric", "execution"],
        },
        "summary": {"type": "string"},
        "confidence": {"type": "number"},
        "note": {"type": "string"},
    },
    "required": ["platforms", "summary"],
}

PROMPT_RULES = (
    "\n\n## 标题候选工程（P11-2，硬性；规范全文见下方 metadata_style_guide）\n"
    "1) 口径是 **「吸睛手法最大化 ∩ 失实红线零违反」**：先满足红线，再把手法的张力做到最大。\n"
    "2) 输出 **5 条** `title_candidates`，须覆盖 **≥3 种不同 technique**（白名单 6 选）。\n"
    "3) 每条必须给 `evidence_refs`（支撑该标题的脚本段落下标，0-based，必须真实存在）；"
    "标题中**出现的每个数字**都必须给 `number_sources`（数字出处段落下标）——"
    "**数字找不到出处即失实**，宁可改写标题也不许保留。\n"
    "4) **禁止**承诺脚本没交付的内容（标题诈骗 = 完播率杀手）；**禁止**震惊体模板（见黑名单）。\n"
    "5) 候选**不得与脚本首句雷同**（连续 12 字重合即违规）。\n"
    "6) 每条候选必须写 `disappointment_risk`：哪类观众可能失望、为什么**仍算不失实**。\n"
    "7) 输出 `ab_plan`：`platform=\"bilibili\"`、`variants` 为 ≥2 条候选标题文本、"
    "`metric=\"ctr\"`、`execution=\"manual\"`（**人工执行；系统不做任何发布动作**）。\n"
    "8) `platforms[]` 既有字段（各平台 title/description/tags/chapters）照旧输出，不受本工程影响。"
)


@register
class MetadataAgent(Agent):
    role = "metadata"
    tier = "M"
    description = "元数据/SEO：标题候选工程 + 各平台元数据方案。吸睛但不失实，不决定发布。"
    system_prompt = (
        "你是视频元数据与 SEO 专员。根据成片与脚本产出各平台元数据方案（标题、简介、标签、章节），"
        "并执行**标题候选工程**：在不违反失实红线的前提下把手法的吸引力做到最大。"
        "你只出方案，不发布、不决定最终标题。输出严格 JSON。\n\n"
        "## 标题与封面候选规范（必须遵守）\n"
        f"{_load_metadata_guide()}"
        f"{PROMPT_RULES}"
    )
    output_schema = OUTPUT_SCHEMA

    def run(self, engine, task: dict) -> None:
        super().run(engine, task)
        # V2：发布面文案必须零 [CLAIM:xxx] 标记（防御性剥离，即使模型复制了内部稿）
        import json as _json
        from ...core.strip import strip_claims_deep
        task = engine.db.get_task(task["task_id"])
        art = engine.db.get_artifact(task["artifacts"][-1])
        with open(art["path"], encoding="utf-8") as fh:
            data = _json.load(fh)
        cleaned = strip_claims_deep(data)
        with open(art["path"], "w", encoding="utf-8") as fh:
            _json.dump(cleaned, fh, ensure_ascii=False, indent=2)
