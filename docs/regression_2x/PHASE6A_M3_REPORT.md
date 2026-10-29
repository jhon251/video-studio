# 6-A / M3 —— Production Integrity Truth Set & Regression Hardening

- 阶段：**6-A/M3**（建立 PI-1…PI-6 冻结真值集 + 门禁回归证据；**不做** 6-B/6-C、不做 DQ 自动硬化、不做任何自动修复）
- 前置：6-A 审计 → 6-A/M1 只读度量层 → **6-A/M2 硬门接线**（`PHASE6A_M2_REPORT.md`）
- 本轮**不**动：5.x Final 与 r1/r2/r3 基线、历史 Judge / truth set（M1 v1）/ threshold / multimodal evaluator、
  DQ 判定逻辑；**不重渲染**、不新建 baseline/tag。
- 证据：`docs/regression_2x/logs/phase6a_m3_*.json`；真值集：`tests/fixtures/production_integrity_truth_v2.json`；
  套件：`tests/integrity_truth_test.py`。

---

## 1. 变更清单

### 1.1 源码（行为影响逐项说明）

| 文件 | 变更 | 影响 |
|---|---|---|
| `src/video_studio/core/integrity.py` | `summarize()` **汇总口径收紧** | 只要集合中含 `NOT_ASSESSABLE`（此前仅在"全部为 NA"时才不给 PASS），overall 不再折算为 PASS：`FAIL > UNKNOWN > NOT_ASSESSABLE > PASS`。**只影响汇总报告**，不参与门禁阻断（门禁逐 PI 判定） |
| `src/video_studio/agents/editing/agent.py` | 产物证据新增 `production_integrity.effective_flags` 与 `post_render.disabled` | 纯**审计字段**（加法）；门禁判定逻辑一行未改，渲染行为不变 |

`summarize()` 收紧的动机（M3 自查发现）：M1 模块契约写着"`UNKNOWN` 与 `NOT_ASSESSABLE` 绝不等同 `PASS`"，
但旧实现在"部分 PASS + 部分 NOT_ASSESSABLE"时会给 overall=PASS（例如计划模式下 PI-5=N/A）。
M3 的真值集把这一点固化为可回归的行为：新用例 `M3-S-MIXED-PASS-NOT-ASSESSABLE`（PASS+NA ⇒ NOT_ASSESSABLE）。
既有断言不受影响：M1 `integrity_test` 的 I7（单 NA ⇒ NA、全 PASS ⇒ PASS、含 FAIL ⇒ FAIL）与 M2 `integrity_gates_test` G7e 全部保持通过。

### 1.2 测试与夹具

| 文件 | 变更 |
|---|---|
| `tests/fixtures/production_integrity_truth_v2.json` | **新增**：M3 冻结真值集（58 用例；含覆盖矩阵、门禁语义、不可达状态声明、边界说明、`frozen_sha256` 自锚点） |
| `tests/integrity_truth_test.py` | **新增**：M3 回归套件（**243/243**），覆盖 T0 冻结校验 → T7 端到端门禁语义 |
| `tests/fixtures/production_integrity_truth_v1.json` | **未改**（sha256 `c4ea00273737a544…`，与冻结记录一致；M1 证据保持原样） |

### 1.3 回归/取证脚本（新增，M3 专用路径，不覆盖 M1/M2 证据）

`phase6a_m3_build_truth.py`（冻结 + 覆盖矩阵）、`phase6a_m3_precheck.py`（53 套件预检）、
`phase6a_m3_battery.py`（25 步电池，独立备份 `/logs_6a_m3_frozen/`）、`phase6a_m3_guard_check.py`、
`phase6a_m3_final_check.py`、`PHASE6A_M3_REPORT.md`（本报告）。

**未改动**：`config/config.json`、`config/config.mock.json`、`core/direction.py`（DQ）、`ops/*`、
全部 `mm_*` 与冻结真值集、M1/M2 的历史证据文件。

---

## 2. Truth set 覆盖矩阵

真值集 `production_integrity_truth_v2.json`：**58 用例**，规范化 sha256 `2fa4a1a2229c70b4…`
（文件 sha256 `5a2ac9f5a35fa2c8…`，两者均写入 `logs/phase6a_m3_truth_freeze.json`）。

| PI | PASS | FAIL | UNKNOWN | NOT_ASSESSABLE |
|---|---|---|---|---|
| PI-1 覆盖率 | 边界 0.90 恰好 / 完整旁白闸门 | 0.8999 / 短旁白闸门 | **不可达（源码无此路径）** | 缺旁白时长（含 fail-closed 闸门） |
| PI-2 双侧契约 | 短差恰好 30 s / 完整旁白闸门 | 短差 31 s / 占比 25% | **不可达** | 缺时长输入（含 fail-closed 闸门） |
| PI-3 成片静音 | 无静音 / 2 s 短隙 | 尾部 8 s / 片中 12 s | 无 ffmpeg 路径 | 成片不存在 |
| PI-4 AV 轨道 | 轨差恰好 1.0 s / ±1 帧报数（仅报告） | 轨差 1.05 s / 缺音轨 / 真实错位片 | 轨道时长不可读 | 无轨道探测结果 |
| PI-5 字幕 orphan | orphan 恰好 0.02 / cue.start == 旁白结束 | orphan 0.03 / 覆盖比越界 / orphan 闸门 | **不可达** | 无 cue / 旁白结束未知 / 计划模式 |
| PI-6 边界漂移 | 漂移恰好 5.0 s | 漂移 5.1 s / **仅漂移即阻断** | 缺逐段时长 / 段数不符 / **全库历史产物** | 无脚本段落 |

- 矩阵 **24 格：已填 21，按设计不可达 3**（PI-1/PI-2/PI-5 的 UNKNOWN —— 源码里缺数据一律返回 `NOT_ASSESSABLE`）。
  M3 **不伪造**这些状态；不可达声明由 `state_reachability` 固化并由套件 T0f/T2 校验。
- 授权书点名的 8 类异常全部覆盖：正常完整旁白、短旁白、尾部静音、中央静音、字幕 orphan、
  AV 轨道异常、segment drift、缺失数据（`M3-PI3-MISSING-FILM`/`M3-PI1-MISSING-NARRATION`/…）。
- 边界覆盖要点：PI-1 恰好 0.90、PI-2 恰好 30 s 与占比超标两条、PI-4 恰好 1.0 s 与 ±1 帧报数、
  PI-5 恰好 0.02 与 `cue.start == narration_end`、PI-6 恰好 5.0 s。
- **诚实的边界缺口**：PI-3 的阈值**等式**（最长恰好 8.000 s / 占比恰好 0.100 / 尾部恰好 5.000 s）
  无法在媒体层确定性分离（silencedetect 采样级抖动 ±0.02 s），故 PI-3 用两侧有余量的媒体用例
  （2 s PASS / 12 s FAIL）＋冻结阈值断言覆盖，真值集内明确记录该口径，不伪造"恰好等于"的媒体期望。

---

## 3. 测试与回归结果

### 3.1 M3 套件（`tests/integrity_truth_test.py`）

| 组 | 内容 | 结果 |
|---|---|---|
| T0 | 冻结校验：schema/阶段、规范化 sha256 自锚点、M1 v1 sha256、策略与开关快照 == 代码默认值、状态可达性 | PASS |
| T1 | 58 个用例的**逐案行为断言**（度量状态 + 字段值 + 门禁 blocked/disabled/reasons） | PASS |
| T2 | 覆盖矩阵逐格核对（用实测状态验证矩阵声明；不可达格必须为空） | PASS |
| T3 | `UNKNOWN/NOT_ASSESSABLE ≠ PASS`：summarize 穷举（含混合态）＋每个 PI 的不可证处置 | PASS |
| T4 | **真实 v9 固定 FAIL 反例**（只读） | PASS |
| T5 | 全库历史产物缺 `segment_details` ⇒ PI-6 **恒 UNKNOWN** | PASS |
| T6 | gate bypass 审计与默认开启（含生产配置无静默关闭） | PASS |
| T7 | **端到端门禁语义**（编辑 agent 真实渲染 7 例 + 1 例正常交付复核） | PASS |

**合计 243/243 通过，rc=0，SKIP=0**（34.5 s）。

### 3.2 全套件预检（`logs/phase6a_m3_precheck.json`）

**53 个套件 → 53 rc=0，failed = []**（新增 `integrity_truth_test` 后由 52 → 53）。

### 3.3 25 步回归电池（`phase6a_m3_battery.py` + 逐项执行器）

| 指标 | 结果 |
|---|---|
| 步骤 | **25/25 全部完成**（`rc_pending = []`）；其中 24 步由电池执行、**1 步（`3a_regression_batch`）外部逐项执行** |
| 非零 rc | `['3a_regression_batch']`（其等价 rc=1；唯一原因是环境性的 `phase2e_real_provider`，见 §3.4） |
| 各步耗时之和 | 4131.1 s |
| step25 `unit_suites` | **53 套件全部 rc=0**（`FAILED: []`） |
| step2 批次（逐项执行） | **24 项：符合预期 23 / 非预期 1**；非预期项 = `phase2e_real_provider`（`needs_network=True`） |
| 冻结日志（708 文件） | 运行中改变 0 / 新增 1（本轮新增的 `phase6a_m3_external_steps.json`）/ 删除 0 → **回拷逐字节恢复 = True** |
| step1 `3a_real_chain` | VERDICT: PASS（PASS=16 / FAIL=0），成片 104.0 s == 时间轴 |
| step4f `phase4f_evidence` | BGM 渲染 SUCCEEDED、旁白 COMPLETE、响度 ok=True（M2 的夹具修复保持有效） |

**执行方式的环境约束（如实披露，非放宽）**：本环境**前台单次调用上限 10 分钟**，后台作业会被环境在约 13 分钟内杀死；
标准 `phase3a_regression_batch.py` 需连续约 34 分钟，被杀时**不写汇总**。故本轮 step2 改由
`phase6a_m3_batch_items.py` 逐项执行：**ITEMS 与 argv 从标准脚本 AST 解析得到（完全一致）**，
step rc 口径与标准脚本一致（`0 if not unexpected else 1`），逐项 rc/耗时/tail 记录于
`logs/phase6a_m3_batch_items.json`；电池以 `--skip 3a_regression_batch` 引用该外部记录
（汇总中标 `executed=externally`、`rc` 取自外部记录，**未伪造**）。
电池自身支持 `--resume`（沿用**首次**启动时的冻结快照，不重复备份）以便在环境杀进程后续跑；
本轮因此出现过 3 次续跑，最终 25 步齐备且冻结日志 drift 0（`phase6a_m3_regression_summary.json`）。

### 3.4 基线完整性与指纹

| 基线 | 文件数 | zip == manifest |
|---|---|---|
| `5.x-post-final-maintenance-baseline`（r1） | 385 | **True** |
| `5.x-post-final-maintenance-baseline-r2` | 387 | **True** |
| `5.x-post-final-maintenance-baseline-r3` | 389 | **True**（r3 未被覆盖） |
| `5.x-final-baseline` | 384 | **True**（sha256 仍 `be1717b9c7fe9ed9…`） |

- **守卫 24 项**：漂移仅 `src/video_studio/agents/editing/agent.py`（M2 接线 + M3 审计字段，均授权）；
  **未授权漂移 = 无**；工作树相对 r3 漂移仍是 M1/M2 那 6 个文件（M3 **没有**新增基线成员文件被改）；缺失 = 0。
- **代码指纹**：M1 `395` `da1be48c58bc7cb9…` → M2 `396` `f15027be4f7cd8e4…` → **M3 `398` `e938e3aaec8ffc67…`**；
  M3 增量 = **changed 2 / added 2 / removed 0**：
  改 `core/integrity.py`（`summarize` 收紧）、`agents/editing/agent.py`（审计字段）；
  增 `tests/fixtures/production_integrity_truth_v2.json`、`tests/integrity_truth_test.py`。
- **真实 v9 母版未被改写**：sha256 `22705c7d7ea20b40…`、46,761,341 B（与 M1/M2 记录一致，未重渲染）。
- **环境 PENDING（单独分列，不计入 M3 能力判定）**：
  `phase2e_real_provider` rc=1（28.8 s）——`provider_wikimedia.py::_request` 抛异常（真实网络依赖项，`needs_network=True`）；
  同一项在 M2 电池中曾 rc=0（201.6 s），属**环境波动**，不是 M3 代码问题；
  批次其余 23 项（含 `cost_boundary`、`phase2e_failure_paths`、`phase2d_provider_e2e`）本轮均 rc=0。

---

## 4. M3 重点检查项逐条回答

### 4.1 truth set 是否覆盖 PI-1～PI-6 的边界？

覆盖：见 §2 矩阵。四态中**可达的每一格都有至少 1 个用例**；不可达 3 格明确声明（并由 T0f/T2 校验），
另含各 PI 的阈值等式边界（PI-1 0.90、PI-2 30 s、PI-4 1.0 s、PI-5 0.02、PI-6 5.0 s）与
"恰好等于算不算违约"的判定（`>` 语义：恰好等于 ⇒ PASS）。
唯一无法媒体化的是 PI-3 的等式边界，已在真值集内如实声明（§2 末）。

### 4.2 PI-6 在大量历史产物缺 `segment_details` 时是否始终保持 UNKNOWN？

是。T5 用**门禁实际会读到的输入**（`voice.segment_details` → 空列表）对全库真实 `voice_output`
逐一抽样（只读）：**实测样本 574 个**（要求 ≥ 100），其中缺脚本产物 0 个；
结论 **全部 UNKNOWN，0 个 PASS、0 个 FAIL**（套件日志 `suite_integrity_truth_test.log`）。
同时验证"缺逐段时长不削弱旁白完整性把关"（PI-1 仍用**实测**旁白时长独立 fail-closed）。
默认策略下 PI-6 的 UNKNOWN **不阻断**（避免误伤旁白完整、时长达标的成片），
但状态如实记为 UNKNOWN（绝不 PASS），且可显式收紧（`block_on_unknown_pi6=true`，用例
`M3-G-PRE-PI6-UNKNOWN-STRICT-OVERRIDE` 证明收紧后即阻断）。

### 4.3 gate bypass 是否可审计且不会被默认路径静默启用？

- **默认全开**：`gate_policy(None)` 与**生产配置**（`config.json` / `config.mock.json`）下
  `gate_enabled`/`post_render_enabled` 均为 true；两配置文件里**不存在** `gates.integrity.enabled=false`
  （T6b 逐文件核对 ⇒ 不存在"默认路径静默关闭"）。
- **旁路必须留痕**：显式关闭时，gate 报告带 `disabled=True` 与明确原因
  （`gate disabled by policy` / `post-render gate disabled by policy`，T6e/T6f）；
  产物证据里新增 `effective_flags`（四个开关的实际取值）与 `pre_render.disabled`/`post_render.disabled`
  （T7 端到端：显式关闭后任务确实放行，但产物里能查到"哪个门被关"）。
- **纵深防线**（本轮发现并固化为用例 `M3-E2E-PRE-DISABLED-STILL-BLOCKED`）：
  只关渲染前硬门**并不能**交付短旁白成片 —— 短旁白必然在成片上留下 >10% 的尾静音，
  渲染后的 PI-3 仍会以 `[PRODUCTION_INTEGRITY_FAILED]` 阻断（实测）。
- 开关**未被移除**（M3 只增加审计字段与真值断言）：`M3-G-PRE-DISABLED-AUDIT` /
  `M3-G-POST-DISABLED-AUDIT` / `M3-E2E-GATE-DISABLED-AUDITED` / `M3-E2E-POST-GATE-DISABLED-AUDITED`。

### 4.4 M3 测试是否真正验证门禁语义，而不是只验证函数返回值？

是，三道相互独立的证据：
1. **门禁层**（T1 的 pre_gate/post_gate 用例）：断言"是否阻断"（`blocked`）、阻断原因、旁路留痕，
   而不只是 PI 状态字符串；且用**判据隔离**构造（例如 `M3-G-PRE-SEGMENT-DRIFT-ONLY`：PI-1/PI-2 全 PASS、
   仅 PI-6 越界 ⇒ 仍阻断；`M3-PI5-ORPHAN-GATE`：显示覆盖比在区间内、仅 orphan 触发）。
2. **端到端层**（T7）：真实编辑 agent 渲染路径 —— 正常片照常登记 `render_output` 且交付 mp4；
   短旁白**零 artifact、零 mp4**；仅 PI-3 违约片**不登记 render_output/attribution**；
   旁路放行必须在产物里留痕；并验证"关前置门仍被后置门拦下"的纵深防线。
3. **真实数据层**（T4/T5）：真实 v9 成片 + 全库真实历史产物（只读）—— 不是合成假设。

---

## 5. 已知边界与结论

### 5.1 已知边界（如实列出）

1. **PI-3 等式边界不可媒体化**（silencedetect 采样级抖动）；已用两侧余量用例 + 冻结阈值覆盖，不伪造等式期望。
2. **PI-1/PI-2/PI-5 无 UNKNOWN 路径**：缺数据一律 `NOT_ASSESSABLE`；矩阵对应格声明为设计不可达。
3. **PI-6 的 UNKNOWN 默认不阻断**（可配置收紧）：理由是历史产物大量缺 `segment_details`（T5），
   据此阻断会误伤旁白完整、时长达标的成片；旁白完整性仍由 PI-1/PI-2 fail-closed 把关。
4. **PI-5 显示覆盖比**为度量报告项（非阻断判据）；硬门判据是授权点名的 **orphan**。
5. **`summarize()` 收紧**是 M3 的语义硬化（PASS 仅当全部 PASS）；它只影响汇总报告口径，
   `run.py integrity` 只读报告的 `summary.overall` 在"混合 PASS+NA"场景会由 PASS 变为 NOT_ASSESSABLE。
   M1/M2 的既有断言与冻结证据不受影响（已复跑验证）。
6. **gate 开关存在**（`gate_enabled` / `post_render_enabled`，默认 true）：M3 不移除，只保证"关闭必须留痕"。
7. **v9 仍是 FAIL**（未修正、未重渲染）：M3 只把它固化为**固定 FAIL 反例**（含成片 sha256 与字节数锚点）。
8. **M2 期间的历史阻断记录（18 条）保留不改**（append-only）；其中 5 条属旧 PI-6 口径，见 M2 报告 §8.4。
9. **step2 的执行方式偏离标准脚本**（逐项执行 + `--skip` 引用外部记录）：原因是本环境前台单次调用上限 10 分钟、
   后台作业约 13 分钟被环境杀死，而标准脚本需连续约 34 分钟。**argv/ITEMS/rc 口径完全一致**，
   逐项证据落盘；电池汇总中标明 `executed=externally`，未把外部结果伪造成电池自身执行。
10. **环境 PENDING 项**：`phase2e_real_provider`（真实网络）本轮 rc=1，同一项在 M2 运行中曾 rc=0 ⇒ 环境波动；
    按授权要求**单独分列**，不计入 M3 能力判定。

### 5.2 结论

- PI-1…PI-6 的**冻结真值集（58 用例 / 24 格矩阵）**已建立并自锚定 sha256；覆盖四态、阈值边界、
  授权书点名的 8 类异常与"不可达状态"的诚实声明。
- **UNKNOWN 永远不能成为 PASS**：在度量层（逐 PI）、汇总层（summarize，含混合态穷举）与门禁层
  （fail-closed 处置）三处都有行为断言。
- **门禁语义**（含 bypass 审计与纵深防线）已成为可长期回归的用例，而不是一次性的手工检查。
- **DQ 判定逻辑未被修改**；5.x Final / r1 / r2 / r3 未被触碰；未重渲染、未自动修复、未新建 tag。
- **STOP**：本轮只做 M3，等待下一步授权。
