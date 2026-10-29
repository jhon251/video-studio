# -*- coding: utf-8 -*-
"""5-K：全量回归前冻结 `logs/` 备份（回归后逐文件回拷依据）。

只写 `docs/regression_2x/logs_5k_frozen/`（不在基线内），不修改 `logs/` 本体。
用法: python docs/regression_2x/phase5k_freeze_logs.py
"""
import hashlib
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
LOGS = ROOT / "docs" / "regression_2x" / "logs"
BAK = ROOT / "docs" / "regression_2x" / "logs_5k_frozen"


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def manifest(d: Path) -> dict:
    out = {}
    for p in sorted(d.rglob("*")):
        if p.is_file():
            out[p.relative_to(d).as_posix()] = sha(p)
    return out


if BAK.exists():
    print("备份目录已存在，改为原地复核（不覆盖）:", BAK)
else:
    shutil.copytree(LOGS, BAK)

man = manifest(BAK)
live = manifest(LOGS)
man.pop("MANIFEST.json", None)
same = man == live
(BAK / "MANIFEST.json").write_text(json.dumps(
    {"frozen_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "source": str(LOGS),
     "file_count": len(man), "files": man}, ensure_ascii=False, indent=1), encoding="utf-8")
print("frozen logs:", len(man), "files | backup == live:", same)
print("backup dir:", BAK)
