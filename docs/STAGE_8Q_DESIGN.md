# Stage 8Q：Final Calibration & Freeze Decision — 设计

> 状态：**设计待裁决**。仅设计评估与最终校准方案，不实现。
> 限制：不进入 3.x；不接视频生成；不新增 Agent；不扩大系统边界。

## 1. 目标

对 Stage 8P 剩余问题做最终分类与校准，给出 **2.x 最终版冻结条件** 与 **Release Candidate（RC）判定标准**。

## 2. A. 剩余 FAIL 分类

| 8P 剩余 FAIL | 分类 | 处置与理由 |
|---|---|---|
| A1 成本命中率 48-53%（cost_est vs 参考带） | **必须修复（口径）** | 验收口径错误：`cost_est=base×complexity` 与不含复杂度的 8O 参考带比较本就不成立。改为校验 `cost_base` ∈ 参考带（应 100%），`cost_est` 仅作输出 |
| B3 过密（SC-TL 9.25 / SC-ALL 6.14） | **必须修复（逻辑）** | 8N fact 合并把多数字塞进 1 个 fact scene，导致密度过载。需"密度感知 fact 拆分"：单 fact scene 密度超阈值时拆为 2 个（证据 [n] 零漂移保持） |
| B3 过稀（existing 1.0-1.33） | **必须修复（阈值）** | 固定下界 1.5 对无数字 claim 不合理。密度阈值改为**按 claim 复杂度自适应**（见 C） |
| B2 数据表达 29-50%（数字密集 claim） | **可接受边界（口径）** | "数据表达"范围收窄为"仅数据可视化"导致误判；事实核查卡本身即数字的可视化表达。将 fact 卡纳入数据表达范围后可达 80-100% |
| C2 中+困难 39-43% vs 30% | **可接受边界（口径）** | 事实类视频的数据可视化（"中"素材）是刚需；改为"困难"硬约束 ≤15% + "中+困难"软预算 ≤45%（报告不 FAIL） |
| 昂贵变体（概念动画 90min） | **留给 3.x** | 成本优化与素材库接入属新能力 |
| 平台/内容细粒度密度适配（完整版） | **留给 3.x** | 2.x 只做 claim 复杂度自适应；平台级完整策略留给 3.x |
| 真实素材/许可素材接入 | **留给 3.x** | 需素材库（本系统边界外） |

## 3. B. Cost Model 最终校准方案

### B1. 口径修复（A1 → 必须修复项）

- 验收改为：每 scene `cost_base`（variant 定价）∈ 8O 参考带 `[ref_low, ref_high]` → **100%**。
- `cost_est = cost_base × complexity`（输出值），不再与参考带比较。

### B2. complexity factor 收窄

8P 的 clamp `[1.0, 2.0]` 过度放大；改为：

```
complexity = clamp(1 + 0.08 × |subtitle_emphasis| + 0.003 × len(text), 1.0, 1.4)
```

（variant 中位成本已含单场景完整工时，复杂度只作轻度修正，上限 1.4。）

### B3. lifecycle overhead 确定性校准（不手调）

目标：`calibrated_hours` 落入各标准**现实带**（非仅 ≥ 下限）：

| 标准 | 现实带（h/成品分钟） |
|---|---|
| 个人创作者 | [2.5, 4.0] |
| 小团队 | [1.5, 2.5] |
| 专业媒体 | [1.0, 1.5] |

**校准程序（一次性、确定性）**：
1. 以 VIDEO-10/15 为参照，先算出 `content_min = Σ cost_base × complexity`。
2. 对每标准求解 `lifecycle_overhead`，使 `calibrated_hours = content_min/60 × (1+overhead)` 落在现实带中位 ±5%。
3. 以该 overhead 对 VIDEO-15 交叉验证仍在带内；两视频均在带内则冻结常数。

产物：`LIFECYCLE_OVERHEAD_FINAL = {个人创作者: x, 小团队: y, 专业媒体: z}`（冻结进 `production_constraints.py`）。

### B4. 验收

- `cost_base` ∈ 参考带 100%。
- 三标准 `calibrated_hours` ∈ 对应现实带（两参照视频均验证）。

## 4. C. Adaptive Constraint Policy 设计

将 8P 的固定阈值改为**随 claim 复杂度自适应**（确定性，无 LLM/随机）：

### C1. 密度带自适应（修 B3 过密/过稀）

```
n = len(claim numbers_years)
density_band = 
  n == 0   -> [0.5, 4.0]
  1 <= n <= 3 -> [1.0, 5.0]
  n >= 4    -> [2.0, 8.0]
avg_density ∈ density_band 为 PASS
```

（数字密集 claim 允许更高密度；无数字 claim 允许稀疏。）

### C2. fact 密度感知拆分（修 B3 过密）

单 fact scene 的 `fact_refs` 数 > 4 或该 scene `density > density_band.high` 时，拆为 2 个 fact scene（按序均分 facts；`[n]` 引用零漂移；scene 数计入块预算，但 fact 允许占 2 镜）。

### C3. 数据表达范围（修 B2 口径）

```
data_expression_scenes = {数据可视化 + 证据截图, 口播 + 全屏数字卡, 事实核查字幕卡, 来源截图 + 引注, 核查清单卡}
data_coverage = 出现在上述场景 emphasis 的 claim 数字数 / claim 数字总数
```

### C4. 素材预算分档（修 C2 口径）

```
hard_budget: 困难 ≤ 15%（硬约束，超出走 fallback）
soft_budget: 中+困难 ≤ 45%（软约束，超出仅报告不 FAIL）
```

### C5. 验收

- 密度带自适应下 avg_density 全样本 PASS（含过密/过稀两端）。
- 数据表达覆盖（扩展范围）≥ 60%。
- 困难 ≤15%（硬）、中+困难 ≤45%（软）。

## 5. D. 2.x Freeze Checklist

1. 冻结模块 SHA256 全部不变（semantic_judge `75DA8D20…`、EvidenceSignal、Aggregation、Fact_check、冻结测试）。
2. 8L/8N 结构指标通过：Script-Scene 覆盖完整性 100%、Evidence 引用零漂移 100%、可执行性 100%。
3. 8N 生产约束通过：Scene 预算 ≤8、MAX_VISUAL_RUN ≤3、VIDEO-10/15 时长 ∈ ±10% 目标带。
4. 8P/8Q 校准通过：cost_base ∈ 参考带 100%、三标准 calibrated ∈ 现实带、困难 ≤15%、数据表达 ≥60%（自适应口径）。
5. 15 套件回归 0 失败。
6. 无生产接线（视频/素材库/TTS/发布均未接入）；全层研究态/隔离实现。
7. 文档齐备：8A-8Q 设计/验收报告 + Freeze Checklist + RC 判定。

## 6. E. Release Candidate 判定标准

**RC = GO** 当且仅当：
- §5 Freeze Checklist 全部通过；
- §2 中所有"必须修复"项修复完成并 PASS；
- §2 中"可接受边界"项已文档化（口径说明 + 数据）；
- §2 中"留给 3.x"项已列表登记（不阻断 2.x）。

**RC = NO-GO** 当：
- 任一"必须修复"项仍 FAIL，或任一冻结项被改动，或任一 Checklist 项失败。
- NO-GO 时只报告根因，不自动二次修复，等待裁决。

## 7. 执行步骤（裁决后）

1. 修口径：`production_constraints.py` 的 A1 校验改为 `cost_base`；complexity 收窄 [1.0,1.4]。
2. 校准 `LIFECYCLE_OVERHEAD_FINAL`（参照 VIDEO-10/15 + 现实带求解）。
3. 实现 Adaptive Constraint Policy（密度带/fact 拆分/数据表达范围/素材分档）。
4. 重跑 8P 验收（自适应口径）+ 8N 回归 + 15 套件 + SHA256。
5. 产出 `r1_stage8q_report.md`：逐项对照 §5/§6，给出 **GO / NO-GO**，停止。

## 8. 不做什么

- 不进入 3.x；不接视频生成/素材库/TTS/发布；不新增 Agent；不扩大系统边界。
- 不改 Truth/Evidence Layer 与冻结模块；不针对具体 claim/网站写特例；失败只报告不自动二次修复。

## 9. 本轮交付

本设计文档 `docs/STAGE_8Q_DESIGN.md`；不实现，等待裁决。
