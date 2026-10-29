# -*- coding: utf-8 -*-
"""5-K 修复：把被误合并的 #62/#63 两行正确拆开（幂等）。

背景：两次 edit 误用「行首前缀」作为 old_string，导致 #62 行头被 #63 行替换、
#62 的正文黏在 #63 行尾。本脚本按「：旧配置的」切分并重建两行。
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
P = Path(r"C:\mp4agent\video-studio\docs\KNOWN_ISSUES.md")
H62 = ("| **#62** | **采用新默认配置（`config/config.json` 去掉内联 `llm.mock.responses`）后，"
       "离线回归项 `run_ingest_test` 转红（根因已实测定位）**")
lines = P.read_text(encoding="utf-8").splitlines(keepends=True)
out, fixed = [], 0
for ln in lines:
    if ln.startswith("| **#63**") and "：旧配置的" in ln:
        head, tail = ln.split("：旧配置的", 1)
        head = head.rstrip()
        if not head.endswith("|"):
            head += " |"
        tail = "：旧配置的" + tail
        if tail.rstrip().endswith("|"):
            row62 = H62 + tail
            out.append(head + "\n")
            out.append(row62)
            fixed += 1
            continue
    out.append(ln)
if fixed:
    P.write_text("".join(out), encoding="utf-8")
print("repaired rows:", fixed)
