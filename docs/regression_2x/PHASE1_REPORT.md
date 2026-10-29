# 3.x Phase 1 报告：真实内容保真 + 本地素材最小装配闭环

- 日期：2026-09-13
- 范围：**仅** Part A（真实 LLM 内容保真）与 Part B（本地素材最小装配）；未开发 BGM、自动发布、特效、UI、Phase 2。
- 当前判定：**Part A PASS（三组真实内容）｜Part B PASS（本地素材上屏）｜Phase 1 整体 PASS**，并附 3 项 PENDING（见 §7）。

---

## 1. 当前配置与实际使用的 LLM provider

| 项 | 值 |
|---|---|
| provider | `deepseek`（`https://api.deepseek.com`，OpenAI 兼容 `/chat/completions`） |
| MockLLM 开关 | `cli.py:67` `if llm_cfg.get("mock")`；`config/config.json` 含 mock 段 → **机械回归走 Mock**；`config/config.real.json`（新，程序化从 config.json 派生）**删除 mock 段** → 走真实 API |
| API key | `.env` 的 `DEEPSEEK_API_KEY`（35 字符），经 `run.py` 的 `load_env(ROOT/".env")` 注入，`DeepSeekClient` 从环境变量读取；未硬编码 |
| 模型 | `/models` 端点仅返回 `deepseek-flash`、`deepseek-v4-pro`；旧名 `deepseek-chat`/`deepseek-reasoner` **仍返回 200**（探测三次调用确认） |
| 档位映射（真实配置） | R → `deepseek-v4-pro`（max_tokens 8192）｜M → `deepseek-flash`（**16384**，实测截断后上调）｜F → `deepseek-flash`（2048） |
| 超时 / 重试 | `timeout_s=120`；`max_retries=2`，退避 5s/10s（仅对 429/5xx/超时/连接失败重试） |
| 错误显式化 | 新增 `LLMError`：`LLM_AUTH(401)` / `LLM_BALANCE(402)` / `LLM_BAD_REQUEST(400,422)` / `LLM_RATE_LIMIT(429)` / `LLM_SERVER(5xx)` / `LLM_TIMEOUT` / `LLM_CONNECTION` / `LLM_BUDGET_EXCEEDED`（本地闸门，未发请求） |
| 预算闸门 | `llm.max_total_usd=0.60`（本次每进程上限；超出即 `LLM_BUDGET_EXCEEDED`，不再发请求） |
| 计价 | 官方价目表（USD/1M tokens，peak/off_peak 按 UTC 时段自动选择）：flash cache_hit 0.006/0.003、cache_miss 0.30/0.15、output 1.20/0.60；v4-pro 0.044/0.022、1.32/0.66、3.96/1.98 |
| 其他 provider | `tools.search/image/video` 均 `none`（不接入外部素材）；`tools.tts= edge-tts`（真实合成）；ffmpeg/ffprobe 为真实二进制 |

**修复前的真实缺陷（本次发现）**：`cost_usd` 字段被写入**档位 budget 上限**而非实际费用；token/耗时未落库；HTTP 层无重试；错误类型不显式。现已：按官方价目表实算、按调用**累加**写回任务、逐调用发 `LLM_CALL` 审计事件（新增事件类型，未改既有类型）。

---

## 2. Part A：单组真实 API 测试（先做，未直接跑三组）

**输入（逐字）**：`做一期介绍黑洞的短视频。` → 项目 `p_314efdfbbeb2`

**过程**：首次尝试（`p_f2587e967ba8`）**失败并如实记录**：`plan` 缺 `$.summary`、`topic` 缺 `$.proposals`（SchemaError，3 次尝试后 BLOCKED）。
- 根因：agent 提示词只写"输出严格 JSON"，**从未把 `output_schema` 的键告诉模型**；Mock 下预置答复恰好合法，因此 2.x 从未暴露。
- 修复：Router 统一注入 Schema + 校验失败时**一次修复重试**；HTTP 返回即记账（失败调用也计费）。

**通过后的核验**：

| 检查项 | 结果 |
|---|---|
| 真实 API 确实被调用 | 15 次调用，模型 `deepseek-flash`(11) + `deepseek-v4-pro`(4) |
| 不是 MockLLM | `LLM_CALL` 事件中 `mock=true` 计数 = **0** |
| 内容围绕黑洞 | topic 58 / research 77 / structure 37 / script 105 / visual 22 / subtitle 35 次主题词命中；**mock 线索词 0** |
| 链路主题一致 | 六个环节主题词均命中（见 §4 表） |
| Claim 闸门仍生效 | 51 条 claim；`UNSUPPORTED` 5 条时**15 类生产任务 25 轮不派发**，人工 `approve-claim` 后才放行 |
| HITL 闸门仍生效 | 4 道任务闸门（topic/structure/script/editing_plan）均需 `approve`；共 4 次 NEEDS_REVIEW |
| 失败/超时/限流有明确状态 | 见 §6 事件清单（SchemaError、JSON 截断、编码器错误、429/5xx 重试路径均在代码中显式化） |
| 记录请求次数/耗时/token/费用 | 15 次 / 42,867 tokens / min 6,308ms、max 41,812ms / **$0.0309** |
| 成片 | `t_829a5a37a5a6_draft.mp4`：**334.434s，1080×1920，2 流，解码 rc=0** |

**单组结论：PASS** → 才进入三组真实内容测试。

---

## 3. Part A：三组真实内容测试

| 组 | 选材 | 项目 | 任务 | 调用/token/费用 | 成片 |
|---|---|---|---|---|---|
| A | 做一期介绍黑洞的短视频。 | `p_314efdfbbeb2` | 26/26 | 15 / 42,867 / $0.0309 | 334.434s，1080×1920，6.87 MB |
| B | 脑机接口发展现状（区分真实/实验/推测） | `p_e7a8b8020fb1` | 26/26 | 19 / 87,624 / $0.0488 | 544.767s，1920×1080，11.67 MB |
| C | 60 秒科技科普（普通观众/节奏适中/钩子-分镜-旁白-字幕-总结） | `p_8f054c227bd4` | 29/30（1 个为被取代的旧 render） | 15 / 87,858 / $0.0720 | 62.000s，1920×1080，1.02 MB |

**内容保真核验（客观、无 LLM 打分）**

- 主题一致性（各环节主题词命中次数）：
  - A：topic 58｜research 77｜structure 37｜script 105｜visual 22｜subtitle 35
  - B：topic 51｜research 73｜structure 8｜script 138｜visual 45｜subtitle 72
  - C：topic 28｜research 75｜structure 45｜script 70｜visual 34｜subtitle 11
- 约束遵循：
  - B：三态区分标记 **fact 2 / experiment 31 / speculation 31**（脚本+结构+字幕）
  - C：钩子✅ 分镜✅ 旁白✅ 字幕✅ 结尾总结✅ 受众字段✅；**时长 62s vs 60s 目标，偏差 3%**
- 字幕↔旁白：A 8/8、B 11/11、C 6/6（归一化包含关系）
- 分镜结构：A 10 镜/8 段、B、C 均字段齐全（按 source 区分：`ai_generate/chart` 需 `gen_prompt`，`stock` 资料画面不要求）
- **三组实质不同**：字幕文本两两 2-gram Jaccard = A-B 6.5%、A-C 2.9%、B-C 2.6%，**文本哈希互不相同**；**彻底消除 2.x "三组成片字节完全相同"（旧值 sha256 均为 `46ac0c57…`）**
- 事实质量抽样（A）：史瓦西半径"太阳约 3 公里/地球约 9 毫米"、LIGO 2015 引力波、EHT 2019 M87 与 2022 银心、无毛定理，并**主动标注**"逃逸速度讲法只是直觉、不是严格定义"

---

## 4. Part B：本地素材最小装配闭环

**链路**：`media/` 本地素材 → `asset_index` → `retrieval 命中` → `editing 选择并装配` → `render` → **成片中真实出现**

| 环节 | 证据 |
|---|---|
| 素材来源 | `run.py ingest <pid> <dir>`，本地图片 2 张（`鲸鱼娘皮肤界面截图_01.jpg` 115,118 B、`鲸鱼娘皮肤展示_02.jpg` 278,063 B），`material_providers={'search':'none','image':'none','video':'none'}`（**未接外部 provider**） |
| 稳定标识 | 逐文件 sha256：`b72556040456e641` / `3be4473e0043440a` |
| retrieval 命中 | `material_mode=local_ingest`、`query_source=dependency_artifacts(visual_plan/script)`、`index_source=project_scan_latest`、`candidates_total=1`、命中项 `score=1` |
| editing/render 使用 | `material_used={name, relative_path, abs_path, sha256:f304650dbc24803c, bytes:115118, match_score:1}`；`material_appearances=[{start_s:0, end_s:null, note:"全片背景（整段使用）"}]`；`visual_source=ingested_material_background`、`material_assembly=SUCCEEDED` |
| 成片真实验证 | `t_f989725e9543_draft.mp4`：1280×720，4.226s，2 流，182,686 B（纯色底版仅 69,919 B）；`ffmpeg -f null` **rc=0** |
| **素材确实在画面中** | 抽帧 t=1s 与素材图相关性 **+0.773**，与纯色对照 **+0.000**（目视确认：VR 头显照片铺满画面＋烧录字幕） |

**修复前状态对照**：装配前 `visual_source=solid_color_subtitle_card`、`material_assembly=PENDING`、成片 69,919 B 纯色底——素材只进候选、不上屏。现已真正上屏，并保留 `PENDING` 路径（无图片素材时如实标注，不伪造）。

---

## 5. Phase 1 实际修改文件

**代码（8 个文件）**

| 文件 | 改动 |
|---|---|
| `src/video_studio/llm/router.py` | `LLMError` 显式错误码；HTTP 重试退避；usage 含 cache/reasoning/latency/attempts；官方价目表实算费用；运行级预算闸门；**Schema 注入提示词 + 一次修复重试** |
| `src/video_studio/agents/base.py` | HTTP 返回即记账；费用按调用**累加**写回；逐调用发 `LLM_CALL` 审计事件 |
| `src/video_studio/memory/repo.py` | **注入上游依赖产物内容**；自我记忆**仅限本项目**（修跨项目主题污染）；容忍 DB 中 JSON 文本字段 |
| `src/video_studio/agents/editing/agent.py` | **本地素材最小装配**（图片背景 + 铺满裁剪 + 证据字段）；`render_params` 白名单归一化；标注修正 |
| `src/video_studio/core/engine.py` | `redo` **重连下游依赖**；新增 `rewire_dependents` |
| `src/video_studio/db/schema.py` | `update_task` 允许更新 `dependencies`（否则 redo 无法重连） |
| `src/video_studio/tools/ffmpeg_tool.py` | 6 处 `subprocess` 明确 `encoding="utf-8", errors="replace"`（防 GBK 解码异常） |
| `config/config.real.json` | 新增：真实 LLM 配置（无 mock 段）、现行模型名、官方价目表、预算闸门 |

**文档与工具（docs/regression_2x/）**：`PHASE1_REPORT.md`（本文件）、`make_real_config.py`、`run_real_test.py`、`probe_llm.py`、`verify_real_content.py`、`phase1_verify.py`、`verify_assembly.py`、`report_llm_ledger.py`、`phase1_cost_report.py`、`rewire_project.py`、`latest_project.py`、`diagnose_redo_stall.py`、`inspect_*.py`、`search_gbk.py`、`check_context_fix.py`、`prove_contamination.py`、`dump_project.py`。

**未改动**：Claim/HITL 闸门语义、append-only 产物、exec 隔离、断点恢复规则、既有 task/artifact/事件类型（仅新增 `LLM_CALL`、`TASK_DEPENDENCY_REWIRED` 两个**新增**类型）、MockLLM 与其配置。

---

## 6. API 消耗、耗时与失败重试

**逐调用台账（`LLM_CALL` 事件，49 次调用 / 218,349 tokens / 记录费用 $0.1517）**

| 项目 | 调用 | tokens | 记录费用 | 最小/最大延迟 |
|---|---|---|---|---|
| A 黑洞 | 15 | 42,867 | $0.0309 | 6,308 / 41,812 ms |
| B 脑机接口 | 19 | 87,624 | $0.0488 | 6,051 / 48,755 ms |
| C 60 秒科普 | 15 | 87,858 | $0.0720 | 8,062 / 95,606 ms |
| A 首次尝试（模式校验失败） | 0（**早于埋点，未记录**） | — | 未记录 | — |

**失败与重试（全部有明确状态，未伪造成功）**

| 项目 | 任务 | 错误 | 处理 |
|---|---|---|---|
| A 首次 | `pm`/`topic` | `$.summary` / `$.proposals 缺少必填字段` | 重试 2 次后 BLOCKED → 修 Schema 注入后重跑 |
| B | `script` | `LLM 输出不是合法 JSON: Expecting ',' delimiter (char 5047)`（max_tokens 截断） | 修复重试 + 引擎重试后成功；**M 档 max_tokens 8192→16384** |
| C | `editing(render)` | `Unknown encoder 'H.264 (libx264, High profile, CRF 18, yuv420p)'` | 3 次失败 BLOCKED → 加参数归一化 → 重做成功 |

**账户余额核对**：会话开始 15.95 CNY → 现在 **12.35 CNY**，净减 **3.60 CNY（≈$0.51）**，**高于**逐调用台账 $0.1517。
差异未完全解释 → 列为 **PENDING**（候选原因：埋点前的 6 次调用未入账；计价时段/缓存命中假设与真实账单可能不同；余额读数精度 0.01 CNY）。**以逐调用台账为可审计记录，以余额差为真实花费口径。**

---

## 7. 状态判定（PASS / PENDING / BLOCKED / FAILED）

**PASS**
1. Part A 单组真实 API 测试（A 黑洞）
2. Part A 三组真实内容测试（A/B/C 主题一致、约束遵循、字幕↔旁白一致、三组实质不同）
3. Part B 本地素材最小装配闭环（素材真上屏，帧相关性 0.773 vs 对照 0.000）
4. 回归：25/25 套件 rc=0；三组机械 E2E（mock）各 26/26 出片；ingest 装配 PASS；ffprobe 真实性 PASS；ffmpeg 解码 rc=0；关键帧抽检完成
5. 闸门未被削弱：Claim 闸门实测阻断 15 类生产任务 25 轮；HITL 4 道闸门逐次人工放行

**PENDING（未伪装为 PASS）**
1. **费用对账差额**：台账 $0.1517 vs 余额减少 ≈$0.51（见 §6）
2. **跨模态语义对齐**：分镜描述与旁白的一致性只有结构化检查（字段完整）+ 低值参考指标（2-gram 2.1%），**语义级对齐需人工/LLM 判定** → 未判 PASS
3. **GBK 解码异常**：CLI 层出现过一次 `UnicodeDecodeError: 'gbk' codec can't decode byte 0x8c`，**未落库、未复现**（已对 `ffmpeg_tool` 6 处 subprocess 加固编码；类别已识别，具体触发点未定位）
4. 真实素材仍无外部 provider（仅本地 ingest）；BGM 未开发（本阶段明确禁止）

**BLOCKED**：无（无因外部条件无法推进的项）

**FAILED**：无未处理失败；3 类失败均已修复并回归（见 §6）

---

## 8. Phase 1 结论

- **Part A（真实内容保真）：PASS**。真实 API 被调用且非 Mock；内容确实围绕各自选材；链路主题一致；Claim/HITL 闸门仍生效；失败/超时/限流/API 错误均有显式状态；请求次数、耗时、token、费用、错误均已记录。
- **Part B（本地素材最小装配）：PASS**。素材从 ingest → 索引 → 检索 → 编辑装配 → 渲染 → **成片画面出现**全链打通，并有抽帧相关性证据；无素材时仍如实标注 `PENDING`。
- **Phase 1 整体：PASS（含 3 项 PENDING）**。PENDING 项不影响本阶段两条目标的达成，但**不主张它们已通过**。
