# -*- coding: utf-8 -*-
"""5-C 断点归档：把本阶段全部测试/回归证据打包为 ZIP + 逐文件 sha256 manifest。

包含：
  · docs/regression_2x/logs/phase5c_*.json            （5-C 全部证据）
  · docs/regression_2x/logs/phase5c_rerun/**          （全量回归本轮输出 + 首轮失败留档）
  · docs/regression_2x/phase5c_*.py                   （只读证据脚本）
  · docs/regression_2x/PHASE5C_REPORT.md              （报告草稿，§10/§13/§14 待补）
  · docs/regression_2x/PHASE5C_CHECKPOINT.md          （若已存在；否则跳过）
不含：冻结证据日志本体（它们仍在 logs/ 且与 5-B 逐字节一致）、基线 ZIP、DB。

用法：python docs/regression_2x/phase5c_archive_tests.py [tag]
产出：docs/regression_2x/snapshots/<tag>.zip  +  <tag>.manifest.json
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
TAG = sys.argv[1] if len(sys.argv) > 1 else "phase5c-tests-archive-20260916"
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
for p in sorted(LOGS.glob("phase5c_*")):
    if p.is_file():
        members.append((p, p.relative_to(R2X).as_posix()))
for p in sorted((LOGS / "phase5c_rerun").rglob("*")) if (LOGS / "phase5c_rerun").is_dir() else []:
    if p.is_file():
        members.append((p, p.relative_to(R2X).as_posix()))
for p in sorted(R2X.glob("phase5c_*.py")):
    members.append((p, p.relative_to(R2X).as_posix()))
for name in ("PHASE5C_REPORT.md", "PHASE5C_CHECKPOINT.md"):
    p = R2X / name
    if p.is_file():
        members.append((p, name))

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
       "contents": "5-C 全部证据与回归输出（含首轮 42/43 失败留档 PRESERVED_*）",
       "files": files}
MAN.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
print("archive:", ZIP)
print("files:", len(files), "uncompressed: {:,}".format(total),
      "zip: {:,} bytes".format(ZIP.stat().st_size))
print("zip sha256:", man["zip_sha256"])
print("manifest:", MAN)
