# PHASE 8 报告：Creator Style v3（红线 + 留存工程）

> 阶段：Phase 8 ｜ 依据：Phase 8 授权书（2026-09-30）｜ 结论：**DONE（回归全绿）**
> 铁律遵守：台账只增不删；FAILED/PENDING 不改写成 PASS；每条结论附可复算证据；
> 历史基线与 v9 / C1–C4 / E / H 候选成片**零改动**。

## 1. 开工前状态核对（§1，必做项）

| 核对项 | 结论 | 证据 |
|---|---|---|
| 6-B（PI/DQ 门禁） | 与代码一致 | `core/direction.py`（`DEFAULT_POLICY` advisory、`enforced: False`）＋ `tests/dq_truth_test.py` **122/122** |
| 6-E（Duration Contract v2） | 与代码一致 | `core/narration.py::duration_contract`（实际 TTS 时长 = narration 事实；`audio_time_base_s`）；相关套件全绿 |
| 6-G 执行链 | 与代码一致 | `docs/regression_2x/logs/phase6g_exec_ledger.jsonl` / `phase6g_rebuild_proposal_register.jsonl` / 冻结快照 sha256 未变（本阶段复核） |
| KNOWN_ISSUES #65–#70 | 已在 `docs/KNOWN_ISSUES.md` L220–226（表格）登记；#67 = 人工验片判 v9 FAIL（不得作为发布候选） | 本阶段**只读**引用，未改台账 |
| **Phase 7 登记状态** | **STATUS.md / CHANGELOG.md 头部均无 Phase 7（P7-1…P7-6）条目** | grep 结果为空 ⇒ 按 §1.2 在下方做**差异登记**（一行，不补写历史条目） |

**差异登记（Phase 7）**：STATUS.md/CHANGELOG.md 缺少 Phase 7 条目；依据用户验收记录
（`P7_1_ACCEPTED` … `P7_6_ACCEPTED`，产物 `docs/regression_2x/logs/visual_requirements.json`、
`asset_index.json`、`asset_diversity.json`、`visual_relevance.json`、`visual_acquisition.json`、
`visual_binding_proposals.json`、`visual_coverage_report.json`，回归 70 套件 rc=0），
Phase 7 实为**已完成并验收**，仅**登记缺失**；本阶段不擅自补写历史条目，仅在此记录差异。

## 2. 改动（§3）

| 文件 | 改动 | sha256 |
|---|---|---|
| `config/script_style_guide.md` | v2 → **v3**：两层优先级（红线层/优化层）+ 留存工程（Hook 纪律 60-90 s / 情绪节拍 5 值且禁连续 3 同类 / CTA 1-2 处且禁裸话术 / 留存不得越界）+ v2 全部条款逐条保留 | 见 §7 台账 |
| `src/video_studio/agents/script/agent.py` | **加法** schema：`segments[].emotion_beat`（enum）/`segments[].retention_device`/顶层 `cta_plan[]`/`hook_map[]`；提示词载入 v3 + 留存元数据纪律 4 条 | 同上 |
| `src/video_studio/agents/structure/agent.py` | **加法** schema：每章 `hook`/`hook_interval_ok`；提示词新增钩子衔接与"连续 90 秒无信息增量点 = 结构缺陷（如实标注）" | 同上 |
| `tests/strip_v2_test.py` | **扩展**：夹具加入 v3 元数据+哨兵；新增 7 项下游隔离断言 | 同上 |
| `tests/pipeline_mock.py` | **扩展**：管线级扫描用户可见产物 + ASS 的 v3 泄漏守卫 | 同上 |
| `tests/creator_style_v3_test.py` | **新增**（27 项） | 同上 |
| v2 快照 | `docs/regression_2x/phase8_style_v2_snapshot.md`（v2 原文逐字，sha256 `17e6439271…d8465`） | 与改动前 `config/script_style_guide.md` 一致 |

**加法纪律（可机检）**：既有字段与 `required` 一律未改未删（`creator_style_v3_test` 1b/1e 断言）。

## 3. 测试与下游隔离（§3.4 / §4）

| 套件 | 结果 | 内容 |
|---|---|---|
| `tests/creator_style_v3_test.py`（新增） | **27/27 PASS** | schema 加法/既有字段未删/枚举强制/v3 规范文本不变量（含 **v2 关键条款逐条留存** 机器比对）/**留存元数据 7 类违规码**/下游隔离（哨兵）|
| `tests/strip_v2_test.py`（扩展） | **21/21 PASS** | 既有 14 项 + 7 项 v3 隔离（voice/SRT/SRT 文件/ASS/metadata/发布稿/朗读稿），且"内部产物保留元数据可追溯" |
| `tests/pipeline_mock.py`（扩展） | **14/14 PASS** | 既有 12 项 + 2 项 v3 管线级泄漏守卫 |
| **完整既有回归** | **见 §5** | 当前口径 70 套件 + 本阶段 1 套件 |

**下游隔离机制（只消费 narration，不新造链路）**：
`core/narration.py::narration_text` 只读 `narration`（并剥离 `[CLAIM:…]`）⇒ TTS 文本；
subtitle 由 `narration` → `build_cues` → SRT/ASS；metadata/publish/narrate 均由 narration 派生。
**哨兵证据**：`V3SENTINEL_*` 出现在 script 内部产物中，但**未出现**在任何用户可见文本。

**诚实边界**：`pipeline_mock` 的 mock 脚本默认无 v3 字段 ⇒ 其守卫证明"管线不会搬运 v3 字段名"
（防回归）；"带 v3 取值的脚本仍不泄漏"由 `strip_v2_test` 与 `creator_style_v3_test` 的哨兵用例证明。

## 4. 离线 A/B 回测（§4，真实 LLM = `deepseek-flash`）

### 4.1 执行台账（**四轮尝试，成本全部计入**）

| 轮次 | max_tokens | v2 | v3 | 该轮成本 | 结论 |
|---|---|---|---|---|---|
| 1 | 4096 | 截断（out=4096） | 截断（out=4095） | $0.00578 | 预算不足；留档 `phase8_ab_attempt1_truncated_*.json` |
| 2 | 8192 | 空内容（out=2024，reasoning 吃满） | 截断（out=8192） | $0.00623 | 留档 `phase8_ab_attempt2_empty_*.json` |
| 3 | 16384 | **合法**（12 段，4 例档） | 截断（out=16385） | $0.01717 | 留档 `phase8_ab_attempt3_v2_valid.json` / `_v3_truncated.json` |
| **4（最终）** | 16384 | **合法**（8 段） | **合法**（8 段） | **$0.01210** | **本报告采用** `phase8_ab_v2.json` / `phase8_ab_v3.json` |

**累计真实花费：$0.04128（上限 $0.30，未触及）**。逐调用 usage/费用/时延均写入每份 artifact
（`usage` / `cost_usd` / `cumulative_cost_usd` / `latency_ms` / `reasoning_tokens`）。

### 4.2 真实技术发现（**不是**规范差异）

`deepseek-flash` 是**推理模型**：`reasoning_content`（隐藏推理）与 `content`（答案）**共享
`max_tokens`**。极小探针实测（`docs/regression_2x/phase8_llm_probe.py`）：
`max_tokens=64` 时 64 token **全部**用于 reasoning、`content` 为空；同题重试 43 token
（37 reasoning + 6 答案）⇒ `content={"ok":true}`。
因此轮次 1–3 的空内容/截断是**推理预算被吃满**，对**两臂同等**发生（不构成 v2/v3 优劣证据）。
**档位配置未被修改**（仍 `llm.tiers.M.model = deepseek-flash`、`max_tokens = 16384`）。

### 4.3 最终对比（同一简报、**两臂共用同一 user 任务行**、同一套后处理指标）

| 指标 | v2 臂 | v3 臂 | 说明 |
|---|---|---|---|
| json_valid / segments | True / 8 | True / 8 | 可比 |
| **前段认知冲突（40 s 口径代理）** | **True** | **True** | 两臂均达标，v3 **未退化** |
| `hook_map` 条目 | 0（字段不存在） | **3** | v3 结构性新增 |
| `emotion_beat` 覆盖 | 0.0（字段不存在） | **1.0** | v3 结构性新增（8/8 段合法枚举） |
| `retention_device` 段数 | 0 | **8** | 每段标注留存装置 |
| CTA 条数 / 裸话术 / 内容绑定 | 0 / 0 / 0 | **2 / 0 / 2** | v3 达规范（1-2 处、无裸话术、内容型） |
| 信息增量标记段数（代理） | 8 | 7 | 相近（不宣称优劣） |
| Claim 边界措辞段数（代理） | 3 | 3 | **未退化** |
| `fact_risks` 存在 / 条数 | True / 12 | True / **13** | **未退化**（v3 略多） |
| 声明总时长 | 706 s | 712 s | 同量级 |
| 旁白字符数 | 3,019 | 3,325 | v3 略长（同任务行下） |
| 单臂成本 | $0.00572 | $0.00638 | 合计 $0.01210 |

**交叉核验**（`docs/regression_2x/logs/phase8_ab_crosscheck.json`，规则与测试同源）：
v3 臂 `v3_validator_violations = []`（无枚举违规、无连续 3 同类节拍、无裸话术、元数据未入正文），
`tts_text_equals_narration_only = True`；v2 臂唯一"违规"是 `V3_HOOK_MAP_SIZE`（字段结构上不存在）。
两臂全文均已留档，供下一阶段 retention-critic 回测。

**A/B 的诚实边界**：① 单样本（每臂 1 次调用），**不构成统计结论**；
② v2 臂在结构上**无法**产出 v3 元数据（`hook_map`/`emotion_beat`/`cta_plan`），故这些行是
**结构性差异**而非"质量提升"的证据；③ 真正可比的是"前段冲突""claim 边界措辞""fact_risks"
三项行为代理 —— 结果显示 **v3 未退化**；④ 真实 LLM 输出**不声称确定性**。

## 5. 回归（§4）

| 项 | 结果 |
|---|---|
| 新增/受影响套件 | `creator_style_v3_test` 27/27 ｜ `strip_v2_test` 21/21 ｜ `pipeline_mock` 14/14 ｜ `dq_truth_test` 122/122 |
| **完整既有回归** | **71 套件 / 71 rc=0 / FAILED: []**（Phase 8 前口径 70 套件 rc=0，本阶段新增 1 套件） |

**回归快照**：`docs/regression_2x/logs/suites_summary.json`（`SUITES: 71 total, 71 rc=0, 0 rc!=0`；
逐套件日志 `docs/regression_2x/logs/suite_*.log`）。

## 6. 边界遵守（§6）

**未触碰**：`core/mm_*.py`、`core/semantics.py`、`core/multimodal.py`、`tests/fixtures/mm_*truth*`、
词表、历史 baseline 与不可变快照（含 Phase 7 的 `visual_binding_proposals.json` /
`visual_coverage_report.json` / `P7_WORKING_TIMELINE` / proposal register / execution ledger）、
`core/integrity.py` 的 PI/DQ 门禁逻辑、`core/visual_binding.py`、`ops/visual_binding.py`、
素材 provider 配置、**LLM 档位配置**。
**未做**：自动换素材（S05 的 REPLACE **保持提案态**）、自动重渲 v9、自动发布、critic 改造、
选题数据接入、视觉层改动。

### 6.1 不可变核验 + 一处**如实登记的差异**（DB 文件字节）

`docs/regression_2x/phase8_immutable_check.py` ⇒ **IMMUTABLE_OK**：6-G final master
`3b61dafd…`（与历史登记一致）、DCv2 master、`6.x-final-baseline` ZIP `bffe9b0d…`（一致）、
manifest/status、execution ledger、proposal register、冻结材料、**Phase 7 全部产物
（p7_1…p7_6，含 `visual_binding_proposals.json` / `visual_coverage_report.json`）** 均与各自
验收阶段的 sha256 一致；v9/C1–C4/E/H 候选成片**零改动**。

**差异登记（必须如实说明）**：与 `phase7_p7_6_acceptance.json` 记录的 `before` 快照比对，
**项目 DB 文件字节已变化**（`658ce58c…` → `6aace13e…`）。只读诊断
（`phase8_db_diag.py` / `phase8_db_writer_diag.py`）结论：

| 项 | 实测 |
|---|---|
| DB 状态 | `journal_mode=wal`、无 `-wal`/`-shm` 附属文件（已检查点回收）、`integrity_check=ok`、`freelist_count=0` |
| 写入者 | **既有回归套件**：最新写入的 project 名为 `phase3b_loudness_fault`、`phase3b_loudness_ok`、`test_phase3a_attribution`、`3c partial/failed/ok`、`phase4c_unusable/bad` 等**测试夹具**（近 24h：+263 tasks / +273 artifacts / +1680 events） |
| 本阶段交付物 | **不写生产 DB**：新增测试用 `tempfile` 工作区 DB；A/B 运行器与全部探针以 `mode=ro` + `PRAGMA query_only=ON` 打开 |
| 结论 | DB 字节变化**由既有套件写测试夹具造成**（Phase 7 期间亦同），**非 Phase 8 代码所致**；因此本阶段**不宣称"DB 逐字节未变"**，只宣称"交付物不写 DB + 关键不可变产物一致" |

该差异同时提示既有台账口径的一处偏差：历史阶段报告的"DB unchanged"仅覆盖**阶段脚本执行窗口**，
未覆盖**回归套件运行窗口**。本阶段按铁律如实登记，**不修改**历史结论。

## 7. 产物 sha256 台账（可复算）

| 产物 | sha256 |
|---|---|
| `config/script_style_guide.md`（v3） | `f9dd41ec1f00da9aeeda976b072404587961912cda2e163baa04448597cbb29c` |
| `docs/regression_2x/phase8_style_v2_snapshot.md`（v2 快照） | `17e6439271dcfed835581cf04d2119d8a773c30191baf10ad53f610dbdfd8465` |
| `src/video_studio/agents/script/agent.py` | `6695a7d900e766dba1c182729a9cb9415a2604e77d4461721f448a32966be75b` |
| `src/video_studio/agents/structure/agent.py` | `eb8bfe49c3e622e24ed4dd608dcba71d0c1e2d3e75dd87f4976df61c7bde5bdf` |
| `tests/creator_style_v3_test.py` | `bd37ac05cae75e5e1715800a1c208365527a255557671b16deacf423a7649625` |
| `tests/strip_v2_test.py` | `2abdad7578e8887aec78159ff136388367841570cea542bbc1fa360db8c74cae` |
| `tests/pipeline_mock.py` | `768586315fe05123b52271cf9d8c5bb6d158d8fe4fa268062accfaa50c0aacf5` |
| `docs/regression_2x/logs/phase8_ab_v2.json` | `1db61f95f43ac34878a12ba43e95a5422c93b1c4b6d682641d76f2ee7f309ac9` |
| `docs/regression_2x/logs/phase8_ab_v3.json` | `b62e9fb0c4528398071dbc2017358801b582c828b0dc883d285f59a17066740b` |
| `docs/regression_2x/logs/phase8_ab_crosscheck.json` | `ae50b627d04b562720805322d27e4238f01a9a425e7e7a4b0b25c7cb955470f2` |

## 8. 已知限制 / 下一阶段输入

1. `validate_script_v3` 当前位于测试文件内；`docs/regression_2x/phase8_ab_crosscheck.py`
   为**逐字复制**同源规则（维护点：两处需同步）。若下一阶段接入 retention-critic，
   建议提取为 `tools/creator_style_v3.py`（本阶段未做，避免超出授权交付物清单）。
2. A/B 为单样本；retention-critic 需多轮采样 + 成片留存代理指标（本阶段无成片，未做）。
3. v9 母片未被重渲；本阶段**不改变**任何成片，"留存提升"必须在下一阶段以新脚本 + 新成片验证。
4. 推理模型（flash）的 `max_tokens` 需覆盖 reasoning + content；生产调用方若沿用旧预算，
   会出现**内容为空**的静默失败。建议下一阶段在 `llm/router.py` 层增加
   "content 为空但 reasoning_tokens>0" 的可诊断错误码（**本阶段未改 router**，属越界）。

**完成，STOP，等待下一阶段授权。**
