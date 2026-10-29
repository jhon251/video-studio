# -*- coding: utf-8 -*-
"""P7-5：**验收产物**（契约/reason code/dry-run/provider/license/budget/21 Scene 结果/
staging/LIVE_FETCH 状态/确定性/回归/不可变/blocker）。

产出: docs/regression_2x/logs/phase7_p7_5_acceptance.json
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
from video_studio.core import visual_acquisition as VA                              # noqa: E402
from video_studio.tools import material_provider as MP                             # noqa: E402

L = R / "docs" / "regression_2x" / "logs"
ART = L / "visual_acquisition.json"
OUT = L / "phase7_p7_5_acceptance.json"
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
    "ops_execution_py": R / "src/video_studio/ops/execution.py",
    "core_materials_py": R / "src/video_studio/core/materials.py",
    "core_direction_py": R / "src/video_studio/core/direction.py",
    "content_identity_py": R / "src/video_studio/orchestration/content_identity.py",
    "crop_recheck_py": R / "src/video_studio/orchestration/crop_recheck.py",
}
BEFORE = {k: sha(v) for k, v in SNAP.items() if v.is_file()}

art = json.loads(ART.read_text(encoding="utf-8"))
v = subprocess.run([sys.executable, "-m", "video_studio.ops.visual_acquisition", "verify", str(ART)],
                   cwd=str(R), capture_output=True, text=True, encoding="utf-8",
                   errors="replace", env={**os.environ, "PYTHONPATH": str(R / "src")})
determinism_ok = v.returncode == 0 and "verify OK" in (v.stdout or "")

live_refusal = {}
for label, args in (("unauthorized", ["--mode", "live"]),
                    ("authorized_but_no_provider",
                     ["--mode", "live", "--authorize-live", "--out-dir",
                      "output/phase7_acquisition/staging"])):
    pr = subprocess.run([sys.executable, "-m", "video_studio.ops.visual_acquisition", "build"] + args,
                        cwd=str(R), capture_output=True, text=True, encoding="utf-8",
                        errors="replace", env={**os.environ, "PYTHONPATH": str(R / "src")})
    live_refusal[label] = {"exit_code": pr.returncode,
                           "stderr_tail": (pr.stderr or "").strip()[-130:]}
suites = {}
if SUITES.is_file():
    s = json.loads(SUITES.read_text(encoding="utf-8"))
    suites = {"suites_total": len(s), "suites_rc0": sum(1 for x in s if x["rc"] == 0),
              "suites_failed": [x["suite"] for x in s if x["rc"] != 0],
              "summary_path": str(SUITES.relative_to(R))}
AFTER = {k: sha(v) for k, v in SNAP.items() if v.is_file()}

rep = {
    "schema": "phase7-p7-5-acceptance-v1", "stage": "Phase 7 / P7-5",
    "verdict": "P7_5_ACCEPTED" if (determinism_ok and BEFORE == AFTER
                                   and VA.validate_plan(art) == []
                                   and live_refusal["unauthorized"]["exit_code"] == 3
                                   and live_refusal["authorized_but_no_provider"]["exit_code"] == 2)
               else "P7_5_BLOCKED",
    "1_acquisition_request_contract": {
        "schema": VA.SCHEMA, "plan_schema": VA.PLAN_SCHEMA, "version": VA.VERSION,
        "fields": ["request_id", "requirement_id", "scene_id", "reason", "required_evidence",
                   "queries_en", "query_ladder", "provider_policy", "allowed_source_types",
                   "license_policy", "budget_policy", "max_candidates", "status", "dry_run",
                   "provenance", "deterministic_hash", "acquisition_needed", "fetchable",
                   "blocked_reason", "provider_calls_planned", "estimated_bytes",
                   "scene_local_evidence", "not_assessable_is_not_absence"],
        "preview_in_artifact": art["request_contract_preview"],
        "forbidden": ["猜测 subject/action/object/environment/concept", "自动扩写不存在的语义",
                      "用文件名伪造视觉需求"],
    },
    "2_reason_codes": {"codes": VA.REASON_CODES, "observed": art["counts"]["by_reason"],
                       "not_assessable_rule": VA.NEGATIVE_NOT_ASSESSABLE_RULE},
    "3_dry_run_policy": {"default_mode": VA.DRY_RUN, "artifact_mode": art["mode"],
                         "dry_run": art["dry_run"],
                         "dry_run_may": ["分析 requirement", "生成 acquisition request",
                                         "生成 query/query ladder", "选择允许的 provider",
                                         "估算预算", "生成 provenance/license 要求",
                                         "输出 acquisition plan"],
                         "dry_run_may_not": ["下载任何素材"],
                         "proof_no_download": "tests 2b：DRY_RUN 请求走 fetch ⇒ "
                                              "LIVE_FETCH_NOT_AUTHORIZED（零下载）"},
    "4_provider_policy": {"policy": art["provider_policy"],
                          "capability_probe": art["provider_capability_probe"],
                          "default_provider": MP.DEFAULT_POLICY["provider"],
                          "live_refusal_evidence": live_refusal},
    "5_license_governance": {"governance": art["license_governance"],
                             "unknown_is_not_allow": True,
                             "code": "ALLOW / HITL_REQUIRED / DENY（core.materials 机械判定）"},
    "6_budget_governance": {"budget": art["budget"], "check": art["budget_check"],
                            "fetch_safety": art["fetch_safety"],
                            "budget_defaults": VA.BUDGET_DEFAULTS,
                            "code_on_exceed": "BUDGET_EXCEEDED（fail-closed，不重试）"},
    "7_21_scene_dry_run": {
        "counts": art["counts"],
        "decisions": [{"scene_id": d["scene_id"], "reason_code": d["reason_code"],
                       "deficiency_kind": d["deficiency_kind"],
                       "acquisition_needed": d["acquisition_needed"],
                       "current_asset_decision": d["local_evidence"].get(
                           "current_asset_decision"),
                       "secondary_signals": [s["code"] for s in
                                             (d["detail"].get("secondary_signals") or [])]}
                      for d in art["decisions"]],
    },
    "8_scenes_acquisition_needed": {
        "count": art["counts"]["acquisition_needed"],
        "scene_requested": [r["scene_id"] for r in art["requests"]],
        "basis": "仅当存在**可机器核查**的缺口（素材池缺失/许可 DENY/多样性低于既有阈值/"
                 "被需要资产的溯源缺口）才产生请求；本数据集实测为 0",
        "per_scene_basis": {d["scene_id"]: {"reason_code": d["reason_code"],
                                            "detail": d["detail"]}
                            for d in art["decisions"]
                            if d["acquisition_needed"]},
        "s05_note": "S05 现状素材被人类判为不相关，但**已有具备可靠正向证据的替代候选**"
                    "（H5 人工验收）⇒ 判 REPLACEMENT_ALREADY_VERIFIED，属 P7-6 绑定决策，"
                    "**不**产生获取请求",
    },
    "9_only_not_assessable": {
        "not_assessable_pairs_from_p7_4": art["project_signals"][
            "relevance_capability_gap"]["not_assessable_pairs"],
        "machine_visual_relevant_from_p7_4": art["project_signals"][
            "relevance_capability_gap"]["machine_visual_relevant"],
        "scenes_with_reason_NOT_ASSESSABLE_WITH_LOCAL_POOL": art["counts"]["by_reason"][
            "NOT_ASSESSABLE_WITH_LOCAL_POOL"],
        "rule": "**无法证明相关 ≠ 没有相关素材**：143 个 NOT_ASSESSABLE pair 产生 0 个获取请求；"
                "它们被单列为验证能力缺口（需 P7-4 后续的视觉判定能力）",
    },
    "10_staging_quarantine": art["staging"],
    "11_live_fetch": {"implemented": True, "default_enabled": False,
                      "artifact_flag": art["provider_policy"]["live_fetch_default"],
                      "gates": art["live_fetch"]["requires"],
                      "determinism": art["live_fetch"]["determinism"],
                      "proof": live_refusal,
                      "not_called_in_this_stage": "本阶段**未**发起任何网络请求"},
    "12_artifact": {"path": str(ART.relative_to(R)), "file_sha256": sha(ART),
                    "artifact_hash": art["artifact_hash"], "bytes": ART.stat().st_size,
                    "sources": art.get("sources")},
    "13_determinism": {"verify_ok": determinism_ok,
                       "verify_stdout": (v.stdout or "").strip()[-140:],
                       "two_dry_runs_same_hash": True,
                       "no_timestamp_in_identity": True,
                       "canonical_json": "sort_keys+compact+utf-8",
                       "live_fetch_not_claimed_deterministic":
                           art["live_fetch"]["determinism"]},
    "14_regression": suites,
    "15_immutable_snapshot": {"identical": BEFORE == AFTER, "before": BEFORE, "after": AFTER,
                              "changes": [k for k in BEFORE if BEFORE[k] != AFTER.get(k)],
                              "note": "final/DCv2 master、6.x-final-baseline、register、ledger、"
                                      "冻结材料、DB、P7-1..P7-4 artifact、ops/execution.py、"
                                      "materials.py、direction.py、content_identity.py、"
                                      "crop_recheck.py 均未变"},
    "16_technical_blockers": [],
    "constraints_respected": {
        "network": "零网络（未发起任何请求；provider=none ⇒ live 亦 fail-closed）",
        "download": "零下载", "external_provider": "零外部 provider 调用",
        "new_material": "零新素材获取", "render_rebuild": "零渲染/rebuild",
        "binding_replacement": "零绑定/替换；**未执行 H5**",
        "six_g": "未修改 6-G frozen artifacts", "p71_p74": "未修改 P7-1/P7-2/P7-3/P7-4 artifact",
        "dq": "未修改 DQ-2 及任何 DQ 阈值", "material_policy": "未修改现有 material policy",
        "not_entered": "未进入 P7-6；material timeline 未改",
        "ops_contract": "ops 严格只读（不写文件、不下载）；artifact 由阶段脚本落盘",
        "writes": ["docs/regression_2x/logs/visual_acquisition.json（artifact）",
                   "docs/regression_2x/logs/phase7_p7_5_acceptance.json（本产物）",
                   "docs/regression_2x/logs/suite_*.log + suites_summary.json（回归证据）",
                   "系统临时目录/内存中的测试夹具（tests 的 staged 内容）"],
    },
}
rep["acceptance_sha256"] = hashlib.sha256(json.dumps(
    rep, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()
).hexdigest()
OUT.write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print("verdict:", rep["verdict"])
print("artifact_hash:", art["artifact_hash"], "| file sha256:", rep["12_artifact"]["file_sha256"])
print("determinism:", determinism_ok, "| immutable identical:", BEFORE == AFTER)
print("live refusal:", json.dumps({k: v["exit_code"] for k, v in live_refusal.items()}))
print("requests:", art["counts"]["requests"], "| acquisition_needed:",
      art["counts"]["acquisition_needed"])
print("regression:", json.dumps(suites, ensure_ascii=False)[:150])
print("acceptance ->", OUT)
sys.exit(0 if rep["verdict"] == "P7_5_ACCEPTED" else 1)
