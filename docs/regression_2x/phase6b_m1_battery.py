# -*- coding: utf-8 -*-
"""6-A / M2 全量回归电池：**与 5-F/5-G/5-J/5-L/5-M/6-A(M1) 电池同一步骤序列**（仅路径适配，不改逻辑）。

步骤表由 **AST 解析** `phase5f_regression.py` 的 `STEPS` 得到；使用 6-B/M1 专用备份/输出目录
（`logs_6b_m1_frozen/`、`logs/phase6b_m1_rerun/`），**不改动任何历史备份、M1/M2 证据与基线**。

用法: python docs/regression_2x/phase6b_m1_battery.py
产出: logs/phase6b_m1_regression_summary.json + logs/phase6b_m1_rerun/**
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
BAK = ROOT / "docs" / "regression_2x" / "logs_6b_m1_frozen"
RERUN = LOGS / "phase6b_m1_rerun"
SUMMARY = LOGS / "phase6b_m1_regression_summary.json"
REF = ROOT / "docs" / "regression_2x" / "phase5f_regression.py"
PY = sys.executable


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


tree = ast.parse(REF.read_text(encoding="utf-8"))
ns = {}
for node in tree.body:
    if (isinstance(node, ast.Assign) and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)):
        ns[node.targets[0].id] = node.value.value
ref_steps = None
for node in tree.body:
    if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "STEPS" for t in node.targets):
        exec(compile(ast.Module(body=[node], type_ignores=[]), "<steps>", "exec"), ns)  # noqa: S102
        ref_steps = [(str(i[0]), [str(x) for x in i[1]]) for i in ns["STEPS"]]
if not ref_steps:
    print("ABORT: 无法从 phase5f_regression.py 解析 STEPS")
    sys.exit(2)
print("电池步骤（{} 步）: {}".format(len(ref_steps), ", ".join(n for n, _ in ref_steps)))

FROZEN_SKIP = ("phase5f_", "phase5l_", "phase5m_", "phase6a_", "phase5c_rerun/", "phase5d_rerun/",
               "phase5e_rerun/", "phase5f_rerun/", "phase5l_rerun/", "phase5m_rerun/",
               "phase6a_rerun/", "phase5d_frames/", "phase5e_frames/")


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
# ---- M3：可续跑（--resume）+ 允许某步"外部前台执行"（--skip，需外部记录，缺记录则 rc=None）----
ARGS = sys.argv[1:]
RESUME = "--resume" in ARGS
SKIP: set = set()
for _i, _a in enumerate(ARGS):
    if _a == "--skip" and _i + 1 < len(ARGS):
        SKIP = {x.strip() for x in ARGS[_i + 1].split(",") if x.strip()}
EXTERNAL = LOGS / "phase6b_m1_external_steps.json"
ext = json.loads(EXTERNAL.read_text(encoding="utf-8")) if EXTERNAL.is_file() else {}

pre = manifest(LOGS, FROZEN_SKIP)
if RESUME and (BAK / "MANIFEST.json").is_file():
    _raw = json.loads((BAK / "MANIFEST.json").read_text(encoding="utf-8"))
    pre = _raw["files"] if isinstance(_raw, dict) and "files" in _raw else _raw
    pre = {k: v for k, v in pre.items() if k != "MANIFEST.json"}
    print("--resume：沿用已有冻结快照 {}（{} 文件），**不重新备份**".format(BAK, len(pre)), flush=True)
else:
    if BAK.exists():
        shutil.rmtree(BAK)
    BAK.mkdir(parents=True, exist_ok=True)
    for rel in pre:
        dst = BAK / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(LOGS / rel, dst)
    (BAK / "MANIFEST.json").write_text(json.dumps(pre, ensure_ascii=False, indent=1),
                                       encoding="utf-8")
    print("冻结日志 {} 个文件 -> {}".format(len(pre), BAK), flush=True)

results = []
t_all = time.time()
PROGRESS = LOGS / "phase6b_m1_regression_progress.json"
_done = {}
if RESUME and PROGRESS.is_file():
    try:
        _done = {r["step"]: r for r in
                 json.loads(PROGRESS.read_text(encoding="utf-8")).get("results", [])}
    except Exception:                                            # noqa: BLE001
        _done = {}


def _progress():
    """每步落盘：外部杀死时仍保留已完成步骤的 rc 与 tail。"""
    rcs = [r.get("rc") for r in results]
    PROGRESS.write_text(json.dumps(
        {"stage": "6-B/M1", "steps_done": len(results), "steps_total": len(ref_steps),
         "all_rc_zero_so_far": (None if any(x is None for x in rcs) else all(x == 0 for x in rcs)),
         "rc_nonzero": [r["step"] for r in results if r.get("rc") not in (0, None)],
         "rc_pending": [r["step"] for r in results if r.get("rc") is None],
         "results": results}, ensure_ascii=False, indent=1), encoding="utf-8")


for name, argv in ref_steps:
    _ext_all = ext.get("steps", ext) or {}
    _ext_rec = _ext_all.get(name) if name in SKIP else None
    if name in _done and not (_ext_rec and _done[name].get("rc") is None):
        results.append(_done[name])
        _progress()
        print("[{:22s}] 跳过（已记录 rc={}）".format(name, _done[name].get("rc")), flush=True)
        continue
    if name in SKIP:
        _e = _ext_rec or {}
        rec = {"step": name, "argv": [], "rc": _e.get("rc"), "seconds": _e.get("seconds"),
               "executed": "externally", "evidence": _e.get("evidence"),
               "tail": ["外部逐项执行：" + str(_e.get("evidence"))]}
        results = [r for r in results if r["step"] != name]      # 覆盖旧的 rc=None 记录
        results.append(rec)
        _progress()
        print("[{:22s}] EXTERNAL rc={} （{}）".format(name, rec["rc"], rec["evidence"]),
              flush=True)
        continue
    argv = [PY if a == r"C:\python3.13\python.exe" else a for a in argv]
    t0 = time.time()
    r = subprocess.run(argv, cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    (RERUN / (name + ".log")).write_text(out, encoding="utf-8")
    tail = [ln.strip() for ln in out.strip().splitlines() if ln.strip()][-14:]
    rec = {"step": name, "argv": argv, "rc": r.returncode, "seconds": round(time.time() - t0, 1),
           "executed": "battery", "tail": tail}
    results.append(rec)
    _progress()
    print("\n[{:22s}] rc={} ({}s)".format(name, r.returncode, rec["seconds"]), flush=True)
    for ln in tail:
        print("    ", ln[:170], flush=True)

print("\n本次续跑耗时 {:.1f}s（各步 seconds 之和见汇总）".format(time.time() - t_all))
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
rcs = [r.get("rc") for r in results]
all_zero = None if any(x is None for x in rcs) else all(x == 0 for x in rcs)
summary = {"stage": "6-B/M1", "steps": results, "steps_count": len(results),
           "frozen_logs_pre_count": len(pre), "frozen_logs_changed": changed,
           "frozen_logs_added": added, "frozen_logs_deleted": deleted,
           "frozen_logs_restored": frozen_restored, "frozen_backup": str(BAK),
           "all_rc_zero_raw": all_zero,
           "rc_nonzero": [r["step"] for r in results if r.get("rc") not in (0, None)],
           "rc_pending": [r["step"] for r in results if r.get("rc") is None],
           "steps_executed_externally": [r["step"] for r in results
                                         if r.get("executed") == "externally"],
           "sum_steps_seconds": round(sum(r["seconds"] or 0 for r in results), 1),
           "seconds_this_launch": round(time.time() - t_all, 1),
           "note": "步骤序列取自 phase5f_regression.py（AST 解析）；6-B/M1 专用备份/输出路径；"
                   "不改动历史备份与任何基线；`executed=externally` 的步骤由外部前台运行，"
                   "其 rc 与证据取自 phase6b_m1_external_steps.json（未伪造）"}
SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
print("=" * 90)
print("冻结日志:", len(pre), "| 改变", len(changed), "| 新增", len(added), "| 删除", len(deleted))
print("冻结日志已恢复:", frozen_restored)
print("全部 rc=0（原始）:", summary["all_rc_zero_raw"], "| 非零:", summary["rc_nonzero"])
print("summary ->", SUMMARY)
