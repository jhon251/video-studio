# 6-B / M1 —— Directorial Quality Read-Only Audit

- 阶段：**6-B/M1**（建立可解释、可定位、**只读**的导演质量度量层 + 真值集/回归；**不做** DQ 自动硬化、不做 6-B/M2、不做 6-C）
- 前置：6-A 审计（人工 6 项发现 + v9 人审 FAIL） → 6-A/M1（DQ-1…DQ-7 只读度量雏形） → 6-A/M2+M3（PI 硬门与真值集，本轮**未改动**）
- 本轮**只读**：不重渲染、不换素材、不剪辑、不自动修复、不接入 `TASK_BLOCKED`、不改变 `render_output`；
  不改 5.x Final / r1 / r2 / r3；不新建 baseline/tag；不修改 PI-1～PI-6 门禁逻辑。
- 证据：`docs/regression_2x/logs/phase6b_m1_*.json`；真值集：`tests/fixtures/directorial_quality_truth_v1.json`；
  套件：`tests/dq_truth_test.py`。

---

## 1. 变更清单

| 文件 | 变更 | 影响 |
|---|---|---|
| `src/video_studio/core/direction.py` | ① 新增 **DQ-8 视觉语义支撑（逐镜）**（闭合授权覆盖项"视觉语义支撑"）；② 为 DQ-1/2/3/4/5/6 统一补 **`findings` 证据锚点**（scene/asset/时间区间/证据层）；③ DQ-7 汇总口径收紧（混有 `NOT_ASSESSABLE` 时不再折算为 PASS）；④ 新增策略键 `min_semantic_match_share` | 全部为**只读诊断输出**的加法/加严；不参与任何阻断，输出恒带 `enforced: False`、`advisory: True` |
| `src/video_studio/ops/direction.py` | 只读编排加入 DQ-8；人读输出补 DQ-8 摘要；mode 标注 6-B/M1 | 仍是 `mode=ro` + `query_only` 只读报告 |
| `tests/direction_test.py` | 测试契约更新：CLI 指标集合断言由 DQ-1…DQ-6 → DQ-1…DQ-6 + DQ-8（DQ-7 为总评），并补 DQ-8 语义单列断言 | 25/25 保持通过（强度不减） |
| `tests/fixtures/directorial_quality_truth_v1.json` | **新增**：DQ 冻结真值集（33 用例 + 5 汇总用例；覆盖映射、机械/语义分类、阈值快照、FAIL 证据契约、v9 真值与再发现期望） | 规范化 sha256 `见 §4` |
| `tests/dq_truth_test.py` | **新增**：DQ 真值集回归（**120/120**） | T0 冻结 → T5 v9 只读审计 |
| `docs/regression_2x/phase6b_m1_*.py` + `PHASE6B_M1_REPORT.md` | 新增：真值冻结、v9 只读审计、逐项批次执行器、可续跑电池、守卫/收尾核对、本报告 | 6-B/M1 专用证据路径，不覆盖 M1/M2/M3 证据 |

**未改动**：`config/config.json`、`config/config.mock.json`、`core/integrity.py`（PI-1…PI-6 门禁逻辑一行未动）、
`agents/**`（DQ 未被任何 agent 引用）、全部 `mm_*` 与冻结真值集、M1/M2/M3 的历史证据文件。

---

## 2. DQ 指标定义（DQ-1…DQ-8；DQ-7 = 总评）

| 指标 | 覆盖项 | 类型 | 判定（默认阈值） | 输出证据（FAIL 必带 `findings` 锚点） |
|---|---|---|---|---|
| **DQ-1** Hook 视觉相关性 | Hook | 语义 | 既有证据层（4-B/5-A/5-D/Judge）任一 MATCH → PASS；任一 MISMATCH → FAIL；全 UNKNOWN → UNKNOWN；无证据 → NOT_ASSESSABLE | `hook_scene`、逐层 `layers`、`findings[kind=hook_layer_verdict/hook_semantic_mismatch]` |
| **DQ-2** 素材复用/重复 | 素材重复 | 机械 | 单素材上屏占比 ≤ `0.35` **且** 唯一素材 ≥ `6` | `per_asset`（镜数/秒数/占比）+ `findings[asset_share_exceeds].scene_windows`、`findings[unique_assets_below_min]` |
| **DQ-3** 静态保持时长 | 静态镜头 | 机械 | 单镜保持 ≤ `25 s`；超阈镜头占比 ≤ `0.20` | `holds[]`（scene/window/hold/asset）+ `findings[hold_exceeds_max].window` + `freeze_profile`（成片 freezedetect，仅证据） |
| **DQ-4** 视觉密度 | 场景变化 / 密度 | 机械 | 镜变 ≥ `2.0` 次/分钟 | `change_points[]`、`longest_scene{scene_id,window}`、`findings[scene_changes_below_min]` |
| **DQ-5** 高潮视觉覆盖 | 视觉高潮 | 机械代理 + 语义单列 | 结构：核心论点镜头（关键词命中）内**唯一素材 ≥ 6** 且 平均保持 ≤ `25 s`；语义：核心镜头任一 MISMATCH → `semantic_state=FAIL`；MATCH ≥ 半数 → PASS；否则 UNKNOWN | `core_detail[]`（scene/asset/window/hits/hold）+ `findings[distinct_assets_in_core_below_min]`、`[semantic_mismatch_in_core]` |
| **DQ-6** 片尾完整性 | Outro | 结构 + 语义单列 | 末 `2` 镜需命中 outro 关键词**且**尾部静音 ≤ `5 s` | `outro_keyword_hits`、`tail_scene_detail[]`（scene/window/asset/旁白片段）、`findings[no_outro_keyword_in_tail]`、`[tail_silence_exceeds].last_scene` |
| **DQ-8** 视觉语义支撑（逐镜）**（6-B/M1 新增）** | 视觉语义支撑 | 语义 | 逐镜复用既有证据：任一镜头 MISMATCH → FAIL；否则 MATCH 占比 ≥ `0.5` → PASS；证据不足 → UNKNOWN；无证据 → NOT_ASSESSABLE | `per_scene[]`（scene/window/asset/逐层判定/verdict）、`layer_counts`、`match_share`、`findings[semantic_mismatch_scenes]`/`[insufficient_semantic_evidence]` |
| **DQ-7** 总评 | 总评 | 汇总（不阻断） | `FAIL > UNKNOWN > NOT_ASSESSABLE > PASS`（6-B/M1 收紧：混有 NA 不再给 PASS） | `counts`、`semantic_states`（语义项单列）、`fail_findings`（把所有 FAIL 的锚点集中列出） |

**证据可回溯契约**：任何 `FAIL` 的返回必须带非空 `findings`，且每个 finding 至少含
`scene_id` / `asset_id` / `[start_s,end_s]` 时间区间 / 证据层名之一 —— 由真值集
`fail_evidence_contract` 固化，并由回归套件对**每个 FAIL 用例**断言。

**机械 vs 语义分类**（授权书第 6 条要求）：
- 机械可测：DQ-2 / DQ-3 / DQ-4（可直接由时间轴、素材、成片复算）；
- 需要语义/人审：DQ-1、DQ-8、DQ-5.semantic_state、DQ-6.semantic_state
  —— **只复用**既有只读证据（4-B/5-A/5-D/Judge），不新算语义；无证据 → NOT_ASSESSABLE，证据不足 → UNKNOWN。

---

## 3. v9 实测结果（真实只读审计；`logs/phase6b_m1_dq_v9.json`）

项目 `p_96efdc03e1aa` / 成片 `t_d0a54bdf1810_draft.mp4`（**未重渲染**，sha256 `22705c7d…` 前后一致）。

| 指标 | 状态 | 关键实测 |
|---|---|---|
| DQ-1 Hook | **UNKNOWN** | S01 四层判定全为 UNKNOWN（4b/5a/5d/judge）；无任何层给 MATCH ⇒ 语义结论**不伪造** |
| DQ-2 素材重复 | **FAIL** | 21 镜仅 **4** 个唯一素材（下限 6，缺 2）；最大占比 **0.3329**（`asset_3f0b94a3f2ac`，7 镜 / 510 s） |
| DQ-3 静态保持 | **FAIL** | 均值 **72.952 s**、最大 **95.0 s**（S07 385–480 s）、**21/21 镜 > 25 s**（占比 1.0）；成片 freezedetect：389 块 / 最长 10.8 s / 冻结总时长 1523.72 s |
| DQ-4 视觉密度 | **FAIL** | **0.822** 镜变/分钟（< 2.0）、唯一素材 0.157/分钟 |
| DQ-5 高潮覆盖 | **FAIL** | 核心论点镜头 **20** 个但仅 **4** 个素材（下限 6）；语义 `FAIL`（MATCH 5 / MISMATCH 7 / UNKNOWN 68） |
| DQ-6 片尾 | **FAIL** | outro 关键词命中 **0**；尾部静音 **570.869 s**（> 5 s）；语义 UNKNOWN |
| DQ-8 视觉语义支撑 | **FAIL** | 21 镜均有证据：MATCH 5 / MISMATCH 7 / UNKNOWN 72；`match_share=0.0595`；MISMATCH 镜头 **S05(245–300 s)、S11(690–770 s)、S18(1245–1330 s)** |
| **DQ-7 总评** | **FAIL** | 计数 PASS 0 / FAIL 6 / UNKNOWN 1 / NA 0；语义项单列：DQ-1 UNKNOWN、DQ-5 FAIL、DQ-6 UNKNOWN、DQ-8 FAIL |

### 3.1 人审发现"再发现"表（6-A 已确认的 7 项）

| id | 人审发现 | 指标 | 期望 | 实测 | 再发现 | 证据定位 |
|---|---|---|---|---|---|---|
| H1 | Hook 视觉错位 | DQ-1 | UNKNOWN | UNKNOWN | **PARTIAL** | 证据层对 S01 全 UNKNOWN ⇒ 机械侧只能证明"无 MATCH"；"错位"本身仍属人工语义判定（不伪造） |
| H2 | 21 镜仅 4 素材重复使用 | DQ-2 | FAIL | FAIL | **FULL** | `per_asset` + 逐素材 `scene_windows` |
| H3 | 全片近乎静止（均值 ≈73 s、17/21 镜 >60 s、冻结 99.46%） | DQ-3 | FAIL | FAIL | **FULL** | `holds[]`（含 S07 385–480 s）+ `freeze_profile` |
| H4 | 镜变密度 ≈0.82/分钟 | DQ-4 | FAIL | FAIL | **FULL** | `scene_changes_per_min` + `longest_scene.window` |
| H5 | 旁白↔画面语义支撑不足 | DQ-8 | FAIL | FAIL | **FULL** | 逐镜层判定 + MISMATCH 镜头时间区间（S05/S11/S18） |
| H6 | 核心论点缺视觉高潮 | DQ-5 | FAIL | FAIL | **FULL** | `core_detail`（20 核心镜 / 4 素材）+ `findings` |
| H7 | 缺片尾/outro | DQ-6 | FAIL | FAIL | **FULL** | `outro_keyword_hits=[]` + `tail_scene_detail` + `tail_silence_s=570.869` |

**再发现结论：6 FULL + 1 PARTIAL + 0 NO**（PARTIAL 即 Hook：机械证据只能到 UNKNOWN，语义结论保留给人审）。

### 3.2 本轮发现并如实记录的一处文档不一致

6-A 审计报告**正文**的"每素材上屏秒数"表写作 485.0/435.0/350.0/205.0 s；而**实测证据**
（`logs/phase6a_audit.json.visual.per_asset`）与 DQ-2 复算结果一致，为 **510/432/355/235 s**
（占比 0.333/0.282/0.153/0.232）。差异在报告正文、不在证据；DQ 侧以证据为准，
且**结论方向不变**（4 素材、最大占比 ≈1/3、远低于下限 6）。该差异已固化进真值集
`documentation_discrepancy`，并由套件 T0f 断言。

---

## 4. Truth set / regression 覆盖

- 真值集：`tests/fixtures/directorial_quality_truth_v1.json`（**33 用例 + 5 汇总用例**），
  规范化 sha256 `022a091895752c3c…`（文件内自锚点 `frozen_sha256`，改真值必须显式重冻结；
  冻结记录：`logs/phase6b_m1_truth_freeze.json`）；
  状态分布：PASS 12 / FAIL 9 / UNKNOWN 3 / NOT_ASSESSABLE 9。
- 覆盖矩阵（授权 7 项全覆盖）：Hook→DQ-1；素材重复/密度→DQ-2+DQ-4；静态镜头→DQ-3；场景变化→DQ-4；
  **视觉语义支撑→DQ-8（新增）**；视觉高潮→DQ-5；Outro→DQ-6；总评→DQ-7。
- 边界用例：DQ-2 占比恰好 0.35、唯一素材恰好 6；DQ-3 保持恰好 25 s、超阈占比恰好 0.20；
  DQ-4 密度恰好 2.0/分钟 与总时长 0（UNKNOWN）；DQ-5 语义 MATCH 恰半数；DQ-8 `match_share` 恰好 0.5；
  DQ-7 混合 PASS+NA（收紧后 → NOT_ASSESSABLE）。
- 不变量断言：① 每个 FAIL 的 findings 非空且可定位；② UNKNOWN/NOT_ASSESSABLE 穷举下 DQ-7 绝不为 PASS；
  ③ 语义项单列且原样保留；④ 阈值快照 == 代码默认值（**不得为让 v9 变好而调阈值**）；
  ⑤ advisory-only（静态 AST + 运行期 DB/目录零改动）。
- 回归套件：`tests/dq_truth_test.py` = **120/120 通过**（含真实 v9 只读审计与再发现期望核对）。

---

## 5. 回归结果

| 项目 | 结果 |
|---|---|
| DQ 真值集回归 `tests/dq_truth_test.py` | **120/120 rc=0，SKIP=0** |
| 既有 DQ 套件 `tests/direction_test.py`（含契约更新） | **25/25 rc=0** |
| PI 侧未受影响的套件 `integrity_truth_test` / `integrity_gates_test` | **243/243** / **45/45** rc=0（PI-1～PI-6 逻辑未改） |
| 25 步回归电池（`phase6b_m1_battery.py`） | **25/25 完成，`all_rc_zero_raw = True`，`rc_nonzero = []`，`rc_pending = []`** |
| step25 `unit_suites` | **54 套件全部 rc=0**（新增 `dq_truth_test` 后 53 → 54） |
| step2 批次（逐项执行） | **24 项：符合预期 24 / 非预期 0**（本轮网络可用，`phase2e_real_provider` 亦通过） |
| 各步耗时之和 | 4711.6 s（本轮出现过环境杀进程后的 `--resume` 续跑） |
| 冻结日志（708 文件） | 运行中改变 170 / 新增 32 / 删除 0 → **回拷逐字节恢复 = True（drift 0）** |

**执行方式的环境约束（如实披露，非放宽）**：前台单次调用上限 10 分钟、后台作业约 13 分钟被环境杀死，
而标准 `3a_regression_batch.py` 需连续约 34 分钟 ⇒ step2 由 `phase6b_m1_batch_items.py`
**逐项执行**（ITEMS/argv 从标准脚本 AST 解析，完全一致；step rc 口径一致），电池以
`--skip 3a_regression_batch` 引用外部记录（汇总标 `executed=externally`，**未伪造**）；
电池支持 `--resume`（沿用首次的**真实**冻结快照，不重复备份）。

---

## 6. 基线完整性与已知边界

### 6.1 基线完整性

| 基线 | 文件数 | zip == manifest |
|---|---|---|
| `5.x-post-final-maintenance-baseline`（r1） | 385 | **True** |
| `5.x-post-final-maintenance-baseline-r2` | 387 | **True** |
| `5.x-post-final-maintenance-baseline-r3` | 389 | **True**（r3 未被覆盖） |
| `5.x-final-baseline` | 384 | **True**（sha256 仍 `be1717b9c7fe9ed9…`） |

- **守卫 24 项**：漂移仅 `agents/editing/agent.py`（M2/M3 的授权变更，**本轮未再改它**）；
  **未授权漂移 = 无**；工作树相对 r3 漂移仍是既有那 6 个文件，**缺失 = 0**。
- **代码指纹**：M3 `398` `e938e3aaec8ffc67…` → **6-B/M1 `400` `9cd07d694a5e0033…`**；
  本轮增量 = **changed 3 / added 2 / removed 0**：
  改 `core/direction.py`、`ops/direction.py`、`tests/direction_test.py`；
  增 `tests/fixtures/directorial_quality_truth_v1.json`、`tests/dq_truth_test.py`。
- **v9 母版未被改写**：sha256 `22705c7d7ea20b40…`、46,761,341 B（未重渲染）。
- **真实 DB 与项目目录**：本轮 DQ 审计与套件运行前后 DB sha256、成片 sha256、`output/` 清单**逐字节一致**。

### 6.2 已知边界（如实列出）

1. **Hook（DQ-1）只能到 UNKNOWN**：现有只读证据层（4-B/5-A/5-D/Judge）对 S01 全部 UNKNOWN
   ⇒ 机械层无法证实/否证"错位"；该结论保留给人工语义判定（本轮记为 **PARTIAL** 再发现）。
2. **DQ-5 的"视觉高潮"是代理指标**：只度量核心论点镜头的素材多样性/保持时长；
   "有无视觉信息升级"的形态判断属人工语义范畴，故其语义项单列（v9 为 FAIL，来自逐镜 MISMATCH）。
3. **DQ-3 的阈值口径差异（不冲突）**：6-A 报告正文用 60 s 描述（17/21 镜 > 60 s），
   DQ-3 冻结阈值是 25 s（21/21 镜超阈、占比 1.0）；同一缺陷在两个阈值下都判 FAIL，**阈值未因 v9 调整**。
4. **DQ-7 汇总口径收紧**（本轮改动）：混有 `NOT_ASSESSABLE` 时不再折算为 PASS（与 PI 侧 M3 同口径）；
   只影响汇总报告，不影响任何阻断。
5. **`tests/direction_test.py` 契约更新**：CLI 指标集合断言由 DQ-1…DQ-6 更新为 DQ-1…DQ-6 + DQ-8
   （DQ-7 是总评）——因为本轮按授权覆盖项新增了 DQ-8；断言强度未降低（并补语义单列断言）。
6. **执行方式偏离标准电池 step2**（逐项 + `--skip` 外部记录），原因与本轮披露同 §5。
7. **文档与证据不一致（本轮发现）**：6-A 报告正文的每素材秒数（485/435/350/205 s）与实测证据
   （`phase6a_audit.json.visual.per_asset` = 510/432/355/235 s）不同；**不改证据、不改 v9 结论**，
   差异已固化进真值集 `documentation_discrepancy` 并由套件断言。
8. **一处自身失误已修复并披露**：6-B/M1 收尾脚本克隆时漏改输出路径，曾覆写
   `logs/phase6a_m3_final_check.json`；已修正为写 `phase6b_m1_final_check.json`，
   并以 M3 脚本重跑恢复 M3 文件（文件内新增 `provenance` 字段说明"重跑时刻状态已含 6-B/M1 变更"，
   M3 时点数值保存在 `PHASE6A_M3_REPORT.md` §3.3/§3.4 与未受影响的 M3 电池/批次证据中）。
9. **DQ 仍 advisory**：未接入 `TASK_BLOCKED`、未改变 `render_output`、未自动修复；
   静态证明（无 agents 引用、无写库/写产物形态）+ 运行期证明（DB/目录零改动）双保险。
10. 未执行：DQ 自动硬化（6-B/M2）、6-C、任何自动换素材/剪辑/重渲染、新 baseline/tag。

---

## 7. 结论与未授权项

- DQ-1…DQ-8 + 总评已成为**可解释、可定位、只读**的度量层：每个 FAIL 都能回溯到 scene / asset / 时间区间 / 证据层。
- **v9 的真实只读审计重新发现了 6-A 人工确认的全部 7 项导演质量问题**（6 FULL + 1 PARTIAL），
  其中 Hook 项保持 UNKNOWN —— 没有为了让结果"好看"而调阈值或伪造语义结论。
- **UNKNOWN 未被当作 PASS**（度量层逐项 + 汇总层穷举 + 语义项单列）。
- DQ 仍为 **advisory/read-only**：未接入 TASK_BLOCKED、未改变 render_output、未自动修复；PI 门禁未改。
- 未执行：DQ 自动硬化（6-B/M2）、6-C、任何自动换素材/剪辑/重渲染、新 baseline/tag。
- **STOP**：本轮只做 6-B/M1 read-only audit。
