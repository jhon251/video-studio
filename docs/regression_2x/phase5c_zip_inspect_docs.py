# -*- coding: utf-8 -*-
"""列出基线 ZIP 内 docs/ 与 docs/regression_2x/ 条目（只读），用于确认基线收录口径。"""
import sys
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
BASE = Path(r"C:\mp4agent\video-studio\docs\regression_2x\baseline")
zp = BASE / (sys.argv[1] if len(sys.argv) > 1 else "5.x-phase5b-baseline.zip")
names = [i.filename for i in zipfile.ZipFile(zp).infolist() if not i.is_dir()]
docs = [n for n in names if n.startswith("docs/")]
r2x = [n for n in docs if n.startswith("docs/regression_2x/")]
print("total entries", len(names), "| docs/", len(docs), "| docs/regression_2x/", len(r2x))
print("\n-- top-level prefixes --")
pref = {}
for n in names:
    p = n.split("/")[0] + ("/" + n.split("/")[1] if n.count("/") >= 1 else "")
    pref[p] = pref.get(p, 0) + 1
for k in sorted(pref):
    print("   {:55s} {}".format(k, pref[k]))
print("\n-- docs/regression_2x entries --")
for n in sorted(r2x):
    print("   ", n)
