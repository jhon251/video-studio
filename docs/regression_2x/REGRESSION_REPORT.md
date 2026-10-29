# 2.x 基线回归验收报告（进入 3.x 前的门禁）

- 日期：2026-09-13
- 范围：`video-studio` V2.0.x（pyproject `version = "2.0.0"` + CHANGELOG V2.0.1/V2.0.2 增量）
- 硬标准（用户定义）：**输入选材 → 生成视频规划 → 生成分镜与素材需求 → 执行视频流程 → 成功输出视频**；只出文本/分镜不算通过。
- 结论：**PASS（限定为"机械闭环 + 工程回归"）**；**内容级验收 PENDING**（见 §5）。修复前为 **FAIL（0 视频）**。

---

## 1. 当前 2.x 实际状态

### 1.1 本次发现并修复的**阻断级缺陷**（修复前 2.x 核心闭环是断的）

| 现象 | 证据 |
|---|---|
| 新项目走文档快速开始必失败 | `voice` 任务报 `Invalid voice 'default'.` → `audio_mix`/`render` 依赖不满足 |
| CLI 路径永久阻塞 | 项目 A：26 任务中 14 SUCCEEDED / **12 PENDING**，连续 **29 轮** `run` 执行 **0** 个任务 |
| 自带集成测试同时退化 | `tests/pipeline_mock.py` = **5/8**（"全部任务完成""render 成功" FAIL，完成 16/26、阻塞 1） |

**根因链（三处叠加）**

1. `config/config.json` 的 `tools.tts` 只有 `provider`，**缺 `voice_type`**；
2. `agents/voice/agent.py` 回退成字面量 `"default"`（真值）→ 使 `tts_tool` 内置合法默认音色 `zh-CN-XiaoxiaoNeural` **失效** → edge-tts 判为非法音色；
3. `tools/tts_tool.py` 未把 edge-tts 的异常包成 `ToolError` → VoiceAgent 的 `except ToolError` 优雅降级（`_plan_only`）**路径失效** → 任务硬失败并阻塞全链。

**修复（3 处，最小改动；未删功能、未跳步骤）**

| 文件 | 改动 | 新指纹（sha256 前 32） |
|---|---|---|
| `config/config.json` | `tools.tts` 增加 `"voice_type": "zh-CN-XiaoxiaoNeural"` | `b264644539b2adbbf0f6897b5a118b2a` |
| `src/video_studio/agents/voice/agent.py` | 两处回退 `"default"` → `""` | `216eb5f69192261d8be6af7023633506` |
| `src/video_studio/tools/tts_tool.py` | `asyncio.run` 包 try/except → `ToolError("TTS_FAILED")` | `b671b339634b97788a281e0857d00b04` |

未改动的关键文件：`core/engine.py` `e35dee9a962f78963816218c548e6d67`、`run.py` `dd5aa9af6e6ceb0c78c9f319c474906c`、`pyproject.toml` `edf0cdb1cc2659e34fd4ea0212f639db`。

### 1.2 修复后的能力核对（用户列出的 6 项）

| 能力 | 状态 | 证据 |
|---|---|---|
| 输入选材/素材描述 | ✅ | 三条选材在库中 `goal` **逐字 UTF-8 保真**（见 §2.4） |
| 根据选材生成视频方案 | ✅ | `plan_output`(pm) + `topic_output` + `research_output` + `source_verify_output` + `structure_output` |
| 分镜/镜头/旁白/字幕/画面提示词 | ✅（内容为 mock） | `visual_plan_output`(shots: description/shot_size/gen_prompt) + `script_output`(segments[].narration) + `subtitle`(.srt) |
| 音乐 | ⚠️ 仅方案 | `audio_plan` = "混音方案：-14 LUFS 标准化 + BGM 闪避"，**无 BGM 素材/生成能力** |
| 素材需求/检索 | ⚠️ 空结果 | `asset_index`（0 文件）、`retrieval_candidates`（0 候选）——`tools.search/image/video` 均为 `provider: none` |
| 执行完整流程并输出视频 | ✅ | 26/26 任务、3 个可解码 mp4（§2.3） |
| 2.x 接口/数据结构/工作流未破坏 | ✅ | **25/25 测试套件 rc=0**（§3）；事件/产物/manifest/断点恢复均正常 |

---

## 2. 三组测试结果

三组输入原文保存于 `docs/regression_2x/inputs.md` 与 `prompts.json`。

### 2.1 汇总

| 组 | 选材 | 项目 ID | 任务完成 | 成片 | 结果 |
|---|---|---|---|---|---|
| A | 做一期介绍黑洞的短视频。 | `p_a96a7b8bcb79` | **26/26**（SETTLED） | `A_blackhole_draft.mp4` 69,919 B | PASS（机械闭环） |
| B | 做一期介绍脑机接口发展现状的视频，要求区分真实技术、实验阶段和未来推测。 | `p_11d338f7dc9f` | **26/26**（SETTLED） | `B_bci_draft.mp4` 69,919 B | PASS（机械闭环） |
| C | 制作一条60秒科技科普视频，面向普通观众，节奏适中，包含开头钩子、分镜、旁白、字幕和结尾总结。 | `p_1b49b0c2b0b7` | **26/26**（SETTLED） | `C_60s_draft.mp4` 69,919 B | PASS（机械闭环） |

每组的完整闭环（逐轮日志在 `logs/{A,B,C}_loop2.log`）：
`init` → `plan`(26 任务) → `run` → HITL 闸门 `approve`（topic/structure/script/editing_plan）→
**Claim 闸门 `approve-claim`**（A: c_613 / B: c_614 / C: c_615）→ `run` → `render` → 成片 → 26/26 SUCCEEDED。

### 2.2 成片真实性核验（不只验"文件存在"）

用**已知可用的 ffprobe**（`gpt-sovits` 包内）交叉验证（项目自带的 `bin\ffprobe.exe` 不可信，见 §5-①）：

| 项 | 实测值（A/B/C 三组一致） |
|---|---|
| 容器/流 | `mov,mp4,m4a,3gp,3g2,mj2`；**2 条流** |
| 视频 | `h264` 1280×720，30 fps，**126 帧，4.200 s** |
| 音频 | `aac` **24000 Hz 单声道，4.226 s**，101 帧 |
| 大小/哈希 | 69,919 B；sha256 `46ac0c5792836df0dd2a0130e31547a4…`（三组**完全相同**） |
| 解码完整性 | `ffmpeg -i … -f null -` **rc=0，无错误** |
| 画面证据 | 抽帧成功（53,771 B PNG）：深色底 + **烧录字幕**"大家好，这期聊聊鲸鱼娘皮肤背后的故事。" |
| 音轨电平 | `astats` 峰值 **-3.94 dB** / RMS **-19.98 dBFS** → 真实人声，非静音 |
| 配音来源 | `media/voice/narration.mp3` 25,724 B / **4.248 s**（edge-tts 真实合成） |

### 2.3 字幕产物

字幕侧产物 `subtitle` + `.srt`：
```
1
00:00:00,000 --> 00:00:15,000
大家好，这期聊聊鲸鱼娘皮肤背后的故事。
```
字幕已烧录进画面（帧证据）。

### 2.4 输入保真

数据库中三组 `goal` 与用户输入**逐字一致**（含中文逗号/句号）：
- A：`做一期介绍黑洞的短视频`
- B：`做一期介绍脑机接口发展现状的视频，要求区分真实技术、实验阶段和未来推测。`
- C：`制作一条60秒科技科普视频，面向普通观众，节奏适中，包含开头钩子、分镜、旁白、字幕和结尾总结。`

---

## 3. 工程回归（全量测试套件）

**25/25 套件 `rc=0`**（`docs/regression_2x/logs/suites_summary.json`）：

| 套件 | 结果 | 套件 | 结果 |
|---|---|---|---|
| smoke_mock | 12/12 | schema_v2_test | 10/10 |
| pipeline_mock | **12/12**（修复前 5/8） | agents_v2_test | 28/28 |
| factcheck_v2_test | 23/23 | hitl_v2_test | 19/19 |
| search_quality_v2_test | 51/51 | strip_v2_test | 14/14 |
| claim_structuring_test | 6/6 | evidence_pool_test | 7/7 |
| evidence_regression_test | 23/23 | llm_semantic_judge_test | 16/16 |
| numeric_parser_test | 9/9 | sufficiency_judge_test | 15/15 |
| text_quality_test | 8/8 | stage31_intent_test | 37/37 |
| stage31_package_test | 22/22 | stage31_queryplan_test | 13/13 |
| stage31_rights_test | 69/69 | stage31_semantic_test | 6/6 |
| stage33_executor_layers_test | ALL PASS | stage33_motion_test | ALL PASS |
| stage33_realizer_test | ALL PASS | stage33_sanitizer_test | ALL PASS |
| stage33_statement_test | ALL PASS | | |

---

## 4. 基线固化

因**仓库无 Git**（`C:\mp4agent\video-studio` 无 `.git`；`STATUS.md:5` 记载"无 Git 仓库（按用户指示不引入版本控制）"），
`git tag 2.x-final-baseline` **无法执行 → BLOCKED/PENDING（待用户裁定）**。已用等价方式固化：

| 产物 | 内容 | 指纹 |
|---|---|---|
| `docs/regression_2x/baseline/2.x-final-baseline.zip` | src+config+tests+scripts+docs+根文件（排除 output/projects/models/.venv_tts/bin 可执行） | sha256 `24dd412529207afa7df9c0b755b5bf7e1816a299268d551f9ae491ab95b3241e` |
| `docs/regression_2x/baseline/baseline_manifest.json` | 691 个文件逐文件 sha256 + 字节数 | — |

证据目录：`docs/regression_2x/`（`inputs.md`、`prompts.json`、`outputs/` 3 个 mp4、`logs/` 126 个、脚本 4 个）。

---

## 5. 已知问题（本次实测）

| # | 级别 | 问题 | 状态 |
|---|---|---|---|
| ① | P1 | **`bin/ffprobe.exe` 与 `bin/ffmpeg.exe` 字节相同**（同 SHA256 `2CE797A0…`）→ `FFmpegTool.probe` 仅靠 `ffmpeg -i` stderr 降级路径可用；任何直接依赖 ffprobe 的判定不可信 | **未修**（PENDING，需替换为真 ffprobe） |
| ② | P1 | **Mock 模式内容与选材无关**：三组不同选材产出**字节完全相同**的成片（同一 sha256） | 属设计（`llm.mock` 段存在），**内容保真未验证** |
| ③ | P1 | **素材 provider 全为 `none`** → `asset_index` 0 文件、`retrieval_candidates` 0 候选 → 成片画面为深色底+烧录字幕（无真实素材） | **未修**（PENDING） |
| ④ | P2 | **无音乐/BGM 能力**：仅 `audio_plan` 文本（"-14 LUFS 标准化 + BGM 闪避"） | 能力缺口（非回归） |
| ⑤ | P2 | README 快速开始**未写 Claim 审核步骤**；V2 的 claim gate 会阻塞全部 15 类生产任务，必须 `approve-claim` | 文档缺口（未修） |
| ⑥ | P3 | mock 脚本 `duration_s=15` 但成片 4.2 s，字幕 cue 跨度 15 s 与成片时长不一致 | 仅 mock 数据问题 |
| ⑦ | P3 | 早期 `STATUS.md` 待办仍列 "edge-tts 真声配音"——本次已验证 edge-tts 实际可用（24 kHz 单声道） | 状态待更新 |

**问题归属判定**：①③④⑤⑥ 为**既有 2.x/环境问题**（非本次引入）；② 为既有设计行为；**唯一由"近期改动引入"的回归是 voice 默认音色链**（§1.1），已修复并回归验证。

---

## 6. 是否通过基线验收

- **机械闭环（用户硬标准）**：**PASS** —— 三组选材各自 26/26 任务、真实产出可解码 mp4（视频+音频 2 条流、抽帧、电平、烧录字幕全部核验）。
- **前提**：该 PASS 建立在**本次修复**之上；修复前同一路径 **0 视频**、自带集测 5/8。**没有删除功能、没有跳过步骤、没有伪造状态**。
- **内容级（选材 → 内容保真 → 素材/音乐）**：**PENDING**（②③④）。当前环境只能证明"流程能出片"，不能证明"出的是符合选材内容的片"。

---

## 7. 是否可以开始 3.x

**可以开始 3.x 的设计与开发**（硬标准已通过），但必须遵守以下安全边界：

1. **冻结基线**：以 `2.x-final-baseline.zip`（sha256 `24dd4125…`）+ manifest 作为唯一回归基准，3.x 开发不得修改该 zip 内容。
2. **回归门槛（每次合并前必跑）**：25 套件全绿 + 三组选材 E2E 出片（可脚本化：`python docs/regression_2x/run_all_tests.py`）。
3. **不得放宽/移除**：Claim 审核闸门、HITL 闸门（topic/structure/script/materials/final_cut/publish）、append-only 产物、exec 隔离、manifest 断点恢复（`run.py recover`）。
4. **数据兼容**：`projects/video_studio.db` 迁移必须保持历史行可读（照 V2.0.2 `migrate()` 做法），不得破坏 `changelog` 审计链。
5. **契约稳定**：3.x 新能力以新增 Agent/模块为主，不得改写既有 agent 的 task/artifact/事件契约（26 类产物类型、事件类型）。
6. **先还债**：优先修 ①（假 ffprobe）、③（素材 provider/ingest 路径）、⑤（README 补 claim 步骤），或在 3.x 规划中明确承接；②的内容保真需真实 LLM（`.env` 已有 `DEEPSEEK_API_KEY`，但**需你授权消耗 API 额度**，并移除 `config.llm.mock` 段才生效）。

### 待你裁定（必须人工决策，我不擅自执行）

1. **Git tag**：`git init` 需先设计 `.gitignore`（当前整树 17.97 GB：output 10.2 GB / models 5.6 GB / .venv_tts 1.75 GB / bin 225 MB，源码仅 ~9 MB）。选项：(a) 维持"无版本控制"，以 zip+manifest 为基线（已完成）；(b) 授权 `git init` + 排除大目录后打 `2.x-final-baseline` tag。
2. **内容保真验收**：是否授权用真实 DeepSeek API 重跑三组选材（需移除 mock 段，消耗额度；素材仍需 provider 或本地 `ingest`）。
