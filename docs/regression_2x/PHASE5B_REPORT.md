# 5.x Phase 5-B 报告：多模态证据增强 + 人审候选闭环（只生成候选）（2026-09-16）

**授权**：5-B —— ① 基于 5-A 的 `MATCH/MISMATCH/UNKNOWN` 与视觉证据，为 **MISMATCH/低置信度**镜头生成**候选素材**；
② 候选必须可解释（候选 asset、来源、许可证、视觉相似度/语义证据、与旁白的关联证据、风险/限制）；
③ **只生成候选，不自动选材、不自动替换、不自动 redo**；④ 复用 4-C 的 HITL → decision → changelog → redo 闭环，
本阶段**默认只走"候选→人工确认"入口**，未经人工确认不得修改生产状态；⑤ 保留 4-B 与 5-A 全部历史证据（不覆盖、不删除）；
⑥ 许可闸门、append-only、版本链、attribution 1:1、HITL 不得绕过；⑦ 候选不足/视觉模型不可用/许可未知/语义不确定
必须 `UNKNOWN/BLOCKED`，禁止猜测；⑧ 用 S04/S06 做真实候选验证，并覆盖"有合格候选 / 无合格候选 / 许可证不合格"三类路径；
⑨ 全量回归 3-A～5-A，DB/旧产物不应因"仅候选"测试被修改；⑩ baseline + SHA256 + DoD + KNOWN_ISSUES 后 STOP，不进入 5-C。

**基线核对（含授权书文件名笔误，如实登记）**：授权书写的是 `svg5.x-phase5a-baseline.zip` —— 该文件名**不存在**；
实际文件为 `docs/regression_2x/baseline/5.x-phase5a-baseline.zip`，实测 sha256
`1f6bb1062dc7a49570cc298992fd6d99a5579cf387c53c9b0d2aa8c1d8232bac`，**与授权书给出的 SHA256 完全一致**（5,988,237→6,011,955 字节，
文件大小 6,011,955）。按 SHA256 判定为同一基线，本阶段据此继续（该笔误不影响安全性：SHA256 匹配）。

**结论：PASS**（只生成候选；真实 S04/S06 产出合格候选且包含 4-C 历史人工选定素材；三类路径齐备；只读、确定性、无自动写）。

---

## 1. 变更文件与影响面

| # | 文件 | 类型 | 影响面 |
|---|---|---|---|
| 1 | `src/video_studio/core/mm_candidates.py` | **新增**（纯函数 + 只读调用） | 候选池归一（verified+本地存在）、`asset_id` 映射、许可判类与门禁结论、**视觉证据**（同一 CLIP 模型对候选图片按 12 域打分）、**预期域相似度**、资格判定与排除原因码、候选清单与报告 |
| 2 | `src/video_studio/ops/mm_candidates.py` | **新增**（只读） | `mode=ro` 读库 → 复用 5-A 判定 → 候选池 → CLIP 打分 → 人读/JSON 报告（含人工确认命令**文本**） |
| 3 | `tests/mm_candidates_test.py` | **新增** | 5-B 单测 **29/29**（A–I 九组） |
| 4 | `docs/regression_2x/phase5b_evidence.py` | **新增**（docs，不入基线） | 证据收集（真实 S04/S06 + 三路径 + 4-C 交叉核对 + 只读/确定性） |
| 5 | `src/video_studio/cli.py` | 修改（**加法**） | 新增只读子命令 `mm-review`（与 `report`/`metrics`/`semantic-check`/`rhythm`/`multimodal-check` 同列，**不经过** `build_engine()`） |

**未改动**：`core/semantics.py`、`core/lexicons/semantics_v1.json`（4-B）、`core/multimodal.py`（5-A）、
`core/selection_review.py`/`ops/selection_review.py`（4-C 选定写入路径——**仍是对生产状态唯一的写入口**）、
`db/schema.py`、`core/materials.py`、`core/audio.py`、`core/supply.py`、`core/rhythm.py`、`config/config.json`。

## 2. 候选的证据链（要求 2）

每个候选都带：

| 证据类 | 字段（示例值来自真实 S04） |
|---|---|
| 候选 asset | `asset_id`（`asset_ + sha256[:12]`，与 2-C/3-A 同口径）、`name`、`relative_path`、`sha256_prefix`、`bytes` |
| 来源 | `source.provider`（`wikimedia_commons`）、`source_id`（`139518403`）、`source_url`、`scope`（`external`/`local_user_material`） |
| 许可证 | `license`（`CC BY-SA 4.0`）、`license_class`（`FREE_ATTRIBUTION`）、`license_cleared`、`attribution`、`usage_restrictions` |
| **视觉证据** | `visual_evidence.visual_sim_expected`（如 **0.2886**）、`visual_best_domain`（`xr_device`）、`top_domains`、`image_sha256`、**模型指纹**（`snapshot` + `weights_sha256`） |
| 语义/旁白关联 | `semantic_evidence.expected_domain_source`（`lexicon_4b_surface_vote_v1` / 4-E 回退）、`narration_matched_forms`、`narration_sha256`、`keyword_match_score` |
| 风险/限制 | `risks[]`：已被其它镜头占用（列出镜头号）、视觉相似度低于阈值、许可非清晰、本地素材不做法律判断、**替换需重跑渲染并重新通过旁白完整性/响度/抽帧核验** |

## 3. 真实回归：S04/S06（要求 8 第一类）

在 **4-B 真值 + 5-A 判定 MISMATCH** 的冻结产物 `a_2ed5f41d6b58` 上运行 `run.py mm-review`：

| 镜头 | 5-A 判定 | 状态 | 合格候选（按视觉相似度降序） | 被排除 |
|---|---|---|---|---|
| **S04** | MISMATCH（期望 xr_device，Δ=−0.0574） | **CANDIDATES_READY** | ① `Meta Quest 3 side View.jpg` **0.2886** ② `Meta Quest 3 front View.jpg` **0.2817** ③ `Visitor using a Meta Quest 3 VR headset…` **0.2788**（全部 `FREE_ATTRIBUTION` / 来源可溯） | 当前鲨鱼照：`CURRENT_ASSET; LOW_VISUAL_SIM(0.1628<0.22)` |
| **S06** | MISMATCH（期望 xr_device，Δ=−0.0381） | **CANDIDATES_READY** | 同上三条（0.2886 / 0.2817 / 0.2788） | 同上 |

**与 4-C 历史闭环交叉核对**：候选清单**包含** 4-C 中人工实际选定的素材 —— S04 历史选定 `asset_4f49f4c7edd0`（Visitor…）、
S06 历史选定 `asset_edece2b357f1`（Quest 3 front）**都在候选内**（另有 `asset_f3cf2b80432d`）；历史决定
`d_a74b1d9f5ab6`（S04）/ `d_9a7600dfeebf`（S06）仍原样保留在 `decisions` 表中（只读核对）。
→ 说明候选器能把"当时人选的素材"作为候选**再现**，且额外给出一个视觉相似度更高的选项（side），**排序不等于决定**（由人决定）。

每个镜头同时输出**人工确认命令文本**（例如
`python run.py select-candidate <project_id> --scene S04 --asset asset_f3cf2b80432d --by <human_id> --reason "<理由>"`），
该命令**只是文本**：本阶段 `select_candidate_called=0`、`redo_triggered=0`。

## 4. 三类路径（要求 8 第二/三类，与真实路径同一判定代码）

| 路径 | 输入 | 结果 |
|---|---|---|
| 有合格候选 | 真实 S04/S06（above） + 受控样例 | `CANDIDATES_READY`（候选 1–3 条，含全套证据） |
| **无合格候选** | 候选池为空（受控构造） | **`BLOCKED` / `MMC_NO_CANDIDATES`**（不猜测、不凑数） |
| **许可证不合格** | 池中仅有 `fair use`（`RESTRICTED`）素材（受控构造） | **`BLOCKED` / `MMC_NO_LICENSED_CANDIDATE`**，并把该素材列入 `rejected[].excluded_reasons=[LICENSE_NOT_CLEAR(RESTRICTED)]` |
| （附加）视觉不达标 | 池中仅有视觉相似度 0.16 的素材 | 不产出合格候选（`LOW_VISUAL_SIM`，状态 `BLOCKED/UNKNOWN` 之一，**绝不硬凑**） |
| （附加）模型不可用 | 模型目录不存在 | 报告级 **`UNKNOWN` / `MMC_MM_UNAVAILABLE`**，全部待复核镜头 `UNKNOWN` 且**零候选** |
| （附加）期望域推不出 | 旁白无词表命中 | **`UNKNOWN` / `MMC_UNKNOWN_DOMAIN`**（不生成候选） |

> 受控构造的样例素材/许可为构造值，但**走完全相同的判定代码**；真实素材路径见 §3。

## 5. 复用的 4-C 闭环与"未确认不改生产状态"（要求 3/4）

- **唯一写入口仍是 4-C**：`run.py select-candidate`（写既有 `decisions` + `changelog`，含 `--by`/`--reason` 校验）
  与人工 `run.py redo`（append-only + version+1）。本阶段**没有新增任何写入路径**，也没有调用它们。
- 静态证明（测试 G3）：`core/mm_candidates.py` 与 `ops/mm_candidates.py` 无写库 SQL、无
  `write_artifact`/`set_task_status`/`run_cycle`/`build_engine`，且**无** `record_selection(...)`/`select_candidate(...)`/
  `redo(...)` 调用形式。
- 运行声明（报告 `meta`）：`select_candidate_called=0`、`redo_triggered=0`、`db_writes=0`、`production_writes=0`；
  报告 `policy`：`auto_select/auto_replace/auto_redo/writes_to_db/bypasses_hitl/bypasses_license_gate` 全为 `false`，
  `requires_human_decision=true`。

## 6. 历史证据保留（要求 5/6）

- 4-B：`core/semantics.py` 与 `semantics_v1.json` **逐字节未改**（词表 sha256 前缀仍 `083e8d55c9899706`），真值仍钉 `a_2ed5f41d6b58`；
- 5-A：`core/multimodal.py` 未改；5-A 报告/证据文件未改（本阶段只**读取**其判定）；
- 5-B 报告与 5-A/4-B 结论**并列保存**（同一请求同时给出两层判定与候选依据）；
- `decisions`/`changelog` 行数在运行前后**完全一致**（未新增、未修改）。

## 7. 只读与确定性（要求 9）

| 项 | 实测 |
|---|---|
| DB | 真实 DB **字节未变**；`tasks/artifacts/events/decisions/changelog` 行数未变 |
| 项目文件 | 该项目 **74 个文件（含 5 个成片与全部历史产物）逐字节未变** |
| 确定性 | 同一输入两次运行报告（剔除临时目录与 pid 占位后）**逐字节一致**；候选排序稳定（视觉相似度降序） |
| 不触发 | `redo` 0 次、`select-candidate` 0 次、`build_engine()` 未调用（只读子命令） |
| 模型指纹 | 与 5-A 同一模型：快照 `3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268`、权重 sha256 `a63082132ba4f97a…` |

## 8. 全量回归（要求 9）

| 项 | 结果 |
|---|---|
| 全部套件 | `run_all_suites.py` → **43 total / 43 rc=0 / FAILED: []**（42 + 新增 `mm_candidates_test` **29/29**） |
| 回归批次 | `phase3a_regression_batch.py` → **24/24 as_expected（非预期 0）** |
| 3-A / 3-B | **16/16 PASS** / **32/32 + 12/12** |
| 4-A / 4-B / 4-C | **18/18** / **29/29** / **18/18**（版本链仍 v5 `t_b8f866ddc062`） |
| 4-D / 4-E / 4-F / 4-G | **55/55** / **35/35** / **48/48** / **34/34** |
| 5-A | **34/34**（真值回归 S04/S06 双 MISMATCH 不变） |
| `provider=none` | `config/config.json` 未改；未新增 provider；各阶段默认开关未变 |
| 网络 PENDING | 两项 Wikimedia 真实网络用例**状态与期望值未改写**（本轮通过仅作记录） |

## 9. 未做与已知限制（如实登记）

1. **未做**：自动选材/自动替换/自动 redo、写库、写生产产物、进入 5-C。
2. **候选排序 ≠ 决定**：按**视觉相似度**降序（真实案例里 `side` 排第一，而人当时选了 `Visitor`/`front`）——
   这正是"只给候选、由人决定"的设计；排序不构成推荐结论。
3. **候选池有限**：真实项目只有 4 个已验证本地素材（另外 6 个候选因 `ASSET_OVERSIZE`/`PROVIDER_RATE_LIMITED` 不可用），
   因此三个镜头共用同一组候选，且都带"已被其它镜头占用"的复用风险。
4. **候选图片评分只用 1 帧**（候选是静态图）；`min_visual_sim=0.22` 为工程默认阈值（可配、非法值回退）。
5. **本地自带素材默认不视为合格候选**（`require_license_clear=True`）：因管线无法核验用户声明（与 3-A 的
   `license_gate_applies` 口径一致，见 `KNOWN_ISSUES.md` #6）；如需放行需人工在 4-C 闭环中决定。
6. 授权书基线文件名笔误（`svg5.x-…`）已在 §0 如实登记；按 SHA256 判定为同一基线。

## 10. 冻结结果

| 项 | 值 |
|---|---|
| 标签 | `5.x-phase5b-baseline` |
| ZIP | `docs/regression_2x/baseline/5.x-phase5b-baseline.zip`（6,031,637 字节） |
| **zip sha256** | **`dee0e33cad31418bb04fd76ae9d6d62d394cdd1741e22b8ba7ef31e9a39ab67e`** |
| 文件数 / 源码字节 | **367 文件 / 7,946,132 字节**（`src/ config/ tests/ scripts/` + 根文件，排除 `docs/` 与 `models/`） |
| manifest | `baseline/baseline_manifest_5.x-phase5b-baseline.json`（逐文件 sha256 由 ZIP 内字节重算） |
| 零漂移校验 | `verify_baseline.py 5.x-phase5b-baseline` → **MATCH**（zip 哈希一致、清单 == ZIP 条目、0 缺失、0 漂移） |
| 断点快照 | `snapshots/5.x-phase5b-20260916.{zip,db,json}`（DB sha256 `9b6321d25ce6ec2a…`，17,969,152 字节） |
| 上一冻结基线（未动） | `5.x-phase5a-baseline.zip` sha256 `1f6bb106…2bac` |
| 相对上一基线（实测） | **代码 修改 1 / 新增 3 / 删除 0**：改 `cli.py`；增 `core/mm_candidates.py`、`ops/mm_candidates.py`、`tests/mm_candidates_test.py`；另 `CHANGELOG.md`/`STATUS.md` 文档登记；`config/config.json` 与 DB schema **未变** |
| 回归批次 | `phase3a_regression_batch.py` → **24 项全部 rc=0，非预期结果 = 0** |
| 视觉模型（不入包） | 与 5-A 同一模型：快照 `3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268`、权重 sha256 `a63082132ba4f97a…` |

**停止点**：按授权完成 5-B 即 **STOP**，不进入 5-C。
