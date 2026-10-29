"""Bounded reachability retry loop for the real provider (no faking: just wait and report)."""
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(r"C:\mp4agent\video-studio")
OUT = ROOT / "docs" / "regression_2x" / "logs" / "phase3a_network_wait.txt"
URL = ("https://commons.wikimedia.org/w/api.php?action=query&format=json&formatversion=2"
       "&generator=search&gsrnamespace=6&gsrlimit=2&gsrsearch=Quest%20PSVR2%20PICO"
       "&prop=imageinfo&iiprop=url")
UA = "video-studio-material/1.0 (local pipeline)"
ATTEMPTS = int(sys.argv[1]) if len(sys.argv) > 1 else 8
GAP = float(sys.argv[2]) if len(sys.argv) > 2 else 25.0
lines = []
ok_at = None
for i in range(1, ATTEMPTS + 1):
    t0 = time.time()
    try:
        req = urllib.request.Request(URL, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=25) as r:            # noqa: S310
            d = json.loads(r.read().decode("utf-8"))
        n = len(((d.get("query") or {}).get("pages")) or [])
        rec = {"attempt": i, "status": r.status, "items": n,
               "latency_s": round(time.time() - t0, 2)}
        ok_at = i
        lines.append(json.dumps(rec, ensure_ascii=False))
        print(lines[-1], flush=True)
        break
    except Exception as exc:                                          # noqa: BLE001
        rec = {"attempt": i, "error": "{}: {}".format(type(exc).__name__, str(exc)[:110]),
               "latency_s": round(time.time() - t0, 2)}
        lines.append(json.dumps(rec, ensure_ascii=False))
        print(lines[-1], flush=True)
        if i < ATTEMPTS:
            time.sleep(GAP)
OUT.write_text("\n".join(lines), encoding="utf-8")
print("\nREACHABLE_AT_ATTEMPT={} (None=still down)".format(ok_at))
print("written", OUT)
