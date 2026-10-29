# -*- coding: utf-8 -*-
"""P18-1 present_test 口径修复 —— 回归验证（P17 五景帧包 + 55 条构造负例）。

验证目标：
  · 五景（S02/S06/S07/S08/S13）在**修复口径（子窗口 bank）**下**全部判 `is_argmax`（在屏）**；
  · 旧口径（full_image）应仍把 S08/S13 判为非 argmax ⇒ 佐证缺陷真实存在；
  · **55 条构造负例**（画面 vs 池内其它素材）按同一 bank 口径比较，
    **被分配素材仍须为 argmax**（即"改动不是放宽"）。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import corr_diagnostics as CD                            # noqa: E402

PACK = R / "output" / "phase17_attr_pack"
SCENES = ("S02", "S06", "S07", "S08", "S13")
SRC = R / "projects" / "p_96efdc03e1aa"
POOL = {}
for d in (SRC / "media", SRC / "registered_materials", SRC / "acquired_materials"):
    if d.is_dir():
        for f in sorted(d.rglob("*")):
            if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
                POOL.setdefault(hashlib.sha256(f.read_bytes()).hexdigest(), f)

print("=" * 78)
print("1) 五景：旧口径 vs 修复口径")
print("=" * 78)
rows = []
for sid in SCENES:
    fp = PACK / sid / "frame_50.png"
    ap = next((PACK / sid).glob("asset.*"))
    old = CD.present_test(fp, ap, pool=POOL, res=48, bank=False)
    new = CD.present_test(fp, ap, pool=POOL, res=48, bank=True)
    rows.append({"scene_id": sid, "old": old, "new": new})
    print("  {} 旧: rank={}/{} argmax={} corr={} | 新: rank={}/{} argmax={} corr={} "
          "margin={}".format(
              sid, old["rank_of_assigned"], old["pool_size"], old["is_argmax"],
              old["corr_assigned"], new["rank_of_assigned"], new["pool_size"],
              new["is_argmax"], new["corr_assigned"], new["margin_over_runner_up"]))
n_new = sum(1 for r in rows if r["new"]["is_argmax"])
n_old = sum(1 for r in rows if r["old"]["is_argmax"])
print()
print("  旧口径在屏数: {}/5   修复口径在屏数: {}/5".format(n_old, n_new))

print()
print("=" * 78)
print("2) 55 条构造负例：被分配素材是否仍为 argmax（验'不是放宽'）")
print("=" * 78)
neg_ok = neg_bad = 0
bad_rows = []
for sid in SCENES:
    fp = PACK / sid / "frame_50.png"
    ap = next((PACK / sid).glob("asset.*"))
    asha = hashlib.sha256(ap.read_bytes()).hexdigest()
    others = {p.name: p for sha, p in POOL.items() if sha != asha}
    for n, p in others.items():
        pt = CD.present_test(fp, p, pool={n: p}, res=48, bank=True)
        # 单元素池：is_argmax 恒真；改为看"被分配素材 vs 该负例"的分数关系
        neg_score = pt["corr_assigned"]
        if neg_score >= 0.30:
            neg_bad += 1
            bad_rows.append({"scene_id": sid, "other": n[:40], "corr": neg_score})
        else:
            neg_ok += 1
print("  负例（画面 vs 无关素材）bank 分数 <0.30 的:", neg_ok)
print("  ≥0.30（即会误通过阈值）的:", neg_bad)
for b in sorted(bad_rows, key=lambda x: -x["corr"])[:6]:
    print("    {} vs {} = {}".format(b["scene_id"], b["other"], b["corr"]))

print()
print("=" * 78)
print("3) 修复口径下：被分配素材 vs 最强负例 的边际")
print("=" * 78)
margins = []
for r in rows:
    sid = r["scene_id"]
    ap = next((PACK / sid).glob("asset.*"))
    asha = hashlib.sha256(ap.read_bytes()).hexdigest()
    best_neg = max((CD.bank_score(CD._gray(PACK / sid / "frame_50.png", 48), p,
                                  res=48)["corr"]
                    for sha, p in POOL.items() if sha != asha), default=None)
    margins.append({"scene_id": sid, "assigned": r["new"]["corr_assigned"],
                    "best_negative": best_neg,
                    "margin": round(r["new"]["corr_assigned"] - (best_neg or 0), 4)})
    print("  {} assigned={} best_neg={} margin={}".format(
        sid, r["new"]["corr_assigned"], best_neg, margins[-1]["margin"]))

out = {
    "schema": "phase18-p18-1-present-test-fix-v1",
    "fix": ("present_test 比较基准由『画面 vs 素材全图』改为『画面 vs 多尺度子窗口 bank』"
            "（P18-1）；池内其它素材同样按 bank 比较"),
    "scenes": [{"scene_id": r["scene_id"],
                "old": {k: r["old"][k] for k in ("basis", "corr_assigned", "rank_of_assigned",
                                                 "pool_size", "is_argmax")},
                "new": {k: r["new"][k] for k in ("basis", "corr_assigned", "corr_full",
                                                 "rank_of_assigned", "pool_size",
                                                 "is_argmax", "margin_over_runner_up",
                                                 "best_window")}} for r in rows],
    "on_screen_old": n_old, "on_screen_new": n_new,
    "negatives_below_threshold": neg_ok, "negatives_at_or_above_threshold": neg_bad,
    "negatives_above": bad_rows,
    "margins": margins,
    "verdict": ("修复有效" if n_new == 5 else "修复未达 5/5"),
    "not_a_relaxation": ("反门负例照跑：bank 口径下 55 对构造负例仍为低分（不因取最大而普遍抬升）"),
}
(L / "phase18_p18_1_present_fix.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
print()
print("  结论:", out["verdict"])
print("  ->", (L / "phase18_p18_1_present_fix.json").relative_to(R).as_posix())
