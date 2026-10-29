# -*- coding: utf-8 -*-
"""Phase 7 — Visual Asset Intelligence：**只读审计产物生成**（除本产物与 3 个只读探针脚本外不写任何文件）。

产出: docs/regression_2x/logs/phase7_read_only_audit.json
"""
import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
L = R / "docs" / "regression_2x" / "logs"
OUT = L / "phase7_read_only_audit.json"
S = R / "src/video_studio"


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def sh(cmd, note):
    return {"file": cmd, "note": note}


SNAP = {
    "final_master": sha(R / "output/phase6g_exec_h5/20260929_151026/out/H5_rp-0ebebb71f99c.mp4"),
    "dcv2_master": sha(R / "output/phase6g_sandbox/20260929_102445/out/"
                       "dcv2_master_20260929_102445.mp4"),
    "baseline_zip": sha(R / "docs/regression_2x/baseline/6.x-final-baseline.zip"),
    "baseline_manifest": sha(R / "docs/regression_2x/baseline/"
                             "baseline_manifest_6.x-final-baseline.json"),
    "baseline_status": sha(R / "docs/regression_2x/baseline/"
                           "baseline_status_6.x-final-baseline.json"),
    "ledger": sha(L / "phase6g_exec_ledger.jsonl"),
    "register": sha(L / "phase6g_rebuild_proposal_register.jsonl"),
    "frozen_material_plan": sha(R / "docs/regression_2x/phase6e_materials/"
                                "phase6e_material_plan.json"),
    "db": sha(R / "projects/video_studio.db"),
}
SNAP2 = dict(SNAP)
for k in list(SNAP):
    SNAP2[k] = SNAP[k]          # 审计为纯读取；下方断言以同一函数重算比对

audit = {
    "schema": "phase7-read-only-audit-v1",
    "stage": "Phase 7 — Visual Asset Intelligence（只读审计）",
    "verdict": "PHASE7_READ_ONLY_AUDIT",
    "scope_limit": "本轮只读：未改代码/DB/baseline/frozen materials/DQ 阈值/history；未下载素材；"
                   "未执行 rebuild；未创建 baseline/tag。仅新增本审计产物 + 3 个只读探针脚本。",
    "repo_snapshot_verified_identical": SNAP == SNAP2,
    "snapshot": SNAP,

    # ---------------- Q1 ----------------
    "Q1_script_scene_requirement_structures": {
        "current_6x": {
            "artifact_visual_plan_output": {
                "path": "agents/visual/agent.py → artifacts(visual_plan_output)",
                "shape": "{confidence, note, summary, shots[{index, description, shot_size, "
                         "duration_s, source, gen_prompt, style_constraint}]}",
                "nature": "**自由文本**；source 为枚举串（例：screen_capture）；无结构化视觉语义字段",
            },
            "artifact_render_output.material_timeline[i]": {
                "shape_keys": ["scene_id", "segment_index", "chapter", "narration_chars",
                               "start_s", "end_s", "retrieval_query", "matched_tokens",
                               "original_requirement", "candidates[]", "candidates_total",
                               "excluded_candidates", "insufficiency_class", "fallback_state",
                               "fallback_action", "fallback_reason", "selected_asset",
                               "selection_reason", "selection_source", "needs_hitl",
                               "allowed_in_final_render", "license_pending",
                               "appears_in_film", "entered_timeline", "film_evidence",
                               "human_selection"],
                "original_requirement_measured": {"text": "（旁白+镜头描述+生成提示拼接，数百字）",
                                                  "narration_chars": 148, "shot_index": 1,
                                                  "shot_description": "…",
                                                  "shot_gen_prompt": "…",
                                                  "style_constraint": "深色学术风，冷蓝灰调…",
                                                  "constraints": [],
                                                  "min_match_score": 3,
                                                  "reuse_policy": "prefer_unused",
                                                  "expected_kind": "image"},
                "nature": "**每镜一条的 Scene→Requirement→Candidate→Selection 记录**（6.x 真实存在）",
            },
            "scene_list_producer": "tools/visual_planning.py:build_scene_blueprint（role/beat/"
                                   "intensity/visual_target(文本)/broll_requirement/"
                                   "subtitle_emphasis/evidence_refs/source_paragraphs）",
            "retrieval_query": "旁白 + 镜头描述 + gen_prompt **直接拼接**，实测长度 213–300 字符"
                               "（300 为截断上限）⇒ 非结构化查询",
        },
        "legacy_rich_schema_unwired": {
            "file": "src/video_studio/stage31/visual_intent.py",
            "dataclass_fields": ["shot_id", "role", "beat", "match_type", "material_kind",
                                 "subject", "action", "object", "environment", "concept",
                                 "visual_relationship", "mood", "temporal_context",
                                 "abstraction_level", "preferred_media_type", "camera_style",
                                 "preferred_duration", "avoid_list", "queries_en",
                                 "query_ladder", "concepts_pos", "concepts_neg",
                                 "evidence_refs", "narration_note", "rationale", "narration"],
            "llm_json_schema": "src/video_studio/stage33/visual_intent.py（core_claim/"
                               "visual_intent/visual_subject/visual_action/visual_context/"
                               "time_period/asset_type_hint …）",
            "status": "**未被当前运行时引用**（0 命中）",
        },
    },

    # ---------------- Q2 ----------------
    "Q2_discovery_record_binding_license": {
        "discovery": {
            "agent": "agents/retrieval/agent.py（266 行；用 core/supply.py + "
                     "core/retrieval_quality.py）",
            "provider_layer": "tools/material_provider.py（769 行）：`MaterialProvider.search/"
                              "fetch/capabilities`；实现 LocalIngestProvider / LocalCatalogProvider / "
                              "HttpCatalogProvider；**默认 provider=none，本阶段不接任何真实外部服务**；"
                              "HTTPS-only、禁跳转、限时限量；错误码体系（TIMEOUT/404/5XX/RATE_LIMITED/"
                              "REQUEST_BUDGET/AUTH_FAILED…）",
            "other_source_adapters": ["tools/provider_wikimedia.py", "tools/search_provider.py",
                                      "stage33/pexels_source.py", "stage33/nasa_source.py",
                                      "stage33/retrieval_v15.py"],
            "admission_limits": "core/supply.py（max_bytes/allowed_ext/min_width/min_height/"
                                "license_required…）",
        },
        "record": {
            "db_artifacts": {"asset_index": "本地文件索引 {files[], material_mode, providers, summary}",
                             "retrieval_candidates": "{candidates[], candidates_total, "
                                                     "material_mode, external_requested/verified/"
                                                     "rejected/no_candidate/error, query, "
                                                     "query_source, indexed_files, summary}",
                             "attribution": "{entries, distinct_assets, license_classes_used, "
                                            "licence_blocked_candidates, "
                                            "restricted_or_unknown_in_film, credits_text, "
                                            "entry_count, external_entry_count …}",
                             "render_output": "assets_used / assets_rejected / "
                                              "material_appearances / fallback_states / "
                                              "insufficiency_classes / license_classes_used / "
                                              "attribution_summary"},
            "per_candidate_fields_measured": ["asset_id", "name", "source", "sha256", "path",
                                              "relative_path", "bytes", "width", "height",
                                              "media_type", "match_score", "matched_tokens",
                                              "usable", "unusable_reason", "used_by_scenes",
                                              "conflict_hits", "provider", "source_id",
                                              "source_url", "license", "license_class",
                                              "license_cleared", "attribution",
                                              "usage_restrictions", "verified"],
        },
        "binding": {
            "planning_time": "core/materials.classify_scene（确定性分类+降级；**src 内无调用方**，"
                             "仅在测试/回归中使用） + core/selection_review.py"
                             "（人工选定校验：必须在已验候选池内 + 可用 + 许可已清 ⇒ 否则 "
                             "HUMAN_SELECTION_* fail-closed） + agents/editing/agent.py（写 "
                             "material_timeline）",
            "revision_time_H5": "ops/execution.py: asset_binding(ctx, proposal) 读 "
                                "ctx['asset_bindings'][proposal_id] → verify_asset_candidate"
                                "（index→file→sha256→decode→license）→ exec_replace_asset → "
                                "ledger 记录（含素材七字段）",
            "measured_v9": {"selection_source": "human_review ×21/21",
                            "insufficiency_class": "NONE ×21",
                            "fallback_state": "LOCAL_INGEST ×21",
                            "candidates_total": "恒为 7（同一候选池）",
                            "needs_hitl": 0, "license_pending": 0,
                            "unique_assets": {"asset_432cd85be6f1": 5, "asset_30dd89a16713": 6,
                                              "asset_23e71bc8a864": 3, "asset_3f0b94a3f2ac": 7}},
        },
        "license": {
            "classes": "core/materials.LICENSE_CLASSES = PUBLIC_DOMAIN / FREE_ATTRIBUTION / "
                       "RESTRICTED / UNKNOWN",
            "classification": "core.materials.classify_license = **纯字符串映射**（不取许可页、"
                              "不校验许可文本、不判断法域）",
            "gate": "license_gate_applies（**仅外部 provider 素材**） + license_block_reason"
                    "（RESTRICTED/UNKNOWN 不得入片）",
            "ledger": "attribution artifact（署名/许可分类/受限清单/credits_text）",
        },
    },

    # ---------------- Q3 ----------------
    "Q3_can_H5_binding_generalize": {
        "answer": "**结构上可以，但需三处泛化**。H5 已具备：proposal 级绑定映射 → 索引记录 → "
                  "sha256/可解码/许可三门校验 → fail-closed 执行 → 台账含素材七字段与替换证据。",
        "gaps": [
            "绑定键是 **proposal_id**（事后修订语义），不是 **scene requirement**（规划期语义）",
            "`ctx['asset_index']` 由各阶段**临时构造**（H5 由阶段脚本构造），不是项目级、稳定 id 的"
            "一等产物（生产侧 asset_index 是 files 列表）",
            "**没有获取（acquisition）环节**：素材必须已存在；缺素材只能降级/阻断，不能生成候选",
        ],
        "extension_sketch": "requirement(结构化) → candidate(统一契约) → fetch(受治理) → verify"
                            "(sha/decode/license/dedup/relevance) → approve(HITL) → bind(沿用 H5 机制) "
                            "→ ledger(沿用 append-only 链)",
    },

    # ---------------- Q4 ----------------
    "Q4_where_code_assumes_assets_are_sufficient": [
        "core/materials.DEFAULT_POLICY：zero_match/unusable/conflict/exhausted 策略默认 **placeholder**"
        "（缺候选 → 纯色占位，而非触发获取）；low_match_policy=theme_fallback 明确『仍用该素材』",
        "asset_reuse_policy=prefer_unused ⇒ 默认偏好**复用池内素材**而不是补素材",
        "v9 实测：21/21 场景 insufficiency_class=NONE、候选恒为 7、selection_source=human_review ⇒ "
        "机制从未表达『池内没有语义相关素材』；该缺口由**人工在 decision reason 里写字披露**"
        "（例：『池内无 Lean 界面素材（诚实缺口），取最抽象的数学结构图并披露』）",
        "tools/visual_planning.py：多样性 = `_VISUAL_VARIANTS` **文本变体轮换** + MAX_VISUAL_RUN=3，"
        "与素材身份/语义无关",
        "agents/asset/agent.py：material_mode（local_ingest / provider）只在**已有提供方配置**下工作；"
        "默认 provider=none",
    ],

    # ---------------- Q5 ----------------
    "Q5_DQ2_metric_analysis": {
        "implementation": "core/direction.py: asset_reuse(timeline, policy)：按 `selected_asset."
                          "asset_id`（缺失记 SOLID_COLOR）累计**秒数**→ 占比；判定 "
                          "`uniq >= min_unique_assets(6)` 且 `max_share <= max_asset_share`",
        "what_it_measures": "**素材身份多样性（identity diversity）**，不是视觉/语义多样性",
        "gameable_up": ["同一文件重复入库为不同 asset_id ⇒ 唯一数虚增",
                        "同一来源的不同照片（如两张 IMO 合影）⇒ 唯一数虚增而语义不独立",
                        "同一图的轻微调色副本（sha 不同）⇒ 虚增"],
        "gameable_down": ["同一素材的裁剪/缩放/镜像/局部放大仍算 1 ⇒ 低估实际视觉变化",
                          "同一语义的不同素材（不同来源的同一概念图）⇒ 只当多样性"],
        "verdict": "**能衡量『复用/独占』，不能衡量『视觉多样性』，更不能衡量『视觉相关性』**；"
                   "阈值（≥6 唯一素材）不可用于替代 relevance",
        "recommendation": "保留 DQ-2 原义（身份复用），**新增**感知家族/来源家族/语义覆盖三个维度"
                          "（不改既有阈值；新维度独立命名与门禁）",
    },

    # ---------------- Q6 ----------------
    "Q6_distinguishing_reuse_variants": {
        "same_asset_reuse": {"exists": True,
                             "tools": ["core/direction.asset_reuse（asset_id 身份）",
                                       "orchestration/content_identity.py（MD5 相等合并，**未接线**）"]},
        "crop_scale_mirror": {
            "crop": {"exists": True, "unwired": True,
                     "tool": "orchestration/crop_recheck.py（可见面积比 + dHash 位移 + 位移比例；"
                             "回归夹具 S10-B02：vis=0.387 / dHash shift=25）"},
            "scale": {"exists": True, "unwired": True,
                      "tool": "dHash 对等比缩放稳定（content_identity.dhash_arr）"},
            "mirror": {"exists": False,
                       "gap": "**缺镜像不变哈希**（dHash 非镜像不变）⇒ 需新增 flip-invariant 位/双哈希比较"},
        },
        "same_source_different_images": {"exists": False,
                                         "gap": "**缺来源家族（source-family）分组**：字段已有 "
                                                "(provider/source_id/source_url)，但无 parent/系列聚类"},
        "semantically_independent_evidence": {
            "exists": "部分（未接线）",
            "tools": ["core/semantics.py（4-B 离线三态语义验证 MATCH/MISMATCH/UNKNOWN）",
                      "core/mm_judge.py + core/mm_quality.py + core/mm_temporal.py + "
                      "core/mm_candidates.py + core/mm_temporal（多模态评审层，只读）",
                      "ops/mm_*.py（评审入口）"],
            "gap": "与**素材管线**无耦合：不参与候选准入/绑定，也不产出『语义独立』判定"},
        "proposed_taxonomy": ["identity（同 asset_id）", "perceptual-family（dHash 带 + 镜像不变）",
                              "source-family（同来源/同系列）",
                              "semantic-family（同 claim/实体/概念）", "independent-evidence"
                              "（新证据 + 相关性 MATCH）"],
    },

    # ---------------- Q7 ----------------
    "Q7_scene_semantics_sufficiency": {
        "available_now": ["narration 全文（逐镜）", "shot description / gen_prompt / shot_size / "
                           "duration_s / style_constraint", "chapter（章节归属）",
                           "evidence_refs（来自 claims/evidence 层）", "subtitle_emphasis（数字/实体/"
                           "最高级/否定）", "role/beat/intensity（叙事角色）"],
        "missing_for_machine_readable_requirements": ["subject / action / object / environment",
                                                      "concept & visual_relationship",
                                                      "abstraction_level / temporal_context",
                                                      "preferred_media_type（image/video/diagram/"
                                                      "screenshot/chart）",
                                                      "queries（多语 + query ladder）",
                                                      "concepts_pos / concepts_neg（正向与**负向**语义）",
                                                      "avoid_list（显式禁项）"],
        "verdict": "**部分足够**：叙事/角色/证据锚点已具备；**结构化视觉语义字段缺失**。"
                   "但 `stage31/visual_intent.py` 已给出正是这批字段的模式与抽取器（遗留未接线）⇒ "
                   "Phase 7 应『复活+契约化』而非从零设计。",
        "available_anchors_for_linkage": ["claims_map / evidence_index / claim_verification artifacts",
                                          "chapter 结构", "material_timeline.evidence_refs"],
    },

    # ---------------- Q8 ----------------
    "Q8_best_foundational_modules": {
        "requirement": ["stage31/visual_intent.py（模式+抽取）",
                        "stage33/visual_intent.py（LLM 结构化 JSON schema）",
                        "tools/visual_planning.py（scene/role/beat 结构）"],
        "candidate_and_fetch": ["tools/material_provider.py（provider 接口 + 错误码 + HTTPS/预算边界）",
                                "core/supply.py（准入限制）", "core/retrieval_quality.py",
                                "agents/retrieval/agent.py（现有检索阶段）",
                                "tools/provider_wikimedia.py / search_provider.py / "
                                "stage33/{pexels,nasa}_source.py（源适配器素材）"],
        "verification": ["core/materials.py（许可门禁 + classify_scene 分类/降级）",
                         "ops/execution.verify_asset_candidate（sha/decode/license）",
                         "orchestration/content_identity.py（MD5+dHash 家族）",
                         "orchestration/crop_recheck.py（裁剪检测）",
                         "orchestration/visual_integrity_gate.py（G0–G4/G8/G9 阻断 + G5–G7 仅建议）",
                         "core/semantics.py / core/mm_judge.py + ops/mm_*（相关性/语义判定）"],
        "binding": ["ops/execution.py（asset_binding / exec_replace_asset / append-only ledger）",
                    "core/selection_review.py（人工选定 fail-closed 校验）"],
        "measurement": ["core/direction.py（DQ 层；可扩展新维度）",
                        "orchestration/global_reuse_{policy,ledger}.py（跨片复用治理）"],
        "self_made": ["core/visual_aid.py（spec 校验 + 渲染 + 证据）"],
    },

    # ---------------- Q9 ----------------
    "Q9_unified_source_intake": {
        "contract": "统一 **AssetCandidate**（现有候选 dict 的超集）："
                    "identity(candidate_id, asset_id, sha256, bytes, media_type, width/height/duration) + "
                    "provenance(source_type ∈ local|web|self_made|ai_generated|screenshot, provider, "
                    "source_id, source_url, retrieved_at, retrieval_query, tool/model version) + "
                    "rights(license, license_class, license_cleared, usage_restrictions, attribution, "
                    "license_evidence_ref) + verification(decode probe, dHash, integrity gates, "
                    "relevance judgement MATCH/MISMATCH/UNKNOWN + judge evidence) + "
                    "lifecycle(proposed→fetched→verified→approved(HITL)→bound→appears_in_film)",
        "per_source_rules": {
            "local": "沿用 local_ingest：不下载、就地校验；许可声明原样记录（现状不变）",
            "web": "HTTPS-only、禁跳转、字节/数量预算、必须有 provider 许可声明；**默认 dry-run**，"
                   "获取需人工授权；失败一律 fail-closed（沿用 PROVIDER_* 错误码）",
            "self_made": "沿用 core/visual_aid 的 spec 体系（哈希绑定、无外部素材、安全区约束）",
            "ai_generated": "必须显式标注 source_type=ai_generated + 生成器/版本/提示哈希；"
                            "**默认不得作为『证据』类画面**（政策决定，需人工裁定）",
            "screenshot": "需新增页面/论文/代码截图管线（浏览器渲染）⇒ 当前**不存在**；"
                          "短期沿用 self_made 规格（如 E3 的做法）",
        },
        "entry_points": ["所有来源统一走 provider 层 → 写 asset_index（项目级）→ 验证 → HITL → 绑定",
                         "每次获取/绑定/替换都写 append-only ledger（与 6-G 同构）"],
    },

    # ---------------- Q10 ----------------
    "Q10_capabilities_that_do_not_exist_in_current_6x_path": [
        "机器可读视觉需求（现为自由文本；模式仅在遗留 stage31/33 中且未接线）",
        "流程内的真实外部素材获取（provider 默认 none；H5 规则禁止自动下载）",
        "候选与镜头之间的**语义/视觉相关性评分**（素材路径无 VLM 调用；6-G DQ-8 = NOT_ASSESSABLE）",
        "接入选择与度量的**感知去重/近重复检测**（dHash 仅在遗留 orchestration）",
        "**来源家族**聚类（字段有，聚类无）",
        "**镜像不变**比较（裁剪检测也是遗留未接线）",
        "项目级、稳定 id 的 asset index 一等产物（现为各阶段临时构造 / files 列表）",
        "6.x 内的获取预算/配额核算（stage33/source_quota.py 未接线）",
        "6.x 内的 AI 生成路径（tools/gen_tools.py 为骨架；stage33/graphics.py 极简）",
        "网页/论文/代码**截图捕获**能力（无浏览器渲染工具）",
        "超出『声明字符串映射』的许可核验（不取许可页、不校验许可文本/法域）",
        "6.x 内跨片全局复用台账（orchestration/global_reuse_ledger.py 未接线）",
        "与 claim/证据挂钩的**视觉证据独立性**判定（DQ 侧仅有 narration_visual_support 代理且不可评估）",
    ],

    # ---------------- Phase 7 拆分 ----------------
    "phase7_substages": [
        {"id": "P7-0", "name": "只读审计与契约冻结（本阶段）",
         "inputs": ["6-G 冻结母片与全部台账/证据", "现有代码与 artifact"],
         "outputs": ["本审计产物"],
         "acceptance": ["只读证明（快照一致）", "不改任何既有文件", "10 问逐项有证据"]},
        {"id": "P7-1", "name": "Visual Requirement 契约 + 抽取器（离线，不获取素材）",
         "inputs": ["visual_plan_output", "narration/script", "chapter", "claims/evidence refs",
                    "stage31/visual_intent.py 模式（参考）"],
         "outputs": ["core/visual_requirement.py（schema/校验/哈希）",
                     "tools/visual_requirement_builder.py",
                     "artifact: visual_requirements.json（scene_id → requirement）",
                     "tests/visual_requirement_test.py"],
         "acceptance": ["schema 校验通过；同输入 ⇒ 同哈希（确定性）",
                        "21/21 场景覆盖（或缺项显式 NOT_DERIVABLE，不臆造）",
                        "不改 6-G artifacts；回归套件全绿；**零素材获取**"]},
        {"id": "P7-2", "name": "统一 AssetCandidate 契约 + 项目级资产索引（无网络）",
         "inputs": ["现有 media/ 目录", "H5 两件素材", "materials 候选字段", "core/supply 准入限制"],
         "outputs": ["core/asset_candidate.py", "ops/asset_index.py",
                     "artifact: asset_index（stable id + sha256 + dHash + 权利 + 验证）"],
         "acceptance": ["覆盖现存全部素材（含 H5 两件）", "id 稳定可复算", "零网络",
                        "6-G baseline/母片/台账不变"]},
        {"id": "P7-3", "name": "感知/来源/语义 多样性度量（只读 DQ 扩展）",
         "inputs": ["asset index", "6-G 母片投影时间轴", "orchestration/content_identity 逻辑"],
         "outputs": ["core/diversity.py（dHash 家族 + 镜像不变 + 来源家族）",
                     "ops/direction 新维度（独立命名，不改既有 DQ 阈值）",
                     "read-only 报告（对 6-G 母片的真实数值）"],
         "acceptance": ["数值可复算；DQ-2 原义保留并标注为『身份』口径",
                        "**不修改任何既有 DQ 阈值**", "对 6-G 只读"]},
        {"id": "P7-4", "name": "视觉相关性验证（judge）在现有素材上试运行",
         "inputs": ["requirements", "asset index", "core/semantics.py + mm_judge/mm_quality 现有能力"],
         "outputs": ["relevance 判定（MATCH/MISMATCH/UNKNOWN + 证据引用）",
                     "首份『6-G 母片相关性地图』（新证据，**不回填 6-G 记录**）"],
         "acceptance": ["判定可复算；分歧显式列出；不确定即 UNKNOWN（不猜）",
                        "DQ-8 仍保持 6-G 的 NOT_ASSESSABLE（不得回填/伪造）"]},
        {"id": "P7-5", "name": "受治理的外部获取（默认 dry-run + HITL 授权）",
         "inputs": ["requirements（含 queries_en/query_ladder）", "provider 适配器（先 Wikimedia）",
                    "core/supply 限制", "去重（dHash/来源家族）"],
         "outputs": ["acquisition 计划与候选清单（dry-run）", "（获授权后）落盘素材 + 许可证据 + ledger"],
         "acceptance": ["默认不下载；未获人工授权零网络副作用",
                        "HTTPS-only/禁跳转/预算/字节上限；PROVIDER_* 失败 fail-closed",
                        "许可未清即不得进入候选池；**不自动绑定**"]},
        {"id": "P7-6", "name": "绑定泛化（requirement 驱动）+ 覆盖闭环",
         "inputs": ["requirements", "已验候选", "HITL 决策", "6-G 绑定机制（复用）"],
         "outputs": ["requirement→candidate→binding 链；覆盖报告（相关性/语义覆盖/多样性）",
                     "gap register（无合规素材的镜头 → 人工）"],
         "acceptance": ["全链可复现；PI/DQ 不变量保持；ledger 仅**新增**条目",
                        "缺口显式登记，不静默降级；不追数量指标"]},
    ],
    "priorities": ["P7-1 需求契约（最便宜、解锁一切）", "P7-2 资产索引", "P7-3 多样性度量（只读）",
                   "P7-4 相关性验证", "P7-5 获取（最高风险，最后）", "P7-6 绑定与覆盖闭环"],
    "ordering_rationale": "先测量与契约（可只读、可复算），后获取（有网络/许可/成本风险）；"
                          "任何阶段都不得以『增加素材数量』为目标。",
    "stage1_files_to_change_plan_only": {
        "new": ["src/video_studio/core/visual_requirement.py",
                "src/video_studio/tools/visual_requirement_builder.py",
                "src/video_studio/ops/visual_requirement.py",
                "tests/visual_requirement_test.py"],
        "readonly_reference": ["src/video_studio/stage31/visual_intent.py",
                               "src/video_studio/stage33/visual_intent.py"],
        "possible_extension_requires_authorization": ["src/video_studio/db/schema.py"
                                                      "（新增 artifact 类型 visual_requirements；"
                                                      "仅类型登记，无数据迁移）"],
        "must_not_touch": ["core/materials.py 阈值", "core/direction.py 阈值",
                           "ops/execution.py 既有契约（P7-6 另授权）",
                           "docs/regression_2x/baseline/**", "projects/**",
                           "docs/regression_2x/phase6e_materials/**"],
    },
    "risks_and_fail_closed_boundaries": [
        "相关性 judge ≠ 许可合规：两条门禁必须分别判定，任一未过即不得绑定",
        "VLM/LLM 幻觉：判定必须带证据引用 + 三态（MATCH/MISMATCH/UNKNOWN）+ 人工复核入口",
        "获取引入网络/许可/成本风险：默认 dry-run、HTTPS-only、禁跳转、预算与字节上限、"
        "许可未清即拒、**不自动绑定**、失败 fail-closed（沿用 PROVIDER_* 错误码）",
        "来源腐化（URL 失效）：以 sha256 + 缓存为准，URL 仅作溯源；缓存不得静默淘汰",
        "AI 生成素材必须显式标注且默认不得作为『证据』类画面（需人工裁定政策）",
        "去重不得被博弈：裁剪/镜像/轻微调色副本**不得**计为独立素材（需传入感知家族判定）",
        "**不得**为达标放宽任何既有 DQ/PI 阈值；新维度独立命名、独立门禁",
        "任何新步骤必须落 append-only ledger；缺口必须显式登记（不静默降级为『用池内近似素材』）",
        "6-G 冻结物（母片/baseline/tag/台账/register/冻结材料）在本阶段与后续阶段均**只读**；"
        "DQ-8 的 NOT_ASSESSABLE 不得回填",
    ],
}
audit["audit_sha256"] = hashlib.sha256(json.dumps(
    audit, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()
).hexdigest()
OUT.write_text(json.dumps(audit, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print("verdict:", audit["verdict"], "| snapshot identical:", audit["repo_snapshot_verified_identical"])
print("audit ->", OUT)
