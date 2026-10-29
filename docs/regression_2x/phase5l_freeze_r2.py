# -*- coding: utf-8 -*-
"""5-L：**带门禁**的基线冻结（全绿才冻结；否则中止并保持 FAILED/PENDING）。

门禁（全部满足才冻结，否则 exit 3 且不写任何基线文件）：
  G1 电池 25/25 步 rc=0（`all_rc_zero_raw == True`）
  G2 冻结日志恢复 True（drift 0 / missing 0）
  G3 批次 24/24 as_expected（网络项已按环境如实分类时也需为 True，否则人工判定）
  G4 单元套件全 rc=0（failed == []）
  G5 两个针对性套件全绿（maintenance_fixes_test 28/28、offline_mock_test 23/23）
  G6 旧 `5.x-final-baseline.zip` sha256 仍为授权值

冻结产物：`5.x-post-final-maintenance-baseline-r2`（**不覆盖** r1 与 5.x Final）+ manifest + 校验 + 状态文件。
用法: python docs/regression_2x/phase5l_freeze_r2.py [--force-show-gate]
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
R2_TAG = "5.x-post-final-maintenance-baseline-r2"
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


# G1/G2 电池
bp = LOGS / "phase5l_regression_summary.json"
bat = json.loads(bp.read_text(encoding="utf-8")) if bp.is_file() else {}
gate("G1 电池 25/25 步 rc=0", bat.get("all_rc_zero_raw") is True and bat.get("steps_count") == 25
     and not bat.get("rc_nonzero"), {"steps": bat.get("steps_count"),
                                     "rc_nonzero": bat.get("rc_nonzero")})
gate("G2 冻结日志恢复（drift 0 / missing 0）", bat.get("frozen_logs_restored") is True
     and not bat.get("frozen_logs_deleted"), {"changed": len(bat.get("frozen_logs_changed") or []),
                                              "added": len(bat.get("frozen_logs_added") or []),
                                              "deleted": bat.get("frozen_logs_deleted")})
# G3 批次
bjson = LOGS / "phase5l_rerun" / "phase3a_regression_batch.json"
rows = json.loads(bjson.read_text(encoding="utf-8")) if bjson.is_file() else []
unexp = [r["name"] for r in rows if not r["as_expected"]]
gate("G3 批次 24/24 符合预期", len(rows) == 24 and not unexp, {"items": len(rows), "unexpected": unexp})
# G4 套件
sjson = LOGS / "phase5l_rerun" / "suites_summary.json"
srows = json.loads(sjson.read_text(encoding="utf-8")) if sjson.is_file() else []
sfailed = [r["suite"] for r in srows if r["rc"] != 0]
gate("G4 单元套件全 rc=0", bool(srows) and not sfailed,
     {"total": len(srows), "failed": sfailed})
# G5 针对性套件
tgt = {}
for f in ("maintenance_fixes_test.py", "offline_mock_test.py"):
    p = LOGS / "phase5l_targeted_suites.txt"
    tgt[f] = p.is_file() and (f in p.read_text(encoding="utf-8"))
txt = (LOGS / "phase5l_targeted_suites.txt").read_text(encoding="utf-8") if (
    LOGS / "phase5l_targeted_suites.txt").is_file() else ""
gate("G5 针对性套件全绿（28/28 + 23/23）", "结果: 28/28 通过" in txt and "结果: 23/23 通过" in txt,
     {"28/28": "结果: 28/28 通过" in txt, "23/23": "结果: 23/23 通过" in txt})
# G6 旧 Final 未变
fz = BASE / "{}.zip".format(FINAL_TAG)
gate("G6 旧 5.x-final-baseline sha256 未变", sha(fz) == FINAL_SHA, sha(fz)[:16])

print("\n门禁汇总:", json.dumps({k: v["pass"] for k, v in gates.items()}, ensure_ascii=False))
if not ok:
    print("ABORT：门禁未全通过 → **不冻结**（保持 FAILED/PENDING，不强行冻结为全绿）")
    (LOGS / "phase5l_freeze_gate.json").write_text(
        json.dumps({"frozen": False, "gates": gates}, ensure_ascii=False, indent=1), encoding="utf-8")
    sys.exit(3)

r1 = subprocess.run([PY, r"docs\regression_2x\make_baseline.py", R2_TAG, "--no-docs"], cwd=str(ROOT),
                    capture_output=True, text=True, encoding="utf-8", errors="replace")
print(r1.stdout[-800:])
r2 = subprocess.run([PY, r"docs\regression_2x\make_manifest_one.py", R2_TAG], cwd=str(ROOT),
                    capture_output=True, text=True, encoding="utf-8", errors="replace")
print(r2.stdout[-500:])
r3 = subprocess.run([PY, r"docs\regression_2x\verify_baseline.py", R2_TAG], cwd=str(ROOT),
                    capture_output=True, text=True, encoding="utf-8", errors="replace")
print(r3.stdout)
verdict = "MATCH" if "VERDICT: MATCH" in (r3.stdout or "") else "DIFF"
man = json.loads((BASE / "baseline_manifest_{}.json".format(R2_TAG)).read_text(encoding="utf-8"))
r4 = subprocess.run([PY, r"docs\regression_2x\make_snapshot.py", "5.x-post-final-maintenance-20260921-r2"],
                    cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
                    errors="replace")
print(r4.stdout[-400:])
status = {"tag": R2_TAG, "frozen_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
          "zip_sha256": man["zip_sha256"], "file_count": man["file_count"],
          "verify_baseline": verdict, "gates": {k: v["pass"] for k, v in gates.items()},
          "regression_status": {"verdict": "ALL_GREEN" if verdict == "MATCH" else "NOT_VERIFIED",
                                "battery": "{}/25 rc=0".format(
                                    bat.get("steps_count", 0) if bat.get("all_rc_zero_raw") else 0),
                                "batch": "{}/24 as_expected".format(
                                    sum(1 for r in rows if r["as_expected"])),
                                "suites": "{}/{} rc=0".format(len(srows) - len(sfailed), len(srows)),
                                "targeted": "28/28 + 23/23"},
          "supersedes_without_overwriting": ["5.x-post-final-maintenance-baseline (r1, r5-K 检查点)",
                                             "5.x-final-baseline (5.x 终稿，sha256 未变)"],
          "note": "本基线在 5-L 修正（离线 mock 独立化 + M5d 重钉 + p_96efdc 重渲染）且电池全绿后冻结"}
(BASE / "baseline_status_{}.json".format(R2_TAG)).write_text(
    json.dumps(status, ensure_ascii=False, indent=1), encoding="utf-8")
(LOGS / "phase5l_freeze_gate.json").write_text(
    json.dumps({"frozen": True, "gates": gates, "tag": R2_TAG, "zip_sha256": man["zip_sha256"],
                "verify": verdict}, ensure_ascii=False, indent=1), encoding="utf-8")
print("frozen:", R2_TAG, man["zip_sha256"][:16], "| verify:", verdict)
print("status ->", BASE / "baseline_status_{}.json".format(R2_TAG))
