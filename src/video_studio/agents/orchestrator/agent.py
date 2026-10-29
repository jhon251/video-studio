"""Orchestrator Agent：任务规划 / 异常重规划 / 成本监控。

V1 中日常派单由 Engine 状态机自动完成；本 Agent 的 LLM 能力用于
"给定项目目标生成任务计划"与"异常时的重规划建议"。
"""

from ..base import Agent, register

PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "phases": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "phase": {"type": "string"},
                    "tasks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "task_type": {"type": "string"},
                                "agent_role": {"type": "string"},
                                "depends_on": {"type": "array"},
                                "requires_approval": {"type": "boolean"},
                            },
                            "required": ["task_type", "agent_role"],
                        },
                    },
                },
                "required": ["phase", "tasks"],
            },
        },
        "summary": {"type": "string"},
        "confidence": {"type": "number"},
        "note": {"type": "string"},
    },
    "required": ["phases", "summary"],
}


@register
class OrchestratorAgent(Agent):
    role = "orchestrator"
    tier = "M"          # 日常规划用 M；异常重规划时 Engine 可临时升 R（V2 细化）
    description = "总调度：把目标拆成任务 DAG、派单、推进状态机、处理异常。"
    system_prompt = (
        "你是视频生产系统的总调度 Orchestrator。人类决定做什么与核心观点，你决定怎么做："
        "把目标拆成生产任务、确定 agent_role 与依赖关系、标注哪些任务需要人工审批。"
        "你不创作内容，只做生产管理。输出严格 JSON。"
    )
    output_schema = PLAN_SCHEMA

    def run(self, engine, task: dict) -> None:
        # 计划任务：生成计划并实际注册为引擎任务
        super().run(engine, task)
        task = engine.db.get_task(task["task_id"])  # 重读产物列表
        artifact_id = task["artifacts"][-1] if task["artifacts"] else None
        if artifact_id is None:
            return
        art = engine.db.get_artifact(artifact_id)
        with open(art["path"], encoding="utf-8") as fh:
            import json as _json
            plan = _json.load(fh)
        for phase in plan.get("phases", []):
            phase_name = phase.get("phase", "phase")
            for spec in phase.get("tasks", []):
                engine.create_task(
                    task["project_id"], spec["task_type"], spec["agent_role"],
                    dependencies=[],  # V1：计划任务的依赖在创建时手工指定（见 pipeline）
                    inputs={"phase": phase_name, **spec.get("inputs", {})},
                    expected_output={},
                    requires_approval=bool(spec.get("requires_approval")),
                )
