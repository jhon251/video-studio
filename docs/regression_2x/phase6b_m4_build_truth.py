# -*- coding: utf-8 -*-
"""6-B/M4 —— 受控执行真值集**冻结** + 契约统计（幂等）。"""
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
LOGS = ROOT / "docs" / "regression_2x" / "logs"
TRUTH = ROOT / "tests" / "fixtures" / "revision_execution_truth_v1.json"


def canonical_sha(obj: dict) -> str:
    payload = {k: v for k, v in obj.items() if k != "frozen_sha256"}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def file_sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


t = json.loads(TRUTH.read_text(encoding="utf-8"))
sha_before = canonical_sha(t)
if t.get("frozen_sha256") != sha_before:
    t["frozen_sha256"] = sha_before
    TRUTH.write_text(json.dumps(t, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
assert canonical_sha(json.loads(TRUTH.read_text(encoding="utf-8"))) == sha_before

ap = LOGS / "phase6b_m4_approvals_v9.jsonl"
ex = LOGS / "phase6b_m4_execution_ledger_v9.jsonl"


def load(p):
    return ([json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
            if p.is_file() else [])


rec = {
    "schema": "revision-execution-truth-freeze-v1",
    "stage": "6-B/M4",
    "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "truth_path": TRUTH.relative_to(ROOT).as_posix(),
    "truth_canonical_sha256": sha_before,
    "truth_file_sha256": file_sha(TRUTH),
    "gate_case_count": len(t["gate_cases"]),
    "execution_case_count": len(t["execution_cases"]),
    "frozen_policy": t["frozen_policy"],
    "v9_state": {"approvals": [(a.get("proposal_label"), a.get("decision")) for a in load(ap)],
                 "executions": [(e.get("proposal_label"), e.get("state")) for e in load(ex)],
                 "approvals_entries": len(load(ap)), "executions_entries": len(load(ex))},
    "v9_execution_expect": t["v9_execution_expect"],
    "help": "改真值集后重跑本脚本刷新 frozen_sha256；只校验请运行 tests/execution_truth_test.py",
}
(LOGS / "phase6b_m4_truth_freeze.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1),
                                                  encoding="utf-8")
print("truth canonical sha256:", sha_before)
print("gate/execution 用例:", len(t["gate_cases"]), "/", len(t["execution_cases"]))
print("v9 approvals:", rec["v9_state"]["approvals"])
print("v9 executions:", rec["v9_state"]["executions"])
print("json ->", LOGS / "phase6b_m4_truth_freeze.json")
