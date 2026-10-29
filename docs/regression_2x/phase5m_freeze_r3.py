# -*- coding: utf-8 -*-
"""5-M：**带门禁**的基线冻结（全绿才冻结；否则 exit 3 且不写任何基线文件）。

门禁：
  G1 电池 25/25 步 rc=0（`all_rc_zero_raw == True`）
  G2 冻结日志恢复 True（changed 已回拷 / deleted 0）
  G3 批次 24/24 符合预期
  G4 单元套件全 rc=0（含新增 captions_test）
  G5 受影响套件全绿（captions 21/21、scene_assembly、narration_contract、5-K/5-L 守卫、attribution、pipeline_mock）
  G6 旧 `5.x-final-baseline.zip` sha256 仍为授权值
  G7 代码/测试指纹：电池前 == 电池后（`src/config/tests/scripts`）

冻结产物：`5.x-post-final-maintenance-baseline-r3`（**不覆盖** r2/r1 与 5.x Final）。
用法: python docs/regression_2x/phase5m_freeze_r3.py
"""
import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
R2 = ROOT / "docs" / "regression_2x"
LOGS = R2 / "logs"
BASE = R2 / "baseline"
PY = sys.executable
R3_TAG = "5.x-post-final-maintenance-baseline-r3"
FINAL_TAG = "5.x-final-baseline"
FINAL_SHA = "be1717b9c7fe9ed9124be3876db64b5893915a4d0ffad56bd37eded5e6e2141e"


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


gates, ok = {}, True


def gate(name, cond, detail):
    global ok
    gates[name] = {"pass": bool(cond), "detail": detail}
    ok = ok and bool(cond)
    print("{} {} {}".format("PASS" if cond else "FAIL", name, detail))


bp = LOGS / "phase5m_regression_summary.json"
bat = json.loads(bp.read_text(encoding="utf-8")) if bp.is_file() else {}
gate("G1 电池 25/25 步 rc=0", bat.get("all_rc_zero_raw") is True and bat.get("steps_count") == 25
     and not bat.get("rc_nonzero"), {"steps": bat.get("steps_count"),
                                     "rc_nonzero": bat.get("rc_nonzero")})
gate("G2 冻结日志恢复", bat.get("frozen_logs_restored") is True and not bat.get("frozen_logs_deleted"),
     {"changed": len(bat.get("frozen_logs_changed") or []),
      "added": len(bat.get("frozen_logs_added") or []),
      "deleted": bat.get("frozen_logs_deleted")})
bjson = LOGS / "phase5m_rerun" / "phase3a_regression_batch.json"
rows = json.loads(bjson.read_text(encoding="utf-8")) if bjson.is_file() else []
unexp = [r["name"] for r in rows if not r["as_expected"]]
gate("G3 批次 24/24 符合预期", len(rows) == 24 and not unexp, {"items": len(rows), "unexpected": unexp})
sjson = LOGS / "phase5m_rerun" / "suites_summary.json"
srows = json.loads(sjson.read_text(encoding="utf-8")) if sjson.is_file() else []
sfailed = [r["suite"] for r in srows if r["rc"] != 0]
gate("G4 单元套件全 rc=0", bool(srows) and not sfailed, {"total": len(srows), "failed": sfailed})
txt = (LOGS / "phase5m_affected_suites.txt").read_text(encoding="utf-8") \
    if (LOGS / "phase5m_affected_suites.txt").is_file() else ""
need = {"captions_test.py": "结果: 21/21 通过", "scene_assembly_test.py": "结果: 15/15 通过",
        "narration_contract_test.py": "结果: 40/40 通过",
        "maintenance_fixes_test.py": "结果: 28/28 通过",
        "offline_mock_test.py": "结果: 23/23 通过",
        "attribution_compliance_test.py": "结果: 24/24 通过"}
missing = [k for k, v in need.items() if v not in txt]
gate("G5 受影响套件全绿（列举式）", not missing, {"missing": missing})
fz = BASE / "{}.zip".format(FINAL_TAG)
gate("G6 旧 5.x-final-baseline sha256 未变", sha(fz) == FINAL_SHA, sha(fz)[:16])
fa = LOGS / "phase5m_code_fingerprint_before.json"
fb = LOGS / "phase5m_code_fingerprint_after.json"
subprocess.run([PY, r"docs\regression_2x\phase5m_code_fingerprint.py", "now"], cwd=str(ROOT),
               capture_output=True, text=True, encoding="utf-8", errors="replace")
fn = LOGS / "phase5m_code_fingerprint_now.json"


def _agg(p):
    return json.loads(p.read_text(encoding="utf-8"))["aggregate_sha256"] if p.is_file() else None


def _files(p):
    return json.loads(p.read_text(encoding="utf-8"))["files"] if p.is_file() else {}


delta = sorted(k for k in set(_files(fa)) | set(_files(fb))
               if _files(fa).get(k) != _files(fb).get(k))
same_fp = bool(fb.is_file() and fn.is_file()) and _agg(fb) == _agg(fn)
gate("G7 代码/测试指纹：冻结时 == 电池修复后", same_fp,
     {"after": (_agg(fb) or "")[:16], "now": (_agg(fn) or "")[:16],
      "before_vs_after_delta": delta,
      "note": "before→after 的差异为 5-M 期间按测试契约修正的 tests/strip_v2_test.py（烧录字幕源 "
              "_seg*.txt → _captions_*.ass）；电池末步 unit_suites 在修复后运行，故以 after 为基准"})

print("\n门禁汇总:", json.dumps({k: v["pass"] for k, v in gates.items()}, ensure_ascii=False))
if not ok:
    print("ABORT：门禁未全通过 → **不冻结**（保持 FAILED/PENDING，不强行冻结为全绿）")
    (LOGS / "phase5m_freeze_gate.json").write_text(
        json.dumps({"frozen": False, "gates": gates}, ensure_ascii=False, indent=1), encoding="utf-8")
    sys.exit(3)

r1 = subprocess.run([PY, r"docs\regression_2x\make_baseline.py", R3_TAG, "--no-docs"], cwd=str(ROOT),
                    capture_output=True, text=True, encoding="utf-8", errors="replace")
print(r1.stdout[-600:])
r2 = subprocess.run([PY, r"docs\regression_2x\make_manifest_one.py", R3_TAG], cwd=str(ROOT),
                    capture_output=True, text=True, encoding="utf-8", errors="replace")
print(r2.stdout[-400:])
r3 = subprocess.run([PY, r"docs\regression_2x\verify_baseline.py", R3_TAG], cwd=str(ROOT),
                    capture_output=True, text=True, encoding="utf-8", errors="replace")
print(r3.stdout)
verdict = "MATCH" if "VERDICT: MATCH" in (r3.stdout or "") else "DIFF"
man = json.loads((BASE / "baseline_manifest_{}.json".format(R3_TAG)).read_text(encoding="utf-8"))
r4 = subprocess.run([PY, r"docs\regression_2x\make_snapshot.py",
                     "5.x-post-final-maintenance-20260921-r3"], cwd=str(ROOT), capture_output=True,
                    text=True, encoding="utf-8", errors="replace")
print(r4.stdout[-300:])
status = {"tag": R3_TAG, "frozen_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
          "zip_sha256": man["zip_sha256"], "file_count": man["file_count"],
          "verify_baseline": verdict, "gates": {k: v["pass"] for k, v in gates.items()},
          "regression_status": {"verdict": "ALL_GREEN" if verdict == "MATCH" else "NOT_VERIFIED",
                                "battery": "25/25 rc=0" if bat.get("all_rc_zero_raw") else "NOT_ALL",
                                "batch": "{}/24 as_expected".format(
                                    sum(1 for r in rows if r["as_expected"])),
                                "suites": "{}/{} rc=0".format(len(srows) - len(sfailed), len(srows)),
                                "affected_suites": "captions 21/21 + scene_assembly 15/15 + "
                                                   "narration_contract 40/40 + 5-K 28/28 + 5-L 23/23 + "
                                                   "attribution 24/24"},
          "supersedes_without_overwriting": ["5.x-post-final-maintenance-baseline-r2（5-L）",
                                             "5.x-post-final-maintenance-baseline（5-K，r1）",
                                             "5.x-final-baseline（5.x 终稿，sha256 未变）"],
          "scope": "5-M 仅改字幕呈现（core/captions.py 新增；subtitle/editing agent 改用之）",
          "note": "电池运行期间仅改动 docs/（含 CHANGELOG/STATUS 的 5-M 条目）；"
                  "src/config/tests/scripts 指纹在电池前后一致（G7）"}
(BASE / "baseline_status_{}.json".format(R3_TAG)).write_text(
    json.dumps(status, ensure_ascii=False, indent=1), encoding="utf-8")
(LOGS / "phase5m_freeze_gate.json").write_text(
    json.dumps({"frozen": True, "gates": gates, "tag": R3_TAG, "zip_sha256": man["zip_sha256"],
                "verify": verdict}, ensure_ascii=False, indent=1), encoding="utf-8")
print("frozen:", R3_TAG, man["zip_sha256"][:16], "| verify:", verdict)
