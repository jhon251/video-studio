# 3.x Phase 2-C 报告：素材不足降级分类学 + 完整可追溯

- 日期：2026-09-13
- 授权范围（逐字）：**"授权进入 Phase 2-C：素材不足降级分类学 + 完整可追溯"**；"完成后立即停止，等待下一阶段授权。不要开始外部 Provider、BGM 或其他后续工作。"
- 交付：① 六类素材不足诊断 ② 明确的 fallback 策略（含 HITL / 是否可入最终渲染）③ 禁止静默降级的代码级保证 ④ 逐镜头完整可追溯 ⑤ 真实故障 + 真实成片证据
- 未做（越界即不做）：外部素材 Provider、BGM、自动发布、UI 大改、新 Agent、语义级镜头↔旁白对齐、成本对账、Git tag。
- 未触碰：Claim/HITL 核心机制、append-only、exec isolation、断点恢复、既有 task/artifact/event 契约（**未新增事件类型、未新增 artifact 类型**）、Phase 2-B.1 旁白完整性闸门、timeline 权威时长契约。

---

## 0. 结论先行（判定行）

| # | 判定项 | 结论 |
|---|---|---|
| 1 | 六类诊断可区分且落盘（NO_CANDIDATE / LOW_MATCH / ASSET_UNUSABLE / ASSET_CONFLICT / ASSET_EXHAUSTED / ASSEMBLY_BLOCKED） | **PASS**（确定性单测 40/40 + 4 个真实故障项目） |
| 2 | 每种降级都有 state/reason/original_requirement/selected_asset/selection_reason/needs_hitl/allowed_in_final_render | **PASS**（逐镜头记录，`phase2c_trace.py` 断言 38/38） |
| 3 | 禁止静默降级（不伪装命中 / 不把占位当素材 / 不改写 BLOCKED / 不只改状态不看画面） | **PASS**（含成片抽帧核验：分配素材必须在窗口内出现，占位必须被证实不是素材） |
| 4 | 逐镜头完整可追溯（scene_id→需求→候选与分数→最终选择→分类→原因→asset 指纹→是否入 timeline→是否出现在成片→证据） | **PASS**（`logs/phase2c_traceability.md` / `.json`） |
| 5 | 真实故障证据：正常命中 / 无候选 / 低匹配 / 素材不可用 各有真实项目与真实成片（或真实阻断） | **PASS**（`PHASE2C_FAULT_REPORT.md`） |
| 6 | 回归：30 套件 / 3 机械 E2E / 真实小测 MockLLM=0 / ffprobe 真实性 / ffmpeg decode | **PASS** |
| 7 | Phase 2-A/B 素材分配结果**与 2-B.1 完全一致**（本阶段只新增分类与追溯） | **PASS**（见 §5） |

---

## 1. 分类学（诊断 vs 动作，两级字段）

| `insufficiency_class`（为什么不足） | 判据 | 默认 `fallback_state`（怎么处理） |
|---|---|---|
| `NO_CANDIDATE` | 素材池中与镜头查询关键词交集为空的素材也没有（分数全 0） | `SOLID_COLOR_CARD`（安全占位，`selected_asset=null`） |
| `LOW_MATCH` | 有候选但最高分 < 阈值（默认 `min_match_score=3`） | `THEME_FALLBACK`（同主题降级，明确标注 + `needs_hitl=true`） |
| `ASSET_UNUSABLE` | 素材存在但无法解码/尺寸不合格（`ASSET_DECODE_FAILED` / `ASSET_TOO_SMALL` / `ASSET_EMPTY_FILE`） | `SOLID_COLOR_CARD`（先尝试次优可用候选；不可用素材**绝不**参与选择） |
| `ASSET_CONFLICT` | 素材名命中镜头负向约束（从 `style_constraint`/`description` 抽取"不出现X/不得含X/no X"） | `SOLID_COLOR_CARD`（跳过冲突素材，尝试无冲突候选） |
| `ASSET_EXHAUSTED` | 候选均已被其他镜头占用且复用策略禁止复用（`asset_reuse_policy=forbid`） | `SOLID_COLOR_CARD` |
| （装配级）`ASSEMBLY_BLOCKED` | 已提供本地素材（`material_mode=local_ingest`）却**没有任何镜头**能把真实素材放上屏 | `BLOCKED_FOR_HUMAN` → **render 阻断**，等待人工补充素材 |

策略可配置（`config.editing.*`，缺省保持既有行为）：`min_match_score` / `low_match_policy` / `zero_match_policy` /
`unusable_policy` / `conflict_policy` / `exhausted_policy` / `asset_reuse_policy` / `block_when_all_degraded` /
`min_asset_width` / `min_asset_height` / `frame_verify` / `frame_match_min_corr`。

**「阻断」而非「降级」的两种情形**：① 策略把某类诊断设为 `block`；② 装配级 `ASSEMBLY_BLOCKED`（本轮默认开启）。
`needs_hitl` 是**记录/建议**字段，**不改变**任何 HITL 闸门或任务审批顺序（Phase 2-C 不动 HITL 核心）。

---

## 2. 禁止静默降级（代码级保证，均可在产物中核对）

1. **降级必留痕**：任何非正常命中都会写 `insufficiency_class` + `fallback_reason`（含实际分数与阈值）+
   `fallback_action`；`fallback_state` 只有 `LOCAL_INGEST` 才代表正常命中。
2. **占位不伪装**：`SOLID_COLOR_CARD` 场景 `selected_asset=None`；成片抽帧核验会确认该窗口**不匹配任何素材**
   （`placeholder_verified`），否则判渲染失败。
3. **不可用素材不进渲染**：池构建阶段即做解码/尺寸判定，`usable=False` 的素材被排除并记录原因；
   D 用例实测损坏文件从未进入 ffmpeg。
4. **不改写状态**：素材不足 → render 抛 `[ASSET_INSUFFICIENT]` → 任务 FAILED→重试→**BLOCKED**（终态保留）。
5. **不只看 artifact**：render 产出后逐镜头抽帧核验（`scene_evidence`），把
   `appears_in_film` 写回时间轴；"分配了素材却在该窗口看不到它" → 渲染失败。

---

## 3. 逐镜头可追溯（需求 4 的字段映射）

| 要求 | 落盘字段（`render_output.material_timeline[]`） |
|---|---|
| scene_id | `scene_id` |
| 原始素材需求 | `original_requirement{text, narration_chars, shot_index, shot_description, shot_gen_prompt, style_constraint, constraints[], min_match_score, reuse_policy, expected_kind}` |
| 候选列表及分数 | `candidates[]{asset_id, name, source, sha256, path, relative_path, bytes, match_score, matched_tokens, usable, unusable_reason, width, height, used_by_scenes, conflict_hits}`、`candidates_total` |
| 最终选择 | `selected_asset{asset_id,name,source,sha256,path,relative_path,bytes,width,height,retrieval_match_score}` 或 `null` |
| fallback 分类 | `insufficiency_class` + `fallback_state` + `fallback_action` |
| fallback 原因 | `fallback_reason`、`selection_reason` |
| 素材指纹 | `selected_asset.sha256 / path / bytes`（+ 候选各自指纹） |
| 是否进入 timeline | `entered_timeline` + `start_s/end_s`（实际镜头窗口） |
| 是否出现在成片 | `appears_in_film` + `film_evidence{sample_t, best_asset_id, corr, match, placeholder_like}` |
| 对应验证证据 | `material_verification{method, min_corr, checked_scenes, placeholder_verified, failed_scenes, skipped}` |

阻断项目的追溯：决策记录写在 render **之前**的 `MATERIAL_TIMELINE` 事件（既有事件类型，字段为纯新增），
`phase2c_trace.py` 会读取并核对。

---

## 4. 真实证据（本轮）

### 4.1 故障矩阵（4 个真实项目，详见 `PHASE2C_FAULT_REPORT.md`）

| 用例 | 构造 | render | 结果 |
|---|---|---|---|
| A_normal | 1 段强匹配 + 1 段无关 | SUCCEEDED | S01 `NONE/LOCAL_INGEST`（命中 6）**抽帧命中**；S02 `NO_CANDIDATE/SOLID_COLOR_CARD`（`selected_asset=null`）**占位被证实**；成片 10.0s、decode rc=0 |
| B_no_candidate | 只有无关素材 | **BLOCKED** | 全镜头 `NO_CANDIDATE` → `ASSEMBLY_BLOCKED` → **无成片**；`[ASSET_INSUFFICIENT]` |
| C_low_match | 素材名仅共享 1 字（分数 1 < 阈值 3） | SUCCEEDED | `LOW_MATCH/THEME_FALLBACK`、`needs_hitl=true`；**降级素材确实在屏**且被标注为降级 |
| D_unusable | 损坏的伪装 `.jpg` | **BLOCKED** | `ASSET_UNUSABLE` + `ASSET_DECODE_FAILED: UnidentifiedImageError`；损坏文件**从未进入 ffmpeg**；无成片 |

### 4.2 真实 LLM 项目（12 镜头，`p_ab2b352e06b8`）

- 成片 `t_22a2c150e235_draft.mp4`：25,033,388 bytes / **438.000s** / 2 流 / `ffmpeg -f null` **rc=0**。
- 12/12 镜头 `NONE → LOCAL_INGEST`；逐镜头抽帧 **12/12 命中各自素材**（corr 0.670–0.745）；
  **未渲染镜头 0 个**；不同素材镜头对最大相关 **0.102**。
- `phase2c_trace.py` 断言 **38/38 通过**（含"每个镜头都有完整决策记录"、"占位场景 selected_asset 必须为 null"、
  "appears_in_film 与抽帧证据一致"、"至少 1 个正常素材被抽帧证实上屏"）。

---

## 5. 与 Phase 2-B.1 的一致性（本阶段应"只增不改"）

为保证"只新增分类与追溯"，本轮**修正了两处自己引入的偏差**（如实记录）：

1. **误改匹配语义**：Phase 2-C 初版重写了 `_kw_tokens`/`_match_score`（改变了二元组切法与 2 字拉丁词计权），
   导致素材分配与 2-B.1 不一致（S01 由镜片变成头环）。已从
   `baseline/3.x-phase2b1-baseline.zip` 取回**冻结实现并逐字还原**，现与冻结版**字节级一致**
   （实测 diff 行数 = 0）。同时把 `style_constraint` 从匹配查询中移除（它只用于约束冲突判定）。
2. **消费者读错产物**：引擎重试任务时每次都会 attach 新产物，而消费者取 `artifacts[0]`（失败轮次的旧产物）
   → 实测一次真实 TTS 失败后 voice 重试成功，render 仍读到 INCOMPLETE 产物而阻断（机械 E2E A 组 BLOCKED）。
   已修正 `editing`/`voice`/`qa` 的产物遍历为**最新优先**（`[::-1]`），修复后 3 组机械 E2E 全部 SETTLED。

**一致性结果**：修正后 real 项目成片与 2-B.1 **同为 25,033,388 bytes / 438.0s**，且 S01/S02/S03 的分配与
相关系数与 2-B.1 逐一致（0.672 / 0.744 / 0.684）→ Phase 2-C 未改变素材分配行为。

---

## 6. 回归结果（最终代码，2026-09-13）

| 项 | 命令 | 结果 |
|---|---|---|
| 全部套件 | `run_all_suites.py` | **30 total / 30 rc=0 / FAILED: []**（29 旧 + 新增 `material_taxonomy_test` 40/40） |
| 3 机械 E2E | `run_all_tests.py --fresh` | A/B/C **全 SETTLED**，各 17.000s / 2 流 / 24000Hz 真实旁白 |
| 真实 LLM 小测 | `real_small_test.py` | **PASS**：2 调用 / 4,182 tokens / $0.002188，**MockLLM=0**，模型 `deepseek-flash` |
| 本地 ingest 链路 | `run_ingest_test.py` | **PASS**：17.000s、抽帧 t=8.5s 命中 0.747 |
| ffprobe 真实性 | `check_binaries.py` | **PASS**（真 ffprobe 且非 ffmpeg 副本） |
| ffmpeg 解码 | 各成片 `ffmpeg -v error -i .. -f null -` | **rc=0**（真实项目 + 4 个故障项目成片） |
| Phase 2-A/B 验收 | `phase2_accept.py --verify` | **PASS**（12/12 在屏，3 个不同素材） |
| Phase 2-C 追溯 | `phase2c_trace.py` | **38/38** |
| Phase 2-B.1 契约 | `narration_contract_test.py` | **40/40**（旁白闸门与时长契约未受影响） |

---

## 7. 代码改动（可追溯）

| 文件 | 改动 |
|---|---|
| `src/video_studio/core/materials.py`（新） | 分类学 + 策略 + 逐镜头决策记录：`classify_scene` / `assembly_class` / `policy_from_config` / `extract_constraints` / `conflict_hits` / `insufficient_message` / `MaterialInsufficientError` / 帧核验工具（48×48 灰度相关） |
| `src/video_studio/agents/editing/agent.py` | 素材池**可用性判定**（解码/尺寸/字节 + 原因码）；`_build_material_timeline` 走分类器并写全量追溯；**素材不足闸门**（ffmpeg 之前阻断）+ `[ASSET_INSUFFICIENT]`；`MATERIAL_TIMELINE` 事件新增决策/分类字段；**产出后逐镜头抽帧核验**（`scene_evidence` / `material_verification` / `appears_in_film`）；`render_output` 新增 `traceability_version / material_policy / insufficiency_summary / insufficiency_classes / fallback_states / scenes_needing_hitl / assets_rejected`；`assembly_state` 语义细化（全正常=SUCCEEDED、有素材但降级=PARTIAL、纯占位=PENDING、阻断=BLOCKED）；匹配函数**还原为 2-B.1 冻结版** |
| `src/video_studio/agents/voice/agent.py`、`qa/agent.py` | 产物遍历改**最新优先**（`artifacts[::-1]`），修复"重试后消费者读到旧产物" |
| `tests/material_taxonomy_test.py`（新） | 40 项确定性单测：六类诊断 + 策略分支 + HITL/可渲染标志 + 不伪造/不静默降级 + 装配级阻断 |
| `docs/regression_2x/phase2c_fault_matrix.py`（新） | 4 个真实故障项目构造与证据采集 |
| `docs/regression_2x/phase2c_trace.py`（新） | 逐镜头追溯核对与报告生成（38 项断言） |

---

## 8. 基线与文档

- 新基线：`docs/regression_2x/baseline/3.x-phase2c-baseline.zip`（**330 文件 / 7,181,305 源码字节**，
  sha256 `21b685f65db87bf1de4265090d3589dce87cf7747b8a26b272ef93f7bd7bde77`），
  `verify_baseline.py 3.x-phase2c-baseline` → **MATCH（零漂移：zip 哈希一致、清单==条目、0 缺失、0 漂移）**。
  关键指纹：`core/materials.py e1358fa8573168de…`（新）、`agents/editing/agent.py 7940b9df089c868b…`、
  `agents/voice/agent.py 9f102d2b78b8ba91…`、`tests/material_taxonomy_test.py 751fb59ff88b13f3…`（新）、
  `config/config.json b264644539b2adbb…`（未改）。
- 更新：`CHANGELOG.md`（V2.2.2-Phase2C）、`STATUS.md`、`README.md`（分类学与追溯字段）、`BASELINE_README.md`。
- 证据文件：`logs/phase2c_fault_matrix.{log,json}`、`logs/phase2c_traceability.{md,json}`、
  `logs/phase2_accept.json`、`logs/phase2_evidence.md`、`logs/suites_summary.json`。

---

## 9. 停止点

按授权：本阶段到此为止。**未开始**外部 Provider、BGM、自动发布、UI、语义级对齐、成本对账、Git tag。
等下一阶段授权。
