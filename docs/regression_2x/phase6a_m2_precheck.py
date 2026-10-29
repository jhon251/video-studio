# -*- coding: utf-8 -*-
"""6-A/M2 预检（只读式）：跑遍 `tests/*.py` 全部套件，**只记录 rc/tail**，不写任何冻结日志。

用途：在正式 25 步电池之前，快速定位"M2 改动引入的隐藏套件红"。
与 `run_all_suites.py` 的区别：**不**写 `logs/suite_*.log` / `logs/suites_summary.json`
（那些属于冻结证据，只能由电池自身的"备份→运行→回拷"机制触碰）。

用法: python docs/regression_2x/phase6a_m2_precheck.py
产出: logs/phase6a_m2_precheck.json
"""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
LOGS = ROOT / "docs" / "regression_2x" / "logs"
PY = sys.executable
files = sorted(p for p in (ROOT / "tests").glob("*.py") if p.name != "__init__.py")
rows = []
t0 = time.time()
for p in files:
    ts = time.time()
    try:
        r = subprocess.run([PY, str(p.relative_to(ROOT))], cwd=str(ROOT), capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=1800)
        out = (r.stdout or "") + (r.stderr or "")
        rc = r.returncode
    except subprocess.TimeoutExpired:
        out, rc = "TIMEOUT", -9
    tail = [ln.strip() for ln in out.strip().splitlines() if ln.strip()][-2:]
    ratios = ["{}/{}".format(a, b) for a, b in
              re.findall(r"(\d+)\s*/\s*(\d+)\s*(?:passed|through|pass|ok|通过)", out, re.I)]
    rows.append({"suite": p.stem, "rc": rc, "seconds": round(time.time() - ts, 1),
                 "tail": tail, "ratios": ratios})
    print("[{:30s}] rc={} ({:.1f}s) {}".format(p.stem, rc, time.time() - ts, " | ".join(tail)[:110]),
          flush=True)
bad = [r["suite"] for r in rows if r["rc"] != 0]
out = {"stage": "6-A/M2-precheck", "total": len(rows), "rc0": len(rows) - len(bad),
       "failed": bad, "seconds": round(time.time() - t0, 1), "results": rows}
(LOGS / "phase6a_m2_precheck.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                              encoding="utf-8")
print("\nSUITES: {} total, {} rc=0, failed={}".format(len(rows), len(rows) - len(bad), bad))
print("json ->", LOGS / "phase6a_m2_precheck.json")
