# -*- coding: utf-8 -*-
"""列出某个基线 ZIP 内最大的若干条目，并检查是否包含给定前缀（只读）。"""
import sys
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
BASE = Path(r"C:\mp4agent\video-studio\docs\regression_2x\baseline")
zp = BASE / (sys.argv[1] if len(sys.argv) > 1 else "5.x-phase5b-baseline.zip")
infos = sorted((i for i in zipfile.ZipFile(zp).infolist() if not i.is_dir()),
               key=lambda i: -i.file_size)
print("zip:", zp.name, "entries:", len(infos),
      "uncompressed total: {:,}".format(sum(i.file_size for i in infos)),
      "zip bytes: {:,}".format(zp.stat().st_size))
print("\nlargest 12 entries:")
for i in infos[:12]:
    print("  {:>10,}  {}  ({})".format(i.file_size, i.filename, "dir" if i.is_dir() else ""))
for pref in ("docs/regression_2x/snapshots/", "docs/regression_2x/baseline/",
             "docs/regression_2x/logs/", "docs/regression_2x/logs_5b_frozen/"):
    hits = [i for i in infos if i.filename.startswith(pref)]
    print("\nprefix {:45s} entries={:4d} bytes={:,}".format(
        pref, len(hits), sum(i.file_size for i in hits)))
