# -*- coding: utf-8 -*-
"""P17-2 度量 v2 裁定实验。

v2 定义（候选，阈值 0.30 不变）：
  `corr_effective = max( corr_res48(全图, 画面),
                         max over 尺度{1.0,0.8,0.6,0.45,0.35} x 5x5 网格
                             的 corr_res48(画面, 素材子窗口[16:9]) )`

判定分离度：
  · 正集 = 5 个已人工看图证实"在屏"的景（S02/S06/S07/S08/S13，P17-1 帧包）
  · 负集 = 画面 vs 池内其它素材（构造错配，16:9 同口径）
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

import numpy as np
from PIL import Image

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import corr_diagnostics as CD                            # noqa: E402

PACK = R / "output" / "phase17_attr_pack"
SCALES = (1.00, 0.80, 0.60, 0.45, 0.35)
GRID = 5
THRESH = 0.30


def _g(arr, size):
    return np.asarray(Image.fromarray(arr.astype("uint8")).convert("L").resize((size, size)),
                      dtype=np.float64)


def v2(frame_path, asset_path, res=48, scales=SCALES, grid=GRID):
    with Image.open(frame_path) as im:
        fg = np.asarray(im.convert("L"), dtype=np.float64)
    with Image.open(asset_path) as im:
        A = np.asarray(im.convert("L"), dtype=np.float64)
    H, W = A.shape[:2]
    f48 = _g(fg, res)
    full = round(CD._corr(f48, _g(A, res)), 4)
    best = (-2.0, None)
    for sc in scales:
        w = max(4, int(round(W * sc)))
        h = max(4, int(round(w * 9.0 / 16.0)))
        if h > H:
            h = H
            w = max(4, int(round(h * 16.0 / 9.0)))
        if w > W:
            continue
        for j in range(grid):
            y0 = int(round(j * (H - h) / max(grid - 1, 1)))
            for i in range(grid):
                x0 = int(round(i * (W - w) / max(grid - 1, 1)))
                c = CD._corr(f48, _g(A[y0:y0 + h, x0:x0 + w], res))
                if c > best[0]:
                    best = (round(c, 4), {"scale": sc, "x0": x0, "y0": y0, "w": w, "h": h})
    return {"corr_full": full, "corr_bank": best[0], "window": best[1],
            "corr_v2": round(max(full, best[0]), 4)}


SRC = R / "projects" / "p_96efdc03e1aa"
POOL = {}
for d in (SRC / "media", SRC / "registered_materials", SRC / "acquired_materials"):
    if d.is_dir():
        for f in sorted(d.rglob("*")):
            if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
                POOL.setdefault(hashlib.sha256(f.read_bytes()).hexdigest(), f)

print("=" * 78)
print("正集：5 景（人工证实『在屏』）")
print("=" * 78)
pos = []
for sid in ("S02", "S06", "S07", "S08", "S13"):
    fp = PACK / sid / "frame_50.png"
    ap = next((PACK / sid).glob("asset.*"))
    r = v2(fp, ap)
    r.update(scene_id=sid, pass_original=r["corr_full"] >= THRESH,
             pass_v2=r["corr_v2"] >= THRESH)
    pos.append(r)
    print("  {} full={:<8} bank={:<8} v2={:<8} 原={} v2={}".format(
        sid, r["corr_full"], r["corr_bank"], r["corr_v2"], r["pass_original"], r["pass_v2"]))

print()
print("=" * 78)
print("负集：画面 vs 池内其它素材（构造错配）")
print("=" * 78)
negB = []
for sid in ("S02", "S06", "S07", "S08", "S13"):
    fp = PACK / sid / "frame_50.png"
    ap = next((PACK / sid).glob("asset.*"))
    asha = hashlib.sha256(ap.read_bytes()).hexdigest()
    for sha, p in POOL.items():
        if sha == asha:
            continue
        r = v2(fp, p)
        r.update(scene_id=sid, other=p.name[:34], pass_original=r["corr_full"] >= THRESH,
                 pass_v2=r["corr_v2"] >= THRESH)
        negB.append(r)
print("  对数:", len(negB))
print("  原度量误通过:", sum(1 for r in negB if r["pass_original"]),
      "| 最大 corr:", max(r["corr_full"] for r in negB))
print("  v2   误通过:", sum(1 for r in negB if r["pass_v2"]),
      "| 最大 corr:", max(r["corr_v2"] for r in negB))
print("  v2 误通过明细:")
for r in sorted(negB, key=lambda x: -x["corr_v2"])[:6]:
    if r["pass_v2"]:
        print("    {} vs {} v2={} full={}".format(r["scene_id"], r["other"],
                                                  r["corr_v2"], r["corr_full"]))
ps = sum(1 for r in pos if r["pass_v2"])
po = sum(1 for r in pos if r["pass_original"])
fo = sum(1 for r in negB if r["pass_original"])
fv = sum(1 for r in negB if r["pass_v2"])
print()
print("=" * 78)
print("分离度小结（阈值 0.30 不变）")
print("=" * 78)
print("  正集通过: 原 {} / 5  |  v2 {} / 5".format(po, ps))
print("  负集误通过: 原 {} / {}  |  v2 {} / {}".format(fo, len(negB), fv, len(negB)))
print("  双门判定: 正门(需 5/5) {} | 反门(需 0 误通过) {} => 采纳 {}".format(
    "过" if ps == 5 else "不过", "过" if fv == 0 else "不过",
    "是" if (ps == 5 and fv == 0) else "否"))
out = R / "docs" / "regression_2x" / "logs" / "phase17_metric_v2_experiment.json"
out.write_text(json.dumps({
    "schema": "phase17-metric-v2-experiment-v1",
    "definition": {"corr_effective":
                   "max(corr_full_res48, max over scales x grid of corr(frame, asset_subwindow 16:9))",
                   "scales": list(SCALES), "grid": GRID, "res": 48, "threshold": THRESH},
    "dual_gate": {"positive_gate_required": "5/5 PASS", "negative_gate_required": "0 false pass",
                  "positive_actual": ps, "negative_false_pass": fv,
                  "adopted": bool(ps == 5 and fv == 0)},
    "positives": pos, "negatives_constructed": negB,
    "summary": {"pos_pass_original": po, "pos_pass_v2": ps,
                "neg_false_pass_original": fo, "neg_false_pass_v2": fv,
                "neg_total": len(negB)},
}, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
print("  ->", out.relative_to(R).as_posix())
