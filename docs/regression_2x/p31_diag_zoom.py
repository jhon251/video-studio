# -*- coding: utf-8 -*-
"""P31：定位 S11p2/S13p2 核验低分的原因（运动推近 vs 素材的内容覆盖）。

对同一成片帧，计算：
  · 与「素材全图 48×48」的 corr（= 冻结旧口径）
  · 与「素材中心 w% 子窗口 48×48」的 corr（模拟不同推近程度）
⇒ 若中心子窗口的 corr 明显更高，说明**低分来自推近裁剪**，而非素材不在屏。
只读。
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
from PIL import Image

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core.materials import frame_corr                            # noqa: E402


def g48(im, res=48):
    return np.asarray(im.convert("L").resize((res, res)), dtype=np.float64)


def center_crop(im, frac):
    W, H = im.size
    w, h = int(W * frac), int(H * frac)
    x0, y0 = (W - w) // 2, (H - h) // 2
    return im.crop((x0, y0, x0 + w, y0 + h))


def main() -> int:
    pool = [c for c in json.loads(
        (R / "docs/regression_2x/logs/phase16_retrieval_payload.json")
        .read_text(encoding="utf-8"))["candidates"] if c.get("path")]
    bysha = {c["sha256"]: c for c in pool}
    FR = R / "output/p31_probe/frames"
    for sid, sha in (("S11p2", "301ff850be9cc1a1dd460fcfa6ce2763d0786c5ba2c42193915a74efcb1f99ba"),
                     ("S13p2", "301ff850be9cc1a1dd460fcfa6ce2763d0786c5ba2c42193915a74efcb1f99ba")):
        fp = FR / "{}.png".format(sid)
        ap = bysha[sha]["path"]
        with Image.open(fp) as f, Image.open(ap) as a:
            fg = g48(f)
            print("=== {} ===".format(sid))
            print("  成片帧 {}x{} | 素材 {}x{}  ({})".format(
                f.size[0], f.size[1], a.size[0], a.size[1],
                pathlib.Path(ap).name[:40]))
            base = frame_corr(fg, g48(a))
            print("  素材全图 48×48 corr            = {:.3f}   (= 冻结旧口径)".format(base))
            for frac in (0.5, 0.6, 0.7, 0.8, 0.9, 1.0):
                c = frame_corr(fg, g48(center_crop(a, frac)))
                print("  素材中心 {:>3.0f}% 子窗口 corr      = {:.3f}".format(frac * 100, c))
            # 素材按 16:9 中心裁到与成片同宽高比后再比
            W, H = a.size
            tw = min(W, int(H * 16 / 9))
            cc = center_crop(a, tw / W) if tw < W else a
            print("  素材 16:9 中心裁切 corr         = {:.3f}".format(frame_corr(fg, g48(cc))))
            print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
