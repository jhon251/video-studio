# -*- coding: utf-8 -*-
"""5-K 杂物清理：把临时备份/杂物从**受基线收录**的目录移出到隔离目录（可回溯，不删除内容）。

- `config/config.mock.json.bak` → `output/_quarantine_20260921/`（config/ 在基线内，必须移出）
- `output/run05/fix1_backup_orchestrator_core.py.bak` → 同一隔离目录（虽不在基线内，一并归置）
写入 `output/_quarantine_20260921/MANIFEST.json`（含原路径、大小、sha256、移动时间）。

用法：python docs/regression_2x/phase5k_cleanup.py
"""
import hashlib
import json
import pathlib
import shutil
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
QDIR = ROOT / "output" / "_quarantine_20260921"
TARGETS = [
    ROOT / "config" / "config.mock.json.bak",
    ROOT / "output" / "run05" / "fix1_backup_orchestrator_core.py.bak",
]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


QDIR.mkdir(parents=True, exist_ok=True)
man_p = QDIR / "MANIFEST.json"
man = json.loads(man_p.read_text(encoding="utf-8")) if man_p.is_file() else {"moved": []}
for src in TARGETS:
    if not src.is_file():
        print("跳过（不存在）:", src.relative_to(ROOT))
        continue
    dst = QDIR / (src.parent.name + "__" + src.name)
    rec = {"original": str(src.relative_to(ROOT)), "quarantined": str(dst.relative_to(ROOT)),
           "bytes": src.stat().st_size, "sha256": sha(src), "moved_at": time.time()}
    shutil.move(str(src), str(dst))
    man["moved"].append(rec)
    print("已隔离:", rec["original"], "→", rec["quarantined"], rec["bytes"], "B", rec["sha256"][:12])
man["note"] = ("5-K（Post-Final Maintenance）：临时备份/杂物移出受基线收录目录；"
               "内容原样保留在隔离目录，可随时回溯，且不会被收录进任何 baseline。")
man_p.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
print("manifest:", man_p.relative_to(ROOT), "| 条目:", len(man["moved"]))
