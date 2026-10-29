# -*- coding: utf-8 -*-
"""Phase 10：枚举 JSON 格式变体，找出与基线钉定 sha256 一致的写法（7b03424846f1…）。"""
import collections
import hashlib
import itertools
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
TARGET = "7b03424846f15efc"
p = R / "config" / "config.json"
j = json.loads(p.read_text(encoding="utf-8"), object_pairs_hook=collections.OrderedDict)
if "topic_signals" in (j.get("tools") or {}):
    j["tools"].pop("topic_signals")

hits = []
for indent, ea, nl, sep in itertools.product([None, 1, 2, 4], [True, False], ["", "\n"],
                                            [None, (",", ": "), (",", ":")]):
    kw = {"ensure_ascii": ea, "indent": indent}
    if sep:
        kw["separators"] = sep
    txt = json.dumps(j, **kw) + nl
    h = hashlib.sha256(txt.encode("utf-8")).hexdigest()
    if h.startswith(TARGET):
        hits.append((indent, ea, repr(nl), sep, h))
print("命中:", hits if hits else "无")
# 顺带打印几个候选值，便于判断差距
for indent, ea, nl in ((2, False, "\n"), (2, False, ""), (4, False, "\n"), (2, True, "\n")):
    txt = json.dumps(j, ensure_ascii=ea, indent=indent) + nl
    print("  indent={} ensure_ascii={} nl={!r} -> {}".format(
        indent, ea, nl, hashlib.sha256(txt.encode("utf-8")).hexdigest()[:16]))
print("当前磁盘:", hashlib.sha256(p.read_bytes()).hexdigest()[:16])
