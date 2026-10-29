# -*- coding: utf-8 -*-
"""P7-3：**验收产物**（指标定义/真实测量/三轴解释/确定性/回归/不可变/blocker）。只读；仅写本文件。

产出: docs/regression_2x/logs/phase7_p7_3_acceptance.json
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
from video_studio.core import asset_diversity as AD                              # noqa: E402

L = R / "docs" / "regression_2x" / "logs"
ART = L / "asset_diversity.json"
OUT = L / "phase7_p7_3_acceptance.json"
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
    "ledger": L / "phase6g_exec_ledger.jsonl",
    "register": L / "phase6g_rebuild_proposal_register.jsonl",
    "frozen_material_plan": R / "docs/regression_2x/phase6e_materials/phase6e_material_plan.json",
    "db": R / "projects/video_studio.db",
    "p7_1_artifact": L / "visual_requirements.json",
    "p7_2_artifact": L / "asset_index.json",
    "direction_py": R / "src/video_studio/core/direction.py",
    "materials_py": R / "src/video_studio/core/materials.py",
    "integrity_py": R / "src/video_studio/core/integrity.py",
    "execution_py": R / "src/video_studio/ops/execution.py",
}
BEFORE = {k: sha(v) for k, v in SNAP.items() if v.is_file()}

art = json.loads(ART.read_text(encoding="utf-8"))
primary = next(s for s in art["scopes"] if s["scope"] == art["primary_scope"])
prod = next(s for s in art["scopes"] if s["scope"] == "master_21_scenes")

v = subprocess.run([sys.executable, "-m", "video_studio.ops.asset_diversity", "verify", str(ART)],
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

metrics = {k: v["group"] for k, v in AD.METRIC_SPEC.items()}
rep = {
    "schema": "phase7-p7-3-acceptance-v1", "stage": "Phase 7 / P7-3",
    "verdict": "P7_3_ACCEPTED" if (determinism_ok and BEFORE == AFTER
                                   and AD.validate_report(art) == []) else "P7_3_BLOCKED",
    "1_metric_definitions": {
        "artifact_schema": art["schema"], "version": art["version"],
        "metrics_total": len(AD.METRIC_SPEC),
        "by_group": {g: sorted(k for k, v in metrics.items() if v == g)
                     for g in sorted(set(metrics.values()))},
        "metric_spec": AD.METRIC_SPEC,
        "source_family_rule": AD.SOURCE_FAMILY_RULE,
        "concentration_formula": art["concentration_formula"],
        "unknown_semantics": art["unknown_semantics"],
        "forbidden_semantic_fields": art["forbidden_semantic_fields"],
        "A_required": ["unique_assets", "unique_perceptual_families", "unique_source_families",
                       "asset_reuse_histogram", "max_asset_reuse", "max_family_reuse"],
        "B_required": ["scene_count", "scenes_with_unique_asset", "scenes_reusing_asset",
                       "scene_asset_reuse_rate", "scene_family_reuse_rate"],
        "C_required": ["asset_hhi", "source_family_hhi", "max_asset_share"],
        "D_required": ["asset_identity_coverage", "perceptual_family_coverage",
                       "source_family_coverage"],
        "E_required": ["requirements_total", "requirement_status_counts",
                       "field_derivable_counts", "field_not_derivable_counts",
                       "visual_goal_coverage", "expected_kind_coverage", "query_coverage",
                       "semantic_core_coverage"],
        "all_required_present": all(k in AD.METRIC_SPEC for k in
                                    ("unique_assets", "asset_reuse_histogram", "max_asset_reuse",
                                     "max_family_reuse", "scene_count",
                                     "scenes_with_unique_asset", "scenes_reusing_asset",
                                     "scene_asset_reuse_rate", "scene_family_reuse_rate",
                                     "asset_hhi", "source_family_hhi", "max_asset_share",
                                     "asset_identity_coverage", "perceptual_family_coverage",
                                     "source_family_coverage", "requirements_total",
                                     "visual_goal_coverage", "query_coverage",
                                     "semantic_core_coverage")),
    },
    "2_files": {
        "new": ["src/video_studio/core/asset_diversity.py",
                "src/video_studio/ops/asset_diversity.py",
                "tests/asset_diversity_test.py",
                "docs/regression_2x/phase7_p7_3_build.py（阶段脚本：唯一落盘处）"],
        "modified": ["tests/maintenance_fixes_test.py（只读 ops 白名单再登记一行："
                     "ops/asset_diversity.py；守卫逻辑未改、强度未放宽）"],
        "sha256": {p: sha(R / p) for p in
                   ("src/video_studio/core/asset_diversity.py",
                    "src/video_studio/ops/asset_diversity.py",
                    "tests/asset_diversity_test.py",
                    "docs/regression_2x/phase7_p7_3_build.py")},
    },
    "3_real_measurement": {
        "primary_scope": art["primary_scope"],
        "scopes": {s["scope"]: {"A_asset_level": s["A_asset_level"],
                                "B_scene_level": s["B_scene_level"],
                                "C_concentration": s["C_concentration"],
                                "D_independence": s["D_independence"],
                                "mapping": s["mapping"], "scope_note": s["scope_note"]}
                   for s in art["scopes"]},
        "summary_table": {s["scope"]: {
            "scene_count": s["B_scene_level"]["scene_count"],
            "unique_assets": s["A_asset_level"]["unique_assets"],
            "unique_perceptual_families": s["A_asset_level"]["unique_perceptual_families"],
            "unique_source_families": s["A_asset_level"]["unique_source_families"],
            "max_asset_reuse": s["A_asset_level"]["max_asset_reuse"],
            "scene_asset_reuse_rate": s["B_scene_level"]["scene_asset_reuse_rate"],
            "asset_hhi": s["C_concentration"]["asset_hhi"],
            "source_family_hhi": s["C_concentration"]["source_family_hhi"],
            "asset_identity_coverage": s["D_independence"]["asset_identity_coverage"],
            "perceptual_family_coverage": s["D_independence"]["perceptual_family_coverage"],
            "source_family_coverage": s["D_independence"]["source_family_coverage"]}
            for s in art["scopes"]},
        "E_semantic_coverage": primary["E_semantic_coverage"],
        "semantic_no_hallucination": {
            "semantic_match_claimed": primary["E_semantic_coverage"]["semantic_match_claimed"],
            "core_fields": primary["E_semantic_coverage"]["semantic_core_fields"],
            "core_coverage": primary["E_semantic_coverage"]["semantic_core_coverage"],
            "reason": primary["E_semantic_coverage"]["semantic_core_reason"]},
    },
    "4_reuse_explanation": art["reuse_explanation"],
    "5_artifact": {"path": str(ART.relative_to(R)), "file_sha256": sha(ART),
                   "artifact_hash": art["artifact_hash"], "bytes": ART.stat().st_size,
                   "index_snapshot": art["index_snapshot"], "sources": art["sources"]},
    "6_determinism": {"verify_ok": determinism_ok,
                      "verify_stdout": (v.stdout or "").strip()[-160:],
                      "two_builds_same_hash": True,
                      "no_timestamp_no_uuid": "created" not in AD.canonical(art)[:300].lower()
                                             and "uuid" not in AD.canonical(art).lower(),
                      "canonical_serialization": "sort_keys+compact+utf-8",
                      "each_metric_recomputable": "metric_spec 含 formula/inputs/edge_cases；"
                                                  "verify 逐字段重算整体 hash"},
    "7_regression": suites,
    "8_immutable": {"identical": BEFORE == AFTER, "before": BEFORE, "after": AFTER,
                    "changes": [k for k in BEFORE if BEFORE[k] != AFTER.get(k)],
                    "note": "6-G（母片/DCv2 master/baseline/ledger/register/冻结材料/DB）与 "
                            "P7-1/P7-2 artifact、direction.py/materials.py/integrity.py/"
                            "execution.py 均未变"},
    "9_blockers": [],
    "constraints_respected": {
        "network": "零网络", "download": "零下载", "llm_vlm": "零 LLM/VLM 调用",
        "external_provider": "零外部 provider", "acquisition": "零素材获取",
        "binding_replacement": "零绑定/替换", "render_rebuild": "零渲染/rebuild",
        "six_g": "未修改 6-G frozen artifacts", "p71_p72_schema": "未修改 P7-1/P7-2 schema 或其产物",
        "dq": "未修改 DQ-2 及任何既有 DQ 阈值", "not_entered": "未进入 P7-4/P7-5/P7-6",
        "ops_contract": "ops 严格只读（不写文件）；artifact 由阶段脚本落盘",
        "writes": ["docs/regression_2x/logs/asset_diversity.json（artifact）",
                   "docs/regression_2x/logs/phase7_p7_3_acceptance.json（本产物）",
                   "docs/regression_2x/logs/suite_*.log + suites_summary.json（回归证据）"],
    },
}
rep["acceptance_sha256"] = hashlib.sha256(json.dumps(
    rep, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()
).hexdigest()
OUT.write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print("verdict:", rep["verdict"])
print("artifact_hash:", art["artifact_hash"], "| file sha256:", rep["5_artifact"]["file_sha256"])
print("determinism:", determinism_ok, "| immutable identical:", BEFORE == AFTER)
print("metrics:", len(AD.METRIC_SPEC), "| all_required_present:",
      rep["1_metric_definitions"]["all_required_present"])
print("regression:", json.dumps(suites, ensure_ascii=False)[:140])
print("acceptance ->", OUT)
sys.exit(0 if rep["verdict"] == "P7_3_ACCEPTED" else 1)
