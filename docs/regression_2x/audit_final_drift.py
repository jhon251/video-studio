# -*- coding: utf-8 -*-
"""审计 I：当前工作树相对 5.x-final-baseline 的漂移 —— 从基线 ZIP 取出旧版与现行版逐行对比（只读）。

产出：docs/regression_2x/logs/audit_final_drift.json（含 diff 摘要）
"""
import difflib
import hashlib
import json
import pathlib
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
ZIP = ROOT / "docs" / "regression_2x" / "baseline" / "5.x-final-baseline.zip"
MAN = ROOT / "docs" / "regression_2x" / "baseline" / "baseline_manifest_5.x-final-baseline.json"
OUT = ROOT / "docs" / "regression_2x" / "logs" / "audit_final_drift.json"


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


man = json.loads(MAN.read_text(encoding="utf-8"))
drift, added, deleted = [], [], []
for rel, rec in sorted(man["files"].items()):
    p = ROOT / rel
    if not p.is_file():
        deleted.append(rel)
    elif sha(p) != rec["sha256"]:
        drift.append(rel)
for d in ("src", "config", "tests", "scripts"):
    base = ROOT / d
    if not base.is_dir():
        continue
    for p in sorted(base.rglob("*")):
        rel = p.relative_to(ROOT).as_posix()
        if p.is_file() and rel not in man["files"] and "__pycache__" not in p.parts:
            added.append(rel)

print("=== 相对 5.x-final-baseline 的漂移 ===")
print("修改 {} / 新增 {} / 删除 {}".format(len(drift), len(added), len(deleted)))
for x in drift:
    print("   MODIFIED", x)
for x in added[:20]:
    print("   ADDED   ", x)
for x in deleted[:20]:
    print("   DELETED ", x)

details = []
with zipfile.ZipFile(ZIP) as z:
    for rel in drift:
        try:
            old = z.read(rel).decode("utf-8-sig", "replace").splitlines()
        except KeyError:
            details.append({"file": rel, "note": "基线 ZIP 中不存在"})
            continue
        new = (ROOT / rel).read_text(encoding="utf-8-sig", errors="replace").splitlines()
        diff = list(difflib.unified_diff(old, new, fromfile="baseline/" + rel,
                                         tofile="current/" + rel, lineterm="", n=1))
        changed = [ln for ln in diff if ln.startswith(("+", "-")) and not ln.startswith(("+++", "---"))]
        details.append({"file": rel, "old_sha256": man["files"][rel]["sha256"][:16],
                        "new_sha256": sha(ROOT / rel)[:16],
                        "old_lines": len(old), "new_lines": len(new),
                        "changed_lines": len(changed), "diff": diff[:120]})
        print("\n--- {} （旧 {} 行 → 新 {} 行，变更行 {}）---".format(
            rel, len(old), len(new), len(changed)))
        for ln in diff[:40]:
            print("   ", ln[:160])
        if len(diff) > 40:
            print("    …（diff 共 {} 行，完整内容见 JSON）".format(len(diff)))

res = {"baseline": "5.x-final-baseline", "zip_sha256": sha(ZIP), "modified": drift,
       "added": added, "deleted": deleted, "details": details}
OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print("\nwritten", OUT)
