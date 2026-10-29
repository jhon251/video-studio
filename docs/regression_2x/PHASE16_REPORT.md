# PHASE 16 报告：素材池扩充（负例过滤器验证 → 本地登记 → 受治理获取 → S03 重选 → 交付级重渲染）

> 阶段：Phase 16 ｜ 依据：Phase 16 授权书（素材池扩充，目标=补上"交付级"最后一块短板）
> **结论（逐项如实）**：
> **§1 状态核对 DONE ✔ ｜ P16-1 负例过滤器验证：DONE（门禁 FAIL ⇒ 回退人工短名单）｜
> P16-2 本地素材登记：DONE ✔ ｜ P16-3 受治理获取：DONE ✔（4 张 VERIFIED）｜
> P16-4 S03 重选：DONE ✔（扩池后选材重解，S03 换为专属素材）｜
> P16-5 交付级重渲染：**已执行但渲染后核验门阻断** ⇒ **未登记交付级候选**。**
> **核心收获**：素材池 **6 → 12 张唯一图像**；引擎选材由 **5 种素材** 变为 **12 种**，
> **DQ-2 由 FAIL 转 PASS**（最大复用 10 景 → 5 景）；**S03 线稿盲区消除**。
> **核心发现（新）**：新增素材中 **2 张"多面板/竖构图"** 在 1920×1080 模板的中心裁切下严重失真
> ⇒ 渲染后核验门（冻结口径 48×48、min_corr=0.30）按设计判失败。**未调阈值、未改模板**。
> **零 promotion**；LLM **$0**、VLM **$0.0131**（上限 $1）、网络**仅 Wikimedia 8 次请求**。

---

## 1. §1 开工前状态核对（DONE）

| 项 | 实测 |
|---|---|
| Phase 14 产物 | `tools/vlm_judge.py`(`a4048ea6…`)、`tools/vlm_eval.py`(`9a0aa9d3…`)、真值集 27 对(`6104cfc2…`)、KNOWN_ISSUES **#73 在位** |
| Phase 12 许可覆盖层 | `license_overlay_v1.json`(`24cc78b5…`)：**HAS_RECORD 5 / MISSING 3 / CONFLICT 0**；allowed=PD/FREE_ATTRIBUTION/RESTRICTED/UNKNOWN |
| P7-5 获取治理路径 | `tools/provider_wikimedia.py` **在位**（节流 1s、`max_requests` 预算、许可机械分类、完整 `verify_material` 链）；`config.json` `image.provider=none` ⇒ **未接线**，本阶段以治理模块**显式调用** |
| 13-E 候选配方 | `phase13e_p13e3_final_state.json`：`EXECUTED_GATE_BLOCKED`，候选 `t_249079cc5431_draft.mp4`(`af1e22ed…`)；派生脚本 `8ac58983…`（21 段 / 978.656s）；H5 底片 `3b61dafd…`（守卫通过） |

**现实冲突（以现实为准并登记）**：
1. 授权书称"负例判据 `vlm_relevance_truth_v1`（27 对）"；**实测该真值集 27 = 24 RELEVANT + 3 IRRELEVANT**
   ⇒ 授权书后文的"**现有 24 条人工正例**"与之**一致**（指 RELEVANT 部分），非冲突。
2. 授权书举例陷阱 "**PICO/鲨鱼**"；**本片素材池无该类素材**（PICO/鲨鱼属另一项目谱系）
   ⇒ 以等价的"**跨话题族**"陷阱替代，并在评测集里**如实登记该替换**（未伪造 PICO/鲨鱼对）。
3. 授权书 P16-2 称"把 H5 权威绑定素材（**Russell 页等**）登记进 media/"；**实测 H5 候选目录 18 张位图里，
   只有 2 张在 Phase 12 覆盖层有许可记录** ⇒ 按"零推断"**只登记这 2 张**，其余 15 张逐条登记"未登记原因"。

---

## 2. P16-1 负例过滤器验证：**门禁 FAIL ⇒ 过滤器不接线**

**评测集（冻结，sha256 `fceeae24b6ee9e44…`）**：`tests/fixtures/p16_negative_filter_eval_v1.json`
- **负例 20 条** = 人工 3 + 已知陷阱 10 + **构造跨景 7**（≥20 ✔）
- **误杀测试集 24 条** = 真值集全部 RELEVANT 正例
- 达标线**运行前写死**：负例捕获率 ≥60%；误杀率 ≤5%（≤1/24）；每条 DENY 必附理由
- **构造负例的合理性边界（如实登记）**：取"人工为 A 景选定/接受的素材"配给"B 景需求"，
  限定**跨话题族**以避免假负例；人工负例与构造负例**分开统计**，不混为一谈

**实测（真实 VLM，`qwen3-vl-plus`，prompt `vlm-relevance-judge-v2`）**

| 指标 | 实测 | 达标线 | 判定 |
|---|---|---|---|
| 负例捕获率（全部） | **11/20 = 55.00%** | ≥60% | **FAIL** |
| ├ 人工负例 | 2/3 = 66.67% | — | — |
| ├ 已知陷阱 | 6/10 = 60.00% | — | — |
| └ 构造跨景 | 3/7 = 42.86% | — | — |
| **误杀率（24 正例）** | **13/24 = 54.17%** | **≤5%** | **FAIL** |
| 每条 DENY 附理由 | ✔ 全部有 | 必须 | PASS |
| 成本 | **$0.0131**（17 次真实调用） | ≤$1 | ✔ |

**关键发现：误杀率与 P14-2 门禁失配是同一个统计量。**
P14-2 里 24 条人工正例中机器判 IRRELEVANT 也是 **13 条**（54.2%）。
⇒ 该 VLM 在**本片需求定义**下，对"切题但非逐元素复现"的正例系统性判无关；
因此"**作负例过滤器**"与 P14-2 的"**≥90% 一致**"**不可能同时成立**（同一根因，KNOWN_ISSUES #73）。

**未调参救援（如实登记）**：误杀 13 条 > 允许 1 条，任何"只信高置信度 DENY"的后验阈值调整
均属**运行后调参**（授权书禁止），故**如实 FAIL，不调参**。

**回退路径（按授权书 §2）** ⇒ **P16-3 获取预筛 = 人工短名单（provider 元数据）**，过滤器**不接线**。
两条路均不阻塞后续里程碑 ✔

---

## 3. P16-2 本地素材登记（零网络、零推断）：DONE

- 规则：**只登记 Phase 12 覆盖层已有许可记录**的素材；无记录者**一律不登记**（登记=推断许可，违反铁律）
- **已登记 2 张**（文件复制进 `projects/p_96efdc03e1aa/media/registered/`，字节 sha256 复核一致）：

| asset_id | 文件 | 许可 | 类别 | 署名（逐字沿用记录） |
|---|---|---|---|---|
| `ast-92ca33138ffe64f4` | `Russell_PM_1+1=2.png` | PD-US | PUBLIC_DOMAIN | Whitehead & Russell, Principia Mathematica Vol. II (1912), p.86 — via Wikimedia Commons |
| `ast-96a8c4dc359f55ea` | `S11-D0_…p08_tactic-state-rw.png`（= `p08_0.png`） | CC BY 4.0 | FREE_ATTRIBUTION | Nawrocki, Ayers & Ebner — "An Extensible User Interface for Lean 4", LIPIcs 268 (ITP 2023) |

- **未登记 15 张**（逐条留原因）：`Annalen_der_Physik…`、`Lean_logo2*`、`Newton_Principia…`、
  `code-ext/-success`、`widgets_caas`、`figures/p04,p05,p06,p09,p11,p12,p13` 等
  ⇒ **Phase 12 覆盖层无该素材记录**（许可未明 ⇒ 不放行，不推断）
- 台账：`logs/phase16_local_registry.json`

---

## 4. P16-3 受治理获取（P7-5 路径）：DONE（4 张 VERIFIED）

- 通道：`tools/provider_wikimedia.py`（**仅 Wikimedia**；节流 1s；`max_requests` 预算；许可机械分类；
  下载后**逐张走完整校验链** magic bytes/容器/ffprobe/PIL/尺寸/许可）
- 目标场景 = DQ-2 高复用 / DQ-3 长静态点名场景：**S03 / S06 / S07**（人工撰写查询，非模型生成）
- 结果：**获取 4 张 VERIFIED**（上限 12 ✔），**网络请求 8 次 / 失败 0**，下载 53.6s

| scene | 素材 | 尺寸 | 许可 | 类别 |
|---|---|---|---|---|
| S06 | `ScienceOfMathematicsComte.jpg` (`301ff850be9c`) | 1404×696 | Public domain | PUBLIC_DOMAIN |
| S07 | `Jensen's Inequality Proof Without Words.png` (`33b360a5363c`) | 1445×840 | CC BY-SA 4.0 | FREE_ATTRIBUTION |
| S08 | `Euler proof…quadrilateral theorem` (`5144139591a0`) | 885×1033 | CC0 | PUBLIC_DOMAIN |
| S02 | `Comparison of simple power law curves…` (`a3f0e27204cd`) | 1200×1560 | CC BY-SA 4.0 | FREE_ATTRIBUTION |

- **许可门禁逐张不放宽**：候选许可类别分布 PUBLIC_DOMAIN 25 / FREE_ATTRIBUTION 31，**无一例放宽**；
  被拒不进池的原因均为**非许可因素**：`ASSET_OVERSIZE`（>8MiB 流式中断，3 例）、
  `ASSET_DANGEROUS_FILENAME`（危险文件名，2 例）
- 逐请求记账 + 原始留痕：`logs/phase16_acquisition_ledger.json`（含 `request_ledger`）

**池扩充结果：6 → 12 张唯一图像**（P16-2 +2，P16-3 +4）。

---

## 5. P16-4 S03 重选：DONE（扩池后选材重解）

**落地方式（避免"机器确认即放行"）**：不硬编码指定 S03 的素材，而是把**全部 12 张**作为候选池
（`logs/phase16_retrieval_payload.json`），让引擎的**确定性选材**在更大池中**重新求解**。

**结果**：S03 由 13-E 的 *Four color theorem map of Germany*（稀疏线稿，corr 0.153 ⇒ 13-E 阻断根因）
**换为** `432cd85be6f1`（MGB/IMO 数学竞赛页），其**成片抽帧 corr = 0.569 ⇒ 达标**（≥0.30）✔
⇒ **13-E 的 S03 线稿盲区已消除**。

选材分布（21 景）：**12 种素材**（13-E 仅 5 种），单素材最大复用 **5 景**（13-E 为 10 景）。
注：S06/S07 等"改善性替换提案"按授权书 §5 **只生成不执行**——本阶段以"扩池重解"代替人工逐景改选，
**未走 6-B 提议链**（因未做单点人工指定；该边界如实登记）。

---

## 6. P16-5 交付级重渲染：**已执行，渲染后核验门阻断** ⇒ 未登记交付级候选

- 沙箱：`p_32aded38172b`；渲染任务 `t_8364252d64f1`；**173 s**（≤3h ✔）
- 运动 `enabled=true`；派生脚本沿用（`8ac58983…`，**文本零改动**）；v2 时基（978.656s）
- 产出候选：`projects/p_32aded38172b/output/t_8364252d64f1_draft.mp4`（39,946,220 B）
- **未登记 `render_output`/`attribution`**（fail-closed）⇒ **不是交付物**
- 任务终态 **BLOCKED**：`[ASSET_INSUFFICIENT]`，`method=frame_pearson_48x48, min_corr=0.30`，
  **失败 5 景**：S02(0.122) / S06(0.242) / S07(0.078) / S08(0.058) / S13(0.006)

### 6.1 阻断根因（**独立复核 + 人工看图**，未调阈值）
**机理：1920×1080 模板的中心裁切 vs 全图。** 生产模板对素材做
`scale=1920:1080:force_original_aspect_ratio=increase, crop=1920:1080`（**中心裁切**），
而渲染后核验门算的是 `corr(全图, 成片抽帧)`。对**多面板/竖构图**素材，中心裁切只保留中段：

| 素材 | 原尺寸 | corr(全图, 中心裁切画面) | 判定 |
|---|---|---|---|
| `a3f0e27204cd`（S02 用） | **1200×1560 竖** | **0.1397** | **失真** |
| `5144139591a0`（S08 用） | **885×1033 竖** | **0.0906** | **失真** |
| 其余 10 张（含全部 13-E 素材与新获取的 3 张） | 横/方 | 0.60–1.00 | 安全 |

**人工看图证实（S02）**：成片帧**就是**被分配的素材（`Comparison of Linear, Concave, and Convex Functions`
六个面板图），只是被中心裁切后**只剩中间的 "Concave" 两个面板** ⇒ **素材确实在屏**，
失败来自"**全图 vs 中段裁切**"的口径差，**不是错配、不是占位伪装**。

**证据**：`logs/phase16_crop_safety.json`（逐张裁切安全度）、本报告附图结论。
**未调阈值、未改模板、未改判定逻辑**（授权书明令不碰）。

**第二类（未完全归因，如实登记）**：S06(0.242)、S07(0.078)、S13(0.006) 所分配的素材
**裁切安全度分别为 0.72 / 0.92 / 0.76**（本身安全），却仍在**成片抽帧**上低于 0.30
⇒ 失败另有来源（候选：内容密度/低频化后 48×48 重新采样误差、运动层叠加、字幕区影响）。
**本阶段未对此下结论**（需下一阶段专项定位），**不猜测、不掩饰**。

### 6.2 DQ 复算（生产度量，与 13-E 同口径对比）

| 指标 | Phase 13-E 候选 | **Phase 16（本次）** | 变化 |
|---|---|---|---|
| 唯一素材数 | 5 | **12** | **+7** |
| **DQ-2 素材复用** | **FAIL**（单素材最大复用 **10 景**：`asset_cfae038f6106`） | **PASS**（最大复用 **5 景**：`asset_23e71bc8a864`） | **转好 ✔** |
| DQ-3 静态保持 | FAIL（max 67.374s） | FAIL（max 67.374s） | 未变 |
| └ 超 25s 上限景数 | 21 / 21 | 21 / 21 | 未变 |

**DQ-3 不可由换素材修复（如实登记）**：所有单景时长 30.3–67.4 s，**全部**超 25 s 上限；
超限比例 100% > 20% 阈值。该 FAIL 是**剪辑节奏/场景切分**问题，
修它需要**拆分长镜**（6-B `split_scene` 能力），**不在本次授权范围**（授权仅及"素材池扩充 + S03 重选"）。

**结论**：P16-5 **未达成"交付级候选"**（渲染后核验门未过）⇒ **未登记交付级候选、未做 promotion**。
但**素材池目标达成**：DQ-2 转 PASS、S03 盲区消除、选材多样性 5→12。

---

## 7. 登记 / 边界

**新增产物**
| 内容 | 路径 |
|---|---|
| P16-1 评测集（冻结） | `tests/fixtures/p16_negative_filter_eval_v1.json`（sha256 `fceeae24b6ee9e44…`） |
| P16-1 验证报告 / 结论 | `logs/phase16_negative_filter_report.json`、`logs/phase16_p16_1_conclusion.json` |
| P16-2 登记台账 | `logs/phase16_local_registry.json` |
| P16-3 获取台账（逐请求） | `logs/phase16_acquisition_ledger.json` |
| 扩池候选池 | `logs/phase16_retrieval_payload.json`（12 张，sha256 `1642971546d0febc…`） |
| 裁切安全度证据 | `logs/phase16_crop_safety.json` |
| P16-5 DQ 复算 | `logs/phase16_dq_recompute.json` |
| 本报告 | `docs/regression_2x/PHASE16_REPORT.md` |
| 登记的素材（文件） | `projects/p_96efdc03e1aa/media/registered/`（2 张）+ 获取件 `media/external/`（4 张） |

**不碰（已核验）**：`config.json`（仍无 vlm/execution 段）、DB schema、PI/DQ 阈值与判定逻辑、
`mm_*` 冻结栈、词表、baseline、6-B 执行链语义、既有 frozen 真值（`vlm_relevance_truth_v1` **只读引用**）。

### 7.1 登记位置修正（**回归驱动，如实登记**）
**问题（实测发现）**：把登记件/获取件放进 `projects/p_96efdc03e1aa/media/` 会改变
**冻结的 P7-2 索引状态** —— `tests/asset_candidate_test.py::10` 断言该索引为
**"8 个视觉候选（6 项目 + 2 H5）"**（读取 `ops/asset_index.py::DEFAULT_PROJECT_MEDIA`），
新增文件后实测变为 10 个 ⇒ **该套件 rc=1（含 10d）**。

**处置（不改既有测试、不动冻结状态）**：
- P16-2 登记件：`media/registered/` → **`projects/p_96efdc03e1aa/registered_materials/`**
- P16-3 获取件：`media/external/` → **`projects/p_96efdc03e1aa/acquired_materials/`**
- `media/` 已恢复为**恰 6 个项目图像**（与冻结索引一致）；`asset_candidate_test` 复跑 **33/33 rc=0**
- 登记语义**不变**：仍为本地登记；许可/署名逐字沿用记录，**零推断**；台账更新见
  `logs/phase16_local_registry.json`（含 `amendments`）与 `logs/phase16_acquired_registry.json`
- 扩池候选池以**绝对路径**指向上述位置 ⇒ 渲染与登记均不受 `media/` 冻结状态影响

**池口径（唯一图像，按 sha256 去重）**：`media/` 6（原池）+ `registered_materials/` 2（P16-2，
`1e9d2ab4e64e` 有同 sha 副本，去重计 1）+ `acquired_materials/` 4（P16-3）= **12 张**。

**不做（已核验）**：未放宽许可门（拒收均为 oversize/危险文件名）；**未用机器 RELEVANT 放行任何绑定**；
未跳过人工短名单（P16-1 FAIL ⇒ 已回退人工短名单口径）；**未自动 promotion**。

**预算**：LLM **$0**；VLM **$0.0131**（上限 $1 ✔）；网络**仅 Wikimedia**，8 次请求、逐请求留痕；
渲染单次 **173 s**（≤3h ✔）。

### 7.2 回归与不可变性
- **回归（位置修正后）**：**76 套件 / 77 rc=0 / FAILED: ['motion_test']**
  —— 唯一失败 `motion_test::5b`（断言"无外部文件时运动层 off"）系 **Phase 13-E 已授权**的
  `config/render_motion.json`(`enabled=true`) 与该测试前提冲突，**非 Phase 16 引入**（Phase 13-E/14 均已同样登记）。
- **初跑（未修正位置时）为 75/77**：另一失败 `asset_candidate_test` 已由 §7.1 的位置修正解决并复跑 **33/33 rc=0**
  ⇒ 证明该失败**确由 Phase 16 的文件落点引起**，且**以"移出冻结扫描根"而非改测试**的方式修复。
- **停放开关后复跑**：见 `logs/phase16_suites_parked.log`（预期 **77/77 rc=0**，与 13-E/14 同一处置），
  随后开关文件**逐字节还原**（sha256 前后一致）并复核 `enabled=true`。
- **不可变性**：`phase13_immutable_check.py` ⇒ **IMMUTABLE_OK**（母片 `3b61dafda11c1b9d…`、baseline、`config.json` 等钉定值一致）。
- **零 promotion**：未写任何 `render_output`/`attribution`；未改任何 promotion 状态。
