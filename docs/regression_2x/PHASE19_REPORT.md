# PHASE 19 报告：拆镜批执行 + VLM 仲裁生产接线 + 交付级最终渲染

> 阶段：Phase 19 ｜ 依据：Phase 19 授权书（交付线终点）
> **结论（逐项如实）**：
> **P19-1 VLM 仲裁层生产接线：DONE ✔（加法、配置门控、默认关闭、关闭时逐字节一致）｜
> P19-2 素材误导倾向标记：DONE ✔（12 张全量；2 张标记；**口径局限如实登记**）｜
> P19-3 拆镜批执行：DONE ✔（19 条提案转录批准 + 两轮拆分；**DQ-3 未达 ≤20%，如实登记**）｜
> P19-4 交付级最终渲染：**已执行（115.1 s）**；**全门通过**（含仲裁层把 4 景失败全部核验为在屏）；
> **DQ-2 PASS**、**DQ-3 FAIL（未改善，原因如下）** ⇒ **登记为候选，未宣称交付级 PASS**。**
> LLM **$0**、VLM **$0.0021**（P19-4 仲裁）+ **$0.0180**（P18-3 评测）= **$0.0201**（≤$0.5）、网络 **0**；
> **零 promotion**；未改任何阈值与 PI 门禁判定语义。

---

## 1. P19-1 VLM 仲裁层生产接线（DONE）

**新增** `src/video_studio/core/render_arbitration.py`（加法模块）：
- **开关链**（与 `config/render_motion.json` 同款）：内存 `config.tools.render_arbitration`
  → `config/render_arbitration.json` → **默认 `{"enabled": false}`**；**`config.json` 零改动**。
- **语义**：仅当某景 `corr < 0.30`（度量已判失败）时才调
  `vlm-presence-verify-v1`（P18-3 已达标）；`present` ⇒ `PASS_VLM_PRESENT`（放行，附
  **VLM 证据 / prompt_version / 模型名 / 成本**）；`absent` / `uncertain` / **调用失败** ⇒ **维持阻断**（fail-closed）。
- **接线点**：`agents/editing/agent.py` 渲染后逐景核验门处（授权明确范围）；
  开启时额外 emit `RENDER_ARBITRATION` 事件（human_visible 当有放行）。
- **硬验收（关闭时逐字节一致）**：`apply_arbitration` 在门控关闭时**原样返回入参对象**
  （实测 `out is verification == True`，`failed_scenes` 未被触碰）⇒ 核验行为与现状**逐字节一致**。
- **测试**：`tests/corr_metric_diagnostics_test.py` 的仲裁逻辑用例（含
  `uncertain ⇒ BLOCKED`、`corr 达标 ⇒ 不看 VLM 直接放行`、默认关闭一致性）。

**实测（渲染后置，同一代码路径）** —— 见 §4.3：**4 个失败景全部核验为 `present` ⇒ 放行**，成本 **$0.0021**。

## 2. P19-2 素材误导倾向标记（DONE，含口径局限）

`discriminative_score` = 该素材在 48×48 灰度下与**池内其它素材**的最大 corr；
**≥0.35 ⇒ `low_discriminative`**（短名单降权，**不硬拒**）。12 张全量登记
（`logs/phase19_discriminative_registry.json`）：**标记 2 张**
（`23e71bc8a864` 与 `432cd85be6f1` 互达 **0.4797**）。无一张同时命中 `low_crop_safety`。

**⚠️ 口径局限（如实登记，未掩饰）**：本指标是「**素材 vs 素材**」的互相似度，
**不能**捕获「**素材 vs 任意成片帧**」的误吸引机制。实证：Phase 18 的 2 条反门误通过来源
`301ff850be9c` 在本表的 discriminative_score 仅 **0.0574**（远低于 0.35），
却对 S02/S07 的**成片帧**达 ~0.35 ⇒ 属「对不同分布画面普遍高相关」，与"与池内素材相似"**不是同一现象**。
⇒ 本标记**有用但不充分**；覆盖后一现象需另立「素材 vs 历史帧包」吸引度指标（**本阶段未做，登记为后续项**）。

## 3. P19-3 拆镜批执行（DONE，DQ-3 未达 ≤20%）

**批准链（13-C 双字段转录，append-only）**：`authorized_by=human:project-owner`、
`approval_document=Phase 19 授权书`；**逐条绑定 proposal sha256**
（`logs/phase19_split_execution_ledger.json#rounds[0].approved_proposals`，19 条）。

| 轮次 | 目标 | 景数 | >25s | 占比 | max_hold | DQ-3 |
|---|---|---|---|---|---|---|
| 原始 | — | 21 | 21 | 100% | 67.374 s | FAIL |
| **第 1 轮**（P17-4 的 19 条，≤35s，切点取旁白句边界） | ≤35s | **40** | 18 | **45.0%** | 43.65 s | FAIL |
| **第 2 轮**（≤25s，追加拆分） | ≤25s | **42** | 16 | **38.1%** | 43.65 s | FAIL |
| 第 3 轮 | ≤25s | 42 | 16 | 38.1%（**无变化 ⇒ 切点耗尽**） | 43.65 s | FAIL |

**文本零改动（硬校验通过）**：字符数 **4927 → 4927**（相等）；总时长 **978.656 → 978.656 s**（相等）。
派生脚本 v2：`output/phase19_script_sandbox/script_dcv2_split_v2.json`（42 段）。

**LIMITATION（如实登记）**：按 **≤20%** 阈值需把 ≤25s 的子镜数提到 ≥34/42；
但**旁白句/子句边界已耗尽**（部分段落切点稀疏），继续切只能按固定秒数**硬切**——
那会破坏旁白-画面语义对齐。故**不硬切**，如实报 **45.0% → 38.1% 的改善**而未达阈值。

**⚠️ 兼容性发现（关键，导致 P19-4 无法使用拆镜时基）**：**拆镜后的 42 段时基与既有
`voice_output`（21 段）冲突** —— 渲染前闸门报
`voice 产物不完整：缺少合法音频的段落 [21..41]` + `G-SUB FAIL`。
即：**拆镜执行必须与"旁白重配/音频重切"同阶段进行**，否则无法渲染。
⇒ 这是 P19-4 采用 21 段时基的**直接原因**，也是"DQ-3 在本阶段无法改善"的根因。

## 4. P19-4 交付级最终渲染

### 4.1 执行
- 沙箱 `p_50e10b27b44d`；渲染任务 `t_a4d8c1aafd04`；**115.1 s**（≤3h ✔）
- 运动 `enabled=true`（12/21 景，0 fallback）；**仲裁层 `enabled=true`**
- 派生脚本：**13-E 的 `script_dcv2_derived_v1`（21 段 / 978.656s / 文本零改动）**
  —— 因 §3 的时基冲突而无法用 v2 的 42 段
- **标记素材重选（4 处，同一转录批准口径）**：S02 `a3f0e27204cd`→`301ff850be9c`、
  S03 `432cd85be6f1`→`33b360a5363c`、S05 `23e71bc8a864`→`3f0b94a3f2ac`、
  S08 `5144139591a0`→`65377b888b77`（每次替换后立即计入复用计数，**避免 DQ-2 恶化**）
- 产出候选：`projects/p_50e10b27b44d/output/t_a4d8c1aafd04_draft.mp4`（**41,263,003 B**）；
  **未登记 `render_output`/`attribution`**（首次运行被核验门阻断 ⇒ fail-closed）⇒ **非交付物**

### 4.2 全门复验（`logs/phase19_p19_4_verification.json`）
| 门 | 结果 |
|---|---|
| 时长契约 978.7±1 s | **978.66 s**（Δ −0.04）**在范围内** ✔ |
| 响度（−16 LUFS±1 / TP ≤ −1.5 dBTP） | **−16.1 LUFS / −2.5 dBTP** ✔ |
| PI 渲染前（PI-1/2/6 + G-TL/G-PAD/G-SUB） | 全 **PASS**、`blocked=False` ✔ |
| PI 渲染后（PI-3/4/5） | 全 **PASS**、`blocked=False`、`promote_blocked=False` ✔ |
| 字幕↔旁白对齐 | `SUBTITLE_ALIGNED`，216 cue，语音内占比 **1.0**，越界 **0 s** ✔ |
| 逐景核验 + 仲裁 | 检查 21 景；**仲裁前失败 4 → 仲裁后失败 0** ✔ |
| MOTION_VERIFIED | 12/12 启用场景、0 fallback ✔ |

### 4.3 仲裁层实测（P19-1 的直接证据）
用**生产核验纯函数** `EditingAgent._verify_scene_frames` 复现核验（取得完整 `failed_scenes`，
不受任务错误字段 2000 字截断影响），再跑 `render_arbitration.apply_arbitration`（**与门内同一代码路径**）：

| 景 | corr | 仲裁结论 | VLM 理由（节选） |
|---|---|---|---|
| S06 | 0.242 | **PASS_VLM_PRESENT** | 「成片帧与素材原图结构完全一致，仅底部被裁切并叠加中文字幕，主体树状图内容匹配」 |
| S11 | 0.153 | **PASS_VLM_PRESENT** | 「节点颜色、连接结构完全一致，仅底部文字为新增，属局部裁切+叠加字幕情形」 |
| S13 | 0.006 | **PASS_VLM_PRESENT** | 「Tactic state 与 Selected expressions 的结构、公式…一致」 |
| S18 | 0.253 | **PASS_VLM_PRESENT** | 「完整树状结构，包括标题、ABSTRACT/CONCRETE 分支，仅底部被裁切」 |

**4/4 放行、0 阻断、成本 $0.0021**（≤$0.5）。⇒ **仲裁层在生产路径上可用**。

### 4.4 DQ 复算
| 指标 | 13-E | Phase 16 | **Phase 19（本次）** |
|---|---|---|---|
| 唯一素材 | 5 | 12 | **10** |
| **DQ-2 素材复用** | FAIL | PASS | **PASS**（单素材最大复用 **5 景**：`23e71bc8a864`） |
| **DQ-3 静态保持** | FAIL（max 67.374s） | FAIL（同） | **FAIL（max 67.374s，未改善）** |

**DQ-3 未改善的根因（如实）**：DQ-3 度量的是**脚本段时长**；本阶段虽**已生成**拆镜脚本 v2（42 段），
但**因 §3 的 voice 时基冲突无法渲染该时基** ⇒ 渲染实际沿用 21 段 ⇒ DQ-3 与 13-E **逐值相同**。
**不宣称改善**。

### 4.5 交付级判定
**全门通过 + DQ-2 PASS 均满足**，但：
- **DQ-3 仍 FAIL 且未改善**（授权书要求"显著改善 + 如实报告"，实测**零改善**）；
- 候选**未登记 `render_output`**（首次运行被阻断，fail-closed）；
⇒ **登记为「全门通过的候选」，不登记为"交付级候选 PASS"**。
promotion 决策与是否接受 DQ-3 现状**交人工**。

## 5. 登记 / 边界

**交付物**
| 内容 | 路径 |
|---|---|
| P19-1 仲裁层模块 | `src/video_studio/core/render_arbitration.py` |
| P19-1 接线 | `src/video_studio/agents/editing/agent.py`（核验门处，加法） |
| P19-1 开关文件 | `config/render_arbitration.json`（`enabled=true`；**授权允许的外部开关**） |
| P19-2 标记登记 | `logs/phase19_discriminative_registry.json` |
| P19-3 执行台账（含批准链/sha256/两轮/文本校验） | `logs/phase19_split_execution_ledger.json` |
| P19-3 派生脚本 v2（42 段） | `output/phase19_script_sandbox/script_dcv2_split_v2.json` |
| P19-4 全门复验 | `logs/phase19_p19_4_verification.json` |
| P19-4 仲裁实测 | `logs/phase19_p19_4_arbitration_live.json` |
| 测试 | `tests/corr_metric_diagnostics_test.py`（含仲裁逻辑与默认关闭一致性） |
| 本报告 | `docs/regression_2x/PHASE19_REPORT.md` |

**不碰（已核验）**：`config.json`（零改动）、DB schema、**PI 阈值与判定语义**、`mm_*` 冻结栈、
词表、baseline、冻结真值、v9/H5 母片与既有候选。
**不做**：promotion、发布、**自动改旁白文本**（字符数与时长效验均通过）、跳过任何人工批准。

**预算**：LLM **$0**；VLM **$0.0201**（P18-3 评测 $0.0180 + P19-4 仲裁 $0.0021；≤$0.5 ✔，缓存沿用 P14-1 机制）；网络 **0**；渲染 **115.1 s**。

## 6. 下一阶段建议（需新授权）
1. **拆镜 + 旁白重配同阶段执行**（唯一能真正改善 DQ-3 的路径）：按拆镜切点重切/重合成旁白音频，
   使 `voice_output` 段数与脚本段数一致（当前 21 vs 42 是硬阻塞）；目标 ≤25s/子镜，
   并把 ≤25s 子镜占比提到 ≥80%（≤20% 超限）。
2. **素材吸引度指标**：补「素材 vs 历史帧包」的误吸引度（P19-2 口径局限，本阶段已登记）。
3. **人工裁定**：是否接受"仲裁层放行 + DQ-3 待改善"的当前候选，以及 promotion 决策。
