"""Subtitle 工具：SRT 解析 / 平移 / 合并（纯本地，确定性）。"""

from __future__ import annotations

import re

from .base import Tool, ToolContext, ToolError, ToolResult


def parse_srt(text: str) -> list[dict]:
    blocks = re.split(r"\n\s*\n", text.strip())
    entries = []
    for block in blocks:
        lines = [l.strip() for l in block.strip().splitlines() if l.strip()]
        if len(lines) < 2:
            continue
        m = re.match(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)", lines[1])
        if not m:
            continue
        start = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) + int(m.group(4)) / 1000
        end = int(m.group(5)) * 3600 + int(m.group(6)) * 60 + int(m.group(7)) + int(m.group(8)) / 1000
        entries.append({"start": start, "end": end, "text": "\n".join(lines[2:])})
    return entries


def fmt_ts(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, rem = divmod(ms, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


class SubtitleTool(Tool):
    name = "subtitle"
    input_schema = {
        "type": "object",
        "properties": {
            "op": {"type": "string", "enum": ["parse", "shift", "merge"]},
            "srt": {"type": "string"},
            "shift_s": {"type": "number"},
            "output": {"type": "string"},
        },
        "required": ["op"],
    }
    permissions = ["subtitle"]

    def execute(self, inputs: dict, ctx: ToolContext) -> ToolResult:
        op = inputs.get("op")
        if op == "parse":
            entries = parse_srt(inputs.get("srt", ""))
            return ToolResult(ok=True, data={"entries": entries})
        if op == "shift":
            entries = parse_srt(inputs.get("srt", ""))
            delta = float(inputs.get("shift_s", 0))
            out = "\n".join(
                f"{i}\n{fmt_ts(e['start'] + delta)} --> {fmt_ts(e['end'] + delta)}\n{e['text']}\n"
                for i, e in enumerate(entries, 1))
            if inputs.get("output"):
                (ctx.project_dir / inputs["output"]).write_text(out, encoding="utf-8")
            return ToolResult(ok=True, data={"srt": out})
        if op == "merge":
            merged = sorted(
                [e for srt in (inputs.get("srt", ""),) for e in parse_srt(srt)],
                key=lambda e: e["start"])
            out = "\n".join(
                f"{i}\n{fmt_ts(e['start'])} --> {fmt_ts(e['end'])}\n{e['text']}\n"
                for i, e in enumerate(merged, 1))
            if inputs.get("output"):
                (ctx.project_dir / inputs["output"]).write_text(out, encoding="utf-8")
            return ToolResult(ok=True, data={"srt": out})
        raise ToolError("BAD_INPUT", f"未知操作: {op}")
