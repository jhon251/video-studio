"""3.x Phase 3-C：`run.py report` 五类场景的证据采集（命令 / 返回码 / 关键结果 / 产物路径）。

场景：正常项目、失败项目、部分完成项目、不存在项目、只读性（前后指纹对比）。
产出：docs/regression_2x/logs/phase3c_report_{normal,failed,partial,missing,json,readonly}.txt
用法：python docs/regression_2x/phase3c_report_evidence.py
"""
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
LOGS = ROOT / "docs" / "regression_2x" / "logs"
DB = ROOT / "projects" / "video_studio.db"
PY = sys.executable
REAL = "p_f4b466a4a024"          # 正常（3-A/3-B 真实链路项目，已 settled）
TIMEOUT = 600


def cli(*args: str) -> tuple[int, str]:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    r = subprocess.run([PY, "run.py", *args], cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=TIMEOUT, env=env)
    return r.returncode, (r.stdout or "") + (("\n[stderr]\n" + r.stderr) if r.stderr else "")


def fingerprint() -> dict:
    con = sqlite3.connect("file:{}?mode=ro".format(DB.as_posix()), uri=True)
    counts = {t: con.execute("select count(*) from {}".format(t)).fetchone()[0]
              for t in ("projects", "tasks", "artifacts", "events")}
    con.close()
    return {"sha256": hashlib.sha256(DB.read_bytes()).hexdigest(), "size": DB.stat().st_size,
            "counts": counts}


def newest(where_sql: str) -> str | None:
    con = sqlite3.connect("file:{}?mode=ro".format(DB.as_posix()), uri=True)
    row = con.execute("select project_id from projects where " + where_sql +
                      " order by created_at desc limit 1").fetchone()
    con.close()
    return row[0] if row else None


FAILED_PID = newest("project_id like 'p_3cbad%'")
PARTIAL_PID = newest("project_id like 'p_3cpart%'")
MISSING_PID = "p_3c_no_such_project"

lines = ["3.x Phase 3-C：run.py report 证据", "=" * 70, ""]
CASES = [
    ("normal", [REAL], "正常项目（真实链路，已 settled）"),
    ("failed", [FAILED_PID] if FAILED_PID else [REAL], "失败项目（FAILED 任务 + 明确错误码）"),
    ("partial", [PARTIAL_PID] if PARTIAL_PID else [REAL], "部分完成项目（PENDING，无成片）"),
    ("missing", [MISSING_PID], "不存在的项目（期望 rc=2，不崩溃）"),
]
for tag, args, desc in CASES:
    args = [a for a in args if a]
    before = fingerprint()
    rc, out = cli("report", *args)
    after = fingerprint()
    body = ["场景: {}  ({})".format(desc, tag),
            "命令: python run.py report {}".format(" ".join(args)),
            "返回码: {}".format(rc),
            "只读校验: DB sha256 {} / 行数 {} 前后{}".format(
                "不变" if before["sha256"] == after["sha256"] else "**变化**",
                before["counts"],
                "一致" if before["counts"] == after["counts"] else "**不一致**"),
            "", "───── 输出 ─────", out]
    (LOGS / "phase3c_report_{}.txt".format(tag)).write_text("\n".join(body), encoding="utf-8")
    lines += ["[{}] rc={} | DB {} | {} | 产物 logs/phase3c_report_{}.txt".format(
        tag, rc, "未改动" if before["sha256"] == after["sha256"] else "**被改动**",
        desc, tag)]
    print(lines[-1], flush=True)

rc_j, out_j = cli("report", REAL, "--json")
(LOGS / "phase3c_report_json.json").write_text(out_j, encoding="utf-8")
try:
    keys = sorted(json.loads(out_j).keys())
    ok_json = True
except json.JSONDecodeError:
    keys, ok_json = [], False
lines += ["[json] rc={} | 可解析={} | keys={}".format(rc_j, ok_json, keys[:6]),
          "      产物 logs/phase3c_report_json.json"]

before, after = fingerprint(), None
rc_all = 0
for _ in range(3):
    rc_all |= cli("report", REAL)[0]
after = fingerprint()
lines += ["[readonly] 连续 3 次 report 后：DB sha256 {} | 行数 {}".format(
    "不变" if before["sha256"] == after["sha256"] else "**变化**", after["counts"]),
    "           汇总 rc={}".format(rc_all)]
(LOGS / "phase3c_report_readonly.txt").write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines[2:]))
print("\nwritten", LOGS / "phase3c_report_readonly.txt")
