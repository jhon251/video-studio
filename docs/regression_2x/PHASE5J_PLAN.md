# 5.x Final Gate 规划（5-J）——修订版

> 阶段: 5-J 规划（只读审计；未动代码/测试/基线）
> 基线: `5.x-phase5g-baseline`（sha256 `355b2a05…`，当前唯一基准）
> 本文档回答授权的 9 个问题并设计 5.x Final Gate 最小 DoD。
> **修订 (2026-09-19)**：§4 `mm-review-confirm` 重新定义为 **对评估/判定系统只读 + 仅允许 append-only 写入人工决策记录**，
> 解决原版"同时只读又写项目目录"的矛盾。

---

## 1. 5-A～5-I 各自实际完成能力及证据

| 阶段 | 核心能力 | 证据 | 状态 |
|---|---|---|---|
| 5-A | 单帧像素证据（CLIP 3 帧，域一致性/相似度/边际/top-k） | `PHASE5A_REPORT.md`、`core/multimodal.py`、34/34 测试 | ✅ PASS |
| 5-B | 多候选证据池（候选聚合、层间独立性） | `PHASE5B_REPORT.md`、`ops/mm_candidates.py` | ✅ PASS |
| 5-C | 真值钉定与人工决定记录（append-only 台账、只读脚本） | `PHASE5C_REPORT.md`、DB 台账 38/38 | ✅ PASS |
| 5-D | 多帧时序证据（CLIP 7 帧 + 帧间一致性 + 逐帧投票 + 结构性 UNKNOWN） | `PHASE5D_REPORT.md`、53/53 测试 | ✅ PASS |
| 5-E | 校准与可解释性（真值集 14 例冻结、边界距离/证据分级/四段式可解释链/敏感性披露） | `PHASE5E_REPORT.md`、34/34 测试、真值集 sha `7eb952f2…` | ✅ PASS |
| 5-F | Judge 最终裁决（J0–J6 + 5 级优先级 + 冲突不选边 + 10 理由码 + DoD 12/12；零阈值） | `PHASE5F_REPORT.md`、43/43 测试、`5.x-phase5f-baseline` | ✅ PASS/CLOSED |
| 5-G | 真值集 v2 扩充（32 例 / 3 项目 / 多镜头 12 / 纯色 6 / 边界 4；运动 0 LIMITATION）+ 校验器 v2 分支 | `PHASE5G_REPORT.md`、`mm_truth_set_v2.json` sha `8adc2985…`、电池 25/25、`5.x-phase5g-baseline` | ✅ PASS/CLOSED |
| 5-H | 生产报告可见性（`--mm-advisory` 只读咨询节；v1 14 例 + UNKNOWN 分型 + R6 展示） | `PHASE5H_CLOSEOUT.md`、咨询节 57 行、电池 25/25 | ✅ PASS/CLOSED |
| 5-I | v2 多项目报告可见性（32 例 / 3 项目分组；层间冲突显式呈现；纯色 fail-closed 显式呈现） | `PHASE5I_REPORT.md`、咨询节 57 行、电池 25/25 | ✅ PASS/CLOSED |

### 5.x 全域回归证据汇总

- 最终电池 **25/25 步 rc=0**（phase5g_regression_run3/5 直连健康窗口）
- 套件 **46/46 rc=0**
- 冻结指纹 **14/14**（12 精确 + 2 已知 Phase 1.1 编码补丁旧值）
- 生产母片 Run01–04 哈希全部不变
- v1 真值集 `7eb952f2…` 不变
- G10 生产母片 `2f0e6687`（101 拍 / 域一致 67 / HN 34 / A/V 0.15s / 黑帧 0 / 字幕 100%）

---

## 2. 当前仍阻塞 Final 的问题

| # | 问题 | 性质 | 阻塞 Final？ |
|---|---|---|---|
| B1 | **Judge 未接入生产判定链**（#49）：评估结果在咨询节可见但不会自动拦截 MISMATCH | BY DESIGN（5-F 明确边界） | **是**——Final 必须证明 Judge 能安全接线（人工确认、不自动换材） |
| B2 | **S06/S12 实例粒度分歧**：4-B MATCH vs 5A/5D MISMATCH，人工裁决未完成 | 评估发现（5-G 实证） | **是**——Final 必须有人工裁决结论 |
| B3 | **运动素材 = 0**：全库 1592 项目 0 视频资产，评估覆盖矩阵缺口 | LIMITATION（如实） | **否**——LIMITATION 可保留，不虚构 |
| B4 | **phase2e_failure_paths / real_provider 网络红项** | pre-existing environmental | **否**——LIMITATION/PENDING 保留 |
| B5 | **≥40 例真值集目标未达（32/40）** | 5-G 如实披露 | **否**——32 例已足以支撑 Judge 校准 |
| B6 | **VIZ 生产能力未建**（G10 自指拍需结构卡或扩池） | G10 报告 | **否**——G10 已用 HN 角标替代 |
| B7 | **域感知检索扩池**（SS 系后续） | EXP-SS2 建议 | **否**——G10 已达新口径 60 |

---

## 3. 可作为 LIMITATION 保留、无需修复的问题

| 项 | 理由 |
|---|---|
| 运动素材 = 0（B3） | 全库如实记录；评估子系统对静帧已验证；运动素材需新素材供给授权 |
| phase2e 网络红项（B4） | pre-existing environmental；不因网络环境改写 PASS |
| ≥40 真值集目标未达（B5） | 32 例已满足 DoD v2 口径（D1 检查通过）；继续扩充不改变 Judge 结论 |
| VIZ 未建（B6） | G10 已用 HN 替代；VIZ 是新能力非修复 |
| #45 保守 UNKNOWN | BY DESIGN（保守设计优于漏判） |
| #46 阈值敏感性 | BY DESIGN（披露不实施） |
| #47 top-1 解释性 | LIMITATION（仅展示） |
| #49 Judge 未接生产链 | 5-I 设计了最小接线方案（见 §4） |

---

## 4. Judge 是否必须进入生产判定链

**结论：是——但以"对评估/判定系统只读 + 仅允许 append-only 写入人工决策记录"的最小方式接入。**

### 4.1 为什么必须

当前状态：评估结果在咨询节可见（5-H），但人工在看完报告后如果判定"这个镜头不合格，需要换"，**没有系统化的方式把这一决定写回管线**——只能走 4-C 人工决定（HITL），而 4-C 不感知 Judge 的三态判定。

如果 Final 不接 Judge，就意味着：评估子系统建了但生产链不用它——可信度闭环断裂。

### 4.2 最小接线方案（修订版）

**原则：对评估/判定系统只读；仅允许 append-only 写入人工决策记录；绝不自动换材/redo/渲染/发布。**

```
[渲染前] Judge 判定结果（来自 --mm-advisory 或 mm-judge CLI）
    │
    ▼
人工审阅咨询节 → 对每个 MISMATCH/UNKNOWN 镜头做出决策（人工输入）：
    │
    ├── "accept"（接受，不换材）→ 该镜头继续渲染，加角标
    ├── "replace"（记录人工指定候选，不自动执行）→ 需人工在 4-C 流程中另行操作
    └── "keep_unknown"（保留 UNKNOWN）→ 该镜头渲染但角标显示"待确认"
        （keep_unknown ≠ accept：语义不同，不可互换）
    │
    ▼
人工决策通过 mm-review-confirm CLI 以 append-only 方式写入
决策记录文件（项目目录下 mm_review_decisions.jsonl）
    │
    ▼
渲染继续（Judge 结果 + 决策记录均不影响渲染行为——只是人工的决策留痕）
```

### 4.3 决策记录 schema（append-only JSONL）

```json
{
  "decision_id": "dec_<uuid4>",
  "project_id": "p_f4b466a4a024",
  "scene_id": "S06",
  "case_id": "T02_S06_truth_artifact_mismatch",
  "decision": "accept | replace | keep_unknown",
  "rationale": "人工审阅结论（自由文本）",
  "original_asset_id": "a_2ed5f41d6b58",
  "replacement_asset_id": "a_9a7600dfeebf 或 null（replace 时必填）",
  "decided_by": "人工（姓名或 ID）",
  "decided_at": "2026-09-19T16:46:39",
  "input_fingerprint": {
    "judge_json_sha256": "885ef20e9f5a729f…",
    "truth_set_sha256": "7eb952f2797e180c…",
    "v2_master_sha256": "8adc2985d7fa044c…"
  },
  "baseline_sha256": "355b2a053adeecb6c98b7e38f699011452f3af4c60eedbb532553b63fc1c068e"
}
```

### 4.4 append-only 约束

- **历史决策不可覆盖、不可删除**：新决策追加为新行（JSONL）；同 case_id 的新决策不覆盖旧行
- **替换决策不自动执行**：`replace` 仅记录人工指定的候选资产 ID；实际换材/redo 须走 4-C HITL 流程另行授权
- **`keep_unknown` ≠ `accept`**：两者语义不同——accept 表示"人工认为可接受"；keep_unknown 表示"证据不足，保留 UNKNOWN 状态"
- **决策文件为 append-only JSONL**：每行一条决策；追加后不可修改已写入行

### 4.5 Final Gate 中的验证

- 对 G10 生产 Run 的 2 处 VIOLATION（S06/S12）和 6 处 UNRESOLVED（p_8f05）做一次真实人工决策
- 决策 JSONL 落盘 → `mm-review-confirm` 验证可读 → 渲染母片 sha 不变
- DoD：决策文件存在且可解析；每条决策含必填字段；append-only 验证通过（追加新行后旧行不变）；渲染母片 sha 不变

---

## 5. R4/R6 当前到底属于"咨询可见"还是"生产闭环"

| 项 | 5-H 状态 | Final 状态 | 说明 |
|---|---|---|---|
| R4 UNKNOWN 分型 | **咨询可见**（advisory 节标注结构性/证据不足） | **咨询可见**（Final 不升级为自动阻断） | 理由码层已具备等价物；生产报告沿用即可 |
| R6 top-1 一致性 | **咨询可见**（advisory 节展示 + "非判据"标注） | **咨询可见**（Final 不采纳为判定规则） | 样本小（#47），仅解释性 |

**结论：R4/R6 属于"咨询可见"，Final 不需要将它们升级为生产闭环。** 理由码已存在、报告已展示，
唯一缺的是"人工看到后做出决策并留痕"——这正是 §4 的 mm-review-confirm 功能。

---

## 6. 三项遗留问题的处理建议

| 问题 | Final 处理 | 理由 |
|---|---|---|
| **运动素材 0** | **保留 LIMITATION**，Final 报告如实记录 | 全库 0 视频资产，不是 5.x 能解决的问题；评估子系统对静帧已完整验证 |
| **Wikimedia 网络 PENDING** | **保留 PENDING**，Final 报告如实记录 | pre-existing environmental；不因网络改写 PASS |
| **S06/S12 分歧** | **人工裁决**（§4 mm-review-confirm）：人工审阅后做出 accept/replace/keep_unknown 决定，append-only 写入决策记录 | 这是评估发现的真实质量问题，必须人工给出结论才能 Final |

---

## 7. 5.x Final 最小 DoD、验收顺序、回归要求、baseline 要求

### 7.1 Final 最小 DoD

| # | 标准 | 核对方式 |
|---|---|---|
| FD1 | 电池 25/25 rc=0 | 回归电池 |
| FD2 | 套件 46/46 rc=0 | 回归电池 |
| FD3 | 冻结指纹 14/14（12 精确 + 2 Phase 1.1 旧值披露） | 指纹对账 |
| FD4 | Run01–04 母片哈希不变 | hash 对账 |
| FD5 | v1 真值集 sha `7eb952f2…` 不变 | hash 对账 |
| FD6 | v2 真值集 sha `8adc2985…` 不变 | hash 对账 |
| FD7 | evidence ALL_GREEN=true（5-I 基线口径） | evidence JSON |
| FD8 | **人工决策 JSONL 存在且可解析**，至少覆盖 S06/S12 2 处 VIOLATION；每条含 decision_id/project/scene/decision/decided_by/decided_at/input_fingerprint | 决策 JSONL |
| FD9 | **mm-review-confirm 验证**：append-only（追加不覆盖）；accept/replace/keep_unknown 三态合法；replace 不自动执行；渲染行为零变更 | 集成测试 |
| FD10 | **keep_unknown ≠ accept**（语义不可互换） | 集成测试 |
| FD11 | 基线 sha256 记录在 BASELINE_README | README 对账 |

### 7.2 Final 验收顺序

1. 人工审阅 S06/S12 分歧 + p_8f05 纯色底 → 人工填写决策（accept/replace/keep_unknown）
2. 运行 `mm-review-confirm` → append-only JSONL 落盘（历史决策不可覆盖）
3. 电池 25/25 → 套件 46/46 → DRIFT 0
4. evidence ALL_GREEN
5. 冻结 Final baseline + manifest + verify MATCH + delta
6. Final 报告 → present → **STOP**

### 7.3 baseline 要求

- 起点：`5.x-phase5h-baseline`（当前基准）
- Final 新增：`5.x-phase5i-baseline`（或 `5.x-final-baseline`）
- delta 预期：修改 1-2（mm-review-confirm 新增 + 可能的 README 更新）/ 新增 1（决策 JSONL）/ 删除 0

---

## 8. 哪些事情绝对不属于 Final Gate

| 排除项 | 理由 |
|---|---|
| 新增能力（VIZ / 供给扩池 / 运动素材 / 新检索 / 新模型） | 每项都是独立授权阶段 |
| 域感知检索扩池落地（EXP-SS2 生产化） | G10 已达新口径 60；扩池是增量优化不是 Final 门槛 |
| 运动素材支持 | 全库 LIMITATION，Final 如实记录 |
| 修改阈值/真值/判定规则 | 5-F/G/H/I 纪律不变 |
| 自动换材/自动 redo/自动发布 | 人主导纪律不变 |
| Judge 自动拦截 MISMATCH | 人主导：人工确认后才行动 |
| 修改 4-B/5-A/5-D 任何源码 | 已冻结 |
| 追加真值集用例 | 5-G 已冻结 v2；扩充属后续授权 |
| 5.x Final 之后再启动 6.x | 那是新项目，不在本规划范围 |
| 修改 mm_judge / mm_quality / multimodal / mm_temporal / semantics | 5-F～5-I 已冻结，Final Gate 不触碰 |
| 自动执行 replace 决策 | replace 仅记录人工指定候选，不自动执行 |

---

## 9. 距离最终 AI 视频 Agent 目标的客观判断

### 已达成

| 维度 | 状态 |
|---|---|
| 生产链完整（脚本→TTS→素材→渲染→字幕→QA→成片） | ✅ |
| 多模态评估子系统（4-B/5-A/5-D/Judge 4 组件） | ✅ |
| 真值集 32 例 / 3 项目 | ✅ |
| Judge 最终裁决（J0–J6 + 优先级 + 理由码） | ✅ |
| 生产报告可见性（v1 + v2 全量 32 例） | ✅ |
| G10 生产 Run（101 拍 / 域一致 60 / HN 34 角标 / A/V 0.15s / 黑帧 0 / 字幕 100%） | ✅ |
| 冻结基线链（5-E→5-F→5-G→5-H，每步 verify MATCH） | ✅ |
| 回归电池 25/25 + 套件 46/46 | ✅ |

### 差距（Final 后的增量方向，不阻塞 Final）

| 方向 | 当前状态 | 所需 |
|---|---|---|
| Judge 自动拦截 MISMATCH | #49 BY DESIGN（只读咨询） | 人工先验证决策流程可行 → 再授权自动化 |
| 域感知检索扩池 | EXP-SS2 建议 30–45 新素材 | 新检索授权 + Top-K 8-10 + 域重写查询 |
| 运动素材支持 | 全库 0 视频资产 | 新素材供给授权 |
| VIZ 生产能力 | G10 自指拍用 HN 替代 | 新授权（结构卡/图表生成） |
| S06/S12 人工裁决 | 5-I 方案已设计决策流程 | Final Gate 前人工完成 |

### 客观判断

**5.x 阶段已经建立了从"文本脚本 → 视觉素材选择 → 多模态评估 → 最终裁决 → 生产报告 → 人工审阅"的完整闭环。**

剩余差距全部属于两类：
1. **需要人工决策才能关闭的闭环**（S06/S12 裁决、Judge 接线授权）——Final Gate 可关闭
2. **需要新授权才能扩展的能力**（扩池/VIZ/运动素材/自动拦截）——Final 后增量迭代

**5.x 的核心贡献不是"解决了所有问题"，而是"建立了一套可信的、可审计的、人主导的质量评估与决策框架"——Final Gate 验证的正是这个框架的完整性。**

---

## 10. 5.x Final Gate 设计摘要

```
5.x Final Gate = 一个独立阶段（约 1-2 个工作日）

前置：5-I CLOSED + 基线 5.x-phase5g-baseline 只读
输入：G10 生产 Run 评估结果（32 例 / 3 项目 / 2 VIOLATION / 6 UNRESOLVED）

步骤：
  1. 人工审阅 S06/S12 + p_8f05 → 人工填写决策（accept/replace/keep_unknown）
  2. 新增 mm-review-confirm CLI（对评估系统只读；仅 append-only 写入人工决策记录到项目目录 mm_review_decisions.jsonl）
  3. 电池 25/25 → 套件 46/46 → DRIFT 0 → evidence ALL_GREEN
  4. 冻结 Final baseline + manifest + verify MATCH + delta
  5. Final 报告 → present → STOP

输出：
  - Final baseline（SHA256）
  - 决策 JSONL（S06/S12 人工结论 + 全部 32 例决策，append-only）
  - Final 报告（全部 5-A～5-I 能力汇总 + 遗留 + LIMITATION）
  - KNOWN_ISSUES 最终版
```

```
FINAL GATE 规划 = 完成（修订版：mm-review-confirm 语义矛盾已解决）
本轮 = 纯规划 · 零代码 · 零测试 · 零基线 · 零冻结件触碰
STOP——等待人工授权（授权后按 §10 执行 Final Gate）
```
