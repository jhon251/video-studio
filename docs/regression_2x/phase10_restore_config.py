# -*- coding: utf-8 -*-
"""Phase 10：把 config.json / config.example.json 的 `tools.topic_signals` 块**移除**，
使 config.json 逐字节复原到基线钉定值（sha256 目标：manifest 内的 7b03424846f1…）。"""
import collections
import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
TARGET = "7b03424846f15efc"          # manifest 钉定的 config.json sha256 前 16 位


def restore(path: pathlib.Path, target_prefix: str | None) -> None:
    j = json.loads(path.read_text(encoding="utf-8"),
                   object_pairs_hook=collections.OrderedDict)
    tools = j.get("tools") or {}
    if "topic_signals" in tools:
        tools.pop("topic_signals")
    path.write_text(json.dumps(j, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    h = hashlib.sha256(path.read_bytes()).hexdigest()
    ok = (target_prefix is None) or h.startswith(target_prefix)
    print("  {} -> sha256 {}  {}".format(path.name, h[:16], "✓ 与基线一致" if ok else "✗ 仍不一致"))
    return ok


ok1 = restore(R / "config" / "config.json", TARGET)
restore(R / "config" / "config.example.json", None)
print("config.json 复原:", ok1)
sys.exit(0 if ok1 else 1)
