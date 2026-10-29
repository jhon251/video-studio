# -*- coding: utf-8 -*-
"""Phase 13-D 收尾：从已落账的执行记录生成 P13-4 报告（**不重复执行**）+ 核验候选与链。"""
import hashlib
import json
import pathlib
import sys
import time

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")
recs = [json.loads(x) for x in (L / "phase13d_execution_ledger.jsonl").read_text(
    encoding="utf-8").splitlines() if x.strip()]
rec = recs[-1]
out0 = (rec.get("outputs") or [{}])[0]
cand = pathlib.Path(out0.get("path") or "")
cand_abs = cand if cand.is_absolute() else R / cand
exists = cand_abs.is_file()
sha_now = hashlib.sha256(cand_abs.read_bytes()).hexdigest() if exists else None
rc = rec.get("recheck") or {}
ap = [json.loads(x) for x in (L / "phase13d_approvals.jsonl").read_text(
    encoding="utf-8").splitlines() if x.strip()]
report = {
    "schema": "phase13d-p13-4-v1",
    "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "approval_upstream": {"file": "logs/phase13c_approvals.jsonl",
                          "approval_id": "ap-0850dfa8c52f",
                          "binds_proposal": "bp-6320bf486a082901",
                          "approved_by": "human:project-owner",
                          "approval_document": "Phase 13-C 授权书 §0 + 本消息（human:project-owner 签发）"},
    "approval_executor": {k: ap[-1].get(k) for k in
                          ("approval_id", "proposal_id", "proposal_sha256", "approved_by",
                           "approved_at", "approval_document", "recorded_by")},
    "derived_executor_proposal": {"proposal_id": rec.get("proposal_id"),
                                  "proposal_label": rec.get("proposal_label"),
                                  "derived_from": "bp-6320bf486a082901",
                                  "why": "6-B 执行器要求 affected_scope/proposed_change；"
                                         "P7-6 提案内容被批准 sha256 绑定 ⇒ 不可改动，故派生执行提案"},
    "execution": {"state": rec.get("state"), "executor_invoked": rec.get("executor_invoked"),
                  "promoted": rec.get("promoted"), "sandbox_only": rec.get("sandbox_only"),
                  "executed_at": rec.get("executed_at"), "notes": rec.get("notes")},
    "candidate": {"path": str(cand), "bytes": out0.get("bytes"), "sha256_recorded": out0.get("sha256"),
                  "sha256_now": sha_now, "exists": exists,
                  "sha256_match": bool(sha_now and sha_now == out0.get("sha256")),
                  "window": out0.get("window"), "asset_id": out0.get("asset_id"),
                  "source_film_sha256": "22705c7d7ea20b40…（母片，未变）"},
    "asset_evidence": (rec.get("exec_evidence") or {}).get("asset_evidence"),
    "asset_verifications": (rec.get("exec_evidence") or {}).get("asset_verifications"),
    "pi_recheck": {"pi_gate_outcome": rc.get("pi_gate_outcome"),
                   "pi_metrics": rc.get("pi_metrics"), "pi_failed": rc.get("pi_failed"),
                   "pre_render_gate": rc.get("pre_render_gate"),
                   "post_render_gate": rc.get("post_render_gate"),
                   "planning_drift_blocking": rc.get("planning_drift_blocking")},
    "dq_recheck": {"dq_summary": rc.get("dq_summary"), "dq_metrics": rc.get("dq_metrics"),
                   "dq_3_detail": (rc.get("dq_details") or {}).get("DQ-3")},
    "verdict": {
        "execution": "SUCCEEDED（真实执行器产出候选；零 promotion）",
        "pi_gates": "BLOCKED（6 门中 5 门 FAIL：PI-1/2/3/5/6；PI-4 PASS）⇒ **未通过强制复核**",
        "dq": "overall FAIL（DQ-2/3/4/5/6/8 FAIL、DQ-1 UNKNOWN）",
        "honest_note": "PI-2 时长缺口 570.344 s 与 PI-3 尾部静音 570.874 s **远超**本次 55 s 窗口编辑，"
                       "疑为沙箱 ctx 的时基/字幕基未完整附着（6-C 实际用法与可见 build_ctx 的差异），"
                       "**尚未定位** ⇒ 不得据此判定「替换本身有问题」，也不得改写为 PASS",
    },
    "open_question": {"id": "P13D-OPEN-1",
                      "summary": "沙箱 ctx 是否需 attach_dcv2_time_base/母版 caption cues 方能通过 PI-1/2/3/5/6",
                      "status": "UNRESOLVED（下一阶段优先定位）",
                      "evidence": "logs/phase13d_execution_ledger.jsonl（recheck.pi_metrics）"},
    "zero_promotion": True, "source_project_touched": False, "master_touched": False,
}
(L / "phase13d_p13_4.json").write_text(json.dumps(report, ensure_ascii=False, indent=1,
                                                sort_keys=True, default=str), encoding="utf-8")
print("候选:", cand.name, "| 存在:", exists, "| sha 记录 vs 现值一致:", report["candidate"]["sha256_match"])
print("execution:", rec.get("state"), "| promoted:", rec.get("promoted"))
print("PI:", json.dumps(rc.get("pi_metrics"), ensure_ascii=False))
print("DQ overall:", (rc.get("dq_summary") or {}).get("overall"))
print("产物:", "phase13d_p13_4.json")
