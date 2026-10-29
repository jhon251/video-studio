"""Visual Planning Agent：视觉规划——镜头清单与生成需求（规格，不是主观建议）。"""

from ..base import Agent, register

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "shots": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "number"},
                    "description": {"type": "string"},
                    "shot_size": {"type": "string"},
                    "duration_s": {"type": "number"},
                    "source": {"type": "string", "enum": ["stock", "ai_generate", "chart", "screen_capture"]},
                    "gen_prompt": {"type": "string"},
                    "style_constraint": {"type": "string"},
                },
                "required": ["index", "description", "source"],
            },
        },
        "summary": {"type": "string"},
        "confidence": {"type": "number"},
        "note": {"type": "string"},
    },
    "required": ["shots", "summary"],
}


@register
class VisualAgent(Agent):
    role = "visual"
    tier = "M"
    description = "视觉规划：把脚本映射为镜头清单（画面/景别/时长/来源/生成提示词）。"
    system_prompt = (
        "你是视频视觉规划师。把脚本映射为可执行的镜头清单：每镜给出画面描述、景别、时长、"
        "素材来源（素材库/AI生成/图表/录屏）与 AI 生成提示词。你产出规格不产出素材。"
        "输出严格 JSON。"
    )
    output_schema = OUTPUT_SCHEMA
