"""只读：列出"当前工作树"相对**某个基线**的变更（MODIFIED / ADDED / DELETED）。

用法：python docs/regression_2x/baseline_delta.py <tag> [--json]
例：  python docs/regression_2x/baseline_delta.py 4.x-phase4ab-baseline
"""
import hashlib
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
BASE = ROOT / "docs" / "regression_2x" / "baseline"
TAG = sys.argv[1] if len(sys.argv) > 1 else "4.x-phase4ab-baseline"
AS_JSON = "--json" in sys.argv
man = json.loads((BASE / "baseline_manifest_{}.json".format(TAG)).read_text(encoding="utf-8"))

modified, deleted = [], []
for rel, meta in sorted(man["files"].items()):
    p = ROOT / rel
    if not p.is_file():
        deleted.append(rel)
    elif hashlib.sha256(p.read_bytes()).hexdigest() != meta["sha256"]:
        modified.append(rel)

added = []
for d in ("src", "config", "tests", "scripts"):
    base = ROOT / d
    if not base.is_dir():
        continue
    for p in sorted(base.rglob("*")):
        if (p.is_file() and "__pycache__" not in p.parts and ".pytest_cache" not in p.parts
                and p.suffix != ".pyc"):
            rel = p.relative_to(ROOT).as_posix()
            if rel not in man["files"]:
                added.append(rel)
for f in ("run.py", "pyproject.toml", "README.md", "CHANGELOG.md", "STATUS.md"):
    if (ROOT / f).is_file() and f not in man["files"]:
        added.append(f)

out = {"baseline": TAG, "baseline_zip_sha256": man.get("zip_sha256"),
       "modified": modified, "added": added, "deleted": deleted,
       "counts": {"modified": len(modified), "added": len(added), "deleted": len(deleted)}}
if AS_JSON:
    print(json.dumps(out, ensure_ascii=False, indent=1))
else:
    print("相对基线 {} 的变更：修改 {} / 新增 {} / 删除 {}".format(
        TAG, len(modified), len(added), len(deleted)))
    for x in modified:
        print("  MODIFIED {}".format(x))
    for x in added:
        print("  ADDED    {}".format(x))
    for x in deleted:
        print("  DELETED  {}".format(x))
