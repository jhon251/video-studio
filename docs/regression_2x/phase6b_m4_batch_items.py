# -*- coding: utf-8 -*-
"""6-B/M4 —— step2（`3a_regression_batch`）的**逐项可续跑**执行器（等价 argv + 等价 as_expected 语义）。

为什么需要它：本环境下**前台单次调用上限 10 分钟**，而后台作业会被环境在 ~13 分钟内杀死；
标准 `phase3a_regression_batch.py` 需连续 ~37 分钟，会在中途被杀且**不写汇总**。
本执行器逐步执行**同一份 ITEMS**（从该脚本 AST 解析，argv 完全一致），每项完成即落盘进度，
被杀后可用 `--resume` 续跑；最终给出与标准脚本**同一口径**的结论：
  step rc = 0 ⇔ 没有 `as_expected=False` 的项（标准脚本正是 `0 if not unexpected else 1`）。

用法: python docs/regression_2x/phase6b_m4_batch_items.py [--resume] [--only a,b]
产出: logs/phase6b_m4_batch_items.json（逐项 rc/耗时/tail + 汇总）
"""
import ast
import json
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
LOGS = ROOT / "docs" / "regression_2x" / "logs"
REF = ROOT / "docs" / "regression_2x" / "phase3a_regression_batch.py"
OUT = LOGS / "phase6b_m4_batch_items.json"
PROGRESS = LOGS / "phase6b_m4_batch_items_progress.json"
PY = sys.executable

ARGS = sys.argv[1:]
RESUME = "--resume" in ARGS
ONLY = set()
for _i, _a in enumerate(ARGS):
    if _a == "--only" and _i + 1 < len(ARGS):
        ONLY = {x.strip() for x in ARGS[_i + 1].split(",") if x.strip()}

tree = ast.parse(REF.read_text(encoding="utf-8"))
items = None
for node in tree.body:
    if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "ITEMS"
                                            for t in node.targets):
        items = ast.literal_eval(node.value)
if not items:
    print("ABORT: 无法从 phase3a_regression_batch.py 解析 ITEMS")
    sys.exit(2)
items = [i for i in items if not ONLY or i[0] in ONLY]

done = {}
if RESUME and PROGRESS.is_file():
    try:
        done = {r["name"]: r for r in
                json.loads(PROGRESS.read_text(encoding="utf-8")).get("items", [])}
    except Exception:                                            # noqa: BLE001
        done = {}

rows = [done[i[0]] for i in items if i[0] in done]
t0 = time.time()
print("ITEMS: {}（已完成 {}）".format(len(items), len(rows)), flush=True)
for name, argv, expect, needs_net, expect_rc, note in items:
    if name in done:
        print("[{:26s}] 跳过（已记录 rc={}）".format(name, done[name]["rc"]), flush=True)
        continue
    ts = time.time()
    r = subprocess.run([PY] + list(argv), cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    (LOGS / "phase3a_{}.log".format(name)).write_text(out, encoding="utf-8")
    tail = [ln.strip() for ln in out.strip().splitlines() if ln.strip()][-6:]
    rec = {"name": name, "argv": list(argv), "expect": expect, "needs_network": bool(needs_net),
           "expect_rc": expect_rc, "rc": r.returncode,
           "as_expected": r.returncode == expect_rc, "seconds": round(time.time() - ts, 1),
           "tail": tail}
    rows.append(rec)
    PROGRESS.write_text(json.dumps({"items": rows, "done": len(rows), "total": len(items)},
                                   ensure_ascii=False, indent=1), encoding="utf-8")
    print("[{:26s}] rc={} (期望 {}) ({:.1f}s) {}".format(
        name, r.returncode, expect_rc, rec["seconds"], " | ".join(tail)[:120]), flush=True)

unexpected = [x["name"] for x in rows if not x["as_expected"]]
net = [x["name"] for x in rows if x["needs_network"]]
step_rc = 0 if not unexpected else 1
summary = {"schema": "m4-batch-items-v1", "stage": "6-B/M4",
           "source_of_items": REF.relative_to(ROOT).as_posix(),
           "note": "逐项执行 phase3a_regression_batch.py 的同一 ITEMS（argv 一致）；"
                   "step rc 口径与标准脚本一致（无 unexpected ⇒ 0）",
           "total": len(rows), "as_expected_count": len(rows) - len(unexpected),
           "unexpected": unexpected, "needs_network_items": net,
           "step_rc_equivalent": step_rc,
           "seconds_this_launch": round(time.time() - t0, 1),
           "seconds_total_all_items": round(sum(x["seconds"] for x in rows), 1),
           "items": rows}
OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
print("\n批次：{} 项 | 符合预期 {}/{} | 非预期 {} | 等价 step rc = {}".format(
    len(rows), len(rows) - len(unexpected), len(rows), unexpected, step_rc))
print("json ->", OUT)
