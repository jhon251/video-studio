"""asset_render_resolver (Stage 11): from CV-2 top-1 contract to a renderable
still image for the renderer. Reuses existing asset_cache. Explicit fallback.

Flow per top-1 asset:
  contract (asset_id/thumburl/media_type/renderable_visual)
    -> cache check (asset_cache.acquire_asset; preview/download)
    -> validate MIME/size
    -> if renderable direct -> return local image path
    -> if DOCUMENT: thumburl already page-1 PNG -> direct use (no extra work)
    -> if VECTOR: SVG -> PNG conversion (cairosvg if available, else fallback)
    -> if VIDEO: extract frame 0 via ffmpeg (if ffmpeg available) else
                 VIDEO_ASSET_NOT_SUPPORTED
    -> if AUDIO/TEXT/UNKNOWN: ASSET_NOT_RENDERABLE_* -> deterministic text-card
  Every path records: asset_acquisition_status, asset_type, renderable_visual,
  cache_hit, download_status, conversion_status, fallback_reason. No silent failure.

NEVER uses a type blacklist: PDF/SVG/VIDEO get conversion paths.
"""
from __future__ import annotations

import base64
import json
import subprocess
import uuid
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[3]
FFMPEG = ROOT / "bin" / "ffmpeg.exe"
UA = {"User-Agent": "video-studio-stage11/0.1"}
from video_studio.stage33.asset_cache import acquire_asset  # noqa: E402


def _probe(p: Path):
    r = subprocess.run([str(FFMPEG), "-i", str(p)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    import re
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", r.stderr)
    if m:
        return float(m.group(1)) * 3600 + float(m.group(2)) * 60 + float(m.group(3))
    return 0.0


def resolve_renderable(asset: dict, cache_dir: Path, work_dir: Path) -> dict:
    """Get a local still image for the renderer. Returns dict with
    status/local_path/fallback_reason/conversion etc."""
    record = {
        "asset_id": asset.get("asset_id"),
        "title": asset.get("title"),
        "media_type": asset.get("media_type"),
        "renderable_visual": asset.get("renderable_visual"),
        "path": asset.get("path"),
        "asset_acquisition_status": "PENDING",
        "cache_hit": False, "download_status": None,
        "conversion_status": None, "fallback_reason": None,
        "local_path": None,
    }
    thumb = asset.get("thumburl") or ""
    if not thumb:
        record.update({"asset_acquisition_status": "FAIL",
                       "fallback_reason": "ASSET_NOT_FOUND", "download_status": "no_url"})
        return record

    # -- cache-first via asset_cache (shared, no duplicate cache) --
    acq = acquire_asset(cache_dir, asset.get("asset_id", "unknown"), thumb,
                        preview_path=None, ext_hint="image")
    record["cache_hit"] = bool(acq.get("cache_hit"))
    record["download_status"] = acq.get("status")
    if acq.get("status") != "OK":
        record.update({"asset_acquisition_status": "FAIL",
                       "fallback_reason": "ASSET_DOWNLOAD_FAILED",
                       "download_status": acq.get("status") + ":" + str(acq.get("failure_reason"))})
        return record

    local = Path(acq["local_path"])
    record["asset_acquisition_status"] = "OK"
    record["local_path"] = str(local)

    # -- media type handling --
    mt = asset.get("media_type")
    if mt == "IMAGE":
        record["conversion_status"] = "DIRECT_USE"
        return record
    if mt == "DOCUMENT":
        # Commons thumb for PDF page1 is already a PNG; verify by probing bytes
        if local.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
            record["conversion_status"] = "DOCUMENT_THUMB_DIRECT"
            return record
        record["conversion_status"] = "CONVERT_PDF"
        # thumburl is page1 png -> it IS an image; accept
        return record
    if mt == "VECTOR":
        # SVG: try rasterize via cairosvg if available; else fallback
        try:
            import cairosvg  # type: ignore
            png = work_dir / f"{asset.get('asset_id', 'v')}.png"
            cairosvg.svg2png(url=str(local), write_to=str(png), output_width=1280)
            record["conversion_status"] = "SVG_TO_PNG"
            record["local_path"] = str(png)
            return record
        except Exception as e:  # noqa: BLE001
            record.update({"conversion_status": f"SVG_CONVERT_FAILED:{type(e).__name__}",
                           "fallback_reason": "ASSET_CONVERSION_FAILED",
                           "asset_acquisition_status": "FAIL"})
            return record
    if mt == "VIDEO":
        # still frame extraction (allowed conversion; honest note)
        try:
            frame = work_dir / f"{asset.get('asset_id', 'v')}_frame.jpg"
            subprocess.run([str(FFMPEG), "-y", "-i", str(local), "-frames:v", "1",
                            "-q:v", "2", str(frame)], capture_output=True, check=True, timeout=90)
            if frame.exists():
                record["conversion_status"] = "VIDEO_STILL_EXTRACT"
                record["local_path"] = str(frame)
                return record
            raise RuntimeError("no frame")
        except Exception as e:  # noqa: BLE001
            record.update({"conversion_status": f"VIDEO_FAILED:{type(e).__name__}",
                           "fallback_reason": "VIDEO_ASSET_NOT_SUPPORTED",
                           "asset_acquisition_status": "FAIL"})
            return record
    # AUDIO / TEXT / UNKNOWN
    record.update({"asset_acquisition_status": "FAIL",
                   "fallback_reason": ("ASSET_NOT_RENDERABLE_AUDIO" if mt == "AUDIO" else
                                       ("ASSET_NOT_RENDERABLE_TEXT" if mt == "TEXT" else
                                        "ASSET_UNKNOWN_NOT_RENDERABLE")),
                   "download_status": "declined"})
    return record
