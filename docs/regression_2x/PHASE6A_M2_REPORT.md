# 6-A / M2 —— Production Integrity 硬门接线报告

- 阶段：**6-A/M2（只接线 PI；DQ-1…DQ-7 保持只读/建议）**
- 前置：6-A 审计（`PHASE6A_AUDIT.md`）、6-A 计划/DoD（`PHASE6A_PLAN_DOD.md`）、6-A/M1 只读度量层（`PHASE6A_M1_REPORT.md`）
- 本轮**不**做：M3 / 6-B / 6-C、DQ 硬化、自动换素材/剪辑/修复/重渲染、新基线标签
- 本轮**不**动：5.x Final 基线、r1/r2/r3 基线、历史 Judge / truth set / threshold / multimodal evaluator
- 证据目录：`docs/regression_2x/logs/phase6a_m2_*.json`；M2 套件：`tests/integrity_gates_test.py`

---

## 1. 变更清单（源码 / 测试）

| 文件 | 状态 | 行数 | 说明 |
|---|---|---|---|
| `src/video_studio/core/integrity.py` | 修改（M1 新增文件，M2 追加硬门段） | 560 | 硬门判定实现（只接线 PI，未新增任何"D 级"规则）；sha256 `cd763399be50e427…` |
| `src/video_studio/agents/editing/agent.py` | 修改（**相对 r3：+75 行 / −0 行**） | 1441 | 渲染前 / 渲染后接线点；sha256 `da06ab48baa10134…`（逐行取证见 §8.2） |
| `tests/narration_contract_test.py` | 修改（测试契约更新，见 §6b） | 500 | 短旁白由"产出成片"改为"硬门阻断"；`1d4c4f0fb98df529…` |
| `tests/bgm_ducking_test.py` | 修改（测试夹具更新，见 §6b） | 496 | 夹具旁白由 5 s 改为 13 s；`db741f9360bd0547…` |
| `tests/pipeline_mock.py` | 修改（测试夹具更新，见 §6b） | 177 | 用例内替换 TTS 为"按计划时长合成"；`b849052edfdc9280…` |
| `tests/integrity_gates_test.py` | **新增**（M2 套件，45 项断言） | 502 | 反例集 + 阶段正确性 + 只读证明 + 判据校正回归；`27bff07b39ecae6f…` |
| `docs/regression_2x/PHASE6A_M2_REPORT.md` | 新增（本报告） | — | 交付说明 |
| `docs/regression_2x/phase6a_m2_*.py`（battery / guard_check / agent_diff / final_check / v9_gate / legacy_probe / shortfilm_probe / interim_blocks / precheck / preserve_and_restore） | 新增 | — | M2 专用取证与回归脚本（证据可复算） |
| `docs/regression_2x/run_ingest_test.py`（258 行）、`run_all_tests.py`（206 行）、`phase4f_evidence.py`（280 行） | 修改（既有回归脚本的夹具/配置更新，见 §6b） | — | 三者原本依赖"短旁白也能出片" |

**未改动（逐项确认）**：`config/config.json` 与 `config/config.mock.json`（**零**改动；门限默认值在代码内，
仅可用 `config.gates.integrity.*` 加法覆盖）、`core/direction.py`、`ops/integrity.py`、`ops/direction.py`、
`core/narration.py`、`core/captions.py`、`core/audio.py`、`core/materials.py`、全部 `mm_*` 评估件、
`tests/fixtures/production_integrity_truth_v1.json`（M2 只读取）。

**源码/测试指纹（`src config tests scripts` + 根文件）**：M1 `395` 文件 `da1be48c58bc7cb9…`
→ M2 见 §8（增量仅为本轮授权文件，`removed = 0`）。

---

## 2. 门禁接线位置（精确到阶段）

1. **渲染前硬门** —— `agents/editing/agent.py::_render`，`narration_payload is not None` 分支内、
   **任何 ffmpeg 调用之前**：
   `core_integrity.pre_render_gate(script.segments, narration_payload, timeline_total, gate_policy(cfg), narration_duration_s=<实测>)`
   - 旁白时长传**实测值**（对 narration 音轨 ffprobe，与既有闸门同源）；实测不可得才回退产物自报字段。
   - `blocked` ⇒ `TASK_BLOCKED`（`human_visible=True`）+ `raise NarrationIncompleteError`
     （码 `[NARRATION_INCOMPLETE]`，detail 内嵌 `integrity_gate`）。
2. **渲染后硬门** —— 同文件，成片时长校验 / 响度契约 / 抽帧核验**之后**，**写 `render_output` / `attribution` 之前**：
   `core_integrity.post_render_gate(out_abs, timeline_total, cues, narration_end_s, narration_expected, ffmpeg, ffprobe, gate_policy(cfg))`
   - `blocked` ⇒ `TASK_BLOCKED` + `raise core_integrity.ProductionIntegrityError`
     （码 `[PRODUCTION_INTEGRITY_FAILED]`，`detail.stage="post_render"`）。
3. **证据落盘**：仅在通过时写 `render_output`，新增只读字段
   `production_integrity{policy, code, pre_render{blocked,metrics(各 PI 状态),disabled}, post_render{blocked,metrics,narration_expected}, note}`。
4. **失败传播**：沿用引擎既有语义（异常 → FAILED → 重试 → BLOCKED）；**引擎未改**。
5. **阻断消息可读性**：`reasons` 放在 detail JSON 最前，保证被截断的落库错误仍保留人类可读原因。
6. **未接线项**：DQ-1…DQ-7 **零接线**（仍只在 `run.py direction` 只读报告输出）。

---

## 3. 每个 PI 的行为与阈值（默认策略 = 授权点名的判据）

| PI | 阶段 | 阻断判据（默认） | FAIL | UNKNOWN / NOT_ASSESSABLE | 类别 |
|---|---|---|---|---|---|
| PI-1 旁白覆盖率 | 渲染前 | `narration/timeline ≥ 0.90` | 阻断 | **fail-closed 阻断** | hard gate（授权点名） |
| PI-2 双侧时长契约 | 渲染前 | excess 沿用既有规则；shortfall ≤30 s 且 ≤10% | 阻断 | **fail-closed 阻断** | hard gate（授权点名） |
| PI-3 成片音频连续性 | 渲染后 | 最长静音 ≤8 s、占比 ≤10%、尾部 ≤5 s（silencedetect −45 dB/≥2 s） | 阻断 | **fail-closed 阻断** | hard gate（授权点名） |
| PI-4 AV 轨道一致性 | 渲染后 | 缺轨；`\|video−audio\| ≤1.0 s`；`\|video−timeline\| ≤1.0 s`；起始差 ≤0.5 s | 阻断 | **fail-closed 阻断** | 正式检查（授权书明列 post-render 必 fail-closed 的 "AV tracks"） |
| PI-5 字幕 orphan | 渲染后 | `orphan_share ≤ 2%`（cue.start > 旁白结束即 orphan） | 阻断 | 有旁白计划 ⇒ **fail-closed 阻断**；无旁白计划且旁白结束未知 ⇒ 仅记录 | hard gate（授权点名） |
| PI-6 段落边界漂移 | 渲染前 | 最大累计漂移 ≤5 s | 阻断 | **仅记录（如实记 UNKNOWN，绝不记 PASS）** | 正式检查（见 §4） |
| （PI-4 帧数差 / PI-5 显示覆盖比） | 渲染后 | —— | **不参与阻断**（仅度量报告，见 §4） | —— | 度量项 |

**策略覆盖（加法，不改任何既有 config 键语义）**：
`config.gates.integrity.{gate_enabled, post_render_enabled, block_on_unknown, block_on_unknown_pi6, <各阈值>}`；
未配置时全部走代码内默认值（默认开启）。显式关闭属可审计配置动作（M2 套件 G7f 覆盖该分支）。

---

## 4. 判据校正（本轮自查发现并修正的两处"越权收紧" + PI-6 口径）

> 原则：M2 只接线授权点名的检查项；**不得**因为 M1 的 advisory 默认值而收紧既有冻结契约，
> 也不得让"度量项"变成未经授权的阻断项。

### 4.1 PI-4 帧数差：从阻断项改为**度量报告项**
- 事实（真实成片实测）：10 s / 30 fps 成片 ffprobe 报 `nb_frames=299`，而 `duration×fps=298.0`
  ⇒ 帧数差 1.0000… > 阈值 1 被误判违约（浮点边界）。ffprobe 的 `nb_frames` 与 `duration×fps`
  相差 ±1 帧属正常报数差异，**不是音视频不同步**。
- 处置：`frame_count_delta` 仅报告（`frame_count_is_blocking=False`）；PI-4 判据=缺轨 / 轨差 / 时间轴差 / 起始差。
- 同时把 `max_av_track_delta_s`、`max_video_timeline_delta_s` 由 M1 advisory 的 `0.5 s` **对齐为 1.0 s**，
  与产线既有冻结容差 `VIDEO_DURATION_TOLERANCE_S = 1.0 s` 一致（用 0.5 s 会把"既有契约判合格"的成片判违约）。
- 回归证据：M2 套件 G5c/G5d/G5e；`phase2c_fault_matrix` 的 A/C 出片自动恢复（无需改其夹具）。

### 4.2 PI-5 显示覆盖比：从阻断项改为**度量报告项**（硬门判据 = orphan）
- 事实：授权点名的 PI-5 判据是**字幕 orphan**。本产线字幕按时长=阅读速度给定、长镜头内留白，
  `display/narration < 0.60` 是**正常形态**（例如 `audio_loudness_test` 的 14 s 合规成片为 0.49）；
  要改变它必须改字幕生成逻辑，而"不得修改字幕生成逻辑"正是本轮授权前提。
- 处置：`orphan_fail`（占比 >2%）→ 阻断；`coverage_fail` → 仅记录（`coverage_is_blocking=False`），
  并在阻断/证据 reasons 里写明"仅记录不阻断"。
- 回归证据：M2 套件 G4f/G4g；`audio_loudness_test` D1 由 FAIL 恢复为 PASS（32/32）。

### 4.3 PI-6 逐段时长缺失：UNKNOWN 只记录（仍绝不记 PASS）
- 授权书把 PI-6 与 PI-4 并列为"按 6-A 设计稿接入为**正式完整性检查**"，不在四道 hard gate 清单内。
- 取证（只读）：`logs/phase6a_m2_legacy_probe.json` —— 全库真实 `voice_output` **765** 个中
  **545** 个**没有** `segment_details`（逐段真实 TTS 时长；本报告定稿时的实测计数）。这些产物对应的成片
  旁白完整、时长达标；若仅因缺字段就 fail-closed，等于让它们在重渲染时被误判阻断（6-A 设计稿
  之外的新规则 + 误伤正常成片）。
- 处置：PI-6 **明确违约（漂移 >5 s）→ 阻断**；**不可评估 → 只记 UNKNOWN（绝不记 PASS）**。
  可用 `config.gates.integrity.block_on_unknown_pi6 = true` 显式收紧。
- 不构成绕过通道：旁白是否完整由 PI-1/PI-2 用**实测旁白时长**独立 fail-closed 把关（§5 反例集）。

---

## 5. 反例集与断言证据

### 5.1 M2 套件 `tests/integrity_gates_test.py` = **45/45 rc=0**

| 反例 | 期望 | 实测 |
|---|---|---|
| v9 形态短旁白（961.656 s / 1532.0 s，真实数值） | 渲染前阻断 | **BLOCKED**（PI-1 FAIL 0.6277、PI-2 FAIL shortfall 570.344、PI-6 FAIL 552.16） |
| 尾部超长静音（20 s 成片仅 12 s 有声） | 渲染后阻断 | **BLOCKED**（PI-3 FAIL：尾静音 ≈8 s > 5 s、占比 0.4 > 0.1） |
| 片中长静音（40 s 成片中间 12 s 静音） | 渲染后阻断 | **BLOCKED**（PI-3 FAIL：最长 ≈12 s > 8 s、尾部静音 = 0，证明不是"只看尾部"） |
| 字幕 orphan（3/10 条落在旁白结束之后） | 渲染后阻断 | **BLOCKED**（PI-5 FAIL：orphan 3 条 / 占比 0.30 > 0.02） |
| 音视频轨不一致（video 8 s / audio 20 s） | 渲染后阻断 | **BLOCKED**（PI-4 FAIL：轨差 ≈12 s） |
| 正常完整旁白（20 s/20 s、无静音、字幕对齐、轨道一致） | 不阻断 | **PASS**（PI-1…PI-6 全 PASS；端到端 11 s 成片照常登记 `render_output`） |
| UNKNOWN / NOT_ASSESSABLE | 绝不等于 PASS | PI-1 不可证 ⇒ 阻断；PI-3 成片不存在 ⇒ 阻断；PI-5 无 cue（有旁白计划）⇒ 阻断；`summarize` 含 UNKNOWN ⇒ overall=UNKNOWN |
| 判据校正回归 | 不误伤合规片 | G5c/G5d（±1 帧报数 → PASS、容差对齐 1.0 s）、G5e（轨差 0.7 s 不判违约）、G4f/G4g（覆盖比不足 → 仅记录不阻断） |

### 5.2 v9 真实成片只读判定（`logs/phase6a_m2_v9_gate.json`，**未重渲染**）

把既有 `projects/p_96efdc03e1aa/output/t_d0a54bdf1810_draft.mp4`（46,761,341 B，
sha256 `22705c7d7ea20b40…`）直接喂给 M2 硬门：

| 阶段 | 结果 | 关键实测 |
|---|---|---|
| 渲染前 | **BLOCKED** | PI-1 0.6277（短差 570.344 s）、PI-2 双侧违约、PI-6 最大漂移 552.16 s / 末段 −568.344 s |
| 渲染后 | **BLOCKED** | PI-3 570.869 s 静音（占比 0.3726、尾部 570.869 s）；PI-5 216 cues / 73 orphan（0.338、首条 967.4 s）；PI-4 PASS（轨差 0.04 s） |

只读取证：成片 sha256 与 mtime **不变**、`output/` **零新增文件**、**未重渲染**（授权禁止）。
数值与 6-A/M1 实测逐项一致（可复算）。

### 5.3 "短旁白成片本就有长尾静音"的独立取证（`logs/phase6a_m2_shortfilm_probe.json`）

历史 mock/早期用例成片（旁白 4.248 s / 时间轴 17 s）实测：**尾静音 13.26 s（占全片 78%）**、
PI-1 覆盖率 0.2499 ⇒ 它们**本就**是"PI-3 成片静音"违约片（不是被 M2 误伤的合规片）。
M2 只是把这类片**提前拦在 ffmpeg 之前**，而不是等渲染完再拦。

---

## 6. 阶段正确性与"零错误交付物"证据

- **短旁白拦在 ffmpeg 之前**（G9a/G9b）：端到端抛 `[NARRATION_INCOMPLETE]` 且 reason 含 PI-1；
  `eng.written == []`（零 artifact）、`output/` 无新增 mp4、`TASK_BLOCKED` 事件 `human_visible=True`。
- **违约成片拦在交付物落库之前**（G9c–G9f）：仅 PI-3 违约（PI-1/PI-2/PI-6 全 PASS）的成片 ⇒
  `[PRODUCTION_INTEGRITY_FAILED]`、`detail.stage="post_render"`；**`render_output` 与 `attribution` 均未写**
  （中间 mp4 仅作为证据留在临时目录，**不登记为交付物**）。
- **只读性**（G8）：两次判定逐字节一致（可复算）；判定不改写成片（sha256 不变）；零新增媒体文件；
  所有度量/门禁输出带 `read_only=True` / `enforced=False`。

---

## 6b. 本轮伴随的测试/夹具契约更新（**因为夹具本身在产出违约成片**，不是因为放宽门禁）

> 说明：以下夹具在 M2 之前"能出片"，是因为**当时的门禁不检查旁白覆盖率/成片静音**；
> 实测它们产出的成片属"短旁白 + 长尾静音"违约类（§5.3）。M2 之后这类成片不得再作为交付物，
> 故夹具改为"合规成片"，其**原验证意图全部保留**（BGM/ducking/管线接线/素材装配/响度契约）。

| 文件 | 原夹具问题（实测） | 更新 | 更新后 |
|---|---|---|---|
| `tests/narration_contract_test.py` | G3 原期望"9 s 旁白 / 11 s 时间轴"出片成功 | 改为期望硬门阻断（PI-1/PI-2）；新增完整旁白 PASS 用例；I 组改用完整旁白进入产出后校验 | **45/45** |
| `tests/bgm_ducking_test.py` | 旁白 5 s / 时间轴 14 s（覆盖率 0.36）⇒ 9 s 尾静音 | 旁白 6.5+6.5=13.0 s（覆盖率 0.93、尾静音 1 s）；B1/B2/B3/B8 与 E1/E4 测量窗随新时长对齐 | **48/48** |
| `tests/pipeline_mock.py` | mock 脚本计划 15 s，真实 TTS 仅 ~4.2 s ⇒ ~13 s 尾静音 | 用例内把 TTS 工具替换为"按计划时长（16 s）合成的本地旁白"（**不改任何 config**） | **12/12** |
| `docs/regression_2x/run_ingest_test.py` | 同上（脚本经 CLI 子进程驱动，无法 patch 工具） | 临时配置（不动基线 config）把 TTS provider 置 `none`，走产线既有"配音计划模式"，继续验证 ingest→素材时间轴装配→成片 | **VERDICT: PASS**（`material_assembly=SUCCEEDED`） |
| `docs/regression_2x/run_all_tests.py`（batch 项 `e2e_mechanical`） | 同上 | 同上（临时计划模式配置） | **3 组 SETTLED**，render 复为 SUCCEEDED |
| `docs/regression_2x/phase4f_evidence.py` | 旁白 5 s / 14 s ⇒ BGM 渲染被前置门阻断、证据丢失 | 夹具旁白 13 s；`outside`/`tail` 测量窗移到片尾释放窗 | render=**SUCCEEDED**；fail-closed 用例恢复 `BGM_SILENT` / `BGM_LICENSE_RESTRICTED` |
| `docs/regression_2x/phase2c_fault_matrix.py` | A/C 出片被 PI-4（±1 帧报数）误伤 | **无需改夹具**：§4.1 判据校正后自动恢复 | rc=0（A/C 出片、B/D BLOCKED） |

---

## 7. 全量回归（M2 测试 + 52 套件 + 25 步电池 + 环境项分列）

### 7.1 M2 与受影响套件（本地复跑，全部 rc=0）

| 套件 | 结果 |
|---|---|
| `tests/integrity_gates_test.py`（M2 新增） | **45/45** |
| `tests/narration_contract_test.py`（契约更新后） | **45/45** |
| `tests/audio_loudness_test.py`（判据校正后恢复） | **32/32** |
| `tests/bgm_ducking_test.py`（夹具更新后） | **48/48** |
| `tests/pipeline_mock.py`（夹具更新后） | **12/12** |
| `tests/offline_mock_test.py` | **23/23** |
| `tests/integrity_test.py`（M1 只读度量） | **28/28** |
| `tests/direction_test.py`（DQ 只读，未改动） | **25/25** |
| `tests/maintenance_fixes_test.py`（含 ops 只读守卫） | **28/28** |

### 7.2 全库套件预检（`logs/phase6a_m2_precheck.json`，只记录 rc、不写冻结日志）

**52 个套件 → 52 rc=0，failed = []**。

### 7.3 25 步回归电池（`phase6a_m2_battery.py`；步骤序列 AST 取自 `phase5f_regression.py`）

| 指标 | 结果 |
|---|---|
| 步骤 | **25 / 25 rc=0**（`all_rc_zero_raw = true`，`rc_nonzero = []`） |
| 总耗时 | 4630.7 s |
| step25 `unit_suites` | **52 套件全部 rc=0**（`FAILED: []`） |
| step2 回归批次 | **24 项 as_expected = 24/24，非预期结果 = 无** |
| 冻结日志（708 文件） | 运行中改变 170 / 新增 0 / 删除 0 → **回拷后逐字节恢复 = True**（drift 0） |
| step1 `3a_real_chain` | VERDICT: PASS（PASS=16 FAIL=0），成片 104.0 s == 时间轴 |
| step4f `phase4f_evidence` | BGM 渲染 **SUCCEEDED**、旁白 COMPLETE、响度 ok=True；BGM fail-closed 用例恢复 `BGM_SILENT`/`BGM_LICENSE_RESTRICTED` |
| `e2e_mechanical` | 三组 **SETTLED**（且 render 复为 SUCCEEDED） |
| `run_ingest_test` | **VERDICT: PASS**（`material_assembly=SUCCEEDED`） |

### 7.4 环境项（单独分列，不计入 M2 能力判定）

- **本轮**：网络可用 ⇒ `cost_boundary`、`phase2e_failure_paths`、`phase2d_provider_e2e`
  三项均转绿（24/24）。批次自身把 `phase2e_failure_paths` / `phase3a_run1_verify` /
  `phase2e_real_provider` 标注为"依赖真实网络"。
- **同一 M2 代码的更早时段**（本报告 §4 校正之前的运行）曾出现：
  `cost_boundary` = `URLError [WinError 10061]`（余额 API 连接被拒）、
  `phase2e_failure_paths` = 6 项故障注入全部塌缩为 `PROVIDER_DOWNLOAD_FAILED`、
  `phase2d_provider_e2e` = 外部素材 D5–D10 失败。
  **这些是环境（网络出口）问题，不是 M2 能力项**；本报告不把它们计入 M2 结论，也不改写历史 PENDING 记录。

---

## 8. 基线、守卫与指纹

### 8.1 基线完整性（ZIP sha256 == manifest，逐项核对）

| 基线 | 文件数 | zip == manifest |
|---|---|---|
| `5.x-post-final-maintenance-baseline`（r1） | 385 | **True** |
| `5.x-post-final-maintenance-baseline-r2` | 387 | **True** |
| `5.x-post-final-maintenance-baseline-r3` | 389 | **True**（r3 工件未被覆盖） |
| `5.x-final-baseline` | 384 | **True**（sha256 仍为 `be1717b9c7fe9ed9…`） |

### 8.2 守卫（`logs/phase6a_m2_guard_check.json`）

- 守卫 24 项：**漂移仅 1 项** = `src/video_studio/agents/editing/agent.py`（**M2 授权接线点**）；
  **未授权漂移 = 无**。其余 23 项（`mm_*` 评估件、`core/narration.py`、`core/captions.py`、
  `core/audio.py`、`core/materials.py`、voice/subtitle agent、MM 真值集与 5-D/5-E 测试）与 r3 **逐字节一致**。
- 工作树相对 r3 的漂移（仅基线成员文件）：`agents/editing/agent.py`（M2）、`cli.py`（M1 只读子命令）、
  `tests/narration_contract_test.py`、`tests/bgm_ducking_test.py`、`tests/pipeline_mock.py`（M2 契约/夹具）、
  `tests/maintenance_fixes_test.py`（M1 守卫更新）；**缺失 = 0**。
- **授权变更逐行取证**（`logs/phase6a_m2_agent_diff.{json,txt}`，对照 r3 基线 ZIP 内同名文件）：
  `agents/editing/agent.py` 相对 r3 = **`added 75 / removed 0 / hunks 5`**；
  新增行全部属 M2 门禁接线（2 行 import、pre/post gate 调用、`production_integrity` 证据字段、M2 注释）。
  **r3 侧没有任何一行被删除**（不存在改写既有逻辑）。

### 8.3 代码/测试指纹（`src config tests scripts` + 根文件）

| 时点 | 文件数 | 聚合 sha256 |
|---|---|---|
| 6-A/M1 | 395 | `da1be48c58bc7cb9…` |
| 6-A/M2 | 396 | `f15027be4f7cd8e4…` |

增量 = **changed 5 / added 1 / removed 0**：
`core/integrity.py`、`agents/editing/agent.py`、`tests/narration_contract_test.py`、
`tests/bgm_ducking_test.py`、`tests/pipeline_mock.py`（改）；
`tests/integrity_gates_test.py`（增）。**无计划外文件被改。**

### 8.4 历史母版与冻结证据未被改写

- **v9 母版成片**：`projects/p_96efdc03e1aa/output/t_d0a54bdf1810_draft.mp4`
  sha256 `22705c7d7ea20b40d91120146066b89ab2b5fa5c1a1cab18f5346d4c66497651`、46,761,341 B、
  mtime **2026-09-21 22:55:50** ⇒ 与 M1 记录**逐字节一致**（**未重渲染**）。
- **遗留 `5d_frozen_check`（5-D 时代快照，rc=0）**：M1 电池当日 drift = 160，本轮 = 165；
  逐项比对后**新增漂移恰好 5 个**，且都是 M2 内容变更导致的证据文件：
  `phase2c_traceability.md`、`phase3a_narration_contract.log`、`phase4f_evidence_summary.txt`、
  `suite_bgm_ducking_test.log`、`suite_narration_contract_test.log`（无"M1 有而本轮无"的项）。
  该步是历史遗留检查（比较 5-D 时点的 488 个文件），其 drift 是既有状态，**不是 M2 的漂移**；
  权威口径是本电池自带的"备份 → 运行 → 回拷"（**drift 0 / 恢复 True**）。
- **历史取证记录保留不改**（append-only）：M2 实现期间（§4 判据校正之前）产生 18 条
  `[PRODUCTION_INTEGRITY_FAILED]` / `[NARRATION_INCOMPLETE] render 前闸门` 阻断记录，
  其中 12 条为渲染前、6 条为渲染后；5 条含 `PI-6 UNKNOWN`（旧口径）。
  这些记录**原样保留**（不改写历史），其判决口径已在 §4 说明。
  取证：`logs/phase6a_m2_interim_blocks.json`。

---

## 9. 结论、未授权项与 STOP

- **结论**：在授权范围内完成 M2 接线 —— PI-1/PI-2（渲染前）、PI-3/PI-4/PI-5（渲染后）成为正式门禁检查，
  PI-6 按"正式完整性检查"口径接入；**短旁白不再被默认为合法完成**；`apad` 仍是合法音频处理
  （ffmpeg 参数层证据 J1–J3 未变），但不再能掩盖旁白覆盖不足；违约成片**不登记交付物**。
- **v9**：真实成片只读判定 **BLOCKED**（与前次人类裁定 FAIL、登记 #67 一致），未重渲染、未改 r3。
- **未授权/未执行**：DQ 硬化（仍只读/建议）、M3/6-B/6-C、任何自动换素材/剪辑/修复/重渲染、
  新基线标签、5.x Final 与 r1/r2/r3 的任何改动。
- **STOP**：本轮只做 M2，报告如上，等待下一步授权。
