# -*- coding: utf-8 -*-
"""6-B/M5 —— 冻结 M5 真值集（规范化 sha256）并记录用例数 + v9 期望摘要。

用法: python docs/regression_2x/phase6b_m5_build_truth.py
产出: logs/phase6b_m5_truth_freeze.json（并把 frozen_sha256 写回真值集文件）
"""
import hashlib
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
LOGS = ROOT / "docs" / "regression_2x" / "logs"
TRUTH = ROOT / "tests" / "fixtures" / "execution_reliability_truth_v1.json"
OUT = LOGS / "phase6b_m5_truth_freeze.json"
V9 = LOGS / "phase6b_m5_v9_execution.json"


def canonical(obj: dict) -> str:
    return hashlib.sha256(json.dumps({k: v for k, v in obj.items() if k != "frozen_sha256"},
                                     sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


data = json.loads(TRUTH.read_text(encoding="utf-8"))
sha = canonical(data)
data["frozen_sha256"] = sha
TRUTH.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
assert canonical(json.loads(TRUTH.read_text(encoding="utf-8"))) == sha, "冻结写回后 sha 漂移"

v9 = json.loads(V9.read_text(encoding="utf-8")) if V9.is_file() else {}
rec = {
    "schema": "m5-truth-freeze-v1", "stage": "6-B/M5",
    "truth_path": TRUTH.relative_to(ROOT).as_posix(),
    "truth_canonical_sha256": sha,
    "truth_file_sha256": hashlib.sha256(TRUTH.read_bytes()).hexdigest(),
    "conflict_case_count": len(data["conflict_cases"]),
    "asset_case_count": len(data["asset_cases"]),
    "batch_case_count": len(data["batch_cases"]),
    "overlap_policy": data["overlap_policy"],
    "closes_pending": data["closes_pending"],
    "v9_summary": (v9.get("summary") or {}).get("state_counts"),
    "v9_asset_e2e": [(e["proposal_label"], e["asset_evidence"]["asset_id"],
                      e["asset_evidence"]["corr_new_mean"], e["asset_evidence"]["replaced"])
                     for e in (v9.get("asset_e2e") or [])],
    "note": "真值集只描述**期望**；证据由 phase6b_m5_execute_v9.py 在真实 v9 上产生（沙箱内执行）。",
}
OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
print("truth canonical sha256:", sha)
print("cases: conflict {} / asset {} / batch {}".format(
    rec["conflict_case_count"], rec["asset_case_count"], rec["batch_case_count"]))
print("v9 states:", rec["v9_summary"])
print("v9 asset E2E:", rec["v9_asset_e2e"])
print("json ->", OUT)
