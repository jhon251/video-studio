# -*- coding: utf-8 -*-
"""6-A/M1 收尾核对（只读）：r3 工件完整、旧 Final 未变、守卫一致、报告结构、无残留进程。"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
LOGS = ROOT / "docs" / "regression_2x" / "logs"
BASE = ROOT / "docs" / "regression_2x" / "baseline"


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


r3z = BASE / "5.x-post-final-maintenance-baseline-r3.zip"
r3m = BASE / "baseline_manifest_5.x-post-final-maintenance-baseline-r3.json"
man = json.loads(r3m.read_text(encoding="utf-8"))
print("r3 zip sha == manifest:", sha(r3z) == man["zip_sha256"], "| files", man["file_count"])
fz = BASE / "5.x-final-baseline.zip"
print("5.x-final-baseline sha256:", sha(fz)[:16],
      "| 未变:", sha(fz) == "be1717b9c7fe9ed9124be3876db64b5893915a4d0ffad56bd37eded5e6e2141e")
g = json.loads((LOGS / "phase6a_guard_check.json").read_text(encoding="utf-8"))
print("守卫漂移:", g["guards_drifted"] or "无", "| 工作树相对 r3 漂移:", g["tree_drift_vs_r3"])
b = json.loads((LOGS / "phase6a_regression_summary.json").read_text(encoding="utf-8"))
print("电池: steps", b["steps_count"], "| rc!=0:", b["rc_nonzero"],
      "| 日志恢复:", b["frozen_logs_restored"])
s = json.loads((LOGS / "phase6a_rerun" / "suites_summary.json").read_text(encoding="utf-8"))
bad = [x["suite"] for x in s if x["rc"] != 0]
print("step25 套件:", len(s), "| rc0", len(s) - len(bad), "| failed", bad)
bp = json.loads((LOGS / "phase6a_rerun" / "phase3a_regression_batch.json").read_text(encoding="utf-8"))
print("批次:", len(bp), "项 | 符合预期", sum(1 for x in bp if x["as_expected"]),
      "| 非预期", [x["name"] for x in bp if not x["as_expected"]])
for f in ("phase6a_integrity_v9.json", "phase6a_direction_v9.json"):
    d = json.loads((LOGS / f).read_text(encoding="utf-8"))
    print("报告", f, "| schema", d["schema"], "| read_only", d["read_only"],
          "| enforced", d["enforced"], "| overall", d["summary"]["overall"])
r = (ROOT / "docs" / "regression_2x" / "PHASE6A_M1_REPORT.md").read_text(encoding="utf-8")
print("M1 报告章节:", [l for l in r.splitlines() if l.startswith("## ")])
n = len(subprocess.run(["powershell", "-NoProfile", "-Command",
                        "(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
                        "Where-Object { $_.CommandLine -like '*video-studio*' }).Count"],
                       capture_output=True, text=True).stdout.strip())
print("残留相关进程数:", subprocess.run(
    ["powershell", "-NoProfile", "-Command",
     "@(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
     "Where-Object { $_.CommandLine -like '*video-studio*' }).Count"],
    capture_output=True, text=True).stdout.strip())
