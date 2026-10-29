# -*- coding: utf-8 -*-
"""P32-2：核对 P17 attr_pack 的画面帧/素材 与 池内素材的对应关系（供双门语料定版）。只读。"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

from PIL import Image

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
PACK = R / "output" / "phase17_attr_pack"
POOL = R / "docs" / "regression_2x" / "logs" / "phase16_retrieval_payload.json"
SCENES = ("S02", "S06", "S07", "S08", "S13")


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def main() -> int:
    pool = [c for c in json.loads(POOL.read_text(encoding="utf-8"))["candidates"]
            if c.get("path")]
    by_sha = {c["sha256"]: c for c in pool}
    print("池内文件 sha 索引 {} 张".format(len(by_sha)))
    print()
    for s in SCENES:
        d = PACK / s
        assets = [p for p in d.glob("asset.*")]
        frames = sorted(d.glob("frame_*.png"))
        print("=== {} : asset={} frames={} ===".format(
            s, [a.name for a in assets], len(frames)))
        for a in assets:
            h = sha(a)
            hit = by_sha.get(h)
            with Image.open(a) as im:
                sz = im.size
            print("   asset {} {} {} | 池内匹配: {}".format(
                a.name, sz, h[:12],
                (hit or {}).get("name") or ("**不在池内**" if not hit else "")))
            print("      池内相对路径: {}".format((hit or {}).get("relative_path")))
        for f in frames[:1]:
            with Image.open(f) as im:
                print("   frame 样例 {} {}".format(f.name, im.size))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
