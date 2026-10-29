# -*- coding: utf-8 -*-
"""5-E 测试与回归证据归档：打包 ZIP + 逐文件 sha256 manifest。

包含：logs/phase5e_*.json、logs/phase5e_rerun/**、docs/regression_2x/phase5e_*.py、
      PHASE5E_REPORT.md、PHASE5E_CHECKPOINT.md、tests/mm_quality_test.py、
      tests/fixtures/mm_truth_set_v1.json（冻结真值集）、src 下 5-E 新增模块。

用法：python docs/regression_2x/phase5e_archive.py [tag]
产出：docs/regression_2x/snapshots/<tag>.zip + <tag>.manifest.json
"""
import hashlib
import json
import sys
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
R2X = ROOT / "docs" / "regression_2x"
LOGS = R2X / "logs"
OUT = R2X / "snapshots"
TAG = sys.argv[1] if len(sys.argv) > 1 else "phase5e-tests-archive-20260917"
ZIP = OUT / "{}.zip".format(TAG)
MAN = OUT / "{}.manifest.json".format(TAG)
OUT.mkdir(parents=True, exist_ok=True)


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


members = []
for p in sorted(LOGS.glob("phase5e_*")):
    if p.is_file():
        members.append((p, p.relative_to(R2X).as_posix()))
for p in sorted((LOGS / "phase5e_rerun").rglob("*")) if (LOGS / "phase5e_rerun").is_dir() else []:
    if p.is_file():
        members.append((p, p.relative_to(R2X).as_posix()))
for p in sorted(R2X.glob("phase5e_*.py")):
    members.append((p, p.relative_to(R2X).as_posix()))
for name in ("PHASE5E_REPORT.md", "PHASE5E_CHECKPOINT.md"):
    p = R2X / name
    if p.is_file():
        members.append((p, name))
for rel in ("tests/mm_quality_test.py", "tests/fixtures/mm_truth_set_v1.json",
            "src/video_studio/core/mm_quality.py", "src/video_studio/ops/mm_quality.py",
            "src/video_studio/cli.py", "tests/mm_temporal_test.py",
            "src/video_studio/core/mm_temporal.py", "src/video_studio/ops/mm_temporal.py"):
    p = ROOT / rel
    if p.is_file():
        members.append((p, rel))

files = {}
total = 0
with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for p, rel in members:
        data = p.read_bytes()
        z.writestr(rel, data)
        files[rel] = {"sha256": sha_bytes(data), "bytes": len(data)}
        total += len(data)

man = {"tag": TAG, "root": str(ROOT), "file_count": len(files), "uncompressed_bytes": total,
       "zip_bytes": ZIP.stat().st_size, "zip_sha256": sha_file(ZIP),
       "contents": "5-E 全部证据与 3-A～5-D 回归输出（含冻结真值集与校准报告）", "files": files}
MAN.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
print("archive:", ZIP)
print("files:", len(files), "uncompressed: {:,}".format(total),
      "zip: {:,} bytes".format(ZIP.stat().st_size))
print("zip sha256:", man["zip_sha256"])
print("manifest:", MAN)
