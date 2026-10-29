"""Image / Video 生成工具：provider 可切换（V1 需用户配置；未配置时报 NEEDS_CONFIG）。"""

from __future__ import annotations

from .base import Tool, ToolContext, ToolError, ToolResult


class ImageTool(Tool):
    name = "image"
    input_schema = {
        "type": "object",
        "properties": {
            "prompt": {"type": "string"},
            "size": {"type": "string"},
            "output": {"type": "string"},
        },
        "required": ["prompt", "output"],
    }
    permissions = ["image"]

    def execute(self, inputs: dict, ctx: ToolContext) -> ToolResult:
        provider = ctx.config.get("tools", {}).get("image", {}).get("provider", "none")
        if provider == "none":
            raise ToolError("NEEDS_CONFIG",
                            "Image provider 未配置：在 config 中设置 tools.image.provider 与 API 密钥")
        raise ToolError("PROVIDER_NOT_IMPLEMENTED", f"Image provider {provider!r} 待接入")


class VideoGenTool(Tool):
    name = "video"
    input_schema = {
        "type": "object",
        "properties": {
            "prompt": {"type": "string"},
            "duration_s": {"type": "number"},
            "output": {"type": "string"},
        },
        "required": ["prompt", "output"],
    }
    permissions = ["video"]

    def execute(self, inputs: dict, ctx: ToolContext) -> ToolResult:
        provider = ctx.config.get("tools", {}).get("video", {}).get("provider", "none")
        if provider == "none":
            raise ToolError("NEEDS_CONFIG",
                            "Video provider 未配置：在 config 中设置 tools.video.provider 与 API 密钥")
        raise ToolError("PROVIDER_NOT_IMPLEMENTED", f"Video provider {provider!r} 待接入")
