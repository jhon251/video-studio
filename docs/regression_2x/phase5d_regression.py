# -*- coding: utf-8 -*-
"""5-D 全量回归编排（3-A～5-C）：跑完整回归电池，**不覆盖**任何既有（冻结）证据日志。

与 `phase5c_regression.py` 的区别：本阶段把 **5-C 的只读脚本**也纳入电池（回归覆盖 3-A～5-C），
并使用独立的备份/输出目录（`logs_5c_frozen/`、`logs/phase5d_rerun/`），不触碰 5-C 的回归证据。

用法：python docs/regression_2x/phase5d_regression.py [--skip name,name]
"""
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
LOGS = ROOT / "docs" / "regression_2x" / "logs"
BAK = ROOT / "docs" / "regression_2x" / "logs_5c_frozen"
RERUN = LOGS / "phase5d_rerun"
SUMMARY = LOGS / "phase5d_regression_summary.json"
PY = r"C:\python3.13\python.exe"
PID = "p_f4b466a4a024"
V6 = "a_fa4716cffb26"

STEPS = [
    ("3a_real_chain", [PY, "docs/regression_2x/phase3a_real_chain.py", "--resume", PID]),
    ("3a_regression_batch", [PY, "docs/regression_2x/phase3a_regression_batch.py"]),
    ("3b_audit", [PY, "docs/regression_2x/phase3b_audit.py"]),
    ("3b_failure_paths", [PY, "docs/regression_2x/phase3b_failure_paths.py"]),
    ("4ab_evidence", [PY, "docs/regression_2x/phase4ab_evidence.py"]),
    ("4c_evidence", [PY, "docs/regression_2x/phase4c_evidence.py"]),
    ("4d_evidence", [PY, "docs/regression_2x/phase4d_evidence.py"]),
    ("4e_ab_benchmark", [PY, "docs/regression_2x/phase4e_ab_benchmark.py"]),
    ("4f_evidence", [PY, "docs/regression_2x/phase4f_evidence.py"]),
    ("4g_evidence", [PY, "docs/regression_2x/phase4g_evidence.py"]),
    ("4x_audit", [PY, "docs/regression_2x/phase4x_audit.py"]),
    ("5a_evidence", [PY, "docs/regression_2x/phase5a_evidence.py"]),
    ("5b_evidence", [PY, "docs/regression_2x/phase5b_evidence.py"]),
    ("5c_append_only", [PY, "docs/regression_2x/phase5c_append_only.py"]),
    ("5c_db_append_only", [PY, "docs/regression_2x/phase5c_db_append_only.py"]),
    ("5c_verify_film", [PY, "docs/regression_2x/phase5c_verify_film.py", V6]),
    ("5c_failclosed", [PY, "docs/regression_2x/phase5c_failclosed.py"]),
    ("5c_checkpoint_check", [PY, "docs/regression_2x/phase5c_checkpoint_check.py"]),
    ("5d_mm_temporal_test", [PY, "tests/mm_temporal_test.py"]),
    ("unit_suites", [PY, "docs/regression_2x/run_all_suites.py"]),
]


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def manifest(root, skip_prefixes=()):
    out = {}
    for p in sorted(pathlib.Path(root).rglob("*")):
        if p.is_file():
            rel = str(p.relative_to(root)).replace("\\", "/")
            if any(rel.startswith(x) for x in skip_prefixes):
                continue
            out[rel] = sha(p)
    return out


skip = set()
if "--skip" in sys.argv:
    skip = set(sys.argv[sys.argv.index("--skip") + 1].split(","))

RERUN.mkdir(parents=True, exist_ok=True)
# 冻结集：既有证据日志（含 5-C 的 phase5c_*），排除本阶段自己的输出与备份/回归目录
FROZEN_SKIP = ("phase5d_", "phase5c_rerun/", "phase5d_rerun/", "phase5d_frames/")
pre = manifest(LOGS, FROZEN_SKIP)

need_copy = True
if BAK.exists() and any(BAK.iterdir()):
    bman = {k: v for k, v in manifest(BAK).items() if k != "MANIFEST.json"}
    need_copy = bman != pre
    print("backup exists; consistent with current frozen logs:", not need_copy)
if need_copy:
    if BAK.exists():
        shutil.rmtree(BAK)
    BAK.mkdir(parents=True, exist_ok=True)
    for rel in pre:
        dst = BAK / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(LOGS / rel, dst)
    (BAK / "MANIFEST.json").write_text(json.dumps(pre, ensure_ascii=False, indent=1),
                                       encoding="utf-8")
    print("backed up", len(pre), "frozen log files ->", BAK)

results = []
for name, argv in STEPS:
    if name in skip:
        results.append({"step": name, "skipped": True})
        print("[skip]", name, flush=True)
        continue
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
frozen_restored = all(post2.get(k) == v for k, v in pre.items())

prev = {}
if SUMMARY.is_file():
    try:
        prev = json.loads(SUMMARY.read_text(encoding="utf-8"))
    except (ValueError, json.JSONDecodeError):
        prev = {}
prev_steps = {s.get("step"): s for s in (prev.get("steps") or [])}
for i, r in enumerate(results):
    if r.get("skipped") and r["step"] in prev_steps:
        prev_steps[r["step"]]["carried_over_from_previous_run"] = True
        results[i] = prev_steps[r["step"]]

summary = {
    "steps": results,
    "frozen_logs_pre_count": len(pre), "frozen_logs_changed": changed,
    "frozen_logs_added": added, "frozen_logs_deleted": deleted,
    "frozen_logs_restored": frozen_restored, "frozen_backup": str(BAK),
    "all_rc_zero_raw": all(r.get("rc") == 0 for r in results if not r.get("skipped")),
    "note": "既有冻结证据日志（含 5-C 全部证据）已原样恢复；本轮运行结果保留在 logs/phase5d_rerun/",
}
SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")

print("\n" + "=" * 90)
print("冻结日志:", len(pre), "| 改变", len(changed), "| 新增", len(added), "| 删除", len(deleted))
print("冻结日志已恢复:", frozen_restored)
print("全部 rc=0（原始）:", summary["all_rc_zero_raw"])
print("summary ->", SUMMARY)
