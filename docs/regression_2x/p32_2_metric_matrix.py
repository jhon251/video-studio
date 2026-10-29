# -*- coding: utf-8 -*-
"""P32-2 候选度量在**正门+反门**上的同语料对照（决定是否可采纳 v2）。

候选：
  bank_v1   48, 5×5                       （冻结基线）
  bank_v2   192, 自适应网格 ≤170px         （授权书指定形态）
  bank_v3   多分辨率 48/96/192 自适应网格，取最大（**尝试修复稀疏线稿回落**）
  ssim_v2   192, 自适应网格, SSIM
  edge_v2   192, 自适应网格, 边缘图 corr
  ssim_v3   多分辨率 48/96/192, SSIM, 取最大
只说数字，不裁定；裁定由 p32_2_bank_v2_gate.py 的双门给出。
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

import numpy as np
from PIL import Image

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
PACK = R / "output" / "phase17_attr_pack"
P31 = R / "output" / "p31_probe" / "frames"
POOL = L / "phase16_retrieval_payload.json"
TH = 0.30
P17 = ("S02", "S06", "S07", "S08", "S13")
RES_LADDER = (48, 96, 192)


def load(p, res):
    with Image.open(p) as im:
        return np.asarray(im.convert("L").resize((res, res)), dtype=np.float64)


def corr(a, b):
    a = a - a.mean()
    b = b - b.mean()
    d = float(np.sqrt((a ** 2).sum()) * np.sqrt((b ** 2).sum()))
    return float((a * b).sum() / d) if d else 0.0


def ssim(a, b):
    C1 = (0.01 * 255) ** 2
    C2 = (0.03 * 255) ** 2
    ma, mb = a.mean(), b.mean()
    va, vb = a.var(), b.var()
    cov = ((a - ma) * (b - mb)).mean()
    return float(((2 * ma * mb + C1) * (2 * cov + C2)) /
                 ((ma ** 2 + mb ** 2 + C1) * (va + vb + C2)))


def edge(a):
    gx = np.zeros_like(a)
    gy = np.zeros_like(a)
    gx[:, 1:-1] = a[:, 2:] - a[:, :-2]
    gy[1:-1, :] = a[2:, :] - a[:-2, :]
    return np.sqrt(gx ** 2 + gy ** 2)


def bank_max(CD, frame_path, asset_path, scorer, scales, grid_map, ladder):
    """在子窗口库 × 分辨率阶梯上取 scorer 最大值。"""
    with Image.open(asset_path) as im:
        A0 = np.asarray(im.convert("L"), dtype=np.float64)
    H, W = A0.shape[:2]
    grid = grid_map(asset_path)
    frames = {res: load(frame_path, res) for res in ladder}
    best = -2.0
    for sc, w, h in CD._windows_16x9(W, H, scales):
        for y0 in CD._grid_positions(H, h, grid):
            for x0 in CD._grid_positions(W, w, grid):
                sub0 = A0[y0:y0 + h, x0:x0 + w]
                for res in ladder:
                    sub = np.asarray(Image.fromarray(sub0.astype("uint8")).convert("L")
                                     .resize((res, res)), dtype=np.float64)
                    c = scorer(frames[res], sub)
                    if c > best:
                        best = c
    return round(best, 4)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.path.insert(0, str(R / "src"))
    from video_studio.core import corr_diagnostics as CD

    pool = [c for c in json.loads(POOL.read_text(encoding="utf-8"))["candidates"]
            if c.get("path")]
    gmap = CD._Grids.of
    V2S = CD.BANK_SCALES_V2
    gm = lambda p: CD._Grids.of(p)

    positives = []
    for s in P17:
        ap = sorted((PACK / s).glob("asset.*"))[0]
        for fr in sorted((PACK / s).glob("frame_*.png")):
            positives.append((s, fr, ap))
    for sid in ("S11p2", "S13p2"):
        positives.append((sid, P31 / "{}.png".format(sid),
                          next(pathlib.Path(c["path"]) for c in pool
                               if c["sha256"].startswith("301ff850be9c"))))

    # 反门语料：正门帧 × 池内其它素材
    negatives = []
    for sc, fr, ap in positives:
        own = ap
        for c in pool:
            if pathlib.Path(c["path"]) == pathlib.Path(own):
                continue
            negatives.append((sc, fr, c))

    def metric(name, frame_path, asset_path):
        if name == "bank_v1":
            return CD.bank_score(load(frame_path, 48), str(asset_path), res=48)["corr"]
        if name == "bank_v2":
            return CD.bank_score_v2(load(frame_path, 192), str(asset_path))["corr"]
        if name == "bank_v3":
            return bank_max(CD, frame_path, asset_path, corr, V2S, gmap, RES_LADDER)
        if name == "ssim_v2":
            return bank_max(CD, frame_path, asset_path, ssim, V2S, gmap, (192,))
        if name == "ssim_v3":
            return bank_max(CD, frame_path, asset_path, ssim, V2S, gmap, RES_LADDER)
        if name == "edge_v2":
            return bank_max(CD, frame_path, asset_path,
                            lambda a, b: corr(edge(a), edge(b)), V2S, gmap, (192,))
        raise ValueError(name)

    names = ["bank_v1", "bank_v2", "bank_v3", "ssim_v2", "ssim_v3", "edge_v2"]
    t0 = time.time()
    print("正门 {} 条 | 反门 {} 条 | 阈值 {}".format(len(positives), len(negatives), TH))
    print()
    print("=== 正门（要求 100%）===")
    pos_res = {n: [] for n in names}
    for sc, fr, ap in positives:
        line = "  {:<7} {:<13}".format(sc, fr.name)
        for n in names:
            v = metric(n, fr, ap)
            pos_res[n].append({"scene": sc, "frame": fr.name, "v": v})
            line += " {:>8.4f}".format(v)
        print(line)
    print("  {:<21}{}".format("", "".join(" {:>8}".format(n[:8]) for n in names)))
    print()
    for n in names:
        ok = len([r for r in pos_res[n] if r["v"] >= TH])
        print("  正门 {:<9} {}/{} {}".format(n, ok, len(positives),
                                             "✔" if ok == len(positives) else "✘"))
    print()
    print("=== 反门（要求 0 误通过）===")
    neg_res = {n: [] for n in names}
    for sc, fr, c in negatives:
        for n in names:
            neg_res[n].append(metric(n, fr, c["path"]))
    for n in names:
        fp = [v for v in neg_res[n] if v >= TH]
        print("  反门 {:<9} 误通过 {}/{}  max={:.4f} {}".format(
            n, len(fp), len(negatives), max(neg_res[n]), "✔" if not fp else "✘"))
    print()
    print("耗时 {:.1f}s".format(time.time() - t0))
    (L / "p32_2_metric_matrix.json").write_text(json.dumps({
        "schema": "p32-2-metric-matrix-v1", "threshold": TH,
        "positive": {n: {"pass": len([r for r in pos_res[n] if r["v"] >= TH]),
                         "n": len(positives), "rows": pos_res[n]} for n in names},
        "negative": {n: {"fp": len([v for v in neg_res[n] if v >= TH]),
                         "n": len(negatives), "max": max(neg_res[n])} for n in names},
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("-> logs/p32_2_metric_matrix.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
