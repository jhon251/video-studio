# PHASE 27 报告：底片组装 + 错配清除 + 交付级渲染

> 阶段：Phase 27 ｜ 依据：Phase 27 授权书（交付线终点，预算纪律：先保证渲染证据落盘）
> **结论（逐项如实）**：
> **P27-1 底片组装 DONE ✔｜P27-2 错配清除 + 池补齐 部分 DONE｜P27-3 渲染已产出成片、
> 但逐景核验门 fail-closed（17 景）⇒ 未登记交付级候选｜P27-4/P27-5 NOT_EXECUTED**
> **重大进展**：**三指标首次全过** —— 冻结占比 **15.2%**（<50%）、最长静止 **6.0s**（<25s）、
> 开场 90s 变化 **69 次**（≥3）。时长/响度/PI/字幕 全过。
> **阻塞点**：**派生段素材绑定未落到渲染**（40 段中仅 2 段有 `expected_asset_id`）
> ⇒ 逐景核验 17 景失败 + **DQ-2 FAIL**（`max_asset_share 0.9369`、`unique 3`）。
> LLM **$0**、VLM **$0.0007**、网络 **0**、渲染 **172.9 s**。

---

## 1. P27-1 底片组装：DONE ✔

**输入**：40 景 v2.1 时间轴（`script_dcv2_p20_40seg.json`）+ P20-1 voice 切片
（`voice_output_40seg_v21.json`）+ **Phase 23 v4.1 定稿稿**。

**v4.1 文本 ↔ 40 段窗口映射**（`logs/phase27_p27_1_mapping.json`）
- **分段数不符**（v4.1 = **8** 段；底片 = **21 父景 / 40 子段**）⇒ 按授权要求
  **按句界/窗口对齐规则映射并登记规则**：
  「先把 v4.1 全文按**父景累计时长比例**切到 21 个父景，再按**子段时长比例**切到 40 个子段；
   切点**吸附在最接近的句/子句边界**（`[。！？!?；;，,]` 之后）；字符区间偏移 ⇒ **逐字保留**」。
- **文本零改动硬校验**：**3468 → 3468 字符（相等 ✔）**；逐段 `text_sha256` 记录；
  并断言**父景级与子段级双重守恒**（`PARENT_CONSERVATION` / `CHILD_CONSERVATION` 均通过）。
- 派生产物：`output/phase27_script_sandbox/script_p27_v41_40seg.json`（40 段 · **978.634s**）。
- **`assert_lineage` 通过 ✔**：文本守恒 + 段数一致 + 时基差 `|978.634 − 977.884| = 0.75s < 1.0`。
- **`frame_match.bank_derived = true` 已开启**（`config.json` 的 `tools.frame_match`，
  默认值仍为 `false`；关闭路径的逐字节兼容性已在 Phase 26 §0 证明）。

## 2. P27-2 错配清除 + 池补齐：部分 DONE

| 项 | 状态 |
|---|---|
| 错配素材**排除**（P24-2 点名旗帜照，`EXCLUDE_NAME_HINTS`） | ✔ 生效（本轮池内已排除） |
| 标记素材降权重选 | ✔ **4 处**（S02/S03/S05/S08，替换后立即计入复用计数） |
| `bank_derived` 开启 | ✔ |
| **受治理获取（≤6 张 Wikimedia）** | **NOT_EXECUTED**（**网络用量 0/6**） |
| **`cap=2` 新口径分配** | **NOT_EXECUTED**（DQ-2 仍用现口径，见 §3 的 FAIL） |

## 3. P27-3 交付级渲染：成片已产出，**逐景核验门 fail-closed**

**渲染**：沙箱 `p_c7d6b1f4dab2`、任务 `t_649df0e2f014`、**172.9 s**；
成片 `projects/p_c7d6b1f4dab2/output/t_649df0e2f014_draft.mp4`（**43,185,500 B**）——
**未登记 `render_output`**（fail-closed，非交付物）。
**运动**：`plan_counts = {enabled: 40, fallback: 0, scenes: 40, static: 0}` ⇒ **全镜启用、零回退**。

### 3.1 ✅ 三指标**首次全过**（本阶段最大成果）
| 指标 | 阈值 | P24（1.08） | P25 探针 | **P27（1.25 × 40 景 × v4.1）** |
|---|---|---|---|---|
| 冻结占比 | <50% | 73.7% ✘ | 0.0% | **15.2% ✔** |
| 最长连续静止 | <25s | 9.0s | 0.0s | **6.0s ✔** |
| 开场 90s 变化 | ≥3 次 | 5 | 23 | **69 次 ✔** |
> 在**真实 40 景成片**（非探针短片）上首次全过 ⇒ Phase 24 提出的观感目标达成。

### 3.2 其余门禁（全过）
| 门 | 结果 |
|---|---|
| 时长 978.7±1s | **977.88 s** ✔ |
| 响度 | **−16.1 LUFS / −2.5 dBTP** ✔ |
| PI 渲染前 / 后 | 全 **PASS**、`blocked=False`、`promote_blocked=False` ✔ |
| 字幕对齐（v4.1 重排 cue） | `SUBTITLE_ALIGNED`（**171 cue**、语音内 **1.0**、越界 **0 s**）✔ |
| MOTION_VERIFIED | **40/40 启用、0 fallback** ✔ |

### 3.3 ⚠️ 阻塞：**派生段素材绑定未落到渲染**（⇒ 逐景失败 17 + DQ-2 FAIL）
- **`bank_derived` 确实生效**（`summary.bank_derived=true`），但**只有 2 个景**有
  `expected_asset_id` 可供比对（`S01`、`S20`）⇒ `checked = 2/40`。
- 其余 38 个**派生段**（`S02p1`、`S03p2`…）的 `expected_asset_id` 为 `None` ⇒
  落入"占位镜头"分支 ⇒ **17 景失败**（`corr_expected=None`）。
- **连带 DQ-2 FAIL**：`max_asset_share = 0.9369`、`unique_assets = 3`
  （政策 ≤0.35 / ≥6）—— 与 **Phase 20 同一根因**：`MATERIAL_TIMELINE` 的 decisions
  **只覆盖 21 个父景 ID**，未展开到 40 个派生段 ID。
- **仲裁层实测**：仅 1 景进入 VLM 核验（判 `absent`）⇒ **未放行**；成本 **$0.0007**。
- **DQ-3**：`share 0.45`、`max_hold 36.836s` ⇒ **显著改善但未达 ≤20%**（按口径报改善，**不报 PASS**）。

**⇒ 依授权书「全门过 ⇒ 登记交付级候选；不可解 fail-closed ⇒ 如实 STOP，P19 21 景版转正」：
本阶段未登记交付级候选。**

### 3.4 根因与修复路径（明确、可执行）
**根因**：`MATERIAL_TIMELINE` 的 decisions 按**父景 ID** 落库；40 段派生脚本的
scene_id 是派生 ID，闸门按派生 ID 查绑定 ⇒ 查不到。**Phase 21 的"绑定展开"只做在
离线复验脚本里，未进入渲染链**（与 Phase 26 §0 发现的"产物在位但未接入"**同一模式**）。
**修复（下一阶段，建议一次做对）**：
1. 在 `_render` 的素材绑定阶段，把父景绑定**展开**到每个派生段 ID（写进 MATERIAL_TIMELINE
   的 decisions，或让闸门**按 `parent_scene_id` 回退查绑定**）；
2. `bank_derived` 已在位并按派生段取子窗口 corr，绑定修好后 40/40 可核验；
3. DQ-2 的 `cap=2` 新口径与池补齐（≤6 张 Wikimedia）一并执行，DQ-2 才有机会回到 PASS。

## 4. P27-4 / P27-5：NOT_EXECUTED

- **P27-4 终版 promotion 材料包**：未生成（候选未成立）。
- **P27-5 完整回归**：**未跑**（依预算纪律：渲染证据未完整落盘前不把预算花在回归上；
  本轮渲染**已落盘但门未过**，仍按纪律优先如实报告）。
  已知最近一次完整跑：**Phase 25 = 81/81 rc=0**。

## 5. 交付物

| 内容 | 路径 |
|---|---|
| **v4.1 ↔ 40 段窗口映射表**（逐段 sha256 + 守恒校验） | `logs/phase27_p27_1_mapping.json` |
| P27 底片脚本（40 段 · v4.1 文本） | `output/phase27_script_sandbox/script_p27_v41_40seg.json` |
| **P27-3 全门复验** | `logs/phase27_p27_3_verification.json` |
| crop 滤镜诊断（发现 `//` 不被 ffmpeg 支持） | `logs/phase27_crop_diag.json` |
| 成片（未登记交付物） | `projects/p_c7d6b1f4dab2/output/t_649df0e2f014_draft.mp4` |
| 本报告 | `docs/regression_2x/PHASE27_REPORT.md` |

**🔧 顺带修掉一个真 bug（如实登记）**：v2 平移/缩放的滤镜串用了 `//` 做整数除，
**ffmpeg 表达式解析器不支持 `//`**（报 `Undefined constant or missing '('`）
⇒ 首轮渲染 **19/40 景 crop 配置失败**、渲染 **-22 Invalid argument**、成片 0 B。
已改为 `floor(a/b)`，重测 **40/40 滤镜全部通过**（`logs/phase27_crop_diag.json`）。
> 该 bug 在 Phase 24/25 **未被发现**，因为那两阶段只渲染了**单段探针**（S01 为 zoom 分支，
> 且 24s 场景恰好未触发平移分支的 `//` 路径）。**40 景全片渲染才暴露。**

**边界（已核验）**：DB schema、**PI 阈值与判定语义**、**corr 度量与仲裁语义**、
**motion POLICY 常量**、`mm_*` 冻结栈、词表、baseline、母片、既有候选**均未改**；
`config.json` 仅**追加** `tools.frame_match.bank_derived=true`（P27-1 授权项，默认仍 false）。
**不做**：图内元素动画、视频素材、句中拆分、改旁白文本、promotion、发布。

## 6. 下一阶段（唯一剩余路径）
1. **修派生段绑定回退**（`parent_scene_id` 回退查绑定，或把绑定展开进 MATERIAL_TIMELINE）
   —— 这是**唯一**挡住交付级候选的问题；
2. 一并做 **DQ-2 的 `cap=2` 新口径** + **受治理获取 ≤6 张**；
3. 重渲 → 全门复验（预期：逐景 40/40、DQ-2 PASS、三指标保持全过、DQ-3 报改善）；
4. **H7 片尾卡**执行 + P27-4 三版材料包；**完整回归**跑完留档。
