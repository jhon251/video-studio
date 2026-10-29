# -*- coding: utf-8 -*-
"""P32-2 诊断：为何 v2（res=192）在稀疏线稿（S06/S07）上**回落**？

对各候选度量在两套语料上做同语料对照（正门 P17 五景帧 + P31 两景帧；反门同前）：
  M0 corr_full(48)                      —— 冻结旧口径
  M1 bank v1 (48, 5×5)
  M2 bank v2 (192, 自适应网格)
  M3 bank (192, 自适应网格) + **边缘图**（Sobel 前先高斯）后再 corr
  M4 bank (192, 自适应网格) + **SSIM**
只诊断、不改门禁。只读（除本报告）。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

import numpy as np
from PIL import Image, ImageFilter

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
PACK = R / "output" / "phase17_attr_pack"
P31 = R / "output" / "p31_probe" / "frames"
POOL = L / "phase16_retrieval_payload.json"
TH = 0.30
P17 = ("S02", "S06", "S07", "S08", "S13")


def load(p, res):
    with Image.open(p) as im:
        return np.asarray(im.convert("L").resize((res, res)), dtype=np.float64)


def corr(a, b):
    a = a - a.mean()
    b = b - b.mean()
    d = float(np.sqrt((a ** 2).sum()) * np.sqrt((b ** 2).sum()))
    return float((a * b).sum() / d) if d else 0.0


def edge(a):
    """Sobel 幅度（图像域），再标准化 —— 稀疏线稿的"结构"比灰度更稳。"""
    gx = np.zeros_like(a)
    gy = np.zeros_like(a)
    gx[:, 1:-1] = a[:, 2:] - a[:, :-2]
    gy[1:-1, :] = a[2:, :] - a[:-2, :]
    m = np.sqrt(gx ** 2 + gy ** 2)
    return m


def ssim(a, b):
    """全局 SSIM（C1/C2 标准常数，数据范围 255）。"""
    C1 = (0.01 * 255) ** 2
    C2 = (0.03 * 255) ** 2
    ma, mb = a.mean(), b.mean()
    va, vb = a.var(), b.var()
    cov = ((a - ma) * (b - mb)).mean()
    return float(((2 * ma * mb + C1) * (2 * cov + C2)) /
                 ((ma ** 2 + mb ** 2 + C1) * (va + vb + C2)))


def bank_generic(frame, asset_path, res, scorer):
    """在 v2 的子窗口库上取 scorer 的最大值。"""
    from video_studio.core import corr_diagnostics as CD
    with Image.open(asset_path) as im:
        A = np.asarray(im.convert("L"), dtype=np.float64)
    H, W = A.shape[:2]
    grid = CD._Grids.of(asset_path)
    best = -2.0
    for sc, w, h in CD._windows_16x9(W, H, CD.BANK_SCALES_V2):
        for y0 in CD._grid_positions(H, h, grid):
            for x0 in CD._grid_positions(W, w, grid):
                sub = A[y0:y0 + h, x0:x0 + w]
                sub = np.asarray(Image.fromarray(sub.astype("uint8")).convert("L")
                                 .resize((res, res)), dtype=np.float64)
                c = scorer(frame, sub)
                if c > best:
                    best = c
    return round(best, 4)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.path.insert(0, str(R / "src"))
    from video_studio.core import corr_diagnostics as CD

    pool = [c for c in json.loads(POOL.read_text(encoding="utf-8"))["candidates"]
            if c.get("path")]
    # 正门语料
    positives = []
    for s in P17:
        ap = sorted((PACK / s).glob("asset.*"))[0]
        for fr in sorted((PACK / s).glob("frame_*.png")):
            positives.append((s, fr, ap))
    for sid in ("S11p2", "S13p2"):
        positives.append((sid, P31 / "{}.png".format(sid),
                          next(pathlib.Path(c["path"]) for c in pool
                               if c["sha256"].startswith("301ff850be9c"))))

    print("=== 正门：各度量对照（阈值 0.30）===")
    print("{:<8} {:<7} {:>9} {:>9} {:>9} {:>9} {:>9}".format(
        "scene", "frame", "full48", "bank_v1", "bank_v2", "edge192", "ssim192"))
    rows = []
    for sc, fr, ap in positives:
        g48 = load(fr, 48)
        g192 = load(fr, 192)
        full48 = corr(g48, load(ap, 48))
        b1 = CD.bank_score(g48, str(ap), res=48)["corr"]
        b2 = CD.bank_score_v2(load(fr, CD.BANK_RES_V2), str(ap))["corr"]
        e = bank_generic(edge(g192), ap, 192, lambda a, b: corr(edge(a), edge(b)))
        s = bank_generic(g192, ap, 192, ssim)
        rows.append({"scene": sc, "frame": fr.name, "full48": round(full48, 4),
                     "bank_v1": b1, "bank_v2": b2, "edge192": e, "ssim192": s})
        print("{:<8} {:<7} {:>9.4f} {:>9.4f} {:>9.4f} {:>9.4f} {:>9.4f}".format(
            sc, fr.name, full48, b1, b2, e, s))
    print()
    for m in ("full48", "bank_v1", "bank_v2", "edge192", "ssim192"):
        ok = len([r for r in rows if r[m] >= TH])
        print("  {:<9} 正门 {}/{} {}".format(m, ok, len(rows),
                                             "✔" if ok == len(rows) else "✘"))
    (L / "p32_2_metric_diagnosis.json").write_text(json.dumps(
        {"schema": "p32-2-metric-diagnosis-v1", "threshold": TH, "rows": rows},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print()
    print("-> logs/p32_2_metric_diagnosis.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
