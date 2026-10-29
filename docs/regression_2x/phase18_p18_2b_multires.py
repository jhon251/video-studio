# -*- coding: utf-8 -*-
"""P18-2 续：多分辨率 bank 混合变体实验（寻找双门全过的组合）。

关键洞察（来自上一轮）：
  · bank@192 把正集提到 3/5 且反门 0 误通过（严格改善），但丢掉 S07/S13；
  · 边缘图@192 正门 5/5 但反门 35/55（稀疏线稿"到处都是边" ⇒ 无区分力）⇒ **弃用边缘口径**；
  · bank@48 对 S06/S13 有效、bank@192 对 S02/S06/S08 有效 ⇒ 取**多分辨率 bank 的最大值**
    应严格不差于任一单分辨率。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

import numpy as np
from PIL import Image

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

_cache: dict = {}


def gray_np(path, res):
    k = ("g", str(path), res)
    if k not in _cache:
        with Image.open(path) as im:
            _cache[k] = np.asarray(im.convert("L").resize((res, res)), dtype=np.float64)
    return _cache[k]


def asset_np(path):
    k = ("a", str(path))
    if k not in _cache:
        with Image.open(path) as im:
            _cache[k] = np.asarray(im.convert("L"), dtype=np.float64)
    return _cache[k]


def bank_res(frame_path, asset_path, res, scales=CD.BANK_SCALES, grid=CD.BANK_GRID):
    fg = gray_np(frame_path, res)
    A = asset_np(asset_path)
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
                wa = np.asarray(
                    Image.fromarray(A[y0:y0 + h, x0:x0 + w].astype("uint8"))
                    .convert("L").resize((res, res)), dtype=np.float64)
                c = CD._corr(fg, wa)
                if c > best:
                    best = c
    return round(best, 4)


def base48(f, a):
    return round(CD._corr(gray_np(f, 48), gray_np(a, 48)), 4)


VARIANTS = {
    "m1_max(bank48,bank192)": lambda f, a: max(bank_res(f, a, 48), bank_res(f, a, 192)),
    "m2_max(bank48,bank96,bank192)": lambda f, a: max(bank_res(f, a, 48), bank_res(f, a, 96),
                                                      bank_res(f, a, 192)),
    "m3_max(base48,bank48,bank192)": lambda f, a: max(base48(f, a), bank_res(f, a, 48),
                                                      bank_res(f, a, 192)),
    "m4_bank192_only": lambda f, a: bank_res(f, a, 192),
    "m5_max(bank48,bank192,bank384)": lambda f, a: max(bank_res(f, a, 48), bank_res(f, a, 192),
                                                       bank_res(f, a, 384)),
    "m6_max(base48,bank48,bank96,bank192)": lambda f, a: max(base48(f, a), bank_res(f, a, 48),
                                                             bank_res(f, a, 96),
                                                             bank_res(f, a, 192)),
}

print("=" * 100)
print("P18-2 多分辨率 bank 混合：正门（5 景全 PASS）x 反门（55 负例 0 误通过），阈值 0.30")
print("=" * 100)
results = {}
for name, fn in VARIANTS.items():
    pos = {sid: fn(PACK / sid / "frame_50.png", next((PACK / sid).glob("asset.*")))
           for sid in SCENES}
    pos_pass = sum(1 for v in pos.values() if v >= THRESH)
    neg_bad, neg_n = [], 0
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
    ok = (pos_pass == 5 and not neg_bad)
    results[name] = {"pos": pos, "pos_pass": pos_pass, "neg_total": neg_n,
                     "neg_false_pass": len(neg_bad), "neg_false_list": neg_bad,
                     "dual_gate_pass": ok}
    print("  {:38s} 正门 {:>2}/5  反门 {:>2}/{}  {}".format(
        name, pos_pass, len(neg_bad), neg_n, "⇒ 双门全过 ✔" if ok else "⇒ 不过"))
    print("      {}".format(" ".join("{}={}".format(k, v) for k, v in pos.items())))
    if neg_bad:
        print("      误通过: {}".format("; ".join(
            "{} vs {}={}".format(b["scene_id"], b["other"], b["corr"])
            for b in sorted(neg_bad, key=lambda x: -x["corr"])[:4])))

adopted = [k for k, v in results.items() if v["dual_gate_pass"]]
out = {
    "schema": "phase18-p18-2b-multires-bank-v1",
    "threshold": 0.30,
    "dual_gate_frozen": {"positive_required": "5/5 PASS", "negative_required": "0 false pass"},
    "variants": results,
    "adopted": adopted,
    "edge_metric_rejected": {
        "reason": ("边缘图@192 正门 5/5 但反门 35/55 误通过：稀疏线稿在边缘图上"
                   "普遍高度相似（'到处都是边'）⇒ 边缘口径在本语料上**无区分力**，弃用。"),
        "evidence": "logs/phase18_p18_2_v3_variants.json",
    },
}
(L / "phase18_p18_2b_multires_bank.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
print()
print("可采纳变体:", adopted or "无（双门未全过）")
print("->", (L / "phase18_p18_2b_multires_bank.json").relative_to(R).as_posix())
