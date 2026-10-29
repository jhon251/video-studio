"""Compliance Agent：合规检查（版权/敏感/授权）。有权一票拦截发布。"""

from ..base import Agent, register

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["pass", "replace", "block"]},
        "risks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "level": {"type": "string", "enum": ["fatal", "major", "minor"]},
                    "category": {"type": "string"},
                    "item": {"type": "string"},
                    "action": {"type": "string"},
                },
                "required": ["level", "category", "item", "action"],
            },
        },
        "summary": {"type": "string"},
        "confidence": {"type": "number"},
        "note": {"type": "string"},
    },
    "required": ["verdict", "risks", "summary"],
}


@register
class ComplianceAgent(Agent):
    role = "compliance"
    tier = "R"
    description = "合规：版权/敏感内容/素材与音乐字体授权风险。有权阻止发布。"
    system_prompt = (
        "你是视频合规审查员。检查全链路产物的版权风险（素材/音乐/字体/图像授权）、"
        "敏感内容与平台规范。给出风险分级（fatal/major/minor）与处置建议。"
        "verdict：pass 放行 / replace 需替换 / block 拦截发布。你不改内容只报风险。"
        "输出严格 JSON。"
    )
    output_schema = OUTPUT_SCHEMA

    def run(self, engine, task: dict) -> None:
        super().run(engine, task)
        task = engine.db.get_task(task["task_id"])
        import json as _json
        art = engine.db.get_artifact(task["artifacts"][-1])
        with open(art["path"], encoding="utf-8") as fh:
            report = _json.load(fh)
        if report.get("verdict") == "block":
            engine.emit(task["project_id"], "COMPLIANCE_BLOCK", "compliance", task["task_id"],
                        {"summary": report.get("summary", "")[:200]}, human_visible=True)
