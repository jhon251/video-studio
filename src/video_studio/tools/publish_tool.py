"""Publish 工具：V1 = 生成发布包与清单，实际发布由人工执行（需人工批准令牌）。"""

from __future__ import annotations

import json

from .base import Tool, ToolContext, ToolError, ToolResult


class PublishTool(Tool):
    name = "publish"
    input_schema = {
        "type": "object",
        "properties": {
            "video": {"type": "string"},
            "metadata_ref": {"type": "string"},
            "platform": {"type": "string"},
        },
        "required": ["video", "platform"],
    }
    permissions = ["publish"]
    requires_human = True   # 发布必须人工批准（系统级禁令 #2）

    def execute(self, inputs: dict, ctx: ToolContext) -> ToolResult:
        if ctx.human_token is None:
            raise ToolError("NEEDS_HUMAN", "发布需要人工批准令牌")
        video = (ctx.project_dir / inputs["video"]).resolve()
        if not video.is_file():
            raise ToolError("NOT_FOUND", f"视频不存在: {inputs['video']}")
        pkg_dir = ctx.project_dir / "output" / "publish"
        pkg_dir.mkdir(parents=True, exist_ok=True)
        # V2：发布稿嵌入的元数据文案必须剥离 [CLAIM:xxx] 标记
        from ..core.strip import strip_claims_deep
        metadata_copy = None
        metadata_ref = inputs.get("metadata_ref")
        if metadata_ref and ctx.db is not None:
            art = ctx.db.get_artifact(metadata_ref)
            if art:
                try:
                    with open(art["path"], encoding="utf-8") as fh:
                        metadata_copy = strip_claims_deep(json.load(fh))
                except (OSError, json.JSONDecodeError):
                    metadata_copy = None
        manifest = {
            "platform": inputs["platform"],
            "video": inputs["video"],
            "metadata_ref": metadata_ref,
            "metadata": metadata_copy,
            "status": "ready_for_human",
            "instructions": "人工执行发布：将视频上传至目标平台并粘贴元数据",
        }
        (pkg_dir / f"publish_{inputs['platform']}.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return ToolResult(ok=True, data={"package": str(pkg_dir), "manifest": manifest})
