"""Probe: is a REAL 401/403 reachable from the Wikimedia API with a bogus Bearer token?"""
import json
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(r"C:\mp4agent\video-studio")
OUT = ROOT / "docs" / "regression_2x" / "logs" / "auth_probe.txt"
UA = "video-studio-material/1.0 (local pipeline)"
URLS = {
    "read_anon": "https://commons.wikimedia.org/w/api.php?action=query&format=json&meta=siteinfo",
    "read_bogus_bearer": "https://commons.wikimedia.org/w/api.php?action=query&format=json"
                         "&meta=userinfo",
    "login_required": "https://commons.wikimedia.org/w/api.php?action=query&format=json&meta=tokens"
                      "&type=csrf",
}
lines = []
for name, url in URLS.items():
    for auth in (None, "Bearer definitely-invalid-token-for-testing"):
        headers = {"User-Agent": UA}
        if auth:
            headers["Authorization"] = auth
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as r:      # noqa: S310
                body = r.read(200).decode("utf-8", "replace")
            rec = {"case": name, "auth": bool(auth), "status": r.status, "head": body[:120]}
        except urllib.error.HTTPError as exc:
            rec = {"case": name, "auth": bool(auth), "status": exc.code,
                   "head": exc.read(160).decode("utf-8", "replace")}
        except Exception as exc:                                     # noqa: BLE001
            rec = {"case": name, "auth": bool(auth), "error": "{}: {}".format(
                type(exc).__name__, str(exc)[:80])}
        lines.append(json.dumps(rec, ensure_ascii=False))
        print(lines[-1], flush=True)
OUT.write_text("\n".join(lines), encoding="utf-8")
print("\nwritten", OUT)
