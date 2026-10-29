# -*- coding: utf-8 -*-
"""P0（2026-10-20）：**镜头细分**（display-level shot list）。

根因（`video-studio_审计报告.md` §3-①）：timeline 的 `scene` 是**章节**而不是镜头——
实测 63.7s 成片只有 3 个 scene（19.2 / 20.4 / 24.1s），697s 成片 36 个（19.4s/镜）。
观众要盯着同一画面 20 秒，切点还落在动画内部，于是成片"像 AI 拼接"。

本模块是**纯函数**：把每个 scene 按**字幕句界**切成 `max_shot_s` 以内的 shot，
每条 shot 带

* `src_in_s`：同一素材内的入点（视频条按此 `-ss` 前进；静态图忽略）；
* `reframe`：确定性取景缩放（1.00/1.06/1.02/1.10…）——同素材连续切镜时，
  取景逐镜变化，切点才"看得见"；
* `scene_id = "<父景>#<序号>"`、`parent_scene_id`：便于证据追溯；
* 其余字段（`selected_asset`/`hook`/`fallback_state`…）**原样继承**，装配与核验不需要改语义。

不变量（与既有链路兼容）
* `Σ shot 时长 == Σ scene 时长`（总时长契约不变，字幕/淡入淡出/响度链不受影响）；
* 素材归属不变（不换素材、不伪造候选）⇒ 抽帧核验仍按父景窗口成立；
* 无 cue 时的兜底：按 `max_shot_s` **等分**（确定性，无随机）。
"""
from __future__ import annotations

import math

#: 取景序列（确定性循环）：1.00 为原构图，其余为轻微推进（punch-in）
REFRAME_SEQ = (1.00, 1.06, 1.02, 1.10, 1.04, 1.08)

MAX_SHOT_S = 4.0
MIN_SHOT_S = 1.2
#: 视频入点的安全余量（s）：`-ss` 必须落在流内才能取到帧
SRC_MARGIN_S = 0.2


def clamp_src_t(src_in: float, asset_dur: float | None) -> float:
    """把素材内入点夹到 `[0, dur − SRC_MARGIN_S]`（装配侧与核验侧必须**同一函数**）。"""
    x = max(float(src_in or 0.0), 0.0)
    if asset_dur and float(asset_dur) > 0:
        x = min(x, max(float(asset_dur) - SRC_MARGIN_S, 0.0))
    return round(x, 3)
#: 场景已经短于 `max_shot_s × 此系数` ⇒ 不切（避免 4.1s 切成 0.1s + 4.0s）
NO_SPLIT_RATIO = 1.25


def _bounds_from_cues(cues) -> list[float]:
    """切点候选 = **cue 起点**（新一句开始处）。

    P0 修正：原先同时取 cue 的 `start` 与 `end`，实测会切在"一句话刚说完、
    卡内正在换层"的瞬间 ⇒ 成片出现两张卡叠在一起的过渡帧。只取 `start`
    可让切点与"新一句开始/卡内换层"基本对齐。
    """
    out: list[float] = []
    for c in (cues or []):
        try:
            out.append(round(float(c["start"]), 3))
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(set(out))


def _pick_cuts(lo: float, hi: float, n: int, bounds: list[float],
               min_shot_s: float) -> list[float]:
    """从 cue 边界里挑 n-1 个切点，靠近等分位置且相邻间隔 ≥ min_shot_s。"""
    dur = hi - lo
    if n <= 1 or dur <= 0:
        return []
    ideal = [lo + dur * i / n for i in range(1, n)]
    cand = [b for b in bounds if lo + min_shot_s <= b <= hi - min_shot_s]
    chosen: list[float] = []
    for t in ideal:
        pool = [b for b in cand
                if b not in chosen and b > lo + min_shot_s and b < hi - min_shot_s
                and all(abs(b - c) >= min_shot_s for c in chosen)]
        if not pool:
            continue
        near = min(pool, key=lambda x: abs(x - t))
        chosen.append(near)
    chosen.sort()
    # 尾部/头部过短 ⇒ 丢掉最近的切点（宁少切一刀，不留碎镜）
    while chosen and (chosen[0] - lo < min_shot_s or hi - chosen[-1] < min_shot_s):
        if chosen[0] - lo < min_shot_s:
            chosen.pop(0)
        else:
            chosen.pop()
    # 相邻过近 ⇒ 丢掉后一个
    kept: list[float] = []
    for c in chosen:
        if not kept or c - kept[-1] >= min_shot_s:
            kept.append(c)
    return kept


def plan_shots(timeline, cues=None, *, max_shot_s: float = MAX_SHOT_S,
               min_shot_s: float = MIN_SHOT_S, asset_dur: dict | None = None) -> list[dict]:
    """把 timeline 的 scene 细分成 shot 列表（保序、总时长不变、字段继承）。

    `asset_dur`：视频素材时长表 `{path: duration}`（可含 None）。仅用于记录；
    **不再据此禁止细分**——末段入点由装配侧与核验侧共用 `clamp_src_t` 统一夹紧。
    """
    max_shot_s = float(max_shot_s or 0)
    min_shot_s = max(float(min_shot_s or 0), 0.4)
    if max_shot_s <= 0:
        return [dict(s) for s in (timeline or [])]
    bounds = _bounds_from_cues(cues)
    out: list[dict] = []
    gi = 0
    for sc in (timeline or []):
        try:
            lo = round(float(sc["start_s"]), 3)
            hi = round(float(sc["end_s"]), 3)
        except (KeyError, TypeError, ValueError):
            out.append(dict(sc))
            continue
        dur = round(hi - lo, 3)
        if dur <= 0:
            out.append(dict(sc))
            continue
        # P0 守卫：**视频素材短于景**时不切。
        # 取舍：素材不足以覆盖景时，末段只能"定格"或"重播尾段"；
        # 抽帧核验按「源 t = 输出 t − 景起点」取参照帧，重播/夹紧会让该等式失效
        # （实测 p58 T3a/T4b 变红）。保留旧语义（一景一镜 + 尾段定格），
        # 把"补素材或允许尾段重播"记为 P1。
        # `asset_dur` 的键集 = 视频素材；值为 None（探测失败）⇒ 同样不切（保守）。
        _is_vid = False
        _ad = None
        if asset_dur:
            _p = str((sc.get("selected_asset") or {}).get("path") or "")
            _is_vid = _p in asset_dur
            _ad = asset_dur.get(_p)
        if _is_vid and (_ad is None or float(_ad) < dur - 0.05):
            n = 1
        elif dur <= max_shot_s * NO_SPLIT_RATIO:
            n = 1
        else:
            n = max(2, int(math.ceil(dur / max_shot_s - 1e-9)))
        cuts = _pick_cuts(lo, hi, n, bounds, min_shot_s) if n > 1 else []
        # 等分兜底：没有可用句界（或切点太少）时补足到 ≤max_shot_s
        if n > 1 and len(cuts) < n - 1:
            need = n - 1
            grid = [round(lo + dur * (i + 1) / (need + 1), 3) for i in range(need)]
            merged = sorted(set([round(c, 3) for c in cuts] + grid))
            keep: list[float] = []
            for c in merged:
                if lo + min_shot_s <= c <= hi - min_shot_s and (
                        not keep or c - keep[-1] >= min_shot_s):
                    keep.append(c)
            while len(keep) > need:
                keep.pop()
            cuts = keep
        points = [lo] + cuts + [hi]
        for k in range(len(points) - 1):
            s0, e0 = points[k], points[k + 1]
            d = round(e0 - s0, 3)
            if d <= 0:
                continue
            shot = dict(sc)                     # 继承 selected_asset / hook / fallback…
            shot.update({
                "scene_id": "{}#{}".format(sc.get("scene_id"), k),
                "parent_scene_id": sc.get("scene_id"),
                "start_s": s0, "end_s": e0, "duration_s": d,
                "src_in_s": round(s0 - lo, 3),  # 同素材内入点
                "reframe": REFRAME_SEQ[gi % len(REFRAME_SEQ)],
                "shot_index": k, "shot_total": len(points) - 1,
                "shot_rule": "p0-display-shot-v1",
            })
            out.append(shot)
            gi += 1
    return out


