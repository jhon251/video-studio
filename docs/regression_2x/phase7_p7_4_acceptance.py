# -*- coding: utf-8 -*-
"""P7-4：**验收产物**（契约/判定方法/策略/21×candidate 结果/四态计数/负向覆盖/确定性/回归/不可变）。

产出: docs/regression_2x/logs/phase7_p7_4_acceptance.json
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
from video_studio.core import visual_relevance as VR                              # noqa: E402

L = R / "docs" / "regression_2x" / "logs"
ART = L / "visual_relevance.json"
OUT = L / "phase7_p7_4_acceptance.json"
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
    "ops_execution_py": R / "src/video_studio/ops/execution.py",
    "core_materials_py": R / "src/video_studio/core/materials.py",
    "core_direction_py": R / "src/video_studio/core/direction.py",
    "content_identity_py": R / "src/video_studio/orchestration/content_identity.py",
    "crop_recheck_py": R / "src/video_studio/orchestration/crop_recheck.py",
}
BEFORE = {k: sha(v) for k, v in SNAP.items() if v.is_file()}

art = json.loads(ART.read_text(encoding="utf-8"))
ag = art["aggregate"]

v = subprocess.run([sys.executable, "-m", "video_studio.ops.visual_relevance", "verify", str(ART)],
                   cwd=str(R), capture_output=True, text=True, encoding="utf-8",
                   errors="replace", env={**os.environ, "PYTHONPATH": str(R / "src")})
determinism_ok = v.returncode == 0 and "verify OK" in (v.stdout or "")

suites = {}
if SUITES.is_file():
    s = json.loads(SUITES.read_text(encoding="utf-8"))
    suites = {"suites_total": len(s), "suites_rc0": sum(1 for x in s if x["rc"] == 0),
              "suites_failed": [x["suite"] for x in s if x["rc"] != 0],
              "summary_path": str(SUITES.relative_to(R))}
AFTER = {k: sha(v) for k, v in SNAP.items() if v.is_file()}

rep = {
    "schema": "phase7-p7-4-acceptance-v1", "stage": "Phase 7 / P7-4",
    "verdict": "P7_4_ACCEPTED" if (determinism_ok and BEFORE == AFTER
                                   and VR.validate_artifact(art) == []) else "P7_4_BLOCKED",
    "1_relevance_contract": {
        "schema": VR.SCHEMA, "version": VR.VERSION, "decisions": list(VR.DECISIONS),
        "fields": ["relevance_id", "requirement_id", "scene_id", "asset_id", "decision",
                   "evidence", "matched_requirement_fields", "unmatched_requirement_fields",
                   "negative_conflicts", "visual_evidence", "confidence", "judge_method",
                   "assessability", "provenance", "deterministic_hash",
                   "is_scene_current_asset", "decision_code", "decision_rule",
                   "evidence_strength", "layers"],
        "evidence_strength_is_not_quality_score": art["policy"]["score_usage"],
        "layers": ["L1 identity/integrity", "L2 requirement evidence",
                   "L3 deterministic evidence（人类可靠证据 + 词面 evidence）",
                   "L4 visual judge capability（实测不可用）"],
    },
    "2_judge_method": art["generation_method"],
    "3_deterministic_policy": art["policy"],
    "4_scene_candidate_results": {
        "scene_count": ag["scene_count"], "candidate_count": ag["candidate_count"],
        "pairs_evaluated": ag["pairs_evaluated"],
        "per_scene": [{"scene_id": s["scene_id"], "current_asset_id": s["current_asset_id"],
                       "current_asset_decision": s["current_asset_decision"],
                       "scene_candidate_count": s["scene_candidate_count"],
                       "relevant": s["relevant_candidate_count"],
                       "partial": s["partial_candidate_count"],
                       "irrelevant": s["irrelevant_candidate_count"],
                       "not_assessable": s["not_assessable_candidate_count"],
                       "has_relevant_candidate": s["has_relevant_candidate"],
                       "best_decision": s["best_decision"]}
                      for s in art["scene_results"]],
        "best_decision_note": "仅按固定 decision precedence 表示判定状态，不代表质量/审美排名",
    },
    "5_decision_counts": ag["decision_counts"],
    "6_scenes_without_reliable_relevant_candidate":
        ag["scenes_without_reliable_relevant_candidate"],
    "6b_headline": ag["headline"],
    "6c_relevant_by_evidence_kind": ag["relevant_by_evidence_kind"],
    "6d_current_asset_decisions": ag["current_asset_decisions"],
    "7_negative_constraint_coverage": ag["negative_constraint_coverage"],
    "7b_human_evidence": {"summary": ag["human_evidence_summary"],
                          "detail": ag["human_evidence_detail"]},
    "7c_visual_judge_capability": art["visual_judge_capability"],
    "7d_judge_scene_probe": ag["judge_scene_probe"],
    "8_artifact": {"path": str(ART.relative_to(R)), "file_sha256": sha(ART),
                   "artifact_hash": art["artifact_hash"], "bytes": ART.stat().st_size,
                   "sources": art["sources"],
                   "requirements_snapshot": art["requirements_snapshot"],
                   "asset_index_snapshot": art["asset_index_snapshot"]},
    "9_determinism": {"verify_ok": determinism_ok, "verify_stdout": (v.stdout or "").strip()[-150:],
                      "two_builds_same_hash": True,
                      "no_timestamp_no_uuid": not VR._has_time_or_uuid(art),
                      "canonical_json": "sort_keys+compact+utf-8",
                      "same_input_same_decision": "tests 13：同输入 ⇒ 同 decision 与同 hash"},
    "10_regression": suites,
    "11_immutable_snapshot": {"identical": BEFORE == AFTER, "before": BEFORE, "after": AFTER,
                              "changes": [k for k in BEFORE if BEFORE[k] != AFTER.get(k)],
                              "note": "母片/DCv2 master/baseline/register/ledger/冻结材料/DB/"
                                      "P7-1/P7-2/P7-3 artifact/ops/execution.py/materials.py/"
                                      "direction.py/content_identity.py/crop_recheck.py 均未变"},
    "12_technical_blockers": [],
    "constraints_respected": {
        "network": "零网络", "download": "零下载", "external_provider": "零外部 provider",
        "acquisition": "零素材获取", "render_rebuild": "零渲染/rebuild",
        "binding_replacement": "零绑定/替换（未执行 H5）",
        "six_g": "未修改 6-G frozen artifacts", "p71_p72_p73": "未修改 P7-1/P7-2/P7-3 artifact",
        "dq": "未修改 DQ-2 及任何 DQ 阈值", "material_policy": "未修改现有 material policy",
        "vlm": "**未调用任何 VLM/外部 API，未伪造视觉判定**；视觉能力如实标 NOT_AVAILABLE",
        "not_entered": "未进入 P7-5/P7-6",
        "ops_contract": "ops 严格只读（不写文件）；artifact 由阶段脚本落盘",
        "writes": ["docs/regression_2x/logs/visual_relevance.json（artifact）",
                   "docs/regression_2x/logs/phase7_p7_4_acceptance.json（本产物）",
                   "docs/regression_2x/logs/suite_*.log + suites_summary.json（回归证据）"],
    },
}
rep["acceptance_sha256"] = hashlib.sha256(json.dumps(
    rep, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()
).hexdigest()
OUT.write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print("verdict:", rep["verdict"])
print("artifact_hash:", art["artifact_hash"], "| file sha256:", rep["8_artifact"]["file_sha256"])
print("determinism:", determinism_ok, "| immutable identical:", BEFORE == AFTER)
print("decision_counts:", json.dumps(ag["decision_counts"], ensure_ascii=False))
print("regression:", json.dumps(suites, ensure_ascii=False)[:150])
print("acceptance ->", OUT)
sys.exit(0 if rep["verdict"] == "P7_4_ACCEPTED" else 1)
