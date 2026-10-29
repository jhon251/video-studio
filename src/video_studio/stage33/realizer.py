"""realizer（v3-mvp）：Visual Statement → 可执行帧规格（模板只存在于这一层）。

职责（全部确定性）：
- beat 文本由 split_n 逐字落地；
- 层映射：素材层（白名单）/ 色块层 / 锚点词层（≤12 字）/ 几何遮罩；
- 时序：enter/hold/reveal/exit → 帧级整数 alpha 渐变（每层独立）；
- 运动：statement.motion.intent → motion.py 整数轨迹；不可行 → HOLD + 留痕；
- 对比并置：CONTRAST → 左右两个锚点（左=前半、右=后半关键项）；
- 输出 per-beat 帧规格（executor 逐帧合成用）。
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from video_studio.stage33 import motion as motion_lib
from video_studio.stage33 import schemas
from video_studio.stage33.graphics import W, H, hex_rgb
from video_studio.stage33.planner_fallback import NUM_RE, detect_beat_types, split_beats

FPS = 25


def split_n(text: str, n: int, dur: float) -> list[str]:
    pieces = split_beats(text)
    while len(pieces) > n:  # 合并最短相邻（绝不截断丢字）
        best = min(range(len(pieces) - 1),
                   key=lambda i: len(pieces[i]) + len(pieces[i + 1]))
        pieces[best:best + 2] = [pieces[best] + pieces[best + 1]]
    while len(pieces) < n:
        idx = max(range(len(pieces)), key=lambda i: len(pieces[i]))
        p = pieces[idx]
        ms = [m.start() for m in re.finditer(r"[，；。]", p)]
        cut = (ms[len(ms) // 2] + 1) if ms else len(p) // 2
        pieces[idx:idx + 1] = [p[:cut], p[cut:]]
    if dur > 0:
        min_chars = max(int(1.2 * len(text) / dur), 1)
        while len(pieces) > 1:
            small = [i for i, p in enumerate(pieces) if len(p) < min_chars]
            if not small:
                break
            i = small[0]
            if i == 0:
                pieces[0:2] = [pieces[0] + pieces[1]]
            else:
                pieces[i - 1:i + 1] = [pieces[i - 1] + pieces[i]]
    return pieces


def _direction_of(text: str) -> str | None:
    if any(c in text for c in schemas.DIRECTION_LEXICON["DOWN"]):
        return "DOWN"
    if any(c in text for c in schemas.DIRECTION_LEXICON["UP"]):
        return "UP"
    if any(c in text for c in schemas.DIRECTION_LEXICON["RIGHT"]):
        return "RIGHT"
    if any(c in text for c in schemas.DIRECTION_LEXICON["LEFT"]):
        return "LEFT"
    return None


def _stage_alpha(n_frames: int, stages: list[dict], layer_index: int) -> list[int]:
    """阶段 → 该层帧级 alpha（整数、单调段）。enter=0→255；hold=255；exit=255→0；
    reveal=在 40% 处 0→255（第二元素出现）。"""
    n = n_frames
    alphas = [0] * n
    seg = n // 4 if n >= 4 else 1
    # enter（前 1/4）
    e = min(seg, n)
    ramp = motion_lib.alpha_ramp(e, 0, 255)
    alphas[:e] = ramp
    # hold/reveal（中间）
    names = [s.get("name") for s in stages]
    if "reveal" in names:
        r0, r1 = e, min(2 * seg, n)
        rr = motion_lib.alpha_ramp(r1 - r0, 0, 255)
        alphas[r0:r1] = rr
        alphas[r1:] = [255] * (n - r1)
    else:
        alphas[e:] = [255] * (n - e)
    # exit（最后 1/6，若有）
    if "exit" in names:
        x0 = max(0, n - n // 6)
        xr = motion_lib.alpha_ramp(n - x0, 255, 0)
        alphas[x0:] = xr
    return alphas


def _anchor_pos(kind: str, index: int, n_anchors: int) -> tuple[int, int]:
    if kind == "contrast_left":
        return (W // 4, H // 2)
    if kind == "contrast_right":
        return (3 * W // 4, H // 2)
    if kind == "upper":
        return (W // 2, H // 3)
    return (W // 2, H // 2)


def build_beat_spec(beat: dict, stmt: dict, ctx: dict, style: dict,
                    seed: int) -> dict:
    """beat: {beat_id, shot_id, beat_text, start, end, duration}
    stmt: statement 字段（LLM/回退）
    返回执行规格（executor 直接消费）。"""
    dur = beat["duration"]
    # 绝对时间边界 → 帧数（修复 per-beat int() 截断漂移；未来计划的 spec 也使用该口径）
    n_frames = motion_lib.frame_range(beat["start"], beat["end"])
    pal = style["palette"]
    text = beat["beat_text"]
    types = detect_beat_types(text)
    graphic = stmt.get("graphic_layer") or {}
    anchor_text = (graphic.get("text") or stmt.get("attention_target") or "")[:12]
    if anchor_text and anchor_text not in text:
        m = NUM_RE.search(text)
        anchor_text = m.group(0) if m else _first_word(text)
    anchor_text = (anchor_text or "")[:12]
    mat_id = stmt.get("evidence_material")
    layers = []
    stmt_layers = (stmt.get("composition") or {}).get("layers", []) or []
    has_material = bool(mat_id) and any(
        l.get("role") in ("background", "midground") and "素材" in l.get("content", "")
        for l in stmt_layers) or bool(mat_id)
    # 底色
    layers.append({"kind": "color", "color": pal["bg"], "alpha_frames": [255] * n_frames})
    # 素材层（若有）
    if has_material and mat_id:
        layers.append({"kind": "material", "material_id": mat_id,
                       "alpha_frames": [255] * n_frames, "rects": None})
    # 色块/遮罩层（弱化底色区分；无素材时给一个圆角色块承载锚点）
    if not has_material:
        layers.append({"kind": "rounded_rect", "rect": (W // 2 - 520, H // 2 - 260,
                                                       W // 2 + 520, H // 2 + 260),
                       "radius": 28, "color": pal["surface"],
                       "alpha_frames": [255] * n_frames})
    # 对比并置：CONTRAST → 左右双锚点
    is_contrast = "CONTRAST" in types
    if is_contrast:
        left_txt, right_txt = _contrast_parts(text, anchor_text)
        layers.append({"kind": "anchor_text", "text": left_txt[:12],
                       "font_size": style["typography"]["small_anchor"],
                       "color": pal["text"], "stroke": 0,
                       "anchor": _anchor_pos("contrast_left", 0, 2),
                       "alpha_frames": _stage_alpha(n_frames,
                                                    stmt.get("temporal_behavior", {})
                                                    .get("stages", []), 0)})
        layers.append({"kind": "anchor_text", "text": right_txt[:12],
                       "font_size": style["typography"]["small_anchor"],
                       "color": pal["highlight"], "stroke": 0,
                       "anchor": _anchor_pos("contrast_right", 1, 2),
                       "alpha_frames": _stage_alpha(n_frames,
                                                    stmt.get("temporal_behavior", {})
                                                    .get("stages", []), 1)})
    elif anchor_text:
        layers.append({"kind": "anchor_text", "text": anchor_text,
                       "font_size": style["typography"]["anchor"],
                       "color": pal["highlight"] if "DATA" in types else pal["text"],
                       "stroke": 0,
                       "anchor": _anchor_pos("upper", 0, 1)
                                 if "DATA" in types else _anchor_pos("center", 0, 1),
                       "alpha_frames": _stage_alpha(n_frames,
                                                    stmt.get("temporal_behavior", {})
                                                    .get("stages", []), 0)})

    # 运动（整数轨迹；不可行 → HOLD + 留痕）
    motion_note = None
    m_intent = (stmt.get("motion") or {}).get("intent", "none")
    direction = _direction_of(text)
    if m_intent in ("attention_shift", "process_expression", "revelation"):
        mat_layer = next((l for l in layers if l["kind"] == "material"), None)
        if mat_layer is not None and m_intent != "attention_shift":
            # 缩放（素材层）
            zoom_in = m_intent == "process_expression"
            rects = motion_lib.plan_zoom(n_frames, W, H, W, H, zoom_in,
                                         schemas.CAPS["MOTION_MIN_ZOOM_RATIO"],
                                         anchor="center")
            mat_layer["rects"] = rects
            if rects is None:
                motion_note = "缩放幅度不足 → HOLD（静止优先）"
        elif direction and m_intent == "attention_shift":
            rects = motion_lib.plan_pan(n_frames, W, H, W, H, direction,
                                        schemas.CAPS["MOTION_MIN_PAN_RATIO"])
            if rects is not None:
                # 平移应用到素材层；无素材层则应用到全部锚点（文字移动）
                if mat_layer is not None:
                    mat_layer["rects"] = rects
                else:
                    for l in layers:
                        if l["kind"] == "anchor_text":
                            l["shift_frames"] = [
                                (r[0], r[1]) for r in rects]  # 锚点随裁剪位移
            else:
                motion_note = "平移速度不足 1px/帧 → HOLD（静止优先）"
        else:
            motion_note = "运动意图无可行路径 → HOLD（静止优先）"

    return {"beat_id": beat["beat_id"], "shot_id": beat["shot_id"],
            "beat_text": text, "duration": dur, "n_frames": n_frames,
            "anchor_text": anchor_text, "is_contrast": is_contrast,
            "layers": layers, "motion_intent": m_intent, "motion_note": motion_note,
            "statement": {k: stmt.get(k) for k in (
                "narrative_intent", "attention_target", "attention_path",
                "visual_evidence", "visual_metaphor", "shot_language",
                "relation_to_previous", "relation_to_next", "audio_relationship",
                "director_note") if k in stmt},
            "director_note": stmt.get("director_note", "")}


def _first_word(text: str) -> str:
    clean = re.sub(r"[，。；！？、\s]", "", text)
    return clean[:6]


def _contrast_parts(text: str, anchor: str) -> tuple[str, str]:
    for kw in ("但", "却", "而", "反而", "而是", "不是"):
        idx = text.find(kw)
        if idx > 0:
            left = re.sub(r"[，。；！？、\s]", "", text[:idx])
            right = re.sub(r"[，。；！？、\s]", "", text[idx:])
            if anchor in left:
                right = anchor if anchor in right else right
            if anchor in right:
                left = anchor if anchor in left else left
            return (left[:12] or "前"), (right[:12] or "后")
    mid = len(text) // 2
    return (re.sub(r"[，。；！？、\s]", "", text[:mid])[:12] or "前",
            re.sub(r"[，。；！？、\s]", "", text[mid:])[:12] or "后")
