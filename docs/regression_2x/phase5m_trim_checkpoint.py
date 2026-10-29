# -*- coding: utf-8 -*-
"""截断 5-M 断点卡：保留新写的「已结项」内容，删除其后遗留的归档版旧章节。幂等。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
P = Path(r"C:\mp4agent\video-studio\docs\regression_2x\PHASE5M_CHECKPOINT.md")
lines = P.read_text(encoding="utf-8").splitlines(keepends=True)
marker = "## 1. 已完成且已验证（全绿）"
idx = [i for i, l in enumerate(lines) if l.strip() == marker]
if not idx:
    print("stale section not found -> no change; lines:", len(lines))
else:
    cut = idx[0]
    # 去掉紧随其前的分隔线
    while cut > 0 and lines[cut - 1].strip() in ("", "---"):
        cut -= 1
    new = lines[:cut]
    while new and new[-1].strip() == "":
        new.pop()
    P.write_text("".join(new) + "\n", encoding="utf-8")
    print("truncated:", len(lines), "->", len(new) + 1, "lines")
