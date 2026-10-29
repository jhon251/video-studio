"""文件工具：受限读写。只能访问项目目录内路径（沙箱白名单）。"""

from __future__ import annotations

from pathlib import Path

from .base import Tool, ToolContext, ToolError, ToolResult


class FileTool(Tool):
    name = "file"
    input_schema = {
        "type": "object",
        "properties": {
            "op": {"type": "string", "enum": ["read", "write", "list"]},
            "path": {"type": "string"},
            "content": {"type": "string"},
        },
        "required": ["op", "path"],
    }
    permissions = ["file.read", "file.write"]

    def execute(self, inputs: dict, ctx: ToolContext) -> ToolResult:
        op = inputs.get("op")
        rel = inputs.get("path", "")
        if not rel:
            raise ToolError("BAD_INPUT", "缺少 path")
        target = (ctx.project_dir / rel).resolve()
        root = ctx.project_dir.resolve()
        if not str(target).startswith(str(root)):
            raise ToolError("FORBIDDEN", f"越界路径被拒绝: {rel}")
        if op == "read":
            if not target.is_file():
                raise ToolError("NOT_FOUND", f"文件不存在: {rel}")
            return ToolResult(ok=True, data={"content": target.read_text(encoding="utf-8")})
        if op == "write":
            if "file.write" not in (self.permissions or []):
                raise ToolError("FORBIDDEN", "无写入权限")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(inputs.get("content", ""), encoding="utf-8")
            return ToolResult(ok=True, data={"path": str(target), "size": target.stat().st_size})
        if op == "list":
            if not target.is_dir():
                raise ToolError("NOT_FOUND", f"目录不存在: {rel}")
            entries = []
            for p in sorted(target.iterdir()):
                entries.append({"name": p.name, "is_dir": p.is_dir(), "size": p.stat().st_size if p.is_file() else 0})
            return ToolResult(ok=True, data={"entries": entries})
        raise ToolError("BAD_INPUT", f"未知操作: {op}")
