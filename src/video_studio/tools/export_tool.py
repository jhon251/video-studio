"""Export 工具：多版本导出（分辨率/画幅适配，FFmpeg 执行）。"""

from __future__ import annotations

from .base import Tool, ToolContext, ToolResult
from .ffmpeg_tool import FFmpegTool


class ExportTool(Tool):
    name = "export"
    input_schema = {
        "type": "object",
        "properties": {
            "input": {"type": "string"},
            "output": {"type": "string"},
            "resolution": {"type": "string"},
            "aspect": {"type": "string", "enum": ["16:9", "9:16", "1:1"]},
        },
        "required": ["input", "output"],
    }
    permissions = ["export"]

    def execute(self, inputs: dict, ctx: ToolContext) -> ToolResult:
        src = (ctx.project_dir / inputs["input"]).resolve()
        out_path = (ctx.project_dir / inputs["output"]).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        resolution = inputs.get("resolution") or "1920x1080"
        args = [
            "-vf", f"scale={resolution}:force_original_aspect_ratio=decrease,"
                   f"pad={resolution}:(ow-iw)/2:(oh-ih)/2",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        ]
        src_rel = src.relative_to(ctx.project_dir).as_posix()
        out_rel = out_path.relative_to(ctx.project_dir).as_posix()
        return FFmpegTool().execute({"op": "render", "inputs": [src_rel], "args": args,
                                     "output": out_rel}, ctx)
