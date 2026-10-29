# 5-H 规划方案：v2 评估结果生产报告可见性（R4 完整落地 + R6 展示）

> 阶段: 5-H（规划稿，等待人工授权）
> 基线: `5.x-phase5g-baseline`（sha256 `355b2a05…`，当前唯一基准）
> 纪律: 单一核心能力；不进入 5.x Final；不自动换材/选材/redo/发布

---

## 0. 现状断裂（通读代码 + 5-F/5-G/5-H 报告后确认）

### 已完成能力

| 组件 | 能力 | 状态 |
|---|---|---|
| 4-B | 文本语义（类别式规则） | ✅ |
| 5-A | 单帧像素（CLIP 3 帧） | ✅ |
| 5-D | 多帧时序（CLIP 7 帧 + 一致性 + 逐帧投票） | ✅ |
| 5-E | 校准/覆盖度/边界距离/可解释链/敏感性 | ✅ |
| 5-F | Judge 最终裁决（J0–J6 + 优先级 + 冲突不选边 + 10 理由码） | ✅ |
| 5-G | 真值集 v2（32 例 / 3 项目 / 多镜头 12 / 纯色 6 / 边界 4） | ✅ |
| 5-H | `--mm-advisory` 只读咨询节 | ✅ |

### 当前断裂

5-H 的 `--mm-advisory` 读取**一份 Judge JSON**，但 Judge JSON 需要 **judge_truth 覆盖层**来产出 rows。
覆盖层 `mm_judge_truth_v1.json` 只覆盖 **v1 14 例**（全部来自 `p_f4b466a4a024`）。
v2 新增的 **18 例**（p_ab2b 12 + p_8f05 6）没有覆盖层条目 → **Judge JSON rows = 0** → 咨询节返回 None。

结果：**5-G v2 评估发现的 2 处真实层-人分歧（S06/S12 实例粒度漂移）+ 6 处纯色 fail-closed**
**全部不可见于生产报告**。人工无法看到它们，更无法基于它们做决策。

### 关键数据点（v2 评估实际发现，但目前不可见）

| 项目 | 发现 | 当前可见性 |
|---|---|---|
| p_ab2b S06/S12 | **4-B MATCH vs 5A/5D MISMATCH**（12 段复用 3 张静帧的实例粒度漂移） | ❌ 不可见 |
| p_8f05 全片 | **纯色底 + 字幕，零视觉证据**（素材装配 PENDING） | ❌ 不可见 |
| G10 域一致 60/101 | **60 拍域一致 + 34 拍 HN 角标** | ❌ 不可见 |
| p_ab2b S07–S10 | **4 处域边界**（旁白从 VR 换到 BCI，画面未切换） | ❌ 不可见 |

---

## 1. 5-H 核心能力

> **v2 评估结果生产报告可见性**：`run.py report --mm-advisory` 的咨询节从
> "仅 v1 14 例 Judge 结果" 扩展为 "v2 全量 32 例 / 3 项目评估结果"，
> 包括逐项目逐镜头判定 + 2 处实例粒度分歧 + 纯色底 fail-closed + G10 域一致状态。
> 数据来源 = 冻结的 v2 评估产物（phase5g_quality_*.json + phase5g_judge_*.json），零实时计算。

---

## 2. 目标与非目标

### 目标

1. 咨询节读取**全部 3 个 v2 评估产物**（不再只读 v1 一份 Judge JSON）
2. 覆盖 **32 例**（v1 14 + p_ab2b 12 + p_8f05 6），按项目分组展示
3. **2 处 S06/S12 实例粒度分歧**显式呈现（4-B MATCH vs 5A/5D MISMATCH 的层间冲突），标注"需人工裁决"
4. **6 处纯色底 fail-closed** 显式呈现（标注"零视觉证据，层拒绝发证"）
5. **G10 域一致状态**（60 域一致 + 34 HN 角标 + 7 NO_EXPECTATION）在汇总行呈现
6. R4 UNKNOWN 两种语义分型（结构性 vs 证据不足/层间冲突）继续标注
7. R6 top-1 一致性继续展示（标注"非判据"）

### 非目标

- ❌ Judge 接入生产判定链（#49 维持 BY DESIGN）
- ❌ 自动换材/选材/redo/发布
- ❌ 修改任何评分逻辑、阈值、判定规则
- ❌ 修改 mm_judge.py / mm_quality.py / multimodal.py / mm_temporal.py / semantics.py
- ❌ 修改真值集 v1 或 v2
- ❌ 供给扩池、VIZ、G10 域感知重查询落地
- ❌ 进入 5.x Final

---

## 3. 允许修改范围

| 路径 | 允许 | 说明 |
|---|---|---|
| `src/video_studio/ops/report.py` | ✅ | `format_mm_advisory` 重写：从单文件改为多文件聚合 |
| `src/video_studio/cli.py` | ✅ | `--mm-advisory` 接受多路径（逗号分隔或多次出现） |
| `src/video_studio/core/mm_judge.py` | ❌ 零改动 |
| `src/video_studio/core/mm_quality.py` | ❌ 零改动 |
| `src/video_studio/core/multimodal.py / mm_temporal.py / semantics.py` | ❌ 零改动 |
| `tests/fixtures/*` | ❌ 零改动 |
| 冻结模块 14 件 / Run01–04 / 生产 DB 生产项目 | ❌ 只读 |
| `docs/regression_2x/`（5-H→5-I 证据） | ✅ 新增 |

---

## 4. DoD 硬标准

| # | 标准 | 核对方式 |
|---|---|---|
| D1 | 咨询节覆盖 **32 例**（3 项目分组展示），不再仅 v1 14 例 | 断言行数 = 32 |
| D2 | 按项目分组：每组标注项目 ID + 用例数 | 断言含 3 个项目标题 |
| D3 | **2 处 S06/S12 实例粒度分歧**显式呈现（含层间冲突详情：4-B MATCH vs 5A/5D MISMATCH），标注"需人工裁决" | 断言输出含冲突详情 |
| D4 | **6 处纯色底 fail-closed** 显式呈现，标注"零视觉证据，层拒绝发证" | 断言 p_8f05 组有标注 |
| D5 | G10 域一致状态：域一致 60 / HN 34 / NO_EXPECTATION 7 | 断言汇总行数值 |
| D6 | R4 UNKNOWN 两种语义分型继续标注 | 断言 UNKNOWN 行含分型 |
| D7 | R6 top-1 继续展示（"非判据"标注不变） | 断言 |
| D8 | `--mm-advisory` 默认关闭不变；无评估项目不崩溃 | 断言向后兼容 |
| D9 | mm_judge/mm_quality/multimodal/mm_temporal/semantics sha256 与 5-G 基线一致 | hash 对账 |
| D10 | 电池 25/25 rc=0 + 套件 46/46 + DRIFT 0 | 回归电池 |
| D11 | `format_report` 尾行不变 | 断言 |
| D12 | v1 14 例的判定行**逐行一致**（不因格式重写而丢失） | 对账 5-F 冻结 |

---

## 5. 真实验证方案

1. p_f4b466a4a024（v1 14 例）：验证 14 行判定不变
2. p_ab2b352e06b8（v2 12 例）：验证 2 处 VIOLATION 显式呈现
3. p_8f054c227bd4（v2 6 例）：验证纯色 fail-closed 显式呈现
4. 全量 32 例总数核对（14 + 12 + 6 = 32）
5. 回归电池 25/25 + 套件 46/46 + DRIFT 0
6. 人工审阅格式化输出

## 6. fail-closed / 人工审核边界

- `--mm-advisory` 继续为显式开关（默认关闭）
- 节头标注"只读咨询"，尾部标注"人工决策依据，非自动阻断"
- 无评估数据的项目显示"未评估"，不崩溃
- 评估子系统（mm_quality/mm_judge/multimodal/mm_temporal/semantics）零改动

## 7. 兼容要求

- 不加开关时 report 输出与 5-G 基线一致
- 评估子系统 sha256 不变
- 4.x 链路零触碰
- `5.x-phase5g-baseline` 保持只读

## 8. 风险与限制

| 风险 | 缓解 |
|---|---|
| 32 例跨 3 项目的咨询节可能过长 | 按项目分组 + 每项目仅显示状态与理由码（明细入 --json） |
| S06/S12 层间冲突呈现可能被误读为"系统故障" | 标注"需人工裁决"而非"错误"；含四段式解释链 |
| v2 评估产物的三个文件路径需要硬编码或 CLI 传入 | CLI 接受逗号分隔的多路径；RUNBOOK 说明用法 |
| 评估产物过旧 | 报告标注评估时间戳 |

## 9. baseline / manifest / SHA256 / 回滚

- 起点：`5.x-phase5g-baseline`（`355b2a05…`）只读
- 允许修改：`ops/report.py` + `cli.py` → 基线 delta 披露
- 完成后：`make_baseline.py 5.x-phase5h-baseline --no-docs` → verify MATCH → delta vs 5-G → snapshot
- 回滚：还原 report.py + cli.py diff → 即回到 5-G 基线态

## 10. 推荐验收顺序

1. 实现（`format_mm_advisory` 重写为多文件聚合）
2. 三项目 v2 评估数据验证（32 例逐项对账）
3. 单元测试（格式正确 / 无数据不崩溃 / 向后兼容）
4. 回归电池 25/25 + 套件 46/46 + DRIFT 0
5. 冻结 `5.x-phase5h-baseline` + manifest + verify MATCH
6. 人工审阅格式化输出
7. 报告 + STOP

---

## 11. 与最终 AI 视频 Agent 目标的距离

| 已有 | 差距 |
|---|---|
| 多模态评估子系统（5-A～5-G 完整） | ✅ 已完整 |
| Judge 最终裁决（5-F 完整） | ✅ 已完整 |
| v2 真值集 32 例 / 3 项目（5-G） | ✅ 已完整 |
| 生产报告可见性（5-H v1 only → 5-I v2 全量） | **5-I 补全** |
| Judge 接入生产判定链（#49） | 未来（人工先看到，再决定授权自动化） |
| 域感知检索扩池（SS 系） | 未来（已规划 EXP-SS2 后续） |
| VIZ 生产能力 | 未来（G10 阶段自指拍需要） |
| 运动素材支持 | LIMITATION（全库 0 视频资产） |

5-I 是"人主导"闭环的**最后一个可见性缺口**：人工完成评估 → 看到结果 → 做出决策。
补上之后，从"自动生产 → 评估 → 可见 → 人工决策"的闭环就完整了。

---

## 附：执行顺序（授权后）

A. 实现（format_mm_advisory 多文件聚合重写）→ B. 三项目数据验证 → C. 单元测试 → D. 回归电池 → E. 冻结 5.x-phase5h-baseline → F. 人工审阅 → G. 报告 + STOP
