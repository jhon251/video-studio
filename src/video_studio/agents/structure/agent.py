"""Structure Agent：内容结构——整理章节与信息层级，不得改变核心观点。"""

from ..base import Agent, register

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "chapters": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "goal": {"type": "string"},
                    "duration_s": {"type": "number"},
                    "info_points": {"type": "array"},
                    "transition": {"type": "string"},
                    # v3（加法）：章节钩子与"信息增量点间隔"自检
                    "hook": {"type": "string"},
                    "hook_interval_ok": {"type": "boolean"},
                },
                "required": ["title", "goal", "duration_s"],
            },
        },
        "summary": {"type": "string"},
        "confidence": {"type": "number"},
        "note": {"type": "string"},
    },
    "required": ["chapters", "summary"],
}


@register
class StructureAgent(Agent):
    role = "structure"
    tier = "M"
    description = "内容结构：章节/信息层级/时长分配。不改变人类已确认的核心观点。"
    system_prompt = (
        "你是视频内容结构师。把已确认的选题与可信资料整理成视频结构：章节树、每章目标、"
        "时长分配、章节间过渡逻辑。你只能组织信息层级，绝不能改变人类已确认的核心观点。\n\n"
        "## 留存结构纪律（Creator Style v3，硬性）\n"
        "1) 章节之间必须有**钩子衔接**：每章都要有 `hook`（把观众带进下一章的真实问题或"
        "待兑现悬念），而不是「接下来我们来看」式空过渡。\n"
        "2) **连续 90 秒没有信息增量点视为结构缺陷**：`info_points` 要按时间铺开，任一"
        "90 秒窗口内至少一个真正的内容增量（新事实/新证据/被推翻的直觉/代价/限制/反转）。\n"
        "3) `hook_interval_ok` 如实标注：本章是否满足上述间隔要求（true/false）。"
        "不满足时**不要**改数据凑通过，如实标 false 并在 note 说明。\n"
        "4) 钩子是**结构元数据**，不得写进章节正文；不得为制造钩子而虚构事实。\n"
        "5) 既有约束不变：不改变 Scene/章节数量口径、不改变人类已确认的核心观点。\n"
        "输出严格 JSON。"
    )
    output_schema = OUTPUT_SCHEMA
