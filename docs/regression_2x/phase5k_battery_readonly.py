# -*- coding: utf-8 -*-
"""5-K：只跑电池中**未被批次覆盖的只读检查**（不含会改写冻结证据的重跑型步骤）。

不跑的步骤与理由见 PHASE5K_REPORT.md §8 / KNOWN_ISSUES #60：
- `phase3a_real_chain.py`（真实网络链重跑、改写 5 份冻结日志）
- `4ab..5f_evidence.py`（证据重生成；其被守卫的文件已由 M8 逐字节证明未改）
- `5e_calibration` / `5f_judge`（重算 CLIP/Judge，昂贵且被守卫）
用法: python docs/regression_2x/phase5k_battery_readonly.py
产出: docs/regression_2x/logs/phase5k_battery_readonly.json
"""
import json
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
LOGS = ROOT / "docs" / "regression_2x" / "logs"
PY = sys.executable
V6 = "a_fa4716cffb26"

STEPS = [
    ("3b_audit", [r"docs\regression_2x\phase3b_audit.py"]),
    ("4x_audit", [r"docs\regression_2x\phase4x_audit.py"]),
    ("5c_append_only", [r"docs\regression_2x\phase5c_append_only.py"]),
    ("5c_db_append_only", [r"docs\regression_2x\phase5c_db_append_only.py"]),
    ("5c_verify_film", [r"docs\regression_2x\phase5c_verify_film.py", V6]),
    ("5c_failclosed", [r"docs\regression_2x\phase5c_failclosed.py"]),
    ("5c_checkpoint_check", [r"docs\regression_2x\phase5c_checkpoint_check.py"]),
    ("5d_frozen_check", [r"docs\regression_2x\phase5d_frozen_check.py"]),
]
rows = []
for name, argv in STEPS:
    t0 = time.time()
    r = subprocess.run([PY] + argv, cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=1800)
    out = (r.stdout or "") + (r.stderr or "")
    (LOGS / "phase5k_ro_{}.log".format(name)).write_text(out, encoding="utf-8")
    tail = [ln.strip() for ln in out.strip().splitlines() if ln.strip()][-3:]
    rows.append({"step": name, "rc": r.returncode, "seconds": round(time.time() - t0, 1),
                 "tail": tail})
    print("[{:22s}] rc={} {:>6.1f}s  {}".format(name, r.returncode, rows[-1]["seconds"],
                                                " | ".join(tail)[:110]), flush=True)
out = {"steps": rows, "rc0": sum(1 for r in rows if r["rc"] == 0), "total": len(rows),
       "note": "电池中未被批次覆盖的只读检查；重跑型步骤未执行（见 #60）"}
(LOGS / "phase5k_battery_readonly.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                                    encoding="utf-8")
print("\nrc0 {}/{}".format(out["rc0"], out["total"]))
print("json ->", LOGS / "phase5k_battery_readonly.json")
