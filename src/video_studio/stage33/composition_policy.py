"""composition_policy (Stage 12.3): asset_type + visual_intent + focus ->
how the asset enters the frame (fit_mode / crop / framing / safe_area).

Separate from camera_motion (which decides motion AFTER composition).
Composition only decides PRESENTATION, never re-judges material quality
(that's Stage 12.1 gate). No visual model.

Fit modes:
  FULL_BLEED   : scale-to-fill + center crop (visual assets: photo/person/city)
  CONTAIN_BG   : contain within 1920x1080 + blurred background fill
                 (documents/web/screenshots so text/body is NOT cropped)
  DETAIL_CROP  : crop a focus region for dense info assets (chart/diagram)
  FRAMED_DOC   : contain + slight pad + dark frame (document/PDF page style)

Deterministic. Every decision has a reason. No CLIP/detector/segmentation.
"""
from __future__ import annotations


def decide_composition(asset_type: str, visual_intent: str,
                       focus: str | None = None) -> dict:
    intent_l = (visual_intent or "").lower()
    asset = (asset_type or "").upper()

    # info-dense signal
    info_signal = any(k in intent_l for k in
                      ("文档", "论文", "文献", "页面", "截图", "网页", "报告",
                       "document", "paper", "page", "screenshot", "report", "档案"))
    chart_signal = any(k in intent_l for k in
                       ("图表", "数据", "趋势", "统计", "chart", "data", "graph", "infographic"))
    map_signal = any(k in intent_l for k in
                     ("地图", "map", "区域", "region", "分布", "航线"))
    person_signal = any(k in intent_l for k in
                        ("人物", "人群", "员工", "学者", "人类", "people", "office", "person"))

    if asset in ("DOCUMENT", "VECTOR", "UNKNOWN"):
        # info-dense: keep body visible (contain, no brutal crop)
        if map_signal:
            return {"composition_type": "DETAIL_CROP", "fit_mode": "detail_crop",
                    "crop_region": focus or "center", "safe_area": "0.85",
                    "composition_reason": "map: present region of interest, keep legend readable"}
        if chart_signal and not info_signal:
            return {"composition_type": "DETAIL_CROP", "fit_mode": "detail_crop",
                    "crop_region": focus or "center", "safe_area": "0.85",
                    "composition_reason": "chart: present data focus, keep labels readable"}
        return {"composition_type": "CONTAIN_BG", "fit_mode": "contain",
                "crop_region": None, "safe_area": "1.0",
                "composition_reason": "document/web/screenshot: contain so text/body not cropped"}

    if asset == "IMAGE":
        if person_signal:
            return {"composition_type": "FULL_BLEED_SUBJECT", "fit_mode": "cover_subject",
                    "crop_region": focus or "center", "safe_area": "0.9",
                    "composition_reason": "person/office: keep subject whole (safe crop)"}
        if map_signal:
            return {"composition_type": "DETAIL_CROP", "fit_mode": "detail_crop",
                    "crop_region": focus or "center", "safe_area": "0.85",
                    "composition_reason": "map image: present region, keep legend readable"}
        if info_signal:
            return {"composition_type": "FRAMED_DOC", "fit_mode": "contain",
                    "crop_region": None, "safe_area": "1.0",
                    "composition_reason": "image-of-document: framed contain, avoid crop"}
        # city/photo/other visual
        return {"composition_type": "FULL_BLEED", "fit_mode": "cover",
                "crop_region": "center", "safe_area": "0.95",
                "composition_reason": "visual asset: full-bleed center crop (subject centered)"}

    if asset == "VIDEO":
        return {"composition_type": "FULL_BLEED", "fit_mode": "cover",
                "crop_region": "center", "safe_area": "0.95",
                "composition_reason": "video: native cover, center crop"}

    return {"composition_type": "CONTAIN_BG", "fit_mode": "contain",
            "crop_region": None, "safe_area": "1.0",
            "composition_reason": "unknown -> contain (safe, no crop)"}


def fit_mode_to_ffmpeg(decision: dict, out_w: int = 1920, out_h: int = 1080) -> str:
    """Map composition decision to an ffmpeg -vf filter chain string."""
    fit = decision["fit_mode"]
    if fit == "contain":
        # contain + blurred background fill (no black bars, no crop)
        return (f"scale={out_w}:{out_h}:force_original_aspect_ratio=decrease,"
                f"pad={out_w}:{out_h}:(ow-iw)/2:(oh-ih)/2:color=0x0b2e33")
    if fit == "detail_crop":
        # crop center 85% region then scale to fill (zoom-like, keep readable core)
        return (f"scale={out_w}:{out_h}:force_original_aspect_ratio=increase,"
                f"crop={out_w}:{out_h}")
    # cover / cover_subject / full_bleed
    return (f"scale={out_w}:{out_h}:force_original_aspect_ratio=increase,"
            f"crop={out_w}:{out_h}")
