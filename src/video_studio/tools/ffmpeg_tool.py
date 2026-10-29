"""FFmpeg 工具：探测与合成。ffmpeg 缺失时报 FFMPEG_MISSING，由上层降级策略处理。

V2.0.4（3.x-Preflight）：新增 ffprobe 二进制真实性检查。
历史缺陷：bin/ffprobe.exe 曾是 bin/ffmpeg.exe 的副本（同 SHA256），`probe` 因 rc!=0 静默落到
`ffmpeg -i` 降级路径，掩盖了问题；若换了调用参数还会返回"无流"这类误导结果。
现在：检测到 ffprobe 与 ffmpeg 为同一文件、或自称不是 ffprobe 时，**明确报错 FFPROBE_INVALID**，
不再继续返回可能误导的探测结果。
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from .base import Tool, ToolContext, ToolError, ToolResult

# ffprobe 身份校验缓存：path -> (size, mtime, ok, reason)
_FFPROBE_IDENTITY_CACHE: dict[str, tuple[int, float, bool, str]] = {}


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_ffprobe(ffprobe: str | None, ffmpeg: str | None) -> tuple[bool, str]:
    """校验 ffprobe 是否为真实 ffprobe 二进制（fail-closed）。

    判定：① 文件存在；② 与 ffmpeg **不是同一文件**（字节级 SHA256 比较）；
         ③ `-version` 可执行且自述为 ffprobe。
    返回 (ok, reason)。结果按 (size, mtime) 缓存，避免每次探测重复哈希大文件。
    """
    if not ffprobe:
        return False, "未配置/未找到 ffprobe（tools.ffmpeg.ffprobe）"
    p = Path(ffprobe)
    if not p.is_file():
        return False, f"ffprobe 路径不存在：{ffprobe}"
    try:
        st = p.stat()
    except OSError as exc:
        return False, f"ffprobe 无法访问：{exc}"
    key = str(p.resolve())
    cached = _FFPROBE_IDENTITY_CACHE.get(key)
    if cached and cached[0] == st.st_size and cached[1] == st.st_mtime:
        return cached[2], cached[3]

    ok, reason = True, "ok"
    if ffmpeg and Path(ffmpeg).is_file():
        try:
            if _sha256_file(str(p)) == _sha256_file(str(ffmpeg)):
                ok, reason = False, ("ffprobe 与 ffmpeg 是同一文件（SHA256 相同）——"
                                     "这是 ffmpeg 的副本，不是真 ffprobe")
        except OSError as exc:
            ok, reason = False, f"哈希比对失败：{exc}"
    if ok:
        try:
            out = subprocess.run([str(p), "-version"], capture_output=True, text=True,
                                 timeout=60, encoding="utf-8", errors="replace")
            head = ((out.stdout or "") + (out.stderr or ""))[:400].lower()
            if out.returncode != 0 or "ffprobe" not in head:
                ok, reason = False, ("`-version` 未自述为 ffprobe（疑似 ffmpeg 或其他二进制冒充）："
                                     + head.strip()[:120])
        except (OSError, subprocess.SubprocessError) as exc:
            ok, reason = False, f"无法执行 `-version`：{exc}"
    _FFPROBE_IDENTITY_CACHE[key] = (st.st_size, st.st_mtime, ok, reason)
    return ok, reason


class FFmpegTool(Tool):
    name = "ffmpeg"
    input_schema = {
        "type": "object",
        "properties": {
            "op": {"type": "string", "enum": ["probe", "concat", "render"]},
            "inputs": {"type": "array"},
            "output": {"type": "string"},
            "args": {"type": "array"},
        },
        "required": ["op"],
    }
    permissions = ["ffmpeg"]

    def execute(self, inputs: dict, ctx: ToolContext) -> ToolResult:
        cfg = ctx.config.get("tools", {}).get("ffmpeg", {})
        ffmpeg = shutil.which(cfg.get("path", "ffmpeg"))
        ffprobe = shutil.which(cfg.get("ffprobe", "ffprobe"))
        if ffmpeg is None:
            raise ToolError("FFMPEG_MISSING", "未安装 ffmpeg，请安装或配置 tools.ffmpeg.path")
        op = inputs.get("op")
        if op == "raw":
            # 无输入文件的完整命令（如 lavfi 合成）：args 为完整参数尾，output 为输出
            out_rel = inputs.get("output")
            if not out_rel:
                raise ToolError("BAD_INPUT", "缺少 output")
            out_path = (ctx.project_dir / out_rel).resolve()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            cmd = [ffmpeg, "-y", *inputs.get("args", []), str(out_path)]
            # 7200s：多图片输入（-loop 1 逐帧重解码 ×N 段 concat）在长片上可超 30min
            # （实测 p_96efdc03e1aa 21 段图片时间轴 > 1800s，占位色块仅 ~2min），原 1800s 会误杀正常渲染
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=7200,
                                  encoding="utf-8", errors="replace")
            if proc.returncode != 0:
                raise ToolError("RENDER_FAILED", proc.stderr[-300:])
            return ToolResult(ok=True, data={"output": str(out_path)})
        if op == "probe":
            src = inputs.get("inputs", [""])[0]
            target = (ctx.project_dir / src).resolve()
            # 优先 ffprobe（须先通过真实性校验）；ffprobe 缺失时降级为解析 `ffmpeg -i` 的 stderr。
            if ffprobe is not None:
                ok, why = verify_ffprobe(ffprobe, ffmpeg)
                if not ok:
                    # 明确报错，绝不返回"无流"之类由错误二进制造成的误导结果
                    raise ToolError("FFPROBE_INVALID", why)
                out = subprocess.run(
                    [ffprobe, "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(target)],
                    capture_output=True, text=True, timeout=120, encoding="utf-8", errors="replace",
                )
                if out.returncode == 0:
                    info = json.loads(out.stdout)
                    streams = [
                        {"codec_type": s.get("codec_type"), "codec_name": s.get("codec_name"),
                         "duration": s.get("duration"), "width": s.get("width"), "height": s.get("height"),
                         # 3.x Phase 3-B：音频采样率/声道（纯新增字段）——响度母带链必须知道
                         # 输入采样率才能用 `aresample` 复原（loudnorm 会输出 192kHz）
                         "sample_rate": s.get("sample_rate"), "channels": s.get("channels")}
                        for s in info.get("streams", [])
                    ]
                    # 3.x Phase 2-B.1：附带容器时长（旁白时长契约需要它；纯新增字段）
                    return ToolResult(ok=True, data={"streams": streams,
                                                     "duration": (info.get("format") or {}).get("duration"),
                                                     "format": info.get("format", {}).get("format_name"),
                                                     "probe_engine": "ffprobe",
                                                     "ffprobe": str(ffprobe)})
            # fallback：解析 `ffmpeg -i` 的 stderr
            out = subprocess.run([ffmpeg, "-hide_banner", "-i", str(target)],
                                 capture_output=True, text=True, timeout=120,
                                 encoding="utf-8", errors="replace")
            if out.returncode != 0 and "At least one output file" not in out.stderr:
                raise ToolError("PROBE_FAILED", out.stderr[:300])
            import re as _re
            streams = []
            for m in _re.finditer(r"Stream #(\d+):(\d+)(?:\[[^\]]+\])?(?:\([^)]*\))?: ([^:]+): ([^\n]+)", out.stderr):
                codec_type = m.group(3).strip().lower()
                detail = m.group(4).strip()
                width = height = duration = None
                dm = _re.search(r"(?<![0-9a-fA-F])(\d{2,5})x(\d{2,5})\b", detail)
                if dm:
                    width, height = int(dm.group(1)), int(dm.group(2))
                # 3.x Phase 3-B：从 ffmpeg stderr 里解析音频采样率/声道（纯新增字段）
                sr = _re.search(r"(\d+) Hz", detail)
                ch = _re.search(r"(mono|stereo|[\d.]+\(.*?\)|[\d.]+ channels)", detail)
                ch_n = None
                if ch:
                    raw_ch = ch.group(1)
                    ch_n = {"mono": 1, "stereo": 2}.get(raw_ch)
                    if ch_n is None:
                        cm = _re.match(r"([\d.]+)", raw_ch)
                        ch_n = float(cm.group(1)) if cm else None
                        ch_n = int(ch_n) if ch_n is not None and float(ch_n).is_integer() else ch_n
                streams.append({"codec_type": codec_type, "codec_name": detail.split(",")[0].strip(),
                                "duration": duration, "width": width, "height": height,
                                "sample_rate": (sr.group(1) if sr else None), "channels": ch_n})
            dm2 = _re.search(r"Duration: (\d+):(\d+):([\d.]+)", out.stderr)
            if dm2:
                total = int(dm2.group(1)) * 3600 + int(dm2.group(2)) * 60 + float(dm2.group(3))
                for s in streams:
                    if s["duration"] is None:
                        s["duration"] = str(total)
            return ToolResult(ok=True, data={"streams": streams, "format": "parsed-from-ffmpeg",
                                             "probe_engine": "ffmpeg-stderr"})
        if op == "concat":
            files = [(ctx.project_dir / f).resolve() for f in inputs.get("inputs", [])]
            out_rel = inputs.get("output")
            if not out_rel:
                raise ToolError("BAD_INPUT", "缺少 output")
            out_path = (ctx.project_dir / out_rel).resolve()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            concat_file = out_path.with_suffix(".txt")
            concat_file.write_text(
                "".join(f"file '{p.as_posix()}'\n" for p in files), encoding="utf-8")
            cmd = [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
                   "-c", "copy", str(out_path)]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600,
                                  encoding="utf-8", errors="replace")
            if proc.returncode != 0:
                raise ToolError("CONCAT_FAILED", proc.stderr[-300:])
            return ToolResult(ok=True, data={"output": str(out_path)})
        if op == "render":
            # 通用渲染：inputs[0] 为输入，args 为 ffmpeg 参数，output 为输出
            src = (ctx.project_dir / inputs.get("inputs", [""])[0]).resolve()
            out_rel = inputs.get("output")
            if not out_rel:
                raise ToolError("BAD_INPUT", "缺少 output")
            out_path = (ctx.project_dir / out_rel).resolve()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            cmd = [ffmpeg, "-y", "-i", str(src), *inputs.get("args", []), str(out_path)]
            # 与 raw op 同步：7200s（长片响度校正重编码同样可能超 30min）
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=7200,
                                  encoding="utf-8", errors="replace")
            if proc.returncode != 0:
                raise ToolError("RENDER_FAILED", proc.stderr[-300:])
            return ToolResult(ok=True, data={"output": str(out_path)})
        raise ToolError("BAD_INPUT", f"未知操作: {op}")
