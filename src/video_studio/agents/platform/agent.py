"""Platform Adaptation Agent：多平台版本方案（横/竖/长短/各平台）。"""

from ..base import Agent, register

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "versions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "platform": {"type": "string"},
                    "resolution": {"type": "string"},
                    "aspect": {"type": "string"},
                    "duration_s": {"type": "number"},
                    "notes": {"type": "string"},
                },
                "required": ["platform", "resolution"],
            },
        },
        "summary": {"type": "string"},
        "confidence": {"type": "number"},
        "note": {"type": "string"},
    },
    "required": ["versions", "summary"],
}


@register
class PlatformAgent(Agent):
    role = "platform"
    tier = "M"
    description = "平台适配：横版/竖版/长短版与各平台规格方案。不决定内容，不执行发布。"
    system_prompt = (
        "你是视频平台适配师。根据成片信息与目标平台，产出多版本生产方案："
        "每版给出平台、分辨率、画幅、时长策略与安全区说明。你只做方案不做发布。"
        "输出严格 JSON。"
    )
    output_schema = OUTPUT_SCHEMA
