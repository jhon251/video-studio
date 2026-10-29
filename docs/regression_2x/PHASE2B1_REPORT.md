# 3.x Phase 2-B.1 报告：音频完整性与渲染时长契约修复

- 日期：2026-09-13
- 授权范围（逐字）：**"允许进入一个严格限定的 Phase 2-B.1：音频完整性与渲染时长契约修复"**，"本阶段只解决这个问题，禁止开始 Phase 2-C"。
- 本阶段交付：① `VoiceAgent` 分段状态真实化 ②失败段独立重试 + 成功段复用 ③旁白完整性 gate ④**时长契约（timeline 权威）**
- 未开发（越界即不做）：Phase 2-C（fallback 分类学）、素材不足降级、外部素材 provider、BGM、UI 大改、新 Agent。
- 未触碰：Claim/HITL 闸门、append-only、exec isolation、断点恢复、既有 task/artifact/事件契约（**未新增事件类型**）。

---

## 0. 结论先行（判定行）

| # | 判定项 | 结论 |
|---|---|---|
| 1 | 分段状态真实化：任一段失败**不再**整体 SUCCEEDED/confidence=1.0 | **PASS**（受控注入实测：BLOCKED + `[NARRATION_INCOMPLETE]`） |
| 2 | 失败段独立重试 + 成功段复用（不重复生成） | **PASS**（注入运行中 real TTS 调用停在 11，两次重试 0 次新增） |
| 3 | narration 完整性 gate（expected/successful/时长可验证） | **PASS**（voice 与 render 双端落盘字段 + 双端阻断） |
| 4 | 时长契约：timeline 权威、不再 `-shortest` 截短、不完整则在 render 前阻断 | **PASS**（参数层面去除 `-shortest`；成片产出后校验；实测 render BLOCKED 且无新成片） |
| 5 | 12/12 段成功 + 时长容差 + 全 timeline 成片 + S01–S12 全部在屏 | **PASS**（439.056s vs 438.0s = **0.24%**；成片 438.0s；12/12 抽帧命中） |
| 6 | 回归（29 套件 / 3 机械 E2E / 真实小测 MockLLM=0 / 本地装配） | **PASS** |
| 7 | PENDING/BLOCKED/FAILED 未被改写成 PASS | **PASS**（历史 BLOCKED/FAILED 记录原样保留，见 §6） |

一句话：**旁白现在要么完整、要么任务明确失败；成片时长由时间轴决定，音轨不足只会被静音补齐，不会再"成功但被截短"。**

---

## 1. 逐条验收（对照授权清单）

| 授权要求 | 实现 | 证据 |
|---|---|---|
| 每段独立记录 success/failure/error/retry_count | `voice_output.segment_details[]`：`status`（SUCCESS/REUSED/FAILED）、`attempts`、`bytes`、`duration_s`、`text_sha256`、`errors[{code,retryable,attempt,error}]` | `logs/phase2_evidence.md` §4b 表（12 行逐段） |
| 任一段失败不得整体 SUCCEEDED/confidence=1.0 | 全段齐备才 `complete=True/confidence=1.0`；否则写 INCOMPLETE 证据后 **抛错** → 任务 FAILED→重试→BLOCKED | 注入实测：voice v5 **BLOCKED**，`confidence=0.0`，`error=[NARRATION_INCOMPLETE] voice 分段未全部成功` |
| 已成功段不重复生成 | `media/voice/segments_manifest.json`（文本哈希+音色+provider+时长）→ 合法即复用（`status=REUSED`） | 注入运行 cycle1 real=11 → cycle2/3 **real=11 不变**；收尾运行 **real=1**（只补 seg04） |
| 已存在且合法的成功音频允许复用 | 复用条件：文件存在 & bytes>0 & ffprobe 时长>0 & 文本哈希/音色/provider 一致 | 单元测试 E1/E2/E3（第二次运行 0 次调用）；真实 11/12 段复用 |
| 临时网络失败保留明确错误码 | 归类 `TTS_NETWORK`（retryable）/`TTS_SYNTHESIS_FAILED`/`TTS_INVALID_AUDIO`/`TTS_CONCAT_FAILED`，保留原始异常文本 | 单元测试 D2/C8/C9：`TTS_NETWORK` + `speech.platform.bing.com` 原文保留 |
| 失败段独立重试 | `tools.tts.max_attempts`（默认 3）+ 退避；**仅可重试错误**重试 | 单测 D1：第 1 次网络失败→第 2 次成功（attempts=2）；C8：网络类重试到 attempts=3 |
| expected/successful/音频实际时长可验证 | `voice_output`：`expected_segments/successful_segments/failed_segments/reused_segments/narration_duration_s/script_time_base_s/duration_contract` | `logs/phase2_evidence.md` §4b |
| narration 不完整 → render 必须 fail/block，禁止"成功但被截短" | ① render **调用 ffmpeg 之前**闸门（完整性+时长）② 产出后校验 `|成片-时间轴| ≤ 1.0s` | 实测：render v3 **BLOCKED**，`error=[NARRATION_INCOMPLETE] render 前闸门`，输出目录无新文件 |
| timeline 是最终视频时长权威来源 | `-t {timeline}` + 音轨 `apad` 补齐；**移除 `-shortest`**；旁白偏长超容差则阻断 | 单测 G2：旁白 9s、时间轴 11s → 成片 **11.0s**；J1/J2/J3：三个分支均无 `-shortest` |
| 不完整时在 render 前阻断，而非自动缩短 timeline | 阻断抛 `NarrationIncompleteError`；从不修改 timeline/`total` | 单测 F1/F2 + 真实 render v3 BLOCKED（时间轴仍为 438.0s 未变） |
| 不改既有契约 | 未新增事件类型；`render_output`/`voice_output` 仅**新增字段**（旧字段 `audio`/`segments`/`output` 语义不变） | `git`-less 基线零漂移校验见 §7 |

---

## 2. 时长契约（本阶段定义，代码内可审计）

| 项 | 定义 | 取值 |
|---|---|---|
| 权威时长 | `Σ max(segment.duration_s, 3.0) + 2.0`（`core/narration.script_time_base_s`，与时间轴末镜头 `end_s` 恒等） | 438.0s（本项目） |
| 完整性（硬闸门） | 每段非空旁白都有**合法音频**（存在/非空/可探测正时长） | 12/12 |
| 容差 | `editing.narration_duration_tolerance_ratio`，默认 **0.10** | 实测偏差 **0.24%** |
| 旁白较短 | `apad` 静音补齐到时间轴长度；视频**不缩短** | 本项目未触发（旁白更长） |
| 旁白较长 | 容差内 → 按时间轴裁尾并如实记录；**超容差 → 阻断** | 裁剪 1.056s（记录 `audio_trimmed_to_timeline=true`） |
| 产出后校验 | `|成片时长 - 时间轴| ≤ 1.0s`，否则任务失败 | 438.0s vs 438.0s → `video_duration_ok=true` |

判定一致性：`script_time_base_s(script) == _build_material_timeline(...)[-1]["end_s"]`（单测 A1 = 11.0 vs 11.0）。

---

## 3. 真实项目证据（`p_ab2b352e06b8`，真实 TTS、真实引擎、真实 DB）

### 3.1 受控故障注入（`docs/regression_2x/phase2b1_fault_inject.py --inject 4`）

注入方式：只在本进程把 `TTSTool.execute` 换成"第 4 段永久网络失败（`ClientConnectorError: …speech.platform.bing.com…`）"的包装，**其余段走真实工具**；不修改任何生产代码。

```
=== run cycles=4 inject=4 ===
  [cycle 1] 执行 1 个任务（TTS 调用 real=11 injected=3）
  [cycle 2] 执行 1 个任务（TTS 调用 real=11 injected=6）
  [cycle 3] 执行 1 个任务（TTS 调用 real=11 injected=9）
  TTS 调用统计: real=11 injected=9
```

- **11 段真实合成**（cycle1）后被固化进 manifest；cycle2/3 **real 恒为 11 → 成功段 0 次重复生成**（要求 2 实证）。
- 第 4 段每轮 3 次尝试（可重试错误码）→ 3 轮后 `retry_count=2` 用尽 → **voice v5 BLOCKED**：
  `[NARRATION_INCOMPLETE] voice 分段未全部成功: {"expected_segments": 12, "successful_segments": 11, "failed_segments": [4], "error_codes": ["TTS_NETWORK"], …}`
- 产物 `status=INCOMPLETE / complete=False / confidence=0.0`；`narration.mp3` **未被覆盖**（仍是上一版 236.4s 文件）。
- 逐段：`seg04 FAILED attempts=3 errors=[TTS_NETWORK×3]`，其余 11 段 `REUSED attempts=0`（含 bytes/duration）。

### 3.2 render 阻断（要求 ③④ 实证）

```
render  BLOCKED v3 retry=2  [NARRATION_INCOMPLETE] render 前闸门:
  {"reasons": ["voice 产物不完整：voice 产物自述 INCOMPLETE；缺少合法音频的段落: [4]",
               "旁白音轨时长不可探测（文件缺失/为空/ffprobe 失败）"], …}
```

- 输出目录**未产生新 mp4**（旧成片 mtime 保持 21:06 不变）。
- **重要发现（如实报告）**：`render` 的直接依赖只有 `editing_plan` + `audio_mix`（两者 SUCCEEDED），voice 是通过依赖图 BFS 找到的；因此本例 render **确实被派发并执行**，靠的是**渲染前闸门**把它挡住——说明"仅靠依赖层面"不足以防住这个问题，闸门是必需的（这也是本阶段实现的核心价值）。

### 3.3 清除故障 → 完整旁白 → 全长成片

- `voice v6`：**12/12 COMPLETE**，`reused=[0,1,2,3,5..11]`，仅 `seg04 SUCCESS attempts=1` → 该轮 **real TTS 调用 = 1**。
- `narration.mp3` = 2,634,572 bytes / **439.056s**（12 段全非空）。
- `render v4`：`narration_state=COMPLETE`，`video_duration_s=**438.0**`，`video_duration_ok=true`，
  `duration_contract`: 439.056 vs 438.0，偏差 **+1.056s / 0.24%**，容差 10% → `within_tolerance=true`。
- 成片 `t_dba5c8008b82_draft.mp4`：25,033,388 bytes / **438.000s** / 2 流
  （video h264 1920×1080 30fps **13128 帧**；audio aac 24000Hz 单声道 438.0s）；`ffmpeg -f null` **rc=0**。

### 3.4 抽帧核验：S01–S12 全部在屏（要求 ⑤ 实证）

| 镜头 | 窗口(s) | 采样(s) | 期望素材 | argmax | corr |
|---|---|---|---|---|---|
| S01 | 0–30 | 15.0 | asset_3bd63424e488 | 同 | 0.672 |
| S02 | 30–68 | 49.0 | asset_f304650dbc24 | 同 | 0.744 |
| S03 | 68–104 | 86.0 | asset_3af507571a33 | 同 | 0.684 |
| S04 | 104–142 | 123.0 | asset_3bd63424e488 | 同 | 0.678 |
| S05 | 142–174 | 158.0 | asset_3bd63424e488 | 同 | 0.673 |
| S06 | 174–198 | 186.0 | asset_3bd63424e488 | 同 | 0.673 |
| S07 | 198–226 | 212.0 | asset_f304650dbc24 | 同 | 0.730 |
| S08 | 226–278 | 252.0 | asset_3bd63424e488 | 同 | 0.676 |
| S09 | 278–314 | 296.0 | asset_3bd63424e488 | 同 | 0.687 |
| S10 | 314–346 | 330.0 | asset_3bd63424e488 | 同 | 0.670 |
| S11 | 346–402 | 374.0 | asset_f304650dbc24 | 同 | 0.703 |
| S12 | 402–438 | 420.0 | asset_f304650dbc24 | 同 | 0.745 |

- **未渲染镜头 0 个**（上一阶段为 4 个）；不同素材镜头对最大相关 **0.099**；确认在屏的不同素材 **3**。
- 记录：`logs/phase2_accept.json`（`verdict: PASS`）、`logs/phase2_evidence.md`。

---

## 4. 回归（全部重跑于最终代码）

| 项 | 命令 | 结果 |
|---|---|---|
| 全部套件 | `run_all_suites.py` | **29 total / 29 rc=0 / FAILED: []**（28 旧 + 新增 `narration_contract_test`） |
| 新增契约单测 | `tests/narration_contract_test.py` | **40/40**（A 契约一致性；B 完整；C 受控失败/不覆盖/不谎报；C8–C9 重试与错误码；D 重试成功；E 复用；F 渲染前阻断；G 时长==时间轴；J 无 `-shortest`；H 超容差阻断；I 产出后校验阻断） |
| 3 机械 E2E | `run_all_tests.py --fresh` | A/B/C **全 SETTLED**；成片各 **17.000s**、2 流、**24000Hz 真实旁白**（旧实现此处会截短到 ~4.2s） |
| 真实 LLM 小测 | `real_small_test.py` | **PASS**：2 次调用 / 5,480 tokens / $0.002967，台账==任务行，**MockLLM 调用 0 次**，模型 `deepseek-flash` |
| 本地装配链路 | `run_ingest_test.py` | **PASS**：`material_timeline` + `SUCCEEDED`；成片 **17.000s**（旧 4.226s）；t=8.5s 抽帧命中分配素材 **0.747** |
| 二进制真实性 | `scripts/check_binaries.py` | PASS（ffprobe 真实且非 ffmpeg 副本） |

---

## 5. 代码改动（可追溯）

| 文件 | 改动 |
|---|---|
| `src/video_studio/core/narration.py`（新增） | 契约单一来源：`script_time_base_s` / `narration_segment_indexes` / `evaluate_narration` / `duration_contract`（含 `measured`，不把"未测得"当 0s）/ `probe_duration_s` / `segment_file_ok` / `NarrationIncompleteError` / 容差常量（10%、产出后 1.0s、收尾 2.0s） |
| `src/video_studio/agents/voice/agent.py` | 逐段状态机 + manifest 复用 + 可重试错误分类（`TTS_NETWORK` 等）+ 独立重试退避 + 仅全段齐备才重建 `narration.mp3`（不覆盖完整旧音轨）+ 不完整写 INCOMPLETE 证据后抛错 |
| `src/video_studio/agents/editing/agent.py` | 读取完整 voice 产物；**渲染前闸门**（完整性 + 时长）+ **产出后时长校验**；`-shortest` 改为 `apad` + `-t total`（三个分支）；`render_output` 新增 `narration_state/narration_completeness/duration_contract/video_duration_s/video_duration_ok` |
| `src/video_studio/tools/ffmpeg_tool.py` | `probe` 结果**新增**容器 `duration` 字段（纯新增，供时长契约使用） |
| `tests/narration_contract_test.py`（新增） | 40 项确定性单测（假 TTS 用 ffmpeg 生成真 mp3，可编程失败；不访问网络） |
| `docs/regression_2x/phase2b1_fault_inject.py`（新增） | 受控故障注入驱动（status/segments/redo/run --inject/render-args） |
| `docs/regression_2x/phase2_accept.py`、`phase2_evidence.py`、`real_small_test.py`、`run_ingest_test.py` | 取"最新产物/权威成片"的方式修正（按 `created_at`、以 `render_output.output` 为准）、证据字段扩展、MockLLM 计数显式打印 |

---

## 6. 保留的历史状态（**未改写为 PASS**）

| 任务 | 状态 | 真实原因 |
|---|---|---|
| `voice v4` (`t_beb706b76dd7`) | **FAILED** | 我方驱动脚本未导入 Agent 模块 → `未注册 agent: voice`（驱动缺陷，已修；与生产代码无关） |
| `voice v5` (`t_d22a382befe5`) | **BLOCKED** | 受控注入的第 4 段永久网络失败 → 3 轮重试耗尽（**这是本阶段要证明的行为**） |
| `render v3` (`t_a1e48869f441`) | **BLOCKED** | 旁白不完整 → 渲染前闸门阻断，**未产生被截短的成片**（本阶段要证明的行为） |
| 更早的 `voice v1–v3` | SUCCEEDED | 旧实现（1/12、9/12、7/12 段），作为缺陷历史保留 |

---

## 7. 基线与文档

- 新基线：`docs/regression_2x/baseline/3.x-phase2b1-baseline.zip`
  （**328 文件 / 7,125,103 源码字节**，sha256 `574a161bd8ba10206a925169a29d085dad115f6ee25bf8c36cc627e73c326baa`），
  `verify_baseline.py 3.x-phase2b1-baseline` → **MATCH（零漂移：zip 哈希一致、清单==条目、0 缺失、0 漂移）**。
- 关键指纹：`core/narration.py 579fd024f7a790eb…`（新）、`agents/voice/agent.py 5689556120512de1…`、
  `agents/editing/agent.py 8872979cbe95828c…`、`tools/ffmpeg_tool.py 7b62ab0f628da874…`、
  `tests/narration_contract_test.py a169a5f081fde543…`（新）；`config/config.json` 未改（`b264644539b2adbb…`）。
- 更新：`CHANGELOG.md`（V2.2.1-Phase2B1）、`STATUS.md`、`README.md`（旁白与时长契约）、`BASELINE_README.md`
  （新增 §2c 与基准行；已知问题 ⑦⑧⑪ 转为已修，新增 ⑫ 网络依赖显式化）。

---

## 8. 停止点

按授权：本阶段到此为止。**Phase 2-C 未开始**，等下一子阶段授权。
