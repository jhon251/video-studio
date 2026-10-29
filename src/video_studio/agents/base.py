"""Agent 基类与注册表。

每个 Agent = 角色提示词 + 输入/输出 Schema + 模型档位 + 工具权限。
Agent 本体只做"生产管理决策"，执行通过工具层。
"""

from __future__ import annotations

import json

from ..llm.router import SchemaError


class Agent:
    role: str = "base"
    tier: str = "M"                    # R / M / F / '-'
    description: str = ""
    system_prompt: str = ""
    output_schema: dict = {"type": "object"}
    needs_llm: bool = True

    def run(self, engine, task: dict) -> None:
        """默认 LLM Agent 流程：装配上下文 → 调模型 → 校验 → 落产物 → 完成。"""
        from ..memory.repo import Memory

        memory = Memory(engine.db)
        context = memory.working_context(task, engine)
        user = f"{context}\n\n# 任务\n{json.dumps(task['inputs'], ensure_ascii=False, indent=2)}"
        cost = {"model": None, "tokens": 0, "usd": 0.0, "usage": {}}

        def on_cost(model, tokens, cost_usd, usage=None):
            """HTTP 返回即记账：方案校验失败/修复重试也保留费用与审计事件（各记一条）。"""
            cost.update(model=model, tokens=tokens, usd=cost_usd, usage=usage or {})
            u = usage or {}
            try:
                # 费用按调用**累加**（同一任务可能发生：首次调用 + 修复重试 + 引擎重试）
                prev = float((engine.db.get_task(task["task_id"]) or {}).get("cost_usd") or 0.0)
                engine.db.update_task(task["task_id"], model_used=model,
                                      cost_usd=round(prev + float(cost_usd), 8))
                engine.emit(task["project_id"], "LLM_CALL", self.role, task["task_id"], {
                    "model": model, "tier": u.get("tier"), "mock": u.get("mock"),
                    "total_tokens": u.get("tokens"), "prompt_tokens": u.get("prompt_tokens"),
                    "completion_tokens": u.get("completion_tokens"),
                    "cache_hit_tokens": u.get("cache_hit_tokens"),
                    "cache_miss_tokens": u.get("cache_miss_tokens"),
                    "reasoning_tokens": u.get("reasoning_tokens"),
                    "latency_ms": u.get("latency_ms"), "attempts": u.get("attempts"),
                    "price_band": u.get("price_band"), "cost_usd": round(cost_usd, 8),
                })
            except Exception:      # 记账/事件不可用不应影响生产主链
                pass

        try:
            data = engine.router.complete(self.tier, self.system_prompt, user, self.output_schema,
                                          on_cost=on_cost)
        except SchemaError:
            raise
        summary = str(data.get("summary") or json.dumps(data, ensure_ascii=False)[:200])
        artifact_id = engine.write_artifact(
            task["project_id"], task["task_id"], task["task_type"] + "_output", data, summary=summary)
        engine.attach_artifact(task["task_id"], artifact_id)
        if data.get("confidence") is not None:
            engine.db.update_task(task["task_id"], confidence=float(data["confidence"]))
        # 任务完成时写自我心得（Agent 自我记忆）
        if data.get("note"):
            engine.db.put_memory(task["project_id"], "agent_note", task["task_type"],
                                 str(data["note"])[:500], agent_role=self.role)


AGENTS: dict[str, Agent] = {}


def register(agent_cls) -> type:
    """以类装饰器注册：存实例，避免运行时绑定错位。"""
    instance = agent_cls()
    AGENTS[instance.role] = instance
    return agent_cls
