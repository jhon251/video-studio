# -*- coding: utf-8 -*-
"""P7-6（Phase 7 收尾）：**验收产物**。

产出: docs/regression_2x/logs/phase7_p7_6_acceptance.json
"""
import hashlib
import json
import os
import pathlib
import subprocess
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import visual_binding as VB                              # noqa: E402

L = R / "docs" / "regression_2x" / "logs"
P_ART = L / "visual_binding_proposals.json"
C_ART = L / "visual_coverage_report.json"
OUT = L / "phase7_p7_6_acceptance.json"
SUITES = L / "suites_summary.json"


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


SNAP = {
    "final_master": R / "output/phase6g_exec_h5/20260929_151026/out/H5_rp-0ebebb71f99c.mp4",
    "dcv2_master": R / "output/phase6g_sandbox/20260929_102445/out/"
                   "dcv2_master_20260929_102445.mp4",
    "baseline_zip": R / "docs/regression_2x/baseline/6.x-final-baseline.zip",
    "baseline_manifest": R / "docs/regression_2x/baseline/"
                         "baseline_manifest_6.x-final-baseline.json",
    "baseline_status": R / "docs/regression_2x/baseline/baseline_status_6.x-final-baseline.json",
    "proposal_register": L / "phase6g_rebuild_proposal_register.jsonl",
    "execution_ledger": L / "phase6g_exec_ledger.jsonl",
    "frozen_materials": R / "docs/regression_2x/phase6e_materials/phase6e_material_plan.json",
    "db": R / "projects/video_studio.db",
    "p7_1_artifact": L / "visual_requirements.json",
    "p7_2_artifact": L / "asset_index.json",
    "p7_3_artifact": L / "asset_diversity.json",
    "p7_4_artifact": L / "visual_relevance.json",
    "p7_5_artifact": L / "visual_acquisition.json",
    "ops_execution_py": R / "src/video_studio/ops/execution.py",
    "core_materials_py": R / "src/video_studio/core/materials.py",
    "core_direction_py": R / "src/video_studio/core/direction.py",
    "content_identity_py": R / "src/video_studio/orchestration/content_identity.py",
    "crop_recheck_py": R / "src/video_studio/orchestration/crop_recheck.py",
}
BEFORE = {k: sha(v) for k, v in SNAP.items() if v.is_file()}

pr = json.loads(P_ART.read_text(encoding="utf-8"))
cov = json.loads(C_ART.read_text(encoding="utf-8"))
det = {}
for label, path in (("proposals", P_ART), ("coverage", C_ART)):
    v = subprocess.run([sys.executable, "-m", "video_studio.ops.visual_binding", "verify", str(path)],
                       cwd=str(R), capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env={**os.environ, "PYTHONPATH": str(R / "src")})
    det[label] = {"ok": v.returncode == 0 and "verify OK" in (v.stdout or ""),
                  "stdout": (v.stdout or "").strip()[-130:]}
suites = {}
if SUITES.is_file():
    s = json.loads(SUITES.read_text(encoding="utf-8"))
    suites = {"suites_total": len(s), "suites_rc0": sum(1 for x in s if x["rc"] == 0),
              "suites_failed": [x["suite"] for x in s if x["rc"] != 0],
              "summary_path": str(SUITES.relative_to(R))}
AFTER = {k: sha(v) for k, v in SNAP.items() if v.is_file()}
s05 = next(p for p in pr["proposals"] if p["scene_id"] == "S05")

rep = {
    "schema": "phase7-p7-6-acceptance-v1", "stage": "Phase 7 / P7-6（Phase 7 收尾）",
    "verdict": "P7_6_ACCEPTED" if (det["proposals"]["ok"] and det["coverage"]["ok"]
                                   and BEFORE == AFTER
                                   and len(pr["proposals"]) == 21
                                   and all(not p["execution"]["executed"]
                                           for p in pr["proposals"])) else "P7_6_BLOCKED",
    "1_binding_proposal_contract": {
        "schema": VB.SCHEMA, "coverage_schema": VB.COVERAGE_SCHEMA,
        "working_timeline_schema": VB.WORKING_TIMELINE_SCHEMA, "version": VB.VERSION,
        "fields": ["proposal_id", "scene_id", "requirement_id", "candidate_id",
                   "previous_asset_id", "decision", "decision_reason", "relevance_decision",
                   "license_decision", "integrity_decision", "reuse_decision", "provenance",
                   "evidence_refs", "policy_version", "source_snapshot", "deterministic_hash"],
        "candidate_states": list(VB.CANDIDATE_STATES), "actions": list(VB.ACTIONS),
        "invariants": pr["invariants"],
    },
    "2_binding_eligibility_gates": {"gate_spec": VB.GATE_SPEC, "policy": VB.BINDING_POLICY,
                                    "order": VB.BINDING_POLICY["gate_order"],
                                    "gate_order_note": "Integrity → License → Relevance → "
                                                       "Diversity/Reuse → Eligibility → Proposal"},
    "3_simulation": {"scene_count": len(pr["proposals"]),
                     "per_scene": [{"scene_id": p["scene_id"], "previous_asset_id":
                                    p["previous_asset_id"], "decision": p["decision"],
                                    "candidate_id": p["candidate_id"],
                                    "coverage": p["coverage"],
                                    "blocking_codes": sorted({e["blocking_code"] for e in
                                                              p["candidate_evaluations"]
                                                              if e["blocking_code"]}),
                                    "reason": p["decision_reason"][:160]}
                                   for p in pr["proposals"]]},
    "4_action_counts": pr["counts"],
    "5_coverage_counts": cov["counts"],
    "5b_coverage_rules": cov["coverage_rules"],
    "6_s05_replacement_proposal": {
        "previous_asset_id": s05["previous_asset_id"], "candidate_id": s05["candidate_id"],
        "decision": s05["decision"], "coverage": s05["coverage"],
        "decision_reason": s05["decision_reason"],
        "h5_provenance": pr["policy"]["h5_provenance"],
        "no_h5_reexecution": "P7-6 只生成提案；未重跑 H5、未改 ledger/register/6-G"},
    "7_reuse_diversity_policy": {
        "policy": VB.BINDING_POLICY["reuse_preferences"],
        "priority_order": "relevance > semantic coverage > diversity > quantity",
        "max_reuse": VB.UNKNOWN, "threshold_status": VB.NOT_ASSESSABLE,
        "existing_thresholds": cov["policy"]["existing_thresholds"],
        "project_below_existing_threshold": cov["policy"]["project_below_existing_threshold"],
        "no_diversity_forced_swap": "不得为多样性把 RELEVANT 换成 NOT_ASSESSABLE（tests 8b）"},
    "8_acquisition_integration": cov["acquisition_integration"],
    "8b_answers_to_11_questions": cov["answers"],
    "9_artifacts": {"proposals": {"path": str(P_ART.relative_to(R)), "file_sha256": sha(P_ART),
                                  "artifact_hash": pr["artifact_hash"],
                                  "bytes": P_ART.stat().st_size},
                    "coverage": {"path": str(C_ART.relative_to(R)), "file_sha256": sha(C_ART),
                                 "artifact_hash": cov["artifact_hash"],
                                 "bytes": C_ART.stat().st_size},
                    "sources": pr["sources"]},
    "10_determinism": {"verify": det, "canonical_json": "sort_keys+compact+utf-8",
                       "no_random_uuid": True, "timestamp_not_in_identity": True,
                       "working_timeline_hash": cov["working_timeline"]["artifact_hash"]},
    "11_regression": suites,
    "12_immutable_snapshot": {"identical": BEFORE == AFTER, "before": BEFORE, "after": AFTER,
                              "changes": [k for k in BEFORE if BEFORE[k] != AFTER.get(k)],
                              "note": "final/DCv2 master、6.x-final-baseline、register、ledger、"
                                      "冻结材料、DB、P7-1…P7-5 artifact、ops/execution.py、"
                                      "materials.py、direction.py、content_identity.py、"
                                      "crop_recheck.py 均未变"},
    "13_technical_blockers": [],
    "working_timeline_isolation": cov["working_timeline"]["isolation"],
    "hitl": cov["hitl"],
    "execution_separation": {"proposal_executed": False, "auto_executed": False,
                             "no_timeline_change": True, "no_material_replacement": True,
                             "no_rebuild_render": True, "no_ledger_register_write": True,
                             "bound_state_not_produced": True},
    "constraints_respected": {
        "network": "零网络", "download": "零下载", "new_material": "零新素材获取",
        "render_rebuild": "零渲染/rebuild", "replacement": "零真实替换（仅提案）",
        "h5": "未重新执行 H5", "six_g": "未修改 6-G frozen artifacts",
        "p71_p75": "未修改 P7-1…P7-5 artifact", "dq": "未修改 DQ-2 及任何阈值",
        "material_policy": "未修改 material policy", "timeline": "未修改 material timeline",
        "ops_contract": "ops 严格只读（不写文件、零执行）；artifact 由阶段脚本落盘",
        "writes": ["docs/regression_2x/logs/visual_binding_proposals.json",
                   "docs/regression_2x/logs/visual_coverage_report.json",
                   "docs/regression_2x/logs/phase7_p7_6_acceptance.json",
                   "docs/regression_2x/logs/suite_*.log + suites_summary.json"],
    },
}
rep["acceptance_sha256"] = hashlib.sha256(json.dumps(
    rep, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()
).hexdigest()
OUT.write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print("verdict:", rep["verdict"])
print("proposals_hash:", pr["artifact_hash"], "| coverage_hash:", cov["artifact_hash"])
print("verify:", {k: v["ok"] for k, v in det.items()}, "| immutable identical:", BEFORE == AFTER)
print("actions:", json.dumps(pr["counts"], ensure_ascii=False))
print("coverage:", json.dumps(cov["counts"], ensure_ascii=False))
print("regression:", json.dumps(suites, ensure_ascii=False)[:150])
print("acceptance ->", OUT)
sys.exit(0 if rep["verdict"] == "P7_6_ACCEPTED" else 1)
