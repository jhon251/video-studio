# 6-B/M4 报告 —— 人工批准的导演修订执行（Human-Approved Directorial Revision Execution）

- 阶段：**6-B/M4**（授权范围：12 条，见 §1）
- 上游输入：`logs/phase6b_m2_review_ledger_v9.jsonl`（11 条人工决策：REJECT 7 / DEFER 4 / ACCEPT 0）
  + `logs/phase6b_m3_proposal_register_v9.jsonl`（8 条修订方案，全部 `PROPOSED_AWAITING_HUMAN_APPROVAL`）
- 本阶段**不做**：自动批准、自动执行全部方案、全片重做、修改 PI-1…PI-6 定义/阈值、把 DQ 变成硬阻断、
  未经人工批准改动旁白/字幕/素材/时间轴/成片。
- 判据链：**执行后强制重跑 PI-1…PI-6**（复用 6-A/M2 冻结门禁）→ DQ-1…DQ-8 只读诊断（advisory）。

---

## 0. 结论速览

| 项 | 结论 |
| --- | --- |
| 审批层 | 存在且**只能人工记录**：`auto_approved` 恒 `false`（写死），无任何自动批准路径（静态 + 运行期双证） |
| 绑定关系 | 审批绑定 `proposal_id + proposal_sha256 + 人工身份 + 时间 + 理由 + 溯源`，8 个必需字段全部落地 |
| 只有 APPROVE 能执行 | v9 实测：8 条方案中 **2 条 APPROVE、1 条 REJECT、5 条未批准**；**仅 1 条真正执行成功** |
| 篡改防护 | 执行前重算 `proposal_sha256`：改内容 ⇒ `BLOCKED_TAMPERED`；绑错方案 ⇒ `BLOCKED_UNAPPROVED` |
| 失败fail-closed | 执行器异常/复核异常/缺复核 ⇒ 一律 `FAILED`，**不**换方案、**不**扩范围、**不**自动重试 |
| 新素材 | 无真实可验证素材 ⇒ `PENDING_HUMAN_ASSET`（不虚构 asset_id、不占位替换） |
| 局部化上限 | 沿用 M3：>6 镜或 >0.30 占比或 film_wide ⇒ 执行门禁处**再次** `BLOCKED_NOT_LOCAL` |
| PI 复核 | H7 执行后 PI-1/2/3/5/6 仍 FAIL、PI-4 PASS ⇒ `pi_gate_outcome=BLOCKED`（**未提升**） |
| DQ 复核 | DQ-6 由 FAIL → **PASS**（真实可测改善）；DQ-1 UNKNOWN、DQ-2/3/4/5/8 仍 FAIL（局部修改不改善全片问题） |
| 沙箱 | 执行全部发生在 `output/phase6b_m4_sandbox/`（输入=复制品）；v9 母版 / v9 output 目录 / DB **逐字节未变** |
| 台账 | 审批链 3 条、执行链 5 条，两条**独立** append-only hash chain，`chain_ok=true`；三类篡改均被检出 |
| 零自动化 | `executed_without_approval=[]`、`auto_approved=false`、`promoted=[]`、只执行 1/8 条 |
| 单测 | M4 新套件 **45/45**；受影响套件全部 rc=0（详见 §4） |
| 完整回归 | 批次 24/24 符合预期；电池 25 步 + unit_suites（详见 §5） |
| 基线 | r1/r2/r3/5.x-final **四个 ZIP 全部未被改写**（sha == manifest）；未新增标签/基线 |

---

## 1. 变更清单（本阶段授权范围内）

### 1.1 新增源码（执行层，**不在**生产判定链内）

| 文件 | 行数 | 作用 |
| --- | --- | --- |
| `src/video_studio/core/execution.py` | 296 | 审批记录/校验（`make_approval`/`verify_approval`）、局部化再校验（`verify_locality`）、执行门禁（`gate_execution`）、受控执行（`execute_proposal`，执行器由调用方**注入**）、两条 append-only hash-chain 台账、`summarize_executions` |
| `src/video_studio/ops/execution.py` | 227 | 沙箱准备（copy-on-write）、真实执行器 `exec_add_outro_card`（末段重编码 + drawtext 片尾卡 + 其余流复制拼接，时长不变）、`_pending_asset`（无真实素材 ⇒ 人工待处理）、`pi_recheck`（复用冻结 PI 度量 + M2 门禁 + DQ 只读复核） |

### 1.2 新增测试与真值集

| 文件 | 行数 | 作用 |
| --- | --- | --- |
| `tests/execution_truth_test.py` | 389 | 45 项：T0 真值冻结 / T1 门禁矩阵 8 例 / T2+T2b 执行器与 fail-closed 6 例+5 项记录完整性 / T3 双链与篡改 / T4 v9 真实执行 10 项 / T5 零自动化静态证明 5 项 |
| `tests/fixtures/revision_execution_truth_v1.json` | 249 | 真值集 `revision-execution-truth-v1`：必需字段、取值、状态机、冻结策略、8 门禁例、6 执行例、台账契约、素材守恒、PI 复核契约、v9 期望、边界声明；冻结锚 `dcb6bac24a0b6746756a5ba250368c7756f874eaa9f3f7e248c4bf33bbc84eba` |

### 1.3 守卫测试契约更新（**加强**，非放宽）

| 文件 | 变更 | 说明 |
| --- | --- | --- |
| `tests/maintenance_fixes_test.py` | 新增 `AUTHORIZED_WRITE_OPS` + 检查 **M8e**（30/30） | 执行模块**不是只读模块**，故**禁止**并入只读白名单；改为独立类别并施加**更强**约束：沙箱前缀必须 `output/`、**AST 污点传播**证明所有 `write_text/write_bytes/mkdir/rmtree/copy2` 目标均由 `box` 派生、无 DB 写、无 `execute_proposal/execute_all/apply_*/auto_*` 绕过入口、不 import agents、agents 也不可达该模块；另断言两个白名单**互斥** |
| `tests/dq_truth_test.py` | 白名单增加 `ops/execution.py` + 新增 **T4a-2/T4a-3**（122/122） | 执行层读取 DQ 仅用于**执行后只读复核**；T4a-2 证明 `agents/**` **不可达**执行层（DQ 不可能经执行层进入生产阻断判定），T4a-3 证明该模块 DQ 复核为 `advisory=True/enforced=False` 且无写库/阻断调用形态 |
| `tests/execution_truth_test.py` | 新增 T2b 5 项 | 授权书第 4/5 条的可核验断言：执行记录含动作/输入输出/结果/失败原因/溯源；且**执行前后 proposal 逐字节不变**、记录内 hash == 审批绑定值 |
| `src/video_studio/ops/execution.py` | 沙箱脚本产物路径改为**由 `box` 直接派生** | 原来取调用方传入的 `ctx["artifacts"]["script_output"]`；改为 `box/artifacts/script_output.json`（语义等价、路径更确定），使 M8e 的沙箱污点证明成为**静态可证**性质 |

### 1.4 本轮证据脚本（可复现）

| 文件 | 行数 | 产出 |
| --- | --- | --- |
| `docs/regression_2x/phase6b_m4_build_truth.py` | 67 | `logs/phase6b_m4_truth_freeze.json`（真值规范化 sha + 用例数 + v9 期望） |
| `docs/regression_2x/phase6b_m4_execute_v9.py` | 208 | `logs/phase6b_m4_approvals_v9.jsonl`、`logs/phase6b_m4_execution_ledger_v9.jsonl`、`logs/phase6b_m4_v9_execution.json` |
| `docs/regression_2x/phase6b_m4_m8e_negctl.py` | 110 | `logs/phase6b_m4_m8e_negctl.json`（守卫**负对照**：8/8 变异检出、干净样本 0 误报） |
| `docs/regression_2x/phase6b_m4_batch_items.py` | 93 | `logs/phase6b_m4_batch_items.json`（step2 逐项可续跑执行） |
| `docs/regression_2x/phase6b_m4_battery.py` | 191 | `logs/phase6b_m4_regression_summary.json` + `logs/phase6b_m4_rerun/**` |
| `docs/regression_2x/phase6b_m4_guard_check.py` | 93 | `logs/phase6b_m4_guard_check.json`（24 守卫 + 工作树漂移） |
| `docs/regression_2x/phase6b_m4_final_check.py` | 203 | `logs/phase6b_m4_final_check.json`（基线/守卫/套件/执行证据/指纹汇总） |

### 1.5 明确**未**改动

- 未改 `core/integrity.py`（PI-1…PI-6 定义与阈值）、`core/direction.py`（DQ-1…DQ-8）、`core/human_review.py`、`core/revision.py`。
- 未改 `agents/**`（执行层**不接入**生产链；`agents` 不 import `execution`）。
- 未新增人类审批 CLI（见 §6 已知边界）；
- 未新增 `src/video_studio/ops/*` 之外的写型模块；未改 `cli.py`（本轮无新增子命令）。

---

## 2. Proposal / 审批 / 执行 schema

### 2.1 审批记录（`make_approval` → `verify_approval`）

```json
{
  "approval_id": "ap-<sha256(proposal_id|proposal_sha256|decision|approved_by|approved_at)[:12]>",
  "proposal_id": "rp-…", "proposal_sha256": "<规范化 sha256>",
  "decision": "APPROVE | REJECT",
  "approved_by": "human:<identity>", "approved_at": "2026-09-28T00:00:00Z",
  "reason": "<人工理由>", "provenance": "<人工证据来源>",
  "auto_approved": false, "seq": 1, "prev_sha256": "…", "entry_sha256": "…"
}
```

必需字段（真值集冻结）：`approval_id, proposal_id, proposal_sha256, decision, approved_by,
approved_at, reason, provenance`。**缺人工身份/理由**（`approved_by` 不以 `human:` 开头或 `reason` 为空）
⇒ `BLOCKED_UNAPPROVED`（`verify_approval` 第 4 道判定）。

### 2.2 执行门禁（`gate_execution`）与失败编码

| 编码 | 触发条件 |
| --- | --- |
| `BLOCKED_UNAPPROVED` | 无审批记录 / 该方案未获批准 / 审批缺人工身份或理由 / 审批绑定的是**别的** `proposal_id` |
| `BLOCKED_REJECTED` | 存在该方案的人工 **REJECT** 记录 |
| `BLOCKED_TAMPERED` | 有 APPROVE，但当前 `proposal_sha256` ≠ 审批时绑定值（**内容被改**） |
| `BLOCKED_NOT_LOCAL` | `film_wide=true`，或镜数 > `max_scenes_per_proposal=6`，或 `share_of_film` > `0.30`，或范围不可定位 |
| `UNSUPPORTED_ACTION` | 该 action 未实现执行器（**不模拟、不伪造**执行结果） |
| `PENDING_HUMAN_ASSET` | 需要新素材但无**真实存在且经校验**的候选（不虚构 asset_id、不占位替换） |
| `FAILED` | 执行器抛异常 / 强制 PI 复核缺失 / PI-DQ 复核抛异常（**fail-closed**） |
| `SUCCEEDED` | 门禁通过 + 执行器真实返回 + 强制复核完成（`promoted` 恒 `false`） |

判定**顺序**：审批 → 篡改 → 局部化 → 执行器存在性 → 执行 → 强制复核。
其中"绑错方案"在篡改判定之前命中（因为审批根本不指向本方案），故真值集 `EX-G4` 期望
`BLOCKED_UNAPPROVED`（**两者都是拒绝执行**；本轮曾把期望写成 `BLOCKED_TAMPERED`，属期望笔误，
已按代码真实行为修正并复冻：见 §6 自我更正）。

### 2.3 执行记录（`execute_proposal` → `append_execution`）

```json
{
  "schema": "revision-execution-v1", "proposal_id": "rp-…", "proposal_label": "H7-outro-card",
  "finding_id": "hr-…", "action": "add_outro_card", "executed_at": "…Z",
  "proposal_sha256": "…", "approval_ref": {"approval_id": "ap-…", "approved_by": "human:…",
  "decision": "APPROVE", "approved_at": "…"},
  "auto_approved": false, "auto_scope_expansion": false, "auto_retry": false,
  "sandbox_only": true, "advisory": true, "enforced": false,
  "state": "SUCCEEDED", "why": null,
  "steps": [{"step": "…", "in": "…", "out": "…", "output_sha256": "…", "window": [t0,t1]}],
  "outputs": [{"path": "output/phase6b_m4_sandbox/…", "bytes": …, "sha256": "…"}],
  "recheck": {"pi_metrics": {...}, "pi_gate_outcome": "BLOCKED", "dq_metrics": {...}},
  "pi_gate_outcome": "BLOCKED", "promoted": false, "seq": …, "prev_sha256": "…", "entry_sha256": "…"
}
```

### 2.4 PI/DQ 复核契约（执行后**强制**）

- `must_rerun = PI-1…PI-6`；判定**复用 6-A/M2 冻结门禁**（`pre_render_gate` / `post_render_gate`），
  任一 gate blocked ⇒ `pi_gate_outcome = BLOCKED`；**不放行、不提升**。
- DQ 复核随后运行（DQ-1…DQ-8），`advisory=true / enforced=false`；**不**接 `TASK_BLOCKED`。
- 复核异常 ⇒ 执行记录 `FAILED`（fail-closed），**不**以"复核失败"当作成功。

---

## 3. v9 真实受控执行证据（H1～H7）

输入：v9 母版 `projects/p_96efdc03e1aa/output/t_d0a54bdf1810_draft.mp4`
（sha256 `22705c7d7ea20b40…`，46,761,341 B）。8 条 M3 方案 → 3 条人工审批 → 5 条执行记录。

### 3.1 审批（3 条，全部非自动）

| # | proposal | 方案 id | 决策 | 人工身份 | 理由 / 溯源 |
| --- | --- | --- | --- | --- | --- |
| 1 | H7-outro-card | `rp-13aae40036e3` | **APPROVE** | `human:director(6-B/M4)` | 同意在末镜窗口内**原地**加片尾卡（不改总时长、不改旁白正文） / 6-A 审计 §2.7 缺片尾 VERIFIED + KNOWN_ISSUES #67 |
| 2 | H2-asset-pool-diversity | `rp-fe49f9ad40f4` | **APPROVE** | `human:director(6-B/M4)` | 同意补足素材多样性（4→≥6），但**必须**使用真实可验证素材 / 6-A 审计 §2.2 素材重复 VERIFIED |
| 3 | H3-batch1-split-longest | `rp-130d116e03d6` | **REJECT** | `human:director(6-B/M4)` | 本轮不重剪画面节奏（与既有 5.x 交付节奏策略冲突，留待后续人工统一规划） / 导演决定（本轮范围外） |

### 3.2 执行（5 条记录 / 5 类结果）

| proposal | action | 结果 | 证据 |
| --- | --- | --- | --- |
| H7-outro-card（已批准） | `add_outro_card` | **SUCCEEDED** | 沙箱内真实重编码：`output/phase6b_m4_sandbox/p_96efdc03e1aa_h7outro/output/t_d0a54bdf1810_draft_m4_h7_outro.mp4`（48,470,492 B）；steps = 末段重编码（输出 sha256）+ 前段流复制 + 拼接；时长契约保持不变 |
| H2-asset-pool-diversity（已批准） | `add_asset` | **PENDING_HUMAN_ASSET** | 无**真实存在且经校验**的候选素材 ⇒ 进入人工待处理（不虚构 asset_id、不占位替换）；`steps` 记录查询范围与所需素材 |
| H3-batch1-split-longest（已 REJECT） | `split_scene` | **BLOCKED_REJECTED** | 人工 REJECT 记录存在 ⇒ 门禁拒绝，**未**执行 |
| H1-hook-replace（未批准） | `replace_asset` | **BLOCKED_UNAPPROVED** | 无人工审批 ⇒ 拒绝执行 |
| H7-outro-card（内容被篡改后重放） | `add_outro_card` | **BLOCKED_TAMPERED** | 篡改后 `proposal_sha256` ≠ 审批绑定值 ⇒ 拒绝执行 |

> 8 条方案中其余 4 条（H3b / H4 / H5 / H6）**连执行尝试都没有**：它们没有任何审批记录，
> 汇总中计入 `unapproved`（共 5 条：H1/H3b/H4/H5/H6）——"未批准即不执行"由**门禁**保证，而非靠人工自觉。

### 3.3 执行后强制复核（H7）

- **PI-1…PI-6**（冻结度量 + M2 门禁）：`PI-1 FAIL`、`PI-2 FAIL`、`PI-3 FAIL`、`PI-4 PASS`、`PI-5 FAIL`、`PI-6 FAIL`
  ⇒ `pre_render_gate`/`post_render_gate` ⇒ **`pi_gate_outcome = BLOCKED`**。
- **DQ-1…DQ-8**（只读 advisory）：`DQ-1 UNKNOWN`、`DQ-2 FAIL`、`DQ-3 FAIL`、`DQ-4 FAIL`、`DQ-5 FAIL`、
  **`DQ-6 PASS`（执行前 FAIL → 执行后 PASS，真实可测改善）**、`DQ-8 FAIL`。
- 结论：**局部修订只改善它针对的那一项**（DQ-6 片尾完整性），全片问题（覆盖/静音/orphan/节奏/语义支撑）仍在，
  PI 仍 **BLOCKED** —— 这正是诚实结果：本层**不提升、不跳过**任何门禁。

### 3.4 零自动化与只读证据

| 项 | 值 |
| --- | --- |
| `executed_without_approval` | `[]` |
| `auto_approved` | `false` |
| `promoted` | `[]` |
| 已执行方案数 / 总方案数 | **1 / 8** |
| 审批台账 | `logs/phase6b_m4_approvals_v9.jsonl`：3 条，`chain_ok=true` |
| 执行台账 | `logs/phase6b_m4_execution_ledger_v9.jsonl`：5 条，`chain_ok=true` |
| DB sha256 前/后 | `47217a5b8da6dae9…` / `47217a5b8da6dae9…`（**未变**） |
| v9 母版 sha256 前/后 | `22705c7d7ea20b40…` / `22705c7d7ea20b40…`（**未变**） |
| v9 output 目录 | 未变（`v9_output_dir_unchanged=true`） |
| 被触碰的项目文件 | `[]` |

---

## 4. 真值集与单测回归

### 4.1 真值集冻结

`tests/fixtures/revision_execution_truth_v1.json`，规范化 sha256
**`dcb6bac24a0b6746756a5ba250368c7756f874eaa9f3f7e248c4bf33bbc84eba`**
（与 `logs/phase6b_m4_truth_freeze.json` 一致；T0f 断言两者相等）。
内容：8 个门禁用例（EX-G1…EX-G8）、6 个执行用例（EX-E1…EX-E6）、台账契约（append-only +
3 类篡改检出 + 两条独立链）、素材守恒规则、PI 复核契约、v9 期望、5 条边界声明。

### 4.2 M4 新套件 `tests/execution_truth_test.py`：**45/45 通过**（`SKIP=[]`，rc=0）

| 组 | 覆盖 |
| --- | --- |
| T0（6 项） | 真值 schema/阶段、规范化 sha == 文件内锚点、审批必需字段、取值与状态机、冻结策略 == 代码 `POLICY`、与冻结记录一致 |
| T1（8 项） | 门禁矩阵：无审批 / REJECT / 篡改内容 / 绑错方案 / 批准通过 / film_wide / 7 镜 / 占比 0.5 |
| T2（7 项） | 执行器抛异常、无执行器、待素材、成功需复核、缺复核 fail-closed、复核抛异常 fail-closed、成功后 `promoted=false` |
| T2b（5 项） | 记录字段完整（第 4 条）、输入来自执行器真实返回、失败含原因且不回填假输出、**proposal 逐字节不变**（第 5 条）、记录 hash == 审批绑定值 |
| T3（4 项） | 双链完整 + 3 类篡改（改条目 / 删中间条目 / 交换审批）全部检出 |
| T4（10 项） | v9 审批/五类执行结果/零自动化/强制 PI 重跑/DQ 改善/仅沙箱/母版与 DB 未变/母版 sha 一致/双链完整/只执行 1 条 |
| T5（5 项） | 静态：无 auto_* 与批量执行入口、`auto_approved=False` 写死、核心不 import DB/进程、沙箱前缀 `output/`、无 agent import execution |

### 4.3 守卫负对照（证明守卫**可被真实触发**）

`logs/phase6b_m4_m8e_negctl.json`：对 `ops/execution.py` 施加 7 类变异 + 1 个干净样本
⇒ **8/8 变异全部检出、干净样本 0 误报**（`detected=8`、`undetected=[]`、
`clean_baseline_false_positive=[]`）。变异：沙箱前缀逃逸 / `auto_execute_all` / `apply_proposal` /
越界写入 / DB 写 SQL / rmtree 基线目录 / agents 可达。

### 4.4 受影响套件（全部 rc=0）

| 套件 | 结果 |
| --- | --- |
| `tests/execution_truth_test.py`（新） | **45/45** |
| `tests/maintenance_fixes_test.py`（改） | **30/30**（新增 M8e 2 项） |
| `tests/dq_truth_test.py`（改） | **122/122**（新增 T4a-2/T4a-3） |
| `tests/revision_truth_test.py` | 61/61 |
| `tests/review_truth_test.py` | 47/47 |
| `tests/direction_test.py` | 25/25 |
| `tests/integrity_gates_test.py` | 45/45 |
| `tests/integrity_truth_test.py` | 243/243 |
| `tests/narration_contract_test.py` | 45/45 |

---

## 5. 完整回归

### 5.1 step2（`3a_regression_batch`）逐项执行

| 项 | 值 |
| --- | --- |
| 执行器 | `docs/regression_2x/phase6b_m4_batch_items.py`（argv 与 ITEMS 由 **AST 解析同一份** `phase3a_regression_batch.py`，逐项落盘进度、可 `--resume`） |
| 结果 | **24 项 | 符合预期 24/24 | 非预期 [] | 等价 step rc = 0** |
| 耗时 | 1960.9 s（**单次跑完**，未中断） |
| 逐项日志 | `logs/phase3a_<name>.log`；汇总 `logs/phase6b_m4_batch_items.json` |
| 外部步骤记录 | `logs/phase6b_m4_external_steps.json`（`executed_by` / `evidence` / `rc` / `environment_pending={}`，未伪造） |

### 5.2 电池（25 步）

- **25 步全部 rc=0**；`all_rc_zero_raw = True`；`rc_nonzero = []`；`rc_pending = []`。
- 各步 `seconds` 之和 **4373.2 s**；本次启动 2417.1 s（差额 = 由外部执行器完成的 step2，为避免把外部耗时算作本进程耗时）。
- 冻结日志快照：**2377 文件 → 运行中改变 40 / 新增 26 / 删除 0 ⇒ 回拷后逐字节恢复 = True（drift 0）**。
- 步骤序列（AST 解析 `phase5f_regression.py` 的 `STEPS`，与 5-F/5-G/5-J/5-L/5-M/6-A/6-B 各期**同一步骤表**）：

| step | rc | s | step | rc | s | step | rc | s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 3a_real_chain | 0 | 6.1 | 4g_evidence | 0 | 0.4 | 5c_failclosed | 0 | 6.5 |
| **3a_regression_batch** | 0 | 1960.9 (外部) | 4x_audit | 0 | 2.0 | 5c_checkpoint_check | 0 | 1.1 |
| 3b_audit | 0 | 7.5 | 5a_evidence | 0 | 48.4 | 5d_mm_temporal_test | 0 | 121.1 |
| 3b_failure_paths | 0 | 22.5 | 5b_evidence | 0 | 57.8 | 5d_frozen_check | 0 | 0.8 |
| 4ab_evidence | 0 | 168.2 | 5c_append_only | 0 | 0.1 | 5e_mm_quality_test | 0 | 394.7 |
| 4c_evidence | 0 | 1.4 | 5c_db_append_only | 0 | 2.3 | 5e_calibration | 0 | 184.3 |
| 4d_evidence | 0 | 1.2 | 5c_verify_film | 0 | 4.6 | 5f_mm_judge_test | 0 | 179.1 |
| 4e_ab_benchmark | 0 | 0.1 | 4f_evidence | 0 | 13.5 | 5f_judge | 0 | 0.1 |
|  |  |  |  |  |  | **unit_suites** | **0** | **1188.5** |

### 5.3 step25 `unit_suites`：**57 个套件全部 rc=0**

（M3 期为 56 个；本轮新增 `tests/execution_truth_test.py` ⇒ 57。）
其中本轮新增套件 `execution_truth_test` 记录为 `rc=0`、`结果: 45/45 通过   SKIP=[]`
（`logs/phase6b_m4_rerun/suites_summary.json`）。失败套件：**无**。

### 5.4 回归口径声明（诚实性）

- step2 的 rc 取自**外部逐项执行器**；电池将其标为 `executed=externally` 并在汇总中单独列出，
  **不**把外部耗时计入"本次启动耗时"，也**不**声称它是电池进程内执行的。
- 冻结日志在被 25 步改写后**逐字节回拷恢复**（`frozen_logs_restored=True`、deleted 0），
  故各期"冻结证据"未被本轮回归破坏。
- `4x_audit` 记录的批次网络项 `as_expected=24/24` 仅为**本轮观察**，**不**改写任何历史 `PENDING（环境）` 记录。

---

## 6. 基线完整性与已知边界

### 6.1 基线未被改写（4/4）

| 基线 tag | ZIP sha == manifest | 文件数 |
| --- | --- | --- |
| `5.x-post-final-maintenance-baseline` (r1) | **True** | 385 |
| `5.x-post-final-maintenance-baseline-r2` | **True** | 387 |
| `5.x-post-final-maintenance-baseline-r3` | **True** | 389 |
| `5.x-final-baseline` | **True**（sha `be1717b9c7fe9ed9…` 未变） | 384 |

本轮**未新增基线、未新增 tag**（`baseline/` 内 ZIP 清单不变）。

### 6.2 守卫（24 项）与工作树

- 守卫项漂移：**仅** `src/video_studio/agents/editing/agent.py`（6-A/M2 授权的 PI 门禁接线；M4 **未**再改该文件）；
  `unexpected_guard_drift = []`。
- 工作树相对 r3 漂移 6 个文件：`agents/editing/agent.py`、`cli.py`、`tests/bgm_ducking_test.py`、
  `tests/maintenance_fixes_test.py`、`tests/narration_contract_test.py`、`tests/pipeline_mock.py`；**缺失 0**。
  （新增文件不在 r3 清单内，因此不计入"漂移"；其增量见 §6.3。）
- 历史母版：v9 成片 sha256 `22705c7d7ea20b40…` / 46,761,341 B —— **未被改写**。

### 6.3 代码指纹链（逐阶段）

| 阶段 | 文件数 | aggregate sha256(前 16) |
| --- | --- | --- |
| 6-A/M1 | 395 | `da1be48c58bc7cb9` |
| 6-A/M2 | 396 | `f15027be4f7cd8e4` |
| 6-A/M3 | 400 | `9cd07d694a5e0033` |
| 6-B/M1 | 400 | `9cd07d694a5e0033` |
| 6-B/M2 | 404 | `14945b55410aabe9` |
| 6-B/M3 | 408 | `d36ec4d89cadb584` |
| **6-B/M4** | **412** | **`2aa5fd46f5e13663`** |

6-B/M4 增量：**变化 2**（`tests/dq_truth_test.py`、`tests/maintenance_fixes_test.py`）、
**新增 4**（`src/video_studio/core/execution.py`、`src/video_studio/ops/execution.py`、
`tests/execution_truth_test.py`、`tests/fixtures/revision_execution_truth_v1.json`）、**删除 0**。
（`docs/regression_2x/**` 证据脚本与报告不在指纹口径内。）

### 6.4 沙箱

`output/phase6b_m4_sandbox/p_96efdc03e1aa_h7outro/` 存在，位于 `output/` 下、**不在** `projects/` 内：

| 文件 | 字节 |
| --- | --- |
| `output/t_d0a54bdf1810_draft.mp4`（源片**复制品**） | 46,761,341 |
| `output/t_d0a54bdf1810_draft_m4_h7_outro.mp4`（**真实执行产物**） | 48,470,492 |
| `work/head.mp4`（前段流复制） | 46,125,992 |
| `work/outro_card.mp4`（末段重编码 + 片尾卡） | 2,338,729 |
| `work/concat.txt` | 198 |
| `artifacts/script_output.json` / `voice_output.json` | 29,483 / 11,379 |

### 6.5 已知边界（**不**计入 PASS 的能力）

1. **无人类审批 CLI**：本轮审批记录由闭环脚本调用 `core.execution.make_approval` 写入（人工身份/理由/溯源为**必填**字段）。
   授权书未要求 CLI，但必须说明：`approved_by` 是**自陈**身份，**不是**密码学认证 ⇒ 本报告**不**声称"身份不可伪造"。
2. **新素材执行分支未被真实触发**：`_pending_asset` 在 v9 上走的是 `PENDING_HUMAN_ASSET`（无真实候选，符合授权第 8 条）。
   "**有**真实可用素材 ⇒ 确实执行"的那条分支只有代码路径与真值集用例（EX-E3）覆盖，**未**端到端跑通 ⇒ 该能力 **PENDING**。
3. **多方案并发/冲突未验证**：8 条方案中仅 1 条被真实执行；并发执行、同一镜头多方案冲突消解**未**验证 ⇒ PENDING。
4. **执行层不进生产链**（BY DESIGN）：`agents/**` 不 import `execution`（T5e/T4a-2 静态证明），
   故本层只能由脚本/测试驱动；本轮**未**提供 `run.py` 执行子命令。
5. **DQ 复核省略 `measure_freeze`**：`pi_recheck` 中 DQ 复核跳过 freeze 度量（避免长片二次解码），
   DQ-3 的 freeze 证据缺失属**已知省略**（DQ-3 状态判定不依赖 freeze）。
6. **台账链无外部锚/无签名**：append-only hash chain 能检出改写/插入/重排（3 类篡改已实测检出），
   但**不能**防"整链自洽重写" ⇒ 强度边界如实声明。
7. **5-D 期历史检查 `5d_frozen_check` 漂移 164**（`rc=0`，MISSING 0）：历史同量为
   M1/M2/M3 均 165、6-A/M3 期 164 —— 属**既有**口径，本轮**未**将其归零，也未声称与本轮无关。
8. **真值集修正 1 次**：`EX-G4`（"审批绑定到**别的**方案"）的期望原写作 `BLOCKED_TAMPERED`，
   按代码真实行为修正为 `BLOCKED_UNAPPROVED`（两者都是拒绝执行，但**分属不同编码**）；
   修正后复冻 ⇒ 现行锚 `dcb6bac2…`，修正前锚 `58f0bae7…` **作废**。
9. **沙箱残留约 95 MB**（复制品 + 产物）保留作为可复核证据，**未**自动清理；人工删除不影响任何判定。
10. **守卫测试契约变更 2 处、均已披露且为加强**：`maintenance_fixes_test` 新增 `AUTHORIZED_WRITE_OPS` 类别与 M8e
    （写型模块**不得**伪装只读；白名单互斥）+ 负对照 8/8 检出；`dq_truth_test` 白名单扩张同时新增
    T4a-2（agents 不可达执行层）与 T4a-3（只读 advisory、无阻断形态）作为**替代性强化证明**。

---

## 7. 结论

### 7.1 授权 12 条逐条对照

| # | 授权要求 | 状态 | 证据 |
| --- | --- | --- | --- |
| 1 | 审批层：每条方案需人工 `APPROVE/REJECT`，未批准**永不**执行 | **满足** | `core/execution.py` 门禁；v9：8 条方案 → 2 APPROVE / 1 REJECT / 5 未批准；仅 1 条执行 |
| 2 | 审批绑定 `proposal_id + hash + 人工身份 + 时间 + 理由/溯源` | **满足** | 8 必需字段（T0c）；3 条真实审批记录含身份/理由/溯源 |
| 3 | 只有 `APPROVE` 进入执行 | **满足** | T1 门禁矩阵 8/8；未批准 ⇒ `BLOCKED_UNAPPROVED` |
| 4 | 执行记录须含实际动作/输入输出/结果/失败原因/溯源 | **满足** | T2b 5 项；执行记录 schema §2.3（steps 内含 in/out + sha256） |
| 5 | 执行前 hash 校验；执行器**不得**静默改方案 | **满足** | T2b：执行前后 proposal 逐字节不变、hash 一致；篡改 ⇒ `BLOCKED_TAMPERED` |
| 6 | 失败 fail-closed：不自动换方案/不扩范围/不自动批准 | **满足** | T2 6 例：执行器异常/缺复核/复核异常 ⇒ `FAILED`；`auto_*` 恒 false |
| 7 | 保持 M3 局部化上限，不做全片重写 | **满足** | 执行门禁再次校验：`film_wide` / >6 镜 / >0.30 ⇒ `BLOCKED_NOT_LOCAL`（EX-G6/G7/G8） |
| 8 | 新素材仅限真实且可验证，否则人工待处理 | **满足**（有边界） | H2 真实走 `PENDING_HUMAN_ASSET`；"有素材 ⇒ 执行"分支未端到端验证（§6.5-2，PENDING） |
| 9 | 每次执行后重跑 PI-1…PI-6；PI FAIL/UNKNOWN 走既有门禁 | **满足** | H7 后 PI-1/2/3/5/6 FAIL ⇒ `pi_gate_outcome=BLOCKED`；T4d |
| 10 | DQ 保持 advisory，不接 `TASK_BLOCKED` | **满足** | `advisory=true/enforced=false`；T4a-2/T4a-3 静态证明生产链不可达 |
| 11 | v9 须证明 ≥1 条 APPROVE→执行→PI/DQ 复核闭环，且 REJECT/未批准不执行 | **满足** | H7 闭环（真实重编码产物 48,470,492 B + PI/DQ 复核）；H3a `BLOCKED_REJECTED`、H1 `BLOCKED_UNAPPROVED` |
| 12 | 不改 5.x Final / r1r2r3；不覆盖 v9 母版；不新增基线/tag | **满足** | 4 个 ZIP sha == manifest；母版 sha 未变；无新 tag；`no_new_baseline_or_tag` 清单未变 |

### 7.2 量化结论

- 新增源码 **2** 个文件（523 行）；新增测试/真值 **2** 个（638 行）；守卫测试加强 **2** 处（+5 项检查）。
- M4 新套件 **45/45**；受影响套件 9 个**全部 rc=0**；守卫负对照 **8/8 检出、0 误报**。
- 完整回归：step2 批次 **24/24**；电池 **25/25 步 rc=0**；`unit_suites` **57/57 套件 rc=0**；
  冻结日志 **2377 文件 → 改 40 / 增 26 / 删 0 → 恢复 True（drift 0）**。
- v9 受控执行：**8 条方案 → 3 条审批 → 5 条执行记录（5 类结果各 1）→ 1 条真实成功**；
  `executed_without_approval=[]`、`auto_approved=false`、`promoted=[]`；两条台账链 `chain_ok=true`；
  v9 母版 / output 目录 / DB **逐字节未变**。

### 7.3 判定

> **6-B/M4（人工批准的导演修订执行）= PASS。**
>
> 全部 12 条授权要求均已实现并有可复现实测证据；`PASS` **不**包含 §6.5 的 10 项边界，
> 其中第 2/3 项（真实素材执行分支、多方案并发冲突）标注为 **PENDING**，
> 第 1 项（人类审批 CLI）标注为 **未提供（非授权要求）**。
> 未将任何 PENDING/BLOCKED 改写成 PASS；PI 在 v9 上仍为 **BLOCKED**，DQ 仍为 advisory。

**本阶段到此为止（STOP），不进入 6-C。**
等待人工指令：是否将 §6.5 的 PENDING 项（人类审批 CLI、真实素材执行分支、多方案并发）作为下一阶段输入。
