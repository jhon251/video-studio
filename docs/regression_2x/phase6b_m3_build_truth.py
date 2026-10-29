# -*- coding: utf-8 -*-
"""6-B/M3 —— Revision Proposal 真值集**冻结** + 契约统计（幂等）。

用法: python docs/regression_2x/phase6b_m3_build_truth.py
产出: logs/phase6b_m3_truth_freeze.json
"""
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
LOGS = ROOT / "docs" / "regression_2x" / "logs"
TRUTH = ROOT / "tests" / "fixtures" / "revision_proposal_truth_v1.json"


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

reg = LOGS / "phase6b_m3_proposal_register_v9.jsonl"
entries = []
if reg.is_file():
    entries = [json.loads(ln) for ln in reg.read_text(encoding="utf-8").splitlines() if ln.strip()]
record = {
    "schema": "revision-proposal-truth-freeze-v1",
    "stage": "6-B/M3",
    "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "truth_path": TRUTH.relative_to(ROOT).as_posix(),
    "truth_canonical_sha256": sha_before,
    "truth_file_sha256": file_sha(TRUTH),
    "accept_cases": len(t["accept_cases"]),
    "refuse_cases": len(t["refuse_cases"]),
    "frozen_policy": t["frozen_policy"],
    "must_rerun": t["must_rerun"],
    "v9_closure_expect": t["v9_closure_expect"],
    "v9_register_state": {"path": reg.relative_to(ROOT).as_posix(), "entries": len(entries),
                          "actions": sorted({e.get("action") for e in entries}),
                          "executed": [e["proposal_id"] for e in entries if e.get("executed")]},
    "help": "改真值集后重跑本脚本会刷新 frozen_sha256；只校验请运行 tests/revision_truth_test.py",
}
(LOGS / "phase6b_m3_truth_freeze.json").write_text(json.dumps(record, ensure_ascii=False, indent=1),
                                                  encoding="utf-8")
print("truth canonical sha256:", sha_before)
print("accept/refuse 用例:", len(t["accept_cases"]), "/", len(t["refuse_cases"]))
print("v9 登记表:", len(entries), "条 |", record["v9_register_state"]["actions"])
print("json ->", LOGS / "phase6b_m3_truth_freeze.json")
