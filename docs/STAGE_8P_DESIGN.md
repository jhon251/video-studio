# Stage 8P：Production Reality Calibration — 设计

> 状态：**设计待裁决**。仅设计，不实现。
> 限制：不新增 Agent；不接视频生成；不接素材库；不接 TTS/发布；不修改 Truth/Evidence Layer。

## 1. 目标与背景

针对 Stage 8O 现实性审计暴露的三个问题，设计 **Production Constraint Layer**（生产约束层），对 Production Plan 做**校准**：

| 8O 问题 | 8P 校准项 |
|---|---|
| 成本模型粒度不足（未区分 variant、缺生命周期） | A. 成本模型 2.0 |
| 视觉多样性与数据表达冲突（数据可视化 9-10% vs ≥25%） | B. 信息-视觉平衡指标 |
| 素材可获得性需约束（39% 中/困难 vs ≤30%） | C. 素材可获得性约束 |

**层定位**：`production_constraints.py`（新模块）作为 **post-processing 校准层**——读入 8N Production Plan，输出带成本 2.0/平衡指标/素材约束标注的校准版 Plan。**不修改** `visual_planning.py`、Truth/Evidence Layer；只增标注与确定性 fallback，不改证据引用。

## 2. A. 成本模型 2.0

### A1. visual variant 粒度（取代角色级成本）

成本按 `visual_target` 逐变体定价（取 8O 参考带中位）：

| visual_target | 成本(分钟) |
|---|---|
| 口播 + 大字标题卡 / 口播 + 全屏数字卡 | 8 |
| 快切素材 + 大字标题卡 | 22 |
| 结论大字卡 / 结论大字卡 + 落版 | 6 |
| 结论口播 + 关键数字卡 | 12 |
| 结论口播 + 呼应画面 | 15 |
| 事实核查字幕卡 / 来源截图 + 引注 / 核查清单卡 | 12 |
| 待补提示卡（黄底警示） / 转场字幕卡 | 4 |
| 数据可视化 + 证据截图 | 45 |
| 概念动画 + 口播 | 90 |
| 实拍素材 + 数据角标 | 30 |

### A2. complexity factor（复杂度因子）

每 scene 成本随内容复杂度缩放：

```
complexity_i = clamp(1 + 0.10 × |subtitle_emphasis_i| + 0.004 × len(script_text_i), 1.0, 2.0)
```

（字幕重点多、文本长的场景更费工；纯转场/待补接近 1.0。）

### A3. lifecycle factor（生命周期因子）

逐场景内容成本只占整片一部分；乘以标准相关生命周期开销（覆盖脚本迭代/录音重拍/剪辑合成/音频/审校/项目管理）：

```
calibrated_hours = (Σ scene_cost_i × complexity_i) / 60 × (1 + lifecycle_overhead)
lifecycle_overhead = { 个人创作者: 1.5, 小团队: 0.6, 专业媒体: 0.25 }
```

产出：每 scene `cost_est`（分钟）、整片 `calibrated_hours`、`lifecycle_overhead` 与标准名。

## 3. B. 信息-视觉平衡指标

### B1. claim 覆盖（保持 8N）

字幕重点覆盖全部 claim 数字/实体（must-contain 全中）——沿用 8N 验收，不回归。

### B2. 数据表达覆盖（新，化解"多样性 vs 数据"冲突）

claim 的**数字**应获得可视化表达（数据卡/图表），而非仅口播：

```
data_coverage = (出现在"数据可视化 + 证据截图"或"口播 + 全屏数字卡"场景 emphasis 的 claim 数字数) / (claim 数字总数)
```

该指标约束 8N 的多样性：允许 body 变体轮换，但**数字的可视化表达比例不得跌破阈值**。

### B3. scene 效率（新）

```
avg_density = Σ |subtitle_emphasis_i| / n_scenes
zero_density_ratio = (|emphasis_i| == 0 的 scene 数) / n_scenes
```

约束"信息密度不过载、不过稀"：平均密度在带内；纯转场/待补（0 元素）占比受控。

## 4. C. 素材可获得性约束

### C1. difficulty 分类（三档）

| 难度 | 素材来源 | visual_target |
|---|---|---|
| 高（自生成） | 口播/文字卡/截图 | 口播卡、结论大字卡、事实核查卡、待补卡、转场卡 |
| 中（自绘/自做） | 图表/动画/截图标注 | 数据可视化、概念动画、来源截图+引注、结论呼应 |
| 困难（外部素材） | 需素材库/实拍 | 快切素材、实拍素材+数据角标 |

### C2. fallback 策略（确定性降级，保持证据零漂移）

当 scene 难度为"困难"且超出难度预算时，按固定降级链替换视觉（**只改 visual_target/broll，不改 evidence_refs/subtitle_emphasis/script_text**）：

```
快切素材 + 大字标题卡  → 口播 + 大字标题卡
实拍素材 + 数据角标     → 数据可视化 + 证据截图
概念动画 + 口播        → 数据可视化 + 证据截图   （仅当动画超预算时）
结论口播 + 呼应画面     → 结论大字卡 + 落版
```

预算参数：`difficulty_budget = {"困难": 15%, "中+困难": 30%}`（占 scene 总数）。

## 5. 验收指标与成功阈值

| # | 指标 | 成功阈值 |
|---|---|---|
| A1 | variant 成本命中率 | 每 scene `cost_est` ∈ 8O 参考带 ±20% → **≥90%** |
| A3 | 校准总成本不再低估 | 对三种标准，`calibrated_hours` ≥ 对应下限（个人 2.5h/分钟、小团队 1.5、专业 1.0）→ **全 PASS** |
| B1 | claim 覆盖 | must-contain 全中（保持 8N） |
| B2 | 数据表达覆盖 | **≥60%** claim 数字进入数据卡/图表场景 |
| B3 | scene 效率 | 平均密度 ∈ **[1.5, 6]**；0 元素占比 **≤15%** |
| C1 | difficulty 分类 | 每 scene 有 difficulty 标注（100%） |
| C2 | fallback 约束 | 应用后：困难 **≤15%**、中+困难 **≤30%**；evidence_refs **零漂移**；确定性（同输入同输出） |
| 冻结 | 回归 | 15 套件 0 失败 + `semantic_judge.py` SHA256 不变 |

## 6. 停止条件

1. 一次性执行（校准 + 验收）完成后停止；不迭代调参。
2. 校准后仍不达阈值（如某 claim 数据表达覆盖 <60% 且已无可降级场景）→ 记 FAIL，只报告事实/数据/根因，**不自动二次调整**。
3. 不接视频生成/素材库/TTS/发布；不改 Truth/Evidence Layer；不新增 Agent。

## 7. 产物（执行后）

- `projects/_drafts/r1_stage8p_report.md`（PASS/FAIL + 数据 + 根因）
- `projects/_drafts/r1_stage8p_full.json`（校准后 Plan：cost_est/calibrated_hours/balance/difficulty/fallback 明细，可回放）
- 新增模块 `src/video_studio/tools/production_constraints.py`（成本 2.0 + 平衡指标 + 素材约束/fallback）

## 8. 本轮交付

本设计文档 `docs/STAGE_8P_DESIGN.md` 即本轮交付；不实现，等待裁决。
