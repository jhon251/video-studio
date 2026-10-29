# 4.x Phase 4-C 报告：人审候选替换闭环

- 日期：2026-09-15
- 授权范围（逐字）：**"现在授权 4-C：人审候选替换闭环"**（人工明确选择候选；复用既有 redo/changelog/approval/
  append-only/version+1；必须真实完成 ≥1 次替换；候选池为空或全部不合规必须 BLOCKED；不接第二 Provider、
  不做 BGM/UI/自动语义改选材；不改数据库结构；完成后生成新 baseline）
- 阶段判定：**PASS（替换已真实完成并通过全部验收项）**；另有 1 项**如实登记的新增连带效应**（见 §6）

---

## 0. 实现前检查

| 检查项 | 结果 |
|---|---|
| 基线核对 | `verify_baseline.py 4.x-phase4ab-baseline` → zip 哈希与 manifest 一致、清单==ZIP 条目；zip sha256 `3a7eb41a…191f`（与记录一致）；`drifted vs tree: 0` |
| 是否使用 Git | **未使用**（`Test-Path .git` = False） |
| 是否需要改数据库结构 | **不需要**：复用既有 `decisions` / `changelog` 表（**未新增表/列**，未改任何 schema） |
| 是否改 4-A/4-B 判定逻辑 | **未改**（`core/semantics.py`、`core/lexicons/semantics_v1.json` 未改动） |
| 是否改冻结契约 | **未改**（Claim/HITL、append-only、redo、时间轴权威时长、旁白完整性、响度契约、素材验证、许可台账） |
| 素材验证/许可门禁是否绕过 | **未绕过**：候选来自既有验证管线；选定项仍经 `license_gate_applies`/`license_block_reason` 校验 |

## 1. 替换前后的素材/版本关系

项目 `p_f4b466a4a024`，人工决策者 `human:project-owner`。

| 镜头 | 替换前素材 | 替换后素材 | 许可类别 | 语义判定（4-B，替换后） |
|---|---|---|---|---|
| **S04** | `Tiburón azul (Prionace glauca), canal Fayal-Pico, islas Azores…`（鲨鱼照，`asset_28160d959ed5`） | **`Visitor using a Meta Quest 3 VR headset at IPP Greifswald 2025.jpg`**（`asset_4f49f4c7edd0`，sha256 `4f49f4c7edd0…`） | CC BY-SA 4.0 / FREE_ATTRIBUTION | `MATCH`（原 `MISMATCH R3_DOMAIN_DISJOINT`） |
| **S06** | 同上（鲨鱼照） | **`Meta Quest 3 front View.jpg`**（`asset_edece2b357f1`，sha256 `edece2b357f1…`） | CC BY-SA 4.0 / FREE_ATTRIBUTION | `MATCH`（原 `MISMATCH R2_SENSE_CONFLICT`） |

**版本链（append-only，旧版本全部保留）**：

| render 任务 | 版本 | 状态 | 说明 |
|---|---|---|---|
| `t_ec83e67de429` | v1 | SUCCEEDED | 3-A 首轮（无外部素材） |
| `t_539c107ab85e` | v2 | SUCCEEDED | 3-A 补齐全链路 |
| `t_b7a62ec8e29a` | v3 | SUCCEEDED | 3-B 响度契约重渲染（**替换前**） |
| **`t_1dbf3c1bc6f7`** | **v4** | **SUCCEEDED** | **4-C 人审替换后重渲染（当前）** |

产物关系：旧 `render_output=a_2ed5f41d6b58`（任务 v3）→ 新 `render_output=a_d6411bfe1e32`（任务 v4）；
新 `attribution` 与 `credits_t_1dbf3c1bc6f7.txt` 随新任务生成；旧产物与旧 credits **未被修改**。

## 2. 人工选择证据

| 决定 | decision_id | 决策者 | 状态 | 理由（原文） |
|---|---|---|---|---|
| S04 替换 | `d_a74b1d9f5ab6` | `human:project-owner` | `approved` | 4-C 人工复核：S04 讲佩戴动作，应使用真人佩戴实拍，而非无关鲨鱼照片 |
| S06 替换 | `d_9a7600dfeebf` | `human:project-owner` | `approved` | 4-C 人工复核：S06 为收尾边界交代，用中性产品图替代无关鲨鱼照片 |

- 选择由**人工在复核队列（`run.py review`）提供的候选池中明确指定**：S04 选 `asset_4f49f4c7edd0`、
  S06 选 `asset_edece2b357f1`；未被选中的候选与其他选项一并留在队列与时间轴 `candidates` 中可追溯。
- `decisions.artifact_snapshot` 记录 `scene_id / asset_id / before_asset_id / before_asset_name /
  after_asset_name / render_task / render_artifact`，并标注 `source="4-C human review（人工明确选定；非自动改选材）"`。
- 证据文件：`logs/phase4c_human_decision_evidence.json`。

## 3. redo / changelog / approval 证据

| 机制 | 证据 |
|---|---|
| **redo（append-only + version+1）** | `python run.py redo t_b7a62ec8e29a` → 新任务 `t_1dbf3c1bc6f7`（**version=4**），v1–v3 任务与产物全部保留（未被改写）；`run.py run <pid> --limit 4` 执行完成、任务 SUCCEEDED |
| **changelog** | `#798 selection_override S04:asset_4f49f4c7edd0 by=human:project-owner human_confirmed=1`；`#799 … S06:asset_edece2b357f1 … human_confirmed=1` |
| **approval/人工闸门** | 人工决定以 `decisions.state="approved"` 记录；渲染侧只消费**已批准**的决定（`approved`），未批准/缺字段一律忽略 |
| **渲染侧写入时间轴** | 新时间轴 S04/S06：`selection_source="human_review"`、`human_selection={decision_id, decided_by, reason, decided_at}`、`fallback_state=LOCAL_INGEST`、`insufficiency_class=NONE` |
| **只写既有表** | 记录选定只增加 `decisions`/`changelog` 行；任务/产物/事件行数不变（测试 H6 断言） |

## 4. attribution ↔ timeline 1:1

`attribution`（`a_*`，随 v4 生成）⟷ 新 `material_timeline`：**台账 6 条 / 有素材镜头 6 个，逐条
`scene_id` + `asset_id` + `sha256` 全部一致 → PASS**；`restricted_or_unknown_in_film=[]`；
S04 台账记录 `provider=wikimedia_commons / source_id=177258402 / license=CC BY-SA 4.0 /
sha256=4f49f4c7edd0…`。证据：`logs/phase4c_evidence_summary.txt`、`logs/phase4c_new_film_evidence.json`。

## 5. 新成片 ffprobe / 响度 / 抽帧证据

| 项 | 实测 |
|---|---|
| 成片 | `projects/p_f4b466a4a024/output/t_1dbf3c1bc6f7_draft.mp4` |
| ffprobe | `video/h264` + `audio/aac`，`format.duration=104.000000s` |
| 时长契约 | `video_duration_ok=True`（timeline 104.0s == video 104.0s，Δ=0.0s） |
| **响度（3-B 契约）** | **ok=True，I=-16.1 LUFS，TP=-2.7 dBTP，Δ=-0.1 LU**（目标 -16±1、TP ≤ -1.5） |
| **抽帧核验** | 方法 `frame_pearson_48x48`，**检查 6 镜 / 失败 0 镜**；`appears_in_film` 6/6 为 True；**S04 corr 0.472、S06 corr 0.919**（阈值 0.30） |
| 语义复核（4-B 对**新成片**） | `S04 MATCH`、`S06 MATCH`（原分别为 `R3_DOMAIN_DISJOINT` / `R2_SENSE_CONFLICT`） |

## 6. 一并如实登记的连带效应（未自动处理）

替换后**出现 1 个新的 `MISMATCH`：S05**。原因：项目的 `asset_reuse_policy=prefer_unused`，
S04 占用了原属 S01/S05 的 "Visitor…" 图后，**被释放出来的鲨鱼照**成为 S05 的"未使用候选"并被确定性选中
→ 语义 `MISMATCH` 由 S04/S06 **转移**到 S05（`MISMATCH` 计数 2 → 1）。

- 这是**确定性复用策略的后果**，**不是**自动改选材（我未对 S05 做任何自动决定）。
- 处理方式：**未自动再改**；若需修正，人工再下一次决定即可（机制已就绪：
  `run.py review` → `run.py select-candidate … --scene S05 …` → `run.py redo <render_task>`）。
- 该现象已登记为 4.x 已知问题（另见 §8）。

## 7. 回归

**套件**：`run_all_suites.py` → **37 total / 37 rc=0 / FAILED: []**（36 旧 + 新增 `human_selection_test` **18/18**；
其中 4-B 套件 **29/29**、4-A 套件 **18/18**、3-C 报告套件 **18/18**、3-B 响度 **32/32**、3-A 合规 **24/24**）。

**批次**：`phase3a_regression_batch.py` → **24 项中 22 项 rc=0**；`phase3a_classify_batch.py` →
非预期结果 = **2 项**，均为**真实网络**用例（见 §8.7）。

| 项 | 命令 | 结果 |
|---|---|---|
| 全部套件 | `run_all_suites.py` | **37/37 rc=0**（`FAILED: []`） |
| 4-C 机制 | `tests/human_selection_test.py` | **18/18** |
| 4-A 指标 | `tests/metrics_test.py` | **18/18**（M6b 已改为跨模块一致性） |
| 4-B 验证器 | `tests/semantic_check_test.py` | **29/29**（真值钉在冻结产物 `a_2ed5f41d6b58`；含 C0 载体断言） |
| **3-A 真实链路（离线复核）** | `phase3a_real_chain.py --resume p_f4b466a4a024` | **16/16 PASS**（替换后抽帧 S04 0.472 / S06 0.919） |
| 3-B 响度 | `tests/audio_loudness_test.py` / `phase3b_failure_paths.py` | **32/32** / **12/12**（新成片实测 **-16.1 LUFS / TP -2.7 dBTP**） |
| 3-C 只读报告 / 成本边界 | `tests/report_command_test.py` / `phase3c_cost_boundary.py` | **18/18** / rc=0 |
| 2-C 追溯 / 故障矩阵 | `phase2c_trace.py` / `phase2c_fault_matrix.py` | **38/38** / A/C 出片、B/D **BLOCKED** |
| 2-D 边界 / Provider E2E | `phase2d_boundary_matrix.py` / `phase2d_provider_e2e.py` | **40/40** / **12/12** |
| ingest / E2E / 真实小测 / 二进制 / 2-A·B 验收 | 同批次 | PASS（抽帧 0.747）/ A/B/C **SETTLED** / PASS（MockLLM=0）/ PASS / PASS |
| **network（环境）** | `phase2e_failure_paths.py` / `phase2e_real_provider.py` | **rc=1 → `PENDING（环境）`**（TLS 握手超时 / `PROVIDER_TIMEOUT`；**期望值未修改、状态未改写**） |
| Provider 契约 / 分类学 | `material_provider_test.py` / `material_taxonomy_test.py` | **46/46** / **40/40** |

**`provider=none` 回归**：`config/config.json` sha256 `b264644539b2adbb…` 与冻结基线 manifest **一致**；
默认配置产出的项目仍为 `mode=none`、外部请求/下载 = 0 且照常出片（`tests/metrics_test.py` M5 组、
`logs/phase4ab_provider_none.txt`）。

**替换前后 3-A 关键断言对照**：全部 16 项仍 PASS；被替换的两个镜头抽帧相关度由
S04 0.736（鲨鱼照）→ **0.472（真人佩戴图）**、S06 0.732（鲨鱼照）→ **0.919（Quest 3 正面图）**，
均 ≥ 阈值 0.30；`attribution` 条目数 6 == 有素材镜头数 6。

## 8. 未完成项与已知问题（如实登记）

1. **S05 新增 MISMATCH**（§6）：属复用策略连带效应，未自动处理，需人工再决定。
2. **候选池规模受限**：本项目的可替换候选只有 3 个（其余 6 个候选因 `ASSET_OVERSIZE`/`PROVIDER_RATE_LIMITED`
   被拒，**不可选**）——若候选池为空或全部不合规，机制会给出 `HUMAN_SELECTION_EMPTY_POOL` / 校验失败并
   要求 BLOCKED（测试 H3/H5 已覆盖），**不会**随便选一个凑通过。
3. **人工决定无身份认证**：`--by` 是自填标识（无登录/签名机制），仅作审计留痕；如需强身份需另行设计（不在授权内）。
4. **决定不可撤销/覆盖语义为"最新一条生效"**：同镜头再记录一条即以后者为准（旧的仍 append-only 保留）。
5. **4-A/4-B 的既有已知限制不变**（真值样本 n=6、知识库覆盖有限、`keyboard` 等同形词未收录、未实现 LLM 判定、
   判定结果不落库）。
6. **3.x 已知问题状态一律不变**（`docs/KNOWN_ISSUES.md` 13 项）。
7. **2 项 Wikimedia 真实网络回归仍为 `PENDING（环境）`**：`phase2e_failure_paths`、`phase2e_real_provider`
   （TLS 握手超时，`logs/phase4ab_net_probe.txt`）；**状态未改写、期望值未修改**。
   **跨时点观察（仅记录，不改状态）**：同一脚本在本阶段两次收尾时各出现过一次 **29/29 通过**
   （网络间歇恢复），随后再次因超时失败 → 该振荡本身即"环境不稳定"的证据。
8. **4-C 期间对测试的两处口径修正（非放宽）**：① 4-B 真值表**钉在 3-A 冻结产物**（此前读"最新成片"，
   会被 4-C 的修复带漂移——那等于改真值凑绿）；② 4-A 的 M6b 由硬编码旧期望改为**跨模块一致性**。
   两处都只改"载体/断言方式"，**没有**改动任何判定逻辑、阈值或真值。

## 9. 新 baseline

| 项 | 值 |
|---|---|
| 标签 | `4.x-phase4c-baseline` |
| ZIP | `docs/regression_2x/baseline/4.x-phase4c-baseline.zip`（5,889,743 字节） |
| zip sha256 | `08018d4e81d8c3df0a85953158bda1d86c02494237413f4b91b2b6d56f09171d` |
| 文件数 / 源码字节 | **348 文件 / 7,538,751 字节**（`src/ config/ tests/ scripts/` + 根文件，**排除 `docs/`**） |
| manifest | `baseline_manifest_4.x-phase4c-baseline.json`（逐文件 sha256 由 ZIP 内字节重算） |
| 零漂移校验 | `verify_baseline.py 4.x-phase4c-baseline` → **MATCH**（zip 哈希一致、清单 == ZIP 条目、**0 缺失、0 漂移**） |
| 阶段 snapshot | `snapshots/4.x-phase4c-20260916.{zip,db,json}`（DB sha256 `8a05cd7aa83d73e2…`，12,042,240 B） |
| 收工中间态（历史） | `snapshots/4.x-phase4c-wip-20260915.{zip,db,json}`（zip sha256 `00f1e15a…d02e`） |
| 上一冻结基线（未动） | `4.x-phase4ab-baseline.zip` sha256 `3a7eb41a…191f`（工件完好、manifest 内部一致） |

**相对 4-A/4-B 基线的变更（`logs/phase4c_change_list.json`）**：**修改 8 / 新增 3 / 删除 0** ——
修改 `CHANGELOG.md`、`README.md`、`STATUS.md`、`agents/editing/agent.py`、`cli.py`、`ops/metrics.py`、
`tests/metrics_test.py`、`tests/semantic_check_test.py`；
新增 `core/selection_review.py`、`ops/selection_review.py`、`tests/human_selection_test.py`。
（`ops/metrics.py` 的改动仅为**新增只读参数** `artifact_id` + `_art_by_id()`，用于把真值钉在指定产物上；
4-A/4-B 的判定逻辑与阈值**未改动**。）

## 10. 停止点

按授权：**未**接入第二 Provider、**未**做 BGM/UI/节奏自动改时长/Git tag、**未**做自动语义改选材或自动生成替换候选、
**未**修改成片（替换只能由人工显式 `redo` 触发）、**未**改数据库结构、**未**改 4-A/4-B 判定逻辑与任何冻结契约。
**已完成即 STOP，不进入 4-D/4-E/4-F。**
