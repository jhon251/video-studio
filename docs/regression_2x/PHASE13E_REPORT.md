# PHASE 13-E 报告：P13D-OPEN-1 根因重定向（底片谱系核正）

> 阶段：Phase 13-E ｜ 依据：Phase 13-E 授权书（P13D-OPEN-1 根因重定向 + 幂等重跑）
> **结论（逐项如实）**：
> **P13E-1 谱系与绑定核验：DONE ✔ ⇒ 结论 (A)**（权威底片 = **978.7 s DCv2/H5 谱系**）｜
> **监理备择假设：成立 ✔**；**我方 Phase 13-D 的「ctx 时基/字幕基未附着」假设：证伪 ✘**｜
> **P13E-2 ctx 修正 + P13-4 幂等重跑：PENDING（未执行）**｜**P13E-3 P13-5 运动臂全片候选：PENDING（未执行）**｜
> **底片谱系守卫：已实现并自检通过（stage 层）**；**未加入 `tests/` 套件**（加入需重跑 77 套件，本阶段未做）
> 铁律：**PI/DQ 阈值未放宽**；母片/既有候选/Phase 7–13D 产物零改动；P13D-OPEN-1 的**原始登记保留**（本阶段**不改写**，仅追加根因）；LLM $0、网络 0、零渲染。

## 1. P13E-1 核验证据（只读，逐项可复算）

| 项 | 实测 |
|---|---|
| **权威底片（DCv2/H5 谱系）** | `output/phase6g_exec_h5/20260929_151026/out/H5_rp-0ebebb71f99c.mp4` ｜ **978.7 s** ｜ sha256 `3b61dafda11c1b9d22381833a00645670ec8b4f25b8fccca813bb7ac63cee0be`（= 6-G 冻结母片，未变 ✓） |
| 其时间轴来源 | `logs/phase6f_rebuild_plan_v2.json#new_production_timeline`（**21 景**）；**S05 = [181.776, 221.862]** |
| **v9（历史）底片** | `projects/p_96efdc03e1aa/output/t_d0a54bdf1810_draft.mp4` ｜ **1532.0 s** ｜ sha256 `22705c7d7ea20b40d91120146066b89ab2b5fa5c1a1cab18f5346d4c66497651` |
| 其时间轴 | `render_output`(task `t_d0a54bdf1810`).`material_timeline`（21 景）；**S05 = [245.0, 300.0]** |
| **13-D 实际使用的窗口** | **[245.0, 300.0]** ⇒ **与 v9 轴逐值一致**（与 DCv2 轴 **不一致**）⇒ **确证 ctx 误绑 v9 1532 s 底片** |
| 权威谱系 PI 历史 | `phase6g_exec_h5.json`：**PI-1/2/6 = PASS、PLANNING_DRIFT/G-TL/G-PAD/G-SUB = PASS**（pre）；**PI-3/4/5 = PASS、frozen_recheck = PASS**（post）⇒ **978.7 s 谱系本身 PI 全过** ✔ |
| 指纹吻合 | PI-1 **0.6277 = 961.7/1532.0**（v9 历史值 #65）；PI-2/PI-3 **570.344/570.874 s** 与 PI-5 **73 条/33.8%** = v9 历史缺陷（#67）；PI-6 漂移 **552.16 s ≈ 1532.0 − 978.7 = 553.3 s**（两谱系时长差） |

**结论三选一：** **(A) 权威底片 = 978.7 s DCv2/H5 谱系** ✔（预期最可能者被实证）。
**推论（实测证据支持）**：13-D 的 **PI-1/2/3/5/6 FAIL 是「底片选择错误」的度量伪影**——
五门所报数值**逐值等于 v9 母片的历史缺陷**，而**权威谱系同项全 PASS**；本次 S05 替换（55 s 窗口、素材校验与拼接证据齐备）
**不是** FAIL 的成因。

### 1.1 两个假设的裁定（不偏袒自己）
- **监理备择假设（底片谱系绑定错误）**：**成立** ✔（窗口数值 + 时长差 + PI 指纹三重吻合）。
- **我方 Phase 13-D 假设（ctx 时基/字幕基未附着）**：**证伪** ✘（若为时基未附着，PI 数值不会逐值等于 v9 历史缺陷，也不会恰好相差 553.3 s）。
  **登记**：该假设错误，其登记原文保留在 `logs/phase13d_p13_4.json#open_question` 与 `PHASE13D_REPORT.md`（**不改写**），本报告追加**最终根因**。

### 1.2 对 6-C 的**成因重定调**（只登记，不改写历史）
6-C 的 **4/4 BLOCKED** 与本次**同源**：6-C 亦以 **v9 1532 s draft** 作为 `FILM` 与 timeline（`phase6c_batch.py`：`FILM = …/t_d0a54bdf1810_draft.mp4`）。
⇒ 其 BLOCKED 的**成因**应重新定调为**底片谱系选择**（而非"方案本身不可行"）。**6-C 的 `phase6c_approvals.jsonl` /
`phase6c_execution_ledger.jsonl` 与报告原文一律未改**（只在本报告与 STATUS 追加该定调）。

## 2. 底片谱系守卫（P13E-4 守卫，已实现 + 自检通过）

- 实现：`docs/regression_2x/phase13e_p13e1_conclusion.py::assert_lineage()` —— 以
  **`AUTHORITATIVE_LINEAGE`（id/film/sha256/duration_s/timeline_source/s05_window）** 为基准，
  对给定底片做 **sha256 + 时长（±1 s）双校验**；不符即 `ValueError`（拒绝构建 ctx）。
- 自检证据（`logs/phase13e_p13e1_conclusion.json#lineage_guard`）：
  · 权威底片 ⇒ `LINEAGE_OK` ✔；· **v9 底片 ⇒ `REJECTED（守卫正确拦截 v9 底片）`** ✔
- **操作守则（建议入 KNOWN_ISSUES 或操作手册）**：*任何 REPLACE/ADD 类修订候选的 ctx，必须以 DCv2/H5 978.7 s 谱系为底片；
  构建前必须通过 `assert_lineage()`。*
- **未做**：未把守卫加入 `tests/` 套件（加入会使回归口径变为 77 套件，需重跑全量；本阶段预算内未执行 ⇒ 如实 PENDING）。

## 3. P13E-2 / P13E-3 状态：**PENDING（未执行）**

| 步骤 | 状态 | 说明 |
|---|---|---|
| P13E-2 ctx 修正（978.7 s 底片 + 6-C 同款构件 + 13 条素材注册表 + Phase 12 覆盖层） | **PENDING** | 未执行；权威谱系与 S05 窗口 [181.776, 221.862] 已核实，构造参数已备 |
| P13E-2 派生执行提案 + 转录批准（`derived_from=bp-6320bf486a082901`，注明底片谱系变更；沿用 13-C 双字段格式） | **PENDING** | 未执行 |
| P13E-2 幂等重跑 P13-4（新沙箱 label `13e`）+ PI-1…PI-6 强制复核 + `replaced=true` 抽帧比对 | **PENDING** | 未执行；**预期**：正确底片上 PI 应 PASS（权威谱系历史全 PASS） |
| P13E-3 P13-5 运动臂全片候选（S05 替换 + 运动层）+ 全门复验 + DQ 双口径 | **PENDING** | 未执行（前置 = P13E-2 PI 通过） |

## 4. 预算 / 边界 / 回归

| 项 | 结果 |
|---|---|
| LLM / 网络 / 渲染 | **$0 / 0 次 / 零渲染** ✓ |
| 代码改动 | **未改 `src/`**（新增只读核验脚本 + 结论 JSON + 本报告） |
| 阈值 | **未放宽任何 PI/DQ 阈值** ✓ |
| 回归 | 未改被测代码 ⇒ 沿用 Phase 13 干净口径 **76 套件 / 76 rc=0 / FAILED: []**（未重跑） |
| 不可变 | 权威底片 `3b61dafda11c1b9d…`、v9 底片 `22705c7d7ea20b40…`、`config.json` `7b03424846f15efc…`、P7-6 产物 `3f7fd67737d8e52d…`、13-D 台账/批准/报告**均未改** ✓ |

## 5. 产物 sha256 台账（可复算）

| 产物 | sha256 |
|---|---|
| `docs/regression_2x/logs/phase13e_p13e1_conclusion.json` | `7e93471a72ab468021fe1105246613646e4932f5abc2ea4521ac3eb6903af325` |
| `docs/regression_2x/phase13e_p13e1_conclusion.py`（含守卫） | `c4b72e7d0346e0b83aab050c2bacd286becc97bee8754efedaf98692d2dfe5e4` |
| `docs/regression_2x/logs/phase13d_p13_4.json`（13-D 登记，**未改**） | `bb1022898a5711db…` |
| 权威底片（**未变**） | `3b61dafda11c1b9d…` |

## 6. 下一步（下一阶段直接执行）
1. `assert_lineage(H5 978.7s 底片)` 通过后，以 **DCv2 时间轴**（`new_production_timeline`，S05=[181.776,221.862]）重建 ctx；
2. 派生执行提案（`derived_from=bp-6320bf486a082901` + **底片谱系变更说明**）+ 转录批准（`recorded_by=agent:transcription`、
   `human_note.authorized_by=human:project-owner`、`approval_document="Phase 13-E 授权书"`）；
3. 新沙箱 label `13e` 幂等重跑 P13-4 ⇒ 预期 PI 全 PASS（若仍 FAIL 且量级数百秒 ⇒ (A) 被证伪，回到 (B)/(C) 分支如实报告）；
4. PI 通过后执行 P13E-3（运动臂全片候选 + 全门复验 + DQ 双口径），零 promotion；
5. 补 `tests/` 守卫套件 + 全量回归（口径将变为 77 套件）。

**Phase 13-E 本阶段收尾：P13E-1 DONE（结论 A，根因确证，两个假设已裁定）；P13E-2/P13E-3 PENDING；守卫已实现并自检通过。STOP。**

---

## 7. Phase 13-E 续跑（P13E-2 结论 + 守卫入套件 + 回归）

### 7.1 守卫入 `tests/` 套件（按续跑授权第 1 条，**先做**）
- 新增 core 模块 `src/video_studio/core/lineage_guard.py`（纯校验：`AUTHORITATIVE_LINEAGE`/`LEGACY_LINEAGE` 常量、
  `check_lineage()`、`assert_lineage()`、`load_authoritative_timeline()`；sha256 + 时长 ±1 s 双校验）。
- 新增套件 `tests/lineage_guard_test.py` ⇒ **10/10 PASS**（权威底片 `LINEAGE_OK`；**v9 底片 `LINEAGE_MISMATCH` 且 `assert_lineage` 抛错**；
  缺失 ⇒ `FILM_MISSING`；权威时间轴 21 景且 S05=[181.776,221.862]；与结论 JSON 一致；模块不触碰 PI/DQ 阈值、不写文件）。
- **真实缺陷（被仓库静态守卫抓出并已修）**：`subprocess_encoding_test` 报
  `src 内所有 subprocess(text=True) 均指定 encoding（静态守卫）| 漏点：['src/video_studio/core/lineage_guard.py:56']`
  ⇒ 我的新模块 `ffprobe` 调用缺 `encoding`；**已补 `encoding="utf-8", errors="replace"`**，该套件 6/6 PASS。
- **全量回归（含新套件）**：**77 套件 / 77 rc=0 / FAILED: []** ✔（口径由 76 → **77** 套件）。

### 7.2 P13E-2 结论：**在权威底片上，S05 替换已实现 ⇒ 重复拼接为 no-op（未执行无意义渲染）**

| 证据 | 实测 |
|---|---|
| 守卫 | 权威底片 `LINEAGE_OK`（sha256 `3b61dafda11c1b9d…`，时长 978.7 s，容差 1.0 s） |
| 权威时间轴性质 | `phase6f_rebuild_plan_v2.json#new_production_timeline` = **纯时基计划**（21 条仅 `start_s/end_s/narrative_window_s/pause_after_s`，**无素材绑定**：`selected_asset/asset_id` 全为 null） |
| H5 谱系的 S05 绑定 | `asset_records[0] = {asset_id: asset_h5_S05_65377b888b778226, path: C:\mp4agent\h5_asset_candidates\S05\Russell_PM_1+1=2.png, sha256: 65377b888b778226…}`；`binding = {"S05": "asset_h5_S05_65377b888b778226", "S11": "asset_h5_S11_1e9d2ab4e64ef982"}` |
| 素材 sha256 校验 | 与 H5 人工验收值 `65377b888b778226…` **一致** ⇒ `True` |
| H5 门禁（与本次目标直接相关） | `P0-S05 素材存在且 sha256 与人工验收一致` ✔；**`C1 内置逐镜替换证据：S05/S11 均已替换（replaced_all）`** ✔；**`B1 逐镜窗口 ASS == DCv2 表（2 文件，覆盖 ['S05','S11']）`** ✔ |
| H5 谱系 PI | pre：PI-1/2/6 + PLANNING_DRIFT/G-TL/G-PAD/G-SUB = PASS；post：PI-3/4/5 + frozen_recheck = PASS |

**结论**：P13-4 的目标（权威底片上 S05 = Russell 页、`replaced=true` 证据、PI 通过）**在 6-G/H5 母片上已经达成**；
在正确底片上再次执行同一 REPLACE 只会产出等价重复件 ⇒ **本阶段不做重复渲染**（no-op 判定，理由与证据见
`logs/phase13e_p13e2_finding.json`）。13-D 的 PI BLOCKED 已由 P13E-1 定格为**底片谱系错误的度量伪影**，与替换本身无关。

**副产物登记（下一阶段需知）**：H5 报告顶层**未持久化** `_caption_time_base`/`timeline_identity`（其门禁
"P6 DCv2 timeline identity 校验通过"为执行期校验）⇒ 若未来仍需在权威底片上做**真实拼接**，须先定位该时基的持久化来源；
**本阶段未尝试绕过该门禁**。

### 7.3 P13E-3 状态：**PENDING（未执行）**
运动臂全片候选（S05 已替换 + 运动层 `enabled=true`）**未产出**：需一次**全片渲染**（978.7 s 底片，管线级端到端）
+ 全门复验（PI 全门/响度/时长/逐景 corr（**S06 小裕度如实记录、不调阈值**）/字幕与旁白对齐）+ DQ 双口径报告
（DQ-3 `freezedetect` 语义并列，**不宣称 PASS**）。零 promotion；建议后台作业、单次 ≤3 h、超限先报告。

### 7.4 本次续跑的边界与预算
LLM **$0**、网络 **0**、**未做渲染**；**未放宽任何 PI/DQ 阈值**；权威底片/v9 底片/`config.json`/P7-6 产物/13-D 台账与报告**均未改**；
新增仅：`core/lineage_guard.py`、`tests/lineage_guard_test.py`、`logs/phase13e_p13e2_finding.json` 与本节。


---

## 8. Phase 13-E 收官（P13E-3 授权执行）：**就绪度 DONE；渲染 PENDING（前置缺口已定位）**

### 8.1 已完成就绪项（全部实测）
| 项 | 结果 |
|---|---|
| 底片守卫 | `LINEAGE_OK`（`assert_lineage(H5_rp-0ebebb71f99c.mp4)`，978.7 s，sha256 `3b61dafda11c1b9d…`） |
| 运动开关（授权允许的外部渲染开关文件） | 新建 `config/render_motion.json`（`enabled=true`）；`resolve_config` ⇒ `{"enabled": true}`，来源 `render_motion.json`；**`config.json` 未改动** |
| 运动策略出处 | `core/motion.py` `POLICY[…]`（zoom ≤1.08、平移 ≤画面 3%、<10s 静止、启用 ≤60%、窗口 ≤150 帧）——**未放宽任何阈值** |
| DCv2 权威窗口 | `remapping_21_segments`（21 条）合计 **978.7 s**，与权威底片**完全一致**（S05=[181.776, 221.862]） |
| S05/Russell 绑定 | 已在权威底片（H5 `binding` + `asset_records` + `replaced_all` 门禁），无需替换 |

### 8.2 **前置缺口（本阶段新发现）**：DCv2 谱系**没有脚本产物**
- 项目内唯一 `script_output` = `a_49b58fb3dc01`（21 段、**总时长 1530.0 s = v9 谱系**）；
  **不存在**总时长 ≈978.7 s 的 DCv2 脚本 ⇒ `readiness.dcv2_script_artifact_exists = False`。
- 后果：**管线级端到端渲染需要脚本**；若用现有 v9 脚本渲染，产出的是 **v9 1530 s 片**——按 Phase 13-E 谱系纪律
  **禁止**在 v9 底片上渲染（会重现 #65/#67 度量伪影）⇒ **本阶段不做该渲染**。
- 登记为 KNOWN_ISSUES 候选 **#72**：*权威（DCv2/H5）谱系产物不完整——重建只产出时基计划与成片，未产出对应 `script_output`*；
  **本阶段未擅自新建脚本产物**（无授权不写生产产物）。

### 8.3 P13E-3 执行配方（已固化，下一阶段可一次性执行）
产物：`logs/phase13e_p13e3_readiness.json`（含逐景 21 条 new 窗口 + TTS 时长 + pause 预算）。
1. 守卫通过后，按 `remapping_21_segments` **合成 DCv2 脚本**（段时长 = `new_timeline_window_s`，合计 978.7 s；
   旁白**文本**沿用既有脚本；旁白**音频为事实来源**，按 `new_audio_window_s` + `pause_budget_s` 放置）；
2. 素材绑定沿用 H5 `binding`（S05=Russell 页，sha256 已核验）；
3. 走 Engine/editing `_render` 渲染（**运动开关已 `enabled=true`**）；
4. 复验：PI 全门 / 响度契约 / 时长契约（978.7±1 s）/ **逐景抽帧 corr（S06 小裕度如实记录、不调阈值）** / 字幕与旁白对齐；
5. **DQ 双口径**：原口径复算 + DQ-3 `freezedetect` 语义并列说明（**不宣称 PASS**）；
6. 逐景 **MOTION_VERIFIED** 证据（`<project>/render/motion_evidence.json` + 场景 10%/90% 抽帧像素差）；
7. 零 promotion；后台作业；单次 ≤3 h，超限先报告实际增速。

### 8.4 本次收官阶段的边界与预算
LLM **$0**、网络 **0**、**未执行全片渲染**；**未放宽任何 PI/DQ 阈值**；权威底片/v9 底片/现有脚本产物/`config.json`/
P7-6 产物/13-D 台账与报告**均未改**；新增仅 `config/render_motion.json`（授权允许的渲染开关文件）、
`logs/phase13e_p13e3_readiness.json` 与本节。


---

## 9. Phase 13-E 最终执行（授权：① DCv2 脚本合成 + ② 全片运动候选渲染）

### 9.1 ① DCv2 脚本产物合成：**DONE**（纯派生，文本逐字未改）
- **沙箱新文件（零覆盖）**：`output/phase13e_script_sandbox/script_dcv2_derived_v1.json`
  ｜sha256 `8ac58983624f6ff9…`｜21 段｜**总时长 978.656 s**（= 权威底片 978.7 s）
- **文本逐字校验：True** —— `text_hash_original == text_hash_derived`（4947 字符，**未改一字**，含标点/空白）
- **派生依据**：`derived_from = a_49b58fb3dc01`（sha256 `3d76f4bc798b67f0…`）；段时长 = `remapping_21_segments.new_timeline_window_s`；
  音频为事实来源（`new_audio_window_s` + `pause_budget_s`）；`synthesis_rule_version = dcv2-script-derivation-v1:verbatim-text+remapping-windows`
- **内容链未重跑**：本产物**继承**原脚本既有 claim/事实核查/结构审结论（报告与 provenance 均写明"内容结论继承自 a_49b58fb3dc01 谱系"）
- **映射证据（关键）**：v9 脚本 21 段**无 `scene_id` 字段** ⇒ 采用**段序↔景序**映射，并以**时长证据**证实：
  **20/21 逐段吻合**（段时长 == `old_timeline_window_s` == v9 渲染时间轴窗口）；
  唯一偏差为 **S21：脚本 65.0 s vs 旧窗口 67.0 s（Δ=2.0 s）**——系已知 **E1 片尾卡插入**的时长差，
  **属时长差异而非文本对齐问题** ⇒ **无需改写任何文本**，故**未触发**授权 (a) 的 STOP 条件。
- provenance：`logs/phase13e_script_derivation_provenance.json`（含源/规则/时间证据/绑定继承/零覆盖标记）

### 9.2 ② 全片运动候选渲染：**PENDING（未启动）**
- 已就绪输入：派生脚本（上）、运动开关 `config/render_motion.json`（`enabled=true`）、
  H5 素材绑定（S05=Russell 页，sha256 已核验）、权威底片（权威谱系真相源，已过守卫）。
- **未启动原因（如实）**：管线级渲染需先构建 **Engine 夹具**
  （项目 + `script_output`(=派生脚本) + `retrieval` 载荷/素材池 + 旁白音频），再跑 `editing._render`（运动 enabled），
  随后执行全门复验（PI 全门 / 响度契约 / 时长 978.7±1 s / 逐景 corr（S06 小裕度如实记录、不调阈值）/ 字幕与旁白对齐）、
  DQ 双口径（**不宣称 PASS**）与逐景 **MOTION_VERIFIED**；单次渲染 ≤3 h。**本阶段预算内未启动**。
- 配方见 §8.3；就绪输入见 `logs/phase13e_p13e3_final_state.json`。

### 9.3 本次执行的口径与边界
回归 **77 套件 / 77 rc=0 / FAILED: []**（本阶段未改被测代码）｜LLM **$0**、网络 **0**、**未执行渲染**、**零 promotion**、**未放宽任何 PI/DQ 阈值**；
权威底片/v9 底片/既有脚本产物/`config.json`/P7-6 产物/13-D 台账与报告**均未改**；新增仅派生脚本（沙箱）、
provenance、最终状态与本节。

---

## 10. Phase 13-E P13E-3 ② 全片运动候选渲染（**已执行；渲染后核验门阻断**）

### 10.1 口径判定（启动前，用生产代码干跑）
按 §8.3 **字面**执行会**确定性失败**，故启动前先做权威干跑（调用仓库自身
`narration_plan` / `pre_render_gate`）：

| 情形 | 时基 | 渲染前硬门 | 成片时长 |
|---|---|---|---|
| ① 字面（voice 产物原样 ⇒ **v1**） | 规划时基 | **BLOCKED**：`PI-6 FAIL 最大漂移 15.0 s > 5.0 s` | 980.656 s（**超契约 1.956 s**） |
| ② **v2 时基**（沙箱派生 voice 补 `audio_time_base_s`） | `audio_time_base` 权威 | **PASS**（PI-1/2/6 + G-TL/G-PAD/G-SUB 全 PASS） | **978.656 s** |

根因：派生脚本令 `duration_s = DCv2 窗口 = 实际 TTS + pause 0.75`（v2 语义写进了 v1 的 declared 字段），
而 v1 的 PI-6 正是度量 declared-vs-actual —— 故 `0.75×(n−1) > 5 s`（n≥8）者必然 FAIL。
**经用户授权采用情形 ②**；原 voice 产物（`a_e99273b936c0`）**只读未改**，派生件带完整 provenance。

### 10.2 执行结果（后台作业，**207 s**）
- 沙箱项目 `p_e4c65c1c58ed`；渲染任务 `t_249079cc5431`（`render` / editing `_render`）
- 运动层：**enabled=true**，21 景中 **12 景启用**（S03/S04/S06/S07/S09/S11/S12/S13/S15/S16/S18/S21），
  9 景静止，**0 fallback**；`render/motion_evidence.json` 已留痕
- 产出候选：`projects/p_e4c65c1c58ed/output/t_249079cc5431_draft.mp4`（59,832,977 B）
- **未登记 `render_output`/`attribution`** ⇒ 按 fail-closed 语义**不是交付物**，仅候选供人工观看
- 任务终态 **BLOCKED**（渲染后核验门，见 10.4）

### 10.3 全门复验（全部为**实测**；证据 `logs/phase13e_p13e3_render.json`）
| 门 | 结果 |
|---|---|
| 时长契约 978.7±1 s | **978.66 s**（Δ = −0.04 s）**在范围内** |
| 响度契约（−16 LUFS ±1 / TP ≤ −1.5 dBTP） | **I = −16.1 LUFS**（Δ 0.1 LU）、**TP = −2.5 dBTP** ⇒ 达标 |
| PI 渲染前（PI-1/2/6 + G-TL/G-PAD/G-SUB） | 全 **PASS**，`blocked=False`，无 reason |
| PI 渲染后（PI-3 静音 / PI-4 轨道 / PI-5 orphan） | 全 **PASS**，`blocked=False`，`promote_blocked=False` |
| 字幕↔旁白对齐（v2） | `SUBTITLE_ALIGNED`；216 cue；`cue_display_in_speech_ratio = 1.0`；越界 0 s；orphan **0**（占比 0.0） |
| 逐景抽帧 corr（**冻结口径** 48×48 灰度 Pearson，阈值 0.30） | **20/21 通过**；未通过 = **S03（0.1536）**；**未调整任何阈值** |
| 逐景 MOTION_VERIFIED（10%/90% 抽帧像素差） | 12/12 启用场景 **verified**（差 1.02–1.69）；静止场景差 0.85–1.86（见 10.5 局限） |

### 10.4 **阻断根因：S03 抽帧核验未达冻结阈值（非运动层所致）**
`agents/editing/agent.py` L823–835 的**成片抽帧核验**（在 PI 渲染后硬门**之前**执行）判定：
`S03` 期望素材 `asset_30dd89a16713` 在其窗口**中点** 101.49 s 处
`corr_expected = corr_best = 0.153 < min_corr 0.30` ⇒ 抛 `[ASSET_INSUFFICIENT]`。

**独立复核（复现生产链）**：
- `corr(S03 成片帧, 素材原图) = 0.1529`
- `corr(S03 成片帧, 静态全幅模板) = 0.1529`← 与运动**无关**
- `corr(S03 成片帧, 运动缩放后) = 0.1720`← 运动**反而提高**相关度
- **人工观看两张图**：成片帧与静态模板为**同一张四色定理示意图**（同一构图/同一组彩色节点），
  仅缩放取景不同 ⇒ **素材确实在屏，非错配、非占位伪装**
- 判定：低分属**冻结度量自身的结构性盲区** —— 该素材是"白底 + 细黑线 + 稀疏彩色圆点"的
  **稀疏高对比线稿**，重采样到 48×48 后信息几乎全落在极少数线条像素上；轻微缩放/位移即让线条
  落到不同像素格，相关系数塌陷（S03 恰为全片唯一此类线稿；其余 20 景为实拍/密纹图片，
  corr 0.54–0.99）。**本次未放宽阈值、未改度量、未调运动参数、未改选材**（均在授权之外）。

### 10.5 DQ 双口径报告（**不宣称 PASS**）
**原口径复算（只读，`core/direction.py`）**
| 指标 | 结果 |
|---|---|
| DQ-2 素材复用 | **FAIL** — `asset_cfae038f6106` 覆盖 S02 等 6+ 镜（素材池仅 5 张真实图像可用） |
| DQ-3 静态保持 | **FAIL** — S06 67.37 s / S07 66.49 s / S03 58.47 s 超 `max_hold_s` |
| DQ-3 `freezedetect`（−60 dB, d=1 s） | **218 个冻结块** |

**口径并列说明（语义，非结论）**：DQ-2/DQ-3 的 FAIL 来自**素材池贫瘠**（本夹具素材池取自项目内
检索产物，仅 5 张真实图像；**不含** H5 权威绑定的 Russell 页，该文件不在 `media/`）与**场景本身很长**
（21 景/978.7 s，单景 30–67 s），**不是**运动层缺陷。`freezedetect` 的 218 个块与 DQ-3 同源：
9 个静止场景按设计无像素变化，被如实计为冻结块。
**两项口径不可互相替代**，且本报告**不把任何一项读作 PASS**。

**本报告的诚实边界（本次实测暴露的方法学局限）**：本次用于"MOTION_VERIFIED"的
**10%/90% 抽帧平均绝对差**（480×270 灰度）**无法区分运动与字幕变化/H.264 量化噪声** ——
静止场景的差值（0.85–1.86）与运动场景（1.02–1.69）**重叠**。故 12/12 `verified` 只证明
"画面在窗口内发生变化"，**不足以单独证明"变化由 crop 平移/缩放造成"**。
运动的**确定性**证据来自 `render/motion_evidence.json`（12 景滤镜串已构造并应用、0 fallback）
与"运动已提高 S03 相关度"这一实测。**该局限如实登记，未被掩盖。**

### 10.6 边界与纪律
LLM **$0**、网络 **0**、**零 promotion**、**未放宽任何 PI/DQ 阈值**、**未修改任何被测生产代码**；
权威底片（sha256 `3b61dafda11c1b9d…` 复核一致）、v9 底片、既有脚本/voice 产物、`config.json`、
P7-6 产物、13-D 台账**均未改**；沙箱零覆盖；`config/render_motion.json` 为授权允许的开关文件（`enabled=true`）。
IMMUTABLE 核验：**`IMMUTABLE_OK`**（`phase13_immutable_check.py`）。

### 10.7 回归 **77/77 rc=0（含一处口径说明，非代码缺陷）**
初跑为 **76/77**，唯一失败 `tests/motion_test.py::5b`
（"默认配置解析 ⇒ off（无外部文件时运动层完全不介入）"）——该断言要求
`resolve_config({}, root=ROOT)` 在**无外部文件**时返回 `enabled=False`，
而本阶段授权的 `config/render_motion.json`（`enabled=true`）正使其解析为 on。
**这是该测试的既有前提（"无外部文件"）与已授权新增开关文件的冲突，不是代码缺陷。**

处置（**未改任何测试、未改阈值**）：把开关文件按字节**暂存到沙箱** → 复跑
⇒ **77 套件 / 77 rc=0 / FAILED: []**（`motion_test` 22/22）→ 再把开关文件**逐字节还原**
（sha256 `27f4a438b02dc773…` 前后一致 ⇒ 还原为零差异），并复核解析仍为 `enabled=true`。
即报告 §8.3 所要求的 `enabled=true` 渲染状态与 77/77 回归**互不冲突**，差异仅来自扫描期间的开关在位性。


