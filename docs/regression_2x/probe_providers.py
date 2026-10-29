"""Probe reachability of candidate free/no-key material providers (ASCII report, no quota cost).

Candidates (all free, no API key, explicit licence metadata in the response):
  wikimedia_commons : MediaWiki API, imageinfo extmetadata (LicenseShortName/Artist/UsageTerms)
  openverse         : WordPress Openverse API, CC licence fields
  metmuseum         : Met Collection API, isPublicDomain
  nasa              : NASA images API, public domain
"""
import json
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(r"C:\mp4agent\video-studio")
OUT = ROOT / "docs" / "regression_2x" / "logs" / "provider_reachability.txt"
UA = "video-studio-material/1.0 (local research; contact: local-user)"
TARGETS = {
    "wikimedia_commons": "https://commons.wikimedia.org/w/api.php?action=query&format=json"
                         "&list=search&srsearch=virtual%20reality%20headset&srnamespace=6&srlimit=1",
    "openverse": "https://api.openverse.org/v1/images/?q=virtual+reality+headset&page_size=1",
    "metmuseum": "https://collectionapi.metmuseum.org/public/collection/v1/search?hasImages=true"
                 "&q=headset",
    "nasa": "https://images-api.nasa.gov/search?q=headset&media_type=image&page_size=1",
}
lines = []
for name, url in TARGETS.items():
    t0 = time.time()
    rec = {"provider": name, "url_host": url.split("/")[2]}
    try:
        ctx = ssl.create_default_context()
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15, context=ctx) as r:  # noqa: S310
            body = r.read(4096)
            rec.update(status=r.status, bytes=len(body), latency_s=round(time.time() - t0, 2),
                       content_type=r.headers.get("Content-Type"),
                       head=body[:120].decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        rec.update(status=exc.code, error="HTTPError", latency_s=round(time.time() - t0, 2))
    except Exception as exc:                                    # noqa: BLE001
        rec.update(status=None, error="{}: {}".format(type(exc).__name__, str(exc)[:120]),
                   latency_s=round(time.time() - t0, 2))
    lines.append(json.dumps(rec, ensure_ascii=False))
    print(lines[-1], flush=True)
OUT.write_text("\n".join(lines), encoding="utf-8")
print("\nwritten", OUT)
