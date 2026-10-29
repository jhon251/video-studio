# -*- coding: utf-8 -*-
"""精确检查 .env 的 VLM_API_KEY 行（不打印完整密钥）：长度、可见字符、异常字符。"""
from __future__ import annotations

import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
p = R / ".env"
print("exists:", p.is_file(), "| bytes:", p.stat().st_size if p.is_file() else None)

for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
    if "VLM" not in line and "vlm" not in line:
        continue
    print("-" * 70)
    print("line", i, "| raw repr (keys masked):")
    # 只显示键名与值的首尾少量字符，避免泄露
    if "=" in line:
        k, _, v = line.partition("=")
        v = v.strip()
        print("   key   =", repr(k))
        print("   value len =", len(v))
        print("   head  =", repr(v[:6]))
        print("   tail  =", repr(v[-4:]))
        bad = [(j, ch, ord(ch)) for j, ch in enumerate(v)
               if not (ch.isalnum() or ch in "-_.")]
        print("   non-token chars:", bad[:12])
    else:
        print("   (no '='):", repr(line[:40]))

print()
print("=== load_env 行为探测 ===")
import os
sys.path.insert(0, str(R / "src"))
from video_studio.core.env import load_env
before = os.environ.get("VLM_API_KEY")
print("before load_env: present =", before is not None,
      "| len =", len(before) if before else 0)
load_env(R / ".env")
after = os.environ.get("VLM_API_KEY")
print("after  load_env: present =", after is not None,
      "| len =", len(after) if after else 0)
if after:
    print("  head =", repr(after[:6]), "tail =", repr(after[-4:]))
