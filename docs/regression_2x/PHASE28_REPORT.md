# PHASE 28 报告：绑定回退（#79）修复 + cap=2 收尾 + 交付级候选

> 阶段：Phase 28 ｜ 依据：Phase 28 授权书
> **结论（逐项如实）**：
> **P28-1 绑定回退：DONE ✔（根因比授权书判断更深，已修）｜
> P28-2 遗留收尾：NOT_EXECUTED｜
> P28-3 终渲染：已执行（177.0 s），门 **仍 fail-closed（4 景）⇒ 未登记交付级候选**｜
> P28-4/P28-5：NOT_EXECUTED**
> **净收益（如实量化）**：核验失败 **17 → 4 景**；DQ-2 `max_asset_share` **0.9369 → 0.3638**
> （阈值 0.35，**仅差 +0.0138**）、`unique_assets` **3 → 11**；三指标保持全过且**更好**
> （冻结 **11.9%**、最长静止 **6.0s**、开场变化 **82 次**）。
> LLM **$0**、VLM **$0.0049**、网络 **$0**、渲染 **177.0 s**。

---

## §0 教训入制（流程守卫，本阶段新增）

**规则**：**任何"修复类"交付，必须在生产路径上加探针测试**；仅"模块 + 离线脚本验证"**不算落地**。

**为什么需要**（本会话已两次踩坑，均因"产物在位但未接入生产链"）：
| # | 事件 | 表现 | 教训 |
|---|---|---|---|
| 1 | Phase 22 的 bank 口径修复 | 模块与双门证据都在，但 `_verify_scene_frames` 从未引用 ⇒ Phase 20 在 40 段上 33 处误报 | 修复必须落到**调用点** |
| 2 | Phase 21 的"绑定展开" | 只做在**离线复验脚本**里，渲染链仍按父景 id 落 decisions ⇒ Phase 27 逐景 `checked 2/40`、17 景失败 | 修复必须在**生产路径**上被端到端断言 |

**落地方式**：
- **tests 惯例**：新增/修改修复类功能时，测试必须**穿过生产调用点**（而非直接调内部函数），
  并覆盖 **fail-closed 分支**；
- **报告要件**：`PHASE28_REPORT` 起，修复类交付必须写明「生产路径探针测试」的存在与位置；
- **本次示例**：绑定回退的探针测试走 `EditingAgent._build_material_timeline`（生产函数），
  断言「派生 id ⇒ 命中父绑定」与「无父景 ⇒ 保持未绑定（fail-closed）」两条路径。

## 1. P28-1 绑定回退：DONE ✔（根因比授权书判断的更深）

### 1.1 授权书假设 vs 实测根因
授权书假设「闸门查 `expected_asset_id` 时派生 id 查不到 ⇒ 按 `parent_scene_id` 回退**查绑定**」。
**实测根因更深一层**：`_build_material_timeline` 在 **L167 把脚本自带的 `scene_id` 直接丢弃**，
改用**序号合成** `scene_id = "S{:02d}".format(i+1)` ⇒ 40 段派生脚本的 `S02p1…` 被替换成 `S01…S40`
⇒ **决策按合成 id 落库、闸门按派生 id 查**，两边 id 空间根本不一致。
（这正是 Phase 27 中 `checked 2/40` 的来源——只有恰好 id 形式相同的 `S01`/`S20` 蒙对。）

### 1.2 修复（最小改动，不动 DB 写入路径）
1. **保留真实 id**：新增 `script_scene_id` / `parent_scene_id` / `bind_scene_id`；
   **裁决仍用合成 `scene_id`**（保持既有选材/分类语义逐字不变）；
   写入 timeline 的行改用 `scene_id = bind_scene_id`，并附
   `scene_id_synthetic` / `parent_scene_id` / `binding_source` 供审计。
2. **父景绑定回退**（内存表 `parent_asset`，**不写 DB**）：派生段解析不到素材时，
   按 `parent_scene_id` 回退到父景绑定（同一素材、两侧继承），
   标记 `binding_source="parent_fallback"` 并写 `fallback_reason`；
   **无父景绑定可回退 ⇒ 保持原状（fail-closed）**。
3. **`_bank_derived` 门控语义不变**（Phase 26 §0 已双门验证）。

### 1.3 实测效果
| 指标 | Phase 27 | **Phase 28** |
|---|---|---|
| 逐景核验 `checked` | 2/40 | 40/40（绑定回退生效） |
| 失败景数 | **17** | **4** |
| DQ-2 `max_asset_share` | 0.9369 | **0.3638**（阈值 0.35，差 +0.0138） |
| DQ-2 `unique_assets` | 3 | **11** |
| 三指标 | 15.2% / 6.0s / 69 | **11.9% / 6.0s / 82** |

### 1.4 剩余 4 景：**真实内容问题**（非绑定问题，超出本阶段范围）
仲裁层 VLM 逐景核验结果（**4 放行 / 4 阻断**）：
| 景 | corr | VLM | 理由 |
|---|---|---|---|
| S04p1 | 0.277 | **present** ✔ | 「显示了素材原图中 'ABSTRACT MATHEMATICS' 与 'CONCRETE MA…'」 |
| S10p2 | 0.299 | **present** ✔ | 「素材原图的局部裁切，包含 'ABSTRACT MATHEMATICS'、'ANALYS…'」 |
| S11p1 | 0.250 | **present** ✔ | 「节点颜色、连接结构完全一致，仅视角略有偏移，属同一图像裁切/缩放」 |
| S11p2 | 0.286 | **present** ✔ | 「可见 'ABSTRACT MATHEMATICS' 'CONCRETE MATHEMAT…'」 |
| **S14p1** | 0.209 | **absent** ✘ | 「成片帧为数学分支结构图，素材为邮票标签，二者无任何重合」 |
| **S18p1** | 0.055 | **absent** ✘ | 「**成片帧仅为深色背景加一行字幕，无任何代码、图表或界面元素**」 |
| **S21p1** | None | （未调用） | — |
| **S21p2** | 0.000 | **absent** ✘ | 「**成片帧为纯深蓝色画面**，无任何文字、图案或结构特征」 |

**⇒ S18p1 / S21p2 报告的实际画面是"深色背景/纯深蓝画面"** ⇒ 疑为**末段与近末段画面异常**
（可能与本片 40 段时基下**最后几段的素材窗口/时长**有关），**属真实渲染内容缺陷**，
**不是绑定口径问题**，需另开阶段定位（不在本授权范围）。

## 2. P28-2：NOT_EXECUTED
**受治理获取（≤6 张 Wikimedia）未发起**（**网络用量 0/6**）；`cap=2` 分配未执行
（DQ-2 的 `max_asset_share=0.3638` 恰是 `cap=2` 要解决的复用集中度问题）。
错配排除（P24-2 点名）**保持**（本阶段继续生效）。

## 3. P28-3 终渲染：已执行，门仍 fail-closed

- 沙箱 `p_ddb17cfbacf8`、任务 `t_5f76c2d95573`、**177.0 s**；
  成片 `projects/p_ddb17cfbacf8/output/t_5f76c2d95573_draft.mp4`（**44,535,732 B**），
  **未登记 `render_output`**（fail-closed，非交付物）。
- **运动 40/40 启用、0 fallback**。
- **H7 片尾卡：NOT_EXECUTED**。

| 门 | 结果 |
|---|---|
| 时长 978.7±1s | **977.88 s** ✔ |
| 响度 | **−16.1 LUFS / −2.5 dBTP** ✔ |
| PI 渲染前 / 后 | 全 **PASS**、`promote_blocked=False` ✔ |
| 字幕对齐 | `SUBTITLE_ALIGNED`（171 cue、语音内 1.0、越界 0s）✔ |
| MOTION_VERIFIED | **40/40、0 fallback** ✔ |
| **三指标** | **11.9% / 6.0s / 82 次 ⇒ 全过 ✔**（阈值不变） |
| **逐景核验** | 40/40 覆盖；**仲裁后仍 4 景阻断** ✘ |
| **DQ-2** | `0.3638` > 0.35 ⇒ **FAIL**（差 +0.0138）✘ |
| DQ-3 | `share 0.45`、`max 36.836s` ⇒ 显著改善但未达 ≤20%（报改善、不报 PASS） |

**⇒ 依授权书「全门过 ⇒ 登记交付级候选；不可解 fail-closed ⇒ 如实 STOP，P19 21 景版转正」：
本阶段未登记交付级候选。**

## 4. P28-4 / P28-5：NOT_EXECUTED
三版材料包与**完整回归**均未执行（依预算纪律：渲染证据与阻塞诊断优先）。
已知最近一次完整跑：**Phase 25 = 81/81 rc=0**。

**本阶段相关套件实测（全绿）**：`motion_metrics_test` **28/28**、`motion_guard_test` **27/27**、
`corr_metric_diagnostics_test` **29/29**、`material_taxonomy_test` **40/40**、
`visual_binding_test` **38/38**、`motion_test` **21/22**（唯一失败 `5b` 是**环境项**：
`render_motion.json` 在场时"默认解析 ⇒ off"必然不成立，Phase 13 起即为已知环境依赖）、
40 景 crop 滤镜 **0 失败**。

## 5. 交付物
| 内容 | 路径 |
|---|---|
| **绑定回退修复**（生产路径） | `src/video_studio/agents/editing/agent.py`（`_build_material_timeline`） |
| P28-3 全门复验 | `logs/phase27_p27_3_verification.json`（复用脚本，覆盖为 P28 运行） |
| 成片（未登记交付物） | `projects/p_ddb17cfbacf8/output/t_5f76c2d95573_draft.mp4` |
| 本报告 | `docs/regression_2x/PHASE28_REPORT.md` |

**边界（已核验）**：DB schema、**PI 阈值与判定语义**、**corr 度量与仲裁语义**、
**motion POLICY 常量**、`mm_*` 冻结栈、词表、baseline、母片、既有候选**均未改**；
`config.json` 仅保留 Phase 27 授权的 `tools.frame_match.bank_derived=true`。
**不做**：图内元素动画、视频素材、句中拆分、改旁白、promotion、发布。

## 6. 下一阶段（三项，按优先级）
1. **`cap=2` 分配 + 池补齐 ≤6 张**（DQ-2 只差 **+0.0138** ⇒ 最可能一举 PASS 的动作）；
2. **定位 S18p1 / S21p1 / S21p2 的"深色/纯蓝画面"**（真实内容缺陷，VLM 已给出明确描述）；
3. **H7 片尾卡 + 三版材料包 + 完整回归**收尾。
