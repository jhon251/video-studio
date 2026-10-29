"""TTS 工具：provider 可切换。

- edge-tts：本地免费（需 pip install edge-tts）
- volcengine：火山引擎语音合成 HTTP 接口，支持"声音复刻"voice_type（用户克隆音色）
- 其他云端复刻服务：按 docs/声音克隆接入指南.md 扩展
"""

from __future__ import annotations

import base64
import uuid

from .base import Tool, ToolContext, ToolError, ToolResult


class TTSTool(Tool):
    name = "tts"
    input_schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "voice": {"type": "string"},
            "output": {"type": "string"},
        },
        "required": ["text", "output"],
    }
    permissions = ["tts"]

    def execute(self, inputs: dict, ctx: ToolContext) -> ToolResult:
        cfg = ctx.config.get("tools", {}).get("tts", {})
        provider = cfg.get("provider", "none")
        if provider == "none":
            raise ToolError("NEEDS_CONFIG", "TTS provider 未配置：config.tools.tts.provider")
        if provider == "edge-tts":
            return self._edge_tts(inputs, ctx)
        if provider == "volcengine":
            return self._volcengine(inputs, ctx, cfg)
        raise ToolError("PROVIDER_NOT_IMPLEMENTED", f"TTS provider {provider!r} 待接入")

    def _save_audio(self, ctx: ToolContext, rel: str, data: bytes) -> str:
        out_path = (ctx.project_dir / rel).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(data)
        return rel

    def _edge_tts(self, inputs: dict, ctx: ToolContext) -> ToolResult:
        try:
            import asyncio
            import edge_tts
        except ImportError:
            raise ToolError("PROVIDER_MISSING",
                            "未安装 edge-tts：pip install edge-tts（或配置云端 TTS provider）") from None
        out_path = (ctx.project_dir / inputs["output"]).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)

        async def _run():
            voice = inputs.get("voice") or "zh-CN-XiaoxiaoNeural"
            tts = edge_tts.Communicate(inputs["text"], voice)
            await tts.save(str(out_path))

        try:
            asyncio.run(_run())
        except Exception as exc:   # edge-tts 抛 ValueError/网络异常，须转成 ToolError，
            # 否则 VoiceAgent 的 except ToolError 优雅降级路径失效，voice 任务会硬失败并阻塞 render。
            raise ToolError("TTS_FAILED", f"edge-tts 合成失败: {type(exc).__name__}: {exc}") from None
        return ToolResult(ok=True, data={"audio": inputs["output"],
                                         "voice": inputs.get("voice") or "zh-CN-XiaoxiaoNeural"})

    def _volcengine(self, inputs: dict, ctx: ToolContext, cfg: dict) -> ToolResult:
        """火山引擎语音合成 HTTP 接口（声音复刻 voice_type 直接可用）。

        配置（config.tools.tts）：appid / token / cluster / voice_type
        voice_type 即声音复刻审核通过后获得的音色 ID（如 S_xxx）。
        """
        import requests

        appid = cfg.get("appid", "")
        token = cfg.get("token", "")
        cluster = cfg.get("cluster", "volcano_tts")
        voice_type = cfg.get("voice_type") or inputs.get("voice")
        if not appid or not token or not voice_type:
            raise ToolError("NEEDS_CONFIG",
                            "火山引擎配置缺失：config.tools.tts 需要 appid / token / voice_type（声音复刻音色ID）")
        payload = {
            "app": {"appid": appid, "token": token, "cluster": cluster},
            "user": {"uid": "video-studio"},
            "audio": {"voice_type": voice_type, "encoding": "mp3"},
            "request": {"reqid": str(uuid.uuid4()), "text": inputs["text"], "operation": "query"},
        }
        resp = requests.post(
            "https://openspeech.bytedance.com/api/v1/tts",
            headers={"Authorization": f"Bearer;{token}", "Content-Type": "application/json"},
            json=payload, timeout=180,
        )
        try:
            body = resp.json()
        except ValueError:
            raise ToolError("TTS_FAILED", f"响应非 JSON: HTTP {resp.status_code}") from None
        if body.get("code") != 3000:
            raise ToolError("TTS_FAILED", f"火山引擎返回 {body.get('code')}: {body.get('message', '')[:200]}")
        audio = base64.b64decode(body["data"])
        rel = self._save_audio(ctx, inputs["output"], audio)
        return ToolResult(ok=True, data={"audio": rel, "voice": voice_type})
