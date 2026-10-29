# -*- coding: utf-8 -*-
"""5-F 测试与回归证据归档：打包 ZIP + 逐文件 sha256 manifest。

包含：logs/phase5f_*.json、logs/phase5f_rerun/**、docs/regression_2x/phase5f_*.py、
      PHASE5F_REPORT.md、PHASE5F_MULTIMODAL_DOD.md、PHASE5F_CHECKPOINT.md、
      tests/mm_judge_test.py、tests/fixtures/mm_judge_truth_v1.json、
      src 下 5-F 新增模块、以及三层/5-E 的关键冻结文件（真值集、模块）。

用法：python docs/regression_2x/phase5f_archive.py [tag]
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
TAG = sys.argv[1] if len(sys.argv) > 1 else "phase5f-tests-archive-20260917"
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
for p in sorted(LOGS.glob("phase5f_*")):
    if p.is_file():
        members.append((p, p.relative_to(R2X).as_posix()))
for p in sorted((LOGS / "phase5f_rerun").rglob("*")) if (LOGS / "phase5f_rerun").is_dir() else []:
    if p.is_file():
        members.append((p, p.relative_to(R2X).as_posix()))
for p in sorted(R2X.glob("phase5f_*.py")):
    members.append((p, p.relative_to(R2X).as_posix()))
for name in ("PHASE5F_REPORT.md", "PHASE5F_MULTIMODAL_DOD.md", "PHASE5F_CHECKPOINT.md"):
    p = R2X / name
    if p.is_file():
        members.append((p, name))
for rel in ("tests/mm_judge_test.py", "tests/fixtures/mm_judge_truth_v1.json",
            "tests/fixtures/mm_truth_set_v1.json",
            "src/video_studio/core/mm_judge.py", "src/video_studio/ops/mm_judge.py",
            "src/video_studio/core/mm_quality.py", "src/video_studio/ops/mm_quality.py",
            "src/video_studio/core/mm_temporal.py", "src/video_studio/core/multimodal.py",
            "src/video_studio/cli.py", "docs/regression_2x/logs/phase5e_quality.json",
            "docs/regression_2x/logs/phase5e_evidence.json"):
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
       "contents": "5-F 全部证据与 3-A～5-E 回归输出（含 Judge 真值覆盖层、DoD、三层冻结件）",
       "files": files}
MAN.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
print("archive:", ZIP)
print("files:", len(files), "uncompressed: {:,}".format(total),
      "zip: {:,} bytes".format(ZIP.stat().st_size))
print("zip sha256:", man["zip_sha256"])
print("manifest:", MAN)
