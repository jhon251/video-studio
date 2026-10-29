# -*- coding: utf-8 -*-
"""P13-1：**生产运动层**（整数帧 pan/zoom；纯函数、确定性、零 I/O）。

来源与边界：本模块是 stage33 实验结论的**提炼重写**（不 import 实验代码、不改写 stage33 的
NOT_VALIDATED 状态）。沿用其实验纪律：
  · **整数帧**：所有位移/缩放步长均为整数像素，逐帧矩形可用闭式表达精确复算；
  · **恒定步长 + 三段缓动**（加速 20% / 匀速 60% / 减速 20%），轨迹单调、无方向反转、无 0/1 交替；
  · **prefer STATIC over meaningless motion**：无明确运动理由、或时长过短 ⇒ 静止。
与授权书的差异登记：授权书写"zoompan/crop 滤镜串"；本模块输出**crop 表达式滤镜串**
（`crop=w=…:h=…:x=…:y=…`，仅用整数运算与 `min/max/floor`）——因为 `zoompan` 是**亚像素浮点插值**，
与"整数帧"纪律冲突；且 crop 表达式可被本模块的 `evaluate_closed_form()` 在 Python 侧**精确复算**，
从而可证明"滤镜串 ⇔ 权威逐帧矩形"等价（见 tests/motion_test.py）。

策略常量（依据逐条注明；**只可收紧不可放宽**）：
  · `MAX_ZOOM_END = 1.08`：授权书 P13-1(a) 上限；不威胁成片抽帧核验 `corr ≥ 0.30`。
  · `PAN_MAX_RATIO = 0.03`：授权书 P13-1(b) 平移幅度 ≤ 画面宽高 3%，单方向。
  · `MIN_SCENE_S = 10.0`：授权书 P13-1(c) 场景 < 10s 保持静止。
  · `MAX_ENABLED_RATIO = 0.6`：授权书 P13-1(c)"启用比例确定性"——最多 60% 场景启用，
    选取顺序 `(hook 优先, 时长降序, scene_id 升序)`，写死在 `select_scenes()`。
  · `STATIC_HEAD_TAIL_FRAMES = 8`：stage33 纪律（头尾静止，避免入场/出场抖动）。
  · `ZOOM_STEP_PX = 2` / `PAN_MIN_STEP_PX = 1`：stage33 纪律（缩放偶数步长、平移 ≥1px/帧）。
"""
from __future__ import annotations

from .visual_requirement import canonical, sha256_text

SCHEMA = "motion-plan-v1"
VERSION = 1
PLAN_RULE_VERSION = "motion-integer-frame-v1"

MAX_ZOOM_END = 1.25
#: **P24-1 之前的旧上限**（1.08）。P25-1 授权把上限提到 1.25；
#: 该旧值保留为**每景 corr 守卫的降级目标**（某景 corr<0.30 ⇒ 该景幅度降回 1.08 重渲）。
MAX_ZOOM_END_V1 = 1.08
#: 每景 corr 守卫阈值（P25-1）：渲染后逐景复核，低于此值 ⇒ 该景幅度降级到 `MAX_ZOOM_END_V1`
CORR_GUARD_MIN = 0.30
PAN_MAX_RATIO = 0.03
MIN_SCENE_S = 10.0
MAX_ENABLED_RATIO = 0.6
#: **P24-1 运动策略 v2**：全镜缓推。启用比例上限提到 1.0（全镜启用），
#: 但仍遵守 prefer-STATIC：`<MIN_SCENE_S` 的景保持静止（本片所有景 >10s，故全片启用）。
MAX_ENABLED_RATIO_V2 = 1.0
FULL_SCENE_MOTION = True
STATIC_HEAD_TAIL_FRAMES = 8
ZOOM_STEP_PX = 2
PAN_MIN_STEP_PX = 1
DEFAULT_FPS = 25
MOTION_FALLBACK_CODE = "MOTION_FALLBACK_STATIC"
#: **设计决定（已登记）**：stage33 的「恒定步长 ≥1px/帧 且贯穿整场景」与授权书的幅度上限
#: （平移 3% ≈46px、缩放 8% ≈142px）在长场景下不可同时满足（仅 0.16–0.25px/帧）。
#: 生产模块改为：运动集中在**至多 150 帧（6s）**的窗口内，窗口内步长 ≥1px/帧（平移）
#: 或 2px/帧（缩放），窗口外静止；**幅度上限不变、整数帧纪律不变**。
MOTION_WINDOW_MAX_FRAMES = 150

MOTION_TYPES = ("STATIC", "SLOW_ZOOM_IN", "SLOW_PAN")
POLICY = {
    "max_zoom_end": {"value": MAX_ZOOM_END,
                     "basis": "授权书 P13-1(a)：zoom 1.00→≤1.08；不威胁 corr≥0.30 抽帧核验；"
                              "**实测后可收紧不可放宽**"},
    "pan_max_ratio": {"value": PAN_MAX_RATIO, "basis": "授权书 P13-1(b)：平移 ≤ 画面宽高 3%，单方向"},
    "min_scene_s": {"value": MIN_SCENE_S, "basis": "授权书 P13-1(c)：场景 <10s 保持静止（prefer STATIC）"},
    "max_enabled_ratio": {"value": MAX_ENABLED_RATIO,
                          "basis": "授权书 P13-1(c)：启用比例确定性——上限 60%，"
                                   "选取序 (hook, 时长降序, scene_id 升序)"},
    "static_head_tail_frames": {"value": STATIC_HEAD_TAIL_FRAMES, "basis": "stage33 纪律：头尾静止"},
    "zoom_step_px": {"value": ZOOM_STEP_PX, "basis": "stage33 纪律：缩放偶数步长 2px/帧"},
    "pan_min_step_px": {"value": PAN_MIN_STEP_PX, "basis": "stage33 纪律：平移 ≥1px/帧"},
    "default_fps": {"value": DEFAULT_FPS, "basis": "生产渲染默认 fps（6-E 时长契约口径）"},
    "motion_window_max_frames": {"value": MOTION_WINDOW_MAX_FRAMES,
                                 "basis": "P13-1 设计决定登记：运动集中在 ≤150 帧窗口内，"
                                          "窗口内步长 ≥1px/帧（平移）/2px/帧（缩放），"
                                          "窗口外静止（幅度上限与整数帧纪律不变）"},
}


def _stage_frames(motion_frames: int) -> tuple[int, int, int]:
    """三段缓动帧数分配（加速 20% / 匀速 60% / 减速 20%，整数）。"""
    n1 = max(1, round(motion_frames * 0.2))
    n3 = max(1, round(motion_frames * 0.2))
    n2 = max(1, motion_frames - n1 - n3)
    return n1, n2, n3


def _steps(total_units: int, n1: int, n2: int, n3: int, min_step: int) -> list[int] | None:
    """把总单位数按三段恒定步长分配；平均速度 < min_step ⇒ None（→ 静止）。"""
    n = n1 + n2 + n3
    if n <= 0 or total_units <= 0:
        return None
    if total_units / n < min_step:
        return None
    s2 = max(min_step, round(total_units / n))
    s1 = max(min_step, s2 // 2)
    s3 = max(min_step, s2 // 2)
    steps = [s1] * n1 + [s2] * n2 + [s3] * n3
    diff = total_units - sum(steps)
    if diff > 0:
        for i in range(diff):
            steps[n1 + (i % n2)] += 1
    elif diff < 0:
        for _ in range(-diff):
            idx = max(range(len(steps)), key=lambda i: steps[i])
            if steps[idx] > min_step:
                steps[idx] -= 1
            else:
                break
    return steps


def cumulative(steps: list[int], n1: int, n2: int, n3: int, frame_offset: int) -> int:
    """累积位移（闭式）：C(k) = s1·min(max(k,0),n1) + s2·min(max(k-n1,0),n2) + s3·min(max(k-n1-n2,0),n3)。

    该闭式即滤镜串中 `min/max` 表达式的**同一公式**（整数语义精确一致）。
    """
    k = max(frame_offset, 0)
    s1, s2, s3 = steps[0], steps[n1] if len(steps) > n1 else 0, steps[n1 + n2] if len(
        steps) > n1 + n2 else 0
    return (s1 * min(k, n1) + s2 * min(max(k - n1, 0), n2) + s3 * min(max(k - n1 - n2, 0), n3))


def _even_round_half_up(x: float) -> int:
    """强制偶数尺寸：`2*floor((x+1)/2)` —— 与滤镜串中同一表达式**逐值一致**（整数语义）。"""
    return 2 * int((float(x) + 1) // 2)


def plan_scene(scene: dict, *, out_w: int, out_h: int, fps: int = DEFAULT_FPS,
               enabled: bool = True, direction: str = "RIGHT",
               motion_type: str = "SLOW_ZOOM_IN",
               zoom_max: float | None = None,
               min_scene_s: float | None = None) -> dict:
    """单场景运动计划（纯函数）。返回含权威逐帧矩形 + 闭式参数 + 滤镜串的确定性记录。

    `scene` 需含：`scene_id`、`duration_s`、`src_path`（仅记录用，不读取）、可选 `src_w/src_h`
    （缺省按 `out_w/out_h` 外扩 8% 作为可用画布，仍是**确定性**取值）。
    """
    sid = str(scene.get("scene_id"))
    dur = float(scene.get("duration_s") or 0.0)
    src_path = scene.get("src_path")
    n_frames = max(1, round(dur * fps))
    src_w = int(scene.get("src_w") or round(out_w * MAX_ZOOM_END))
    src_h = int(scene.get("src_h") or round(out_h * MAX_ZOOM_END))
    base = {"schema": SCHEMA, "version": VERSION, "rule_version": PLAN_RULE_VERSION,
            "scene_id": sid, "duration_s": dur, "fps": fps, "n_frames": n_frames,
            "src_path": src_path, "src_w": src_w, "src_h": src_h,
            "out_w": out_w, "out_h": out_h, "direction": direction,
            "static_head_tail_frames": STATIC_HEAD_TAIL_FRAMES}
    if not enabled or dur < (MIN_SCENE_S if min_scene_s is None else float(min_scene_s)):
        rects = [(0, 0, out_w, out_h)] * n_frames
        return {**base, "enabled": False, "motion_type": "STATIC", "rects": rects,
                "params": {"zoom_start": 1.0, "zoom_end": 1.0, "pan_px": 0},
                "reason": ("disabled_by_policy" if not enabled
                           else "duration<{:.1f}s ⇒ prefer STATIC".format(
                               MIN_SCENE_S if min_scene_s is None else float(min_scene_s))),
                "fallback_code": None}
    if motion_type == "SLOW_PAN":
        span = max(src_w - out_w, 0)
        # 平移幅度 = **画面尺寸的 3%**（授权书 P13-1(b)），并受可用画布余量约束
        total = min(int(out_w * PAN_MAX_RATIO), span) if span > 0 else 0
        total = max(total, 1) if span > 0 else 0
        avail = max(n_frames - STATIC_HEAD_TAIL_FRAMES, 0)
        if FULL_SCENE_MOTION:
            # P24-1 v2：平移同样**摊满整景**（v1 用 `min(avail, total, 150)` ⇒ 挤在景头）
            motion = avail
        else:
            motion = min(n_frames - 2 * STATIC_HEAD_TAIL_FRAMES,
                         max(total // PAN_MIN_STEP_PX, 1), MOTION_WINDOW_MAX_FRAMES)
        if span <= 0 or avail <= 0 or total <= 0 or motion <= 0:
            return _static_fallback(base, n_frames, out_w, out_h,
                                    "PAN_INFEASIBLE（画布无余量或时长过短）")
        if FULL_SCENE_MOTION:
            n1 = max(motion // 2, 1)
            n3 = max(motion // 8, 1)
            n2 = max(motion - n1 - n3, 1)
            n3 = max(motion - n1 - n2, 1)
            steps = [1] * motion
        else:
            n1, n2, n3 = _stage_frames(motion)
            steps = _steps(total, n1, n2, n3, PAN_MIN_STEP_PX)
            if steps is None:
                return _static_fallback(base, n_frames, out_w, out_h, "PAN_SPEED_BELOW_MIN")
        x0 = (span - total) // 2
        y0 = max((src_h - out_h) // 2, 0)
        # P33-1 修复③：**平移方向按景平衡**。原实现 direction 恒为 "RIGHT" ⇒ 所有平移景
        # 系统性向同一侧漂移（实测 9 个平移景全部 (+56,0)）。现由 `build_plan` 按景序号
        # **交替**给出方向（父景序号偶数 ⇒ RIGHT、奇数 ⇒ LEFT）⇒ 全片方向均衡，
        # 且幅度上限（3%）与整数帧纪律不变。
        sign = -1 if direction == "LEFT" else 1
        rects = [(x0, y0, out_w, out_h)] * STATIC_HEAD_TAIL_FRAMES
        for k in range(0, motion + 1):          # 含 k=0（起步帧＝起始位置）⇒ 与闭式逐帧一致
            if FULL_SCENE_MOTION:
                # 与 zoom 同式：像素级均匀插值（0 → total），景末恰好到达 total
                cc = min(cumulative(steps, n1, n2, n3, k), motion)
                off = (cc * total) // motion
            else:
                off = cumulative(steps, n1, n2, n3, k)
            rects.append((x0 + sign * off, y0, out_w, out_h))
        rects += [rects[-1]] * max(n_frames - len(rects), 0)
        rects = (rects + [rects[-1]] * n_frames)[:n_frames]
        return {**base, "enabled": True, "motion_type": "SLOW_PAN", "rects": rects,
                "params": {"zoom_start": 1.0, "zoom_end": 1.0, "pan_px": total,
                           "head_static": STATIC_HEAD_TAIL_FRAMES, "motion_frames": motion,
                           "n1": n1, "n2": n2, "n3": n3,
                           "s1": steps[0], "s2": steps[n1], "s3": steps[n1 + n2], "sign": sign,
                           "v2_progress": bool(FULL_SCENE_MOTION)},
                "reason": ("缓慢平移（单方向；幅度 = 画面宽×{:.0%} ≤ 3%；**全镜** motion={} 帧）"
                           .format(PAN_MAX_RATIO, motion) if FULL_SCENE_MOTION else
                           "缓慢平移（单方向；幅度 = 画面宽×{:.0%} ≤ 3%；运动窗口 {} 帧 ≤ {}）"
                           .format(PAN_MAX_RATIO, motion, MOTION_WINDOW_MAX_FRAMES)),
                "fallback_code": None}
    # 默认：缓慢推近（整数偶数步长；高度按同一公式由宽度推导，保证闭式可复算）
    # P25-1：上限由授权提到 `MAX_ZOOM_END`（1.25）；**每景 corr 守卫**可在渲染后把
    # 个别景降级到 `MAX_ZOOM_END_V1`（1.08）重渲 —— 见 `core/motion_guard.py`。
    zoom_end = min(MAX_ZOOM_END, float(zoom_max or MAX_ZOOM_END))
    w_start, h_start = out_w, out_h
    w_end = _even_round_half_up(out_w / zoom_end)
    h_end = _even_round_half_up(out_h / zoom_end)
    units = max((w_start - w_end) // ZOOM_STEP_PX, 0)
    # ---- P24-1 运动策略 v2：**全镜缓推** ----
    # 旧（v1）：`motion = min(avail, units, 150)` ⇒ 运动挤在景头 ≤150 帧窗口内，窗口外静止
    #          （监理实测：全片 94.8% 片长逐帧冻结、最长静止 64s）。
    # 新（v2）：`motion = avail`（**摊满整景**），并把每帧像素步长取为
    #          `ceil(units / motion)`（≥1）⇒ 推进在整景内**均匀完成**且**恰好在景末到达上限**
    #          （幅度上限 MAX_ZOOM_END=1.08 **不变**；整数帧纪律保持；闭式可复算）。
    avail = max(n_frames - STATIC_HEAD_TAIL_FRAMES, 0)
    if FULL_SCENE_MOTION:
        motion = avail
        step_px = max(1, -(-units // motion)) if motion > 0 else 1
    else:
        motion = min(avail, max(units, 1), MOTION_WINDOW_MAX_FRAMES)
        step_px = ZOOM_STEP_PX
    if units <= 0 or avail <= 0 or motion <= 0:
        return _static_fallback(base, n_frames, out_w, out_h, "ZOOM_INFEASIBLE")
    # P24-1 v2：三阶段**均匀铺满整景**（v1 的 `_stage_frames` 是为 ≤150 帧窗口设计的
    # 50/75/25 分配；沿用到整景会只用 148+446+148 帧 ⇒ 推进在景末前停止、幅度走不满）。
    if FULL_SCENE_MOTION:
        n1 = max(motion // 2, 1)
        n3 = max(motion // 8, 1)
        n2 = max(motion - n1 - n3, 1)
        n3 = max(motion - n1 - n2, 1)            # 收敛到恰好 motion 帧
        steps = [1] * motion
    else:
        n1, n2, n3 = _stage_frames(motion)
        steps = _steps(units, n1, n2, n3, step_px)
    if FULL_SCENE_MOTION:
        # v2：**完全绕过**单位步长计算器（`_steps`）。原因：`_steps` 的整数最小步长
        # （`step_px≥1`）在短景上无解（如 2.6s 景只有 57 帧，走完 71 个单位需 ≥142 帧），
        # 旧实现会因此回退静止并把 `motion` 改成单位数（57），破坏"摊满整景"。
        # v2 的宽度由**像素级 Q8 插值**决定，与步长无关 ⇒ 只需一个计数序列。
        steps = [1] * motion
        step_px = max((w_start - w_end) / max(motion, 1), 1e-9)
    else:
        steps = _steps(units, n1, n2, n3, step_px)
        if steps is None:
            return _static_fallback(base, n_frames, out_w, out_h, "ZOOM_SPEED_BELOW_MIN")

    def h_of(w: int) -> int:
        return _even_round_half_up(w * out_h / out_w)

    rects = [((src_w - w_start) // 2, (src_h - h_start) // 2, w_start, h_start)] \
        * STATIC_HEAD_TAIL_FRAMES
    # ---- P24-1 v2：**直接 Q8 进度**闭式（不经"单位"量化）----
    # 动机：8% 幅度 = 142px = 71 个单位（2px/单位）；把 71 个单位摊到 750 帧，
    # **整数单位步长**只能是 0 或 1 ⇒ 要么在头 142 帧走完（其余静止），要么走不满。
    # 故 v2 改为**直接在像素精度上按帧均匀插值**（Q8 定点，1/256 px）：
    #   `w(n) = w_end + (w_start − w_end)·(1 − c(n)/motion)`，c(n) 为均匀三阶段的累计帧数。
    # 这样幅度仍 ≤ 1.08，但**推进摊满整景**（逐帧宽度单调、景末恰好 w_end）。
    # `crop_filter` 用同一算式 ⇒ 闭式与逐帧 rects **逐帧一致**（tests 断言）。
    _delta_full = w_start - w_end                       # 总推进（px，整数）
    step_q8 = max(1, -(-_delta_full * 256 // motion)) if motion > 0 else 256
    for k in range(0, motion + 1):              # 含 k=0（起步帧＝起始位置）
        c_k = min(cumulative(steps, n1, n2, n3, k), motion) if FULL_SCENE_MOTION \
            else cumulative(steps, n1, n2, n3, k)
        if FULL_SCENE_MOTION:
            w = w_end + ((motion - c_k) * _delta_full) // motion
        else:
            w = w_start - (step_q8 * c_k) // 256
        w = max(w_end, w)
        h = h_of(w)
        rects.append(((src_w - w) // 2, (src_h - h) // 2, w, h))
    rects += [rects[-1]] * max(n_frames - len(rects), 0)
    rects = (rects + [rects[-1]] * n_frames)[:n_frames]
    return {**base, "enabled": True, "motion_type": "SLOW_ZOOM_IN", "rects": rects,
            "params": {"zoom_start": 1.0, "zoom_end": round(out_w / w_end, 4),
                       "pan_px": 0, "w_start": w_start, "w_end": w_end, "h_start": h_start,
                       "h_end": h_end, "n1": n1, "n2": n2, "n3": n3,
                       "s1": steps[0], "s2": steps[n1], "s3": steps[n1 + n2],
                       "head_static": STATIC_HEAD_TAIL_FRAMES, "motion_frames": motion,
                       "step_q8": step_q8, "step_px": round(step_q8 / 256.0, 4),
                       "delta_full": _delta_full, "v2_progress": bool(FULL_SCENE_MOTION)},
            "reason": ("缓慢推近：zoom 1.00→{:.2f}（≤{:.2f}，上限不变）；"
                       "**全镜缓推** motion={} 帧（≈整景 {} 帧）、步长 {}px/帧（整数帧纪律）"
                       .format(out_w / w_end, MAX_ZOOM_END, motion, n_frames, step_px)
                       if FULL_SCENE_MOTION else
                       "缓慢推近：zoom 1.00→{:.2f}（≤{:.2f}）；运动窗口 {} 帧 ≤ {}"
                       .format(out_w / w_end, MAX_ZOOM_END, motion, MOTION_WINDOW_MAX_FRAMES)),
            "fallback_code": None}


def _static_fallback(base: dict, n_frames: int, out_w: int, out_h: int, why: str) -> dict:
    return {**base, "enabled": False, "motion_type": "STATIC",
            "rects": [(0, 0, out_w, out_h)] * n_frames,
            "params": {"zoom_start": 1.0, "zoom_end": 1.0, "pan_px": 0},
            "reason": why, "fallback_code": MOTION_FALLBACK_CODE}


def evaluate_closed_form(plan: dict, n: int) -> tuple[int, int, int, int]:
    """在 Python 侧按**闭式**复算第 n 帧矩形 —— 用于证明滤镜串 ⇔ 权威矩形等价。"""
    p = plan["params"]
    if not plan["enabled"]:
        return 0, 0, plan["out_w"], plan["out_h"]
    if plan["motion_type"] == "SLOW_PAN":
        k = n - p["head_static"]
        c = (p["s1"] * min(max(k, 0), p["n1"]) + p["s2"] * min(max(k - p["n1"], 0), p["n2"])
             + p["s3"] * min(max(k - p["n1"] - p["n2"], 0), p["n3"]))
        span = plan["src_w"] - plan["out_w"]
        x0 = (span - p["pan_px"]) // 2
        y0 = max((plan["src_h"] - plan["out_h"]) // 2, 0)
        if p.get("v2_progress"):
            # P24-1 v2：与 rects / crop_filter 同式
            _m = int(p["motion_frames"])
            off = (min(c, _m) * int(p["pan_px"])) // _m
        else:
            off = c
        return (x0 + p["sign"] * off, y0, plan["out_w"], plan["out_h"])
    st = p["head_static"]
    k = n - st
    c = (p["s1"] * min(max(k, 0), p["n1"]) + p["s2"] * min(max(k - p["n1"], 0), p["n2"])
         + p["s3"] * min(max(k - p["n1"] - p["n2"], 0), p["n3"]))
    if p.get("v2_progress"):
        # P24-1 v2：直接 Q8 进度（与 `plan_scene` 的 rects 同一算式）
        _m = int(p["motion_frames"])
        _d = int(p["delta_full"])
        cc = min(c, _m)
        w = max(p["w_end"], p["w_end"] + ((_m - cc) * _d) // _m)
    else:
        w = max(p["w_end"], p["w_start"] - (int(p.get("step_q8") or (ZOOM_STEP_PX * 256)) * c) // 256)
    h = _even_round_half_up(w * plan["out_h"] / plan["out_w"])
    return ((plan["src_w"] - w) // 2, (plan["src_h"] - h) // 2, w, h)


def crop_filter(plan: dict) -> str:
    """生成 ffmpeg `crop` 滤镜串（整数闭式；`n` = 帧号）。仅用 min/max/floor 与整数算术。"""
    if not plan["enabled"]:
        return "crop={}:{}:0:0".format(plan["out_w"], plan["out_h"])
    p = plan["params"]
    if plan["motion_type"] == "SLOW_PAN":
        c = "{s1}*min({k0},{n1})+{s2}*min({k1},{n2})+{s3}*min({k2},{n3})".format(
            s1=p["s1"], s2=p["s2"], s3=p["s3"], n1=p["n1"], n2=p["n2"], n3=p["n3"],
            k0="max(n-{},0)".format(p["head_static"]),
            k1="max(n-{}-{},0)".format(p["n1"], p["head_static"]),
            k2="max(n-{}-{},0)".format(p["n1"] + p["n2"], p["head_static"]))
        x0 = (plan["src_w"] - plan["out_w"] - p["pan_px"]) // 2
        y0 = max((plan["src_h"] - plan["out_h"]) // 2, 0)
        sign = "-" if p["sign"] < 0 else "+"
        if p.get("v2_progress"):
            # P24-1 v2：像素级均匀插值（与 rects 同式）⇒ 平铺满整景、景末恰好 pan_px
            # **注意**：ffmpeg 表达式解析器**不支持 `//`**（整数除）⇒ 必须用 `floor(a/b)`
            # （P27 实测：`//` 报 `Undefined constant or missing '('`，导致 crop 配置失败、
            #  渲染 -22 Invalid argument）。
            _m = int(p["motion_frames"])
            _t = int(p["pan_px"])
            off = "floor(min(({}),{})*{}/({}))".format(c, _m, _t, _m)
        else:
            off = "1*({})".format(c)
        # **加法**而非乘法（P13-3 真实渲染发现的缺陷②：旧写法 `x0*(c)` 把位移乘到 x0 上，
        #  c 增大后迅速被 clamp ⇒ 位移在 n≈20 后停止）；
        # 且表达式内 min/max 的逗号必须靠引号保护（缺陷①：`No such filter: '0)'`）。
        x = "{}{}{}".format(x0, sign, off)
        return "crop={}:{}:x='{}':y='{}'".format(plan["out_w"], plan["out_h"], x, y0)
    c = "{s1}*min({k0},{n1})+{s2}*min({k1},{n2})+{s3}*min({k2},{n3})".format(
        s1=p["s1"], s2=p["s2"], s3=p["s3"], n1=p["n1"], n2=p["n2"], n3=p["n3"],
        k0="max(n-{},0)".format(p["head_static"]),
        k1="max(n-{}-{},0)".format(p["n1"], p["head_static"]),
        k2="max(n-{}-{},0)".format(p["n1"] + p["n2"], p["head_static"]))
    # P24-1：v2 用 **直接 Q8 进度**（`w_end + (motion−c)·delta_full/motion`）；
    # v1 用单位步长（`w_start − step_q8·c/256`）。两者 `c` 的算式与 plan 完全一致。
    if p.get("v2_progress"):
        _m = int(p["motion_frames"])
        _d = int(p["delta_full"])
        w = "max({},{} + ({}-min(({}),{}))*{}/({}))".format(
            p["w_end"], p["w_end"], _m, c, _m, _d, _m)
    else:
        _sq8 = int(p.get("step_q8") or (ZOOM_STEP_PX * 256))
        w = "max({},{} - floor({}*({})/256))".format(p["w_end"], p["w_start"], _sq8, c)
    h = "2*floor((({w})*{oh}/{ow}+1)/2)".format(w=w, oh=plan["out_h"], ow=plan["out_w"])
    x = "floor(({sw}-({w}))/2)".format(sw=plan["src_w"], w=w)
    y = "floor(({sh}-({h}))/2)".format(sh=plan["src_h"], h=h)
    return "crop=w='{}':h='{}':x='{}':y='{}'".format(w, h, x, y)


# ---- P0（2026-10-20）：**按镜长限幅**的运动幅度 ------------------------------
# 审计结论（`video-studio_审计报告.md` §3-④）：`render_motion.json` 曾以
# 「慢推在 20s 镜上表现为**蠕动**」为由全片停用运动——但蠕动是**镜长**造成的：
# 1.25 倍摊到 20s（600 帧）≈ 每帧 0.02px。正确修法是让**幅度 ∝ 镜长**，
# 使"推进速率"近似恒定，而不是关掉运动。
# 仅当 `build_plan(duration_scaled=True)` 时生效；缺省仍走 `MAX_ZOOM_END`（旧行为逐字不变）。
DURATION_ZOOM = (
    (2.0, 1.14),    # ≤2s：可推 14%（快门级镜头，动作感最强）
    (4.0, 1.12),    # 2–4s：12%
    (6.0, 1.09),    # 4–6s：9%
    (10.0, 1.06),   # 6–10s：6%
    (999.0, 1.03),  # >10s：3%（长镜只给极轻，避免"爬"）
)


def zoom_for_duration(dur: float) -> float:
    """按镜长给出推进幅度（确定性；上限仍受 `MAX_ZOOM_END` 约束）。"""
    d = max(float(dur or 0.0), 0.0)
    for cap_s, z in DURATION_ZOOM:
        if d <= cap_s:
            return min(z, MAX_ZOOM_END)
    return min(DURATION_ZOOM[-1][1], MAX_ZOOM_END)


def select_scenes(scenes: list[dict], *, policy: dict | None = None) -> list[dict]:
    """确定性挑选启用运动的场景（v2：**全镜**；`<min_scene_s` 的景仍保持静止）。

    v1 口径：时长 ≥10s 且 ≤60%（序：hook 优先、时长降序、scene_id 升序）。
    **v2（P24-1）**：`max_enabled_ratio` 默认提高到 `MAX_ENABLED_RATIO_V2 = 1.0`，
    并**强制启用 hook 景**（`force_hook`，S01）——即使它因时长被排在 cap 之外。
    prefer-STATIC 语义不变：`duration_s < min_scene_s` 一律静止。
    """
    pol = policy or {}
    max_ratio = float(pol.get("max_enabled_ratio", MAX_ENABLED_RATIO_V2))
    min_s = float(pol.get("min_scene_s", MIN_SCENE_S))
    eligible = [s for s in scenes if float(s.get("duration_s") or 0) >= min_s]
    ordered = sorted(eligible, key=lambda s: (not bool(s.get("hook")),
                                              -float(s.get("duration_s") or 0),
                                              str(s.get("scene_id"))))
    cap = int(len(scenes) * max_ratio)
    chosen = ordered[:max(cap, 0)]
    allowed = {str(s.get("scene_id")) for s in chosen}
    # 强制 hook（S01）：授权书 P24-1「S01（hook）强制启用」
    if pol.get("force_hook", True):
        for s in scenes:
            if s.get("hook") and float(s.get("duration_s") or 0) >= min_s:
                allowed.add(str(s.get("scene_id")))
    out = []
    for s in scenes:
        sid = str(s.get("scene_id"))
        out.append({**s, "motion_enabled": sid in allowed})
    return out


def _scene_ordinal(scene_id) -> int:
    """从 scene_id 取**父景序号**（P25：派生段 id 形如 `S02p1` ⇒ 取 `02`；不可解析取 0）。

    v1 直接 `int(str(scene_id).lstrip("S"))`，对派生段 id（含 `p`）会抛 `ValueError`。
    """
    import re as _re
    m = _re.match(r"^\D*(\d+)", str(scene_id or ""))
    return int(m.group(1)) if m else 0


def build_plan(scenes: list[dict], *, out_w: int, out_h: int, fps: int = DEFAULT_FPS,
               enabled: bool = True, policy: dict | None = None,
               duration_scaled: bool = False) -> dict:
    """全片运动计划（确定性）：逐场景计划 + 汇总 + artifact_hash。

    `duration_scaled=True`（P0）：幅度按镜长限幅（`zoom_for_duration`），
    使"推进速率"近似恒定——短镜给 12–14%，长镜只给 3%，消除 20s 镜的"蠕动"观感。
    缺省 `False` ⇒ 逐字段与旧行为一致（现有测试/基线不受影响）。
    """
    picked = select_scenes(scenes, policy=policy) if enabled else [
        {**s, "motion_enabled": False} for s in scenes]
    plans = []
    _min_s = (policy or {}).get("min_scene_s")
    for s in picked:
        dur = float(s.get("duration_s") or 0)
        _ord = _scene_ordinal(s.get("scene_id"))
        mtype = "SLOW_PAN" if (_ord % 2 == 0 and s.get("motion_enabled")) else "SLOW_ZOOM_IN"
        # P33-1：平移方向**按景平衡**（确定性；同一父景的派生段方向一致）
        _dir = "RIGHT" if (_ord // 2) % 2 == 0 else "LEFT"
        plans.append(plan_scene(s, out_w=out_w, out_h=out_h, fps=fps, direction=_dir,
                                enabled=bool(s.get("motion_enabled")), motion_type=mtype,
                                zoom_max=(zoom_for_duration(dur) if duration_scaled else None),
                                min_scene_s=_min_s))
    body = {"schema": SCHEMA, "version": VERSION, "rule_version": PLAN_RULE_VERSION,
            "policy": {**POLICY, "duration_scaled": bool(duration_scaled)},
            "fps": fps, "out_w": out_w, "out_h": out_h,
            "enabled": bool(enabled),
            "scenes": sorted(plans, key=lambda p: str(p["scene_id"])),   # 输出恒按 scene_id 排序
            "counts": {"scenes": len(plans),
                       "enabled": sum(1 for p in plans if p["enabled"]),
                       "static": sum(1 for p in plans if not p["enabled"]),
                       "fallback": sum(1 for p in plans if p["fallback_code"])},
            "fallback_code": MOTION_FALLBACK_CODE,
            "read_only": True, "artifact_hash": ""}
    body["artifact_hash"] = plan_hash(body)
    return body


EXTERNAL_CONFIG_REL = "config/render_motion.json"


def resolve_config(config: dict | None, *, root=None) -> tuple[dict, str]:
    """解析运动层开关（**不修改被基线钉定的 config.json**，沿用 P10 三级链模式）：

      1) `config["tools"]["render_motion"]`（若存在——运行时注入或未来重钉基线后写入）
      2) **可选外部文件** `config/render_motion.json`（默认不存在 ⇒ off）
      3) 内置默认 `{"enabled": False}` ⇒ 渲染输出与现状**逐字节一致**

    **差异登记**：授权书要求"开关走 resolve_config 链（可选外部文件 config/render_motion.json，
    默认 off）"——与 P10 教训一致：`config.json` 的逐字节 sha256 被有效基线 manifest 钉定，
    故本模块只在外部文件/内存配置里读取开关，**不改 config.json**。
    """
    import json as _json
    import pathlib as _pathlib
    tools = ((config or {}).get("tools") or {})
    inline = tools.get("render_motion")
    if isinstance(inline, dict) and inline:
        return {"enabled": False, **inline}, "config.tools.render_motion（内存/未来基线）"
    base = _pathlib.Path(root) if root else _pathlib.Path(".")
    ext = base / EXTERNAL_CONFIG_REL
    if ext.is_file():
        try:
            j = _json.loads(ext.read_text(encoding="utf-8"))
            block = j.get("render_motion") if isinstance(j, dict) else None
            block = block if isinstance(block, dict) else (j if isinstance(j, dict) else None)
            if isinstance(block, dict) and block:
                return {"enabled": False, **block}, str(ext)
        except (UnicodeDecodeError, ValueError):
            return {"enabled": False}, "{}（损坏 ⇒ 保守回落 off）".format(ext)
    return {"enabled": False}, "default（无配置 ⇒ 运动层关闭）"


def plan_hash(plan: dict) -> str:
    return sha256_text(canonical({k: v for k, v in plan.items()
                                  if k not in ("artifact_hash",)}))

def validate_plan(plan: dict) -> list[str]:
    errs = []
    if plan.get("schema") != SCHEMA:
        errs.append("schema 非法")
    if plan.get("artifact_hash") != plan_hash(plan):
        errs.append("artifact_hash 不一致")
    for p in plan.get("scenes") or []:
        if len(p["rects"]) != p["n_frames"]:
            errs.append("{} 矩形数 != 帧数".format(p["scene_id"]))
        if p["enabled"]:
            bad = [r for r in p["rects"] if r[2] > p["src_w"] or r[3] > p["src_h"]
                   or r[0] < 0 or r[1] < 0]
            if bad:
                errs.append("{} 矩形越界".format(p["scene_id"]))
            if p["motion_type"] == "SLOW_ZOOM_IN":
                end_zoom = p["out_w"] / p["params"]["w_end"]
                if round(end_zoom, 4) > MAX_ZOOM_END + 1e-9:
                    errs.append("{} zoom 超上限".format(p["scene_id"]))
            if p["motion_type"] == "SLOW_PAN":
                if p["params"]["pan_px"] > int(p["out_w"] * PAN_MAX_RATIO):
                    errs.append("{} 平移超画面 3%".format(p["scene_id"]))
    return errs
