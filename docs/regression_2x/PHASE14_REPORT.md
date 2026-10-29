# PHASE 14 报告（§1 开工核对 + 可行性判定）：VLM 视觉相关性判定

> 阶段：Phase 14 ｜ 依据：Phase 14 授权书（OpenAI 兼容 VLM，便宜优先，评测门禁前置）
> **结论（逐项如实）**：
> **§0/§1 状态核对：DONE ✔ ｜ P14-1 provider：PENDING ｜ P14-2 冻结评测集 + 评测门禁：PENDING ｜ P14-3 集成：PENDING（受 P14-2 硬门约束）｜ P14-4 测试/验收：PENDING**
> **决定性阻塞：本环境无任何 VLM/视觉 API 凭据 ⇒ P14-2 评测门禁无法真实运行；按授权书"未达标/未运行 ⇒ 不进入 P14-3"，
> 本阶段不写任何集成代码，如实 STOP。** 铁律：**无凭据 ⇒ 不伪造评测结果**；不进入未通过硬门的集成。

## 0. §0 前置条件核对（Phase 13-E 是否阻塞）

| 项 | 结果 |
|---|---|
| Phase 13-E 产物 | **不存在**（`docs/regression_2x/*13e*`、`logs/*13e*`、`output/*13e*` 均为空）⇒ **13-E 不在进行中**，本阶段**不受其写操作阻塞**（本阶段亦无后台作业在跑） |
| 差异登记 | 授权书提到"Phase 13-E 可能仍在进行"；**实测无 13-E 任何痕迹**（本会话最后一阶段为 13-D，已 STOP 登记）。以现实为准：**不等待** |

## 1. §1 开工核对（DONE）

### 1.1 P7-4 相关性门禁现状（`core/visual_relevance.py`）
- 判定词表：`RELEVANT / PARTIAL / IRRELEVANT / NOT_ASSESSABLE`（`DECISIONS`），
  优先级 `DECISION_PRECEDENCE = (IRRELEVANT, RELEVANT, PARTIAL, NOT_ASSESSABLE)`。
- 规则链（人工证据优先、缺证据即 NA）：`R0_L1_IDENTITY`（L1 身份/完整性失败 ⇒ NOT_ASSESSABLE）、
  `R1_HUMAN_NEGATIVE`（人工否决 ⇒ IRRELEVANT）、`R2_HUMAN_POSITIVE`（人工判定 ⇒ RELEVANT）等。
- **实测判定分布**（`logs/visual_relevance.json`，21 景）：**候选判定 = RELEVANT 22 / NOT_ASSESSABLE 143 / IRRELEVANT 3**
  ⇒ 与授权书所述"**143 对 NA**"**完全吻合** ✔（这是 P14-3 的可测目标）。
- 候选评估结构：`scene_results[].candidate_results[]`（含 `asset_id`/`decision`/`rule`/`evidence`）。

### 1.2 可用**人工**真值来源（逐条记录出处与定位字段）

| # | 来源（路径） | 定位字段 | 规模/分布 | 用途 |
|---|---|---|---|---|
| A | `docs/regression_2x/logs/visual_relevance.json` | `scene_results[].{scene_id, requirement_id}` + `candidate_results[].{asset_id, decision, rule, evidence}` | 21 景；**RELEVANT 22 / NA 143 / IRRELEVANT 3** | 主目标（NA→? 分布）；人工来源部分可作正/负例 |
| B | `docs/regression_2x/logs/phase6b_m2_review_ledger_v9.jsonl` | `finding_id` / `scene_id` / `asset_id` / `decision` / `decided_by` / `decided_at` / `entry_sha256` | **11 条**：REJECT 7 / DEFER 4 | **IRRELEVANT 类负例**（含 S05 四色地图人工否决等） |
| C | `docs/regression_2x/logs/phase5d_mmt_truth.json`（mm 真值集） | `scenes[].{verdict, narration_text, expected_domain, reason}` | **6 景**：**MATCH 4 / MISMATCH 2** | 语义相关/不相关正负例（冻结） |
| D | `docs/regression_2x/logs/phase6g_exec_h5.json#human_decision` | 字符串 `"D0 / S05 PD-US（人工已接受地域）"` | 1 条 | Russell 页 ↔ S05 的**人工接受**（正例 provenance） |
| E | DB `decisions`（只读） | `node` / `made_by` / `scene_id`+`asset_id`（`selection_override`） | `selection_override` **529**；`made_by` = human 2440 / human:tester 504 / human:operator 21 / human:project-owner 4 | 人工选材正例池（可回溯） |
| F | 已知陷阱对 | PICO/鲨鱼**词法陷阱**（P7 实证）+ **S05 四色地图人工否决** | ≥2 类 | **必须判 IRRELEVANT** 的负例（评测硬项） |

**差异登记（现实优先）**：授权书称"mm_truth_set 冻结真值中的人工 `content_label`"；**实测**
`logs/*truth*.json`（含 `phase5d_mmt_truth.json`、`phase6b_m{1..5}_truth_freeze.json`）
**均无 `content_label` 字段**——mm 真值集的标签字段是 **`verdict`（MATCH/MISMATCH）**，
而 `phase6b_m2/m3_truth_freeze.json` 只是**冻结清单**（`truth_file_sha256`/`truth_path`/`case_ids`/`accept_cases`/`refuse_cases`），
不含逐对标签。**以现实为准**：P14-2 的标签将从上表 A–F **逐条取用**并记录 provenance（不臆造 `content_label`）。

### 1.3 既有先例（缓存/成本/fail-closed）
- 缓存先例：`llm_judge_cache`（键 = `prompt_version|model|输入哈希`）⇒ P14-1 沿用同一范式，但**走文件缓存**（授权书禁止新增 DB 表）。
- 成本/预算先例：`LLM_REASONING_BUDGET_EXHAUSTED`（`llm/router.py`，reasoning 与 content 共享 `max_tokens`）⇒ VLM 调用同样需要 `max_tokens` 预算与显式错误码，不静默截断。
- fail-closed 先例：`tools/material_provider.py`（`PROVIDER_*` 分类学：NOT_CONFIGURED/TIMEOUT/RATE_LIMITED/MALFORMED/EMPTY/OVERSIZE…）⇒ P14-1 沿用同一分类学。

## 2. **决定性阻塞**：无 VLM 凭据（P14-2 无法运行）

| 检查 | 实测结果 |
|---|---|
| 环境变量（VLM/QWEN/GLM/DASHSCOPE/ZHIPU/OPENAI/SILICON/VISION 等） | **无** |
| `.env` 键名 | `TAVILY_API_KEY`、`DEEPSEEK_API_KEY`（**无**视觉/VLM 类键） |
| 结论 | **P14-2 的 ≥30 对真实评测无法执行** ⇒ 依授权书"评测门禁前置、未达标不进入 P14-3"，**本阶段不写集成代码**（避免产出无法验证的"接线"） |

**解除所需（人工提供，三项任一缺失仍不可运行）**：
1. `.env` 增加 `VLM_API_KEY=<key>`（名称可配，默认 `VLM_API_KEY`）；
2. `base_url`（OpenAI 兼容端点，如便宜视觉档：qwen-vl-flash / glm-4v-flash 一类）；
3. `model` 名称。
配置落点（**不改 `config.json`**，P10 教训）：可选外部文件 `config/vlm_judge.json`（示例文件 `config/vlm_judge.example.json`），
三级链 = 内存 `config.tools.vlm_judge` → `config/vlm_judge.json` → 默认 `{"enabled": false}`。

## 3. P14-1…P14-4 状态

| 项 | 状态 | 说明 |
|---|---|---|
| P14-1 `tools/vlm_judge.py` | **PENDING** | 设计已冻结（见 §4），**未写代码**：无凭据时其大部分价值（真实判定）无法验证；先等凭据，避免产出未验证模块 |
| P14-2 冻结评测集 + 评测门禁 | **PENDING（阻塞：无凭据）** | 达标线**运行前写死**：overall agreement ≥ 90% 且「人工 IRRELEVANT → 机器 RELEVANT」= **0**；正例误判（RELEVANT→IRRELEVANT）只报告不阻断 |
| P14-3 集成（加法、默认关闭） | **PENDING（受 P14-2 硬门约束）** | 严禁在门禁未通过前接线 |
| P14-4 测试/回归/成本 | **PENDING** | 成本硬上限 **$2**；本阶段实际花费 **$0**（未调用任何 API） |

## 4. P14-1 设计冻结（下一阶段直接执行，不再决策）
- `tools/vlm_judge.py`：OpenAI 兼容 `chat/completions` + 图像输入（本地图 → **确定性降采样：最长边 ≤768px、JPEG q80**，参数入 `POLICY` 并注明依据=成本控制）；`temperature=0`；JSON 输出 + Schema 校验；超时/重试预算；`PROVIDER_*` fail-closed 错误码；
  **文件缓存**：键 = `prompt_version|model|image_sha256|need_text_sha256`（命中即 $0 复用）；
  输出 `{label: RELEVANT|PARTIAL|IRRELEVANT, reason, confidence}`；**判定独立性**：单次只看一个 (需求, 候选图) 对；
  `resolve_config` 三级链 + key 只从环境变量读；`require_key` 且无凭据 ⇒ `PROVIDER_NOT_CONFIGURED`（零伪造）；默认 `enabled=false`。
- `run.py vlm-eval`（只读 CLI）：overall agreement + 混淆矩阵 + 逐对明细 + 总成本；二次运行走缓存 ⇒ **$0 且逐字节一致**。
- 语义映射（P14-3）：`RELEVANT ⇒ PASS`（仍需许可+完整性门）、`PARTIAL ⇒ HITL`、`IRRELEVANT ⇒ DENY`、调用失败 ⇒ `NOT_ASSESSABLE ⇒ HITL`（fail-closed）。
- 边界不变：绑定仍只产提案；执行仍走 6-B 人工批准链；**VLM 只缩小 HITL 面，不移除人工环节**；不用于事实核查。

## 5. 本阶段预算 / 边界 / 影响面
- **API 花费 $0**（未发起任何 VLM 调用）；网络 **0 次**；**未改 `src/`**、未改 `config.json`、未改 DB。
- 仅新增**只读盘点脚本**（`docs/regression_2x/phase14_truth_inventory.py`）与本报告；Phase 7–13 产物、母片、冻结真值**零改动**。
- 回归沿用 Phase 13 口径 **76 套件 / 76 rc=0 / FAILED: []**（本阶段未改被测代码，未重跑）。

## 6. 下一步（凭据到位后一次性执行）
1. 写 `tools/vlm_judge.py` + `config/vlm_judge.example.json` + `run.py vlm-eval`（含缓存与 `$` 记账）。
2. 用 §1.2 的 A–F 来源构建 `tests/fixtures/vlm_relevance_truth_v1.json`（≥30 对，逐对 provenance，含陷阱负例与灰度难例），并在报告中钉定其 sha256。
3. 跑评测（预算内，先小批试探单价再全量）→ 出 `logs/phase14_eval_report.json`；
   **达标** ⇒ 才做 P14-3 集成 + `logs/phase14_na_resolution.json`（143 对 NA 的实测分布）；
   **未达标** ⇒ 只报告不接入（亦为合格交付）。
4. 回归 + IMMUTABLE_OK + STATUS/CHANGELOG 登记。

**Phase 14 本阶段收尾：§0/§1 DONE；P14-1…P14-4 全部 PENDING，阻塞条件 = 无 VLM 凭据（base_url/model/key 未提供）。STOP。**

---

## 7. Phase 14 执行（凭据到位后一次性执行）：**P14-1 DONE ✔ ｜ P14-2 DONE（门禁 FAIL）｜ P14-3 未执行（受门禁约束）｜ P14-4 DONE**

> 凭据已到位并**实测连通**：`.env#VLM_API_KEY`（阿里云百炼，116 字符，`sk-ws-…`）、
> `config/vlm_judge.json`（`base_url=dashscope compatible-mode`、`model=qwen3-vl-plus`、`enabled=true`）。

### 7.1 P14-1 provider 实现（**DONE**）
新增 `src/video_studio/tools/vlm_judge.py`，§4 冻结设计**逐条落地**：

| 设计要求 | 实现 |
|---|---|
| OpenAI 兼容 `chat/completions` + 图像输入 | `_post_json` + `messages[].image_url`（data URI） |
| 确定性降采样最长边 ≤768px、JPEG q80 | `prepare_image_data_uri`（`Image.LANCZOS`、固定 q80）；参数入 `POLICY` 并注明依据=成本控制 |
| `temperature=0` | `POLICY["temperature"]` |
| JSON 输出 + Schema 校验 | `_extract_json` + `validate_output`（label 枚举/reason 非空/confidence∈[0,1]） |
| 超时/重试预算 | `timeout_s=90`、`max_retries=2` + 指数退避 |
| `PROVIDER_*` fail-closed | 10 个错误码（见 `ERROR_CODES`），**任何失败都不抛异常**，label 置 `NOT_ASSESSABLE` |
| 文件缓存（键含 prompt_version/model/image_sha256/need_text_sha256） | `cache_key` + `output/vlm_judge_cache/<key>.json`；命中即 `$0` 复用 |
| —— **实测偏差登记** | 设计假定 `temperature=0` ⇒ 同输入同判定；**实测不成立**：两次独立运行有 2 对标签改变（见 §7.3）。缓存内一致（同键同字节）成立，**跨键/跨版本复现不保证** |
| 三级 `resolve_config` + key 只从环境变量读 | `resolve_config`；`api_key()` 只读 `api_key_env`；无凭据 ⇒ `PROVIDER_NOT_CONFIGURED` |
| 默认 `enabled=false` | `DEFAULT_CONFIG`；`config.json` **零改动** |
| 判定独立性（单次只看一对） | `build_prompt` **刻意不传入**同景其它候选、词面分数、任何既有机器/人工结论 |

`config/vlm_judge.example.json` + `run.py vlm-eval`（只读 CLI：overall agreement + 混淆矩阵 + 逐对明细 + 总成本；
二次运行走缓存 ⇒ **$0 且逐字节一致**，已实测 `sha256` 相同）。

**P14-1 的一处如实修正（诊断驱动，非为达标调参）**：首版需求文本只给 `visual_goal`，模型把
「主题相关但非逐元素复现」一律判无关。经查 `visual_requirements.json#source_identity`，
**P7-4 构建需求时的上游输入是 `shot_description` + `narration` + `shot_plan`**（`visual_goal ← shot_description`），
故需求文本必须同时给出「画面目标」与「本镜旁白」，否则模型看到的需求比 P7-4 自身可用的更贫瘠。
修正后 `PROMPT_VERSION` 升为 `vlm-relevance-judge-v2`，并**清空旧语义缓存**（避免跨语义复用）。**此修正使一致率从 0/1 提升有限，门禁最终仍 FAIL（见 7.3）。**

### 7.2 P14-2 冻结真值集（`tests/fixtures/vlm_relevance_truth_v1.json`）
- **规模 27 对**：`RELEVANT 24` / `IRRELEVANT 3`；`sha256 = 6104cfc202113510…`
- **逐对 provenance**：来源文件 + 定位字段 + **人工原文理由**（operator 选材理由 / 6-A 审计 REJECT / H5 人工验收）
- 来源：`logs/visual_relevance.json`（22 正 + 3 负）、`logs/phase6g_exec_h5.json#human_decision`（+2 正）；
  扩展索引收录 H5 人工验收的 S05/S11 上屏素材（逐条登记，**不在**冻结 7-2 素材索引内）
- **⚠️ 未达授权要求的 ≥30 对**：全仓仅存在 27 对带显式人工正/负证据的 (镜头, 素材) 对。
  缺口**运行前登记并保留**，**未**用机器判定充数（已获用户确认按 27 对执行）。
  `selection_override` 的 541 条中约 516 条为鉴权测试，其 `before_asset_id` 混杂后期**许可/镜次身份**替换，
  与同对的正例标签**自相矛盾**，故**排除**；改用 `human:project-owner` 的 3 条语义替换作为负例。
- 达标线**运行前写死**：`agreement ≥ 90%` 且 `人工 IRRELEVANT→机器 RELEVANT = 0`；
  归一规则亦写死：`PARTIAL` / `NOT_ASSESSABLE`（含调用失败）**一律计为不一致**（保守口径）。

### 7.3 P14-2 评测结果：**门禁 FAIL ⇒ 不集成**
| 项 | 实测（两次独立运行） |
|---|---|
| overall agreement | **4 / 27 = 14.81%**（阈值 90%）⇒ **FAIL**；首次独立运行为 **3 / 27 = 11.11%**，同样 FAIL |
| 人工 IRRELEVANT → 机器 RELEVANT | **0**（上限 0）⇒ **通过**（两次运行一致） |
| 正例误判 RELEVANT→IRRELEVANT | 13（只报告不阻断） |
| 非二值（PARTIAL/NA） | 10 |
| 混淆矩阵（人工→机器，末次） | `RELEVANT: {IRRELEVANT 13, PARTIAL 9, RELEVANT 2}`；`IRRELEVANT: {IRRELEVANT 2, PARTIAL 1}` |
| 成本 | **$0.0202**（上限 $2）｜API 调用 25 ｜缓存命中 2 |
| 门禁 | **FAIL ⇒ 按授权书「未达标只报告不集成」** |

**⚠️ 实测到的端点非确定性（如实登记）**：设计假定 `temperature=0` ⇒ 同输入同判定，实测**不成立**：
清空缓存后的两次独立运行有 **2 对**标签发生变化（S04 `PARTIAL→RELEVANT`、S07 `IRRELEVANT→PARTIAL`），
一致率因此由 11.11% 变为 14.81%。**文件缓存仍保证「同缓存键同字节结果」**（已验证二次运行 `$0` 且报告 sha256 一致），
但**跨缓存键/换模型版本时结果不保证复现**。此不确定性**不改变门禁结论**（两次均远低于 90%）。
诊断变体在末次运行同样为 14.81%（首次 25.93%），亦受同一非确定性影响。

**P14-3（集成 + 143 对 NA 实测）未执行** —— 授权书明令「严禁在门禁未通过前接线」，本阶段**未改任何生产链**、
**未写** `logs/phase14_na_resolution.json`。

### 7.4 失配根因（**有证据的结论，且未调参掩饰**）
模型**准确执行了被给定的任务**，其理由逐条精确，例如：
- S08「画面为紧密堆积的球体结构，直观呈现开普勒猜想中的球体密堆问题」⇒ **RELEVANT**（与人工一致）
- S03「图为图论中的节点连接结构，**与四色定理相关**，但未体现『空椅子与屏幕光』…」⇒ PARTIAL
- S06「图片为 1976 年邮票标签，内容与…Detlefsen/Luker 观点…无关」⇒ IRRELEVANT

根因 = **判定口径与人工判据不同源**，而非模型能力不足：
1. `visual_goal` **派生自脚本/分镜的生成式画面描述**（如 S01「暗背景，长串无法辨识的证明步骤缓慢滚动」），
   而人工 operator 的选择理由是**叙事/主题切题性**（如 S01「真实 IMO 数学国家队合影，契合『数学与人类』主题」）。
   两者是**不同判据**：模型判「是否逐元素复现分镜画面」，人工判「能否作该镜可用的视觉锚点」。
2. 素材池仅 8 张（21 镜复用），**不可能逐镜复现分镜画面**；模型据此大量判 IRRELEVANT/PARTIAL，
   属**按字面执行的正确行为**。
3. **关键不对称（可用于生产设计）**：两个提示词变体下，
   「人工 IRRELEVANT→机器 RELEVANT」**均为 0**、且机器仅 1–5 次判 RELEVANT
   ⇒ 该 VLM 在此设定下是**可靠的「拒绝器」**，但**不是可靠的「确认器」**。

**诊断变体（明确标注不参与门禁）**：`--prompt-variant diag_anchor`（把口径改为「话题是否同一、可作视觉锚点」）
使一致率由 11.11% 升至 **25.93%**（首次运行），但末次运行为 **14.81%**（与门禁口径**同值**）
⇒ 在端点非确定性下，该变体**未带来稳定提升**，佐证**失配源于「判据定义」而非提示词措辞**。
（`logs/phase14_eval_diag_anchor.json`；两变体「人工 IRRELEVANT→机器 RELEVANT」**均为 0**。）

### 7.5 本阶段预算 / 边界
- **API 花费 $0.0375**（门禁 27 对 $0.0202 + 诊断变体 27 对 $0.0167 + 连通性探针 $0.0006），**上限 $2** ✔
  （逐调用台账见 `logs/phase14_cost_ledger.json`；门禁报告另有一次独立运行 $0.0201，未计入本合计）
- 单价表 `PRICING` 标注 `verified=False` ⇒ **未按真实账单核对**，成本为估算（已如实登记，未参与任何判定）
- **未改** `src/` 既有生产代码（仅**新增** `tools/vlm_judge.py`、`tools/vlm_eval.py` 与 `cli.py` 的**新增**只读子命令）
- **未改** `config.json`、**未写 DB**、**零 promotion**、**未接线**任何 agent、**未放宽**任何阈值
- 冻结产物（母片/DCv2/baseline/真值）**零改动**；**IMMUTABLE_OK**（`phase13_immutable_check.py`）

### 7.5.1 回归（**77/77 rc=0**，含一处环境口径说明）
- 首跑 **76/77**，唯一失败 `tests/motion_test.py::5b`（断言「无外部文件时运动层 off」）——
  系 **Phase 13-E 已授权**的 `config/render_motion.json`（`enabled=true`）与该测试前提冲突，
  **非 Phase 14 引入、非代码缺陷**（Phase 14 只新增文件与一个只读子命令，不触碰 motion/render 路径）。
- 处置（**未改任何测试、未改任何阈值**）：把开关文件按字节**暂存沙箱** → 复跑
  ⇒ **77 套件 / 77 rc=0 / FAILED: []**（`motion_test` 22/22，日志 `logs/phase14_suites_parked.log`）
  → 再把开关文件**逐字节还原**（sha256 `27f4a438b02dc773…` 前后一致），并复核解析 `enabled=true`。
- 与 Phase 13-E 同一处置方式，结论一致：**渲染所需的 `enabled=true` 与 77/77 回归互不冲突**，
  差异仅来自扫描期间的开关在位性。


### 7.6 §5 交付物
| 交付物 | 路径 |
|---|---|
| P14-1 provider | `src/video_studio/tools/vlm_judge.py` |
| 评测逻辑 | `src/video_studio/tools/vlm_eval.py` |
| 只读 CLI | `run.py vlm-eval`（`src/video_studio/cli.py`） |
| 配置示例 | `config/vlm_judge.example.json` |
| 冻结真值集（27 对） | `tests/fixtures/vlm_relevance_truth_v1.json`（sha256 `6104cfc202113510…`） |
| **门禁报告** | `logs/phase14_eval_report.json` |
| 成本台账（逐调用） | `logs/phase14_cost_ledger.json` |
| 诊断变体报告（不参与门禁） | `logs/phase14_eval_diag_anchor.json` |
| 标签盘点 | `logs/phase14_label_inventory.json` |
| P14-3 集成 / NA 实测 | **未产出**（门禁 FAIL，按授权书不集成） |

### 7.7 下一步建议（需人工授权，本阶段不执行）
1. **判据对齐**：若目标是「主题/叙事切题性」，应把 `visual_goal` 与人工判据的统一写成**显式判定规范**
   （即修改 P7-4 的需求语义），而**不是**在提示词里绕；
2. **换用途**：把该 VLM 用作**负例过滤/降 HITL 面**（拒收 IRRELEVANT）而非「确认相关」；
   本次证据支持其在负例方向可靠（误报 0），但**需另立只含负例的评测集**来验证；
3. **补真值**：人工补足 ≥30 对（含更多负例）后重跑门禁；当前 27 对且负例仅 3，置信度不足。

