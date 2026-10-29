# -*- coding: utf-8 -*-
"""5-C 全量回归编排（3-A～5-B）：跑完整回归电池，**不覆盖**任何既有（冻结）证据日志。

做法：
  1) 先把 `docs/regression_2x/logs/` 现有文件做成快照清单 + 备份到 `logs_5b_frozen/`；
  2) 依次运行 3-A/3-B/4-A…4-G/5-A/5-B 的证据脚本与测试套件，逐条记录 rc 与关键输出；
  3) 把本次运行**改动/新增**的日志复制到 `logs/phase5c_rerun/`（作为 5-C 的新证据）；
  4) 从备份恢复所有既有日志文件 → 冻结证据（5-A/5-B 等）逐字节不变；
  5) 输出 `logs/phase5c_regression_summary.json`。

用法：python docs/regression_2x/phase5c_regression.py [--skip name,name]
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
BAK = ROOT / "docs" / "regression_2x" / "logs_5b_frozen"
RERUN = LOGS / "phase5c_rerun"
PY = r"C:\python3.13\python.exe"
PID = "p_f4b466a4a024"

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
    ("unit_suites", [PY, "docs/regression_2x/run_all_suites.py"]),
]


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def manifest(root):
    out = {}
    for p in sorted(pathlib.Path(root).rglob("*")):
        if p.is_file():
            out[str(p.relative_to(root)).replace("\\", "/")] = sha(p)
    return out


skip = set()
if "--skip" in sys.argv:
    skip = set(sys.argv[sys.argv.index("--skip") + 1].split(","))

RERUN.mkdir(parents=True, exist_ok=True)
pre = manifest(LOGS)
RERUN.mkdir(parents=True, exist_ok=True)
pre = {k: v for k, v in manifest(LOGS).items() if not k.startswith("phase5c_rerun/")}

# ---- 备份（仅首次；若已存在则校验一致，避免覆盖冻结备份） ----
need_copy = True
if BAK.exists() and any(BAK.iterdir()):
    bman = {k: v for k, v in manifest(BAK).items() if k != "MANIFEST.json"}
    need_copy = bman != pre
    print("backup exists; consistent with current logs:", not need_copy)
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
    tail = [ln.strip() for ln in out.strip().splitlines() if ln.strip()][-12:]
    rec = {"step": name, "argv": argv, "rc": r.returncode, "seconds": round(time.time() - t0, 1),
           "tail": tail}
    results.append(rec)
    print("\n[{:20s}] rc={} ({}s)".format(name, r.returncode, rec["seconds"]), flush=True)
    for ln in tail:
        print("    ", ln[:170], flush=True)

# ---- 差异 → 复制到 rerun 目录 → 恢复冻结日志 ----
post = {k: v for k, v in manifest(LOGS).items() if not k.startswith("phase5c_rerun/")}
changed = sorted(k for k in pre if k in post and pre[k] != post[k])
added = sorted(k for k in post if k not in pre)
deleted = sorted(k for k in pre if k not in post)
for rel in changed + added:
    dst = RERUN / rel.replace("/", "__")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(LOGS / rel, dst)
restored = []
for rel in pre:
    shutil.copy2(BAK / rel, LOGS / rel)
    restored.append(rel)
post2 = {k: v for k, v in manifest(LOGS).items() if not k.startswith("phase5c_rerun/")}
frozen_restored = all(post2.get(k) == v for k, v in pre.items())

SUMMARY = LOGS / "phase5c_regression_summary.json"
prev = {}
if SUMMARY.is_file():
    try:
        prev = json.loads(SUMMARY.read_text(encoding="utf-8"))
    except (ValueError, json.JSONDecodeError):
        prev = {}
prev_steps = {s.get("step"): s for s in (prev.get("steps") or [])}
for r in results:
    if r.get("skipped") and r["step"] in prev_steps:
        prev_steps[r["step"]]["carried_over_from_previous_run"] = True
        results[results.index(r)] = prev_steps[r["step"]]

summary = {
    "steps": results,
    "logs_pre_count": len(pre), "logs_changed": changed, "logs_added": added,
    "logs_deleted": deleted, "rerun_copies": [str((RERUN / (r.replace('/', '__'))).name)
                                              for r in changed + added],
    "frozen_logs_restored": frozen_restored,
    "frozen_backup": str(BAK),
    "all_rc_zero": all(r.get("rc") == 0 for r in results if not r.get("skipped")),
    "note": "既有冻结证据日志已原样恢复；本次运行结果保留在 logs/phase5c_rerun/",
}
SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")

print("\n" + "=" * 90)
print("改变/新增日志:", len(changed), "改变", len(added), "新增", "删除", len(deleted))
print("冻结日志已恢复:", frozen_restored)
print("全部 rc=0:", summary["all_rc_zero"])
print("summary ->", SUMMARY)
