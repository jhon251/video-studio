"""Retrieval v1.5 (Stage 12.5): intent-driven media preference for Commons search.

Problem proven by Stage 12.5 audit: Commons gsrsearch (namespace 6) matches file
DESCRIPTION text; archive.org bulk document scans dominate the index, so the
Stage 12.1 pre-gate pool was 78 DOC / 0 IMG and V1/CV-2 never saw a real photo.

Policy (visual-intent driven, NOT a type blacklist — Dartmouth-style archival
PDFs stay reachable when the intent asks for DOCUMENT):
  asset_type_hint IMAGE    -> query + " filetype:bitmap"  (real photos)
  asset_type_hint VIDEO    -> query + " filetype:bitmap"  (photo = usable visual; motion is motion policy's job)
  asset_type_hint DOCUMENT -> unconstrained               (archives / original documents allowed)
  anything else / unknown  -> bitmap first, one unconstrained fallback pass if 0 results

Fallback: deterministic relaxation ladder (bitmap full -> bitmap 3 words ->
bitmap 2 words -> unconstrained), stopping at the first non-empty pool; every
attempt is recorded in the trace.

This module does not touch V1 / sanitizer / gate / CV-2 / asset_cache.
"""
from __future__ import annotations

import time

import requests

UA = {"User-Agent": "video-studio-stage12-5/0.1"}
_last_request_at = 0.0
_MIN_INTERVAL_S = 0.8  # Commons rate-limits bursts -> throttle all search calls
_BACKOFF_S = (2.0, 5.0)  # retry backoff on transient/HTML error responses


def _throttled_get(url: str, params: dict) -> requests.Response:
    global _last_request_at
    wait = _MIN_INTERVAL_S - (time.time() - _last_request_at)
    if wait > 0:
        time.sleep(wait)
    _last_request_at = time.time()
    return requests.get(url, headers=UA, params=params, timeout=40)


def media_preference(intent: dict) -> dict:
    hint = (intent.get("asset_type_hint") or "IMAGE").upper()
    if hint == "DOCUMENT":
        return {"constraint": None, "fallback": None,
                "reason": "hint=DOCUMENT -> unconstrained (archives allowed)"}
    if hint in ("IMAGE", "VIDEO"):
        return {"constraint": "filetype:bitmap", "fallback": None,
                "reason": f"hint={hint} -> bitmap photos (photo is the usable visual)"}
    return {"constraint": "filetype:bitmap", "fallback": "unconstrained",
            "reason": f"hint={hint} -> bitmap first, unconstrained fallback"}


def search_commons(query: str, limit: int = 8) -> list[dict]:
    url = "https://commons.wikimedia.org/w/api.php"
    params = {"action": "query", "format": "json", "generator": "search",
              "gsrsearch": query, "gsrnamespace": 6, "gsrlimit": limit,
              "prop": "imageinfo", "iiprop": "url|size", "iiurlwidth": 640}
    attempts_left = 1 + len(_BACKOFF_S)
    for attempt in range(attempts_left):
        try:
            r = _throttled_get(url, params)
            pages = r.json().get("query", {}).get("pages", {})
            out = []
            for _pid, pg in pages.items():
                ii = (pg.get("imageinfo") or [{}])[0]
                out.append({"title": pg.get("title", ""),
                            "thumburl": ii.get("thumburl") or "",
                            "url": ii.get("descriptionurl") or "",
                            "size": ii.get("width", 0)})
            return out
        except Exception:  # noqa: BLE001
            if attempt < attempts_left - 1:
                time.sleep(_BACKOFF_S[attempt])
                continue
            # errors must NOT become pseudo-candidates: a fake entry would stop
            # the relaxation ladder and pollute the gate with SEARCH_ERROR titles
            return []


def search_with_media_preference(intent: dict, queries: list[str],
                                 limit: int = 8) -> dict:
    """Union search over queries with the intent's media preference applied.

    Deterministic relaxation ladder (stop at first non-empty pool; every
    attempt recorded):
      1. "<query> filetype:bitmap"            (preference-constrained)
      2. "<first 3 words> filetype:bitmap"    (over-specific full-text relax)
      3. "<first 2 words> filetype:bitmap"
      4. "<query>" unconstrained              (last resort; gate still judges)
    Returns {"candidates", "preference", "trace", "attempts"}.
    """
    pref = media_preference(intent)
    cands: list[dict] = []
    seen: set[str] = set()
    trace: list[dict] = []

    def run(queries_: list[str], constrained: bool) -> None:
        for q in queries_:
            sent = f"{q} filetype:bitmap" if constrained else q
            res = search_commons(sent, limit)
            trace.append({"query": q, "sent": sent, "n": len(res),
                          "constrained": constrained})
            for c in res:
                if c["title"] and c["title"] not in seen:
                    seen.add(c["title"])
                    cands.append(c)

    def words(q: str, n: int) -> str:
        return " ".join(q.split()[:n])

    attempts = []
    if pref["constraint"]:
        ladder = [("bitmap_full", lambda q: f"{q} filetype:bitmap"),
                  ("bitmap_w3", lambda q: f"{words(q, 3)} filetype:bitmap"),
                  ("bitmap_w2", lambda q: f"{words(q, 2)} filetype:bitmap"),
                  ("unconstrained", lambda q: q)]
    else:
        ladder = [("unconstrained", lambda q: q)]
    for name, build in ladder:
        attempts.append(name)
        run(queries, constrained=(name != "unconstrained"))
        if cands:
            break
    return {"candidates": cands, "preference": pref,
            "trace": trace, "attempts": attempts}


def media_type(title: str) -> str:
    t = (title or "").lower()
    if ".pdf" in t or ".djvu" in t:
        return "DOC"
    if ".svg" in t:
        return "SVG"
    if t.endswith((".wav", ".ogg", ".mp3", ".flac")):
        return "AUDIO"
    if t.endswith((".webm", ".ogv", ".mp4", ".mov")):
        return "VIDEO"
    return "IMG"
