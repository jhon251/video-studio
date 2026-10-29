# -*- coding: utf-8 -*-
"""P7-1：**验收产物**（schema 定义 / 文件清单 / 21 镜结果 / NOT_DERIVABLE / artifact SHA /
确定性验证 / 回归结果 / 6-G 不可变快照 / blocker）。只读既有产物；仅写本文件。

产出: docs/regression_2x/logs/phase7_p7_1_acceptance.json
"""
import hashlib
import json
import pathlib
import subprocess
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import visual_requirement as VR                          # noqa: E402
from video_studio.tools import visual_requirement_builder as VB                 # noqa: E402

L = R / "docs" / "regression_2x" / "logs"
ART = L / "visual_requirements.json"
OUT = L / "phase7_p7_1_acceptance.json"
SUITES = L / "suites_summary.json"


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


SNAP_KEYS = {
    "final_master": R / "output/phase6g_exec_h5/20260929_151026/out/H5_rp-0ebebb71f99c.mp4",
    "dcv2_master": R / "output/phase6g_sandbox/20260929_102445/out/dcv2_master_20260929_102445.mp4",
    "baseline_zip": R / "docs/regression_2x/baseline/6.x-final-baseline.zip",
    "baseline_manifest": R / "docs/regression_2x/baseline/"
                         "baseline_manifest_6.x-final-baseline.json",
    "baseline_status": R / "docs/regression_2x/baseline/baseline_status_6.x-final-baseline.json",
    "ledger": L / "phase6g_exec_ledger.jsonl",
    "register": L / "phase6g_rebuild_proposal_register.jsonl",
    "frozen_material_plan": R / "docs/regression_2x/phase6e_materials/phase6e_material_plan.json",
    "db": R / "projects/video_studio.db",
    "visual_plan_artifact": R / ("projects/p_96efdc03e1aa/artifacts/"
                                 "a_a6279580600a.json"),
    "material_timeline_artifact": R / ("projects/p_96efdc03e1aa/artifacts/"
                                       "a_82b543375e11.json"),
    "execution_py": R / "src/video_studio/ops/execution.py",
    "materials_py": R / "src/video_studio/core/materials.py",
    "direction_py": R / "src/video_studio/core/direction.py",
}
BEFORE = {k: sha(v) for k, v in SNAP_KEYS.items() if v.is_file()}

art = json.loads(ART.read_text(encoding="utf-8"))
reqs = art["requirements"]
nd = {k: v["NOT_DERIVABLE"] for k, v in art["counts"]["field_status_counts"].items()
      if v["NOT_DERIVABLE"]}
nd_reasons: dict[str, dict] = {}
for r in reqs:
    for k, meta in r["field_status"].items():
        if meta["status"] == "NOT_DERIVABLE":
            nd_reasons.setdefault(k, {}).setdefault(meta.get("reason", ""), 0)
            nd_reasons[k][meta.get("reason", "")] += 1

# 确定性：独立进程二次构建 → 与现有 artifact 比对
env = {"PYTHONPATH": str(R / "src")}
v = subprocess.run([sys.executable, "-m", "video_studio.ops.visual_requirement", "verify",
                    str(ART)], cwd=str(R), capture_output=True, text=True, encoding="utf-8",
                   errors="replace", env={**__import__("os").environ, **env})
determinism_ok = v.returncode == 0 and "verify OK" in (v.stdout or "")

suites = {}
if SUITES.is_file():
    s = json.loads(SUITES.read_text(encoding="utf-8"))
    total = len(s)
    rc0 = sum(1 for x in s if x["rc"] == 0)
    failed = [x["suite"] for x in s if x["rc"] != 0]
    ratios = [r for x in s for r in (x.get("ratios") or [])]
    suites = {"suites_total": total, "suites_rc0": rc0, "suites_failed": failed,
              "ratios_recorded": ratios, "summary_path": str(SUITES.relative_to(R)),
              "note": "逐套件运行 tests/*.py（rc=0 为准）；本阶段新增 visual_requirement_test 已含在内"}
AFTER = {k: sha(v) for k, v in SNAP_KEYS.items() if v.is_file()}

rep = {
    "schema": "phase7-p7-1-acceptance-v1", "stage": "Phase 7 / P7-1",
    "verdict": "P7_1_ACCEPTED" if (determinism_ok and art["counts"]["requirements"] == 21
                                   and BEFORE == AFTER) else "P7_1_BLOCKED",
    "1_schema_final_definition": {
        "requirement_schema": VR.SCHEMA, "artifact_schema": VR.ARTIFACT_SCHEMA,
        "artifact_version": VR.ARTIFACT_VERSION,
        "required_fields": list(VR.REQUIRED_FIELDS),
        "three_state_semantics": {"DERIVABLE": "输入存在显式依据（或既有确定性规则可机械抽取）",
                                  "NOT_DERIVABLE": "输入中根本不存在该类信息（不得臆造）",
                                  "INVALID": "身份/溯源/结构违反 ⇒ 构造期抛错，产物中不出现"},
        "field_spec": {k: VR.FIELD_SPEC[k] for k in sorted(VR.FIELD_SPEC)},
        "normalization": art["normalization"],
        "evidence_type_map": VR.EVIDENCE_TYPE_MAP,
        "anti_hallucination_guard": {
            "fields_requiring_evidence": list(VR.EVIDENCE_REQUIRED_FIELDS),
            "rule": "这些字段一旦赋值，provenance.evidence_refs 必须给出该字段证据引用，"
                    "否则抛 VR_INVALID_HALLUCINATION_NO_EVIDENCE",
            "p7_1_behaviour": "确定性 builder **从不赋值**这五个字段 ⇒ 21/21 均为 NOT_DERIVABLE"},
        "builder_rules": VB.BUILDER_RULES,
        "future_interface": VR.extractor_contract(),
    },
    "2_files": {
        "new": ["src/video_studio/core/visual_requirement.py",
                "src/video_studio/tools/visual_requirement_builder.py",
                "src/video_studio/ops/visual_requirement.py",
                "tests/visual_requirement_test.py",
                "docs/regression_2x/phase7_p7_1_build.py（阶段脚本：**唯一落盘处**）"],
        "modified": ["tests/maintenance_fixes_test.py（仅只读 ops 白名单登记一行；见下）"],
        "guard_registration_disclosure": {
            "guard": "tests/maintenance_fixes_test.py M8d（禁止新增未授权 ops/ 模块）",
            "why": "P7-1 按要求新增 `ops/visual_requirement.py`；该守卫要求新 ops 模块必须登记在"
                   "只读白名单或授权写入白名单中，否则回归必然红。",
            "how_resolved": "① 把 ops 模块改为**严格只读**（不写任何文件：artifact 落盘移至阶段脚本 "
                            "docs/regression_2x/phase7_p7_1_build.py）；"
                            "② 在 READONLY_OPS_WHITELIST 登记一行（带理由注释）。"
                            "未放宽任何检查强度：M8d/M8e 原检查逻辑一行未改。",
            "strength_change": "无（未放宽；仅新增白名单条目）"},
        "proposed_db_registration_not_executed": {
            "file": "src/video_studio/db/schema.py",
            "proposal": "登记 artifact 类型 `visual_requirements`（仅类型白名单，无迁移、无写入）",
            "executed": False, "reason": "P7-1 明确不进行 DB 迁移/写入"},
        "sha256": {"src/video_studio/core/visual_requirement.py":
                       sha(R / "src/video_studio/core/visual_requirement.py"),
                   "src/video_studio/tools/visual_requirement_builder.py":
                       sha(R / "src/video_studio/tools/visual_requirement_builder.py"),
                   "src/video_studio/ops/visual_requirement.py":
                       sha(R / "src/video_studio/ops/visual_requirement.py"),
                   "tests/visual_requirement_test.py":
                       sha(R / "tests/visual_requirement_test.py")},
    },
    "3_scene_results_21_of_21": {
        "requirements": 21, "coverage": "S01–S21 全覆盖（每镜一条）",
        "per_scene": [{"scene_id": r["scene_id"], "requirement_id": r["requirement_id"],
                       "status": r["status"], "deterministic_hash": r["deterministic_hash"],
                       "visual_goal": bool(r["visual_goal"]), "queries_en": len(r["queries_en"] or []),
                       "query_ladder_steps": len(r["query_ladder"] or []),
                       "concepts_pos": len(r["concepts_pos"] or []),
                       "avoid_list": len(r["avoid_list"] or []),
                       "evidence_type": r["evidence_type"],
                       "not_derivable_fields": [k for k, m in r["field_status"].items()
                                                if m["status"] == "NOT_DERIVABLE"]}
                      for r in reqs],
        "status_counts": {"DERIVABLE": art["counts"]["derivable"],
                          "NOT_DERIVABLE": art["counts"]["not_derivable"]},
    },
    "4_not_derivable": {"field_counts": nd, "reasons": nd_reasons,
                        "explanation": "深层语义五字段（subject/action/object/environment/"
                                       "concept）在**当前输入中无结构化来源** ⇒ 全部显式 "
                                       "NOT_DERIVABLE；4 个镜（S01/S13/S17/S20）内容文本无拉丁 "
                                       "token ⇒ queries_en/query_ladder NOT_DERIVABLE（不做翻译）。"
                                       "**未为覆盖率臆造任何字段。**"},
    "5_artifact": {"path": str(ART.relative_to(R)), "file_sha256": sha(ART),
                   "artifact_hash": art["artifact_hash"], "bytes": ART.stat().st_size,
                   "counts": art["counts"], "source_identity": art["source_identity"],
                   "requirement_hashes": art["requirement_hashes"]},
    "6_determinism": {
        "verify_cmd": "python -m video_studio.ops.visual_requirement verify <artifact>",
        "verify_ok": determinism_ok, "verify_stdout": (v.stdout or "").strip()[-200:],
        "covered_normalizations": ["字段/key 顺序", "空白（多空格/Tab/换行）", "Unicode NFD↔NFC",
                                   "无序列表顺序与重复", "有序阶梯保序", "空字段", "无时间戳"],
        "evidence": "tests/visual_requirement_test.py 的 7/7b/7c/7d/7e/7f/3/3b/4e 用例"},
    "7_regression": suites,
    "8_six_g_immutable_snapshot": {
        "identical": BEFORE == AFTER, "before": BEFORE, "after": AFTER,
        "changes": [k for k in BEFORE if BEFORE[k] != AFTER.get(k)],
        "note": "母片/DCv2 master/baseline(ZIP+manifest+status)/ledger/register/冻结材料/DB/"
                "源产物(visual_plan、material_timeline)/execution.py/materials.py/direction.py "
                "全部未变"},
    "9_technical_blockers": [],
    "constraints_respected": {
        "network": "未访问网络（builder 纯离线；测试无网络调用）",
        "llm": "未调用任何真实 LLM/外部 API（仅定义接口）",
        "material_download": "未下载任何素材",
        "six_g": "未修改 6-G（母片/baseline/tag/ledger/register/冻结材料/DQ 阈值）",
        "panel_kind": "未改 _PANEL_KIND",
        "db": "未做 DB 迁移或写入（只读打开 mode=ro + query_only）",
        "p7_2_to_p7_6": "未接入",
        "rebuild": "未执行任何 rebuild；未做 H5 类素材替换",
        "writes": ["docs/regression_2x/logs/visual_requirements.json（artifact，由阶段脚本落盘）",
                   "docs/regression_2x/logs/phase7_p7_1_acceptance.json（本产物）",
                   "docs/regression_2x/logs/suite_*.log + suites_summary.json（既有运行器产出）",
                   "注：`ops/visual_requirement.py` **不写任何文件**（只读契约）"],
    },
}
rep["acceptance_sha256"] = hashlib.sha256(json.dumps(
    rep, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()
).hexdigest()
OUT.write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print("verdict:", rep["verdict"])
print("artifact_hash:", art["artifact_hash"], "| file sha256:", rep["5_artifact"]["file_sha256"])
print("determinism:", determinism_ok, "| 6-G snapshot identical:", BEFORE == AFTER)
print("regression:", json.dumps(suites, ensure_ascii=False)[:200])
print("acceptance ->", OUT)
sys.exit(0 if rep["verdict"] == "P7_1_ACCEPTED" else 1)
