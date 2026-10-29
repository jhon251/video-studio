# PHASE 11 报告：标题与封面候选工程（吸睛但不失实）

> 阶段：Phase 11 ｜ 依据：Phase 11 授权书（2026-09-30）｜ 结论：**DONE（回归全绿）**
> 铁律：台账只增不删；FAILED/PENDING 不改写成 PASS；每条结论附可复算证据；
> 历史基线、v9/C1–C4/E/H 成片、Phase 7–10 产物**零改动**；**`config.json` 零改动**（P10 教训）。

## 1. 开工前状态核对（§1）与差异登记

| 核对项 | 结论 | 证据 |
|---|---|---|
| **config.json 钉定** | ✅ **本阶段零改动** | sha256 `7b03424846f15efc…` = 基线 manifest 钉定值（`phase11_immutable_check.py` 断言） |
| `agents/metadata/agent.py` 现状 | ✅ | 原 prompt 明写"禁止标题党"；schema 仅 `platforms[]`；`run()` 末尾 `strip_claims_deep` 防泄漏 |
| `agents/thumbnail/agent.py` 现状 | ✅ | 4 概念方案字段；`image` provider 默认 `none`（只出方案不出图） |
| 真实旧基线 `a_e0ec01d11b5a.json` | ✅ | 6 平台条目（`title/description/tags/chapters`），**无** `title_candidates`/`ab_plan` ⇒ 结构码 `OLD_FORMAT` 对照锚点 |
| v3 稿 `phase8_ab_v3.json` | ✅ | 8 段；作为本阶段测试与回测脚本 |

**差异登记（现实优先）**：授权书称 metadata agent 有"titles=5 个普通标题"；**实测**其既有字段是
`platforms[]`（6 平台各一 `title`），**并无顶层 `titles`**（`titles` 属 **script** agent）。
故本阶段按现实：**`platforms[]` 逐字保留不动**，新增顶层 `title_candidates`（5 候选）/`ab_plan`。

## 2. P11-1 retention 小修（无 CTA 语义统一）

**问题（Phase 10 实测）**：无 CTA 稿件（机械层 `CTA_ABSENT`）的 CTA 维度按"可用值"取中位，
出现 **仅 1/3 采样给分、median=1.0** 的不一致（把"无 CTA"当成"低分"）。

**改法**：`ops/retention.py` 新增 `_force_cta_not_assessable()`：机械层判定 0 CTA ⇒
CTA 维度对**全部采样**一致输出 `NOT_ASSESSABLE`（`score=null`、`agreement=NOT_ASSESSABLE`、
`scored_samples=0`、`coverage_note` 说明原因）；原始采样值仍保留在 `samples` 供审计；
**单采样路径同样应用**；有 CTA 的稿件不受影响。
**证据**：`retention_check_test` 新增 8/8b/8c/8d 四条断言（**40/40 PASS**）。

## 3. P11-2 标题候选工程

### 3.1 新规范 `config/metadata_style_guide.md`（新建，与 `script_style_guide.md` **分离**）
- **吸睛手法白名单 6 种**：`curiosity_gap` / `specificity` / `stakes` / `expectation_break` /
  `identity_callout` / `process_promise`（每条含定义 + 好例 + 坏例）。
- **失实红线（优先级高于吸睛）**：数字可溯源 / 断言有出处 / 不承诺未交付内容 / 震惊体黑名单 /
  不与正文首句雷同。
- **平台规格**：主标 ≤40 字、封面大字 ≤12 字、A/B 变体 ≥2、多样性 ≥3、回声阈值。
- 全部阈值均由 `core/title_check.THRESHOLDS[...]["basis"]` **注明出处**（不发明新数）。

### 3.2 metadata agent（**加法**）
- schema 新增 `title_candidates[]`（`text/technique/evidence_refs/number_sources/why_win/
  disappointment_risk`）与 `ab_plan`（`platform/variants/metric/execution/note`）；
  **`platforms[]` 与 `required` 未改未删**。
- prompt 重写为"执行 metadata_style_guide：吸睛手法最大化 ∩ 失实红线零违反" + 8 条硬性规则
  （5 候选覆盖 ≥3 手法、数字必须给出处、禁标题诈骗、禁与首句雷同、必写 `disappointment_risk`、
  `ab_plan.execution="manual"`）。

### 3.3 thumbnail agent（**加法**）
- schema 新增 `cover_text_candidates[]`（`text`≤12 字 + `cover_title_pairing` ∈ 互补/递进/反差 +
  `pairing_note`）；prompt 增加封面大字纪律（与主标互补、禁重复、同受失实红线、仍是概念方案不出图）。

## 4. P11-3 只读标题校验器（`core/title_check.py` + CLI `run.py title-check`）

**逐候选输出 PASS/FAIL + 违规码**（14 个）：`TITLE_TOO_LONG`、`TITLE_COVER_TOO_LONG`、
`TITLE_SENSATIONALISM`、`TITLE_TECHNIQUE_INVALID`、`TITLE_EVIDENCE_REF_OUT_OF_RANGE`、
`TITLE_EVIDENCE_REF_DUPLICATE`、`TITLE_NUMBER_UNTRACEABLE`、`TITLE_NO_NUMBER_SOURCES`、
`TITLE_TECHNIQUE_DIVERSITY_LOW`、`TITLE_ECHOES_OPENING`、`COVER_DUPLICATES_TITLE`、
`COVER_PAIRING_INVALID`、`TITLE_EMPTY`、`TITLE_NOT_A_STRING`；结构码 `OLD_FORMAT` /
`NO_TITLE_CANDIDATES`（能力差异，**不判 FAIL**，且新字段门记 `not_assessable_gates`）。

**数字可溯性（反标题诈骗核心门）**：标题中每个数字（阿拉伯/中文/混合/近似）须能在
`number_sources` 指向段落原文找到同值；两侧先归一化（`三千`→3000、`99%`、`几十万`⇒10⁵ 量级匹配）。

**CLI**：`run.py title-check --script <path> [--metadata <path>] [--json] [--no-timestamp]`
—— 只读、不访问 DB、不建 engine、零写入；`--json --no-timestamp` **两次运行逐字节一致**（已测）。

### 4.1 **实测标定（两处修正，均已登记）**
1. **回声门改用 3-gram**：初版用"单字重合率 >0.6"⇒ 旧基线 6 条标题**全部** >0.8（中文同主题必然重合）
   ⇒ 误报泛滥。改为 **LCS ≥12 字 或 3-gram 重合率 >0.5**，并把标定依据写回规范 §二.5。
   **验证**：旧基线 6 条 → **0 条回声误报**；逐字复用首句的构造样例 → 正确报 `TITLE_ECHOES_OPENING`。
2. **数字抽取的"计量性"precision 修正**：初版把量词/习语中的「一」当数字 ⇒ 回测中 3/5 候选被误判
   `TITLE_NO_NUMBER_SOURCES`（实测码：`{"code":"TITLE_NO_NUMBER_SOURCES","numbers":[["num",1]]}`，
   文本如「机器证明最难**的一步**…」「验证**这一环**…」「重新排**一遍**」）。
   修正为：仅**多位数字串**或**单字数字 + 计量单位**（年/月/页/秒/分钟/倍/万/亿/% …）计为数字断言；
   `一步/一遍/这一环/一份` 不再计。**这是精度修正而非放宽**：`十六年`/`三千页`/`20 年`/`99%`/
   `几十万` 等真实数量表达仍全部受门（`phase11_number_probe.py` 前后对照）。
   **该修正使回测判据① 由 2/5 变为 5/5**（原因在**校验器质量**，不在模型或放宽标准）。

## 5. P11-4 测试与真实回测

### 5.1 测试
| 套件 | 结果 | 覆盖 |
|---|---|---|
| `tests/title_check_test.py`（新增） | **30/30 PASS** | 逐违规码（长度/封面长度/震惊体 6 变体/枚举/引用越界与重复/**数字可溯含中文归一化**/多样性/回声/封面对/ab_plan）、legacy 结构与"新字段门不可评"、真实旧基线 6 条**零回声误报**、确定性与 `--json --no-timestamp` 逐字节 |
| `tests/strip_v2_test.py`（扩展） | **29/29 PASS** | 新增 8 条：P11 计划数据在 metadata 产物中保留；**不入** voice 计划/SRT/SRT 文件/ASS/朗读稿/**发布面正文字段**（title/description/tags）；并**显式断言**「发布清单按设计内嵌 metadata 计划数据」这一事实（披露而非回避） |
| `tests/retention_check_test.py`（P11-1） | **40/40 PASS** | 8/8b/8c/8d：无 CTA 统一 `NOT_ASSESSABLE`、修复 Phase 10 的 1/3 采样不一致、有 CTA 不受影响、单采样同样应用 |

### 5.2 真实回测（对 v3 稿跑**新 metadata agent + thumbnail agent**，真实 `deepseek-flash`）
`logs/phase11_title_ab.json`

| 判据 | 结果 | 证据 |
|---|---|---|
| ① 新候选 5/5 通过全部机械门（**数字可溯性 100%**） | **达成** | `counts.pass=5/fail=0`、`number_traceability_100pct=true`、`techniques` 覆盖 **5 种**、`diversity_assessed=true`；封面 3/3 PASS（`cover_gates_ok=true`） |
| ② 与旧基线对比的能力增量 | **达成** | 新：5 候选 ×（technique+evidence_refs）覆盖 ≥3 手法；旧：`structural_codes=["OLD_FORMAT","NO_TITLE_CANDIDATES"]`、0 条带引用 ⇒ `capability_increment=true` |
| ③ 失实红线抽检 | **留待人工确认** | 随机 3 条（固定 seed=11，可复算）列出「标题断言 + 出处段落原文 + 标题内数字」；`manual_verdict="待人工确认（本阶段不宣称语义级不失实已自动化）"` |
| ④ `ab_plan` 存在且 `execution=manual` | **达成** | `platform=bilibili`、`variants=3`、`metric=ctr`、`execution=manual` |

**成本**：本阶段真实 LLM 三次调用合计 **$0.0266**（run1 $0.00641 / run2 $0.00885 / run3 $0.01134），
上限 $0.15 未触。**网络**：0（本阶段无外部请求）。

## 6. 回归与不可变

| 项 | 结果 |
|---|---|
| 新增/更新套件 | `title_check_test` 30/30；`strip_v2_test` 29/29；`retention_check_test` 40/40 |
| **完整既有回归** | **74 套件 / 74 rc=0 / FAILED: []** |
| 不可变核验 | `phase11_immutable_check.py` ⇒ `IMMUTABLE_OK`（**`config.json` = 基线钉定值**；6-G 母片/baseline/Phase 7–10 产物一致） |

## 7. 边界遵守（§7）

**未碰**：发布链（`agents/platform`、`tools/publish_tool.py`）、image/video provider（封面仍概念态）、
script/structure/topic 三个 agent、critic/retention 既有维度与阈值（P11-1 只改 CTA 缺席语义）、
**`config.json` / `config.example.json`**、其余禁改清单（`mm_*`/`semantics`/`multimodal`/词表/
truth 夹具/baseline/`core/integrity.py`/`visual_binding`）。
**未做**：自动发布、自动 A/B 执行（`ab_plan` 只是提案，`execution=manual`）、自动改标题、定时任务。

## 8. 产物 sha256 台账（可复算）

| 产物 | sha256 |
|---|---|
| `config/metadata_style_guide.md` | `008a943fc54133770d0c7583fdd8ddf7d64c9ba0114ac8ff7590aa8f44802d76` |
| `src/video_studio/core/title_check.py` | `91b7781fb4e50056b8c548022b9baf007f1073db4fccccd353fb65b98a91f929` |
| `src/video_studio/agents/metadata/agent.py` | `5a8db7cf9df940d96b73247d56897c056f083ec280ec6eaf8ca512aa8e8b2bf1` |
| `src/video_studio/agents/thumbnail/agent.py` | `b97ccbfd546f97f36966053e4778705f034be1b86d97704d204bbca5973d431d` |
| `src/video_studio/ops/retention.py`（P11-1） | `082fbb391c68fba2a430dc3be38c85fb8290c1c1a63f01180aafe666171972bb` |
| `src/video_studio/cli.py`（title-check） | `311df3d35e3ea99d971af5240a707d0f7b2e9570bef9e27c267574238f1a20e4` |
| `tests/title_check_test.py` | `ec390f11dc07c3f6f67c001853ad5b2275472527e13bf1b8f21ed28c21eeee2c` |
| `docs/regression_2x/logs/phase11_title_ab.json` | `9c120910b739ad224e48b05dd74b3d3258d8ad169e6a9e1d99d172a0cf0f2781` |
| `config/config.json`（**零改动**，= 基线钉定值） | `7b03424846f15efc…`（见 §1） |

## 9. 已知限制 / 下一阶段输入

1. **机械门是必要不充分条件**：数字可溯/引用存在/黑名单/长度/多样性/回声已自动化；
   **断言与出处的语义相符仍需人工终审**（回测 §5.2 ③ 已留"待人工确认"）。
2. **LLM 采样波动仍存在**：同提示两次调用候选文本不同；本阶段判据①以最后一次真实回测为准，
   并把两次中间结果（含一次由**校验器 bug** 导致的 2/5）如实登记（§4.1-2）。
3. `disappointment_risk` / `why_win` 为**文本字段**，机械门只校验其**非空**（未做语义质量判定）。
4. 封面候选由 thumbnail agent 产出（本次 3 条），与主标的互补性只做**枚举与去重**校验。
5. 发布清单按设计内嵌 metadata 计划数据（`publish_*.json` 的 `metadata` 段）——
   本阶段显式断言该事实；若未来要求"清单也不含计划数据"，需改发布链（本阶段边界禁止）。

**完成，STOP，等待下一阶段授权。**
