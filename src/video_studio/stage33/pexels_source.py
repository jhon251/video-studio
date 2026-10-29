"""pexels_source (Stage 12.23): independent photo/video source adapter.

Pexels API (key read from user config, never hardcoded):
  - legal: Pexels License — free to use, attribution appreciated; photographer
    + photo id recorded per candidate for attribution.
  - domain complement: modern domestic/office/urban-life photography — the
    exact coverage gap measured across 12.11-12.22 (hook scenes, home office,
    classrooms) that Commons lacks as photos.

Contract: candidates use the SAME shape as Commons candidates
  {"title", "thumburl", "url", "size", "tier"} + "src" provenance block, and
  flow through the SAME frozen Gate -> V1 -> CV-2 chain — no bypass, no
  separate qualification. This adapter performs retrieval only; it never
  judges or filters relevance.

Videos: a videos-search function is provided for completeness; the 12.23
experiment uses the photo endpoint only (the CV-2/eligibility contract is
image-based, identical to 12.14's NASA image-only adapter).
"""
from __future__ import annotations

import time

import requests

UA = {"User-Agent": "video-studio-stage12-23/0.1"}
_last = 0.0
_MIN_INTERVAL_S = 1.0  # be polite to the free API
LICENSE_NOTE = ("Pexels License (free to use, attribution appreciated); "
                "photographer+id recorded")


def _throttled_get(url: str, params: dict, key: str) -> dict:
    global _last
    wait = _MIN_INTERVAL_S - (time.time() - _last)
    if wait > 0:
        time.sleep(wait)
    _last = time.time()
    r = requests.get(url, headers={"Authorization": key, "User-Agent": UA["User-Agent"]},
                     params=params, timeout=40)
    r.raise_for_status()
    return r.json()


def search_pexels_photos(queries: list[str], key: str, per_page: int = 3,
                         cap: int = 8) -> dict:
    """Search Pexels photos; return candidates in the unified Candidate Contract."""
    out: list[dict] = []
    seen: set[int] = set()
    trace = []
    for q in queries or []:
        try:
            data = _throttled_get("https://api.pexels.com/v1/search",
                                  {"query": q, "per_page": per_page,
                                   "orientation": "landscape"}, key)
            items = data.get("photos") or []
        except Exception as e:  # noqa: BLE001
            trace.append({"query": q, "n": 0, "error": str(e)[:80]})
            continue
        n_new = 0
        for p in items:
            pid = p.get("id")
            if pid in seen:
                continue
            seen.add(pid)
            src = p.get("src") or {}
            alt = (p.get("alt") or "").strip()
            out.append({
                "title": alt or f"Pexels photo {pid} by {p.get('photographer', '')}",
                "thumburl": src.get("large") or src.get("medium") or "",
                "url": p.get("url") or f"https://www.pexels.com/photo/{pid}",
                "size": p.get("width") or 0,
                "tier": "second_source",
                "src_pexels": True,
                "src": {"source": "pexels_photos", "pexels_id": pid,
                        "photographer": p.get("photographer", ""),
                        "photographer_url": p.get("photographer_url", ""),
                        "alt": alt[:200], "avg_color": p.get("avg_color", ""),
                        "license": LICENSE_NOTE},
            })
            n_new += 1
            if len(out) >= cap:
                break
        trace.append({"query": q, "n": len(items), "n_new": n_new})
        if len(out) >= cap:
            break
    return {"candidates": out, "trace": trace}


def search_pexels_videos(queries: list[str], key: str, per_page: int = 2) -> dict:
    """Video search available but UNUSED by the 12.23 experiment (image
    eligibility contract); provided so the adapter is photo/video complete."""
    out, trace = [], []
    for q in queries or []:
        try:
            data = _throttled_get("https://api.pexels.com/videos/search",
                                  {"query": q, "per_page": per_page,
                                   "orientation": "landscape"}, key)
            items = data.get("videos") or []
        except Exception as e:  # noqa: BLE001
            trace.append({"query": q, "n": 0, "error": str(e)[:80]})
            continue
        for v in items:
            out.append({"pexels_video_id": v.get("id"), "url": v.get("url"),
                        "duration": v.get("duration"),
                        "image_preview": v.get("image"),
                        "src": {"source": "pexels_videos",
                                "license": LICENSE_NOTE}})
        trace.append({"query": q, "n": len(items)})
    return {"candidates": out, "trace": trace}
