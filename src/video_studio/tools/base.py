"""工具层基座：Agent 操作世界的唯一入口。

- 统一接口：name / input_schema / output_schema / permissions / execute。
- 权限：按角色能力令牌校验（rules.json roles[role].tools）。
- 全部调用走 call()，统一记录审计事件。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class ToolError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(f"[{code}] {message}")
        self.code = code


@dataclass
class ToolResult:
    ok: bool
    data: Any = None
    error: str | None = None
    usage: dict = field(default_factory=dict)


class Tool:
    name: str = "tool"
    version: str = "0.1"
    input_schema: dict = {"type": "object", "properties": {}}
    output_schema: dict = {"type": "object"}
    permissions: list[str] = []          # 能力令牌（如 file.read）
    requires_human: bool = False         # 敏感操作：需人工批准令牌

    def execute(self, inputs: dict, ctx: "ToolContext") -> ToolResult:
        raise NotImplementedError

    def estimate_cost(self, inputs: dict) -> float:
        return 0.0


@dataclass
class ToolContext:
    role: str
    project_id: str
    project_dir: Path
    db: Any
    config: dict
    human_token: str | None = None       # 人工批准令牌（审批通过后注入）


class ToolRegistry:
    def __init__(self, rules: dict):
        self._tools: dict[str, Tool] = {}
        self.rules = rules

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise ToolError("UNKNOWN_TOOL", f"工具不存在: {name}")
        return self._tools[name]

    def call(self, role: str, tool_name: str, inputs: dict, ctx: ToolContext,
             on_audit=None) -> ToolResult:
        """权限校验 + 审计 + 执行。"""
        tool = self.get(tool_name)
        role_cfg = self.rules.get("roles", {}).get(role, {})
        allowed = set(role_cfg.get("tools", []))
        if not tool.permissions:
            pass  # 无权限声明的工具视为只读安全
        else:
            missing = [p for p in tool.permissions if p not in allowed]
            if missing:
                raise ToolError("FORBIDDEN", f"角色 {role} 无权限 {missing} 调用 {tool_name}")
        if tool.requires_human and ctx.human_token is None:
            raise ToolError("NEEDS_HUMAN", f"工具 {tool_name} 需要人工批准")
        if on_audit is not None:
            on_audit(tool_name, inputs)
        return tool.execute(inputs, ctx)
