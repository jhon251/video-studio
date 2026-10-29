"""Run every test suite in tests/ and summarize (ASCII source).

Usage: python docs/regression_2x/run_all_suites.py
"""
import json
import re
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
LOGS = ROOT / "docs" / "regression_2x" / "logs"
LOGS.mkdir(parents=True, exist_ok=True)

files = sorted(p for p in (ROOT / "tests").glob("*.py") if p.name != "__init__.py")
summary = []
for p in files:
    r = subprocess.run([sys.executable, str(p.relative_to(ROOT))], cwd=str(ROOT),
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800)
    out = (r.stdout or "") + (r.stderr or "")
    (LOGS / "suite_{}.log".format(p.stem)).write_text(out, encoding="utf-8")
    m = re.findall(r"(\d+)\s*/\s*(\d+)\s*(?:passed|through|pass|ok)", out, re.I)
    last = [ln.strip() for ln in out.strip().splitlines() if ln.strip()][-3:]
    summary.append({"suite": p.stem, "rc": r.returncode, "tail": last,
                    "ratios": ["{}/{}".format(a, b) for a, b in m]})
    print("[{:28s}] rc={} {}".format(p.stem, r.returncode, " | ".join(last)[:150]), flush=True)

ok = sum(1 for s in summary if s["rc"] == 0)
print("\n" + "=" * 100)
print("SUITES: {} total, {} rc=0, {} rc!=0".format(len(summary), ok, len(summary) - ok))
print("FAILED:", [s["suite"] for s in summary if s["rc"] != 0])
(LOGS / "suites_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
print("summary ->", LOGS / "suites_summary.json")
