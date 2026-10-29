# -*- coding: utf-8 -*-
"""P33-2 核查：扩容池构成 + 相邻同素材 / 每素材景数（分配纪律）。"""
from __future__ import annotations

import collections
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")

POOL = L / "phase33_retrieval_payload.json"


def main() -> int:
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    cands = [c for c in pool["candidates"] if c.get("path")]
    uniq = {c["sha256"] for c in cands}
    new = [c for c in cands if str(c.get("origin") or "").startswith("P33-2")]
    print("池候选 {} 条 | 唯一 sha {} | 本轮新增 {}".format(len(cands), len(uniq), len(new)))
    print()
    print("=== 新增 ===")
    for c in new:
        p = pathlib.Path(c["path"])
        print("  {:<46} {}x{} {:<16} {}".format(
            str(c["name"])[:46], c.get("width"), c.get("height"),
            str(c.get("license"))[:16], "OK" if p.is_file() else "**缺失**"))
    print()
    print("=== 全池唯一素材 ===")
    for i, c in enumerate(sorted(cands, key=lambda x: str(x.get("name")))):
        print("  {:>2}. {:<48} {}".format(i + 1, str(c.get("name"))[:48],
                                          str(c.get("sha256"))[:12]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
