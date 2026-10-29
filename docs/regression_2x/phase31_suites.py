# -*- coding: utf-8 -*-
"""Phase 31 P31-5：完整单元回归（tests/*_test.py 一次跑完，收集 rc 与汇总）。

复用既有约定：逐套件独立进程执行、汇总 `rc==0` 计数、落盘
`logs/phase31_suites.log` 与 `logs/phase31_suites_summary.json`。
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import time

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
PY = R / ".venv_tts" / "Scripts" / "python.exe"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    tests = sorted((R / "tests").glob("*_test.py"))
    print("套件数: {}".format(len(tests)))
    logp = L / "phase31_suites.log"
    rows, t0 = [], time.time()
    with logp.open("w", encoding="utf-8") as fh:
        for t in tests:
            st = time.time()
            p = subprocess.run([str(PY), str(t)], cwd=str(R), capture_output=True,
                               text=True, encoding="utf-8", errors="replace")
            dt = time.time() - st
            out = (p.stdout or "") + (p.stderr or "")
            tail = [ln for ln in out.strip().splitlines() if ln.strip()][-3:]
            rows.append({"suite": t.name, "rc": p.returncode, "seconds": round(dt, 1),
                         "tail": tail})
            line = "[rc={}] {:<44} {:>6.1f}s | {}".format(
                p.returncode, t.name, dt, " / ".join(x[:90] for x in tail))
            print(line, flush=True)
            fh.write(line + "\n")
            fh.write(out[-4000:] + "\n" + "=" * 70 + "\n")
    rc0 = [r for r in rows if r["rc"] == 0]
    bad = [r for r in rows if r["rc"] != 0]
    summary = {"schema": "phase31-suites-summary-v1",
               "suites_total": len(rows), "rc0": len(rc0), "failed": bad,
               "elapsed_s": round(time.time() - t0, 1), "rows": rows}
    (L / "phase31_suites_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print()
    print("=" * 74)
    print("完整回归: {}/{} rc=0 | 失败 {} | {:.1f}s".format(
        len(rc0), len(rows), len(bad), summary["elapsed_s"]))
    for b in bad:
        print("  FAIL {} rc={} | {}".format(b["suite"], b["rc"], " / ".join(b["tail"])[:200]))
    print("=" * 74)
    print("-> " + str((L / "phase31_suites_summary.json").relative_to(R)))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
