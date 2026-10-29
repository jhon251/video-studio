# -*- coding: utf-8 -*-
"""6-B/M2 —— Human Review 真值集**冻结** + 契约统计（幂等；只写真值集自身与冻结记录）。

用法: python docs/regression_2x/phase6b_m2_build_truth.py
产出: logs/phase6b_m2_truth_freeze.json
"""
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
LOGS = ROOT / "docs" / "regression_2x" / "logs"
TRUTH = ROOT / "tests" / "fixtures" / "human_review_truth_v1.json"


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

ledger = LOGS / "phase6b_m2_review_ledger_v9.jsonl"
entries = []
if ledger.is_file():
    for line in ledger.read_text(encoding="utf-8").splitlines():
        if line.strip():
            entries.append(json.loads(line))
dec_counts = Counter(e.get("decision") for e in entries)
record = {
    "schema": "human-review-truth-freeze-v1",
    "stage": "6-B/M2",
    "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "truth_path": TRUTH.relative_to(ROOT).as_posix(),
    "truth_canonical_sha256": sha_before,
    "truth_file_sha256": file_sha(TRUTH),
    "case_count": len(t["cases"]),
    "case_ids": [c["id"] for c in t["cases"]],
    "decision_vocabulary": t["decision_vocabulary"],
    "required_decision_fields": t["required_decision_fields"],
    "unknown_policy": t["unknown_policy"],
    "non_execution_contract": t["non_execution_contract"],
    "v9_closure_expect": t["v9_closure_expect"],
    "v9_ledger_state": {"path": ledger.relative_to(ROOT).as_posix(), "entries": len(entries),
                        "decision_counts": dict(dec_counts)},
    "help": "改真值集后重跑本脚本会刷新 frozen_sha256（= 一次可审计的改真值动作）；"
            "只想校验请运行 tests/review_truth_test.py",
}
(LOGS / "phase6b_m2_truth_freeze.json").write_text(json.dumps(record, ensure_ascii=False, indent=1),
                                                  encoding="utf-8")
print("truth canonical sha256:", sha_before)
print("cases:", len(t["cases"]), "| 决策词汇:", t["decision_vocabulary"])
print("v9 台账:", len(entries), "条 |", dict(dec_counts))
print("json ->", LOGS / "phase6b_m2_truth_freeze.json")
