"""Search 工具：provider 可切换（V1 需用户配置搜索 API；未配置时报 NEEDS_CONFIG）。"""

from __future__ import annotations

from .base import Tool, ToolContext, ToolError, ToolResult


class SearchTool(Tool):
    name = "search"
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "max_results": {"type": "number"},
        },
        "required": ["query"],
    }
    permissions = ["search"]

    def execute(self, inputs: dict, ctx: ToolContext) -> ToolResult:
        provider = ctx.config.get("tools", {}).get("search", {}).get("provider", "none")
        if provider == "none":
            raise ToolError("NEEDS_CONFIG",
                            "Search provider 未配置：在 config 中设置 tools.search.provider 与 API 密钥")
        raise ToolError("PROVIDER_NOT_IMPLEMENTED", f"Search provider {provider!r} 待接入")
