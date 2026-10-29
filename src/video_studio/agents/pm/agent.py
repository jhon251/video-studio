"""PM Agent：项目计划 / 排期 / 优先级 / 风险登记。"""

from ..base import Agent, register

PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "milestones": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "gate": {"type": "boolean"},
                    "tasks": {"type": "array"},
                },
                "required": ["name"],
            },
        },
        "risks": {"type": "array"},
        "priority_hints": {"type": "object"},
        "summary": {"type": "string"},
        "confidence": {"type": "number"},
        "note": {"type": "string"},
    },
    "required": ["milestones", "summary"],
}


@register
class PMAgent(Agent):
    role = "pm"
    tier = "M"
    description = "项目经理：整体进度、排期、优先级、资源与风险。"
    system_prompt = (
        "你是视频生产团队的项目经理。你管时间、优先级与风险，不管内容创意。"
        "根据项目目标产出里程碑计划（哪些环节是人工审批闸门）、风险清单与优先级建议。输出严格 JSON。"
    )
    output_schema = PLAN_SCHEMA
