# -*- coding: utf-8 -*-
"""5-K：把 KNOWN_ISSUES §18 的 #52..#63 行按编号升序重排（幂等）。"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
P = Path(r"C:\mp4agent\video-studio\docs\KNOWN_ISSUES.md")
lines = P.read_text(encoding="utf-8").splitlines(keepends=True)
idx = [i for i, l in enumerate(lines) if re.match(r"^\| \*\*#\d+\*\* \|", l) and
       int(re.match(r"^\| \*\*#(\d+)\*\* \|", l).group(1)) >= 52]
if not idx:
    print("no 5-K rows found")
    raise SystemExit(0)
lo, hi = min(idx), max(idx)
block = lines[lo:hi + 1]
if any(not re.match(r"^\| \*\*#\d+\*\* \|", l) for l in block):
    print("block not contiguous / unexpected content -> no change")
    raise SystemExit(0)
ordered = sorted(block, key=lambda l: int(re.match(r"^\| \*\*#(\d+)\*\* \|", l).group(1)))
if ordered == block:
    print("already ordered")
else:
    lines[lo:hi + 1] = ordered
    P.write_text("".join(lines), encoding="utf-8")
    print("reordered", len(block), "rows ->",
          [int(re.match(r"^\| \*\*#(\d+)\*\* \|", l).group(1)) for l in ordered])
