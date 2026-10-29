# 6-A 最小实施方案 + DoD + 真值集 + 回归范围（**设计稿；本阶段不实施**）

- 上游：`PHASE6A_AUDIT.md`（只读审计，6 项人工发现全部核实）
- 边界（授权原文）：**本轮只做方案/现状审计**；不修代码、不重渲染、不动 baseline；
  后续实施阶段（6-B）**禁止自动换素材、禁止自动剪辑、禁止自动发布**；Judge / truth set / 阈值 / 多模态 evaluator 的**既有冻结物不得修改**
  （新增度量与门禁**不得**改动 `core/mm_*.py`、`core/multimodal.py`、词表、`tests/fixtures/mm_*truth*` 的语义与阈值）

---

## 1. 目标与非目标

**目标（可度量、可 fail-closed）**
1. 让"旁白覆盖不足 / 音频断裂 / 字幕孤儿 / 音视频轨不一致"成为**渲染前或渲染后的硬门**，不再被 `apad` 掩盖；
2. 让"导演质量"的**可度量红线**（hook 相关性、素材复用、静态保持、视觉密度、高潮覆盖、片尾）产出**只读诊断报告**，
   供人工验片裁决（第一版不阻断、不自动动作）；
3. 输出**测试真值集**与**回归范围**，使上述判定可回归、可复算、可审计。

**非目标（明确禁止）**
- 不实现"自动换素材 / 自动重剪 / 自动重渲 / 自动发布"；
- 不修改 5.x 冻结的 Judge / truth set / threshold / multimodal evaluator / human decision chain；
- 不改动 `5.x-final-baseline`、r1、r2、r3（任何历史基线）。

---

## 2. 最小实施方案（3 个里程碑，M1 可独立交付）

### M1（只读度量层，零阻断风险）
| 新增/改动 | 内容 |
|---|---|
| `src/video_studio/core/integrity.py`（**新**） | 纯函数度量：`narration_coverage()`、`duration_contract_delta()`（复用既有 `core.narration.duration_contract`）、`subtitle_orphans()`、`audio_silence_profile()`（`silencedetect` 解析）、`av_track_consistency()`（ffprobe 三轨）、`timeline_gaps()` |
| `src/video_studio/core/direction.py`（**新**） | 纯函数度量：`asset_reuse()`、`static_hold_profile()`（`freezedetect` 解析 + 逐镜保持）、`visual_density()`、`hook_relevance()`（调用**既有只读** 4-B/5-A/5-D 证据，不新算阈值）、`climax_coverage()`（关键词→镜头→素材变化）、`ending_completeness()` |
| `src/video_studio/ops/integrity.py`、`ops/direction.py`（**新**） | 只读编排（`mode=ro`，不写库、不改产物） |
| `run.py integrity <pid> [--json] [--film-task T]`、`run.py direction <pid> [--json] [--film-task T]`（**新增只读子命令**） | 输出诊断报告；不改任何既有命令行为 |
| `tests/integrity_test.py`、`tests/direction_test.py`（**新**） | 单元 + 夹具（见 §4） |

### M2（硬门接线，fail-closed，**只加判定不加算法**）
| 接线点 | 改动 | 阻断行为 |
|---|---|---|
| `core/narration.py`（**新增判定函数**，不改既有字段语义） | `coverage_gate(contract, policy)`：`shortfall_s > policy.max_shortfall_s` 或 `coverage < policy.min_coverage` → `blocked=True` | 纯判定，无副作用 |
| `agents/editing/agent.py` 渲染前闸门（既有 `blocks` 列表） | **新增两条**：① 短差超阈值；② 覆盖率下界 | `NarrationIncompleteError` → `TASK_BLOCKED`（沿用既有错误码与事件格式） |
| 渲染后（既有 `enforce_loudness_on_film` 之后） | **新增** `integrity.verify_film()`：PI-3/PI-5（静音/孤儿）不达标 → 交付物标 `NOT_DELIVERABLE` + 事件（**不删文件、不自动重渲**） | 阻断"可发布"判定 |
| `config/config.json`（**示例/默认关闭或按授权值**） | 新增 `gates.integrity.*` 阈值段（**不得**改动既有 `llm/hitl/tools` 语义） | 阈值集中、可审计 |

### M3（真值集 + 回归 + 报告接线）
- `tests/fixtures/production_integrity_truth_v1.json`（**新，冻结**）：§4 真值集；
- 报告层（`ops/report.py`，只读展示）：把 PI/DQ 结论并入生产报告咨询节（**只读**，不驱动动作）；
- 回归：§5 范围；电池步骤**不新增**（沿用 25 步），新增套件由 `unit_suites` 自然覆盖。

**预计新增模块清单（8 个文件 + 2 个命令 + 1 段配置）**
```
src/video_studio/core/integrity.py      （新，纯函数）
src/video_studio/core/direction.py      （新，纯函数）
src/video_studio/ops/integrity.py       （新，只读编排）
src/video_studio/ops/direction.py       （新，只读编排）
src/video_studio/cli.py                 （改：+2 只读子命令）
src/video_studio/agents/editing/agent.py（改：+2 条渲染前判定 + 1 处渲染后校验调用）
src/video_studio/core/narration.py      （改：+1 判定函数；既有字段与语义不变）
config/config.json                      （改：+gates.integrity 段，阈值显式）
tests/integrity_test.py                 （新）
tests/direction_test.py                 （新）
tests/fixtures/production_integrity_truth_v1.json（新，冻结）
```
**规模估计**：M1 ≈ 600–900 行（含测试）；M2 ≈ 120–200 行（接线 + 判定）；M3 ≈ 300–500 行（真值集 + 报告 + 回归）。
**风险**：阈值口径（覆盖率下界、最长静音）属**产品/导演决策**，必须由人工给定初始值；本方案只提供可配置项与默认建议值。

---

## 3. DoD（可度量条款；HARD=阻断，ADV=只读诊断/人工裁决）

| 编号 | 条款 | 口径（可复算） | 级别 | 证据 |
|---|---|---|---|---|
| **PI-1** | 旁白覆盖率下界 | `narration_duration_s / timeline_duration_s ≥ 0.90`（可配） | **HARD（渲染前）** | `core/integrity.narration_coverage` + 既有 `voice_output` |
| **PI-2** | 时长契约双侧 | `shortfall_s ≤ max_shortfall_s`（建议 ≤ 30 s 或 ≤ 10% 时间轴）且既有 `excess` 规则保留 | **HARD（渲染前）** | `core.narration.duration_contract` |
| **PI-3** | 成片音频连续性 | 最长静音 ≤ 8 s；静音占比 ≤ 10%；**旁白结束后静音 ≤ 5 s** | **HARD（渲染后）** | `ffmpeg silencedetect` 解析（`core/integrity.audio_silence_profile`） |
| **PI-4** | 音视频轨一致性 | `abs(video_s − audio_s) ≤ 0.5 s` 且 `abs(video_s − timeline) ≤ 1 帧` | ADV（→ 可升 HARD） | ffprobe 三轨 |
| **PI-5** | 字幕时间基与 orphan | cue 必须落在语音有效区间；`orphan_share ≤ 2%`；显示覆盖 ∈ [0.6, 1.1]× 语音时长 | **HARD** | `core/captions` 产出 + `duration_contract` |
| **PI-6** | 段落边界对齐 | 每镜 `abs(voice_start − script_start)` 累计漂移 ≤ 5 s（或每镜 ≤ 0.5 s） | **HARD（渲染前）** | `voice_output.segment_details` × `script.segments` |
| **DQ-1** | Hook 相关性 | S01 的 4-B/5-A/5-D 至少一层 `MATCH`，否则 `HOOK_UNVERIFIED` | ADV（人工裁决；不自动换素材） | 既有只读评估证据 |
| **DQ-2** | 素材复用上限 | 任一素材上屏 ≤ 35% 时长；唯一素材数 ≥ 6（21 镜口径：≥ ceil(scenes/4)） | ADV→HARD 分阶段 | `render_output.material_timeline` |
| **DQ-3** | 静态保持上限 | 单镜保持 ≤ 25 s（可配）；超限镜数占比 ≤ 20% | ADV→HARD 分阶段 | 时间轴 + `freezedetect` |
| **DQ-4** | 视觉密度 | ≥ 2.0 视觉变化/分钟（镜头变化 + 画面内容变化） | ADV | `direction.visual_density` |
| **DQ-5** | 高潮覆盖 | 核心论点镜头内**至少 1 次**素材/画面更换，或存在 ≥1 个"升级型视觉" | ADV | `direction.climax_coverage` |
| **DQ-6** | 片尾完整性 | 存在 outro 段（旁白含收束语 + 画面变化）且**末 10 s 无长静音** | **HARD（结构项）**+ADV（语义项） | `direction.ending_completeness` + PI-3 |
| **DQ-7** | 导演质量总评 | 以上 DQ 项汇总为**只读诊断报告**，附人工验片结论（结构化） | 流程门（人工） | 6-B 报告 + `final_cut`/`publish` 闸门 |

**DoD 验收方式（6-B 结束时必须全部可复算）**
1. `run.py integrity <pid> --json` 与 `run.py direction <pid> --json` 输出与真值集逐例一致；
2. 对**已知失败样本**（本项目 v9）必须复现：PI-1 FAIL（62.77%）、PI-3 FAIL（570.87 s）、PI-5 FAIL（33.8%）、
   DQ-2 FAIL（7/21=33.3% 尚可、唯一素材 4 < 6）、DQ-3 FAIL（17/21 > 60 s）、DQ-5 FAIL、DQ-6 FAIL；
3. 对**历史合规成片**（Run01–04 母片）必须**不误报**为 FAIL（除已知 LIMITATION 项，需在真值集中显式标注）；
4. 阻断路径演练：构造 PI-2 越界样本 → 任务必须 `TASK_BLOCKED`（非 SUCCEEDED），且**不得产出成片**；
5. 冻结件守卫：`core/mm_*.py`、`core/multimodal.py`、词表、`tests/fixtures/mm_*truth*` 与 r3 **逐字节一致**。

---

## 4. 测试真值集设计（`production_integrity_truth_v1.json`，建议 ≥ 16 例）

**真值来源（三类，全部可复算）**
1. **真实失败样本**：`p_96efdc03e1aa` v9（PI-1/PI-3/PI-5/DQ-2/DQ-3/DQ-5/DQ-6 = FAIL，已在 6-A 实测）；
2. **历史合规样本**：Run01–04 母片 + `p_ab2b352e06b8`/`p_8f054c227bd4`（用于"不误报"）；其已知 LIMITATION（运动素材 0 等）在真值集中显式标注为 `KNOWN`；
3. **合成故障夹具**（用 ffmpeg 生成，秒级、离线、确定性）：见下表。

| 例 | 构造 | 期望判定 |
|---|---|---|
| T01 | 旁白覆盖 100%、时长精确 | 全 PASS |
| T02 | 旁白 60%（apad 补静音） | PI-1 FAIL、PI-3 FAIL（长静音） |
| T03 | 旁白 110%（超容差） | PI-2 FAIL（既有 `excess` 阻断路径回归） |
| T04 | 静音 3 s × 3 处（内部碎断） | PI-3 判"最长静音 3 s"PASS（阈值内），但 `blocks=3` 需记录 |
| T05 | 旁白结束→尾部静音 12 s | PI-3 FAIL（尾部静音项） |
| T06 | 字幕 cue 全部落在语音区间 | PI-5 PASS |
| T07 | 字幕 cue 30% 落在静音区（复现 v9） | PI-5 FAIL |
| T08 | 视频轨比时间轴短 1 帧 / 短 21 s（复现 v7） | PI-4 PASS(1 帧) / FAIL(21 s) |
| T09 | 单素材重复 90% | DQ-2 FAIL |
| T10 | 单镜保持 120 s | DQ-3 FAIL |
| T11 | 21 镜 21 素材、8 s/镜 | DQ-2/DQ-3/DQ-4 PASS |
| T12 | 无 outro、末镜为限制声明（复现 v9） | DQ-6 FAIL（结构项） |
| T13 | 有 outro 卡 + 收束语 | DQ-6 PASS |
| T14 | 核心论点镜无画面变化 | DQ-5 FAIL |
| T15 | 旁白段数与脚本段数一致但每段时长错配 | PI-6 FAIL（漂移超阈值） |
| T16 | 音轨缺失/不可探测 | PI-3/PI-4 FAIL（fail-closed，沿用既有 `NARRATION_INCOMPLETE`） |

> 真值集**冻结**（sha256 记录于 manifest/证据）；判定必须**纯函数可复算**，不得含"人类主观打分"；
> 主观项（审美、叙事张力）**不进真值集**，只进人工验片检查单。

---

## 5. 回归范围（6-B 实施后必须全绿才可冻结）

| 范围 | 内容 | 期望 |
|---|---|---|
| 新增套件 | `tests/integrity_test.py`、`tests/direction_test.py` | 全 rc=0，且对真值集 16 例逐例一致 |
| 既有单元套件 | 全部套件（当前 **49** 个，6-B 后预计 **51**） | 全 rc=0（**特别是** `narration_contract_test`、`scene_assembly_test`、`maintenance_fixes_test`(5-K)、`offline_mock_test`(5-L)、`captions_test`(5-M)） |
| 全量电池 | 25 步（步骤序列不变） | 25/25 rc=0；冻结证据日志 drift 0 |
| 阻断路径演练 | T03/T16 触发 `TASK_BLOCKED` 且不产成片 | 必须 BLOCKED（**不得** SUCCEEDED） |
| 冻结件守卫 | `core/mm_*.py`、`core/multimodal.py`、`ops/mm_*.py`、词表、`tests/fixtures/mm_*truth*`、`core/selection_review.py`、`core/audio.py`、`core/materials.py` | 与 r3 **逐字节一致**（新增度量不得改其语义） |
| 基线 | 冻结新 tag（如 `6-a-baseline`） | `verify_baseline` MATCH；**不得覆盖** `5.x-final-baseline`/r1/r2/r3 |
| 端到端 | 一次"合规"重跑（mock 离线）与一次"刻意失败"重跑 | 前者 PI/DQ 全 PASS；后者按真值集 FAIL 且被门阻断 |

---

## 6. 零改动复核（本轮）

```powershell
python docs\regression_2x\verify_baseline.py 5.x-post-final-maintenance-baseline-r3   # 期望 MATCH
python docs\regression_2x\phase5m_code_fingerprint.py now                              # 期望 == c495dd64913c…
(Get-FileHash docs\regression_2x\baseline\5.x-final-baseline.zip -Algorithm SHA256).Hash # 期望 be1717b9…
```

> 结论：**本轮（6-A）只写了 `docs/` 下的审计文档与只读审计脚本，未改动 `src/ config/ tests/ scripts/`、未重渲染、未改任何基线。**

---

## 7. 建议的阶段切分（待授权）

| 阶段 | 内容 | 门 |
|---|---|---|
| **6-B** | 实施 M1（只读度量层 + 2 个只读子命令 + 2 个测试套件 + 真值集冻结） | 真值集全通过 + 电池全绿 + 不误报历史合规样本 |
| **6-C** | 实施 M2（渲染前/后硬门接线 + 阈值入 config + 阻断路径演练） | DoD PI-1…PI-6 全绿；阻断演练 BLOCKED |
| **6-D** | DQ 红线分级（ADV→HARD）与人工验片结构化闸门（`final_cut`/`publish` 前检查单） | 人工验片结论可追溯；发布候选必须 DQ 全 PASS |
| **6-E** | 用 6-A 已知失败样本（v9）作为**验收靶**，端到端证明"该被拦住的一定被拦住" | 靶样本全部 BLOCKED/FAIL，且给出可执行整改建议（不自动执行） |
