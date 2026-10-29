"""Phase 3-C 测试：`run.py report <project_id>` 只读报告（5 类场景 + 只读性）。

场景：
  R1 正常项目（已 settled 的真实项目）——任务/产物/成本/素材/响度/验证都在
  R2 失败项目（FAILED/BLOCKED + 明确错误码）
  R3 部分完成项目（存在 PENDING，无成片）
  R4 不存在的项目（明确报错 + rc=2，不崩）
  R5 **只读性**：DB 文件字节不变、tasks/artifacts/events/projects 行数不变、
     只读连接写操作被 SQLite 拒绝
  R6 `--json` 输出可解析且与文本模式同源

用法：python tests/report_command_test.py
"""
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.db.schema import Database  # noqa: E402
from video_studio.ops.report import build_report, format_report, readonly_connection  # noqa: E402

DB = ROOT / "projects" / "video_studio.db"
PY = sys.executable
PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(("PASS  " if ok else "FAIL  ") + name + (" | " + str(detail)[:200] if detail else ""))


def cli(*args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    return subprocess.run([PY, "run.py", *args], cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=600, env=env)


def db_fingerprint() -> dict:
    h = hashlib.sha256(DB.read_bytes()).hexdigest()
    con = sqlite3.connect("file:{}?mode=ro".format(DB.as_posix()), uri=True)
    counts = {t: con.execute("select count(*) from {}".format(t)).fetchone()[0]
              for t in ("projects", "tasks", "artifacts", "events", "decisions", "claims")}
    con.close()
    return {"sha256": h, "size": DB.stat().st_size, "counts": counts}


# ---------------- 构造确定性 fixture（测试自身可以写；report 不允许写） ----------------
db = Database(DB)
SUFFIX = str(int(time.time()))[-6:]
P_OK, P_FAILED, P_PARTIAL, P_MISSING = ("p_3cok" + SUFFIX, "p_3cbad" + SUFFIX,
                                        "p_3cpart" + SUFFIX, "p_3cnone" + SUFFIX)
for pid, name in ((P_OK, "3c ok"), (P_FAILED, "3c failed"), (P_PARTIAL, "3c partial")):
    if db.get_project(pid) is None:
        db.create_project(pid, name, "Phase 3-C report fixture")

def mk_task(pid: str, ttype: str, role: str, status: str, **extra) -> str:
    """用 Database 直接插一条任务（测试 fixture；report 本身不允许写）。"""
    tid = "t_3c" + SUFFIX + ttype[:4]
    db.insert_task({"task_id": tid, "project_id": pid, "task_type": ttype,
                    "agent_role": role, "status": status, "dependencies": [],
                    "inputs": {}, "artifacts": [], "evidence": [], "lineage": [],
                    "expected_output": {}, **extra})
    return tid


# 正常项目：一个 LLM 任务（带成本）+ 一条成片产物（引用真实项目的渲染产物，只读展示）
t_ok = mk_task(P_OK, "script", "script", "SUCCEEDED", cost_usd=0.0123,
               model_used="deepseek-flash")
real = sqlite3.connect("file:{}?mode=ro".format(DB.as_posix()), uri=True)
real.row_factory = sqlite3.Row
row = real.execute("select path from artifacts where project_id='p_f4b466a4a024' and "
                   "type='render_output' order by created_at desc limit 1").fetchone()
real.close()
if row:
    db.insert_artifact({"artifact_id": "a_" + SUFFIX + "ok01", "project_id": P_OK,
                        "task_id": t_ok, "type": "render_output",
                        "path": row["path"], "sha256": "deadbeef", "size": 1,
                        "provenance": {}, "license": None, "version": 1,
                        "summary": "3-C report fixture", "superseded_by": None})

# 失败项目：FAILED 任务 + 明确错误码 + TASK_FAILED 事件（event_id 是 AUTOINCREMENT，用 append_event）
t_bad = mk_task(P_FAILED, "render", "editing", "FAILED", cost_usd=0.0031,
                model_used="deepseek-flash",
                error="成片响度不满足契约：LOUDNESS_OUT_OF_RANGE：I=-19.7 LUFS")
db.append_event(P_FAILED, "TASK_FAILED", "editing", t_bad,
                {"error": "LOUDNESS_OUT_OF_RANGE：I=-19.7 LUFS"}, True)

# 部分完成项目：一个 PENDING 任务、无成片
mk_task(P_PARTIAL, "voice", "voice", "PENDING")

# ================= R1 正常项目（真实项目：全量数据都在） =================
REAL_PID = "p_f4b466a4a024"          # 3-A/3-B 的真实链路项目（已 settled，含成片/台账/响度）
before = db_fingerprint()
r1 = cli("report", REAL_PID)
rep_real = build_report(DB, REAL_PID, project_dir=ROOT / "projects" / REAL_PID)
check("R1 正常项目 rc=0 且输出含任务/产物/成本/素材/响度小节",
      r1.returncode == 0 and all(k in r1.stdout for k in
                                 ("任务（", "产物（", "成本（LLM", "外部素材用量", "成片与验证")),
      "rc={} head={}".format(r1.returncode, r1.stdout[:60].replace("\n", " ")))
check("R1b 成本明确标注为估算（非账单）",
      rep_real["cost"]["estimate"] is True and "非真实账单" in rep_real["cost"]["note"],
      rep_real["cost"]["note"])
check("R1c 外部素材标注为非计费且统计到真实用量（请求/下载字节/限流）",
      rep_real["material"]["billing"] is False
      and (rep_real["material"].get("provider_stats") or {}).get("downloaded_bytes", 0) > 0
      and (rep_real["material"].get("provider_stats") or {}).get("requests", 0) > 0,
      rep_real["material"].get("provider_stats"))
check("R1d 成片响度验证结果被读出（3-B 证据）",
      (rep_real["film"].get("audio_loudness") or {}).get("ok") is True
      and rep_real["film"]["audio_loudness"].get("measured_lufs") is not None,
      rep_real["film"].get("audio_loudness", {}).get("measured_lufs"))
check("R1e 上屏核验与台账逐条一致",
      rep_real["attribution"].get("entry_count")
      == len(rep_real["film"].get("appears_in_film") or {})
      and all(rep_real["film"]["appears_in_film"].values()),
      (rep_real["attribution"].get("entry_count"), rep_real["film"].get("appears_in_film")))
check("R1f 抽帧核验无失败镜头且旁白状态为 COMPLETE",
      not (rep_real["film"].get("material_verification") or {}).get("failed_scenes")
      and rep_real["narration"].get("status") == "COMPLETE",
      (rep_real["film"].get("material_verification", {}).get("failed_scenes"),
       rep_real["narration"].get("status")))

# ================= R2 失败项目 =================
r2 = cli("report", P_FAILED)
rep2 = build_report(DB, P_FAILED, project_dir=ROOT / "projects" / P_FAILED)
check("R2 失败项目 rc=0 且列出 FAILED 任务与原因",
      r2.returncode == 0 and rep2["tasks"]["by_status"].get("FAILED") == 1
      and any("LOUDNESS_OUT_OF_RANGE" in str(p.get("error")) for p in rep2["problems"]),
      [p.get("error") for p in rep2["problems"]][:1])
check("R2b 失败事件被列出", any("LOUDNESS_OUT_OF_RANGE" in str(e.get("error"))
                              for e in rep2["events"]["recent_failures"]),
      rep2["events"]["recent_failures"][:1])
check("R2c 失败项目无成片时仍能给出（无 render_output）", rep2["film"] == {}, rep2["film"])

# ================= R3 部分完成项目 =================
r3 = cli("report", P_PARTIAL)
rep3 = build_report(DB, P_PARTIAL, project_dir=ROOT / "projects" / P_PARTIAL)
check("R3 部分完成项目 rc=0 且显示 PENDING 与未派发清单",
      r3.returncode == 0 and rep3["tasks"]["by_status"].get("PENDING") == 1
      and len(rep3["tasks"]["pending"]) == 1, rep3["tasks"]["by_status"])
check("R3b 部分完成项目如实显示无成片", rep3["film"] == {} and "无 render_output" in r3.stdout,
      rep3["film"])

# ================= R4 不存在的项目 =================
r4 = cli("report", P_MISSING)
rep4 = build_report(DB, P_MISSING)
check("R4 不存在项目 rc=2 且给出明确信息（不崩溃）",
      r4.returncode == 2 and "项目不存在" in (r4.stderr + r4.stdout)
      and rep4["found"] is False and "项目不存在" in format_report(rep4),
      "rc={} err={}".format(r4.returncode, (r4.stderr or "").strip()[:80]))

# ================= R5 只读性 =================
after = db_fingerprint()
check("R5 DB 文件字节不变（sha256/大小）",
      before["sha256"] == after["sha256"] and before["size"] == after["size"],
      "{} vs {}".format(before["sha256"][:16], after["sha256"][:16]))
check("R5b 六张表行数全部不变", before["counts"] == after["counts"],
      "{} -> {}".format(before["counts"], after["counts"]))
try:
    con = readonly_connection(DB)
    con.execute("insert into decisions (decision_id, project_id, node, made_by, state, "
                "rationale, artifact_snapshot, created_at) values ('x','x','x','x','x','x','x',0)")
    con.close()
    ro_blocked = False
except sqlite3.OperationalError as exc:
    ro_blocked = "readonly" in str(exc).lower() or "read-only" in str(exc).lower()
check("R5c 只读连接写操作被 SQLite 拒绝", ro_blocked, "OperationalError(readonly)")
# 只读性还要覆盖"未触发任务"：报告后 tasks 表无新行、无 TASK_* 事件新增
check("R5d 报告未触发任何任务（无新增任务/事件行）",
      before["counts"]["tasks"] == after["counts"]["tasks"]
      and before["counts"]["events"] == after["counts"]["events"], after["counts"])

# ================= R6 JSON 模式 =================
r6 = cli("report", REAL_PID, "--json")
try:
    j = json.loads(r6.stdout)
    ok_json = r6.returncode == 0 and j["found"] and "cost" in j and "material" in j
except (json.JSONDecodeError, KeyError):
    j, ok_json = {}, False
check("R6 --json 输出可解析且含核心字段", ok_json, sorted(j.keys())[:8])
check("R6b JSON 与文本同源（同一 build_report）",
      ok_json and j["tasks"]["total"] == rep_real["tasks"]["total"],
      (j.get("tasks", {}).get("total"), rep_real["tasks"]["total"]))

print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print("失败项:", FAIL)
sys.exit(0 if not FAIL else 1)
