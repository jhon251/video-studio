# PHASE 9 报告：retention-critic（内容留存质量评分器 · 机械层 + LLM 评审层，只读）

> 阶段：Phase 9 ｜ 依据：Phase 9 授权书（2026-09-30）｜ 结论：**DONE（回归全绿）**
> 铁律遵守：台账只增不删；FAILED/PENDING 不改写成 PASS；每条结论附可复算证据；
> 历史基线、v9/C1–C4/E/H 候选成片、Phase 7/8 产物**零改动**。

## 0. 职责边界（写入报告，硬性）

| 维度 | 归属 | 说明 |
|---|---|---|
| **事实**（claim 证据链、幻觉、越界断言） | `agents/critic/agent.py`（事实红队，tier R） | 本阶段**零改动**；`retention` **不评事实** |
| **留存**（hook/节奏/情绪/CTA） | 本阶段新增 `core/retention.py` + `ops/retention.py` | 只读、不接入生产闸门、不阻断任务、不自动改稿 |

**`critic` 管事实红线，`retention` 管留存，二者互不替代**（已写入每份报告 `responsibility_boundary`
与 `out_of_scope`，并由测试断言）。

## 1. 开工前状态核对（§1）

| 核对项 | 结论 | 证据 |
|---|---|---|
| Phase 8 交付物在位且与 `PHASE8_REPORT.md` 一致 | ✅ | `phase8_final_verify.py`：报告 sha256 台账 **10/10 一致**；STATUS/CHANGELOG 含 Phase 8 条目与 Phase 7 差异登记；回归 71 套件 rc=0 |
| v3 规范 / 两 agent 新 schema / v3 测试 / A/B 两份日志 | ✅ | `config/script_style_guide.md`(v3) sha256 `f9dd41ec…`、`tests/creator_style_v3_test.py` **27/27**、`phase8_ab_v2|v3.json` 在位 |
| `agents/critic/agent.py`（只读参考） | ✅ | `role="critic"`、`tier="R"`、7 类攻击维度、verdict=PASS/REWORK/BLOCK/NEED_EVIDENCE；**本阶段未改** |
| `llm/router.py`（档位/Schema 校验/缓存先例） | ✅ | 档位 `R=deepseek-v4-pro / M=deepseek-flash`；`validate_json`；缓存先例 `llm_judge_cache`（键含 prompt_version+model） |
| `core/rhythm.py`（只读建议器先例） | ✅ | `status="SUGGESTION"`、`applied=false`、`executed=false`、`requires_human_decision=true` ⇒ 本阶段沿用同款只读语义 |
| 真实脚本样例 `a_49b58fb3dc01.json` | ✅ | 21 段 / 1530 s（v2 时代正片稿）⇒ 作为基线锚点 |

**差异登记（与授权书描述的现实差异）**：授权书 P9-3 要求 `temperature=0`，但 `llm/router.py` 的
`DeepSeekClient.complete` **硬编码 `temperature=0.7`**；授权书同时限定对 router 的改动**仅限 P9-1**。
故本阶段**未改**父类行为，改以 `ops/retention.py::TemperatureZeroClient`（**子类覆盖**，仅替换
temperature、复用父类 api_key/base_url/timeout/重试策略）实现 `temperature=0`；父类与既有调用链
行为**完全不变**。该差异已登记并写入报告。

## 2. P9-1：可诊断错误码（`llm/router.py`，小改动）

**背景（Phase 8 真实发现）**：`deepseek-flash` / `deepseek-v4-pro` 均为**推理模型**，
`reasoning_content`（隐藏推理）与 `content`（正文）**共享 `max_tokens`**；预算被推理吃满时
`content` 为空，上层此前只能看到"JSON 解析失败"。

**改动**：`DeepSeekClient.complete` 在 200 响应后新增判定 —— `content` 为空（strip 后）且
`reasoning_tokens > 0` ⇒ 抛 `LLMError("LLM_REASONING_BUDGET_EXHAUSTED", …)`，异常对象附
`usage`（prompt/completion/reasoning/cache 命中与 miss/**max_tokens_requested**）与 `model`。
**不改档位、不改既有错误路径语义、不自动加大预算、不重试**（同预算重试只会重复烧钱）；
`content` 非空时行为**完全不变**。

**测试**（`tests/retention_check_test.py` 5 / 5b / 5c）：空内容+reasoning>0 ⇒ 错误码 + usage 明细；
内容非空 ⇒ 不误报；空内容但 reasoning=0 ⇒ 沿用原语义。

## 3. P9-2：机械层（`core/retention.py`，纯函数、离线、确定性、**零 LLM**）

阈值**全部镜像** `config/script_style_guide.md` v3「留存工程」节（每项带 `basis` 注明出处，
不发明新数）：hook 窗口 40 s、hook 间隔 90 s、同类节拍 <3、CTA ≤2、段落 >120 s / <8 s、
结尾互动 ≤1。

| 维度 | 判定内容 | v2 稿 | v3 稿 | 生产正片稿（基线锚点） |
|---|---|---|---|---|
| `hook_structure` | 首段落在 40 s 窗口内、开场寒暄黑名单 | **WARN**(HOOK_WINDOW_EXCEEDED) | **WARN**(同) | PASS |
| `hook_interval` | 相邻信息增量点/悬念点 >90 s | PASS | PASS | **WARN**(HOOK_INTERVAL_EXCEEDED) |
| `emotion_beats` | 枚举合法性、连续 3 同类、覆盖率 | NOT_ASSESSABLE(V3_METADATA_ABSENT) | **PASS**(覆盖 1.0) | NOT_ASSESSABLE(同) |
| `cta` | 条数 ≤2、裸话术黑名单、位置 | NOT_ASSESSABLE(CTA_ABSENT) | **PASS**(2 处、0 裸话术) | NOT_ASSESSABLE(CTA_ABSENT) |
| `rhythm` | 超长/过短段落、每段字数/秒 | PASS | PASS | PASS |
| `ending` | 收束表述 + 互动句 ≤1 | PASS | PASS | PASS |
| **mechanical_score** | 权重显式（0.25/0.20/0.15/0.15/0.15/0.10），**仅对可评估维度归一化** | **82.1** | **87.5** | **85.7** |

**结构码纪律**：缺 v3 元数据 ⇒ `V3_METADATA_ABSENT` **单独计数、不计 FAIL**，对应维度
`NOT_ASSESSABLE` 且**不进入评分分母**（避免把"没标"当"做得差"）。证据一律带
**段落下标 + 原文引用**；`WARN/FAIL` 无证据时校验器报错。

**规约保真修正（透明登记）**：初版 `CLOSING_MARKERS` 词表过窄，将 v3 稿的
「最后回到那个判断：…」误判为 `ENDING_NO_CLOSURE`（WARN）。按 style guide（结尾**按功能**定义：
回答"我们现在究竟知道了什么"）补齐同类功能表述。**改前结果：v3 ending=WARN（v2=PASS）；
改后：v2/v3 均 PASS**，判据①由"未达成"变为"达成"。该调参**仅修正规约保真度**，未放宽 FAIL 判定，
且并列登记于此。

## 4. P9-3：LLM 评审层（`ops/retention.py`，tier=R、temperature=0、缓存、PARTIAL 纪律）

- **rubric**：`hook_strength` / `cta_naturalness` / `tension_curve`（各 0-5），**每项必须附原文引用**；
  `tension_curve` 含逐段张力档位与**低谷定位**；输出 top-3 可执行改稿建议（`target/action/why`）。
- **缓存**：`cache_key = sha256(prompt_version | model | script_sha256)`（沿用 `llm_judge_cache` 先例）；
  **ops 只读缓存**（由调用方注入/持久化），ops 自身不落盘。
- **prompt 版本**：`retention-judge-v2`（v1→v2 的变更见 §6 成本与截断登记）。
- **失败纪律**：LLM 不可用/调用异常/输出非法 ⇒ `status=PARTIAL`、**rubric 为空**；
  校验器拒绝"PARTIAL 却带分数"，也拒绝"有分无证据"（测试 6/6d/6e/6f/6g）。

**权威回测（真实 `deepseek-v4-pro`，temperature=0）结果**：

| 稿件 | 机械层 | hook | CTA 自然度 | 张力曲线 | 建议数 | 单次成本 |
|---|---|---|---|---|---|---|
| v2（A/B v2 臂） | 82.1 | 3.5 | 1.0 | 3.0（低谷 [4,6]） | 3 | $0.010012 |
| v3（A/B v3 臂） | 87.5 | **4.0** | **5.0** | 3.5（低谷 [2,7]） | 3 | $0.012105 |
| 生产正片稿 | 85.7 | 4.0 | **null**（无 CTA，判官**未编造**） | 3.5（低谷 [4,10,15,18,20]） | 3 | $0.012973 |

v2 的 hook 改进建议（可执行，节选）：「把核心悬念压缩到前 15 秒，把范围限定与材料说明后置到段1」。
v3 的 hook 建议：「压缩第 0 段范围说明和两层问题铺陈，在抛出『算不算证明』后更快切入 1977 年四色定理事件」。

## 5. P9-4：CLI（只读）

| 命令 | 行为 |
|---|---|
| `run.py retention-check <pid> [--task T]` | 读项目最新 `script_output`（或指定 task 产物）评分；DB 以 `mode=ro`+`query_only` 打开 |
| `run.py retention-check --script <path>` | 评独立脚本 JSON（语料回测入口） |
| `--json` | 键排序；配合 `--no-timestamp` ⇒ **两次运行逐字节一致**（已测） |
| `--no-llm` | 只用机械层（零 LLM 调用、零成本） |
| `--cache <file>` | **只读** LLM 缓存（命中不调用 LLM；本命令从不写缓存） |

两者均**零 DB 写入、不派发任务、不阻断任何流程**；`retention-check` 已加入 CLI 的只读命令白名单
（不构建 engine ⇒ 无副作用）。`ops/retention.py` 已登记进维护守卫的只读 ops 白名单
（`tests/maintenance_fixes_test.py`，**守卫逻辑未改**）⇒ 守卫 **30/30**。

## 6. 真实 LLM 成本台账（逐调用，上限 $0.30）

| 轮次 | 目的 | v2 | v3 | prod | 小计 |
|---|---|---|---|---|---|
| A | prompt v1 / max_tokens 8192 | $0.014880 | $0.014431 | $0.018404 | $0.047715 |
| B | prompt v2（收紧输出）/ 12288 | $0.008662 | $0.011973 | $0.019854 | $0.040489 |
| C | 比较口径修正（**全缓存命中**） | $0 | $0 | $0 | $0.000000 |
| D | 采样 3 | $0.007950 | $0.009046 | $0.009577 | $0.026573 |
| E | 采样 4 | $0.010756 | $0.006593 | $0.017962 | $0.035311 |
| **F（权威）** | 采样 5 | $0.010012 | $0.012105 | $0.012973 | **$0.035090** |
| | | | | | **合计 $0.185178** |

**真实技术发现（登记）**：轮次 A 的 `prod` 在 8192 处被**截断**（`completion_tokens=8193`、
JSON 在 `per_segment` 中途断开）⇒ 校验器如实判 `LLM_OUTPUT_INVALID` / **PARTIAL，未编造分数**；
轮次 B 起将评审预算提至 12288 并在 prompt v2 中收紧输出体积（evidence ≤20 字、`per_segment` ≤24 项），
`prod` 恢复正常。**该发现同时是 P9-1 错误码的同类问题**（推理/输出共享预算），已在报告中并列记录。

## 7. 测试与验收（§3）

| 套件 | 结果 | 覆盖 |
|---|---|---|
| `tests/retention_check_test.py`（新增） | **34/34 PASS** | 机械层逐维度（三份真实稿件夹具）、结构码路径、黑名单变体（5 开场 + 5 CTA）、确定性（机械层逐字节 + CLI `--json --no-timestamp` 逐字节）、**P9-1 三种场景**、LLM 层纪律（PARTIAL 无分数 / 缓存命中一致 / 非法输出 / 无证据拒绝 / P9-1 透传）、职责边界与只读三标记、ops 静态只读证据、机械层纯函数性 |
| 既有 router / 相关套件 | 全绿 | 见下 |
| **完整既有回归** | **72 套件 / 72 rc=0 / FAILED: []** | `docs/regression_2x/logs/suites_summary.json` |

### 7.1 区分度回测判定（授权书 §3 核心验收）

| 判据 | 结果 | 依据 |
|---|---|---|
| ① 机械层：v3 各维度 ≥ v2 | **达成** | hook_structure WARN=WARN；hook_interval PASS=PASS；emotion_beats NA→PASS；cta NA→PASS；rhythm PASS=PASS；ending PASS=PASS（v2 缺元数据以结构码呈现、0 FAIL） |
| ② LLM 层：v3 hook 强度 ≥ v2，且 ≥1 条 v2 可执行 hook 建议 | **达成（权威样本）** | v3 4.0 ≥ v2 3.5；v2 给出 2 条 hook 建议（`target=opening`、`target=ending`） |
| ③ 评分器不评事实对错 | **达成** | `out_of_scope` 明示三条（事实/critic 归口、画面素材、审美）；报告含 `not_a_fact_check` |
| ④ 生产正片稿基线分 | **达成** | 机械层 **85.7**（21 段 / 1530 s）+ LLM rubric（hook 4.0 / CTA null / 张力 3.5，低谷 [4,10,15,18,20]）作为后续改稿对照锚点 |
| 附：二次运行必须命中缓存且输出一致 | **达成** | 三臂 `cache_hit=True` 且**判定内容逐字节一致**（`identical_to_first=True`）；`artifact_hash` 因**按设计包含成本证据字段**而不同，已显式登记（`artifact_hash_equals`） |

### 7.2 采样方差（如实登记，**判据②曾在某一轮未达成**）

`logs/phase9_retention_variance.json`（从 5 份独立真实采样的归档缓存汇总，**零新增成本**）：

| 稿件 | hook 强度 5 次采样 | 均值 | 总体标准差 |
|---|---|---|---|
| v2 | 4.5 / 4 / 4 / 4 / 3.5 | 4.0 | 0.316 |
| v3 | 3.5 / 4 / 4.0 / 4.5 / 4 | 4.0 | 0.316 |

**逐采样配对 v3 ≥ v2 达成率 = 0.8（4/5）**：轮次 B（prompt v2 首轮）出现 v2=4.5 > v3=3.5，
**判据②当轮未达成**（已如实登记，未改写）。结论：机械层**完全确定性**；LLM rubric 层是
**单样本估计**，本阶段判据②以权威样本（轮次 F）为准并同时给出分布；
**若下一阶段要用 rubric 分做决策依据，建议多采样聚合**（本阶段未实施，属越界）。

## 8. 边界遵守（§5）

**未接入生产判定链**：未改 `pipeline/lifecycle.py`、未给任何既有闸门加阈值、`agents/critic/agent.py`
**零改动**；`retention-check` 不派任务、不阻断、不自动改稿（`applied=false`、`executed=false`、
`dispatches_tasks=false`）。
**未触碰**：`core/mm_*`、`semantics.py`、`multimodal.py`、词表、truth 夹具、一切 baseline 与不可变快照、
`core/integrity.py`、`core|ops/visual_binding.py`、素材 provider 配置、**LLM 档位配置**
（P9-1 只加错误码，未动预算与档位）。
**未做**：自动改稿、自动换素材、自动发布、选题数据接入。

## 9. 产物 sha256 台账（可复算）

| 产物 | sha256 |
|---|---|
| `src/video_studio/core/retention.py` | `78cf000a59ef03cacf52452991829bd504560d65cea3aecaceae99d465e8f6fe` |
| `src/video_studio/ops/retention.py` | `cc3341f053656085e705431d1bdca78fbda082479aec96832f2d2f5901aa2648` |
| `src/video_studio/llm/router.py`（P9-1） | `6797b2d100525d9754b745c3c342db789cb13e298e9d4695c4ef5d75c0a3c762` |
| `src/video_studio/cli.py`（P9-4） | `bb403eec6a91b415beb2454b8985d7c284b268723de05e911fc40f456f0a447d` |
| `tests/retention_check_test.py` | `38c0fa2263fa0a8fcba60e1b5f4cd9e5f0a743070ab37ae10a25a184d16741ce` |
| `docs/regression_2x/logs/phase9_backtest_v2.json` | `7ea05c476cab59d161fea00f7dc85b026ca7bc84fa7e26831871b66f9f2dab8a` |
| `docs/regression_2x/logs/phase9_backtest_v3.json` | `95982f24b53154389cfc1121bfbcb0412b6b922b1d43910da044e3b5ad69aeff` |
| `docs/regression_2x/logs/phase9_backtest_prod.json` | `b0267106c1ac6f476df2c4c5cb721b7cc4ddf48264c9dbc596b35439c26b6eee` |
| `docs/regression_2x/logs/phase9_backtest_summary.json` | `807737ca2c57ff56b514c2096eff8b004a0d1dda62cbd8b40bdc6db6cb043672` |
| `docs/regression_2x/logs/phase9_retention_variance.json` | `73c26920a6d0d7b98b22bfabea7022f321a5f0a22c56d780d3e4a57fb1655eab` |

## 10. 已知限制 / 下一阶段输入

1. **LLM rubric 为单样本**（σ≈0.32/5 分），判据②达成率 4/5；建议下一阶段多采样聚合或改用结构化规则。
2. `cta_plan[].at_segment` 的**基数语义（0-based / 1-based）未被 schema 钉住**：v3 A/B 稿出现
   `at_segment=8`（而段数为 8）⇒ 本阶段只把它当证据展示、不参与逻辑判定；建议下一阶段在规范/schema
   中明确为 0-based。
3. 生产正片稿的 `cta_naturalness = null`（无 CTA）——判官**未编造分数**，符合纪律；但也说明
   "CTA 自然度"维度对无 CTA 稿件不可评（当前按 null 处理，未折算 0 分）。
4. 机械层 `hook_interval` 对 v2 时代稿件使用**代理标记**（`intent_proxy`，已登记）；
   v3 元数据在位时以 `retention_device` 为准。
5. 本评分器**不接入任何闸门**：其价值在于"改稿前量化基线 + 改稿后对照"，不构成发布门。

**完成，STOP，等待下一阶段授权。**
