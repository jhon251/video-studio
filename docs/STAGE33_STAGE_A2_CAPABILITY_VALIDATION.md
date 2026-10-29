# Stage 33 — Stage A-2: Capability Validation (Post-Engineering-Fix)

> **性质**:研究实验（分析师评分），零生产修改。预注册先于评分。
> 前置：Stage A-1 = ENGINEERING_RECOVERABLE（Axis 1/2/3 修复已验证）。
> 机器可读:`output/prod02/stage_a2_registration.json`

---

## 1. 核心原则

> **Generation success ≠ Capability pass。**
> 15/15 渲染成功 ≠ 15/15 证据质量通过。

严格区分：
- **生成成功** = VIZ 文件存在 + 渲染无错误
- **能力通过** = 生成成功 **且** 全部 atomic claims 被覆盖 **且** factual_correctness = correct **且** 非装饰

## 2. 实验设计

- **对象**:Stage A 原 15 个 VIZ objects（不增不减）
- **Control**:EXP-B 分析师 mockup
- **Treatment**:Stage A-1 修复后的 AI VIZ Generator
- **模型**:deepseek-v4-flash + High（与 A-1 一致）
- **评价**:分析师逐维度评分（8 维度 × 15 对象 = 120 行）
- **Protocol-2 priming**:可选子集

## 3. 评价维度(8 项)

| 维度 | 尺度 | 定义 |
|---|---|---|
| claim_coverage | 0 / 0.5 / 1 | VIZ 是否证据每个 atomic claim |
| info_structure_correctness | correct / partial / incorrect | 信息结构是否适合 |
| factual_correctness | correct / partial / incorrect / unsupported | 事实是否可溯源 |
| source_grounding | grounded / partial / ungrounded | 溯源完整度 |
| non_decoration | non_deco / partially_deco / purely_deco | 是否全为信息元素 |
| visual_qa | pass / warn / fail | 可读性+布局+无溢出 |
| readability | readable / partial / unreadable | 字号/对比/间距 |
| stability | stable / partial / unstable | 重跑结构一致性 |

## 4. 判定标准(预注册)

| 分类 | 条件 |
|---|---|
| **SUPPORTED** | ≥12/15 capability_pass AND factual_error_count = 0 AND intent_variance LOW |
| **PARTIALLY_SUPPORTED** | ≥9/15 capability_pass AND factual_error ≤ 2 |
| **NOT_SUPPORTED** | <9/15 capability_pass OR factual_error > 2 |
| **INCONCLUSIVE** | 生成失败 > 5 或评价过稀 |

## 5. 冻结边界

14 冻结件 · P-2 seal · EXP-B seal · EXP-A seal · render_163 · Run 01/02 · correspondence 50.5% · Stage 18–21 · per-claim shadow：全部不变。Production VIZ Rollout = NOT AUTHORIZED。

## 6. 执行流程

1. 用户授权 A-2 执行
2. 对 15 对象运行修复后的生成管线（同 A-1，同模型/参数）
3. 分析师按 8 维度逐对象评分
4. 与 EXP-B Control mockup 配对比较
5. 汇报 per-object + aggregate 指标

---

```
STAGE A-2 = READY（注册完成，待执行授权 + DeepSeek 余额）
STOP——不自行执行实验
```
