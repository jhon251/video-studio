"""Thumbnail Agent：封面方案与生产任务。方案需人工可审；生成由 Image 工具执行。

Phase 11（P11-2）**加法**：新增 `cover_text_candidates[]`（封面大字方案，≤12 字，须声明与
所选主标的互补关系）——仍为**概念方案，不出图**（`image` provider 默认 none）。
"""

from ..base import Agent, register

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "concepts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "composition": {"type": "string"},
                    "text_overlay": {"type": "string"},
                    "gen_prompt": {"type": "string"},
                },
                "required": ["title", "gen_prompt"],
            },
        },
        # ---- P11-2（加法）：封面大字候选 ----
        "cover_text_candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "封面大字（≤12 字）"},
                    "cover_title_pairing": {
                        "type": "string", "enum": ["互补", "递进", "反差"],
                        "description": "与所选主标的互补关系；**禁止与主标重复**"},
                    "pairing_note": {"type": "string",
                                     "description": "为什么这样配对不是重复而是增益"},
                },
                "required": ["text", "cover_title_pairing"],
            },
        },
        "summary": {"type": "string"},
        "confidence": {"type": "number"},
        "note": {"type": "string"},
    },
    "required": ["concepts", "summary"],
}


@register
class ThumbnailAgent(Agent):
    role = "thumbnail"
    tier = "M"
    description = "封面：按成片/标题产出封面候选方案 + 封面大字候选；最终采用由人工决定。"
    system_prompt = (
        "你是视频封面设计师。根据视频内容与标题产出封面候选方案：构图、文字叠加与"
        "图像生成提示词。多方案供人工选择。\n\n"
        "## 封面大字纪律（P11-2，硬性）\n"
        "1) 额外输出 `cover_text_candidates`（2-3 条），每条 `text` **≤12 字**（封面文字须 3 秒读完）。\n"
        "2) 每条必须声明 `cover_title_pairing` ∈ 互补/递进/反差，并写 `pairing_note` 说明"
        "为何是**增益而非重复**；**禁止与主标重复**（重复等于浪费封面注意力）。\n"
        "3) 封面大字同样受失实红线约束：不得出现脚本中没有的数字或承诺"
        "（规范见 config/metadata_style_guide.md §二）。\n"
        "4) 仍是**概念方案，不出图**（image provider 默认 none）；不自动生成、不自动发布。\n"
        "输出严格 JSON。"
    )
    output_schema = OUTPUT_SCHEMA
