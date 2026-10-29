"""Verify a baseline manifest against the CURRENT tree (drift check) and against its zip.

Usage: python docs/regression_2x/verify_baseline.py [tag]
       tag default: 2.x-preflight-baseline
"""
import hashlib
import json
import sys
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
BASE = ROOT / "docs" / "regression_2x" / "baseline"
TAG = sys.argv[1] if len(sys.argv) > 1 else "2.x-preflight-baseline"
man = json.loads((BASE / "baseline_manifest_{}.json".format(TAG)).read_text(encoding="utf-8"))
zp = BASE / "{}.zip".format(TAG)


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


print("tag:", TAG, "| files:", man["file_count"], "| zip sha256:", man["zip_sha256"][:32])
print("zip exists:", zp.exists(), "| zip hash matches manifest:",
      zp.exists() and sha(zp) == man["zip_sha256"])

with zipfile.ZipFile(zp) as z:
    zip_names = {i.filename for i in z.infolist() if not i.is_dir()}
same = set(man["files"]) == zip_names
print("manifest file list == zip entries:", same)

missing, drift = [], []
for rel, rec in man["files"].items():
    p = ROOT / rel
    if not p.exists():
        missing.append(rel)
    elif sha(p) != rec["sha256"]:
        drift.append(rel)
print("missing in tree:", len(missing), missing[:5])
print("drifted vs tree:", len(drift), drift[:5])
print("VERDICT:", "MATCH" if not missing and not drift and same else "DIFF")
