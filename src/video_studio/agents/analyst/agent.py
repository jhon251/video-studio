"""Data Analyst Agent：发布后数据回收与复盘，经验入库（反哺下一次生产）。"""

from ..base import Agent, register

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "metrics": {"type": "object"},
        "findings": {"type": "array"},
        "lessons": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "tag": {"type": "string"},
                    "lesson": {"type": "string"},
                    "applies_to": {"type": "array"},
                },
                "required": ["tag", "lesson"],
            },
        },
        "summary": {"type": "string"},
        "confidence": {"type": "number"},
        "note": {"type": "string"},
    },
    "required": ["findings", "lessons", "summary"],
}


@register
class AnalystAgent(Agent):
    role = "analyst"
    tier = "M"
    description = "数据分析：回收平台数据、复盘、把可复用经验写入经验库。"
    system_prompt = (
        "你是视频数据分析师。根据回收的平台数据与项目过程产出复盘报告："
        "关键指标、发现、以及可复用的经验教训（每条约 tag 与适用范围）。"
        "你只提供数据事实，不替人类决定下一期选题。输出严格 JSON。"
    )
    output_schema = OUTPUT_SCHEMA

    def run(self, engine, task: dict) -> None:
        super().run(engine, task)
        task = engine.db.get_task(task["task_id"])
        import json as _json
        art = engine.db.get_artifact(task["artifacts"][-1])
        with open(art["path"], encoding="utf-8") as fh:
            report = _json.load(fh)
        # 经验入库（长期记忆：experience）
        for lesson in report.get("lessons", []):
            engine.db.put_memory(task["project_id"], "experience", lesson.get("tag", "lesson"),
                                 f"{lesson.get('lesson', '')}", agent_role="analyst")
