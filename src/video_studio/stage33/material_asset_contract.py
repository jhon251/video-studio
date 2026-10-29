"""material_asset_contract (Stage 11): stable candidate identity + renderability.

Bridges: raw candidates (Commons, with thumburl/url) -> CV-2 result (rank/title)
-> renderer. Pure integration layer. Does NOT touch CV-2 / V1 / sanitizer.

Concepts:
  asset_id    = stable machine identity derived from source url (sha256 prefix)
  media_type  = IMAGE / DOCUMENT / VECTOR / AUDIO / VIDEO / TEXT / UNKNOWN
  renderable_visual = True if the asset can be turned into a still visual
                by direct use OR a legitimate conversion (PDF page -> image;
                SVG -> PNG; WEBP -> jpg; VIDEO -> still frame is ALLOWED here
                only via ffmpeg extraction? NO — keep honest: video still-frame
                extraction is supported by ffmpeg; but if renderer is static
                image only, we record VIDEO_STILL_EXTRACT and use frame 0).
                AUDIO -> not visual (AUDIO_NOT_VISUAL); TEXT -> not visual.
  NEVER does a pure type blacklist: PDF/SVG may be renderable via conversion.

Acquisition uses ONLY the existing asset_cache.acquire_asset (no second cache).
Fallback reasons are explicit (ASSET_DOWNLOAD_FAILED / ASSET_NOT_RENDERABLE /
ASSET_CONVERSION_FAILED / ASSET_NOT_FOUND / VIDEO_ASSET_NOT_SUPPORTED /
AUDIO_NOT_VISUAL / UNKNOWN). No silent failure.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path


def media_type_of(title: str, thumburl: str = "", url: str = "") -> str:
    t = (title or "").lower()
    u = (thumburl or url or "").lower()
    if ".pdf" in t or ".pdf" in u or "page1-" in u:
        return "DOCUMENT"
    if ".svg" in t or ".svg" in u:
        return "VECTOR"
    if ".wav" in t or ".mp3" in t or ".ogg" in t or ".flac" in t or ".wav" in u:
        return "AUDIO"
    if ".mp4" in t or ".webm" in t or ".ogv" in t or ".mov" in t or ".mp4" in u:
        return "VIDEO"
    if ".txt" in t or ".md" in t:
        return "TEXT"
    for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".avif"):
        if ext in t or ext in u:
            return "IMAGE"
    if "/thumb/" in u:
        # thumbnails without recognizable ext: treat as IMAGE (Commons thumb)
        return "IMAGE"
    return "UNKNOWN"


def renderability(media_type: str) -> dict:
    """Return (renderable_visual, path). No type blacklist: PDF/SVG/VIDEO get
    conversion paths; AUDIO/TEXT/UNKNOWN are honestly not visual."""
    if media_type == "IMAGE":
        return {"renderable_visual": True, "path": "direct", "note": ""}
    if media_type == "DOCUMENT":
        return {"renderable_visual": True, "path": "convert_pdf_page",
                "note": "PDF -> first page PNG (has thumburl already = rendered page1 thumb)"}
    if media_type == "VECTOR":
        return {"renderable_visual": True, "path": "convert_svg_png", "note": "SVG -> PNG"}
    if media_type == "VIDEO":
        return {"renderable_visual": True, "path": "still_frame",
                "note": "video -> extract frame (ffmpeg); if unavailable VIDEO_ASSET_NOT_SUPPORTED"}
    if media_type == "AUDIO":
        return {"renderable_visual": False, "path": "none",
                "note": "AUDIO_NOT_VISUAL", "fallback": "ASSET_NOT_RENDERABLE_AUDIO"}
    if media_type == "TEXT":
        return {"renderable_visual": False, "path": "none",
                "note": "TEXT_NOT_VISUAL", "fallback": "ASSET_NOT_RENDERABLE_TEXT"}
    return {"renderable_visual": False, "path": "none",
            "note": "UNKNOWN", "fallback": "ASSET_UNKNOWN_NOT_RENDERABLE"}


def asset_id_of(url: str) -> str:
    if not url:
        return "asset_nourl"
    return "a_" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]


def build_contract(candidates_raw: dict, cv2_results: dict) -> dict:
    """Merge raw candidate URLs with CV-2 rankings by title.

    Returns per-shot: {shot_id, v1_top1_title, vision_top1_title,
    selected_top1 (contract)}, plus candidates reservoir keyed by title.
    """
    raw_by_title = {}
    for sid, info in candidates_raw.get("shots", {}).items():
        for cand in info.get("requested", []):
            raw_by_title[(sid, cand.get("title"))] = cand

    per_shot = []
    for ps in cv2_results.get("per_shot", []):
        sid = ps.get("shot_id")
        baselines = ps.get("baseline_top_k") or []
        visions = ps.get("vision_top_k") or []
        finals = ps.get("final_top_k") or []
        baseline_titles = [c.get("title") for c in ps.get("candidates", [])
                           if c.get("rank") in baselines]
        # rebuild candidate list with URLs from raw reservoir
        cands = []
        for c in ps.get("candidates", []):
            raw = raw_by_title.get((sid, c.get("title")), {})
            mid = c.get("rank")
            url = raw.get("thumburl") or raw.get("url") or ""
            contract = {
                "rank": mid,
                "title": c.get("title"),
                "asset_id": asset_id_of(raw.get("url") or url),
                "thumburl": raw.get("thumburl", ""),
                "source_url": raw.get("url", ""),
                "media_type": media_type_of(c.get("title"), raw.get("thumburl", ""),
                                            raw.get("url", "")),
                "vision_fit": c.get("vision_fit"),
                "vision_success": c.get("vision_success"),
                "acq": c.get("acq"),
                "cache_hit": c.get("cache_hit"),
            }
            contract.update(renderability(contract["media_type"]))
            cands.append(contract)
        if not cands:
            per_shot.append({"shot_id": sid, "selected_top1": None, "candidates": [],
                             "note": "no_candidate"})
            continue
        # sorted by vision (same rule as CV-2: top fits first), keep V1 order for non-fit
        def sk(x):
            return (-(x["vision_fit"] if x["vision_fit"] is not None else -1.0), x["rank"])
        ordered = sorted(cands, key=sk)
        per_shot.append({
            "shot_id": sid,
            "v1_top1_title": cands[0]["title"] if cands else None,
            "vision_top1_title": ordered[0]["title"] if ordered else None,
            "selected_top1": ordered[0] if ordered else None,
            "candidates": cands,
        })
    return {"per_shot": per_shot,
            "reservoir_size": len(raw_by_title)}
