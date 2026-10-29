# -*- coding: utf-8 -*-
"""P18-2 corr v3 变体实验：192px 重采样 × 子窗口 bank × 边缘图口径。

对每个候选度量同时在**正集**（P17 目视在屏 5 景，含 S07 边缘案例）与
**负集**（55 条构造错例：画面 vs 池内其它素材）上评估，报告
「正门（需 5/5 PASS，阈值 0.30）」与「反门（需 0 误通过）」。
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
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import corr_diagnostics as CD                            # noqa: E402

PACK = R / "output" / "phase17_attr_pack"
SCENES = ("S02", "S06", "S07", "S08", "S13")
THRESH = 0.30
SRC = R / "projects" / "p_96efdc03e1aa"
POOL = {}
for d in (SRC / "media", SRC / "registered_materials", SRC / "acquired_materials"):
    if d.is_dir():
        for f in sorted(d.rglob("*")):
            if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
                POOL.setdefault(hashlib.sha256(f.read_bytes()).hexdigest(), f)


def gray_arr(path, res):
    with Image.open(path) as im:
        return np.asarray(im.convert("L").resize((res, res)), dtype=np.float64)


def edge_arr(path, res, radius=1.0):
    """Sobel 幅值图（PIL FIND_EDGES 后归一化）。"""
    with Image.open(path) as im:
        g = im.convert("L").resize((res, res)).filter(ImageFilter.FIND_EDGES)
    a = np.asarray(g, dtype=np.float64)
    return a


def bank_gray(frame_path, asset_path, res, scales=CD.BANK_SCALES, grid=CD.BANK_GRID):
    fg = gray_arr(frame_path, res)
    with Image.open(asset_path) as im:
        A = np.asarray(im.convert("L"), dtype=np.float64)
    H, W = A.shape[:2]
    best = -2.0
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
                win = Image.fromarray(A[y0:y0 + h, x0:x0 + w].astype("uint8"))
                wa = np.asarray(win.convert("L").resize((res, res)), dtype=np.float64)
                c = CD._corr(fg, wa)
                if c > best:
                    best = c
    return round(best, 4)


def bank_edge(frame_path, asset_path, res, scales=CD.BANK_SCALES, grid=CD.BANK_GRID):
    fg = edge_arr(frame_path, res)
    with Image.open(asset_path) as im:
        A = np.asarray(im.convert("L"), dtype=np.float64)
    H, W = A.shape[:2]
    best = -2.0
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
                win = Image.fromarray(A[y0:y0 + h, x0:x0 + w].astype("uint8"))
                wa = np.asarray(win.convert("L").resize((res, res))
                                .filter(ImageFilter.FIND_EDGES), dtype=np.float64)
                c = CD._corr(fg, wa)
                if c > best:
                    best = c
    return round(best, 4)


VARIANTS = {
    "v2_base48": lambda f, a: round(CD._corr(gray_arr(f, 48), gray_arr(a, 48)), 4),
    "v3_bank192": lambda f, a: bank_gray(f, a, 192),
    "v3_edge192": lambda f, a: bank_edge(f, a, 192),
    "v3_max_bank192_base48": lambda f, a: max(bank_gray(f, a, 192),
                                              round(CD._corr(gray_arr(f, 48),
                                                             gray_arr(a, 48)), 4)),
    "v3_max_edge192_bank192": lambda f, a: max(bank_edge(f, a, 192), bank_gray(f, a, 192)),
    "v3_max_edge192_base48": lambda f, a: max(bank_edge(f, a, 192),
                                              round(CD._corr(gray_arr(f, 48),
                                                             gray_arr(a, 48)), 4)),
}

print("=" * 100)
print("P18-2 v3 变体：正门（5 景须全 PASS）x 反门（55 负例须 0 误通过），阈值 0.30")
print("=" * 100)
results = {}
for name, fn in VARIANTS.items():
    pos = {}
    for sid in SCENES:
        fp = PACK / sid / "frame_50.png"
        ap = next((PACK / sid).glob("asset.*"))
        pos[sid] = fn(fp, ap)
    pos_pass = sum(1 for v in pos.values() if v >= THRESH)
    neg_bad = []
    neg_n = 0
    for sid in SCENES:
        fp = PACK / sid / "frame_50.png"
        ap = next((PACK / sid).glob("asset.*"))
        asha = hashlib.sha256(ap.read_bytes()).hexdigest()
        for sha, p in POOL.items():
            if sha == asha:
                continue
            neg_n += 1
            v = fn(fp, p)
            if v >= THRESH:
                neg_bad.append({"scene_id": sid, "other": p.name[:38], "corr": v})
    results[name] = {"pos": pos, "pos_pass": pos_pass, "neg_total": neg_n,
                     "neg_false_pass": len(neg_bad), "neg_false_list": neg_bad}
    print("  {:26s} 正门 {:>2}/5  反门误通过 {:>2}/{}  {}".format(
        name, pos_pass, len(neg_bad), neg_n,
        "⇒ 双门全过 ✔" if (pos_pass == 5 and not neg_bad) else "⇒ 不过"))
    print("      正集明细: {}".format(
        " ".join("{}={}".format(k, v) for k, v in pos.items())))
    if neg_bad:
        print("      误通过: {}".format(
            "; ".join("{} vs {}={}".format(b["scene_id"], b["other"], b["corr"])
                      for b in sorted(neg_bad, key=lambda x: -x["corr"])[:4])))

out = {
    "schema": "phase18-p18-2-v3-variants-v1",
    "threshold": 0.30,
    "dual_gate_frozen": {"positive_required": "5/5 PASS",
                         "negative_required": "0 false pass"},
    "variants": results,
    "adopted": [k for k, v in results.items()
                if v["pos_pass"] == 5 and v["neg_false_pass"] == 0],
    "note": ("正集为 P17 目视在屏 5 景（含 S07 边缘案例 0.2766）；"
             "负集为 55 条构造错配（画面 vs 池内其它素材）。"),
}
(L / "phase18_p18_2_v3_variants.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
print()
print("可采纳变体:", out["adopted"] or "无（双门未全过）")
print("->", (L / "phase18_p18_2_v3_variants.json").relative_to(R).as_posix())
