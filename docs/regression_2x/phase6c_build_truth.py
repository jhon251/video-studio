# -*- coding: utf-8 -*-
"""6-C —— 冻结批次真值集（规范化 sha256 写回 + 记录摘要）。

用法: python docs/regression_2x/phase6c_build_truth.py
产出: logs/phase6c_truth_freeze.json
"""
import hashlib
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
LOGS = ROOT / "docs" / "regression_2x" / "logs"
TRUTH = ROOT / "tests" / "fixtures" / "directorial_batch_truth_v1.json"
BATCH = LOGS / "phase6c_batch.json"
OUT = LOGS / "phase6c_truth_freeze.json"


def canonical(obj: dict) -> str:
    return hashlib.sha256(json.dumps({k: v for k, v in obj.items() if k != "frozen_sha256"},
                                     sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


data = json.loads(TRUTH.read_text(encoding="utf-8"))
sha = canonical(data)
data["frozen_sha256"] = sha
TRUTH.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
assert canonical(json.loads(TRUTH.read_text(encoding="utf-8"))) == sha

b = json.loads(BATCH.read_text(encoding="utf-8")) if BATCH.is_file() else {}
rec = {"schema": "directorial-batch-freeze-v1", "stage": "6-C",
       "truth_path": TRUTH.relative_to(ROOT).as_posix(),
       "truth_canonical_sha256": sha,
       "truth_file_sha256": hashlib.sha256(TRUTH.read_bytes()).hexdigest(),
       "batch_summary": (b.get("summary") or {}).get("state_counts"),
       "candidate_count": b.get("candidate_count"),
       "candidates": [{"index": c["index"], "proposal_label": c["proposal_label"],
                       "film": c["film"], "film_sha256": c["film_sha256"],
                       "bytes": c["bytes"], "pi_gate_outcome": c["pi_gate_outcome"],
                       "dq_metrics": c["dq_metrics"],
                       "audio_identical": (c["verification"] or {}).get("audio_identical_stream"),
                       "duration_delta_s": (c["verification"] or {})
                       .get("duration_delta_vs_master_s")} for c in b.get("candidates") or []],
       "h4_decision": (b.get("h4_decision") or {}).get("decision"),
       "h2_state": (b.get("batches") or [{}, {}])[1].get("states") if b.get("batches") else None,
       "note": "真值集只描述**期望**；证据由 phase6c_batch.py 在真实 v9 上产生（沙箱内执行，"
               "v9 母版零改动，不做 promotion）。"}
OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
print("truth canonical sha256:", sha)
print("candidates:", [(c["index"], c["proposal_label"], c["pi_gate_outcome"],
                       c["audio_identical"], c["duration_delta_s"])
                      for c in rec["candidates"]])
print("H4:", rec["h4_decision"], "| ledger:", (b.get("summary") or {}).get("ledger"))
print("json ->", OUT)
