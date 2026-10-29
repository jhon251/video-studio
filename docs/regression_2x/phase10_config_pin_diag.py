# -*- coding: utf-8 -*-
"""Phase 10 诊断：config.json sha256 与基线 manifest 钉定值的关系 + M5d 断言出处。"""
import hashlib
import json
import pathlib
import re
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
cfg = R / "config" / "config.json"
disk = hashlib.sha256(cfg.read_bytes()).hexdigest()
print("disk config.json sha256:", disk[:16], "…")
mani = sorted((R / "docs" / "regression_2x" / "baseline").glob("baseline_manifest_*.json"))
for m in mani:
    j = json.loads(m.read_text(encoding="utf-8"))
    hit = None
    def walk(o, path=""):
        global hit
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(v, str) and "config/config.json" in k:
                    hit = (k, v)
                walk(v, path + "/" + str(k))
        elif isinstance(o, list):
            for x in o:
                walk(x, path)
    walk(j)
    print(" ", m.name, "-> config 钉定:", hit)
print("\n=== M5d 断言出处 ===")
for t in sorted((R / "tests").glob("*.py")) + sorted((R / "docs" / "regression_2x").glob("*.py")):
    try:
        s = t.read_text(encoding="utf-8")
    except Exception:
        continue
    if "M5d" in s and "config.json" in s:
        for i, line in enumerate(s.splitlines(), 1):
            if "M5d" in line or ("config/config.json" in line and ("sha256" in line or "manifest" in line)):
                print("  {}:{}: {}".format(t.relative_to(R).as_posix(), i, line.strip()[:150]))
