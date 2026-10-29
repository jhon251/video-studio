"""Phase 1.1: add encoding='utf-8', errors='replace' to every subprocess(text=True) call in
src/video_studio that lacks it (AST-precise insertion, no regex guesswork).

Usage: python docs/regression_2x/patch_subprocess_encoding.py [--apply]
"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
APPLY = "--apply" in sys.argv
TARGETS = ("run", "check_output", "Popen", "call", "check_call")
INSERT = ', encoding="utf-8", errors="replace"'

fixed = []
for py in sorted((ROOT / "src" / "video_studio").rglob("*.py")):
    src = py.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src, filename=str(py))
    except SyntaxError:
        continue
    inserts = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = fn.attr if isinstance(fn, ast.Attribute) else (fn.id if isinstance(fn, ast.Name) else "")
        if name not in TARGETS:
            continue
        kw = {k.arg for k in node.keywords if k.arg}
        if "text" not in kw and "universal_newlines" not in kw:
            continue
        if "encoding" in kw:
            continue
        for k in node.keywords:
            if k.arg in ("text", "universal_newlines"):
                inserts.append((k.value.end_lineno, k.value.end_col_offset))
    if not inserts:
        continue
    lines = src.splitlines(keepends=True)
    for lineno, col in sorted(inserts, reverse=True):
        idx = lineno - 1
        line = lines[idx]
        lines[idx] = line[:col] + INSERT + line[col:]
    new = "".join(lines)
    ast.parse(new, filename=str(py))          # 语法自检
    fixed.append((py.relative_to(ROOT).as_posix(), len(inserts)))
    if APPLY:
        py.write_text(new, encoding="utf-8")

print("文件 | 修复调用数" + ("（已写入）" if APPLY else "（dry-run）"))
for f, n in fixed:
    print("  {} | {}".format(f, n))
print("合计: {} 文件 / {} 处调用".format(len(fixed), sum(n for _, n in fixed)))
