# PHASE 10 报告：数据驱动选题（topic signals）+ retention 评分器硬化

> 阶段：Phase 10 ｜ 依据：Phase 10 授权书（2026-09-30）｜ 结论：**DONE（回归全绿）**
> 铁律：台账只增不删；FAILED/PENDING 不改写成 PASS；每条结论附可复算证据；
> 历史基线、v9/C1–C4/E/H 成片、Phase 7/8/9 产物**零改动**。

## 1. 开工前状态核对（§1）与**现实差异登记**

| 核对项 | 结论 | 证据 |
|---|---|---|
| Phase 8/9 交付物在位 | ✅ | `phase9_final_verify.py`：报告 sha256 台账 10/10 一致；STATUS/CHANGELOG 含 Phase 9 条目；回归 72 套件 rc=0；`core/retention.py`、`ops/retention.py`、`logs/phase9_backtest_summary.json` 在位 |
| `agents/topic/agent.py` 现状 | ✅ | 41 行，`TOPIC_SCHEMA` 无任何数据输入字段；`system_prompt` 无信号规则 |
| `memory/repo.py::working_context` | ✅ | 上下文 = 项目目标 / 已确认决策 / 输入产物（a_* 与依赖产物）/ 本项目自我经验 |
| provider 惯例（`tools/material_provider.py`） | ✅ | `PROVIDER_*` 分类、超时/重试/大小上限、流式截断、fail-closed（本阶段沿用同一分类学） |
| **B 站接口实测（2026-09-30，1 次请求）** | ✅ 可用，但**结构描述有差异** | HTTP 200、`Content-Type: application/json; charset=utf-8`、84,635 B、`code=0` |

**差异登记（现实优先）**：授权书称接口返回 `data:[{...}]`；**实测 `data` 是对象**：
`data = {"list": [ ...50 条... ], "no_more": false}`（`data[0]` 会 `KeyError`）。
本阶段的 provider **两种形态都接受**（`data_shape` 字段如实记录实际形态），并以实测为准。
其余字段与授权书一致（`title/desc/tname/tnamev2/stat{view,like,coin,favorite,share,danmaku,
reply}/duration/pubdate/owner.name/bvid/short_link_v2/rcmd_reason.content`），需浏览器 UA、UTF-8 ✓。

### 1.1 差异登记（二）：`config.json` 被基线**逐字节钉定** ⇒ 不给它加新键

**冲突**：授权书 P10-2 要求 "config 新增 `tools.topic_signals.{provider, manual_path}`"；
但仓库既有硬契约把 `config/config.json` 的**逐字节 sha256** 钉在"当前有效基线"manifest
（tag `5.x-post-final-maintenance-baseline`，值 `7b03424846f1…`）上：

| 契约 | 位置 | 断言 |
|---|---|---|
| M5d | `tests/metrics_test.py` | `manifest["files"]["config/config.json"]["sha256"] == 磁盘现值` |
| L7b / L7c | `tests/offline_mock_test.py` | 同上（并注明"测试契约更新，非业务语义变更"） |
| pin_satisfiable | `docs/regression_2x/phase5l_evidence.py` | 同上 |

本阶段首次实施时确实改写了 `config.json` ⇒ **M5d / L7b 两处转红（实测 71/73）**。
唯一"修法"是**重钉当前有效基线 manifest** ⇒ 属"修改基线/不可变快照"，被本阶段边界（§7）禁止。

**处置（以现实为准 + 登记）**：
1. `config/config.json` **逐字节复原**（从基线 ZIP 内 `config/config.json` 只读提取，
   sha256 复核 = `7b03424846f1…` ✓）；`config/config.example.json` 同步复原（`d5e838509d0c…`）。
2. 配置改由 `topic_signals.resolve_config()` 解析：`config.tools.topic_signals`（若存在，**向前兼容**）
   → **可选外部文件** `config/topic_signals.json`（默认不存在 ⇒ `provider=none`）
   → 内置默认 `{provider:"none"}`；另附 `config/topic_signals.example.json`（示例，不参与读取）。
3. 语义与授权书一致（默认 `provider=none`、既有行为不变、`llm.tiers` 逐字未改），
   差异仅在于"配置落点"：**未动被钉定的 config.json**。
4. 修复后 `metrics_test` **18/18**、`offline_mock_test` **23/23** 恢复；完整回归见 §6。

## 2. P10-1 retention 评分器硬化

### 2.1 多采样聚合
- `ops/retention.py`：`judge_script(..., samples=N)`；`samples>1` 时独立采样 N 次，
  逐项输出 **median + 全距 + agreement**（全距 ≤1.0 ⇒ `STABLE`，否则 `UNSTABLE`），
  并新增 **`scored_samples` / `sample_coverage` / `coverage_note`**（当部分采样给 `null` 时如实披露）。
- **缓存键含 sample 序号**（`prompt_version|model|script_sha|sample_index`）；
- **单采样路径行为不变**（`samples==1` 输出结构与 Phase 9 完全一致，无 `samples` 键）——测试断言；
- CLI：`run.py retention-check --samples N`（**默认 3**）。

**3 采样结果（真实 `deepseek-v4-pro`，temperature=0）**：`logs/phase10_retention_3sample.json`

| 稿件 | 机械层 | hook median(全距) | CTA median(全距) | 张力 median(全距) | 成本 |
|---|---|---|---|---|---|
| v2 | 82.1 | 4.0 (1.0, STABLE, 3/3) | **1.0 (0.0, STABLE, 1/3 ⚠)** | 3.5 (1.0, STABLE, 3/3) | $0.017412 |
| v3 | **80.0** | **4.5** (0.5, STABLE, 3/3) | **4.5** (0.5, STABLE, 3/3) | 3.5 (0.0, STABLE, 3/3) | $0.024975 |
| 生产正片稿 | 85.7 | 4.0 (1.0, STABLE, 3/3) | `null`（0/3 ⇒ `NOT_ASSESSABLE`） | 3.5 (0.0, STABLE, 3/3) | $0.021247 |

**判定：v3 median ≥ v2 median —— 三项全部满足**（hook 4.5≥4.0、CTA 4.5≥1.0、张力 3.5≥3.5）✓
**诚实标注**：v2 的 `cta_naturalness` 中位仅来自 **1/3 采样**（其余为 `null`）⇒ 已用
`coverage_note` 明示"样本数不足，谨慎解读"；生产稿 CTA 为 `NOT_ASSESSABLE`（无 CTA，判官不编造）。

### 2.2 `cta_plan[].at_segment` 语义钉死为 0-based
- `agents/script/agent.py`：字段 `description` 明示"0-based；有效范围 `0..segments.length-1`"；
- `core/retention.py`：机械层新增结构违规码 **`CTA_AT_SEGMENT_OUT_OF_RANGE`** 与
  **`CTA_AT_SEGMENT_INVALID`**（越界/非整数 ⇒ `WARN`，**不计 FAIL**），并记录 `at_segment_semantics`；
- `config/script_style_guide.md` v3 §2.3 增补注脚；
- `tests/creator_style_v3_test.py` 增补断言（1f/1g）；`tests/retention_check_test.py` 增补 3e/3f。

**承认真实影响（行为变更登记）**：Phase 8 的 A/B v3 稿使用 `at_segment=8`（而段数为 8，0-based 下越界）
⇒ 该稿机械层 `cta` 由 `PASS` 变为 **`WARN(CTA_AT_SEGMENT_OUT_OF_RANGE)`**，`mechanical_score`
由 **87.5 → 80.0**。这是**新钉死规则正确检出既有歧义**（不是回归）；Phase 8/9 的冻结产物未被改动，
本文并列登记 87.5（Phase 9）与 80.0（Phase 10）两个口径。

## 3. P10-2 选题信号层（`tools/topic_signals.py`，新模块）

- **两个 provider，同一快照 schema**：
  `manual`（本地策展 JSON）｜`bilibili_popular`（真实接口，**单次请求**，`request_count` 如实记录）。
- **归一化条目**：`{source, kind, title, url, url_derived, bvid, author, tname,
  metrics{view,like,coin,favorite,share,danmaku,reply}, duration_s, published_at,
  rcmd_reason, fetched_at, raw_index, desc}`；缺失数值记 **`null`（不填 0）**；
  仅当 url 缺失而 bvid 存在时派生规范链并**显式标注 `url_derived=true`**。
- **校验与丢弃披露**：条目上限 **100**；按 `url`/`bvid` **去重**；必填（title/url）缺失即丢弃，
  逐条记录 `MISSING_TITLE` / `MISSING_OR_INVALID_URL` / `NOT_AN_OBJECT` / `DUPLICATE_*` / `OVER_LIMIT`
  与 `dropped_count`；全程 UTF-8。
- **fail-closed 错误码**（沿用素材 provider 分类学）：`PROVIDER_CODE_NONZERO`（`code!=0`）、
  `PROVIDER_TIMEOUT`、`PROVIDER_RATE_LIMITED`（429）、`PROVIDER_HTTP_404/5XX/ERROR`、
  `PROVIDER_MALFORMED`（结构异常/非 UTF-8 JSON）、`PROVIDER_EMPTY`、`PROVIDER_OVERSIZE`（>4 MiB 流式截断）、
  `PROVIDER_FILE_MISSING/INVALID`（manual）；**无任何 silent fallback、零伪造条目**。
- **快照模式（确定性关键）**：`run.py fetch-signals --provider bilibili_popular [--out]`（**人工触发**）
  ⇒ `signals/snapshot_<provider>_<UTC>.json`；**topic agent 运行期只读快照、绝不联网**
  （本阶段实测：fetch-signals 请求数 **1**，agent 运行期网络请求 **0**）。
- **config 加法（现实差异登记，见 §1.1）**：授权书要求把 `tools.topic_signals` 写进 `config.json`；
  但仓库硬契约把 `config/config.json` 的**逐字节 sha256** 钉在"当前有效基线" manifest 上
  （`7b03424846f1…`）⇒ 改它会使 `metrics_test` M5d / `offline_mock_test` L7b / `phase5l_evidence`
  转红，而唯一"修法"是重钉基线 manifest——被本阶段边界禁止。故**以现实为准**：`config.json`
  **逐字节未改**（曾一度改写，已从基线 ZIP 精确复原并核验 sha256 与钉定值一致）；配置改由
  `topic_signals.resolve_config()` 解析：`config.tools.topic_signals`（若存在，向前兼容）
  → **可选外部文件** `config/topic_signals.json` → 内置默认 `{provider:"none"}`；
  另提供 `config/topic_signals.example.json`（**示例，不参与运行时读取**）。
  语义与授权书一致：**默认 `provider=none`**，既有行为不变；`llm.tiers` 与其余配置逐字未改。

**真实拉取（1 次请求）**：`signals/snapshot_bilibili_popular_20260929T153554Z.json`
（41,808 B，sha256 `a2edc06b7468138a…`）—— 原始条目 50、保留 **50**、丢弃 0、`kinds=["hot_rank"]`、
`data_shape="dict.list"`（真实形态如实记录）。

## 4. P10-3 topic agent 数据驱动提案（**全部加法**）

- `TOPIC_SCHEMA` 加法：`proposals[].{signal_refs, why_now, angle_gap}` + 顶层 `signals_digest`
  `{count, kinds, top_titles}`；**既有字段与 `required` 未改未删**（测试 7/7b 断言）。
- `system_prompt` 新增「选题信号规则」四条：引用真实条目（0-based 下标）/ `why_now` 基于真实数据 /
  `angle_gap` 说明差异化角度（不是复述热点）/ **无信号时禁止编造热度数据**且 `note` 必须逐字含
  「无数据信号，本提案为纯头脑风暴」。
- 运行期实现（**不改 `base.py`、不加管线阶段**）：`TopicAgent.run` 以与 `base.Agent.run` **同构**的流程
  装配上下文，在工具层加载信号（只读）并注入 prompt 的「# 选题信号」区块；产物中：
  · `signals_digest` 由 **agent 从快照计算并覆盖** LLM 复述（`digest_source="snapshot（权威…）"`）⇒ 摘要不可能被编造；
  · `signals_context` 记录 provider/status/reason_code/快照路径与 sha256/条目数/**`signal_refs` 校验结果**；
  · 无信号时**强制补齐披露串**（若 LLM 未写）；
  · 有信号但 `signal_refs` 违规时，把违规计数写入 `note` 并在 `signals_context` 留证（**不自动改稿**）。
- **人工闸门不变**：topic 任务仍 `SUCCEEDED → NEEDS_REVIEW`，信号只是输入（A/B 实测两臂状态均为 `SUCCEEDED`，
  产物挂在任务上，未自动批准）。

## 5. P10-4 测试与真实 A/B

### 5.1 测试
| 套件 | 结果 | 覆盖 |
|---|---|---|
| `tests/topic_signals_test.py`（新增） | **23/23 PASS** | 归一化/去重/丢弃计数/上限 100、manual 夹具、**6 类 provider 失败路径 + 两种 data 形态**（零伪造）、快照确定性（同文件两次读取逐字节一致）、agent 只读加载与 `provider=none`/无快照路径、`signal_refs` 三类违规码、无信号披露、topic schema 加法不变式 |
| `tests/retention_check_test.py`（更新） | 见 §6 回归 | 新增 3e/3f（at_segment 越界/非整数）+ 1b 期望更新（P10-1 钉死后的预期变更） |
| `tests/creator_style_v3_test.py`（更新） | 见 §6 回归 | 新增 1f/1g（0-based description + style guide 注脚） |

### 5.2 真实 A/B（同一选题目标「做一期 AI/数学类科普视频」，两臂真实 agent 路径）
`logs/phase10_topic_ab.json`

| 判定项 | 结果 | 证据 |
|---|---|---|
| 带信号提案 **100% 有合法 `signal_refs`** | ✅ | 5/5 提案合法（实时复算 `validate_signal_refs.all_valid=true`，产物内校验亦为 true）；引用示例 `[0,10]` |
| `why_now` 非空 | ✅ | 5/5；且**引用真实数据**（如"[0] 以 1170915 播放、66585 点赞在「科学科普」分区"——与快照条目 0 的 `metrics` 逐值一致） |
| `angle_gap` 非空 | ✅ | 5/5 |
| 不带信号走披露路径 | ✅ | `provider=none` ⇒ `signals_context.status=NO_PROVIDER`、`digest_count=0`、`signal_refs` 全空、`note` 含固定披露串 |
| **无编造热度数据** | ✅ | 两臂 `why_now`/`angle_gap` 中所有 ≥1000 的数字**均可在快照 metrics 中找到**（0 处编造） |
| 风险披露纪律不退化 | ✅ | 两臂提案均含 `risks` 字段；无信号臂 `why_now` 明确写"不基于任何热度数据…无法给出时效性理由" |
| 成本 | ✅ | 带信号 $0.0027849 + 不带信号 $0.0014373 = **$0.0042222** |

**总花费（本阶段真实 LLM）**：retention 3 采样（两轮，第二轮含覆盖披露与缓存落盘）
$0.068641 + $0.063634 + topic A/B $0.004222 = **$0.136497 ≤ $0.20** ✓
**网络**：bilibili **1 次**请求（免费）；topic agent 运行期 **0** 次；探针 2 次（§1 实测，含 1 次修正结构探测）。

## 6. 回归与不可变

| 项 | 结果 |
|---|---|
| 新增/更新套件 | `topic_signals_test` 23/23；`retention_check_test`、`creator_style_v3_test` 全绿 |
| **完整既有回归** | **73 套件 / 73 rc=0 / FAILED: []**（Phase 9 口径 72 套件 + 本阶段新增 `topic_signals_test`；期间 M5d/L7b 因 config 改写一度转红，复原后恢复全绿——见 §1.1） |
| 不可变核验 | `phase10_immutable_check.py`（6-G 母片/baseline/Phase 7/8/9 产物 + 关键源码）——见产物 |

**回归快照**：`docs/regression_2x/logs/suites_summary.json`。

## 7. 边界遵守（§7）

**未碰**：search/fact-check 的 search provider 配置（`topic_signals` 是**独立新通道**，不共用）；
`pipeline/lifecycle.py`（信号经 agent 工具层加载，**未加管线阶段**）；topic 人工闸门；
`core/retention.py` 的**既有阈值与维度定义**（P10-1 只加采样聚合与 `at_segment` 校验）；
`mm_*`、`semantics.py`、`multimodal.py`、词表、truth 夹具、baseline、`core/integrity.py`、
`core|ops/visual_binding.py`、素材 provider 与 **LLM 档位配置**（`llm.tiers` 逐字未改）。
**`config/config.json` 逐字节未改**（sha256 `7b03424846f1…` = 基线钉定值，已核验）；
topic_signals 配置改由可选外部文件/内置默认解析（见 §1.1 差异登记）。
**未做**：自动批热点追更（fetch-signals 是**人工触发的单次拉取**，无定时任务）、自动改提案、
自动批闸门、发布。

## 8. 产物 sha256 台账（可复算）

| 产物 | sha256 |
|---|---|
| `src/video_studio/tools/topic_signals.py` | `d3b1770b5cbe61220857922bc5526770bc710582f91b46a5b4f641a043d2fc6a` |
| `src/video_studio/agents/topic/agent.py` | `67e5d2f1d253c764d1477f1caa327fd1d96b1ee957315fa9fc45e32f86e52177` |
| `src/video_studio/ops/retention.py`（P10-1） | `4562fdea3facb5b91f054b5e79c2e0ed837e3f053b0cf8ddfacfc9d243fb87cd` |
| `src/video_studio/core/retention.py`（P10-1） | `2d22b8f63dea9b7d0c30cc9a1a2423c4066f06aae1704d029a0af3d61b064d83` |
| `src/video_studio/agents/script/agent.py`（at_segment） | `1c99bad990445689fa488430440728f1de7e060244079ddbf243227b8ba50ed6` |
| `src/video_studio/cli.py`（fetch-signals + --samples） | `436113c37b3b178a9f5488cc049322fb97e33b4d0b0bf25ab2439980059f365e` |
| `config/script_style_guide.md`（注脚） | `624510f406df9294f42bd68325f2c5e1dd28699c7ca83ba25a75791494fc3304` |
| `tests/topic_signals_test.py` | `b606ced19b1d7900e49e9b70bb6b2c99cc11a3c8391486cf46cc48c077c18f8c` |
| `docs/regression_2x/logs/phase10_retention_3sample.json` | `1b118d38a796f3ce62ff38e499663a3a491a3ed86b4276f9c130b726706288fc` |
| `docs/regression_2x/logs/phase10_topic_ab.json` | `95054b922153f64f5220df2a29c62fb682c4d0d51529c80ba5d1d322d4989a66` |
| `signals/snapshot_bilibili_popular_20260929T153554Z.json` | `a2edc06b7468138a0c1c7447768248fe9741419ca9c28c12782d83c4eb70fe12` |
| `config/config.json`（**逐字节未改**，= 基线钉定值） | `7b03424846f15efc…`（manifest 钉定，见 §1.1） |
| `config/topic_signals.example.json`（示例，不参与读取） | `e2823d455d4711e65e2271552a62460284bade1681aa60c682ef510ab7150615` |

## 9. 已知限制 / 下一阶段输入

1. **v2 的 `cta_naturalness` 仅 1/3 采样给分**（其余 `null`）⇒ 该中位样本数不足（已披露）；
   建议下一阶段对"无 CTA 稿件"规定：该项直接判 `NOT_ASSESSABLE` 而不参与中位（当前按可用值取中位）。
2. B 站接口**无 key**、`ps` 上限与风控策略可能变化；本阶段只做**人工单次拉取**，未做重试与定时。
3. 信号条目**仅热度/分区/时长**等元数据，**不含语义内容**；`angle_gap` 的"差异化"由 LLM 判断，
   本阶段只校验其**非空**与**引用有效性**，未做语义相关性判定（属下一阶段可选工作）。
4. `fetch-signals` 会写入 `signals/`（运行时数据目录）；该目录不参与回归与基线。
5. Phase 8 的 A/B v3 稿仍带 1-based 的 `at_segment=8`（历史冻结产物，未改）；其机械层口径
   在 Phase 9 为 87.5、Phase 10 为 80.0（已并列登记）。

**完成，STOP，等待下一阶段授权。**
