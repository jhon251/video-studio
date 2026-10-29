# -*- coding: utf-8 -*-
"""5-M：**代码/测试指纹**（基线成员，不含 docs）——证明"电池跑的就是最终冻结的代码"。

用法: python docs/regression_2x/phase5m_code_fingerprint.py [label]
产出: docs/regression_2x/logs/phase5m_code_fingerprint_<label>.json
"""
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
LOGS = ROOT / "docs" / "regression_2x" / "logs"
label = sys.argv[1] if len(sys.argv) > 1 else "before"
DIRS = ("src", "config", "tests", "scripts")
FILES = ("run.py", "pyproject.toml", "README.md")


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


man = {}
for d in DIRS:
    for p in sorted((ROOT / d).rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc":
            man[p.relative_to(ROOT).as_posix()] = sha(p)
for f in FILES:
    p = ROOT / f
    if p.is_file():
        man[f] = sha(p)
agg = hashlib.sha256(json.dumps(man, sort_keys=True).encode()).hexdigest()
out = {"label": label, "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "count": len(man),
       "aggregate_sha256": agg, "files": man}
(LOGS / "phase5m_code_fingerprint_{}.json".format(label)).write_text(
    json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("label:", label, "| files:", len(man), "| aggregate sha256:", agg)
print("json ->", LOGS / "phase5m_code_fingerprint_{}.json".format(label))
