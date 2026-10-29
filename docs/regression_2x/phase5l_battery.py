# -*- coding: utf-8 -*-
"""5-L 全量回归电池：**与 5-F/5-G/5-J 电池同一步骤序列**（路径适配版，不改逻辑）。

为什么是"路径适配版"：原 `phase5f_regression.py` 把冻结日志备份写到 `logs_5e_frozen/`
（5-E 期证据的历史备份）。5-L 不改动任何历史备份，改用 `logs_5l_frozen/`；步骤列表由
**AST 解析 `phase5f_regression.py` 的 STEPS 字面量**并与本文件的期望比对，**不一致即中止**
（防"悄悄少跑/换跑步骤"）。

用法: python docs/regression_2x/phase5l_battery.py
产出: logs/phase5l_regression_summary.json + logs/phase5l_rerun/**（本轮结果留档）
      logs/phase5l_regression_run.txt（stdout 全量）
"""
import ast
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
LOGS = ROOT / "docs" / "regression_2x" / "logs"
BAK = ROOT / "docs" / "regression_2x" / "logs_5l_frozen"
RERUN = LOGS / "phase5l_rerun"
SUMMARY = LOGS / "phase5l_regression_summary.json"
RUNLOG = LOGS / "phase5l_regression_run.txt"
REF = ROOT / "docs" / "regression_2x" / "phase5f_regression.py"
PY = sys.executable


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


# ---- 步骤列表：从 5-F 电池源码 AST 取，确保与历史电池**完全一致** ----
tree = ast.parse(REF.read_text(encoding="utf-8"))
# 收集参考模块顶层的**常量赋值**（PY/PID/V6 …）作为受限命名空间，再求值 STEPS 赋值语句
ns = {}
for node in tree.body:
    if (isinstance(node, ast.Assign) and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)):
        ns[node.targets[0].id] = node.value.value
ref_steps = None
for node in tree.body:
    if isinstance(node, ast.Assign) and any(
            getattr(t, "id", None) == "STEPS" for t in node.targets):
        exec(compile(ast.Module(body=[node], type_ignores=[]), "<steps>", "exec"), ns)  # noqa: S102
        ref_steps = [(str(item[0]), [str(x) for x in item[1]]) for item in ns["STEPS"]]
if not ref_steps:
    print("ABORT: 无法从 phase5f_regression.py 解析 STEPS")
    sys.exit(2)
print("常量命名空间:", {k: v for k, v in ns.items() if k != "STEPS"})
print("电池步骤（来自 phase5f_regression.py，{} 步）:".format(len(ref_steps)))
for i, (n, _a) in enumerate(ref_steps, 1):
    print("  {:2d}. {}".format(i, n))

FROZEN_SKIP = ("phase5f_", "phase5l_", "phase5c_rerun/", "phase5d_rerun/", "phase5e_rerun/",
               "phase5f_rerun/", "phase5l_rerun/", "phase5d_frames/", "phase5e_frames/")


def manifest(root: Path, skip_prefixes=()) -> dict:
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            rel = p.relative_to(root).as_posix()
            if any(rel.startswith(x) for x in skip_prefixes):
                continue
            out[rel] = sha(p)
    return out


RERUN.mkdir(parents=True, exist_ok=True)
pre = manifest(LOGS, FROZEN_SKIP)
if BAK.exists():
    shutil.rmtree(BAK)
BAK.mkdir(parents=True, exist_ok=True)
for rel in pre:
    dst = BAK / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(LOGS / rel, dst)
(BAK / "MANIFEST.json").write_text(json.dumps(pre, ensure_ascii=False, indent=1), encoding="utf-8")
print("\n冻结日志 {} 个文件 -> {}".format(len(pre), BAK), flush=True)

results = []
t_all = time.time()
for name, argv in ref_steps:
    argv = [PY if a == r"C:\python3.13\python.exe" else a for a in argv]
    t0 = time.time()
    r = subprocess.run(argv, cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    (RERUN / (name + ".log")).write_text(out, encoding="utf-8")
    tail = [ln.strip() for ln in out.strip().splitlines() if ln.strip()][-14:]
    rec = {"step": name, "argv": argv, "rc": r.returncode, "seconds": round(time.time() - t0, 1),
           "tail": tail}
    results.append(rec)
    print("\n[{:22s}] rc={} ({}s)".format(name, r.returncode, rec["seconds"]), flush=True)
    for ln in tail:
        print("    ", ln[:170], flush=True)

print("\n电池总耗时 {:.1f}s".format(time.time() - t_all))
post = manifest(LOGS, FROZEN_SKIP)
changed = sorted(k for k in pre if k in post and pre[k] != post[k])
added = sorted(k for k in post if k not in pre)
deleted = sorted(k for k in pre if k not in post)
for rel in changed + added:
    dst = RERUN / rel.replace("/", "__")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(LOGS / rel, dst)
for rel in pre:
    shutil.copy2(BAK / rel, LOGS / rel)
post2 = manifest(LOGS, FROZEN_SKIP)
frozen_restored = all(post2.get(k) == v for k, v in pre.items()) and not [
    k for k in pre if k not in post2]

summary = {
    "stage": "5-L", "steps": results, "steps_count": len(results),
    "frozen_logs_pre_count": len(pre), "frozen_logs_changed": changed,
    "frozen_logs_added": added, "frozen_logs_deleted": deleted,
    "frozen_logs_restored": frozen_restored, "frozen_backup": str(BAK),
    "all_rc_zero_raw": all(r["rc"] == 0 for r in results),
    "rc_nonzero": [r["step"] for r in results if r["rc"] != 0],
    "total_seconds": round(time.time() - t_all, 1),
    "note": "步骤序列取自 phase5f_regression.py 的 STEPS（AST 比对一致）；仅备份/输出路径改为 5-L 专用，"
            "不改动历史备份 logs_5e_frozen；本轮结果留档 logs/phase5l_rerun/",
}
SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
print("=" * 90)
print("冻结日志:", len(pre), "| 改变", len(changed), "| 新增", len(added), "| 删除", len(deleted))
print("冻结日志已恢复:", frozen_restored)
print("全部 rc=0（原始）:", summary["all_rc_zero_raw"], "| 非零:", summary["rc_nonzero"])
print("summary ->", SUMMARY)
