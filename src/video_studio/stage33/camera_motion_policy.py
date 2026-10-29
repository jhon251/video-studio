"""camera_motion_policy (Stage 12.2): asset_type + visual_intent + focus -> motion.

Decides, per shot, what camera motion to apply and WHY, reusing stage33/motion.py
(plan_hold / plan_pan / plan_zoom). No new motion engine. No CV model.

Core principle: prefer STATIC over meaningless motion. Every non-STATIC motion
must carry a direction reason; if no visual reason exists -> STATIC (plan_hold).

Inputs: asset_type (from Stage 11 contract), visual_intent (Stage 12.1),
        optional focus hint (center/top/bottom/left/right or None).
Outputs trace: motion_type, motion_direction, start_scale, end_scale,
               focus_point, motion_reason.

Never re-judges material quality (that's Stage 12.1 gate's job). Never rescues
a gate-rejected asset.
"""
from __future__ import annotations

from video_studio.stage33 import motion as motion_lib


def decide_motion(asset_type: str, visual_intent: str, focus: str | None = None,
                  time_period: str = "") -> dict:
    """Return motion decision (deterministic, no CV)."""
    intent_l = (visual_intent or "").lower()
    asset = (asset_type or "").upper()

    # --- future/cinematic signal from intent + period ---
    future_signal = ("future" in time_period.lower()) or any(
        k in intent_l for k in ("未来", "future", "futuristic", "城市天际线", "cinematic"))
    hist_signal = ("historical" in time_period.lower()) or any(
        k in intent_l for k in ("历史", "1956", "工业革命", "archive", "historical"))
    city_signal = any(k in intent_l for k in ("城市", "city", "天际线", "基础设施", "infrastructure"))
    person_signal = any(k in intent_l for k in ("人物", "人群", "员工", "学者", "人类", "people", "office"))
    map_signal = any(k in intent_l for k in ("地图", "map", "区域", "region", "分布", "航线"))
    chart_signal = any(k in intent_l for k in ("图表", "chart", "数据", "data", "趋势", "统计"))

    if asset == "VIDEO":
        return {"motion_type": "SOURCE_NATIVE", "motion_direction": None,
                "start_scale": 1.0, "end_scale": 1.0, "focus_point": None,
                "motion_reason": "video asset: keep native motion (no camera transform)"}

    if asset == "DOCUMENT" or asset == "VECTOR":
        # document/chart: detail zoom or STATIC; no drifting
        if asset == "VECTOR" and chart_signal:
            return {"motion_type": "SLOW_ZOOM_IN", "motion_direction": None,
                    "start_scale": 1.0, "end_scale": 1.06, "focus_point": "center",
                    "motion_reason": "chart/data: slow zoom to detail focus"}
        if asset == "VECTOR" and map_signal:
            return {"motion_type": "SLOW_PAN", "motion_direction": "RIGHT",
                    "start_scale": 1.0, "end_scale": 1.0, "focus_point": "center",
                    "motion_reason": "map: left-to-right region scan"}
        if focus:
            return {"motion_type": "SLOW_ZOOM_IN", "motion_direction": None,
                    "start_scale": 1.0, "end_scale": 1.08, "focus_point": focus,
                    "motion_reason": f"document detail focus at {focus}"}
        return {"motion_type": "STATIC", "motion_direction": None,
                "start_scale": 1.0, "end_scale": 1.0, "focus_point": None,
                "motion_reason": "document/chart without clear focus -> static hold"}

    if asset == "IMAGE":
        # map intent -> region pan
        if map_signal:
            return {"motion_type": "SLOW_PAN", "motion_direction": "RIGHT",
                    "start_scale": 1.0, "end_scale": 1.0, "focus_point": "center",
                    "motion_reason": "map image: left-to-right region scan"}
        # future + city -> slow cinematic pan (with reason)
        if future_signal and city_signal:
            return {"motion_type": "SLOW_PAN", "motion_direction": "RIGHT",
                    "start_scale": 1.0, "end_scale": 1.0, "focus_point": "center",
                    "motion_reason": "future city cinematic: slow left-to-right read (skyline)"}
        if city_signal and not future_signal and not hist_signal:
            return {"motion_type": "SLOW_ZOOM_IN", "motion_direction": None,
                    "start_scale": 1.0, "end_scale": 1.06, "focus_point": "center",
                    "motion_reason": "city scene: subtle center zoom to subject"}
        if person_signal:
            return {"motion_type": "SLOW_ZOOM_IN", "motion_direction": None,
                    "start_scale": 1.0, "end_scale": 1.08, "focus_point": "center",
                    "motion_reason": "person/office scene: slow zoom-in on subject"}
        if hist_signal:
            return {"motion_type": "STATIC", "motion_direction": None,
                    "start_scale": 1.0, "end_scale": 1.0, "focus_point": None,
                    "motion_reason": "historical scene: static hold (respect archive)"}
        # ordinary photo -> subtle zoom; if unsure -> STATIC
        return {"motion_type": "SUBTLE_ZOOM", "motion_direction": None,
                "start_scale": 1.0, "end_scale": 1.04, "focus_point": "center",
                "motion_reason": "ordinary photo: subtle zoom"}

    # unknown -> STATIC
    return {"motion_type": "STATIC", "motion_direction": None,
            "start_scale": 1.0, "end_scale": 1.0, "focus_point": None,
            "motion_reason": "unknown asset type -> static (no motion reason)"}


def build_rects(decision: dict, n_frames: int, src_w: int, src_h: int,
                out_w: int, out_h: int) -> list | None:
    """Map decision -> motion.py trajectory. Returns None -> HOLD (caller)."""
    mt = decision["motion_type"]
    if mt in ("STATIC", "SOURCE_NATIVE"):
        return motion_lib.plan_hold(n_frames, (src_w - out_w) // 2 if src_w > out_w else 0,
                                    (src_h - out_h) // 2 if src_h > out_h else 0,
                                    min(out_w, src_w), min(out_h, src_h))
    if mt == "SLOW_ZOOM_IN":
        ratio = (decision["end_scale"] - decision["start_scale"]) or 0.06
        rects = motion_lib.plan_zoom(n_frames, src_w, src_h, out_w, out_h,
                                     zoom_in=True, ratio=max(ratio, 0.04),
                                     anchor="center")
        return rects
    if mt == "SLOW_PAN":
        direction = {"RIGHT": "RIGHT", "LEFT": "LEFT"}.get(decision["motion_direction"], "RIGHT")
        rects = motion_lib.plan_pan(n_frames, src_w, src_h, out_w, out_h,
                                    direction=direction, ratio=0.08)
        return rects
    if mt == "SUBTLE_ZOOM":
        rects = motion_lib.plan_zoom(n_frames, src_w, src_h, out_w, out_h,
                                     zoom_in=True, ratio=0.04, anchor="center")
        return rects
    return motion_lib.plan_hold(n_frames, 0, 0, min(out_w, src_w), min(out_h, src_h))
