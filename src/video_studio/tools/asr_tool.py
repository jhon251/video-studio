"""ASR 工具：本地 faster-whisper（V1）；可切换云端 ASR。"""

from __future__ import annotations

from .base import Tool, ToolContext, ToolError, ToolResult


class ASRTool(Tool):
    name = "asr"
    input_schema = {
        "type": "object",
        "properties": {
            "audio": {"type": "string"},
            "language": {"type": "string"},
        },
        "required": ["audio"],
    }
    permissions = ["asr"]

    def execute(self, inputs: dict, ctx: ToolContext) -> ToolResult:
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise ToolError("PROVIDER_MISSING",
                            "未安装 faster-whisper：pip install faster-whisper（或配置云端 ASR provider）") from None
        audio = (ctx.project_dir / inputs["audio"]).resolve()
        if not audio.is_file():
            raise ToolError("NOT_FOUND", f"音频不存在: {inputs['audio']}")
        model = WhisperModel("base", device="cpu", compute_type="int8")
        segments, info = model.transcribe(str(audio), language=inputs.get("language"))
        segs = [{"start": s.start, "end": s.end, "text": s.text} for s in segments]
        return ToolResult(ok=True, data={"language": info.language, "segments": segs})
