# 4.x Final Consolidation / Audit（2026-09-16）

**授权（逐字要点）**：做 4.x 最终收口/审计，**不进入 5.x、不做 UI**；对照 4.x 总 DoD 逐项审计 4-A～4-G；
全量回归证明 3.x 与 4-A～4-G 无退化；保持冻结底座、HITL、append-only、provider/许可闸门、响度契约；
不新增 UI/自动发布/自动语义改选材/自动剪辑/5.x；**检查并明确 4-F 的 BGM LRA≈18 LU 与既有 LRA=11 契约
（先判断 11 是目标值/参考值/硬门槛，未明确前不得改音频链）**；检查 4-G 建议仍只读未执行；
检查网络 PENDING 诚实性；完成最终文档、已知问题台账、DoD 矩阵与 baseline；**无证据不得 PASS**；
输出最终 verdict（PASS / PASS WITH FOLLOW-UP / BLOCKED / FAILED）；完成后 STOP。

**基线**：`4.x-phase4g-baseline.zip` sha256
`1daf93a1a3971ae5b0c22b57b1fe81a23a878d763c543ea801aabd02adf013c3`（实测一致，5,986,380 字节）。

---

## 0. 最终 verdict：**PASS WITH FOLLOW-UP**

- **PASS 的部分**：4-A～4-G 的全部授权项均有可复算证据并达标；3.x 与 4.x 全量回归无退化（见 §2）；
  冻结底座逐字节未改（见 §3）；HITL / append-only / 许可闸门 / 响度契约 / 时间轴权威时长 / 旁白完整性均有守护测试；
  4-G 建议全部只读未执行（见 §5）；网络 PENDING 记录未被改写（见 §6）。
- **FOLLOW-UP 的部分**（**不是失败、不是回归**，但需要下一阶段授权或决策，故不写成纯 PASS）：
  1. **LRA 门槛策略待决策**：审计确认 `LRA=11` **不是硬门槛**（见 §4）；是否要把 LRA 变成硬门槛属**契约变更**，
     需新的授权，本轮**未改音频链、未改契约**。
  2. **两处历史文档措辞已在本轮修正**（文档级，无代码变更）：3-B 把 `TARGET_LRA=11` 与两个硬门槛并列写作"契约常量"，
     易被误读为门槛；4-F 报告曾写"实测 LRA 由 ebur128 给出并记录在 `audio_loudness` 证据中"——**该句不准确**
     （`measure_loudness()` 只解析 I 与 TP，不解析 LRA），本轮已改正并补上实测 LRA 数值。
  3. **4-F 的 BGM 路径使用两遍线性 loudnorm**（同一契约常量；原因见 §4.4）——方法差异已在文档中显式登记。
  4. 累积的既有限制（缓存新鲜度、词典覆盖、节奏阈值、`--by` 无身份认证、候选池规模、ducking 为时间段规则等）
     统一登记进 `docs/KNOWN_ISSUES.md` 的 4.x 小节。

---

## 1. 4.x 总 DoD 矩阵（逐项审计 4-A～4-G）

> 说明：4.x 没有单独的"DoD 总表"文件，**总 DoD = 各阶段授权书列出的要求**（逐字引用见各阶段报告首节）。
> 下表把每条要求与**可复算证据**绑定；证据文件均在 `docs/regression_2x/logs/`。

### 1.1 4-A 只读质量/成本指标

| # | DoD 要求 | 证据 | 判定 |
|---|---|---|---|
| A1 | 只读（不改 DB/任务/产物） | `tests/metrics_test.py` 18/18（`mode=ro`；运行前后 DB sha256/行数不变） | PASS |
| A2 | 输出确定性（可复算） | 同套件：两次运行 JSON 逐字节一致 | PASS |
| A3 | 成本口径=估算（非账单）、外部素材=用量（非计费） | `docs/COST_BOUNDARY.md` + 指标输出字段 | PASS |
| A4 | 不接第二 Provider / 不改默认配置 / 不改冻结契约 | `logs/phase4ab_change_list.json`（改 1 文件：cli 接线只读命令） | PASS |

### 1.2 4-B 离线三态语义核验

| # | DoD 要求 | 证据 | 判定 |
|---|---|---|---|
| B1 | MATCH/MISMATCH/UNKNOWN 三态、离线只读 | `tests/semantic_check_test.py` **29/29**（含 socket 禁用） | PASS |
| B2 | 类别式规则、**无数值阈值** | 规则表 R0–R5（`core/semantics.py`）+ 报告 §口径 | PASS |
| B3 | 同形词义按"词义+语境"解析 | `pico/quest/valve/index…` 12 条歧义条目 | PASS |
| B4 | 真值表钉在冻结产物（禁止改真值凑绿） | 固定为 `a_2ed5f41d6b58`；4-D/4-E/4-F/4-G 各轮均未改 | PASS |
| B5 | 不把"检索到候选"当"语义正确" | 4-E 歧义组 UNKNOWN 10/10（不记 TP）；4-B 全库扫描只作描述性 | PASS |

### 1.3 4-C 人审候选替换闭环（含收尾修复）

| # | DoD 要求 | 证据 | 判定 |
|---|---|---|---|
| C1 | 候选必须**人工显式选择** | `decisions d_a74b1d9f5ab6 / d_9a7600dfeebf / d_a683da3c5d3b`，`made_by=human:project-owner` | PASS |
| C2 | 复用既有 redo/changelog/approval/append-only/version+1 | `changelog #798/#799/#820`（`human_confirmed=1`）；render v1–v5 全部保留 | PASS |
| C3 | 真实完成 ≥1 次替换 | 3 次人工替换（S04/S06/S05）→ v4、v5 成片 | PASS |
| C4 | 校验/许可门禁不被绕过，非法即阻断 | `tests/human_selection_test.py` **18/18**（池外/不可用/许可受限 → 拒绝） | PASS |
| C5 | attribution ⟷ 新时间轴 1:1 | `logs/phase4c_evidence_summary.txt` §4（6/6） | PASS |
| C6 | 收尾消除 S05 连带 MISMATCH | 4-C Fix 报告：语义 `MATCH=6/MISMATCH=0/UNKNOWN=0`，**代码增量 0** | PASS |

### 1.4 4-D 供给韧性底座

| # | DoD 要求 | 证据 | 判定 |
|---|---|---|---|
| D1 | 最小增量：缓存/限流·超时分类/失败可解释/可控降级 | `core/supply.py` + `tools/supply.py`（分类表 32 码、重试计划、缓存、五档阶梯） | PASS |
| D2 | 八条路径覆盖 + fail-closed | `tests/supply_resilience_test.py` **55/55**；`logs/phase4d_paths.json`（8/8 fail-closed） | PASS |
| D3 | 失败不污染既有产物/台账/版本链 | `logs/phase4d_failclosed.json`（文件/任务/产物/事件计数不变、真实 DB 字节不变） | PASS |
| D4 | 默认行为不变（provider=none、缓存默认关闭） | `DEFAULT_POLICY.provider=none`、`supply_cache=False`；`config/config.json` 未改 | PASS |
| D5 | 不接第二 Provider / 不改数据库结构 | `logs/phase4d_change_list.json`（`db_schema_changed=false`） | PASS |

### 1.5 4-E 检索质量量化与 A/B

| # | DoD 要求 | 证据 | 判定 |
|---|---|---|---|
| E1 | 固定测试集 + A/B 基准 | `tests/retrieval_bench_v1.json`（23 语料/21 查询/6 组，入基线） | PASS |
| E2 | 指标可复算并明确 TP/FP/UNKNOWN | `logs/phase4e_ab_results.json`（含指标定义）；A→B：TP 19→43、FP 39→18、域命中 0.6875→1.0 | PASS |
| E3 | 覆盖中文/英文/同义多语言/无结果弱结果 | 六组结果 + 真实网络中文查询探针（0 → 8 候选） | PASS |
| E4 | 不自动改选材、默认不变 | `tools.retrieval` 缺省 v1/不扩展；`config/config.json` 未改 | PASS |
| E5 | 不改 4-B 真值 | `tests/retrieval_quality_test.py` F1/F2 断言（词表 sha256 + 真值钉定） | PASS |

### 1.6 4-F 可选 BGM + 旁白 ducking

| # | DoD 要求 | 证据 | 判定 |
|---|---|---|---|
| F1 | Optional Extension、默认关闭 | `BGM_DEFAULTS.enabled=False`；关闭时 `bgm.applied=false`、无新增输入/滤镜 | PASS |
| F2 | 来源/许可/attribution 明确，未验证即拒绝 | `logs/phase4f_bgm_evidence.json` 校验矩阵（11 类）+ 引擎级 BLOCKED | PASS |
| F3 | 旁白优先、不被覆盖 | 实测：混音中旁白窗口电平与旁白单独**一致**（-33.1 vs -33.1 dB） | PASS |
| F4 | ducking 确定性/可复算/可测试 | 规则 + `volume` 表达式为纯函数；实测 duck 深度 **6.0 dB**（规则 -6 dB） | PASS |
| F5 | 最终母带仍满足 `-16±1 LUFS` / `TP ≤ -1.5 dBTP` / LRA 契约 | 实测 **-15.9 LUFS / TP -8.0 dBTP**；**LRA 语义见 §4**（非门槛；实测成片 LRA 13.8 LU） | PASS（含 §4 澄清） |
| F6 | 十条路径 + 不静默降级 | `tests/bgm_ducking_test.py` **48/48**；失败 → `[BGM_REJECTED] <code>` + BLOCKED | PASS |
| F7 | BGM 关闭时既有输出保持原行为 | 关闭路径无 BGM 输入/滤镜；3-B 套件 32/32；4-C 成片未变 | PASS |

### 1.7 4-G 只读节奏分析与人工建议

| # | DoD 要求 | 证据 | 判定 |
|---|---|---|---|
| G1 | 只读：不改时间轴/时长/旁白/素材/BGM、不 redo、不绕 HITL | `tests/rhythm_advisor_test.py` **34/34** K1–K5；`logs/phase4g_rhythm_evidence.json` 只读证明 | PASS |
| G2 | 覆盖 7 个分析项 | 10 条规则（含静态画面、BGM duck、切换密度、覆盖异常） | PASS |
| G3 | 每条建议含 scene_id/当前时长/规则/证据/动作/风险 | 套件 B2 断言字段齐全；真实项目 11 条建议均可逐条核对 | PASS |
| G4 | UNKNOWN 时不得强行给建议 | 6 类 UNKNOWN；用例 G1–G3/H1 | PASS |
| G5 | 输出确定性、可复算 | 纯函数三次一致 + CLI 三次 stdout 逐字节一致 | PASS |
| G6 | 建议不被误报为已执行 | 文本标注『建议·未执行』；无"已执行/已应用"字样 | PASS |

### 1.8 4.x 全局禁令

| # | 禁令 | 证据 | 判定 |
|---|---|---|---|
| X1 | 不进入 5.x、不做 UI | 无 UI 代码/依赖；`cli.py` 只新增只读子命令 | PASS |
| X2 | 不做自动发布 / 自动剪辑 / 自动语义改选材 | 无发布路径；选材仍由 2-C + 4-C 人工闭环；4-E/4-G 均只给建议 | PASS |
| X3 | 不接第二 Provider | `provider_from_config` 注册点未增（仅 local_ingest/local_catalog/http_catalog/wikimedia_commons） | PASS |
| X4 | 不改数据库结构 | `db/schema.py` 与 4.x 起点**逐字节相同**（§3） | PASS |
| X5 | 默认 `provider=none` 行为不变 | `config/config.json` 逐字节相同；4-A…4-G 各轮 provider=none 回归 | PASS |

---

## 2. 全量回归（3.x + 4-A～4-G）

| 项 | 命令 | 结果 |
|---|---|---|
| 全部套件 | `run_all_suites.py` | **41 total / 41 rc=0 / FAILED: []**（3.x 套件 + 4-A…4-G 新增 7 套） |
| 回归批次 | `phase3a_regression_batch.py` | **24 项 as_expected 24/24**（含 3-A 真实链路、2-C/2-D/2-E、e2e、二进制、ingest） |
| 3-A 真实链路 | `phase3a_real_chain.py --resume p_f4b466a4a024` | **16/16 PASS / FAIL 0 / PENDING 0** |
| 3-B 响度 / 失败路径 | `audio_loudness_test.py` / `phase3b_failure_paths.py` | **32/32** / **12/12** |
| 4-A / 4-B | `metrics_test.py` / `semantic_check_test.py` | **18/18** / **29/29** |
| 4-C / 4-D | `human_selection_test.py` / `supply_resilience_test.py` | **18/18** / **55/55**（八路径 fail-closed 8/8） |
| 4-E / 4-F / 4-G | `retrieval_quality_test.py` / `bgm_ducking_test.py` / `rhythm_advisor_test.py` | **35/35** / **48/48** / **34/34** |
| 4-C 现状复核 | `phase4c_evidence.py` | 版本链 v1–**v5 `t_b8f866ddc062`**；语义 `MATCH=6/MISMATCH=0/UNKNOWN=0`；1:1（6/6） |
| 4-D/4-E/4-F/4-G 证据 | `phase4d/4e/4f/4g_evidence.py` | 全部重跑通过（8/8 fail-closed、A/B 差值不变、BGM 契约达标、节奏只读） |

## 3. 冻结底座审计（4.x 起点 `4.x-phase4ab-baseline` 对比，**字节 sha256** 判定）

| 文件 | 逐字节未改 | 说明 |
|---|---|---|
| `config/config.json` | **是** | 默认配置（含 provider=none）自 4-A 起未动 |
| `src/video_studio/db/schema.py` | **是** | **无数据库结构变更** |
| `src/video_studio/core/materials.py` | **是** | 许可分类/门禁、2-C 分类学未动 |
| `src/video_studio/core/narration.py` | **是** | 旁白完整性 + 时间轴权威时长未动 |
| `src/video_studio/core/semantics.py` + `lexicons/semantics_v1.json` | **是** | 4-B 验证器与词表未动 |
| `src/video_studio/agents/voice/agent.py` | **是** | 配音链未动 |
| `src/video_studio/core/audio.py` | 否（+89/−0，新增 2 函数） | 既有函数仅 `evidence_block` 有改动（加 LRA 说明）；新增 `measure_loudnorm_input`/`normalize_two_pass`（**仅 4-F BGM 路径调用**） |
| `src/video_studio/agents/editing/agent.py` | 否（+259/−12） | 4-D 供给 façade 接线、4-E 检索 opt-in、4-F BGM 闸门/预混（**默认关闭**）；改动函数：`_render`、`_narration_args`、`_build_attribution`、`_build_material_timeline`、`_af` |
| `src/video_studio/tools/material_provider.py` | 否（+40/−11） | 4-D：`TransportError.retry_after_s`、429 `Retry-After`、重试统一走 `core.supply`（默认策略逐值一致） |
| `src/video_studio/cli.py` | 否（+77/−24） | 4-A/4-C/4-G 新增只读或仅记录决定型子命令（不经过 `build_engine()`） |
| `src/video_studio/ops/metrics.py` | 否（+39/−3） | 4-C：`semantic_report` 新增只读 `artifact_id` 参数 + `_art_by_id` |

**无函数被删除**（删除函数数均为 0）；所有改动都在对应阶段报告与 `logs/phase4x_*`、`logs/phase4[acdefg]_change_list.json` 中逐条登记。

## 4. LRA 语义审计（授权第 5 项，**本轮核心**）

### 4.1 代码证据（`logs/phase4x_audit.json` → `lra_audit`）
- `LRA` 在 `src/` 共 **14 处**引用：`core/audio.py`（`TARGET_LRA=11.0`、`loudnorm_filter(lra=…)`、
  `LOUDNESS_CONTRACT["target_lra"]`、两遍法 `measured_LRA` 与证据块）、`agents/audio/agent.py`（写入 `audio_plan.target_lra`）。
- **fail-closed 闸门 `check_contract()` 的源码里没有 LRA**（`gate_source_contains_lra = False`）。

### 4.2 行为证据
- 构造实测 `{"lufs": -16.0, "true_peak_dbtp": -2.0}` 并把 LRA 分别设为 **99 LU** 与 **0.5 LU**：
  **闸门结论都不变（均 ok）** → LRA **不参与判定**。

### 4.3 判定结论（回答"目标值 / 参考值 / 硬门槛"）
> **`LRA=11` 是 ffmpeg `loudnorm` 的"目标参数"（写进滤镜串，作为动态归一的目标动态范围），
> 同时是契约字典 `LOUDNESS_CONTRACT["target_lra"]` 里的"参考/复现值"（写进产物证据便于审计）。
> 它**不是硬门槛** —— 4.x/3.x 的硬门槛只有两项：集成响度 `-16 LUFS ±1`、真峰 `≤ -1.5 dBTP`。**

因此 **BGM 混音的 18.30 LU（预混输入）与既有 `LRA=11` 之间不存在"违约"**：11 是归一器的目标参数，
不是必须达到的实测值。**本轮未修改音频链、未改契约常量**（符合"未明确前不得擅自修改音频链"的要求）。

### 4.4 实测数值（本轮现测，`measure_lra`，ebur128 取 Summary 块）
| 对象 | 实测 I | 实测 LRA | 备注 |
|---|---|---|---|
| 4-C v5 成片（纯旁白） | **-16.1 LUFS** | **2.0 LU** | 3-A/3-B 的参照成片 |
| 4-F 含 BGM 的**预混输入** | -33.8 LUFS | **18.30 LU** | 旁白 + 带 ducking 包络的 BGM（这就是"LRA≈18"的来源） |
| 4-F 两遍母带后的 WAV | **-15.9 LUFS** | **13.8 LU** | 同一契约常量（-16 / TP -1.5 / LRA 11） |
| 4-F 含 BGM 的**交付成片** | **-15.9 LUFS** | **13.8 LU** | AAC 编码后实测；TP -8.0 dBTP |

> **为什么 BGM 路径用两遍线性 loudnorm**：单遍**动态**模式在该混音上系统性低于目标（实测输出 **-19.5 LUFS**，
> 偏差 3.5 LU > 既有 3 LU 收尾校正上限 → 按契约 fail-closed）；两遍法先把 `offset=3.53` 采纳进来再做
> `linear=true` 精确归一，实测落到 -15.9 LUFS。**BGM 关闭时该函数不被调用**，既有单遍链一字未改。

### 4.5 本轮做的文档级修正（**不含代码/契约变更**）
1. `docs/RUNBOOK.md`：新增"LRA 语义"说明（目标参数 ≠ 硬门槛）。
2. `docs/KNOWN_ISSUES.md`：新增 4.x 小节，登记"LRA 门槛策略待决策"等 follow-up。
3. `docs/regression_2x/PHASE4F_REPORT.md` §6：**更正**"实测 LRA 记录在 `audio_loudness` 证据中"的不准确表述，
   并补上本审计的实测数值。

## 5. 4-G 只读复核（授权第 6 项）

| 检查 | 结果 |
|---|---|
| 建议数 / UNKNOWN | 11 条 / 0 条 |
| 全部建议未执行 | `status=SUGGESTION`、`applied=false`、`executed=false` **全部为真**；`applied_changes=0` |
| 两次运行一致性 | 逐字节一致 |
| 运行前后 | 真实 DB 字节未变；五张表行数未变；项目 **74** 个文件（含 5 个成片）逐字节未变 |
| 策略 | `policy.mode=readonly_advisory`、`auto_apply/auto_redo/bypasses_hitl=false` |

## 6. 网络 PENDING 诚实性（授权第 7 项）

| 检查 | 结果 |
|---|---|
| `STATUS.md` 中的 PENDING 记录 | 基线（4-A）内 11 条 → 当前**全部保留**（11/11），仅**追加**本轮观察 |
| `docs/KNOWN_ISSUES.md` / `PHASE4A_4B_REPORT.md` | 在 `docs/` 下、按 `--no-docs` 口径**不在基线 zip 内**（无法字节对比）→ 本轮改为核对**当前内容仍如实标注 PENDING**（分别 1 条 / 6 条） |
| 本轮批次 | 24 项 `as_expected=24/24`，其中 3 项依赖真实网络（`phase2e_failure_paths`、`phase3a_run1_verify`、`phase2e_real_provider`）本轮 rc=0 —— **仅作观察记录**，历史 `PENDING（环境）` 状态与期望值**未改写** |

## 7. 新 baseline（最终收口）

| 项 | 值 |
|---|---|
| 标签 | `4.x-final-baseline` |
| ZIP | `docs/regression_2x/baseline/4.x-final-baseline.zip` |
| zip sha256 / 文件数 / 源码字节 | 见下方"冻结结果" |
| 零漂移校验 | `verify_baseline.py 4.x-final-baseline` → **MATCH** |
| 断点快照 | `snapshots/4.x-final-20260916.{zip,db,json}` |

**冻结结果**：`4.x-final-baseline.zip` = **360 文件 / 7,824,335 字节 / zip sha256
`5992da33fa4cb7ed0ec3767b3137d299def623ca2a645bed18a8cbc50bb9f2c0`**；
`verify_baseline.py 4.x-final-baseline` → **MATCH**（zip 哈希一致、清单 == ZIP 条目、0 缺失、0 漂移）；
快照 `snapshots/4.x-final-20260916.{zip,db,json}`（DB sha256 `b2dc58ccbfcb4f88…`，15,859,712 字节）。

**相对上一基线（`4.x-phase4g-baseline`）的差异（`baseline_delta.py` 实测）：修改 2 / 新增 0 / 删除 0 ——
仅 `CHANGELOG.md` 与 `STATUS.md`（**文档**）。**
→ 这一条本身就是收口审计的核心结论：**本轮没有任何产品代码/测试/配置变更**，`src/`、`tests/`、`scripts/`、
`config/`、`run.py` 与 `4.x-phase4g-baseline` **逐字节一致**（见 §3 的冻结底座审计）。

## 8. 交付物索引（4.x 全阶段）

| 阶段 | 报告 | 证据 | 基线 |
|---|---|---|---|
| 4-A + 4-B | `PHASE4A_4B_REPORT.md` | `logs/phase4ab_*.json/txt` | `4.x-phase4ab-baseline` |
| 4-C | `PHASE4C_REPORT.md` | `logs/phase4c_*` | `4.x-phase4c-baseline` |
| 4-C 收尾 | `PHASE4C_FIX_REPORT.md` | 同上 + `phase4c_evidence.py` 复跑 | `4.x-phase4c-fix-baseline` |
| 4-D | `PHASE4D_REPORT.md` | `logs/phase4d_*` | `4.x-phase4d-baseline` |
| 4-E | `PHASE4E_REPORT.md` | `logs/phase4e_*` | `4.x-phase4e-baseline` |
| 4-F | `PHASE4F_REPORT.md` | `logs/phase4f_*` | `4.x-phase4f-baseline` |
| 4-G | `PHASE4G_REPORT.md` | `logs/phase4g_*` | `4.x-phase4g-baseline` |
| **收口** | **本文件** | `logs/phase4x_audit.json/txt` | **`4.x-final-baseline`** |

**停止点**：按授权完成收口即 **STOP**，等待下一阶段授权（不进入 5.x、不做 UI）。
