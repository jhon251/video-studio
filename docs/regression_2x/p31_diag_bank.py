# -*- coding: utf-8 -*-
"""P31：bank_score 的最优窗口 vs 手工 16:9 网格窗口对比（定位 bank 覆盖边界）。只读。"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
from PIL import Image

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import corr_diagnostics as CD                          # noqa: E402

ASSET = (R / "projects/p_96efdc03e1aa/media/"
         "301ff850be9cc1a1dd460fcfa6ce2763d0786c5ba2c42193915a74efcb1f99ba.jpg")
FR = R / "output/p31_probe/frames"


def main() -> int:
    pool = [c for c in json.loads(
        (R / "docs/regression_2x/logs/phase16_retrieval_payload.json")
        .read_text(encoding="utf-8"))["candidates"] if c.get("path")]
    ap = next(c["path"] for c in pool
              if c["sha256"].startswith("301ff850be9c"))
    ap = pathlib.Path(ap)
    with Image.open(ap) as im:
        W, H = im.size
        A = np.asarray(im.convert("L"), dtype=np.float64)
    print("素材 {} ({}x{})".format(ap.name[:44], W, H))
    for sid in ("S11p2", "S13p2"):
        g = np.asarray(Image.open(FR / "{}.png".format(sid)).convert("L")
                       .resize((48, 48)), dtype=np.float64)
        bk = CD.bank_score(g, str(ap), res=48)
        print("  {} bank best = corr {:.4f} scale {} x0 {} y0 {} w {} h {}".format(
            sid, bk["corr"], bk["scale"], bk["x0"], bk["y0"], bk["w"], bk["h"]))
        # 手工：遍历所有可能的 16:9 窗口尺寸（宽 40..100%）与 9x9 位置
        best = (-2, None)
        for frac in [x / 100 for x in range(40, 101, 2)]:
            w = int(W * frac)
            h = int(round(w * 9 / 16))
            if h > H:
                h = H
                w = int(round(h * 16 / 9))
            if w > W or h < 8 or w < 8:
                continue
            for j in range(9):
                y0 = int(round(j * (H - h) / 8))
                for i in range(9):
                    x0 = int(round(i * (W - w) / 8))
                    sub = A[y0:y0 + h, x0:x0 + w]
                    gg = np.asarray(Image.fromarray(sub.astype(np.uint8))
                                    .resize((48, 48)), dtype=np.float64)
                    c = CD._corr(g, gg)
                    if c > best[0]:
                        best = (c, {"frac": frac, "x0": x0, "y0": y0, "w": w, "h": h})
        print("     手工最优 = corr {:.4f} @ {}".format(best[0], best[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
