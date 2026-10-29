# -*- coding: utf-8 -*-
"""把 PHASE6A_M1_REPORT.md 的 §8/§9 顺序理顺（§8 边界确认 在前、§9 过程披露 在后）。幂等。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
P = Path(r"C:\mp4agent\video-studio\docs\regression_2x\PHASE6A_M1_REPORT.md")
lines = P.read_text(encoding="utf-8").splitlines(keepends=True)
idx8 = next((i for i, l in enumerate(lines) if l.startswith("## 8. ")), None)
idx9 = next((i for i, l in enumerate(lines) if l.startswith("## 9. ")), None)
if idx8 is None or idx9 is None:
    print("sections not found:", idx8, idx9)
elif idx9 < idx8:
    sec9 = lines[idx9:idx8]
    sec8 = lines[idx8:]
    lines = lines[:idx9] + sec8 + sec9
    P.write_text("".join(lines), encoding="utf-8")
    print("swapped: §8 now before §9")
else:
    print("already ordered")
