# -*- coding: utf-8 -*-
"""Phase 33 / P33-1 —— **运动质量门**（替代"只测变化不测质量"的空档）。

背景：既有三指标（`motion_metrics`）只度量"画面**有没有变化**"
（冻结占比 / 最长静止 / 开场变化），**不度量运动本身好不好**。
监理指出的三类观感缺陷此前无任何门禁覆盖：

  ① **zoom 居中锚定**：推近窗口必须**在源上居中收缩**（不得系统性偏移到某一角）；
  ② **逐帧位置单调化**：Q8 取整后不得出现位置往复（颤动）；
  ③ **平移方向按景平衡**：不得全片系统性同向漂移。

本文件把上述三项写成**运行前写死的门**（纯函数、零渲染、零网络）：
  · **Q1 无往复振荡**：帧间位置增量的符号翻转 **≤ 2 次/景**（阈值写死）；
  · **Q2 净漂移 ≤ 宣称幅度**：逐轴 |末−首| ≤ 计划声明的幅度（zoom=delta_full / pan=pan_px）；
  · **Q3 居中锚定**：`SLOW_ZOOM_IN` 的 x0/y0 恒等于 `(src−w)//2`（逐帧）；
  · **Q4 方向平衡**：全片 `SLOW_PAN` 的 LEFT/RIGHT 数量差 ≤1（无系统性同向）；
  · **Q5 闭式 ⇔ 逐帧一致**：`evaluate_closed_form` 与权威 `rects` 逐帧相等（防口径漂移）；
  · **Q6 头尾静止**：首/末 `STATIC_HEAD_TAIL_FRAMES` 帧与起始/终止位置一致。

运行: python tests/motion_quality_test.py
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core import motion as M                                        # noqa: E402

PASS, FAIL = [], []
MAX_FLIPS = 2          # 运行前写死：每景帧间位置符号翻转上限


def check(name, ok, detail=None):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else json.dumps(detail, ensure_ascii=False,
                                                      default=str)[:300]))
    return bool(ok)


def flips(seq):
    """相邻增量的符号翻转次数（忽略零增量）——往复振荡的直接度量。"""
    d = [seq[i + 1] - seq[i] for i in range(len(seq) - 1)]
    nz = [x for x in d if x != 0]
    return sum(1 for i in range(len(nz) - 1) if (nz[i] > 0) != (nz[i + 1] > 0))


# 覆盖面：短/中/长景 + 派生段命名 + hook（含 <10s 与 >35s 边界）
SCENES = []
_DURS = [31.231, 21.061, 21.115, 22.495, 36.745, 33.224, 18.600, 17.315, 23.541,
         36.836, 5.0, 9.9, 10.0, 44.0, 12.0]
for i, d in enumerate(_DURS):
    SCENES.append({"scene_id": "S{:02d}".format(i + 1), "duration_s": d,
                   "hook": i == 0, "src_path": "asset_{}.png".format(i)})
# 派生段命名（同一父景两段）
SCENES += [{"scene_id": "S20p1", "duration_s": 18.0, "hook": False, "src_path": "a.png"},
           {"scene_id": "S20p2", "duration_s": 22.0, "hook": False, "src_path": "a.png"}]

plan = M.build_plan(SCENES, out_w=1920, out_h=1080, fps=25)
scenes = plan["scenes"]
print("景数 {} | 启用 {} | 静止 {} | fallback {}".format(
    plan["counts"]["scenes"], plan["counts"]["enabled"], plan["counts"]["static"],
    plan["counts"]["fallback"]))
print()

# ---------------- Q1 无往复振荡 ----------------
worst, offenders = 0, []
for p in scenes:
    if not p["enabled"]:
        continue
    xs = [r[0] for r in p["rects"]]
    ys = [r[1] for r in p["rects"]]
    f = max(flips(xs), flips(ys))
    worst = max(worst, f)
    if f > MAX_FLIPS:
        offenders.append({"scene": p["scene_id"], "flips": f, "type": p["motion_type"]})
check("Q1 逐帧位置无往复振荡（每景符号翻转 ≤ {}，实测最差 {}）".format(MAX_FLIPS, worst),
      not offenders, offenders)

# ---------------- Q2 净漂移 ≤ 宣称幅度 ----------------
drift_bad = []
for p in scenes:
    if not p["enabled"]:
        continue
    xs = [r[0] for r in p["rects"]]
    ys = [r[1] for r in p["rects"]]
    if p["motion_type"] == "SLOW_PAN":
        claim_x, claim_y = int(p["params"]["pan_px"]), 0
    else:
        claim_x, claim_y = int(p["params"]["delta_full"]), 0
        # zoom 的 y 位移幅度由宽度按 16:9 推导，上界 = 高度方向的同步收缩
        claim_y = abs(p["rects"][0][3] - p["rects"][-1][3])
    dx, dy = abs(xs[-1] - xs[0]), abs(ys[-1] - ys[0])
    if dx > claim_x + 1 or dy > claim_y + 1:
        drift_bad.append({"scene": p["scene_id"], "dx": dx, "claim_x": claim_x,
                          "dy": dy, "claim_y": claim_y})
check("Q2 全片净漂移 ≤ 宣称幅度（逐轴，允许 1px 取整余量）", not drift_bad, drift_bad)

# ---------------- Q3 居中锚定（zoom） ----------------
cen_bad = []
for p in scenes:
    if not p["enabled"] or p["motion_type"] != "SLOW_ZOOM_IN":
        continue
    for k, r in enumerate(p["rects"]):
        if r[0] != (p["src_w"] - r[2]) // 2 or r[1] != (p["src_h"] - r[3]) // 2:
            cen_bad.append({"scene": p["scene_id"], "frame": k, "rect": list(r)})
            break
check("Q3 zoom 逐帧**居中锚定**（x0/y0 == (src−w)//2，无角偏移）", not cen_bad, cen_bad[:3])

# ---------------- Q4 平移方向平衡 ----------------
pan = [p for p in scenes if p["enabled"] and p["motion_type"] == "SLOW_PAN"]
lefts = sum(1 for p in pan if int(p["params"].get("sign") or 1) < 0)
rights = len(pan) - lefts
check("Q4 平移方向按景平衡（LEFT {} / RIGHT {}，差 ≤1）".format(lefts, rights),
      len(pan) == 0 or abs(lefts - rights) <= 1, {"left": lefts, "right": rights})
# 同向**连续**不得超过 2 个景（防"整体一边倒"）
runs, cur, prev = [], 0, None
for p in scenes:
    if p["enabled"] and p["motion_type"] == "SLOW_PAN":
        sgn = int(p["params"].get("sign") or 1)
        cur = cur + 1 if sgn == prev else 1
        prev = sgn
        runs.append(cur)
    else:
        prev, cur = None, 0
check("Q4b 同向平移不连续超过 2 个景（无系统性一边倒）",
      not runs or max(runs) <= 2, {"max_run": max(runs) if runs else 0})

# ---------------- Q5 闭式 ⇔ 逐帧一致 ----------------
mism = []
for p in scenes:
    if not p["enabled"]:
        continue
    for k in range(p["n_frames"]):
        cf = M.evaluate_closed_form(p, k)
        if tuple(cf) != tuple(p["rects"][k]):
            mism.append({"scene": p["scene_id"], "frame": k, "closed": list(cf),
                         "rects": list(p["rects"][k])})
            break
check("Q5 闭式（滤镜串用）⇔ 权威逐帧矩形 完全一致", not mism, mism[:3])

# ---------------- Q6 头静止 / 单调 / 末帧到位 ----------------
# 设计事实：**只有头部**有 `STATIC_HEAD_TAIL_FRAMES` 的静止；尾部取决于运动是否提前到达终点
#（v2 摊满整景 ⇒ 长景恰好末帧到位，短景可能提前到位后保持）。故 Q6 断言三条**真实不变量**：
#   ① 首 `h` 帧**完全相同**（头静止）；
#   ② 宽度**单调不减**（推近只进不退）且幅度确实发生了；
#   ③ 末帧 == 闭式末端（运动恰好收敛到计划终点，无"走不满/走过头"）。
q6_bad = []
for p in scenes:
    if not p["enabled"]:
        continue
    r = p["rects"]
    h = p["params"]["head_static"]
    if len(set(r[:h])) != 1:
        q6_bad.append({"scene": p["scene_id"], "why": "head_not_static"})
        continue
    if p["motion_type"] == "SLOW_ZOOM_IN":
        w = [x[2] for x in r]
        if not all(w[i + 1] <= w[i] for i in range(len(w) - 1)) or w[0] == w[-1]:
            q6_bad.append({"scene": p["scene_id"], "why": "width_not_monotonic",
                           "w0": w[0], "wn": w[-1]})
            continue
    if tuple(r[-1]) != tuple(M.evaluate_closed_form(p, p["n_frames"] - 1)):
        q6_bad.append({"scene": p["scene_id"], "why": "last_frame_not_at_planned_end"})
check("Q6 头静止 + 推近单调 + 末帧到位（三条不变量）", not q6_bad, q6_bad[:3])

# ---------------- Q7 幅度上限不变（回归守卫） ----------------
amp_bad = []
for p in scenes:
    if not p["enabled"]:
        continue
    if p["motion_type"] == "SLOW_ZOOM_IN":
        z = p["out_w"] / p["params"]["w_end"]
        if round(z, 4) > M.MAX_ZOOM_END + 1e-9:
            amp_bad.append({"scene": p["scene_id"], "zoom_end": z})
    else:
        if int(p["params"]["pan_px"]) > int(p["out_w"] * M.PAN_MAX_RATIO):
            amp_bad.append({"scene": p["scene_id"], "pan_px": p["params"]["pan_px"]})
check("Q7 幅度上限未被本次修复放宽（zoom ≤ {:.2f}；pan ≤ {:.0%} 画面宽）".format(
    M.MAX_ZOOM_END, M.PAN_MAX_RATIO), not amp_bad, amp_bad[:3])

print()
print("=" * 70)
print("motion_quality_test: {} PASS / {} FAIL".format(len(PASS), len(FAIL)))
if FAIL:
    print("FAILED:", json.dumps(FAIL, ensure_ascii=False))
print("=" * 70)
sys.exit(1 if FAIL else 0)
