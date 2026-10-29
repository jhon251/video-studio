# -*- coding: utf-8 -*-
"""P32-2 判定用（精简、快速）：只看**决策相关**的候选度量，两门同语料。

候选：bank_v1（冻结）/ bank_v2（授权指定形态）/ ssim_v2（192 自适应网格, SSIM）
反门语料 = 55 条构造负例（P17 五景画面 × 池内其它 11 张 = 5×11）
          + P31 两景画面 × 非声明素材
优化：每个素材的子窗口库**预先载入并缩放一次**，供多帧复用。
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
WIN_SCALES = (1.0, 0.9, 0.8, 0.72, 0.65, 0.6, 0.5, 0.45, 0.35)
GRID_LIMIT = 170


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


def windows(W, H, scales):
    out = []
    for sc in scales:
        w = max(4, int(round(W * sc)))
        h = max(4, int(round(w * 9.0 / 16.0)))
        if h > H:
            h = H
            w = max(4, int(round(h * 16.0 / 9.0)))
        if w > W or w < 8 or h < 8:
            continue
        out.append((sc, w, h))
    return out


def grid_pos(span, extent, n):
    return [int(round(i * (span - extent) / max(n - 1, 1))) for i in range(n)]


def min_grid(span, extent, limit=GRID_LIMIT):
    if span <= extent:
        return 2
    return max(int(np.ceil((span - extent) / float(limit))) + 1, 2)


class Bank:
    """某素材在某分辨率下的子窗口库（预缩放一次）。"""

    def __init__(self, path, res, scales=WIN_SCALES):
        with Image.open(path) as im:
            self.A = np.asarray(im.convert("L"), dtype=np.float64)
        self.res = res
        self.H, self.W = self.A.shape[:2]
        n = 2
        self.wins = windows(self.W, self.H, scales)
        for _sc, w, h in self.wins:
            n = max(n, min_grid(self.W, w), min_grid(self.H, h))
        self.grid = n
        self.subs = []
        for sc, w, h in self.wins:
            for y0 in grid_pos(self.H, h, n):
                for x0 in grid_pos(self.W, w, n):
                    s = self.A[y0:y0 + h, x0:x0 + w]
                    g = np.asarray(Image.fromarray(s.astype("uint8")).convert("L")
                                   .resize((res, res)), dtype=np.float64)
                    self.subs.append(g)

    def best(self, frame, scorer=corr):
        return round(max(scorer(frame, s) for s in self.subs), 4)


def load(path, res):
    with Image.open(path) as im:
        return np.asarray(im.convert("L").resize((res, res)), dtype=np.float64)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    t0 = time.time()
    pool = [c for c in json.loads(POOL.read_text(encoding="utf-8"))["candidates"]
            if c.get("path")]

    positives = []
    for s in P17:
        ap = sorted((PACK / s).glob("asset.*"))[0]
        for fr in sorted((PACK / s).glob("frame_*.png")):
            positives.append((s, fr, ap))
    for sid in ("S11p2", "S13p2"):
        positives.append((sid, P31 / "{}.png".format(sid),
                          next(pathlib.Path(c["path"]) for c in pool
                               if c["sha256"].startswith("301ff850be9c"))))

    # 素材窗口库缓存（按 素材×res）
    cache = {}

    def bank_of(path, res):
        k = (str(path), res)
        if k not in cache:
            cache[k] = Bank(path, res)
        return cache[k]

    print("预建窗口库中…（池内 12 张 + 5 张 P17 素材）", flush=True)
    for c in pool:
        bank_of(c["path"], 192)
    for s in P17:
        bank_of(sorted((PACK / s).glob("asset.*"))[0], 192)
    print("窗口库就绪（{:.1f}s）".format(time.time() - t0), flush=True)

    def score(kind, fr, path):
        if kind == "bank_v1":
            b = bank_of(path, 48)
            return b.best(load(fr, 48))
        if kind == "bank_v2":
            b = bank_of(path, 192)
            return b.best(load(fr, 192))
        if kind == "ssim_v2":
            b = bank_of(path, 192)
            return b.best(load(fr, 192), ssim)
        raise ValueError(kind)

    kinds = ["bank_v1", "bank_v2", "ssim_v2"]
    print()
    print("=== 正门（要求 100%）===")
    pos = {k: [] for k in kinds}
    for sc, fr, ap in positives:
        line = "  {:<7} {:<13}".format(sc, fr.name)
        for k in kinds:
            v = score(k, fr, ap)
            pos[k].append(v)
            line += " {:>10.4f}".format(v)
        print(line)
    print("  {:<21}{}".format("", "".join(" {:>10}".format(k) for k in kinds)))
    print()
    for k in kinds:
        ok = len([v for v in pos[k] if v >= TH])
        print("  正门 {:<9} {}/{} {}".format(k, ok, len(positives),
                                             "✔" if ok == len(positives) else "✘"))

    print()
    print("=== 反门（要求 0 误通过）===")
    neg = {k: [] for k in kinds}
    pairs = 0
    for sc, fr, ap in positives:
        for c in pool:
            if pathlib.Path(c["path"]) == pathlib.Path(ap):
                continue
            pairs += 1
            for k in kinds:
                neg[k].append((sc, c["name"], score(k, fr, c["path"])))
    for k in kinds:
        fp = [x for x in neg[k] if x[2] >= TH]
        mx = max(x[2] for x in neg[k])
        print("  反门 {:<9} 误通过 {}/{} max={:.4f} {}".format(
            k, len(fp), pairs, mx, "✔" if not fp else "✘"))
        for x in sorted(fp, key=lambda z: -z[2])[:4]:
            print("        {:<7} vs {:<42} {:.4f}".format(x[0], str(x[1])[:42], x[2]))
    print()
    print("耗时 {:.1f}s".format(time.time() - t0))
    (L / "p32_2_decision_matrix.json").write_text(json.dumps({
        "schema": "p32-2-decision-matrix-v1", "threshold": TH,
        "positive": {k: {"pass": len([v for v in pos[k] if v >= TH]), "n": len(positives),
                         "vals": pos[k]} for k in kinds},
        "negative": {k: {"fp": len([x for x in neg[k] if x[2] >= TH]), "n": pairs,
                         "max": max(x[2] for x in neg[k]),
                         "false_passes": [{"scene": x[0], "other": x[1], "v": x[2]}
                                          for x in neg[k] if x[2] >= TH]}
                     for k in kinds},
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("-> logs/p32_2_decision_matrix.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
