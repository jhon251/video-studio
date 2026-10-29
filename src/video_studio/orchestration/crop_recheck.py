"""Crop-aware Visual Recheck.

Runs AFTER crop/layout is decided, BEFORE render. Catches the failure class
where CV2 passes the ORIGINAL image but the FULL_BLEED center crop destroys
the semantics (regression fixture: S10-B02, vis=0.387 / dHash shift=25).

Checks: visible area ratio, crop displacement, dHash shift between the crop
band and the full image, extreme aspect transformation, text-collision risk.
High risk -> DEMOTE with recommended action (contain / alternate crop);
never silently proceeds to render.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from video_studio.orchestration.schemas import CropLayout, CropRisk, GateVerdict
from video_studio.orchestration.content_identity import dhash_arr


def full_bleed_box(w: int, h: int, out_ar: float = 16 / 9):
    """Center-cover crop box for a source of w x h into out_ar. Returns (l, t, r, b)."""
    ar = w / h
    if ar > out_ar:
        cw = int(h * out_ar)
        left = (w - cw) // 2
        return (left, 0, left + cw, h)
    ch = int(w / out_ar)
    top = (h - ch) // 2
    return (0, top, w, top + ch)


def evaluate_crop(path: str, beat_id: str, material_id: str, layout: CropLayout | None = None,
                  chart_text: bool = False, min_visible: float = 0.55,
                  max_shift: int = 14, max_displacement: float = 0.05) -> CropRisk:
    """Evaluate the semantic risk of the decided crop against the full image.

    DEMOTE when: visible fraction < min_visible AND dHash shift > max_shift
    (content destroyed by crop), or aspect transform is extreme, or a text
    asset would be cover-cropped. `contain` layouts always PASS (no crop).
    """
    layout = layout or CropLayout()
    im = Image.open(path)
    w, h = im.size
    src_ar = w / h
    out_ar = layout.out_w / layout.out_h

    if layout.fit_mode in ("contain",) or layout.crop_box is None and layout.fit_mode != "cover":
        return CropRisk(asset_material_id=material_id, beat_id=beat_id,
                        visible_frac=1.0, dhash_shift=0, displacement_frac=0.0,
                        aspect_transform=round(out_ar / src_ar, 3),
                        text_collision_risk=chart_text,
                        verdict=GateVerdict.PASS, reasons=["no_crop_contain"])

    box = layout.crop_box or full_bleed_box(w, h, out_ar)
    l, t, r, b = box
    visible = max(0.0, min(1.0, (r - l) * (b - t) / (w * h)))

    full = dhash_arr(np.asarray(im.convert("L")))
    crop = dhash_arr(np.asarray(im.convert("L").crop(box)))
    shift = int((crop != full).sum())

    cx, cy = (l + r) / 2 / w - 0.5, (t + b) / 2 / h - 0.5
    displacement = float(max(abs(cx), abs(cy)))
    aspect_transform = round(out_ar / src_ar, 3)

    reasons = []
    verdict = GateVerdict.PASS
    if visible < min_visible and shift > max_shift:
        reasons.append(f"content_loss: vis={visible:.3f}<{min_visible} shift={shift}>{max_shift}")
        verdict = GateVerdict.DEMOTE
    if abs(aspect_transform - 1.0) > 0.6 and layout.fit_mode == "cover":
        reasons.append(f"extreme_aspect_transform={aspect_transform}")
        verdict = GateVerdict.DEMOTE
    if displacement > max_displacement:
        reasons.append(f"crop_displacement={displacement:.3f}")
        if verdict == GateVerdict.PASS:
            verdict = GateVerdict.DEMOTE
    if chart_text and layout.fit_mode == "cover":
        reasons.append("text_asset_cover_cropped_text_collision_risk")
        verdict = GateVerdict.DEMOTE
    if not reasons:
        reasons.append("ok")
    return CropRisk(asset_material_id=material_id, beat_id=beat_id,
                    visible_frac=round(visible, 3), dhash_shift=shift,
                    displacement_frac=round(displacement, 3),
                    aspect_transform=aspect_transform,
                    text_collision_risk=chart_text and layout.fit_mode == "cover",
                    verdict=verdict, reasons=reasons)
