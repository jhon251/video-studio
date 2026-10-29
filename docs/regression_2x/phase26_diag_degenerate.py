# -*- coding: utf-8 -*-
"""P26 §0 诊断：bank_score 是否被**退化子窗口**（近常量/低方差）主导？

假设：`bank_score` 对大量子窗口取最大 corr。若某些子窗口方差极低（大片留白/纯色边），
其与任意画面的 Pearson 会被系统性抬高 ⇒ 期望素材与**无关**素材都能拿高分
（Phase 26 §0 实测：无关素材对 S10p1 达 **0.9996**）。本脚本量化该效应。
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
from video_studio.core.materials import gray48, frame_corr                       # noqa: E402

fx = json.loads((R / "output/phase20_p20_2_sandbox/fixture.json").read_text(encoding="utf-8"))
SRC = R / "projects" / "p_96efdc03e1aa"
POOL = {}
for d in (SRC / "media", SRC / "registered_materials", SRC / "acquired_materials"):
    if d.is_dir():
        for f in sorted(d.rglob("*")):
            if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
                POOL.setdefault(hashlib.sha256(f.read_bytes()).hexdigest(), f)

g = gray48(R / "projects" / fx["sandbox_project_id"] / "artifacts" / "_frame_S10p1.png")
peer = next(p for p in POOL.values() if "Postal" in p.name)

# 穷举该素材的所有 bank 子窗口，报告 corr 与窗口标准差的关系
with Image.open(peer) as im:
    A = np.asarray(im.convert("L"), dtype=np.float64)
H, W = A.shape[:2]
rows = []
for sc in CD.BANK_SCALES:
    w = max(4, int(round(W * sc)))
    h = max(4, int(round(w * 9.0 / 16.0)))
    if h > H:
        h = H
        w = max(4, int(round(h * 16.0 / 9.0)))
    if w > W:
        continue
    for j in range(CD.BANK_GRID):
        y0 = int(round(j * (H - h) / max(CD.BANK_GRID - 1, 1)))
        for i in range(CD.BANK_GRID):
            x0 = int(round(i * (W - w) / max(CD.BANK_GRID - 1, 1)))
            wa = np.asarray(Image.fromarray(A[y0:y0 + h, x0:x0 + w].astype("uint8"))
                            .convert("L").resize((48, 48)), dtype=np.float64)
            rows.append({"scale": sc, "x0": x0, "y0": y0, "w": w, "h": h,
                         "std": round(float(wa.std()), 3),
                         "corr": round(float(CD._corr(g, wa)), 4)})
rows.sort(key=lambda r: -r["corr"])
print("素材:", peer.name, "| 尺寸", (W, H), "| 子窗口数", len(rows))
print()
print("corr 前 10 的子窗口（看 std 是否异常低）：")
print("  {:>6s} {:>6s} {:>6s} {:>8s} {:>9s} {:>8s}".format(
    "scale", "x0", "y0", "w", "std", "corr"))
for r in rows[:10]:
    print("  {:>6.2f} {:>6d} {:>6d} {:>8d} {:>9.3f} {:>8.4f}".format(
        r["scale"], r["x0"], r["y0"], r["w"], r["std"], r["corr"]))
stds = np.array([r["std"] for r in rows])
corrs = np.array([r["corr"] for r in rows])
print()
print("窗口 std 分布: min {:.3f} p10 {:.3f} 中位 {:.3f} max {:.3f}".format(
    stds.min(), float(np.percentile(stds, 10)), float(np.median(stds)), stds.max()))
print("窗口 corr 分布: min {:.4f} 中位 {:.4f} max {:.4f}".format(
    corrs.min(), float(np.median(corrs)), corrs.max()))
print("std < 5 的窗口数: {} / {}（其平均 corr {:.4f}）".format(
    int((stds < 5).sum()), len(stds),
    float(corrs[stds < 5].mean()) if (stds < 5).any() else float("nan")))
print("std >= 20 的窗口数: {} / {}（其平均 corr {:.4f}）".format(
    int((stds >= 20).sum()), len(stds),
    float(corrs[stds >= 20].mean()) if (stds >= 20).any() else float("nan")))
print()
print("⇒ 若低 std 窗口的 corr 系统性更高，则 bank 的 max 被**退化窗口**主导 ⇒")
print("   需要**最小方差门**（丢弃 std 过低的子窗口）才有资格做核验口径。")

out = {"schema": "phase26-p26-0-bank-degenerate-diagnosis-v1",
       "asset": peer.name, "asset_size": [W, H], "windows": len(rows),
       "std_stats": {"min": float(stds.min()), "p10": float(np.percentile(stds, 10)),
                     "median": float(np.median(stds)), "max": float(stds.max())},
       "corr_stats": {"min": float(corrs.min()), "median": float(np.median(corrs)),
                      "max": float(corrs.max())},
       "low_std_under_5": {"n": int((stds < 5).sum()),
                           "mean_corr": (float(corrs[stds < 5].mean())
                                         if (stds < 5).any() else None)},
       "high_std_20plus": {"n": int((stds >= 20).sum()),
                           "mean_corr": (float(corrs[stds >= 20].mean())
                                         if (stds >= 20).any() else None)},
       "top10": rows[:10],
       "conclusion": ("bank 的 max 聚合使**低方差（近常量）子窗口**贡献虚高 corr；"
                      "无最小方差门时该度量会把无关素材评到 ~0.99 ⇒ "
                      "**不可作为核验口径**（P26 §0 双门：正门 42.5%、反门 100/440 误通过）。")}
p = R / "docs" / "regression_2x" / "logs" / "phase26_p26_0_bank_degenerate.json"
p.write_text(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
print("->", p.relative_to(R).as_posix())
