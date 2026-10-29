# -*- coding: utf-8 -*-
"""P17-2 前置：原型化候选度量并�?*分离度实�?*（决定是否值得走双门）�?
启发式（三条都被 P17-1 证据支持）：
  · 素材在屏但被**裁切/缩放** �?画面 �?素材的某�?*子窗�?*�?  · 稀疏线稿在 48×48 �?*塌陷** �?重采样会进一步抹平；
  �?候选度�?= �?*同一分辨�?*下，�?       `corr_bank = max over 素材子窗�?宽高�?16:9, 尺度∈{1.0,0.75,0.55,0.4}) of corr(frame, crop)`
     �?`corr_full = corr(frame, 全图)` 的较大者；阈值仍 0.30�?
本脚本只�?*分离度实�?*（不落地、不改门禁）�?  正集 = 5 个已人工证实"在屏"的景（S02/S06/S07/S08/S13�?  负集 = 同为 16:9 画面�?*池内其它素材**（构造错配：画面 vs 别人的素材）
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
from video_studio.core import corr_diagnostics as CD                             # noqa: E402

PACK = R / "output" / "phase17_attr_pack"
SCALES = (1.00, 0.75, 0.55, 0.40, 0.30)
GRID = 3
RES = 48


def _g(arr, size=RES):
    from PIL import Image as I
    return np.asarray(I.fromarray(arr.astype("uint8")).convert("L").resize((size, size)),
                      dtype=np.float64)


def bank_corr(frame_path, asset_path, scales=SCALES, grid=GRID, res=RES):
    """画面 vs 素材子窗口库的最�?corr（宽高比 16:9）�?""
    with Image.open(frame_path) as im:
        fg = np.asarray(im.convert("L"), dtype=np.float64)
    with Image.open(asset_path) as im:
        A = np.asarray(im.convert("L"), dtype=np.float64)
    H, W = A.shape[:2]
    f48 = _g(fg, res)
    best = (-2.0, None)
    for sc in scales:
        # 子窗口：�?= W*sc，高 = �?(16/9)
        w = max(4, int(round(W * sc)))
        h = max(4, int(round(w * 9.0 / 16.0)))
        if h > H:
            h = H
            w = max(4, int(round(h * 16.0 / 9.0)))
        if w > W:
            continue
        xs = [int(round(i * (W - w) / max(grid - 1, 1))) for i in range(grid)]
        ys = [int(round(j * (H - h) / max(grid - 1, 1))) for j in range(grid)]
        for y0 in ys:
            for x0 in xs:
                c = CD._corr(f48, _g(A[y0:y0 + h, x0:x0 + w], res))
                if c > best[0]:
                    best = (round(c, 4), {"scale": sc, "x0": x0, "y0": y0, "w": w, "h": h})
    return {"corr_bank": best[0], "best_window": best[1]}


print("=" * 78)
print("正集：已人工证实『在屏』的 5 景（同一分辨�?48×48�?)
print("=" * 78)
pos_rows = []
for sid in ("S02", "S06", "S07", "S08", "S13"):
    fp = PACK / sid / "frame_50.png"
    ap = next((PACK / sid).glob("asset.*"))
    full = round(CD._corr(CD._gray(fp, RES), CD._gray(ap, RES)), 4)
    bk = bank_corr(fp, ap)
    v2 = max(full, bk["corr_bank"])
    pos_rows.append({"scene_id": sid, "corr_full": full, "corr_bank": bk["corr_bank"],
                     "corr_v2": round(v2, 4), "window": bk["best_window"],
                     "pass_original": full >= 0.30, "pass_v2": v2 >= 0.30})
    print("  {} full={:<8} bank={:<8} v2={:<8} 原判={} v2�?{}  win={}".format(
        sid, full, bk["corr_bank"], round(v2, 4), full >= 0.30, v2 >= 0.30,
        bk["best_window"]))

print()
print("=" * 78)
print("负集：画�?vs 池内**其它**素材（构造错配，同一 bank 度量�?)
print("=" * 78)
POOL = {}
SRC = R / "projects" / "p_96efdc03e1aa"
for d in (SRC / "media", SRC / "registered_materials", SRC / "acquired_materials"):
    if d.is_dir():
        for f in sorted(d.rglob("*")):
            if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
                POOL.setdefault(f.name, f)
neg_rows = []
for sid in ("S02", "S06", "S07", "S08", "S13"):
    fp = PACK / sid / "frame_50.png"
    ap = next((PACK / sid).glob("asset.*"))
    for n, p in POOL.items():
        if p.read_bytes() == ap.read_bytes():
            continue
        full = round(CD._corr(CD._gray(fp, RES), CD._gray(p, RES)), 4)
        bk = bank_corr(fp, p)
        v2 = max(full, bk["corr_bank"])
        neg_rows.append({"scene_id": sid, "other": n[:40], "corr_full": full,
                         "corr_bank": bk["corr_bank"], "corr_v2": round(v2, 4),
                         "pass_original": full >= 0.30, "pass_v2": v2 >= 0.30})
neg_max_o = max(r["corr_full"] for r in neg_rows)
neg_max_v = max(r["corr_v2"] for r in neg_rows)
print("  错配�?{} �?.format(len(neg_rows)))
print("  原度�?最�?corr（错配中最像的�?", neg_max_o, "| 通过阈值个�?",
      sum(1 for r in neg_rows if r["pass_original"]))
print("  v2度量 最�?corr（错配中最像的�?", neg_max_v, "| 通过阈值个�?",
      sum(1 for r in neg_rows if r["pass_v2"]))
print()
print("双重命中（既是别人最大、又过阈）的错配�?5:")
for r in sorted(neg_rows, key=lambda x: -x["corr_v2"])[:5]:
    print("   {} vs {} | full={} bank={} v2={}".format(
        r["scene_id"], r["other"], r["corr_full"], r["corr_bank"], r["corr_v2"]))

print()
print("=" * 78)
print("分离度小�?)
print("=" * 78)
print("  正集: 原度量通过 {}/5 | v2 通过 {}/5".format(
    sum(1 for r in pos_rows if r["pass_original"]),
    sum(1 for r in pos_rows if r["pass_v2"])))
print("  负集: 原度量误通过 {}/{} | v2 误通过 {}/{}".format(
    sum(1 for r in neg_rows if r["pass_original"]), len(neg_rows),
    sum(1 for r in neg_rows if r["pass_v2"]), len(neg_rows)))
out = R / "docs" / "regression_2x" / "logs" / "phase17_metric_prototype.json"
out.write_text(json.dumps({
    "schema": "phase17-metric-prototype-v1",
    "scales": list(SCALES), "grid": GRID, "res": RES, "threshold": 0.30,
    "positives": pos_rows, "negatives": neg_rows,
    "summary": {
        "pos_pass_original": sum(1 for r in pos_rows if r["pass_original"]),
        "pos_pass_v2": sum(1 for r in pos_rows if r["pass_v2"]),
        "neg_false_pass_original": sum(1 for r in neg_rows if r["pass_original"]),
        "neg_false_pass_v2": sum(1 for r in neg_rows if r["pass_v2"]),
        "neg_total": len(neg_rows)},
}, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
print("  ->", out.relative_to(R).as_posix())
