# -*- coding: utf-8 -*-
"""定位含"内层直引号"的可疑行（中文串里再写 " 会破坏 Python 语法）。"""
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")
p = pathlib.Path(sys.argv[1])
for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
    if ln.count('"') > 2 and ("check(" in ln or ln.lstrip().startswith('"')):
        print(i, ln[:170])
