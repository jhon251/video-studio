"""Source Verification Agent：来源核查——盯"出处"，不是盯"陈述"。"""

from ..base import Agent, register

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "credibility": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source": {"type": "string"},
                    "grade": {"type": "string", "enum": ["trusted", "usable", "suspect", "unusable"]},
                    "reason": {"type": "string"},
                },
                "required": ["source", "grade", "reason"],
            },
        },
        "conflicts": {"type": "array"},
        "unusable": {"type": "array"},
        "summary": {"type": "string"},
        "confidence": {"type": "number"},
        "note": {"type": "string"},
    },
    "required": ["credibility", "summary"],
}


@register
class SourceVerifyAgent(Agent):
    role = "source_verify"
    tier = "R"
    description = "来源核查：检查来源是否权威、引用是否真实、多源是否冲突。可打回研究任务。"
    system_prompt = (
        "你是视频生产团队的来源核查员。对每张资料卡逐一核查：来源是否一手/权威机构、"
        "引用是否真实存在、多源之间是否冲突、信息是否已被更权威来源驳斥。"
        "输出来源可信度分级（trusted/usable/suspect/unusable）、冲突报告与不可用清单。"
        "你只裁判出处，不补充事实。输出严格 JSON。"
    )
    output_schema = OUTPUT_SCHEMA
