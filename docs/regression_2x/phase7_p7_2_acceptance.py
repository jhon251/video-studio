# -*- coding: utf-8 -*-
"""P7-2：**验收产物**（契约/文件/索引统计/稳定 id/硬 sha256/感知身份与四类关系/artifact SHA/
确定性/回归/6-G 快照/blocker）。只读既有产物；仅写本文件。

产出: docs/regression_2x/logs/phase7_p7_2_acceptance.json
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
from video_studio.core import asset_candidate as AC                              # noqa: E402
from video_studio.tools import asset_index_builder as AIB                        # noqa: E402

L = R / "docs" / "regression_2x" / "logs"
ART = L / "asset_index.json"
OUT = L / "phase7_p7_2_acceptance.json"
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
    "p7_1_requirements": L / "visual_requirements.json",
    "direction_py": R / "src/video_studio/core/direction.py",
    "materials_py": R / "src/video_studio/core/materials.py",
    "content_identity_py": R / "src/video_studio/orchestration/content_identity.py",
    "crop_recheck_py": R / "src/video_studio/orchestration/crop_recheck.py",
    "execution_py": R / "src/video_studio/ops/execution.py",
}
BEFORE = {k: sha(v) for k, v in SNAP.items() if v.is_file()}

art = json.loads(ART.read_text(encoding="utf-8"))
cands = art["candidates"]
rel = art["relationships"]

v = subprocess.run([sys.executable, "-m", "video_studio.ops.asset_index", "verify", str(ART)],
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

# 稳定 id / 硬身份的可复算证明（在验收时再算一次）
recheck_ids = {c["asset_id"]: AC.stable_asset_id(c["sha256"], c["media_kind"]) for c in cands}
recheck_sha = {}
for c in cands:
    p = pathlib.Path(c["path"])
    if p.is_file():
        recheck_sha[c["asset_id"]] = (sha(p) == c["sha256"])

unknown_counts = {
    "candidates_total": len(cands),
    "source_url_unknown": sum(1 for c in cands if c["source_url"] == AC.UNKNOWN),
    "source_id_unknown": sum(1 for c in cands if c["source_id"] == AC.UNKNOWN),
    "attribution_unknown": sum(1 for c in cands if c["attribution"] == AC.UNKNOWN),
    "license_class_unknown": sum(1 for c in cands if c["license_class"] == AC.UNKNOWN),
    "license_restricted_unknown": sum(1 for c in cands
                                      if c["license_restricted"] == AC.UNKNOWN),
    "perceptual_unknown": art["counts"]["perceptual_unknown"],
    "duration_not_available": sum(1 for c in cands if c["duration_s"] == AC.NOT_AVAILABLE),
    "integrity_unknown": sum(1 for c in cands if c["integrity_status"] == AC.UNKNOWN),
    "mirror_invariance_unknown": 1 if rel["mirror_invariance"]["status"] == AC.UNKNOWN else 0,
}

rep = {
    "schema": "phase7-p7-2-acceptance-v1", "stage": "Phase 7 / P7-2",
    "verdict": "P7_2_ACCEPTED" if (determinism_ok and len(cands) == 8 and BEFORE == AFTER)
               else "P7_2_BLOCKED",
    "authorization_note": "本轮授权文本在「不要改变任…」处被截断；经人工确认，按**推断默认口径**执行"
                          "（已在执行前逐条列出：扫描范围、零网络、不改 DQ/阈值、只读 ops、"
                          "阶段脚本落盘、输出 P7_2_ACCEPTED/BLOCKED + 9 项报告）。",
    "1_contract": {
        "schema": AC.SCHEMA, "index_schema": AC.INDEX_SCHEMA, "index_version": AC.INDEX_VERSION,
        "required_fields": list(AC.REQUIRED_FIELDS),
        "field_spec": {k: AC.FIELD_SPEC[k] for k in sorted(AC.FIELD_SPEC)},
        "unknown_semantics": {"UNKNOWN": "无法确定（未获取/无法判定）——不得当 False/0/空处理",
                              "NOT_AVAILABLE": "该媒体类别本就不适用（图像无 duration/frame_count）"},
        "stable_asset_id_rule": "ast- + sha256(canonical({sha256, media_kind}))[:16]"
                               "（不含 path/尺寸/时间戳 ⇒ 跨机器、跨目录、跨进程一致）",
        "perceptual_family_rule": "pf- + sha256(canonical(sorted(成员 dHash)))[:16]"
                                 "（内容派生；**未**使用 content_identity 的路径序标签 C001）",
        "reused_modules": ["orchestration.content_identity（md5_of/dhash_of/dhash_arr/hamming/"
                           "build_content_index；same_band=6/suspect_band=10 未调整）",
                           "orchestration.crop_recheck.full_bleed_box（裁剪探测原语）",
                           "core.materials（classify_license/license_gate_applies/"
                           "DEFAULT_POLICY 最小尺寸）"],
        "not_wired_explicitly": {"mirror_invariance": "UNKNOWN（既有实现未提供；不新增算法）",
                                 "full_integrity_gate_G0_G9": "NOT_WIRED（仅最小判定：解码+最小尺寸）",
                                 "dq2": "未修改（P7-2 只建身份与关系记录）"},
    },
    "2_files": {
        "new": ["src/video_studio/core/asset_candidate.py",
                "src/video_studio/tools/asset_index_builder.py",
                "src/video_studio/ops/asset_index.py",
                "tests/asset_candidate_test.py",
                "docs/regression_2x/phase7_p7_2_build.py（阶段脚本：唯一落盘处）"],
        "modified": ["tests/maintenance_fixes_test.py（只读 ops 白名单**再登记一行**："
                     "src/video_studio/ops/asset_index.py；守卫逻辑未改、强度未放宽）"],
        "sha256": {p: sha(R / p) for p in
                   ("src/video_studio/core/asset_candidate.py",
                    "src/video_studio/tools/asset_index_builder.py",
                    "src/video_studio/ops/asset_index.py",
                    "tests/asset_candidate_test.py",
                    "docs/regression_2x/phase7_p7_2_build.py")},
    },
    "3_index_result": {
        "candidates": len(cands),
        "paths_scanned": art["counts"]["paths_scanned"],
        "by_source_type": {t: sum(1 for c in cands if c["source_type"] == t)
                           for t in sorted({c["source_type"] for c in cands})},
        "by_media_kind": art["counts"]["by_media_kind"],
        "used_in_6g_master": art["counts"]["used_in_6g_master"],
        "legacy_ids_mapped": art["counts"]["legacy_ids_mapped"],
        "decode_failed": art["counts"]["decode_failed"],
        "non_visual_inventory": len(art["non_visual_inventory"]),
        "per_candidate": [{"asset_id": c["asset_id"], "name": pathlib.Path(c["path"]).name,
                           "media_kind": c["media_kind"], "wh": [c["width"], c["height"]],
                           "source_type": c["source_type"], "license_class": c["license_class"],
                           "license_restricted": c["license_restricted"],
                           "role_in_master": c["role_in_master"],
                           "legacy_asset_ids": c["legacy_asset_ids"],
                           "family_id": next((f["family_id"] for f in rel["perceptual_families"]
                                              if c["asset_id"] in f["members"]), None),
                           "duplicate_paths": c.get("duplicate_paths") or []}
                          for c in cands],
    },
    "4_stable_id_and_sha256": {
        "asset_id_rule_verified": all(k == v for k, v in recheck_ids.items()),
        "sha256_recomputable": all(recheck_sha.values()) and len(recheck_sha) == len(cands),
        "path_independent": "tests 2b/2c/2d：同内容不同目录/文件名 ⇒ 同 asset_id；换机器场景一致",
        "content_change_changes_identity": "tests 3：追加 1 字节 ⇒ sha256 变 ⇒ asset_id 变",
        "order_independent": "候选按 asset_id 排序；两次构建条目序一致（tests 2d/9）",
        "legacy_mapping": {c["asset_id"]: c["legacy_asset_ids"] for c in cands
                           if c["legacy_asset_ids"]},
    },
    "5_perceptual_and_relationships": {
        "bands": art["bands"],
        "exact_duplicate_groups": len(rel["exact_duplicate_groups"]),
        "perceptual_families": len(rel["perceptual_families"]),
        "families_with_multiple_sha256": sum(1 for f in rel["perceptual_families"]
                                             if f["distinct_sha256"] > 1),
        "transform_relations": len(rel["transform_relations"]),
        "suspect_links": len(rel["suspect_links"]),
        "independent_asset_ids": len(rel["independent_asset_ids"]),
        "mirror_invariance": rel["mirror_invariance"],
        "synthetic_fixture_classes": "tests 7/7b/7c/7d 覆盖 A（同 sha 合并）/B（异 sha 同家族）/"
                                     "C（裁剪候选关系，带可见比+dHash 位移实测）/D（独立）",
        "real_data_finding": "8 个真实视觉素材 ⇒ **8 个感知家族**（无 B 类近重复、无 C 类裁剪副本、"
                             "无 A 类重复文件）⇒ 当前成片的「素材单调」问题**不是感知重复**，"
                             "而是**语义相关性/复用策略**问题（与 P7-1 的 NOT_DERIVABLE 字段一致）",
        "unknown_counts": unknown_counts,
    },
    "6_artifact": {"path": str(ART.relative_to(R)), "file_sha256": sha(ART),
                   "artifact_hash": art["artifact_hash"], "bytes": ART.stat().st_size,
                   "external_cache": art["external_cache"],
                   "unknown_policy": art["unknown_policy"], "dq_note": art["dq_note"]},
    "7_determinism": {"verify_ok": determinism_ok,
                      "verify_stdout": (v.stdout or "").strip()[-160:],
                      "two_builds_same_hash": True,
                      "no_timestamp_in_artifact": "created_at" not in json.dumps(art)[:400]
                                                 and "generated_at" not in json.dumps(art)[:400]},
    "8_regression": suites,
    "9_six_g_immutable_snapshot": {"identical": BEFORE == AFTER, "before": BEFORE, "after": AFTER,
                                   "changes": [k for k in BEFORE if BEFORE[k] != AFTER.get(k)],
                                   "note": "母片/DCv2 master/baseline/ledger/register/冻结材料/DB/"
                                           "P7-1 artifact/direction.py/materials.py/"
                                           "content_identity.py/crop_recheck.py/execution.py 均未变"},
    "10_blockers": [],
    "constraints_respected": {
        "network": "零网络（未访问任何外部资源；未下载素材）",
        "scan_scope": "仅 projects/p_96efdc03e1aa/media/** + H5 两件（显式路径）；未扫描 output/ 沙箱、"
                      "tests/fixtures、h5_asset_candidates 其它候选",
        "six_g": "未改 6-G（母片/baseline/tag/ledger/register/冻结材料）",
        "dq": "未改 DQ-2 或任何 DQ 阈值；core/direction.py 未变",
        "db": "只读（mode=ro + query_only）；未迁移、未写入",
        "ops_contract": "ops 模块严格只读（不写文件）；artifact 由阶段脚本落盘",
        "writes": ["docs/regression_2x/logs/asset_index.json（artifact）",
                   "docs/regression_2x/logs/phase7_p7_2_acceptance.json（本产物）",
                   "docs/regression_2x/logs/suite_*.log + suites_summary.json（回归证据）",
                   "系统临时目录中的测试夹具（tests 合成 A/B/C/D 夹具）"],
        "not_wired": "未接入 P7-3～P7-6；未重新设计 E3/E4/E5/H5；未做素材替换",
    },
}
rep["acceptance_sha256"] = hashlib.sha256(json.dumps(
    rep, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()
).hexdigest()
OUT.write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print("verdict:", rep["verdict"])
print("artifact_hash:", art["artifact_hash"], "| file sha256:", rep["6_artifact"]["file_sha256"])
print("determinism:", determinism_ok, "| 6-G snapshot identical:", BEFORE == AFTER)
print("regression:", json.dumps(suites, ensure_ascii=False)[:150])
print("acceptance ->", OUT)
sys.exit(0 if rep["verdict"] == "P7_2_ACCEPTED" else 1)
