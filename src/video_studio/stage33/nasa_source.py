"""nasa_source (Stage 12.14): independent second-source adapter.

Why NASA Image and Video Library (images-api.nasa.gov):
  - legal: NASA media are public-domain per NASA media policy (recorded per
    candidate in provenance); no API key needed; stable JSON API.
  - domain complement: real robots, mission-control rooms, server/computer
    banks, Earth night-city photography, industrial assembly — the visible
    counterparts of AI/automation beats that Commons full-text noise buries.
  - deliberately NOT a Commons mirror query: different index, own metadata
    (nasa_id, center, date_created, keywords).

Contract: candidates use the SAME shape as Commons candidates
  {"title", "thumburl", "url", "size", "tier"}
plus a "src" provenance block. They go through the SAME frozen
Gate -> V1 -> CV-2 chain — no bypass, no separate qualification.

This adapter performs retrieval only; it never judges or filters relevance.
"""
from __future__ import annotations

import time

import requests

UA = {"User-Agent": "video-studio-stage12-14/0.1"}
_last = 0.0
_MIN_INTERVAL_S = 1.0  # be polite to the free API
LICENSE_NOTE = "Public domain (NASA media policy); source+id recorded for attribution"


def _throttled_get(url: str, params: dict) -> requests.Response:
    global _last
    wait = _MIN_INTERVAL_S - (time.time() - _last)
    if wait > 0:
        time.sleep(wait)
    _last = time.time()
    return requests.get(url, headers=UA, params=params, timeout=40)


def search_nasa(queries: list[str], limit: int = 8) -> dict:
    """Search NASA images; return candidates in the unified Candidate Contract."""
    out: list[dict] = []
    seen: set[str] = set()
    trace = []
    for q in queries or []:
        try:
            r = _throttled_get("https://images-api.nasa.gov/search",
                               {"q": q, "media_type": "image", "page_size": limit})
            items = (r.json().get("collection", {}) or {}).get("items", []) or []
        except Exception as e:  # noqa: BLE001
            trace.append({"query": q, "n": 0, "error": str(e)[:80]})
            continue
        n_new = 0
        for it in items:
            data = (it.get("data") or [{}])[0]
            nid = data.get("nasa_id")
            links = it.get("links") or []
            thumb = next((l.get("href") for l in links if l.get("href")), "")
            title = (data.get("title") or "").strip()
            if not nid or not title or nid in seen:
                continue
            seen.add(nid)
            out.append({
                "title": title,
                "thumburl": thumb,
                "url": f"https://images.nasa.gov/details/{nid}",
                "size": data.get("width") or 0,
                "tier": "second_source",
                "src": {"source": "nasa_image_library", "nasa_id": nid,
                        "date_created": data.get("date_created", ""),
                        "center": data.get("center", ""),
                        "keywords": (data.get("keywords") or [])[:6],
                        "description": (data.get("description") or "")[:220],
                        "license": LICENSE_NOTE},
            })
            n_new += 1
        trace.append({"query": q, "n": len(items), "n_new": n_new})
    return {"candidates": out, "trace": trace}
