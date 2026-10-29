# 6-B / M2 —— Human Review Bridge

- 阶段：**6-B/M2**（把 DQ-1…DQ-8 的只读 findings 转化为**可审计的人类审片决策**；**本阶段禁止自动执行任何修改**）
- 前置：6-B/M1（DQ 只读度量 + 真值集 + v9 只读审计：7 项人审发现 6 FULL + 1 PARTIAL）
- 本轮**只读 + append-only**：不重渲染、不换素材、不剪辑、不改字幕/旁白、不自动修复；
  DQ 仍 advisory/read-only，**不接入 `TASK_BLOCKED`**；**PI-1～PI-6 一行未改**；
  不改 5.x Final / r1 / r2 / r3；不新建 baseline/tag。
- 证据：`docs/regression_2x/logs/phase6b_m2_*.json{,l}`；真值集：`tests/fixtures/human_review_truth_v1.json`；
  套件：`tests/review_truth_test.py`。

---

## 1. 变更清单

| 文件 | 变更 | 影响 |
|---|---|---|
| `src/video_studio/core/human_review.py` | **新增**：finding 展开（确定性 finding_id、scene/asset/window/原始证据/provenance）、决策构造与校验、**append-only 哈希链台账**、闭环汇总（含零执行字段） | 纯只读/台账；不写 DB、不写产物、不碰成片 |
| `src/video_studio/ops/review.py` | **新增**：只读编排（读 DQ 报告 + 读台账 → 闭环报告；`write_report` 仅在显式 `--out` 时写报告文件） | `mode=ro` 读库；`executed_actions` 恒为空 |
| `src/video_studio/cli.py` | 新增只读子命令 `dq-review`（含 `--decide/--decision/--reason/--by/--provenance` 追加台账） | 归入既有的"只读/仅记录人工决定"路径（不走 `build_engine`） |
| `tests/maintenance_fixes_test.py` | 测试契约更新：`READONLY_OPS_WHITELIST` 纳入 `ops/review.py`（仍做 AST 只读静态检查） | 守卫**强度不变**（白名单外新增 ops/ 模块一律 FAIL） |
| `tests/dq_truth_test.py` | 测试契约更新：T4a 允许 `ops/review.py` **读取** DQ 报告（注释说明其只读性质） | 25/25、120/120 保持通过 |
| `tests/fixtures/human_review_truth_v1.json` | **新增**：闭环冻结真值集（决策词汇/语义、必需字段、UNKNOWN 策略、零执行契约、台账篡改用例、v9 闭环期望） | 规范化 sha256 见 §4 |
| `tests/review_truth_test.py` | **新增**：闭环回归（**47/47**） | T0 冻结 → T5 零执行证明 |
| `docs/regression_2x/phase6b_m2_*.py` + `PHASE6B_M2_REPORT.md` | 新增：真值冻结、v9 闭环、逐项批次执行器、可续跑电池、守卫/收尾核对、本报告 | 专用证据路径，不覆盖 M1/M2/M3/6-B-M1 证据 |

**未改动**：`config/*`、`core/integrity.py`（PI 门禁）、`agents/**`（经 AST 复核：无任何 agent import review 桥）、
`core/direction.py`（DQ 度量本轮未改）、全部 `mm_*` 与既有真值集。

---

## 2. Review schema（finding → decision 闭环契约）

**Finding（review item）** —— 由 DQ 指标展开，字段：

| 字段 | 说明 |
|---|---|
| `finding_id` | 确定性 ID：`hr-<sha256(project\|metric\|kind\|scene\|asset\|window\|discriminator)[:12]>`（同一 finding 任何时候复算一致） |
| `project_id` / `film_task` | 归属项目与渲染任务 |
| `origin` | `dq_finding`（DQ 派生）或 `human_audit`（人工审计记录） |
| `metric` / `kind` | 指标（DQ-1…DQ-8，人工审计项可为 null）与 finding 类型 |
| `severity` | 该 finding 对应的状态（PASS/FAIL/UNKNOWN/NOT_ASSESSABLE/HUMAN_RECORDED） |
| `unprovable` | 是否为**不可证**状态（UNKNOWN / NOT_ASSESSABLE） |
| `scene_id` / `asset_id` / `window` | **可定位锚点**（镜头、素材、时间区间） |
| `payload` | 原始 finding 原文（含全部子项，如逐镜 MISMATCH 列表） |
| `source_evidence` / `provenance` | 原始证据引用（如 `audit_p96efdc_mm.json`）与派生来源 |
| `default_routing` / `default_routing_policy` | 不可证项默认路由 = `DEFER` / `policy:unknown_requires_human` |

**Decision（决策记录）** —— 字段：`finding_id, project_id, film_task, metric, kind, severity,
unprovable, scene_id, asset_id, window, original_evidence, decision, decision_semantics, reason,
decided_by, decided_at, provenance, covers[], executes_changes=False`，
外加台账链字段 `seq / prev_sha256 / entry_sha256`。

**决策词汇与语义**：

| 决策 | 语义 |
|---|---|
| `ACCEPT` | 人工确认该 finding **不成立或可接受**（不修改任何东西） |
| `REJECT` | 人工确认该 finding 成立且**建议需要修改**（**本阶段不执行修改**） |
| `DEFER` | 暂缓 / 需人工复核 / 待补证据（**UNKNOWN、NOT_ASSESSABLE 一律走此路径**） |

**硬规则（代码级）**：
1. 决策缺 `finding_id/decision/reason/decided_by/provenance` 任一 ⇒ 拒绝写入；
2. 对 `unprovable=True` 的 finding 写 `ACCEPT` ⇒ 抛 `UNKNOWN_CANNOT_BE_ACCEPTED`（**UNKNOWN 永不等于 PASS**）；
3. 台账 **append-only + 哈希链**：`seq` 连续、`prev_sha256` 链式、`entry_sha256` 覆盖全部字段；
   改条目 / 删中间条目 / 换序 **均被 `verify_chain` 检出**；改判只追加新版本，历史保留；
4. **零执行**：报告恒带 `executed_actions: []` 与 `executes_changes: False`；
   `REJECT` 的语义文本明示"建议需要修改（本阶段不执行修改）"；
5. 类级决策可用 `covers: [{metric, kind}]` **显式覆盖**同类实例 finding（`covered_by_decision` 可追溯），
   避免"实例 finding 被静默忽略"。

---

## 3. v9 决策证据（真实闭环；`logs/phase6b_m2_review_v9.json` + `..._ledger_v9.jsonl`）

**决策来源**（不发明、不推断）：`PHASE6A_AUDIT.md` §2/§3 的**人工核实结论**与
"人工判 v9 = FAIL（不得作为发布候选）"、`KNOWN_ISSUES.md #67`。

| 覆盖（M1 重新发现项） | finding（metric / kind） | 决策 | 依据（provenance） |
|---|---|---|---|
| **H1 Hook 错位** | DQ-1 / hook_layer_verdict | **REJECT** | 人工抽帧确认画面与"AI 证明"无关（6-A §2.1 + §3 行3） |
| H1 的不可证面 | DQ-1 / metric_state_unprovable（UNKNOWN） | **DEFER** | 只读证据全 UNKNOWN ⇒ 人工复核路径；不得视为 PASS |
| **H2 素材重复** | DQ-2 / unique_assets_below_min | **REJECT** | 21 镜仅 4 素材（6-A §2.2 + §3 行2） |
| **H3 静态保持** | DQ-3 / over_hold_share_exceeds（**类级**，覆盖 21 条实例） | **REJECT** | 21/21 镜 >25 s、均值 72.95 s（6-A §2.3） |
| **H4 密度** | DQ-4 / scene_changes_below_min | **REJECT** | 0.822 镜变/分钟（6-A §2.4） |
| **H5 语义支撑** | DQ-8 / semantic_mismatch_scenes | **REJECT** | Judge MISMATCH + DQ-8 逐镜复现 S05/S11/S18（6-A §2.5） |
| **H6 视觉高潮** | DQ-5 / distinct_assets_in_core_below_min | **REJECT** | 20 核心镜仅 4 素材（6-A §2.6 + §3 行4） |
| **H7 片尾** | DQ-6 / no_outro_keyword_in_tail | **REJECT** | 无 outro/结束卡（6-A §2.7 + §3 行5） |
| H7 的不可证面 | DQ-6 / metric_state_unprovable（UNKNOWN） | **DEFER** | 语义证据不足 ⇒ 人工复核 |
| 人工审计项① | human_audit / human_subtitle_wrapping_residual | **DEFER** | 6-A §3 行6（PARTIAL：已改善仍有残留） |
| 人工审计项② | human_audit / human_hitl_rationale_mismatch | **DEFER** | 6-A §4 表（HITL approve 理由与成片不一致） |
| **成片级** | —（film-level，不进 finding 台账） | **REJECT** | 人工判 v9 = FAIL（`KNOWN_ISSUES #67`） |

**闭环统计**：review item **40** 条（38 条 DQ 派生 + 2 条人工审计）｜决策 **11** 条
（**REJECT 7 / DEFER 4 / ACCEPT 0**）｜类级决策覆盖实例 finding **29** 条｜**未决 0**｜
孤儿决策 0｜无锚点 item 0｜UNKNOWN 被 ACCEPT **0**｜台账链**完整**｜`executed_actions = []`。

**说明**：**ACCEPT 计数为 0 是如实结果** —— 人审记录未支持任何一项被接受；ACCEPT 能力由真值集用例
`HR-C1` 验证（合成 finding，机械类 FAIL 项可被人工 ACCEPT）。

---

## 4. Truth set / regression 覆盖

- 真值集 `tests/fixtures/human_review_truth_v1.json`：规范化 sha256 `见 logs/phase6b_m2_truth_freeze.json`
  （文件内自锚点，改真值必须显式重冻结）。冻结内容：决策词汇/语义、必需字段、UNKNOWN 策略、
  零执行契约与禁用静态模式、**7 个决策构造用例**（含非法词、缺字段、UNKNOWN 上写 ACCEPT）、
  台账 3 类篡改用例、3 个汇总用例、**v9 闭环期望**（含 7 项 M1 发现必须覆盖、2 项人工审计记录）。
- 套件 `tests/review_truth_test.py` = **47/47 通过**：
  T0 冻结校验｜T1 决策合法性（含 `UNKNOWN_CANNOT_BE_ACCEPTED`）｜T2 append-only + 篡改检出（改/删/换序）｜
  T3 汇总不变量（UNKNOWN 只走 DEFER、类级覆盖、孤儿决策检出）｜T4 真实 v9 闭环（7 项全进 evidence、
  决策一一可追溯、ACCEPT=0、未决=0、链完整、零执行）｜T5 零执行证明（静态 AST + 运行期 DB/成片/目录零改动）。

---

## 5. 完整回归

| 项目 | 结果 |
|---|---|
| 闭环真值集回归 `tests/review_truth_test.py` | **47/47 rc=0，SKIP=0** |
| 受影响的既有套件 | `dq_truth_test` **120/120**、`direction_test` **25/25**、`maintenance_fixes_test` **28/28**（契约更新后）、`integrity_truth_test` **243/243**、`metrics_test` **18/18** |
| 25 步回归电池（`phase6b_m2_battery.py`） | **25/25 完成，`all_rc_zero_raw = True`，`rc_nonzero = []`，`rc_pending = []`** |
| step25 `unit_suites` | **55 套件全部 rc=0**（新增 `review_truth_test` 后 54 → 55） |
| step2 批次（逐项执行） | **24 项：符合预期 24 / 非预期 0**（本轮网络可用） |
| 各步耗时之和 | 4756.3 s（含环境杀进程后的 `--resume` 续跑） |
| 冻结日志（708 文件） | 运行中改变 170 / 新增 269 / 删除 0 → **回拷逐字节恢复 = True（drift 0）** |

**执行方式的环境约束（如实披露）**：前台单次调用上限 10 分钟、后台作业约 13 分钟被环境杀死，
标准 `3a_regression_batch.py` 需连续约 34 分钟 ⇒ step2 由 `phase6b_m2_batch_items.py` **逐项执行**
（ITEMS/argv 从标准脚本 AST 解析，完全一致；step rc 口径一致），电池以 `--skip 3a_regression_batch`
引用外部记录（`executed=externally`，**未伪造**）；电池 `--resume` 沿用首次的**真实**冻结快照。

---

## 6. 基线完整性与已知边界

### 6.1 基线完整性

| 基线 | 文件数 | zip == manifest |
|---|---|---|
| `5.x-post-final-maintenance-baseline`（r1） | 385 | **True** |
| `5.x-post-final-maintenance-baseline-r2` | 387 | **True** |
| `5.x-post-final-maintenance-baseline-r3` | 389 | **True**（r3 未被覆盖） |
| `5.x-final-baseline` | 384 | **True**（sha256 仍 `be1717b9c7fe9ed9…`） |

- **守卫 24 项**：漂移仅 `agents/editing/agent.py`（M2/M3 的既有授权变更，**本轮未再改它**）；
  **未授权漂移 = 无**；工作树相对 r3 漂移仍是既有 6 个文件，缺失 = 0。
- **代码指纹**：6-B/M1 `400` `9cd07d694a5e0033…` → **6-B/M2 `404` `14945b55410aabe9…`**；
  本轮增量 = **changed 3 / added 4 / removed 0**：
  改 `cli.py`（新增只读 `dq-review` 子命令）、`tests/maintenance_fixes_test.py`（ops 白名单纳入 review.py）、
  `tests/dq_truth_test.py`（T4a 允许只读读取 DQ 报告）；
  增 `core/human_review.py`、`ops/review.py`、`tests/fixtures/human_review_truth_v1.json`、`tests/review_truth_test.py`。
- **v9 母版未被改写**：sha256 `22705c7d7ea20b40…`、46,761,341 B（未重渲染）。
- **真实 DB / 成片 / 项目目录**：闭环构建与决策追加前后**逐字节一致**（§3 的 `read_only_evidence`）。

### 6.2 已知边界（如实列出）

1. **v9 的 ACCEPT 计数为 0**：人审记录未支持任何一项被接受 —— 这是如实结果，不是能力缺失；
   ACCEPT 能力由真值集用例 `HR-C1` 证明（合成 finding，机械类项可被人工 ACCEPT）。
2. **决策来源限于已记录的人审结论**（6-A 审计 §2/§3 + `KNOWN_ISSUES #67`）：本轮**不发明**人工意见；
   Hook（H1）的 DQ-1 侧仍是 UNKNOWN —— 决策 REJECT 的 provenance 明确指向"人工抽帧确认"，
   而非机械证据（机械层只能证明"无 MATCH"）。
3. **H3 采用类级决策 + 显式覆盖**：21 条 `hold_exceeds_max` 实例 finding 由 `over_hold_share_exceeds`
   的类级 REJECT 覆盖（`covered_by_decision` 可追溯），避免 21 条重复拍板；覆盖关系写入台账 `covers` 字段。
4. **UNKNOWN 保守性由代码保证**：对 `unprovable=True` 的 finding 写 ACCEPT 会抛
   `UNKNOWN_CANNOT_BE_ACCEPTED`；UNKNOWN/NOT_ASSESSABLE 默认路由为 DEFER。
5. **REJECT 仅为建议**：本阶段无任何执行路径（`executed_actions` 恒空、`executes_changes=False`），
   REJECT 不触发素材替换/剪辑/字幕或旁白变更，也不产生 redo 任务。
6. **两处测试契约更新**（强度不变）：`maintenance_fixes_test` 的只读 ops 白名单纳入 `ops/review.py`
   （白名单外新增 ops/ 模块仍一律 FAIL，且新模块同样通过 AST 只读静态检查）；
   `dq_truth_test` 的"无模块引用 DQ"白名单允许 `ops/review.py` **读取** DQ 报告（不执行任何修改）。
7. **台账 append-only 的语义**：改判（例如日后人工改变结论）会**追加新版本**，历史条目保留；
   当前有效决策取每条 finding 的**最后一条**记录（报告 `rows[].decision` 即当前值）。
8. **执行方式偏离标准电池 step2**（逐项 + `--skip` 外部记录），原因与本轮环境约束同 §5。
9. **未做的**：DQ 自动硬化、6-C、任何自动换素材/剪辑/重渲染、新 baseline/tag；
   也**未**扩大语义判定范围（需语义的项保持 UNKNOWN → DEFER）。

---

## 7. 结论与未授权项

- DQ-1…DQ-8 的只读 findings 已可转化为**可审计的人工决策**：finding ↔ decision 一一可追溯
  （finding_id、scene/asset/时间区间、原始证据、decision、reason、provenance 齐备）。
- **REJECT = "建议需要修改"**，不执行任何修改：`executed_actions` 恒为空、`executes_changes=False`，
  且运行期证明 DB / 成片 / 项目目录零改动。
- **UNKNOWN 始终保守**：一律 DEFER/人工复核，代码级禁止对不可证项写 ACCEPT。
- **台账 append-only**：哈希链 + 篡改检出；改判只追加历史。
- **v9 的 7 项人工问题全部进入 review evidence**，并逐条落地为 REJECT/DEFER（成片级 REJECT）。
- 未扩大语义判定范围（需语义的项保持 UNKNOWN → DEFER；DQ 阈值未改）。
- DQ 仍 advisory/read-only、不接入 TASK_BLOCKED；PI-1～PI-6 未改；未新建 baseline/tag。
- **STOP**：本轮只做 6-B/M2。
