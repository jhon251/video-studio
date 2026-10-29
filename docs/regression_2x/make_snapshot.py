"""Interim snapshot archive (NOT a baseline): freeze the working tree + project DB at a breakpoint.

Usage: python docs/regression_2x/make_snapshot.py <tag>
Writes: docs/regression_2x/snapshots/<tag>.zip  (+ <tag>.db copy of projects/video_studio.db)
        and prints sha256 of both.

与 make_baseline.py 的区别：这只是"断点归档"，**不进入基线表**、不作为验收基准；
内容与基线一致（src/config/tests/scripts + 根文件，排除 docs/projects/output/bin/.venv_tts）。
"""
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
OUT = ROOT / "docs" / "regression_2x" / "snapshots"
OUT.mkdir(parents=True, exist_ok=True)
TAG = sys.argv[1] if len(sys.argv) > 1 else "3.x-wip"
ZIP = OUT / "{}.zip".format(TAG)

INCLUDE_DIRS = ["src", "config", "tests", "scripts"]
INCLUDE_FILES = ["run.py", "pyproject.toml", "README.md", "CHANGELOG.md", "STATUS.md"]
SKIP_PARTS = {"__pycache__", ".pytest_cache", "baseline", "snapshots"}


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


files = []
for d in INCLUDE_DIRS:
    base = ROOT / d
    if base.exists():
        for p in sorted(base.rglob("*")):
            if p.is_file() and not (set(p.parts) & SKIP_PARTS) and p.suffix != ".pyc":
                files.append(p)
for f in INCLUDE_FILES:
    p = ROOT / f
    if p.exists():
        files.append(p)

total = 0
with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for p in files:
        z.write(p, p.relative_to(ROOT).as_posix())
        total += p.stat().st_size
db_src = ROOT / "projects" / "video_studio.db"
db_dst = OUT / "{}.db".format(TAG)
if db_src.is_file():
    shutil.copy2(db_src, db_dst)
info = {"tag": TAG, "files": len(files), "source_bytes": total,
        "zip_bytes": ZIP.stat().st_size, "zip_sha256": sha(ZIP),
        "db_sha256": sha(db_dst) if db_dst.is_file() else None,
        "db_bytes": db_dst.stat().st_size if db_dst.is_file() else None}
(OUT / "{}.json".format(TAG)).write_text(json.dumps(info, ensure_ascii=False, indent=1),
                                        encoding="utf-8")
print(json.dumps(info, ensure_ascii=False, indent=1))
