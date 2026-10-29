# -*- coding: utf-8 -*-
"""Phase 24 / P24-1 测试：运动策略 v2（全镜缓推）+ 冻结占比三指标度量。

覆盖：
  1. v2 策略常量与 `select_scenes`（全镜启用、hook 强制、<10s 静止）
  2. `plan_scene` 全镜缓推：摊满整景、幅度 ≤1.08、闭式与逐帧 rects **逐帧一致**
  3. `motion_metrics` 三指标：**合成短片**上验证冻结/运动判定与阈值方向
  4. **数学冲突上界**：授权幅度下每秒可见变化的上界（回归防漂移）
"""
from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import motion as M                                      # noqa: E402
from video_studio.core import motion_metrics as MM                             # noqa: E402

FAILS, N = [], [0]


def check(name, cond, detail=None):
    N[0] += 1
    if cond:
        print("PASS ", name)
    else:
        print("FAIL ", name, "|", detail)
        FAILS.append(name)


# ---------- 1. v2 策略常量与 select_scenes ----------
check("1 FULL_SCENE_MOTION 已启用", M.FULL_SCENE_MOTION is True)
check("1b 启用比例上限 = 1.0（全镜）", M.MAX_ENABLED_RATIO_V2 == 1.0)
scenes = [{"scene_id": "S{:02d}".format(i + 1), "duration_s": d, "hook": (i == 0)}
          for i, d in enumerate([30.0, 5.0, 44.0, 12.0])]
sel = M.select_scenes(scenes)
flags = {s["scene_id"]: s["motion_enabled"] for s in sel}
check("1c 全镜启用（≥10s 的景全部 motion_enabled）",
      flags["S01"] and flags["S03"] and flags["S04"], flags)
check("1d <10s 的景保持静止（prefer-STATIC）", flags["S02"] is False, flags)
# hook 强制：构造 hook 景短于其他景且 ratio 极小（cap=0）时仍被强制启用
only_hook = M.select_scenes([{"scene_id": "H1", "duration_s": 30.0, "hook": True},
                             {"scene_id": "X1", "duration_s": 90.0, "hook": False}],
                            policy={"max_enabled_ratio": 0.0, "force_hook": True})
check("1e hook 强制启用（cap=0 时仍启用）",
      {s["scene_id"]: s["motion_enabled"] for s in only_hook}["H1"] is True, only_hook)

# ---------- 2. plan_scene 全镜缓推 ----------
p = M.plan_scene({"scene_id": "S1", "duration_s": 20.0}, out_w=1920, out_h=1080, fps=25)
pr, rects, n = p["params"], p["rects"], p["n_frames"]
check("2 启用且类型为 SLOW_ZOOM_IN", p["enabled"] and p["motion_type"] == "SLOW_ZOOM_IN")
check("2b 幅度 ≤ MAX_ZOOM_END（1.08）", pr["zoom_end"] <= M.MAX_ZOOM_END + 1e-9,
      pr["zoom_end"])
check("2c 运动摊满整景（motion_frames ≈ n_frames − 8）",
      pr["motion_frames"] == max(n - M.STATIC_HEAD_TAIL_FRAMES, 0), pr["motion_frames"])
check("2d 起点宽度 = out_w", rects[0][2] == 1920, rects[0][2])
check("2e 终点宽度 = w_end（走完全部幅度）", rects[-1][2] == pr["w_end"],
      (rects[-1][2], pr["w_end"]))
mism = [k for k in range(n) if M.evaluate_closed_form(p, k) != rects[k]]
check("2f **闭式与逐帧 rects 逐帧一致**（0 处不一致）", not mism, mism[:5])
check("2g 存在中间变化（非 Static）", any(rects[i][2] != rects[0][2] for i in range(n)))
cf = M.crop_filter(p)
check("2h crop_filter 为 v2 直接进度式（含 delta_full/motion 插值）",
      "v2_progress" in str(pr) and pr.get("v2_progress") is True
      and "max({}".format(pr["w_end"]) in cf and "min((" in cf, cf[:90])
check("2h2 唯一宽度数 > 100（真正摊满整景，而非几步跳变）",
      len({x[2] for x in rects}) > 100, len({x[2] for x in rects}))
p_short = M.plan_scene({"scene_id": "S2", "duration_s": 5.0}, out_w=1920, out_h=1080)
check("2i <10s ⇒ 静止回退", p_short["enabled"] is False
      and p_short["motion_type"] == "STATIC")

# ---------- 3. motion_metrics 三指标（合成短片）----------
ff = None
for cand in (ROOT / "bin" / "ffmpeg.exe", "ffmpeg"):
    if isinstance(cand, pathlib.Path) and cand.is_file():
        ff = str(cand)
        break
    if isinstance(cand, str):
        ff = cand
        break
if ff:
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="p24_"))
    # 静止片：单色 20s ⇒ MAD 全 0 ⇒ 冻结占比 100%
    still = tmp / "still.mp4"
    subprocess.run([ff, "-v", "error", "-y", "-f", "lavfi", "-i",
                    "color=c=gray:s=160x90:d=20:r=25", "-c:v", "libx264",
                    "-preset", "ultrafast", "-crf", "20", str(still)],
                   capture_output=True, text=True)
    # 运动片：testsrc 有动态图案 ⇒ MAD 高 ⇒ 冻结占比低
    moving = tmp / "moving.mp4"
    subprocess.run([ff, "-v", "error", "-y", "-f", "lavfi", "-i",
                    "testsrc=size=160x90:rate=25:duration=20", "-c:v", "libx264",
                    "-preset", "ultrafast", "-crf", "20", str(moving)],
                   capture_output=True, text=True)
    if still.is_file():
        rs = MM.evaluate(str(still), ff)
        check("3 静止片 ⇒ 冻结占比 100%、最长静止 ≈ 全长",
              rs["freeze_ratio"] > 0.9 and rs["longest_static_s"] >= 15.0,
              (rs["freeze_ratio"], rs["longest_static_s"]))
        check("3b 静止片 ⇒ freeze_ratio 指标不通过", rs["pass"]["freeze_ratio"] is False)
    else:
        check("3 静止片生成", False, "ffmpeg lavfi 不可用")
    if moving.is_file():
        rm = MM.evaluate(str(moving), ff)
        check("3c 运动片 ⇒ MAD 显著 > 0（中位数 > 1）", (rm["mad_median"] or 0) > 1.0,
              rm["mad_median"])
        check("3d 运动片 ⇒ 冻结占比 < 50%（指标通过）",
              rm["pass"]["freeze_ratio"] is True, rm["freeze_ratio"])
        check("3e 运动片 ⇒ 开场 90s 变化 ≥3 次",
              rm["pass"]["opening_changes"] is True, rm["opening_changes"])
        check("3f 三指标结构齐备",
              set(rm["pass"]) == {"freeze_ratio", "longest_static", "opening_changes"})
    # 度量确定性：同片两次结果一致
    if still.is_file():
        a = MM.measure_motion(str(still), ff)
        b = MM.measure_motion(str(still), ff)
        check("3g 度量确定性（两次 MAD 序列一致）",
              a["mad_median"] == b["mad_median"] and a["freeze_ratio"] == b["freeze_ratio"])
else:
    check("3 ffmpeg 可用", False, "未找到 ffmpeg")

# ---------- 4. 幅度与三指标口径（P25-1 起：1.25）----------
b = M.plan_scene({"scene_id": "S", "duration_s": 20.0}, out_w=1920, out_h=1080, fps=25)
px_total = 1920 - b["params"]["w_end"]
check("4 1.25 上限 ⇒ 总推进 384px（1920−1536）", px_total == 384, px_total)
probe_px = px_total * MM.PROBE_W / 1920
check("4b 探针尺度总变化 = 64px（>20px，跨过可测阈值）", 60.0 < probe_px < 68.0,
      round(probe_px, 2))
check("4c 摊满 20s ⇒ ≥1px/秒（3.2 可感知；P24 的 1.08 只有 0.59 不可感知）",
      probe_px / 20.0 >= 1.0, round(probe_px / 20.0, 4))
check("4d 三指标阈值与授权一致（<50%、<25s、≥3 次）",
      (MM.FREEZE_RATIO_MAX, MM.MAX_STATIC_S, MM.OPENING_CHANGES_MIN) == (0.50, 25.0, 3))
# 降级路径：显式 1.08 ⇒ 回到 P24 的不可感知区（守卫降级后的情形）
b108 = M.plan_scene({"scene_id": "S", "duration_s": 20.0}, out_w=1920, out_h=1080, fps=25,
                    zoom_max=M.MAX_ZOOM_END_V1)
px108 = 1920 - b108["params"]["w_end"]
check("4e 降级到 1.08 ⇒ 142px（回到不可感知区，故守卫只用于兜底）", px108 == 142, px108)
check("4f 探针 320×180（P25-1 口径）", (MM.PROBE_W, MM.PROBE_H) == (320, 180),
      (MM.PROBE_W, MM.PROBE_H))

print()
print("结果: {}/{} 通过".format(N[0] - len(FAILS), N[0]))
if FAILS:
    print("失败项:", FAILS)
sys.exit(1 if FAILS else 0)
