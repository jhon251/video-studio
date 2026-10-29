"""2.x baseline snapshot without git: zip of source tree + per-file sha256 manifest.

Includes: src, config, tests, scripts, docs, run.py, pyproject.toml, README.md, CHANGELOG.md, STATUS.md
Excludes: output, projects, models, .venv_tts, tmp_wheels, __pycache__, *.pyc, bin/*.exe (binary tools)

Usage: python docs/regression_2x/make_baseline.py
"""
import hashlib
import json
import sys
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
OUT = ROOT / "docs" / "regression_2x" / "baseline"
OUT.mkdir(parents=True, exist_ok=True)
TAG = sys.argv[1] if len(sys.argv) > 1 else "2.x-final-baseline"
ZIP = OUT / "{}.zip".format(TAG)

INCLUDE_DIRS = ["src", "config", "tests", "scripts", "docs"]
if "--no-docs" in sys.argv:
    # 避免"文档里写自身 zip 哈希"的循环：Preflight 快照只固化代码/配置/测试/脚本
    INCLUDE_DIRS = ["src", "config", "tests", "scripts"]
INCLUDE_FILES = ["run.py", "pyproject.toml", "README.md", "CHANGELOG.md", "STATUS.md"]
SKIP_PARTS = {"__pycache__", ".pytest_cache", "baseline"}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


files = []
for d in INCLUDE_DIRS:
    base = ROOT / d
    if not base.exists():
        continue
    for p in sorted(base.rglob("*")):
        if p.is_file() and not (set(p.parts) & SKIP_PARTS) and p.suffix not in (".pyc",):
            files.append(p)
for f in INCLUDE_FILES:
    p = ROOT / f
    if p.exists():
        files.append(p)

manifest = {"tag": TAG, "created_utc": None, "root": str(ROOT), "file_count": len(files),
            "files": {}}
import datetime
manifest["created_utc"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
manifest["created_utc"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

total = 0
with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for p in files:
        rel = p.relative_to(ROOT).as_posix()
        h = sha(p)
        manifest["files"][rel] = {"sha256": h, "bytes": p.stat().st_size}
        total += p.stat().st_size
        z.write(p, rel)

manifest["source_bytes"] = total
manifest["zip_bytes"] = ZIP.stat().st_size
manifest["zip_sha256"] = sha(ZIP)
(OUT / "baseline_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1),
                                            encoding="utf-8")
print("files: {}  source bytes: {:,}  zip: {} ({:,} bytes)".format(
    len(files), total, ZIP.name, ZIP.stat().st_size))
print("zip sha256:", manifest["zip_sha256"])
print("manifest:", OUT / "baseline_manifest.json")

# 关键文件指纹（供报告引用）
print("\nkey fingerprints:")
for rel in ("config/config.json", "src/video_studio/agents/voice/agent.py",
            "src/video_studio/tools/tts_tool.py", "src/video_studio/core/engine.py",
            "run.py", "pyproject.toml"):
    p = ROOT / rel
    if p.exists():
        print("  {:56s} {}".format(rel, sha(p)[:32]))
