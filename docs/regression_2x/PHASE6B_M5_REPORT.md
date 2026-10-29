# 6-B/M5 报告 —— Execution Reliability Closure（关闭 M4 两个 PENDING）

- 阶段：**6-B/M5**（授权：**仅**关闭 6-B/M4 已披露的两个 PENDING，不进入 6-C）
- 关闭对象：
  - **P1**：真实素材 `add_asset / replace_asset` 执行分支 E2E
  - **P2**：多 Proposal 并发/重叠修改的冲突检测、一致性与 fail-closed
- 上游：`logs/phase6b_m4_v9_execution.json`（M4 受控执行）、`logs/phase6b_m3_proposals_v9.json`（8 条真实方案）、
  `logs/phase6b_m2_review_ledger_v9.jsonl`（11 条人工决策）
- 未做：自动批准、自动执行未批准方案、自动合并/排序/扩大范围、修改 PI-1…PI-6、把 DQ 接入 `TASK_BLOCKED`、
  改动 5.x Final / r1 / r2 / r3、覆盖 v9 母版；**未进入 6-C**。

---

## 0. 结论速览

| 项 | 结论 |
| --- | --- |
| **P1 真实素材分支** | **已关闭**：2 条 **APPROVE → 真实执行 → 强制 PI/DQ 复核** 闭环，素材**真实存在 + sha256 一致 + 可解码 + 许可不受限** |
| P1 上屏证明 | 成片**抽帧比对**：A1 相关度 **0.9982**（原素材 −0.119）、D1 **0.7639**（原素材 −0.0891），`replaced=True` |
| P1 失败/待处理 | sha 不符 → `FAILED`(ASSET_SHA_MISMATCH)；文件不存在 → `PENDING_HUMAN_ASSET`(ASSET_MISSING)；不可解码 → `FAILED`(ASSET_UNDECODABLE)；许可受限 → `FAILED`(ASSET_LICENSE_RESTRICTED)；许可未清 → `PENDING_HUMAN_ASSET`(ASSET_LICENSE_PENDING) |
| P1 零虚构 | 成功者**全部**带真实素材证据（`succeeded_without_real_asset_evidence=[]`）；无占位/替代/降级分支（静态 + 运行期证明） |
| **P2 冲突检测** | **已关闭**：`scene / window / asset / target` 四类重叠规则 + 全对矩阵（M5 集合 6 对；6-B/M3 真实 8 方案 **10 对**） |
| P2 阻断语义 | **对称阻断**：参与冲突者**全部** `BLOCKED_CONFLICT`，`requires_human_reapproval=True`，`executor_invoked=False`；**不**自动合并/排序/扩范围 |
| P2 无假阻断 | 未批准（`BLOCKED_UNAPPROVED`）/被拒（`BLOCKED_REJECTED`）方案**不**进入可执行集合 ⇒ 不拖住已批准方案（v9 batch1 `blocked_conflict=[]`） |
| P2 一致性 | 幂等：同一 `proposal_id + proposal_sha256` 重放 ⇒ `BLOCKED_ALREADY_EXECUTED`（不重复执行）；冲突判定**优先**于幂等 |
| P2 并发 | 加锁后：两条互不重叠方案并发 ⇒ 都成功且台账 seq 连续；**同一方案并发 ⇒ 一条成功、一条被幂等阻断** |
| 审批绑定 | 审批仍绑定 `proposal_id + proposal_sha256 + 人工身份 + 时间 + 理由/溯源`（10 条真实审批，`auto_approved=false`） |
| 台账 | 审批链 10 条、执行链 21 条，两条独立 append-only 哈希链，`chain_ok=true`、seq 连续唯一 |
| PI / DQ | PI-1…PI-6 **定义与阈值未改**（M4 冻结状态机逐字未变）；执行后 PI 仍 `BLOCKED`；DQ 仍 advisory（只读推演时间轴，未写回） |
| 真值集 | 新增 30 个 case（冲突 12 / 素材 10 / 批量 8），冻结锚 `78c40cfa247a849e4af898bcdb96a333398fd0cdac84c240e9393eeaf8336ca7` |
| 单测 | M5 新套件 **75/75**；M4 及受影响套件全部 rc=0（详见 §4） |
| 完整回归 | 批次 24/24；电池 25 步；`unit_suites`（详见 §5） |
| 完整性 | r1/r2/r3/5.x-final **四个 ZIP 全部未被改写**；DB / v9 母版 / v9 output 目录 **逐字节未变**；产物只在沙箱内 |

---

## 1. 变更清单

### 1.1 修改（**只增不改**：M4 常量与判定语义保持不变）

| 文件 | 变更 | 说明 |
| --- | --- | --- |
| `src/video_studio/core/execution.py` | +约 210 行 | 新增 M5 冲突层：`M5_STATES`、`ALL_EXECUTION_STATES`、`OVERLAP_POLICY`、`CONFLICT_KINDS`、`proposal_footprint`、`_target_identities`、`_window_intersection`、`pair_conflict`、`detect_conflicts`、`executed_ids`、`gate_batch`、`blocked_record`、`execute_batch`、`_NullLock`。**`EXECUTION_STATES` / `POLICY` / `APPROVAL_*` 均逐字未改**（M4 真值集 T0 仍通过） |
| `src/video_studio/ops/execution.py` | +约 230 行 | 真实素材校验 `verify_asset_candidate`（存在 → sha256 → 可解码 → 许可，复用冻结 3-A 口径）、`current_asset_for_scene`、`probe_media`、窗口内真实替换 `_encode_still_segment`/`_splice_window`、`exec_replace_asset`/`exec_add_asset`、成片抽帧比对 `asset_replacement_evidence`、DQ 推演 `project_timeline`；`pi_recheck` 增加 `dq_details`/`timeline_projection`/`asset_evidence` |
| `tests/maintenance_fixes_test.py` | M8e 判定精度修正 | `str.replace(old,new)` 双参形态不算文件替换（`Path.replace(target)` 只一个实参）；**强度不变**（新增负对照样本 `path_replace_escape` 仍被检出、`str_replace_is_not_a_write` 不误报） |
| `docs/regression_2x/phase6b_m4_m8e_negctl.py` | 负对照样本 8 → 10 | 增设 `Path.replace` 逃逸（必须检出）与 `str.replace`（不得误报）；JSON 证据已重跑 |

### 1.2 新增

| 文件 | 行数 | 作用 |
| --- | --- | --- |
| `tests/fixtures/execution_reliability_truth_v1.json` | ~200 | M5 真值集：冲突 12 例 / 素材 10 例 / 批量 8 例 + 策略镜像 + M3 真实矩阵期望 + v9 期望 + 边界声明 |
| `tests/execution_reliability_test.py` | ~430 | M5 套件 **75 项**：T0 冻结 / T1 冲突矩阵 / T2 素材真实校验 / T3 批量一致性 / T4 v9 真实证据 / T5 并发 / T6 零自动化 |
| `docs/regression_2x/phase6b_m5_execute_v9.py` | ~330 | v9 真实闭环取证（3 批次：真实执行 / 重放 / 冲突） |
| `docs/regression_2x/phase6b_m5_build_truth.py` | 55 | 真值冻结（规范化 sha 写回 + 记录） |
| `docs/regression_2x/phase6b_m5_{batch_items,battery,guard_check,final_check}.py` | — | 全量回归夹具（沿用 M2/M3/M4 同一套步骤表与口径） |

### 1.3 明确未改动

- **未**修改 `core/integrity.py`（PI-1…PI-6 定义/阈值）、`core/direction.py`（DQ-1…DQ-8）、
  `core/revision.py`、`core/human_review.py`、`core/materials.py`（复用其冻结阈值 0.30 / 0.15）。
- **未**修改 `agents/**`（执行层仍不在生产判定链内；`agents` 不 import `execution`）。
- **未**修改 M4 真值集 `revision_execution_truth_v1.json`（`T0e` 断言其 `execution_states` 与代码逐字一致）。
- **未**新增 CLI 子命令、**未**新增基线/tag。

---

## 2. PENDING #1 关闭：真实素材 `add_asset / replace_asset` 执行分支 E2E

### 2.1 素材索引与**真实**校验（10 条：5 真实 + 5 构造）

素材来源 = v9 渲染产物 `material_timeline` 的候选/在用素材（**真实文件**，非合成）。

| asset_id | 构造? | 校验结果 | 依据 |
| --- | --- | --- | --- |
| `asset_23e71bc8a864` | 否 | `ASSET_OK` | 存在 + sha256 一致 + 可解码（local_ingest ⇒ 3-A 许可门禁不适用） |
| `asset_30dd89a16713` | 否 | `ASSET_OK` | 1920×1080 真实素材（v9 在用） |
| `asset_3f0b94a3f2ac` | 否 | `ASSET_OK` | S20 当前素材（1920×1080） |
| `asset_432cd85be6f1` | 否 | `ASSET_OK` | PUBLIC_DOMAIN（cleared） |
| `asset_cfae038f6106` | 否 | `ASSET_OK` | **外部** CC BY 4.0（cleared）⇒ 外部素材分支可用 |
| `asset_synthetic_sha_mismatch01` | 是 | `ASSET_SHA_MISMATCH` → **FAILED** | 记录 sha 与文件实际 sha 不一致 |
| `asset_synthetic_missing01` | 是 | `ASSET_MISSING` → **PENDING_HUMAN_ASSET** | 索引有记录但文件不存在 |
| `asset_synthetic_broken01` | 是 | `ASSET_UNDECODABLE` → **FAILED** | 文件存在但非图像 |
| `asset_synthetic_restricted01` | 是 | `ASSET_LICENSE_RESTRICTED` → **FAILED** | 外部素材 + `fair use` |
| `asset_synthetic_unknown01` | 是 | `ASSET_LICENSE_PENDING` → **PENDING_HUMAN_ASSET** | 外部素材 + `unknown` |

校验口径（每条都**实际重算** sha256、真实 ffprobe 解码，不采信索引声明）：
`存在 → sha256 一致 → 可解码 → 许可（复用冻结 3-A 口径：门禁只适用于外部素材）`。
**校验失败 ⇒ 渲染函数一行都不会被调用**（T2 静态：同一函数内 `verify_asset_candidate` 调用行号 < 渲染调用行号；
且代码中不存在 `fallback_asset` / `substitute` 分支）。

### 2.2 真实闭环（2 条 APPROVE → EXECUTION → PI/DQ recheck）

| 方案 | 素材（真实） | 结果 | 成片抽帧比对（只读） |
| --- | --- | --- | --- |
| `M5-A1-replace-S20` | `asset_30dd89a16713`（1920×1080，local_ingest） | **SUCCEEDED** | 新素材相关度 **0.9982** / 原素材（`asset_3f0b94a3f2ac`）**−0.119** ⇒ `replaced=True`，名额余量 ≫ 0.15 |
| `M5-D1-replace-S21` | `asset_cfae038f6106`（5472×3648，**外部 CC BY 4.0**） | **SUCCEEDED** | 新素材相关度 **0.7639** / 原素材（`asset_30dd89a16713`）**−0.0891** ⇒ `replaced=True` |

- 每窗口抽 **3 帧**（窗口 25% / 50% / 75%），与「新素材 / 原素材」做冻结口径的 48×48 灰度 Pearson 比对；
  阈值复用 `materials.DEFAULT_POLICY`：`frame_match_min_corr=0.30`、`frame_argmax_margin=0.15`。
- 执行是**真实的媒体改写**：head 流复制 + 素材段重编码（覆盖式缩放，不留黑边）+ tail 重编码 + 拼接；
  产物（沙箱内）：`…_m5_rp-49c8e100fae9_replace.mp4`（48,591,819 B）、
  `…_m5_rp-11fe46371751_replace.mp4`（53,815,260 B），输入 = 母版复制品（46,761,341 B）。
- **执行后强制重跑 PI-1…PI-6**（复用冻结度量 + M2 门禁）：
  `PI-1 FAIL / PI-2 FAIL / PI-3 FAIL / PI-4 PASS / PI-5 FAIL / PI-6 FAIL ⇒ pi_gate_outcome = BLOCKED`。
- **DQ 只读复核**（advisory）：`DQ-1 UNKNOWN / DQ-2 FAIL / DQ-3 FAIL / DQ-4 FAIL / DQ-5 FAIL / DQ-6 FAIL / DQ-8 FAIL`。
- **DQ-2 推演数值（诚实披露部分改善）**：A1 换用**已在片中**的素材 ⇒ 唯一素材数仍 **4**（最大占比 0.3329→0.3211）；
  D1 换用**从未使用**的素材 ⇒ 唯一素材数 **4 → 5**；两者仍 `FAIL`，因为冻结阈值要求 **≥6** 个唯一素材。
  ⇒ 本报告**不**声称"DQ-2 已改善"，只给出真实数值。

### 2.3 fail-closed 证明（无素材 / 素材失效 / 校验失败）

| 方案（均已人工 APPROVE） | 结果 | 执行器是否调用 | 是否产出 |
| --- | --- | --- | --- |
| `M5-A2-sha-mismatch-S11` | **FAILED** | 是（校验后立即抛错，**未**渲染） | 无 outputs |
| `M5-A3-asset-missing-S05` | **PENDING_HUMAN_ASSET** | 是（返回待处理） | 无 outputs |
| `M5-A4-undecodable-S18` | **FAILED** | 是（校验后抛错） | 无 outputs |
| `M5-A5-license-restricted-S12` | **FAILED** | 是（校验后抛错） | 无 outputs |
| `M5-A6-license-unknown-S08` | **PENDING_HUMAN_ASSET** | 是（返回待处理） | 无 outputs |

即：**批准 ≠ 执行**——素材不真实/失效时，方案**只能**落到 `FAILED`（校验失败）或 `PENDING_HUMAN_ASSET`（无素材/许可未清），
不存在"换个素材""放个占位图""降低校验标准"的路径（静态 + 运行期双重证明）。

---

## 3. PENDING #2 关闭：多方案重叠/冲突、一致性与 fail-closed

### 3.1 冲突规则（全部为**阻断**型；写死在 `OVERLAP_POLICY`）

| 规则 | 判据 | 处置 |
| --- | --- | --- |
| `scene` | 共同 `scene_id` | 冲突 |
| `window` | 窗口区间有**正长度**交集（端点相接**不算**） | 冲突 |
| `asset` | 共同 `asset_id`（即使窗口不相交，也**保守**判冲突） | 冲突 |
| `target` | 同一目标资源身份（`scene_id/scenes/asset_id/assets/path/slot/window`） | 冲突 |
| class 级描述词（如 `asset_class`） | **不**作为身份 | 不算冲突（避免"所有素材类方案互斥"的过度阻断） |

处置语义（fail-closed）：**对称阻断**——参与任一冲突的方案**全部** `BLOCKED_CONFLICT` +
`requires_human_reapproval=True` + `executor_invoked=False`；**不自动合并、不自动排序、不自动扩大范围**。
冲突只在**可执行集合**（个体门禁已通过者）内成立 ⇒ 未批准/被拒方案不会造成假阻断。

### 3.2 冲突/重叠矩阵

**(a) 6-B/M5 真实方案集合（11 条：9 条 M5 + H1/H3b 对照）——6 对冲突**

| 方案 A | 方案 B | 重叠种类 |
| --- | --- | --- |
| `M5-A1-replace-S20` | `M5-C1-replace-S20-conflict` | scene, window, target |
| `M5-A1-replace-S20` | `M5-C2-replace-S20-conflict` | scene, window, target |
| `M5-C1-replace-S20-conflict` | `M5-C2-replace-S20-conflict` | scene, window, target |
| `M5-D1-replace-S21` | `M5-C1-replace-S20-conflict` | **asset**（同一新素材） |
| `M5-A2-sha-mismatch-S11` | `H3-batch2-next-longest` | scene（**不阻断**：H3b 已被 REJECT） |
| `M5-A5-license-restricted-S12` | `H3-batch2-next-longest` | scene（同上） |

**(b) 6-B/M3 真实 8 条方案（只读复算）——10 对冲突**

| A | B | 种类 | A | B | 种类 |
| --- | --- | --- | --- | --- | --- |
| H1-hook-replace | H6-visual-climax-aid | scene, window | H3-batch1 | H5-semantic-mismatch | scene, target |
| H2-asset-pool-diversity | H3-batch1-split-longest | scene | H3-batch2 | H6-visual-climax-aid | scene, target |
| H2-asset-pool-diversity | H4-density-increase | scene | H3-batch2 | H5-semantic-mismatch | scene, target |
| H2-asset-pool-diversity | H5-semantic-mismatch | scene | H4-density-increase | H5-semantic-mismatch | scene, target |
| H3-batch1 | H4-density-increase | scene, target | H6-visual-climax-aid | H5-semantic-mismatch | scene, target |

完整**逐对矩阵**（对称、自反对角为 `None`）落在 `logs/phase6b_m5_v9_execution.json`
的 `conflict_matrices.m5_set.matrix`（11×11）与 `m3_register_8`（8 方案）。

### 3.3 v9 三个批次的真实结果

| 批次 | 提交（顺序=输入顺序） | 结果 |
| --- | --- | --- |
| `batch1`（9 条） | A1, D1, A2, A3, A4, A5, A6, H1（未批准）, H3b（被拒） | **A1/D1 SUCCEEDED**；A2/A4/A5 FAILED；A3/A6 PENDING_HUMAN_ASSET；H1 BLOCKED_UNAPPROVED；H3b BLOCKED_REJECTED；**`blocked_conflict=[]`（无假阻断）** |
| `batch1_retry`（同 9 条重放） | 同上传入顺序 | **A1/D1 `BLOCKED_ALREADY_EXECUTED`**（幂等，不重复执行）；其余同上 |
| `batch2_overlap`（3 条，均已批准） | A1, C1, C2 | **三条全部 `BLOCKED_CONFLICT`**，`executor_invoked=False`，无新产物 |

统计（21 条执行记录）：`SUCCEEDED 2 / FAILED 6 / PENDING_HUMAN_ASSET 4 / BLOCKED_CONFLICT 3 /
BLOCKED_UNAPPROVED 2 / BLOCKED_REJECTED 2 / BLOCKED_ALREADY_EXECUTED 2`；
`executed_without_approval=[]`、`auto_approved=false`、`promoted=[]`。

### 3.4 一致性与并发

- **幂等**：`executed_ids(ledger, proposal)` 以 `proposal_id + proposal_sha256 + state=SUCCEEDED` 为准；
  重放被阻断（v9 实测 + 单测 BT-4）。
- **优先级**：冲突判定**先于**幂等（BT-5 与 v9 batch2 中已执行过的 A1 仍报 `BLOCKED_CONFLICT`）。
- **并发**：`execute_batch(lock=…)` 把「幂等复查 + 执行 + 落账」放入临界区（并**重新读取**台账）：
  - 两条互不重叠方案并发 ⇒ 都成功，台账 `seq == [1,2]`、`chain_ok=True`；
  - **同一方案并发** ⇒ 一条 `SUCCEEDED`、一条 `BLOCKED_ALREADY_EXECUTED`（`executor_invoked` 仅一次）。
- **不改写输入**：冲突阻断**不修改** proposal（逐字节比对）、不调用执行器、不产生任何 outputs（T6d）。

---

## 4. 新增 truth cases 与单测

### 4.1 真值集 `tests/fixtures/execution_reliability_truth_v1.json`（30 cases）

| 组 | 数量 | 内容 |
| --- | --- | --- |
| `conflict_cases` | 12 | 同镜不同窗 / 跨镜窗口交叠 / 端点相接（不冲突）/ 完全不相干 / 同素材（不相交窗）/ 同目标不同范围 / 三类同时 / 镜+窗+素材 / 双方无痕迹 / 单侧无痕迹 / 0 点相接 / 同批重复提交 |
| `asset_cases` | 10 | 5 真实素材 `ASSET_OK` + 5 构造损坏用例（sha 不符 / 缺文件 / 不可解码 / 许可受限 / 许可未清） |
| `batch_cases` | 8 | 未批准不阻断 / 被拒不阻断 / 冲突对称阻断 / 幂等重放 / 冲突优先于幂等 / 互不重叠各自执行 / 篡改仍阻断 / 全片重写仍阻断 |
| 附加 | — | `overlap_policy` 镜像、`m3_register_matrix_expect`（10 对）、`v9_expect`、`ledger_contract`、`concurrency_contract`、`boundary_notes` |

冻结锚：**`78c40cfa247a849e4af898bcdb96a333398fd0cdac84c240e9393eeaf8336ca7`**
（`logs/phase6b_m5_truth_freeze.json` 记录，T0g 断言一致）。

### 4.2 M5 套件 `tests/execution_reliability_test.py`：**75/75 通过**（`SKIP=[]`，rc=0）

| 组 | 覆盖 |
| --- | --- |
| T0（7 项） | schema/阶段、冻结锚、`OVERLAP_POLICY` 逐键一致、`CONFLICT_KINDS`、M5 状态（且 **M4 状态机逐字未变**）、零自动化偏好写死、冻结记录一致 |
| T1（15 项） | 12 个冲突用例逐例 kinds 比对 + M3 真实 8 方案 10 对逐对一致 + 矩阵对称/自反 + 种类覆盖 ≥3 |
| T2（15 项） | 10 条素材校验逐条代码/状态/构造标记 + 真实素材全部 `ASSET_OK` 且实际 sha == 记录 sha + 许可门禁适用性 + verify 先于渲染（AST 行号）/无替代分支 |
| T3（10 项） | 8 个批量用例逐例状态比对 + 冲突记录带 `requires_human_reapproval` 与对手 + 阻断者不调用执行器 |
| T4（16+ 项） | v9 三批次状态、无假阻断、冲突批三条全阻断且未调用执行器、2 条真实素材 E2E（`replaced=True` + 相关度/边距）、抽帧为只读度量、PI 强制重跑、DQ advisory + DQ-2 推演数值、无假成功、零提升、双链完整、DB/母版/目录零改动 + 沙箱内产物、构造用例登记、台账 21 条 |
| T5（3 项） | 并发互不重叠都成功 + 链连续 + 同方案并发一条被幂等阻断 |
| T6（5 项） | 静态无 `auto_*`/合并/排序/扩范围函数、无 `execute_all/apply_all`、core 不 import DB/进程、运行期冲突不修改 proposal、未实现 action 仍 `UNSUPPORTED_ACTION` |

### 4.3 受影响套件（全部 rc=0）

| 套件 | 结果 |
| --- | --- |
| `tests/execution_reliability_test.py`（新） | **75/75** |
| `tests/execution_truth_test.py`（M4 回归，未改） | 45/45 |
| `tests/maintenance_fixes_test.py` | 30/30 |
| `tests/dq_truth_test.py` | 122/122 |
| `tests/revision_truth_test.py` | 61/61 |
| `tests/review_truth_test.py` | 47/47 |
| `tests/direction_test.py` | 25/25 |
| `tests/integrity_gates_test.py` | 45/45 |
| `tests/integrity_truth_test.py` | 243/243 |
| `tests/narration_contract_test.py` | 45/45 |
| M8e 负对照（M4 脚本，样本扩至 10） | **10/10 检出、0 误报** |

---

## 5. 完整回归

### 5.1 step2（`3a_regression_batch`）逐项执行

| 项 | 值 |
| --- | --- |
| 执行器 | `docs/regression_2x/phase6b_m5_batch_items.py`（argv/ITEMS 由 **AST 解析同一份** `phase3a_regression_batch.py`，逐项落盘可 `--resume`） |
| 结果 | **24 项 | 符合预期 24/24 | 非预期 [] | 等价 step rc = 0** |
| 单轮实际耗时 | 首轮 24 项连跑 **1963.2 s**；重跑后汇总 `seconds_total_all_items = 2007.3 s` |
| 逐项日志 | `logs/phase3a_<name>.log`；汇总 `logs/phase6b_m5_batch_items.json` |
| 外部步骤记录 | `logs/phase6b_m5_external_steps.json`（`executed_by`/`evidence`/`rc`/`environment_pending={}`/`retried_items`，未伪造） |

> **诚实披露（唯一一次非预期）**：首轮连跑中 `phase2e_real_provider`（依赖真实外部 provider）失败
> （rc=1，7.8 s，`external_configured_no_candidate`）；随后**单独重跑通过**（rc=0，76.9 s，R11 真实 provider 上屏证据成立），
> 再以 `--resume` 汇总 24 项。原始 rc 与处理过程在 `phase6b_m5_batch_items.json`、`phase3a_phase2e_real_provider.log`
> 与外部步骤记录中均可复核；**未**改写任何历史记录、**未**把失败算作通过。

### 5.2 电池（25 步）

- **25 步全部 rc=0**；`all_rc_zero_raw = True`；`rc_nonzero = []`；`rc_pending = []`。
- 各步 `seconds` 之和 **4140.4 s**；step2 由外部执行器完成（2007.3 s）并在汇总中单列 `executed=externally`。
- 冻结日志：快照 **2486 文件** → 运行中改变 18 / 新增 90 / 删除 0 ⇒ **回拷逐字节恢复 = True（drift 0）**。
- 首轮电池在回拷阶段因 Windows 文件占用（`WinError 32`）中断（**步骤已全部完成、rc 全 0**），
  随后以 `--resume` 完成回拷与汇总（步骤全部跳过，`frozen_logs_restored=True`）。

| step | rc | s | step | rc | s | step | rc | s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 3a_real_chain | 0 | 6.0 | 4g_evidence | 0 | 0.4 | 5c_failclosed | 0 | 5.3 |
| **3a_regression_batch** | 0 | 2007.3（外部） | 4x_audit | 0 | 2.5 | 5c_checkpoint_check | 0 | 1.0 |
| 3b_audit | 0 | 8.0 | 5a_evidence | 0 | 47.6 | 5d_mm_temporal_test | 0 | 94.3 |
| 3b_failure_paths | 0 | 23.0 | 5b_evidence | 0 | 44.0 | 5d_frozen_check | 0 | 0.6 |
| 4ab_evidence | 0 | 193.4 | 5c_append_only | 0 | 0.1 | 5e_mm_quality_test | 0 | 321.3 |
| 4c_evidence | 0 | 1.6 | 5c_db_append_only | 0 | 1.9 | 5e_calibration | 0 | 162.2 |
| 4d_evidence | 0 | 1.2 | 5c_verify_film | 0 | 3.8 | 5f_mm_judge_test | 0 | 162.4 |
| 4e_ab_benchmark | 0 | 0.1 | 4f_evidence | 0 | 14.0 | 5f_judge | 0 | 0.1 |
|  |  |  |  |  |  | **unit_suites** | **0** | **1038.3** |

### 5.3 step25 `unit_suites`：**58 个套件全部 rc=0**

（M4 期 57 → M5 新增 `tests/execution_reliability_test.py` ⇒ 58；两组 M5 相关套件
`execution_reliability_test`（75/75）与 `execution_truth_test`（45/45）均 rc=0。）失败套件：**无**。

---

## 6. baseline / DB / output 完整性证明

### 6.1 基线未被改写（4/4）

| 基线 tag | ZIP sha == manifest | 文件数 |
| --- | --- | --- |
| `5.x-post-final-maintenance-baseline` (r1) | **True** | 385 |
| `5.x-post-final-maintenance-baseline-r2` | **True** | 387 |
| `5.x-post-final-maintenance-baseline-r3` | **True** | 389 |
| `5.x-final-baseline` | **True**（sha `be1717b9c7fe9ed9…` 未变） | 384 |

本轮**未新增基线、未新增 tag**（`baseline/` 内 ZIP 清单与 M4 期一致）。

### 6.2 DB / 母版 / 项目文件 / 产物位置

| 项 | 证据 |
| --- | --- |
| DB 字节 | `db_sha256_before == db_sha256_after`（`read_only_evidence.db_unchanged = true`；闭环仅以 `mode=ro` + `query_only` 读取） |
| v9 母版成片 | sha256 `22705c7d7ea20b40…` / 46,761,341 B —— 执行前后**逐字节未变**（T4m 与冻结记录一致） |
| v9 output 目录 | `v9_output_dir_unchanged = true`（文件清单 + mtime 快照比对） |
| 被触碰的项目文件 | `project_files_touched = []` |
| 执行产物位置 | 仅在 `output/phase6b_m4_sandbox/p_96efdc03e1aa_m5/output/`（`sandbox_only_outputs = true`，路径反斜杠已规范化） |
| 沙箱内容 | `m5_inputs`（构造用例输入）、`p_96efdc03e1aa_h7outro`（M4 证据）、`p_96efdc03e1aa_m5`（M5：母版复制品 46,761,341 B + 两条真实产物 48,591,819 / 53,815,260 B） |

### 6.3 守卫（24 项）与工作树

- 守卫项漂移：**仅** `src/video_studio/agents/editing/agent.py`（6-A/M2 授权的 PI 门禁接线；M5 **未**再改该文件）；
  `unexpected_guard_drift = []`。
- 工作树相对 r3 漂移 6 个文件：`agents/editing/agent.py`、`cli.py`、`tests/bgm_ducking_test.py`、
  `tests/maintenance_fixes_test.py`、`tests/narration_contract_test.py`、`tests/pipeline_mock.py`；**缺失 0**。
- 本轮新增模块仍受 **M8e**（授权写入型 ops 白名单 + AST 沙箱污点证明 + 无绕过入口）与
  **T4a-2/T4a-3**（生产链不可达 + DQ 只读 advisory）约束：`maintenance_fixes_test` 30/30、`dq_truth_test` 122/122。

### 6.4 代码指纹链

| 阶段 | 文件数 | aggregate sha256(前 16) |
| --- | --- | --- |
| 6-A/M1 | 395 | `da1be48c58bc7cb9` |
| 6-A/M2 | 396 | `f15027be4f7cd8e4` |
| 6-A/M3 | 400 | `9cd07d694a5e0033` |
| 6-B/M1 | 400 | `9cd07d694a5e0033` |
| 6-B/M2 | 404 | `14945b55410aabe9` |
| 6-B/M3 | 408 | `d36ec4d89cadb584` |
| 6-B/M4 | 412 | `2aa5fd46f5e13663` |
| **6-B/M5** | **414** | **`d639f3147cc0f6e2`** |

6-B/M5 增量：**变化 3**（`core/execution.py`、`ops/execution.py`、`tests/maintenance_fixes_test.py`）、
**新增 2**（`tests/execution_reliability_test.py`、`tests/fixtures/execution_reliability_truth_v1.json`）、
**删除 0**。（`docs/regression_2x/**` 证据脚本与报告不在指纹口径内。）

### 6.5 PI / DQ 未被改动（可核验）

- `EXECUTION_STATES` / `POLICY` 逐字未变（M5 只**扩展** `ALL_EXECUTION_STATES`，T0e 断言 M4 真值集
  `execution_states` 与代码逐字一致）。
- `core/integrity.py`（PI-1…PI-6 定义/阈值）与 `core/direction.py`（DQ-1…DQ-8）**未出现在本轮指纹增量**中
  ⇒ 未被修改；`core/materials.py` 亦未改动（阈值 0.30 / 0.15 由 `DEFAULT_POLICY` 读取）。
- DQ 仍 `advisory=True / enforced=False`，且**未**接入 `TASK_BLOCKED`（`dq_truth_test` 122/122 覆盖静态与运行期）。

---

## 7. 已知剩余边界

1. **跨进程无锁**：串行化只在**同进程**内由调用方传入的锁保证；跨进程/跨机器并发**未**做文件锁或 DB 事务
   ⇒ 跨进程同时提交同一方案仍存在"幂等判定—落账"竞态窗口（授权只要求进程内一致性与 fail-closed）。
2. **冲突判定以批次为单位**：`detect_conflicts` 的成立范围 = **同一次提交的可执行集合**；跨批次的同一方案由幂等门禁兜底。
   若人工分两批提交两条互相重叠的方案（各自都不与同批成员冲突），本层**不会**跨批发现重叠 ⇒ **已知边界**。
3. **"覆盖式缩放"是渲染选择**：素材段采用 `scale=increase,crop`（不留黑边）以便成片帧 ↔ 素材可做相关性核验；
   该选择会**裁边**改变原素材构图，已在证据中逐帧记录（`asset_evidence.samples`）。
4. **成功 ≠ 全片达标**：素材替换只影响窗口内画面；v9 的 PI 仍 `BLOCKED`、DQ-2 仍 `FAIL`（唯一素材 4/5 < 6）
   ⇒ 本层**不**提升、**不**绕过任何门禁。
5. **许可判定范围沿用冻结口径**：3-A 许可门禁只适用于**外部**素材；本地 ingest 素材的许可声明不由本层判定
   （与冻结基线一致，既不扩大也不缩小）。
6. **构造用例不冒充真实素材**：5 条构造用例（sha 不符 / 缺文件 / 不可解码 / 许可受限 / 未清）在证据里显式标注
   `constructed=true` 且**不计入**"可用素材"统计（真实可用素材 = 5 条）。
7. **沙箱沿用 M4 根目录**：产物落在 `output/phase6b_m4_sandbox/p_96efdc03e1aa_m5/`（标签区分批次），
   未新建沙箱根（避免改动 M4 冻结的 `SANDBOX_ROOT_REL` 常量）；约 +95 MB 证据保留未清理。
8. **M5 台账重新生成过 3 次**：在补入 `dq_details`、修正沙箱路径判定（`sandbox_only_outputs` 反斜杠）后各重生成；
   台账的 append-only 语义由哈希链校验（seq 连续 + prev/entry sha）与单测（三类篡改检出）证明，
   **而不是**靠"文件从未被重写"这类无证据主张。
9. **M4 证据被扩充而非改写**：`phase6b_m4_m8e_negctl.py` 的负对照样本由 8 增至 10
   （新增 `Path.replace` 逃逸必须检出、`str.replace` 不得误报），JSON 证据已重跑（10/10 检出）；
   PHASE6B_M4_REPORT.md 中的 "8/8" 是 M4 时点记录，两者不冲突（原 8 个样本仍全部检出）。
10. **历史遗留未归零**：`5d_frozen_check` 漂移仍在（`rc=0`，既有 5-D 期检查口径），本轮未归零、未声称已修复；
    历史 18 条 interim `BLOCKED` 任务记录保持 append-only 原样。
11. **未新增人类审批 CLI**：审批入口仍是 `core.execution.make_approval` + 闭环脚本；`approved_by` 是**自陈**身份，
    **不是**密码学认证 ⇒ 本报告**不**声称"身份不可伪造"（沿用 M4 边界声明）。
12. **批次中被重跑的项**：`phase2e_real_provider`（依赖真实外部 provider）在首轮 24 项连跑中因
    `external_configured_no_candidate` 失败（7.8 s），随后单独重跑通过（76.9 s，R11 真实 provider 上屏证据成立）；
    批次最终以 `--resume` 汇总 24 项 —— 该处理过程与原始 rc 均在 `logs/phase6b_m5_batch_items.json` 与
    `logs/phase3a_phase2e_real_provider.log` 中可复核，**未**改写任何历史记录。
---

## 8. 结论

### 8.1 授权要求逐条对照

| 要求 | 状态 | 证据 |
| --- | --- | --- |
| 用真实存在、已验证的素材完成 **≥1 条** APPROVE→EXECUTION→PI/DQ recheck 闭环 | **满足（2 条）** | A1（0.9982）/ D1（0.7639）`replaced=True`；PI 强制重跑 + DQ 只读复核 |
| 无素材 / 素材失效 / 校验失败必须 `PENDING/FAILED`；禁止虚构或占位 | **满足** | A2/A4/A5 `FAILED`；A3/A6 `PENDING_HUMAN_ASSET`；5 条构造用例显式标注；无 `fallback_asset`/替代分支 |
| 涉及同一 scene / asset / window 必须检测 overlap/conflict | **满足** | 4 类规则 + 全对矩阵（M5 6 对 / M3 真实 10 对）+ 12 个 truth case |
| 冲突必须阻止执行或要求人工重新批准；禁止自动合并/排序/扩范围 | **满足** | 对称 `BLOCKED_CONFLICT` + `requires_human_reapproval=True` + `executor_invoked=False`；`auto_merge/auto_reorder/auto_scope_expansion=false`（写死 + 静态断言） |
| approval 继续绑定 `proposal_id + proposal_sha256` | **满足** | 10 条审批全部含绑定字段；批量路径下篡改用例仍 `BLOCKED_TAMPERED`（BT-7） |
| execution ledger/hash-chain 保持 append-only | **满足** | 两条独立链、`chain_ok=true`、seq 21 连续唯一、三类篡改检出（M4 T3 + 本轮并发链校验） |
| PI-1～PI-6 不修改、不降级 | **满足** | 指纹增量不含 `core/integrity.py`；M4 状态机/策略逐字未变；PI 仍可 `BLOCKED` |
| DQ 继续 advisory，不接入 `TASK_BLOCKED` | **满足** | `advisory=True/enforced=False`；DQ 仅用于执行后只读复核与内存推演（未写回） |
| 不修改 5.x Final / r1 / r2 / r3 | **满足** | 4 个 ZIP sha == manifest |
| 不覆盖 v9 母版 | **满足** | 母版 sha256 与 M1 记录一致；产物只在沙箱 |
| 不自动批准、不自动执行未批准 Proposal | **满足** | `auto_approved=false`、`executed_without_approval=[]`、H1 `BLOCKED_UNAPPROVED`；静态无 `auto_*`/`execute_all` |
| 不进入 6-C | **满足** | 本阶段只关闭两个 PENDING，报告到此为止 |

### 8.2 量化结论

- 新增/修改源码 **2** 个文件（+约 440 行，纯**新增**能力：`EXECUTION_STATES`/`POLICY` 逐字未改）；
  新增测试 **1** 个文件（75 项）+ 真值集 **1** 个（30 cases）。
- v9 真实执行：**21 条记录 / 3 批次**；`SUCCEEDED 2`（均带真实素材抽帧证据）、`FAILED 6`、
  `PENDING_HUMAN_ASSET 4`、`BLOCKED_CONFLICT 3`、`BLOCKED_UNAPPROVED 2`、`BLOCKED_REJECTED 2`、
  `BLOCKED_ALREADY_EXECUTED 2`。
- 单测：M5 **75/75**；受影响 10 个套件全部 rc=0；M8e 负对照 **10/10 检出、0 误报**。
- 完整回归：批次 **24/24**（step rc 0）；电池 **25/25 步 rc=0**；`unit_suites` **58/58 rc=0**；
  冻结日志 **2486 → 改 18 / 增 90 / 删 0 → 恢复 True（drift 0）**。

### 8.3 判定

> **6-B/M5（Execution Reliability Closure）= PASS。**
>
> 6-B/M4 的两个 PENDING **均已关闭**且各有可复现的真实证据：
> **P1** = 2 条真实素材 APPROVE→执行→强制 PI/DQ 复核闭环（含成片抽帧比对 `replaced=True`）+ 5 类校验失败的 fail-closed 证明；
> **P2** = 4 类重叠规则 + 全对矩阵 + 对称阻断 + 幂等 + 并发串行化 + 未批准/被拒不造成假阻断。
>
> §7 的 12 项边界**不**计入 PASS，其中"**跨进程并发无锁**"与"**跨批次重叠检测**"是明确的能力缺口（未做即未做）。
> 未把任何 PENDING/BLOCKED 改写成 PASS；v9 的 PI 仍 **BLOCKED**、DQ-2 仍 **FAIL**（唯一素材 5 < 6），
> 相关数值均如实记录。

**本阶段到此为止（STOP），不进入 6-C。** 等待下一阶段授权。
