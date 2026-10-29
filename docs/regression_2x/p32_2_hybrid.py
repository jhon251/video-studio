# -*- coding: utf-8 -*-
"""P32-2：检验 **兼容式修复** bank v1.5 = `max(v1@48, v2@192自适应)` 的正门表现。

动机（诊断结论）：v2 单独使用会在**稀疏线稿**上回落（S06 0.34 / S07 0.25），
但 v2 修好了 P31 的 S11p2/S13p2（0.32/0.33）。若取二者最大：
  · 正门：只要任一版本达标即达标（v1 已 17/17）⇒ 不会回归；
  · 反门：需实测是否引入新误通过。
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
from PIL import Image

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
PACK = R / "output" / "phase17_attr_pack"
P31 = R / "output" / "p31_probe" / "frames"
POOL = L / "phase16_retrieval_payload.json"
TH = 0.30
P17 = ("S02", "S06", "S07", "S08", "S13")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.path.insert(0, str(R / "src"))
    from video_studio.core import corr_diagnostics as CD

    pool = [c for c in json.loads(POOL.read_text(encoding="utf-8"))["candidates"]
            if c.get("path")]

    def load(p, res):
        with Image.open(p) as im:
            return np.asarray(im.convert("L").resize((res, res)), dtype=np.float64)

    positives = []
    for s in P17:
        ap = sorted((PACK / s).glob("asset.*"))[0]
        for fr in sorted((PACK / s).glob("frame_*.png")):
            positives.append((s, fr, ap))
    for sid in ("S11p2", "S13p2"):
        positives.append((sid, P31 / "{}.png".format(sid),
                          next(pathlib.Path(c["path"]) for c in pool
                               if c["sha256"].startswith("301ff850be9c"))))

    print("=== 正门：v1 / v2 / v1.5=max(v1,v2) ===")
    print("{:<8} {:<13} {:>9} {:>9} {:>11}".format("scene", "frame", "v1", "v2", "v1.5"))
    rows = []
    for sc, fr, ap in positives:
        v1 = CD.bank_score(load(fr, 48), str(ap), res=48)["corr"]
        v2 = CD.bank_score_v2(load(fr, CD.BANK_RES_V2), str(ap))["corr"]
        v15 = round(max(v1, v2), 4)
        rows.append({"scene": sc, "frame": fr.name, "v1": v1, "v2": v2, "v1_5": v15})
        print("{:<8} {:<13} {:>9.4f} {:>9.4f} {:>11.4f}".format(sc, fr.name, v1, v2, v15))
    print()
    for k, lab in (("v1", "v1(冻结)"), ("v2", "v2(授权形态)"), ("v1_5", "v1.5=max(v1,v2)")):
        ok = len([r for r in rows if r[k] >= TH])
        print("  正门 {:<18} {}/{} {}".format(lab, ok, len(rows),
                                              "✔" if ok == len(rows) else "✘"))
    (L / "p32_2_hybrid_positive.json").write_text(json.dumps(
        {"schema": "p32-2-hybrid-positive-v1", "threshold": TH, "rows": rows},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print("-> logs/p32_2_hybrid_positive.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
