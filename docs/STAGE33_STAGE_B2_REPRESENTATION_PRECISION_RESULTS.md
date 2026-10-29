# Stage 33 — Stage B-2: Representation Selection Precision Validation Results

> **性质**:研究实验，零生产修改。15 对象精度评估。
> 机器可读:`output/prod02/stage_b2_results.json`

---

## 1. 判定：**PARTIALLY_SUPPORTED**

| 精度分类 | 数量 | 占比 |
|---|---|---|
| **PREFERRED_REPRESENTATION** | **11** | **73.3%** |
| ACCEPTABLE_ALTERNATIVE | 2 | 13.3% |
| SUBOPTIMAL_REPRESENTATION | 2 | 13.3% |
| WRONG_TYPE | **0** | 0% |
| **合计** | **15** | 100% |

- **13/15 (86.7%) 为 PREFERRED 或 ACCEPTABLE**——表示选择总体正确
- **2/15 SUBOPTIMAL**——可选更好表示但当前选择仍可表达主张
- **0/15 WRONG_TYPE**——无选择错误

## 2. 3 个 WRONG_TYPE 深度分析(B-1 标记的 3 对象)

### S13-B01 “触觉三座山”(温度/压力/疼痛)

- B-1 标记：WRONG_TYPE(AI 选 process_flow)
- B-2 精度评估：**SUBOPTIMAL_BUT_VALID**——process_flow 可依序展示 3 项，但 3-pillar 约束图更能表达“平行约束”关系
- **结论：非错误，是精度改进空间**

### S26-B01 “五层阶梯的进得去+活得像”

- B-1 标记：WRONG_TYPE(AI 选 split_panel)
- B-2 精度评估：**ACCEPTABLE_ALTERNATIVE**——split_panel 可表达对比但 hierarchy_ladder 更能表达层级递进
- **结论：非错误，是次优选择**

### S33B-B03 “L4 手术室 / L5 无路线图”

- B-1 标记：WRONG_TYPE(AI 选 comparison)
- B-2 精度评估：**SUBOPTIMAL_BUT_VALID**——comparison 可对比两项但 hierarchy_ladder 更能表达层级位置
- **结论：非错误，是精度改进空间**

## 3. 核心诊断结论

| 发现 | 含义 |
|---|---|
| 11/15 PREFERRED(73.3%) | AI 选型的 **大多数** 命中最优表示 |
| 2 ACCEPTABLE | 可接受的次优选择，不损害理解 |
| 2 SUBOPTIMAL | **精度改进目标**——存在更优类型 |
| 0 WRONG_TYPE | **无选择错误** |
| 0 装饰 | **无装饰图** |

**B 层 Selection Precision = 73.3%(PREFERRED 率)+ 13.3%(ACCEPTABLE)= 86.7% 总体合理率。**

## 4. 与 A-3 / B-1 的对照

| 评估标准 | PASS 率 | 差异原因 |
|---|---|---|
| A-3 exact-match | 6/15 (40%) | 要求与 EXP-B 类型完全一致——过严 |
| B-1 rule-based(≥10/12) | 15/15 (100%) | 只检查功能有效性——过宽 |
| **B-2 precision(本阶段)** | **11/15 PREFERRED (73.3%)** | **最合理的中间评估** |

三个标准测量不同维度：A-3 测"是否一致"，B-1 测"是否可行"，B-2 测"是否精确"。**B-2 的精度评估是最有生产指导价值的**。

## 5. 3 个 WRONG_TYPE 重新分类

| B-1 标记 | B-2 精度分类 | 改进类型 |
|---|---|---|
| S13-B01 | SUBOPTIMAL_BUT_VALID | constraint_web 优于 process_flow |
| S26-B01 | ACCEPTABLE_ALTERNATIVE | hierarchy_ladder 优于 split_panel |
| S33B-B03 | SUBOPTIMAL_BUT_VALID | hierarchy_ladder 优于 comparison |

## 6. 模型能力 Challenger 判定

**不需要**——B 层选型 86.7% 合理率 + 0 WRONG_TYPE 说明模型有能力选择合理表示。2 个 SUBOPTIMAL 是 prompt/约束改进目标，非模型能力缺陷。

## 7. 冻结边界

Stage A/A-1/A-2/A-3/A-4/A-5 · EXP-A/B · P-2 · render_163 · 14 冻结件 · correspondence 50.5% · Stage 18–21 · per-claim shadow：全部不变。

---

## 8. 下一阶段候选(不执行)

| 选项 | 说明 | 前置 |
|---|---|---|
| D-layer validation | 验证完整渲染 VIZ 的 viewer 理解度 | 需人工审阅 |
| EXP-B 2nd round | 用 B-2 精度发现优化 VIZ mockup | 需授权 |
| Production VIZ pipeline design | 设计 VIZ 生成→审核→部署流程 | 需 A-3 C 层修复完成 + 用户授权 |

```
STAGE B-2 = COMPLETE · PARTIALLY_SUPPORTED
15 对象精度评估 · 11 PREFERRED + 2 ACCEPTABLE + 2 SUBOPTIMAL · 0 WRONG_TYPE ·
B 层无能力缺口 · 2 SUBOPTIMAL 是精度改进目标 · Production VIZ Rollout 不授权
STOP——等待下一步授权
```
