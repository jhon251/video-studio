"""Research Agent：资料搜集 / 整理 / 来源记录。搜集与判断分离——本 Agent 不裁判来源可信度。"""

from ..base import Agent, register

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "source_cards": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "summary": {"type": "string"},
                    "origin": {"type": "string"},
                    "retrieval_path": {"type": "string"},
                    "quote": {"type": "string"},
                    "doubts": {"type": "array"},
                },
                "required": ["title", "summary", "origin"],
            },
        },
        "doubt_list": {"type": "array"},
        "summary": {"type": "string"},
        "confidence": {"type": "number"},
        "note": {"type": "string"},
    },
    "required": ["source_cards", "summary"],
}


@register
class ResearchAgent(Agent):
    role = "research"
    tier = "M"
    description = "研究：按资料需求搜集整理资料，每条记录来源与检索路径；不判断来源可信度。"
    system_prompt = (
        "你是视频生产团队的资料研究员。按资料需求搜集、整理资料，输出资料卡集合。"
        "每条资料卡必须记录：标题、内容摘要、原始来源(origin)、检索路径、可引用的原文(quote)。"
        "你只搜集整理，不裁判来源是否可信（交给来源核查岗），也不写脚本。"
        "把拿不准的地方写进 doubt_list。输出严格 JSON。"
    )
    output_schema = OUTPUT_SCHEMA
