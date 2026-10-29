# -*- coding: utf-8 -*-
"""把断点卡片自身的 sha256 补进归档 manifest（避免 ZIP 内自包含的循环）。

用法：python docs/regression_2x/phase5c_archive_stamp.py [tag]
"""
import hashlib
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
R2X = Path(r"C:\mp4agent\video-studio\docs\regression_2x")
TAG = sys.argv[1] if len(sys.argv) > 1 else "phase5c-tests-archive-20260916"
MAN = R2X / "snapshots" / "{}.manifest.json".format(TAG)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


man = json.loads(MAN.read_text(encoding="utf-8"))
extra = {}
for name in ("PHASE5C_CHECKPOINT.md", "PHASE5C_REPORT.md"):
    p = R2X / name
    extra[name.lower().replace(".", "_") + "_sha256"] = sha(p) if p.is_file() else None
    extra[name.lower().replace(".", "_") + "_bytes"] = p.stat().st_size if p.is_file() else None
for name in ("phase5c_checkpoint_check.py", "phase5c_archive_tests.py", "phase5c_archive_stamp.py"):
    p = R2X / name
    extra[name.replace(".", "_") + "_sha256"] = sha(p) if p.is_file() else None
man["sidecar_hashes"] = extra
man["note_sidecar"] = ("本 manifest 内 files 为 ZIP 内条目哈希；sidecar_hashes 为归档时点仍未入包的"
                       "文档/脚本哈希（CHECKPOINT 在归档后写成，故只登记于此处）")
MAN.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
print("manifest updated:", MAN)
print(json.dumps(extra, ensure_ascii=False, indent=1))
