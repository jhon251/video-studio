# PHASE 12 报告：素材索引许可数据 join（让"记录在案的许可"进入绑定门禁）

> 阶段：Phase 12 ｜ 依据：Phase 12 授权书（2026-09-30）｜ 结论：**DONE（回归全绿）**
> 铁律：**只搬运已记录的声明，绝不推断、绝不猜测**；记录缺失 ⇒ 保持 `UNKNOWN`（仍走 HITL）；
> 记录冲突 ⇒ 标记冲突（仍走 HITL，**不择一采信**）；**零 LLM、零网络、零执行**。
> `config.json` / `config.example.json` **零改动**（P10 教训）；历史基线、v9/C1–C4/E/H 成片、
> Phase 7–11 产物零改动。

## 1. 开工前状态核对（§1）与差异登记

| 核对项 | 结论 | 证据 |
|---|---|---|
| P7-2 AssetIndex 构建入口与格式 | ✅ | `logs/asset_index.json`（`asset-index-v1`）——`candidates[]` **8 个**资产，字段含 `asset_id/sha256/license/license_class/attribution/provider/source_id/source_url/license_gate_applies/role_in_master/provenance` |
| P7-6 BindingProposal/coverage 的 license 路径 | ✅ | `ops/visual_binding.py`：`license_gate_applies()` + `VA.license_decision(license, license_class)` ⇒ 候选 `_license_decision`；**21 提案**（15 KEEP / 1 REPLACE / 5 HITL_REQUIRED = S01、S13–S16） |
| `core/materials.py::classify_license` | ✅ **语义零改动** | 行为实测表：`Public domain`→`(PUBLIC_DOMAIN, True)`、`CC BY 4.0`→`(FREE_ATTRIBUTION, True)`、`All rights reserved`→`(RESTRICTED, False)`、`unchecked`→`(UNKNOWN, False)`（第二位是 **`cleared`**，非 restricted）；文件 sha256 `253b628c2d0b1348…` 与 `phase4x_audit.json` 历史指纹一致 |

### 1.1 差异登记（现实优先）
1. **授权书称"DB 中素材/下载相关表"**；**实测 DB 无此类表**（全表：`projects/tasks/events/artifacts/decisions/memories/claims/claim_evidence/conflicts/changelog/evidence/llm_judge_cache`）。
   许可相关只有 `artifacts.license` 列（**18,147 行全为 NULL**）⇒ 记为**负证据**，不作为记录来源。
2. 许可记录**实际**存放于：**attribution 产物**（`entries[]`：`provider/source_id/source_url/license/license_class/attribution/selected_asset/scene_id`）、
   **`render_output.material_timeline[].selected_asset`**（`asset_id/sha256/license/license_class/provider/source_url`）、
   **`logs/phase6g_exec_h5.json::asset_records`**、**retrieval_candidates 产物**（`candidates[]` 含 `license/attribution`）；
   而**下载缓存元数据 `media/external/.index.json` 字段仅 `bytes/cached_at/file`（无许可字段）**——这正是 P7-2 `license=UNKNOWN` 的根因（与授权书判断一致）。
3. 初次核验时猜测的 `logs/phase7_immutable_check.json` **不存在**（Phase 7 用了别的命名）⇒ 记为该文件名猜测失误；P7 关键产物已由 P7-2 索引 / P7-6 proposals / coverage 三者覆盖核对。

## 2. P12-1 许可记录源清单（只读审计）

产物：`logs/phase12_license_sources.json`

| 记录来源 | 位置 | 定位键 | 记录数 | 有许可字段 |
|---|---|---|---|---|
| `attribution_artifact` | `artifacts(type='attribution')` | `artifact_id#entries/scene` | 59 | ✅ |
| `render_material_timeline` | `artifacts(type='render_output').material_timeline` | `artifact_id#material_timeline[scene]` | — | ✅ |
| `retrieval_candidates` | `artifacts(type='retrieval_candidates').candidates` | `artifact_id#candidates[i]` | — | ✅ |
| `h5_report_asset_record` | `logs/phase6g_exec_h5.json::asset_records` | `asset_records[i]` | — | ✅ |
| `external_cache_index` | `projects/*/media/external/.index.json` | `provider\|source_id` | 0 | ❌（负证据） |
| `artifacts_table` | `artifacts.license` | `artifact_id` | 0 | ❌（全 NULL） |

**逐资产三态（8 个索引资产）**：`HAS_RECORD 5 / MISSING 3 / CONFLICT 0`（记录总数 **107**）

| asset_id | 索引 license | 三态 | join 后 class | 是否改变索引判类 |
|---|---|---|---|---|
| `ast-0c365d5195d50bba`（S01 在片素材） | `UNKNOWN` | **HAS_RECORD** | `PUBLIC_DOMAIN` | ✅ |
| `ast-92ca33138ffe64f4` | `PD-US` | HAS_RECORD | `PUBLIC_DOMAIN` | 否 |
| `ast-96a8c4dc359f55ea` | `CC BY 4.0` | HAS_RECORD | `FREE_ATTRIBUTION` | 否 |
| `ast-c6168344b7567dea` | `UNKNOWN` | **HAS_RECORD** | `FREE_ATTRIBUTION` | ✅ |
| `ast-f9743df609846f24` | `UNKNOWN` | **HAS_RECORD** | `FREE_ATTRIBUTION` | ✅ |
| `ast-6c3fc5af91ed650d` / `ast-af59386ae68c0572` / `ast-be956d3210501352` | `unchecked` | MISSING | `UNKNOWN` | 否（本地 ingest） |

**匹配可信度取证（双键）**：`ast-c6168344b7567dea` 与 `ast-f9743df609846f24` 的 join 同时命中
`provider|source_id`（`wikimedia_commons|154075752` / `|154075751`）**与** `sha256`，记录原文 `CC BY 4.0`、
attribution `Luka Rifelj (…facebook…)`；`ast-0c365d5195d50bba` 命中 `wikimedia_commons|14238951` + 记录
`license="Public domain"`、`license_class="PUBLIC_DOMAIN"`、attribution `MGB`（场景 S01/S13/S14/S15/S16 同源）。
**未匹配记录 3 条**（`retrieval_candidates` 中索引宇宙之外的候选）——如实留档，不强行关联。

## 3. P12-2 join 模块与增强覆盖层

`src/video_studio/core/asset_license_join.py`：
- **纯函数**：`license_record()`（判类**调用** `classify_license`，字段 `license_class`/`license_cleared`/`license_blocking`）、
  `match_keys()`/`record_matches()`（**精确键**匹配：`asset_id`/`sha256`/`provider|source_id`/`source_url`，不做模糊或语义匹配）、
  `join_asset()`（三态）、`build_overlay()`、`apply_to_candidate()`、`validate_overlay()`；
- **编排（只读）**：`collect_records()` —— DB `mode=ro` + `query_only`、文件只读；**零写入**。
- **冲突策略**：多记录判类不一致 ⇒ `CONFLICT`，`license_class=UNKNOWN`，两侧 `sides`（判类 + 原文 + 来源定位）全留档，
  policy 明写"门禁按 UNKNOWN 处理（HITL）；不得择一采信"；消费时空（`apply_to_candidate` 原样返回）。
- **缺失策略**：无记录 / 记录本身 `unchecked|unknown` ⇒ `MISSING`（后者 `missing_reason=RECORDS_DECLARE_UNKNOWN`）⇒ 保持 `UNKNOWN`。

**覆盖层产物**：`logs/license_overlay_v1.json`（`asset-license-overlay-v1`，canonical JSON + sha256
`1caa2d7ad93db264…`，`join_rule_version=asset-license-join-v1:record-only-no-inference`，自检通过）。
**原索引零改动（硬证据）**：`run.py build-license-overlay` 前后 `asset_index.json` sha256
均为 `13a637722b06bca0…`（`index_untouched=true`），且该值与历史记录 `asset_diversity.json` 中一致。
**默认不存在 ⇒ 行为与现状完全一致**（见 §5 臂 A）。

## 4. P12-3 绑定模拟接入（**加法、默认关闭**）

- `ops/visual_binding.py::build(db, task_id, logs, overlay=None)`：`overlay` 非空时，候选的
  `license`/`license_class`/`attribution` 由 `ALJ.apply_to_candidate()` 以覆盖层替换（**仅 HAS_RECORD**），
  门禁仍走原 `license_gate_applies()` + `VA.license_decision()`；候选与提案新增 `license_provenance`
  （含 `source_of_record`、覆盖层哈希、join 规则版本、前后判类）。
- **`overlay=None` ⇒ 与 P7-6 逐字节一致**（§5 臂 A 五种比较全 `true`）。
- **未改**：`core/materials.py` 语义（哈希与 `phase4x_audit.json` 一致）、任何门禁阈值、DQ/PI、执行链。

## 5. P12-4 前后对照复验（只读模拟，零执行）

产物：`logs/phase12_coverage_after.json`

**臂 A（无覆盖层）**：与 P7-6 已 ACCEPTED 产物**逐字节一致** ——
`proposals_identical / proposals_artifact_hash_equal / coverage_identical / counts_identical /
proposal_ids_identical` = **全 true** ⇒ 向后兼容硬验收通过。

**臂 B（有覆盖层）**：

| 场景 | license_decision 前 → 后 | decision 前 → 后 | bindable 前 → 后 |
|---|---|---|---|
| S01 | `null`（HITL） → **PASS** | `HITL_REQUIRED` → **KEEP** | 0 → 1 |
| S13 | `null` → **PASS** | `HITL_REQUIRED` → **KEEP** | 0 → 1 |
| S14 | `null` → **PASS** | `HITL_REQUIRED` → **KEEP** | 0 → 1 |
| S15 | `null` → **PASS** | `HITL_REQUIRED` → **KEEP** | 0 → 1 |
| S16 | `null` → **PASS** | `HITL_REQUIRED` → **KEEP** | 0 → 1 |

**覆盖计数前后对照**：`COVERED 16 → 21`、`HITL_REQUIRED 5 → 0`、`UNSUPPORTED 0 → 0`；
动作计数 `KEEP 15 → 20`、`REPLACE 1 → 1`（**S05 保持提案态**）、`ADD/NO_BINDING 0`。
**解锁机理（如实说明）**：五景各有一个候选是被**唯一** `LICENSE_UNKNOWN_HITL` 卡住的
`ast-0c365d5195d50bba`（`relevance=RELEVANT`、人工已记录）⇒ 许可记录 join 后其 license 门转为 PASS，
故整景可由 HITL 转为 KEEP；其余候选仍受 `RELEVANCE_NOT_ASSESSABLE_HITL` 约束（**相关性门不受本阶段影响**）。
**零执行**：`ledger_written=false / rendered=false / assets_replaced=false / six_g_touched=false`。

## 6. P12-5 测试与验收

| 项 | 结果 |
|---|---|
| `tests/asset_license_join_test.py`（新增） | **19/19 PASS**：join 确定性（记录顺序无关、逐字节 + 同哈希）、冲突夹具 ⇒ CONFLICT 不择一、记录缺失/记录自declared-unknown ⇒ MISSING、`classify_license` 行为表（**9 输入，期望取自实测**）+ 零耦合 + 历史指纹、**无覆盖层与 P7-6 逐字节一致**、CJK/URL 编码 attribution 原样保留、真实覆盖层下五景解锁 + provenance 可回溯、S05 保持 REPLACE |
| **完整既有回归** | **75 套件 / 75 rc=0 / FAILED: []** |
| 不可变核验 | `phase12_immutable_check.py` ⇒ **IMMUTABLE_OK**：6-G 母片 / baseline / `config.json`(+example) 钉定值一致；**P7-2 索引**与 `asset_diversity.json` 历史记录一致；**P7-6 proposals/coverage** 与 Phase 10 记录一致；`core/materials.py` 与 `phase4x_audit.json` 一致 |
| 预算 | **LLM $0、网络 0 次**（纯本地数据工程）✔ |

**授权变更登记（不隐藏）**：`ops/visual_binding.py` 哈希由 `f8a48a4bfbcd…` 变为 `d5017ef42b87…`，
原因 = P12-3 授权加法（`overlay` 参数默认 `None`）；向后兼容由臂 A 五项全 `true` 证明。

## 7. 边界遵守（§8）

**未碰**：`core/materials.py` 语义与阈值、PI/DQ 门禁、**P7-2 原索引与 Phase 7 六份产物**、
下载缓存与 provider 配置（join 只读消费记录，**未改下载行为**）、执行链/ledger、其余标准禁改清单
（`mm_*`/`semantics`/`multimodal`/词表/truth 夹具/baseline）、`config.json`。
**未做**：真实素材替换/绑定执行、渲染、**抓取新许可数据（不访问网络补记录）**、LLM 判许可语义、
自动发布、定时任务。

## 8. 产物 sha256 台账（可复算）

| 产物 | sha256 |
|---|---|
| `src/video_studio/core/asset_license_join.py` | `95b8097725f5d68cd2824d640ec4c5f9427f00b95e51077e02bf7026eebd3978` |
| `src/video_studio/ops/visual_binding.py`（P12-3 加法） | `d5017ef42b879afe2a3af4b66a469aab326516f7c2a019bc4f3f8baed2ac3a11` |
| `src/video_studio/cli.py`（build-license-overlay） | `6e8458b08451ac77663156df5da99364028fc721cd2f395d093a5daacb3d6220` |
| `tests/asset_license_join_test.py` | `b83557092df61b6c3368641b8710a68205a0b484653cd3de8681ff03f715876e` |
| `docs/regression_2x/logs/phase12_license_sources.json` | `98da09fd04279a1ce7d2fa18f2b9c7eb25996982bf91600d1deb69d1ecadadde` |
| `docs/regression_2x/logs/license_overlay_v1.json` | `24cc78b5a5952be32aca5293ee48bb476262cb1aa80676718972b0df65590907` |
| `docs/regression_2x/logs/phase12_coverage_after.json` | `7010d5aa17fa3116e0980f463626f6795e07894aff93a8f9cf9d6a7939bd8fb4` |
| `docs/regression_2x/logs/asset_index.json`（P7-2，**零改动**） | `13a637722b06bca0…` |
| `config/config.json`（**零改动**） | `7b03424846f15efc…` |

## 9. 已知限制 / 下一阶段输入

1. **只覆盖"许可"门**：join 让已记录的许可可见；`RELEVANCE_NOT_ASSESSABLE_HITL` 等其它门禁不受影响
   （本轮回放中未阻挡五景，是因为其"上一版素材"已有人工相关性记录；其余候选仍不可绑定）。
2. **本地 ingest 素材（3 个）永远 MISSING**：管线对用户自备文件没有任何提供方声明可查 ⇒ 保持 `UNKNOWN`/HITL
   （与 P2-C/3-A 既有契约一致）；本阶段不新增推断。
3. **未匹配记录 3 条**：索引宇宙之外（`retrieval_candidates` 中的其它候选项）⇒ 留档不关联。
4. 覆盖层是**可选增强**：默认不存在；启用需显式传入（`run.py build-license-overlay` 只生成，
   **不会**自动被管线消费）。
5. `ast-0c365d5195d50bba` 有 **67 条**同源记录全部判类一致（`PUBLIC_DOMAIN`）；若未来出现不一致，
   将按 `CONFLICT` 处理并保持 HITL（本阶段实测 `CONFLICT=0`）。

**完成，STOP，等待下一阶段授权。**
