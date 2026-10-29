# 6-B / M3 —— Human-Approved Directorial Revision Proposal

- 阶段：**6-B/M3**（把 6-B/M2 已确认的 **REJECT** findings 转成结构化、局部、"原则可执行"的修改方案；
  **本阶段禁止实际执行修改**）
- 前置：6-B/M1（DQ 只读度量 + v9 只读审计）→ 6-B/M2（Human Review Bridge：7 条 REJECT + 4 条 DEFER 台账）
- 本轮**只生成方案**：不改素材 / timeline / 字幕 / 旁白 / config / 成片；不写 DB、不派发任务、不 redo；
  DQ 仍 advisory，**不接入 `TASK_BLOCKED`**；**PI-1～PI-6 一行未改**；
  不改 5.x Final / r1 / r2 / r3；不重渲染、不执行 proposal、不新建 baseline/tag。
- 证据：`docs/regression_2x/logs/phase6b_m3_proposals_v9.json` +
  `phase6b_m3_proposal_register_v9.jsonl`；真值集：`tests/fixtures/revision_proposal_truth_v1.json`；
  套件：`tests/revision_truth_test.py`。

---

## 1. 变更清单

| 文件 | 变更 | 影响 |
|---|---|---|
| `src/video_studio/core/revision.py`（281 行） | **新增**：方案构造与校验（必绑人工 REJECT、局部化上限、反虚构 guard）、DEFER/UNKNOWN → 待补证据项、**append-only 方案登记（hash 链）** | 纯生成/登记；不写 DB、不写产物、无任何执行路径 |
| `src/video_studio/ops/revision.py`（130 行） | **新增**：只读编排（读 6-B/M2 闭环 → 套用**人工撰写的方案模板** → 校验/绑定/汇总） | `executed_actions` 恒空；读库经白名单只读模块委托 |
| `src/video_studio/cli.py` | 新增只读子命令 `revision-plan`（`--specs/--register/--out`；**没有** apply/execute 开关） | 归入既有"只读/仅记录人工决定"路径 |
| `tests/maintenance_fixes_test.py` | 测试契约更新：只读 ops 白名单纳入 `ops/revision.py`；`ro_connection` 允许"委托另一白名单只读模块"形态（写库禁令不变） | 28/28 保持通过，守卫强度不变 |
| `tests/fixtures/revision_proposal_truth_v1.json`、`tests/revision_truth_test.py` | **新增**：方案真值集（5 合法 + 12 拒绝用例、登记篡改、v9 期望）+ 回归套件（**61/61**） | 见 §4 |
| `docs/regression_2x/phase6b_m3_*.py` + `PHASE6B_M3_REPORT.md` | 新增：真值冻结、v9 方案闭环、逐项批次执行器、可续跑电池、守卫/收尾核对、本报告 | 专用证据路径 |

**未改动**：`config/*`、`core/integrity.py`（PI 门禁）、`agents/**`（AST 复核：无 agent import revision）、
`core/direction.py`、`core/human_review.py`（M2 层未改）、全部 `mm_*` 与既有真值集。

---

## 2. Proposal schema

**方案字段（必需）**：`proposal_id`（`rp-<sha256(finding|action|discriminator)[:12]>`）、`label`（人工可读标签）、
`finding_id`、`metric/kind/severity`、`scene_id/asset_id/window`、`original_evidence`、`evidence_refs`、
**`decision_ref`**（`{ledger_seq, decision=REJECT, decided_by, decided_at, provenance, entry_sha256}`）、
`action`、`target`、**`proposed_change`**（`{what, how, params}`）、**`affected_scope`**
（`scenes/assets/window/asset_class` + `share_of_film` + `instance_coverage{covered,total,follow_up_required}`
+ `locality_limits` + **`not_touching`**）、**`expected_effect`**（`{metric, direction, basis, assumption, not_guaranteed}`）、
**`constraints`**（`must_preserve` + **`must_rerun`** + `requires_human_approval` + `no_auto_execution`）、
**`risk`**（`[{risk, mitigation}]`）、**`provenance`**（三段链：DQ finding → Human REJECT decision(seq) → proposal，
含 `decision_entry_sha256` 与"执行权在人工"声明）、`status=PROPOSED_AWAITING_HUMAN_APPROVAL`、`approved=false`、`executed=false`。

**action 取值**：`replace_asset / add_asset / split_scene / adjust_hold / reorder_scenes / insert_scene /
text_overlay / add_outro_card / add_visual_aid / no_change_evidence_gap`。

**硬规则（代码级 guard）**：

| 规则 | 实现 |
|---|---|
| 必须绑定**人工 REJECT** | 无 REJECT 决策 ⇒ `PROPOSAL_REQUIRES_HUMAN_REJECT` |
| **DEFER/UNKNOWN 不得变成修改指令** | 不可证 finding ⇒ `DEFER_MUST_NOT_BECOME_CHANGE`（只允许 `evidence_gap`） |
| 局部化 | 单方案 ≤**6** 镜、时长占比 ≤**0.30**、禁止 `film_wide` ⇒ 超限 `SCOPE_NOT_LOCAL` / `FILM_WIDE_REWRITE_FORBIDDEN` |
| 反虚构 | `scenes ⊆ 真实镜头集合`、`assets ⊆ 已知素材集合`（越界即拒）；需要新素材只能用 `new_assets_needed{count, semantic_spec, sourcing}` |
| 预期收益可核 | `expected_effect.basis` 必须引用源 finding 实测值；`assumption` 必填 |
| **零执行** | 无 `apply/execute` 代码路径；登记条目恒 `executed=false / executes_changes=false`；`executed_actions` 恒空 |

---

## 3. v9 H1～H7 proposal evidence

来源：6-B/M2 台账的 **7 条人工 REJECT**（+2 条 DEFER/UNKNOWN → 待补证据项）。
**7 条 REJECT → 8 条方案**（H3 拆为两个局部批次），全部局部化、0 违规、0 构建错误。
影响范围**全部取自既有证据**（镜头 window / 素材 id 来自 DQ finding 与时间轴），未手抄、未虚构。

| 覆盖 | 标签 | action | 影响范围（取自证据） | 预期效果（含 basis/assumption） | 关键约束与风险 |
|---|---|---|---|---|---|
| H1 Hook | `H1-hook-replace` | `replace_asset` | S01（0–40 s），hook 素材 1 个 | DQ-1：S01 由"各层全 UNKNOWN"变为可判定；basis=DQ-1 layers 全 UNKNOWN；**不保证**自动 MATCH | 保 hook 旁白/窗口/总时长；风险：语义仍不匹配、许可不明、抽帧核验失败 → 均需重跑 |
| H2 重复 | `H2-asset-pool-diversity` | `add_asset` | 4 个既有素材 + 首批 4 镜（b1） | DQ-2：unique 4 → ≥6、max_share 0.3329 → ≤0.35；basis=DQ-2 实测；需先获可用新素材（`new_assets_needed{2}`，不虚构 asset_id） | 1:1 署名台账、许可 gate、总时长不变 |
| H3a 静态 | `H3-batch1-split-longest` | `split_scene` | 最长批 4 镜（S07/S06/S16/S18，占片长 0.2285） | DQ-3：本批 hold ≤25 s；over-hold 占比由 1.0 下降；basis=DQ-3 实测；**后续批次待推进** | 旁白/字幕/总时长不变；素材复用不得恶化（DQ-2 不得变差） |
| H3b 静态 | `H3-batch2-next-longest` | `split_scene` | 次长批 5 镜（S03/S11/S12/S15/S17，占片长 0.2611） | 同上 | 同上 + 批次间风格一致 |
| H4 密度 | `H4-density-increase` | `split_scene` | 与 H3a 同批 4 镜（**依赖** H3a） | DQ-4：0.822 → 目标 ≥2.0（本批部分改善，全片目标需多批次 + 人工批准）；basis=DQ-4 实测 | 总时长不变；过度切分风险（设单镜下限） |
| H5 语义 | `H5-semantic-mismatch-replace` | `replace_asset` | S05(245–300 s)/S11(690–770 s)/S18(1245–1330 s) | DQ-8：MISMATCH 3 → 0（需复核）；basis=DQ-8 mismatch_scene_count=3 / match_share=0.0595 | 旁白/字幕/总时长/许可；语义判定仍属人工，DQ 不自动给 MATCH |
| H6 高潮 | `H6-visual-climax-aid` | `add_visual_aid` | 核心论点镜前 5 个（共 20，`instance_coverage{5/20, follow_up}`） | DQ-5：核心镜素材多样性 4 → 目标 ≥6（本批部分改善）；basis=DQ-5 实测 | 不碰非核心镜；`new_assets_needed{2}`（示意图/数据可视化，人工设计或授权） |
| H7 片尾 | `H7-outro-card` | `add_outro_card` | 末镜 S21（1465–1532 s） | DQ-6：outro 关键词 0 → ≥1；尾部静音按 PI-3 单独处置；basis=DQ-6 实测（hits=0 / tail=570.869 s） | 优先原地替换保总时长；若延长必须重跑 PI-2 |

**待补证据项（2 条，DEFER/UNKNOWN）**：`DQ-1:metric_state_unprovable`、`DQ-6:metric_state_unprovable`
—— 均为 `no_proposed_change=true`、`status=AWAITING_EVIDENCE`（需要人工抽帧/语义复核），
**没有**生成任何修改指令。

**局部化 guard 的一次真实拦截（如实记录）**：H4 的首版方案覆盖 9 个镜头（>上限 6）被
`SCOPE_NOT_LOCAL` 拒绝 → 改为 4 镜局部批次（依赖 H3a）后才通过；该拦截已写入真值集边界说明。

---

## 4. Truth set / regression

- 真值集 `tests/fixtures/revision_proposal_truth_v1.json`：规范化 sha256 `见 logs/phase6b_m3_truth_freeze.json`
  （文件内自锚点）。内容：必需字段、action 集合、冻结策略（6 镜 / 0.30 / 禁 film_wide）、`must_rerun` 清单、
  **5 个合法方案用例**（含 `new_assets_needed`）、**12 个拒绝用例**（无 finding / 无 REJECT / 不可证 /
  越界 scene·asset / 超局部化 / film_wide / 缺 basis·assumption / 非法 action / 无锚点）、
  证据缺口契约、登记篡改用例、v9 闭环期望（8 条标签的 H1…H7 可回溯、未覆盖=0、2 条 evidence gap）。
- 套件 `tests/revision_truth_test.py` = **61/61 通过**：
  T0 冻结校验｜T1 合法方案（含人工边界与 provenance 三段链）｜T2 拒绝矩阵 12/12｜
  T3 DEFER/UNKNOWN 只出待补证据项｜T4 append-only 登记 + 篡改检出（改/删/换序）｜
  T5 真实 v9 闭环（7 REJECT → 8 方案，全部绑定 finding→seq/sha→evidence）｜
  T6 不改未被 REJECT 的内容（`not_touching` 非空 + 范围可定位 + basis/assumption + must_rerun）｜
  T7 零执行（静态：无写库/派发/apply 路径、无 agent 引用；运行期：DB/成片/项目目录零改动）。

---

## 5. 完整回归

| 项目 | 结果 |
|---|---|
| 方案真值集回归 `tests/revision_truth_test.py` | **61/61 rc=0，SKIP=0** |
| 受影响的既有套件 | `maintenance_fixes_test` **28/28**（契约更新后）、`review_truth_test` **47/47**、`dq_truth_test` **120/120**、`direction_test` **25/25**、`integrity_truth_test` **243/243**、`report_command_test` **18/18** |
| 25 步回归电池（`phase6b_m3_battery.py`） | **25/25 完成，`all_rc_zero_raw = True`，`rc_nonzero = []`，`rc_pending = []`** |
| step25 `unit_suites` | **55 套件全部 rc=0**（`revision_truth_test` 已并入） |
| step2 批次（逐项执行） | **24 项：符合预期 24 / 非预期 0** |
| 各步耗时之和 | 4613.6 s（含环境杀进程后的 `--resume` 续跑） |
| 冻结日志（708 文件） | 运行中改变 170 / 新增 743 / 删除 0 → **回拷逐字节恢复 = True（drift 0）** |

**执行方式的环境约束（如实披露）**：前台单次调用上限 10 分钟、后台作业约 13 分钟被环境杀死，
标准 `3a_regression_batch.py` 需连续约 34 分钟 ⇒ step2 由 `phase6b_m3_batch_items.py` **逐项执行**
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

- **守卫 24 项**：漂移仅 `agents/editing/agent.py`（M2/M3 既有授权变更，本轮未再改）；
  **未授权漂移 = 无**；工作树相对 r3 漂移仍是既有 6 个文件，缺失 = 0。
- **代码指纹**：6-B/M2 `404` `14945b55410aabe9…` → **6-B/M3 `408` `d36ec4d89cadb584…`**；
  增量 = **changed 2 / added 4 / removed 0**（改 `cli.py`、`tests/maintenance_fixes_test.py`；
  增 `core/revision.py`、`ops/revision.py`、`tests/fixtures/revision_proposal_truth_v1.json`、`tests/revision_truth_test.py`）。
- **v9 母版未被改写**：sha256 `22705c7d7ea20b40…`、46,761,341 B（未重渲染）。
- **DB / 成片 / 项目目录**：方案生成与登记前后**逐字节一致**（§3 的 `read_only_evidence`）。

### 6.2 已知边界（如实列出）

1. **方案 ≠ 执行**：本阶段无任何执行路径（无 `apply/execute`、无 redo、`executed_actions` 恒空），
   所有方案 `status=PROPOSED_AWAITING_HUMAN_APPROVAL / approved=false / executed=false`。
2. **方案内容需人工撰写**：编排层只做"**读证据 → 套模板 → 校验/绑定/登记**"，
   语义性的"改什么"由人工模板给出（本轮 8 个模板逐条绑定到对应 REJECT），框架不会自动发明修改内容。
3. **反虚构**：不得虚构素材/时间点/语义证据 —— 新素材只能声明 `new_assets_needed{count, semantic_spec, sourcing}`；
   `expected_effect` 必须带 `basis`（源 finding 实测值）与 `assumption`，且标 `not_guaranteed`。
4. **局部化是有意的硬约束**：单方案 ≤6 镜 / ≤30% 片长 / 禁 film_wide；因此 21 条超阈镜头**不能**用一个
   "全片重构"方案覆盖，H3/H4 采用**分批 + `instance_coverage{covered,total,follow_up_required}`** 如实标注
   未覆盖部分（本轮 4+5=9 镜，其余留待后续批次）。
5. **DEFER/UNKNOWN 边界守恒**：不可证 finding 即便被人为标 REJECT 也不会生成方案（`DEFER_MUST_NOT_BECOME_CHANGE`），
   只产出待补证据项。
6. **H4 对 H3a 有依赖**：密度提升与切镜批次合并推进，方案内显式声明 `dependency`，
   避免"同批重复改动/相互冲突"。
7. **测试契约更新（强度不变）**：只读 ops 白名单纳入 `ops/revision.py`；`ro_connection` 允许"委托白名单只读模块"
   形态（该文件自身不碰 DB）；写库/派发禁令与异常检测逻辑未放宽。
8. **执行方式偏离标准电池 step2**（逐项 + `--skip` 外部记录），原因同 §5。
9. **未做的**：执行方案、自动换素材/剪辑/重渲染、DQ 硬化、6-C、新 baseline/tag；
   也未扩大语义判定范围（需要语义/人审的部分保持 UNKNOWN 并留在 evidence_gaps）。

---

## 7. 结论与未授权项

- 7 条人工 REJECT finding 已全部转为**结构化、局部、可审计**的修改方案（8 条，H3 两批），
  每条都绑定 `finding_id → Human REJECT decision(seq + entry_sha256) → scene/asset/window → 原始 evidence`。
- 每个方案都给出 `proposed_change / affected_scope / expected_effect / constraints / risk / provenance`，
  并声明 `not_touching`（不改变未被 REJECT 的内容）与 `must_rerun`（执行前必须重跑 PI/DQ/核验/响度/时长/许可）。
- **DEFER/UNKNOWN 未被子偷偷转成修改指令**：只产出 2 条待补证据项。
- **未执行任何修改**：DB / 成片 / 项目目录零改动；无 apply 路径；方案登记 append-only + hash 链。
- DQ 仍 advisory/read-only、不接入 TASK_BLOCKED；PI-1～PI-6 未改；未新建 baseline/tag。
- **STOP**：本轮只做 6-B/M3。
