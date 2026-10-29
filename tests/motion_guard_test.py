# -*- coding: utf-8 -*-
"""Phase 25 / P25-1 测试：**每景 corr 守卫**（硬性）+ 运动 v2.1 幅度 + 三指标断言。

覆盖：
  1. POLICY：`MAX_ZOOM_END` 已上修到 1.25；降级目标 `MAX_ZOOM_END_V1` 仍为 1.08；守卫阈值 0.30
  2. `zoom_max` 参数：显式传 1.08 ⇒ 该景幅度回到 1.08（守卫重渲路径）；缺省 ⇒ 1.25
  3. `guarded_scenes`：跌破阈值 ⇒ DOWNGRADE + `MOTION_DOWNGRADED`；达标 ⇒ KEEP；
     corr 缺失 ⇒ KEEP_UNKNOWN（不降级但要登记）；阈值边界（恰 0.30 ⇒ 不降级）
  4. `rebuild_plan_with_guard`：降级景幅度 ≤1.08 且**只影响这些景**；plan.counts.downgraded 一致
  5. 派生段 id（`S02p1`）的**父景序号解析**（P25 修复：旧实现抛 ValueError）
  6. 三指标阈值与探针口径**运行前写死**（<50% / <25s / ≥3 次 / 320×180 / MAD 0.05）
  7. 确定性：同输入两次守卫结论一致
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import motion as M                                      # noqa: E402
from video_studio.core import motion_guard as G                                # noqa: E402
from video_studio.core import motion_metrics as MM                             # noqa: E402

FAILS, N = [], [0]


def check(name, cond, detail=None):
    N[0] += 1
    if cond:
        print("PASS ", name)
    else:
        print("FAIL ", name, "|", detail)
        FAILS.append(name)


# ---------- 1. POLICY ----------
check("1 zoom 上限已上修到 1.25", M.MAX_ZOOM_END == 1.25, M.MAX_ZOOM_END)
check("1b 降级目标仍为 1.08", M.MAX_ZOOM_END_V1 == 1.08, M.MAX_ZOOM_END_V1)
check("1c 守卫阈值 0.30", M.CORR_GUARD_MIN == 0.30, M.CORR_GUARD_MIN)

# ---------- 2. zoom_max 参数 ----------
p125 = M.plan_scene({"scene_id": "S1", "duration_s": 24.0}, out_w=1920, out_h=1080, fps=25)
p108 = M.plan_scene({"scene_id": "S1", "duration_s": 24.0}, out_w=1920, out_h=1080, fps=25,
                    zoom_max=M.MAX_ZOOM_END_V1)
check("2 缺省 ⇒ zoom_end = 1.25", abs(p125["params"]["zoom_end"] - 1.25) < 0.01,
      p125["params"]["zoom_end"])
check("2b 显式 1.08 ⇒ zoom_end ≈ 1.08（守卫重渲路径）",
      abs(p108["params"]["zoom_end"] - 1.0799) < 0.01, p108["params"]["zoom_end"])
check("2c 1.25 的总推进 > 1.08 的总推进",
      1920 - p125["params"]["w_end"] > 1920 - p108["params"]["w_end"],
      (p125["params"]["w_end"], p108["params"]["w_end"]))

# ---------- 3. guarded_scenes ----------
plan = M.build_plan([{"scene_id": "S01", "duration_s": 24.0, "hook": True},
                     {"scene_id": "S02", "duration_s": 24.0},
                     {"scene_id": "S03", "duration_s": 24.0},
                     {"scene_id": "S04", "duration_s": 24.0}],
                    out_w=1920, out_h=1080, fps=25)
g = G.guarded_scenes(plan, {"S01": 0.55, "S02": 0.29, "S03": 0.30, "S04": None})
check("3 跌破阈值 ⇒ DOWNGRADE", g["downgrade"] == ["S02"], g["downgrade"])
check("3b 恰等于阈值 0.30 ⇒ 不降级（KEEP）", "S03" in g["keep"], g["keep"])
check("3c corr 缺失 ⇒ KEEP_UNKNOWN（登记但不降级）", "S04" in g["unknown"], g["unknown"])
check("3d 降级记录带 MOTION_DOWNGRADED 码",
      any(r.get("code") == G.DOWNGRADE_CODE for r in g["records"]), g["records"])
check("3e all_pass = False（有降级）", g["all_pass"] is False)
g_clean = G.guarded_scenes(plan, {"S01": 0.55, "S02": 0.60, "S03": 0.30, "S04": 0.44})
check("3f 全部达标 ⇒ all_pass True 且无降级",
      g_clean["all_pass"] is True and not g_clean["downgrade"])

# ---------- 4. rebuild_plan_with_guard ----------
scenes = [{"scene_id": "S0{}".format(i), "duration_s": 24.0} for i in (1, 2, 3, 4)]
plan2, g2 = G.rebuild_plan_with_guard(scenes, out_w=1920, out_h=1080, fps=25,
                                      scene_corrs={"S01": 0.5, "S02": 0.1,
                                                   "S03": 0.9, "S04": 0.7})
zby = {p["scene_id"]: p["params"].get("zoom_end") for p in plan2["scenes"]}
check("4 降级景幅度 ≤1.08", zby.get("S02") is None or zby["S02"] <= 1.08 + 1e-6, zby)
check("4b 未降级景**不受影响**（仍是 1.25 或 pan 的 1.0）",
      all(zby[s] is None or zby[s] > 1.08 or zby[s] == 1.0
          for s in ("S01", "S03", "S04")), zby)
check("4c counts.downgraded 与守卫一致",
      plan2["counts"]["downgraded"] == len(g2["downgrade"]), plan2["counts"])
check("4d plan 内嵌 guard 摘要", "guard" in plan2 and plan2["guard"]["min_corr"] == 0.30)

# ---------- 5. 派生段 id 的父景序号解析（P25 修复） ----------
check("5 _scene_ordinal('S02p1') == 2", M._scene_ordinal("S02p1") == 2)
check("5b _scene_ordinal('S01') == 1", M._scene_ordinal("S01") == 1)
check("5c _scene_ordinal 异常输入 ⇒ 0", M._scene_ordinal("X") == 0)
try:
    bp = M.build_plan([{"scene_id": "S02p1", "duration_s": 24.0},
                       {"scene_id": "S01", "duration_s": 24.0}],
                      out_w=1920, out_h=1080, fps=25)
    check("5d 派生段 id 不再抛 ValueError（可建计划）", bp["counts"]["scenes"] == 2)
    types = {p["scene_id"]: p["motion_type"] for p in bp["scenes"]}
    check("5e 'S02p1' 按父景序号 2（偶数）⇒ SLOW_PAN", types["S02p1"] == "SLOW_PAN", types)
except Exception as exc:                                                        # noqa: BLE001
    check("5d 派生段 id 不再抛 ValueError（可建计划）", False,
          "{}: {}".format(type(exc).__name__, exc))

# ---------- 6. 三指标口径运行前写死 ----------
check("6 冻结占比上限 0.50", MM.FREEZE_RATIO_MAX == 0.50)
check("6b 最长静止上限 25.0s", MM.MAX_STATIC_S == 25.0)
check("6c 开场窗口 90s / 变化 ≥3 次",
      MM.OPENING_WINDOW_S == 90.0 and MM.OPENING_CHANGES_MIN == 3)
check("6d 探针 320×180（P25-1 口径）", (MM.PROBE_W, MM.PROBE_H) == (320, 180),
      (MM.PROBE_W, MM.PROBE_H))
check("6e MAD 阈值 0.05", MM.MAD_THRESHOLD == 0.05)

# ---------- 7. 确定性 ----------
a = G.guarded_scenes(plan, {"S01": 0.55, "S02": 0.29, "S03": 0.30, "S04": 0.4})
b = G.guarded_scenes(plan, {"S01": 0.55, "S02": 0.29, "S03": 0.30, "S04": 0.4})
check("7 守卫结论确定性（同输入同输出）",
      a["downgrade"] == b["downgrade"] and a["keep"] == b["keep"])

print()
print("结果: {}/{} 通过".format(N[0] - len(FAILS), N[0]))
if FAILS:
    print("失败项:", FAILS)
sys.exit(1 if FAILS else 0)
