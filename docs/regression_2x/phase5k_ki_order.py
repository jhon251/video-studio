# -*- coding: utf-8 -*-
"""5-K 文档整理：把 KNOWN_ISSUES §18 的 #62 行移到 #61 之后（保持编号顺序）。幂等。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
p = Path(r"C:\mp4agent\video-studio\docs\KNOWN_ISSUES.md")
lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
i62 = next((i for i, l in enumerate(lines) if l.startswith("| **#62**")), None)
i61 = next((i for i, l in enumerate(lines) if l.startswith("| **#61**")), None)
if i62 is None or i61 is None:
    print("rows not both found:", i62, i61)
elif i62 < i61:
    row = lines.pop(i62)
    i61 = next(i for i, l in enumerate(lines) if l.startswith("| **#61**"))
    lines.insert(i61 + 1, row)
    p.write_text("".join(lines), encoding="utf-8")
    print("swapped: #62 now after #61")
else:
    print("already ordered (#61 before #62)")
