# -*- coding: utf-8 -*-
"""P34-3 前置：把 v4.1 全文按段导出为**可读文本**（供人工识别"核查腔"跨度）。"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
sc = json.loads((R / "output/phase33_script_sandbox/script_p33_v41_40seg.json")
                .read_text(encoding="utf-8"))
lines, total = [], 0
for s in sc["segments"]:
    n = s.get("narration") or ""
    total += len(n)
    lines.append("### {} ({} 字, {:.1f}s)\n{}".format(
        s["scene_id"], len(n), float(s.get("duration_s") or 0), n))
out = "# v4.1 全文（40 段，共 {} 字）\n\n".format(total) + "\n\n".join(lines)
p = R / "output" / "p34_probe" / "v41_fulltext.md"
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(out, encoding="utf-8")
print("总字数", total, "->", p.relative_to(R))
