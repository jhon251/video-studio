# -*- coding: utf-8 -*-
"""只为一个基线 tag 生成 manifest（对**冻结 ZIP 内的字节**取哈希，权威口径）。

与 `rebuild_manifests.py` 的区别：**只写指定 tag**，不触碰任何历史 manifest。

用法：python docs/regression_2x/make_manifest_one.py <tag>
产出：docs/regression_2x/baseline/baseline_manifest_<tag>.json
"""
import hashlib
import json
import sys
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
BASE = Path(r"C:\mp4agent\video-studio\docs\regression_2x\baseline")
TAG = sys.argv[1]
ZP = BASE / "{}.zip".format(TAG)
OUT = BASE / "baseline_manifest_{}.json".format(TAG)


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


files, total = {}, 0
with zipfile.ZipFile(ZP) as z:
    for info in sorted(z.infolist(), key=lambda i: i.filename):
        if info.is_dir():
            continue
        data = z.read(info)
        files[info.filename] = {"sha256": sha_bytes(data), "bytes": len(data)}
        total += len(data)
man = {"tag": TAG, "root": str(ZP.parent.parent.parent.parent), "file_count": len(files),
       "source_bytes": total, "zip_bytes": ZP.stat().st_size, "zip_sha256": sha_file(ZP),
       "files": files,
       "note": "manifest 由 ZIP 内条目字节重建（权威）；仅本 tag 生成，未改写历史 manifest"}
OUT.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
print("tag:", TAG, "files:", len(files), "source bytes: {:,}".format(total),
      "zip bytes: {:,}".format(ZP.stat().st_size))
print("zip sha256:", man["zip_sha256"])
print("manifest:", OUT)
