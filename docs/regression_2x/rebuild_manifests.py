"""Rebuild per-zip baseline manifests by hashing entries INSIDE each zip (authoritative bytes).

Why: make_baseline.py wrote a single shared manifest filename, so the second run overwrote the
first. The frozen zip's bytes are authoritative, so hash the zip entries to recover its manifest.

Usage: python docs/regression_2x/rebuild_manifests.py
"""
import hashlib
import json
import sys
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
BASE = Path(r"C:\mp4agent\video-studio\docs\regression_2x\baseline")


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


for zp in sorted(BASE.glob("*.zip")):
    tag = zp.stem
    files = {}
    total = 0
    with zipfile.ZipFile(zp) as z:
        for info in sorted(z.infolist(), key=lambda i: i.filename):
            if info.is_dir():
                continue
            data = z.read(info)
            files[info.filename] = {"sha256": sha_bytes(data), "bytes": len(data)}
            total += len(data)
    man = {"tag": tag, "source": "recovered from zip entries (authoritative)",
           "file_count": len(files), "source_bytes": total,
           "zip_bytes": zp.stat().st_size, "zip_sha256": sha_file(zp), "files": files}
    out = BASE / "baseline_manifest_{}.json".format(tag)
    out.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    print("{:32s} files={:4d} zip_sha256={}  -> {}".format(
        zp.name, len(files), man["zip_sha256"][:32], out.name))

shared = BASE / "baseline_manifest.json"
if shared.exists():
    shared.unlink()
    print("removed ambiguous shared manifest:", shared.name)
