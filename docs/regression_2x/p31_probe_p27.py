# -*- coding: utf-8 -*-
"""读取 phase27_p27_3_verification.json 中 DQ-2 相关字段。"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
d = json.loads((R / "docs/regression_2x/logs/phase27_p27_3_verification.json")
               .read_text(encoding="utf-8"))
print("top keys:", list(d.keys()))


def walk(o, path="", depth=0):
    if depth > 6:
        return
    if isinstance(o, dict):
        for k, v in o.items():
            kl = str(k).lower()
            if "dq" in kl or "share" in kl or "unique" in kl or "reuse" in kl:
                s = json.dumps(v, ensure_ascii=False)
                print("{}{}: {}".format("  " * depth, k, s[:300]))
            if isinstance(v, (dict, list)):
                walk(v, path + "/" + str(k), depth + 1)
    elif isinstance(o, list):
        for i, v in enumerate(o[:4]):
            walk(v, path + "[%d]" % i, depth + 1)


walk(d)
