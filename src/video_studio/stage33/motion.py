"""motion：整数帧运动轨迹生成（废除 zoompan / 正弦 / 亚像素浮点）。

铁律：
- HOLD = 同一矩形重复（帧差恒为 0）；
- 运动 = 恒定整数步长（平移 ≥1px/帧；缩放偶数步长 2px/帧），三段缓动（加速/匀速/减速）；
- 轨迹单调、无 0↔1 交替、无方向反转；
- 幅度低于可感知下限或速度低于最小速度 → 返回 None（调用方降级 HOLD 并留痕）。
"""
from __future__ import annotations


def frame_range(start: float, end: float, fps: int = 25) -> int:
    """绝对时间边界 → 帧数（确定性、无 per-beat 截断漂移）。

    n = round(end*fps) - round(start*fps)。
    时间轴相邻 beat（end_i == start_{i+1}）的帧区间严格连续：无 gap、无 overlap；
    首帧=round(start*fps)，总帧数=round(timeline_end*fps)，全片无累积漂移。
    """
    return max(round(end * fps) - round(start * fps), 1)


def _stage_frames(motion_frames: int) -> tuple[int, int, int]:
    """三段缓动帧数分配：加速 20% / 匀速 60% / 减速 20%（整数）。"""
    n1 = max(1, round(motion_frames * 0.2))
    n3 = max(1, round(motion_frames * 0.2))
    n2 = max(1, motion_frames - n1 - n3)
    return n1, n2, n3


def _speed_steps(total: int, n1: int, n2: int, n3: int, min_speed: int) -> list[int] | None:
    """把总位移 total 按三段恒定步长分配；步长单调（先小后大再小）且 ≥min_speed。

    返回每帧步长列表（长度 n1+n2+n3）。若平均速度 < min_speed → None（→HOLD）。
    """
    n = n1 + n2 + n3
    if n <= 0:
        return None
    avg = total / n
    if avg < min_speed:
        return None
    s2 = max(min_speed, round(avg))
    s1 = max(min_speed, s2 // 2)
    s3 = max(min_speed, s2 // 2)
    covered = s1 * n1 + s2 * n2 + s3 * n3
    # 余数并入匀速段（恒定步长原则下，把余数拆成若干 +1 步）
    steps = [s1] * n1 + [s2] * n2 + [s3] * n3
    diff = total - covered
    if diff > 0:
        # 在匀速段均匀加 1px（误差扩散，仍无 0/1 交替——只在原步长上加 1）
        for i in range(diff):
            steps[n1 + (i % n2)] += 1
    elif diff < 0:
        # 需要减量：从最大步长段逐步减 1（保持 ≥min_speed）
        for _ in range(-diff):
            idx = max(range(len(steps)), key=lambda i: steps[i])
            if steps[idx] > min_speed:
                steps[idx] -= 1
            else:
                break
    return steps


def plan_hold(n_frames: int, x: int, y: int, w: int, h: int) -> list[tuple[int, int, int, int]]:
    return [(x, y, w, h)] * n_frames


def plan_pan(n_frames: int, src_w: int, src_h: int, out_w: int, out_h: int,
             direction: str, ratio: float,
             static_frames: int = 8) -> list[tuple[int, int, int, int]] | None:
    """水平/垂直平移。速度 ≥1px/帧、恒定步长、头尾静止。不可行 → None。"""
    motion = n_frames - 2 * static_frames
    if motion <= 0:
        return None
    span = src_w - out_w if direction in ("LEFT", "RIGHT") else src_h - out_h
    if span <= 0:
        return None
    total = int(span * ratio)
    n1, n2, n3 = _stage_frames(motion)
    steps = _speed_steps(total, n1, n2, n3, min_speed=1)
    if steps is None or sum(steps) == 0:
        return None
    # 起终点（余量由 span-total 平分到两端静止段位置）
    if direction in ("LEFT", "RIGHT"):
        x0 = (span - total) // 2
        y0 = (src_h - out_h) // 2
        sign = 1 if direction == "RIGHT" else -1
        rects = [(x0, y0, out_w, out_h)] * static_frames
        cx = x0
        for s in steps:
            cx += s * sign
            rects.append((cx, y0, out_w, out_h))
        rects += [(cx, y0, out_w, out_h)] * static_frames
    else:
        x0 = (src_w - out_w) // 2
        y0 = (span - total) // 2
        sign = 1 if direction == "DOWN" else -1
        rects = [(x0, y0, out_w, out_h)] * static_frames
        cy = y0
        for s in steps:
            cy += s * sign
            rects.append((x0, cy, out_w, out_h))
        rects += [(x0, cy, out_w, out_h)] * static_frames
    if len(rects) != n_frames:
        rects = (rects + [rects[-1]] * n_frames)[:n_frames]
    return rects


def plan_zoom(n_frames: int, src_w: int, src_h: int, out_w: int, out_h: int,
              zoom_in: bool, ratio: float, anchor: str = "center",
              static_frames: int = 8) -> list[tuple[int, int, int, int]] | None:
    """整数帧缩放：裁剪尺寸按偶数步长（2px/帧）单调变化；锚点固定。不可行 → None。"""
    motion = n_frames - 2 * static_frames
    if motion <= 0:
        return None
    total = int(min(src_w, src_h) * ratio)
    if total < 4:  # 最小 4px（2 帧 × 2px）
        return None
    w0, h0 = out_w, out_h
    # 起终点尺寸
    if zoom_in:
        w_end, h_end = max(out_w - total, out_w // 2), max(out_h - total, out_h // 2)
    else:
        w_end, h_end = min(out_w + total, src_w), min(out_h + total, src_h)
    dw = w_end - w0  # zoom_in: 负
    # 偶数步长分配（每次 2px）
    units = abs(dw) // 2
    if units <= 0:
        return None
    n1, n2, n3 = _stage_frames(motion)
    u_steps = _speed_steps(units, n1, n2, n3, min_speed=1)
    if u_steps is None or sum(u_steps) == 0:
        return None

    def anchor_xy(w: int, h: int) -> tuple[int, int]:
        ax = {"left": 0.0, "center": 0.5, "right": 1.0}.get(
            anchor.split("-")[1] if "-" in anchor else "center", 0.5)
        ay = {"top": 0.0, "center": 0.5, "bottom": 1.0}.get(
            anchor.split("-")[0] if "-" in anchor else "center", 0.5)
        return (int((src_w - w) * ax), int((src_h - h) * ay))

    x0, y0 = anchor_xy(w0, h0)
    rects = [(x0, y0, w0, h0)] * static_frames
    w, h = w0, h0
    sign = 1 if dw >= 0 else -1
    for u in u_steps:
        delta = 2 * u * sign
        w += delta
        h += int(round(delta * (h0 / w0)))
        w = max(out_w // 2, min(w, src_w))
        h = max(out_h // 2, min(h, src_h))
        x, y = anchor_xy(w, h)
        rects.append((x, y, w, h))
    rects += [rects[-1]] * static_frames
    if len(rects) != n_frames:
        rects = (rects + [rects[-1]] * n_frames)[:n_frames]
    return rects


def alpha_ramp(n_frames: int, a0: int, a1: int) -> list[int]:
    """透明度单调整数渐变（误差扩散，无抖动）。a0/a1 ∈ [0,255]；首帧=a0，末帧=a1。"""
    if n_frames <= 1:
        return [a1] * n_frames
    d = a1 - a0
    m = n_frames - 1
    steps = [d // m] * m
    rem = d - sum(steps)
    for i in range(abs(rem)):
        steps[i] += 1 if rem > 0 else -1
    vals, cur = [a0], a0
    for s in steps:
        cur = max(0, min(255, cur + s))
        vals.append(cur)
    vals[-1] = a1
    return vals
