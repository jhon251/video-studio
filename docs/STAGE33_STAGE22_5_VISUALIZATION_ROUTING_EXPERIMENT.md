# Stage 33 — STAGE 22.5: Visualization Routing Experiment

> **性质**:研究实验,零生产修改。预注册先于评分(`stage22_5_preregistration.json`)。
> 机器可读:`output/stage22_visual_quality/stage22_5_visualization_experiment.json`
> 实验产物:5 张生成图表 mockup(`exp225/viz/`)+ 3 张检索真实图表 + 13 组 A/B 对照评分。

## 1. 实验设计

13 拍三组(预注册):**A 结构性无摄影证据**(5:三尺度/瓶颈/带宽/五层回顾/L5 留白)、**B 真实证据优先**(4:BrainGate/NEO/力反馈手套/AI 队友)、**C 易误路由抽象**(4:读vs写/写入接口/NPC 一致性/SAO 钩子)。每拍对照:Path A = 生产池最优照片(冻结判定);Path B = 可视化(HN/生成 mockup/检索图表)。评分 = 预注册 rubric(claim_support / information_gain / narrative function / specificity / honesty_risk),分析师判定并标注。

## 2. 结果(严格按预注册口径)

| 组 | 结果 |
|---|---|
| **A 结构组:可视化胜 5/5** | 时钟(0 信息)→ 三尺度 timeline;化学白板(借用 fallback)→ 约束关系图;通用芯片微距 → 带宽对数图;“L5 不存在”只能用结构留白表达 |
| **B 证据组:真实照片胜 4/4** | R1 修复后 BrainGate 真实临床照可达,胜过任何示意图;DBS 真实设备照(0.95)胜过抽象接口示意 |
| **C 易误路由组:可视化仅胜 1/4** | 唯一胜者是 S18-B02——因为“读vs写”含**对比结构**(预注册已预期可升 V4);其余 3 拍图表=装饰 |

**判定:SUPPORTED(满足全部预注册条件:A≥4/5 ✓ · B≥3/4 ✓ · C≤1 ✓)**

## 3. 最重要的诚实声明(循环性 confound)

A 组胜出的 5 张图是**由知道 narration 的分析师生成的实验 mockup**。本实验证明的是:**可视化能够表达这类主张**(可行性与信息增益为真),**不是**生产系统能自主生成它们。后者是独立的工程能力线,需另行授权建设。检索真实图表为阴性结果(TRL 查询命中飞机照;图表被照片 rubric 判罚)——支持“生成而非检索”的路线假设,但该假设本身未独立验证。

## 4. Entity-Class 诊断(只读,不改阈值)

双向偏差实锤:

| entity_class | 案例 | intent | CV2 |
|---|---|---|---|
| SCIENTIFIC_SPECIMEN | 实验鼠照片 | evidence(implant) | CU/M 0.62 |
| SCIENTIFIC_SPECIMEN | 同一张 | structure(BCI lab) | **USABLE/H 0.95** |
| ABSTRACT_CG | 玻璃瓷砖 | evidence-hardware | **USABLE/H 0.85** |
| HARDWARE | BrainGate 临床照 | evidence(brain implant) | USABLE/H 0.85 |
| DATA_CHART | B2B 脑脑通信图 | evidence(schematic) | **NOT_USABLE/H 0.15(图表盲)** |

**ABSTRACT_CG 在硬件/结构意图下可获 USABLE/HIGH(意图祝福);DATA_CHART 即使主题正确也被照片 rubric 判罚。** 实体类维度缺失同时造成两类错误——这是 Stage 21 EQS 应纳入的维度,本阶段只记录。

## 5. 结论与 Production 建议

1. **Routing 假设 SUPPORTED**:meta/定量/结构型 narration → Visualization 或 Honest Neutral;evidence 型 → 真实证据检索(现状即可);对比/组合结构者升 V4;C 类默认 Honest Neutral 防装饰化。
2. **可视化能力线是生产前必须建成的唯一新能力**(生成 + 风格系统 + 模板审核),属新授权决策。
3. 与已落地修复组合后的 Run 02 改善路径:RC1 = typing+routing(本实验支持)· RC2 = R1(已修复)· RC3 = 族级预算(待实验)。

## 6. 冻结边界

零冻结/生产/baseline 修改;CV2/Gate 未动;Run 01 母片未动;EXP-22.1 的 NOT_SUPPORTED 结论未被重解释;全部产物在 `output/stage22_visual_quality/`。

```
STAGE 22.5 = EXPERIMENT COMPLETE · STOP
A 组可视化 5/5 · B 组真实证据 4/4 · C 组 1/4(恰为对比结构型) · 判定 SUPPORTED(预注册口径) ·
循环性 confound 如实披露(mockup 为分析师生成) · Entity-Class 双向偏差实锤 · 零生产修改
STOP——等待授权,不进入 Stage 23
```
