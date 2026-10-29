# -*- coding: utf-8 -*-
"""Phase 17 / P17-1 & P17-2 测试：渲染后核验诊断函数 + 双向验证运行器。

覆盖：
  1. 基础度量（`_corr` / `_gray` / 与生产 `frame_corr` 同口径）
  2. `center_crop_array` 的确定性、边界与尺度语义
  3. 五假设函数（crop / density / subtitle / region / motion）的性质
  4. `present_test`：同分辨率下的 argmax 判定
  5. `attribute_scene`：在屏 vs 构造错配的区分
  6. P17-2 双向验证运行器：正门（在屏 100% PASS）/ 反门（错配 100% FAIL）

全部离线、确定性、零网络。
"""
from __future__ import annotations

import pathlib
import sys
import tempfile

import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import corr_diagnostics as CD                            # noqa: E402
from video_studio.core.materials import frame_corr, gray48                      # noqa: E402

FAILS = []
N = [0]


def check(name, cond, detail=None):
    N[0] += 1
    if cond:
        print("PASS ", name)
    else:
        print("FAIL ", name, "|", detail)
        FAILS.append(name)


tmp = pathlib.Path(tempfile.mkdtemp(prefix="p17_"))


def mk(name, kind):
    """合成确定性测试图：sparse=白底细线（稀疏）；photo=灰阶渐变（稠密）。"""
    W, H = 640, 360
    a = np.full((H, W), 255, dtype=np.uint8)
    if kind == "sparse":
        for i in range(0, W, 37):
            a[:, i] = 0
        for j in range(0, H, 23):
            a[j, :] = 0
    else:
        yy, xx = np.mgrid[0:H, 0:W]
        a = ((xx * 255 // W) // 2 + (yy * 255 // H) // 2).astype(np.uint8)
    p = tmp / name
    Image.fromarray(a).save(p)
    return p


A = mk("a.png", "sparse")
B = mk("b.png", "photo")

# ---------------- 1. 基础度量 ----------------
ga = gray48(A)
check("1 corr 自比 == 1.0（同图）", abs(frame_corr(ga, ga) - 1.0) < 1e-9)
check("1b 诊断 _corr 与生产 frame_corr 同口径",
      abs(CD._corr(CD._gray(A, 48), CD._gray(A, 48)) - 1.0) < 1e-9)
check("1c 异图 corr < 1", frame_corr(ga, gray48(B)) < 0.999)

# ---------------- 2. center_crop_array ----------------
full = np.asarray(Image.open(B).convert("L"), dtype=np.float64)
c1 = CD.center_crop_array(full, 0, 0, scale=0.5)
c2 = CD.center_crop_array(full, 0, 0, scale=0.5)
check("2 center_crop 确定性（同参同结果）", c1.shape == c2.shape and np.array_equal(c1, c2))
check("2b scale=0.5 尺寸约为一半",
      abs(c1.shape[0] - full.shape[0] // 2) <= 1
      and abs(c1.shape[1] - full.shape[1] // 2) <= 1, (c1.shape, full.shape))
c3 = CD.center_crop_array(full, 0, 0, scale=0.5, dx=0.4)
check("2c 偏移被夹取在合法范围内", c3.shape == c1.shape)

# ---------------- 3. 五假设性质 ----------------
ch = CD.crop_hypothesis(CD._gray(B, 48), B, res=48)
check("3 crop_hypothesis 返回 best/rows", "best" in ch and bool(ch["rows"]))
dh = CD.density_hypothesis(B, B)
check("3b density 自比各级均 = 1.0",
      all(abs(c["corr"] - 1.0) < 1e-6 for c in dh["curve"]), dh["curve"])
sh = CD.subtitle_hypothesis(B, B)
check("3c subtitle 字段齐备", {"corr_full", "corr_masked", "gain"} <= set(sh))
rh = CD.region_hypothesis(B, B)
check("3d region 返回窗口与最佳", "best" in rh and rh["best"]["corr"] > -2)
mo = CD.motion_check("S01", None)
check("3e 无运动证据 ⇒ motion_enabled False", mo["motion_enabled"] is False)

# ---------------- 4. present_test ----------------
pt = CD.present_test(B, B, pool={"a": A}, res=48)
check("4 present_test 自比 is_argmax",
      pt["is_argmax"] is True and pt["rank_of_assigned"] == 1)
pt2 = CD.present_test(A, B, pool={"a": A}, res=48)
check("4b 异图对照 pool_size 正确", pt2["pool_size"] == 2)

# ---------------- 5. attribute_scene ----------------
res_self = CD.attribute_scene(scene_id="T1", frame_path=B, asset_path=B)
check("5 同图自比 ⇒ 判为在屏（非 possible_real_mismatch）",
      res_self["verdict"] != "possible_real_mismatch", res_self["verdict"])
res_other = CD.attribute_scene(scene_id="T2", frame_path=A, asset_path=B, pool={"a": A})
check("5b 构造错配（画面来自 A，被分配 B）⇒ 不为'在屏'",
      res_other["verdict"] == "possible_real_mismatch", res_other["verdict"])
check("5c 归因结果含全部假设",
      {"crop", "density", "subtitle", "region", "motion"} <= set(res_other["hypotheses"]))

# ---------------- 6. P17-2 / P18-2 双向验证运行器 ----------------
def dual_gate(positives, negatives, metric, threshold=0.30):
    """正门：正例 100% PASS；反门：负例 100% FAIL。返回 (ok, detail)。"""
    pos_fail = [p for p in positives if metric(p) < threshold]
    neg_pass = [n for n in negatives if metric(n) >= threshold]
    return (not pos_fail and not neg_pass,
            {"positives_failed": pos_fail, "negatives_passed": neg_pass})


def _self_metric(p):
    return frame_corr(gray48(p), gray48(p))


ok, det = dual_gate([A, B], [], _self_metric)
check("6 双门运行器：正门全过且无负例 ⇒ ok", ok is True and det["positives_failed"] == [])
ok2, det2 = dual_gate([A], [], lambda p: 0.1)
check("6b 双门运行器：正门未过 ⇒ ok False", ok2 is False and det2["positives_failed"] == [A])
ok3, det3 = dual_gate([], [A], _self_metric)
check("6c 双门运行器：反门未过 ⇒ ok False", ok3 is False and det3["negatives_passed"] == [A])

# ---------------- 7. P18-1 present_test 修复（子窗口 bank 口径） ----------------
bk = CD.bank_score(CD._gray(B, 48), B, res=48)
check("7 bank_score 自比达上限（≥0.99）", bk["corr"] >= 0.99, bk["corr"])
check("7b bank_score 返回窗口元数据",
      {"corr", "scale", "x0", "y0", "w", "h"} <= set(bk))
pt_old = CD.present_test(B, B, pool={"a": A}, res=48, bank=False)
pt_new = CD.present_test(B, B, pool={"a": A}, res=48, bank=True)
check("7c 修复后 basis = subwindow_bank", pt_new["basis"] == "subwindow_bank")
check("7d 旧口径 basis = full_image（对照可复现）", pt_old["basis"] == "full_image")
check("7e 修复后仍给出 corr_full 与 margin",
      "corr_full" in pt_new and "margin_over_runner_up" in pt_new)
pt_self = CD.present_test(B, B, res=48, bank=True)
check("7f 自比 ⇒ is_argmax True", pt_self["is_argmax"] is True)

# ---------------- 8. P18-3 仲裁层（不放宽真门） ----------------
def arbitrate(corr_value, presence, threshold=0.30):
    """纯逻辑复刻仲裁层：corr≥阈值 ⇒ 确定性放行；否则按 VLM presence 定夺（fail-closed）。"""
    if corr_value >= threshold:
        return "PASS_DETERMINISTIC"
    return "PASS_VLM_PRESENT" if presence == "present" else "BLOCKED"


check("8 仲裁：corr 达标 ⇒ 不看 VLM 直接放行", arbitrate(0.40, "absent") == "PASS_DETERMINISTIC")
check("8b 仲裁：corr 不足 + present ⇒ 放行", arbitrate(0.20, "present") == "PASS_VLM_PRESENT")
check("8c 仲裁：corr 不足 + absent ⇒ 阻断", arbitrate(0.20, "absent") == "BLOCKED")
check("8d 仲裁：corr 不足 + uncertain ⇒ 阻断（fail-closed）",
      arbitrate(0.20, "uncertain") == "BLOCKED")

print()
print("结果: {}/{} 通过".format(N[0] - len(FAILS), N[0]))
if FAILS:
    print("失败项:", FAILS)
sys.exit(1 if FAILS else 0)
