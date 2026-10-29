# Stage 33 — Stage A-3: Claim-to-Visual Mapping Diagnostic（设计注册）

> **性质**:设计注册，零 API 调用/零渲染/零生产修改。
> 机器可读:`output/prod02/stage_a3_registration.json`

---

## 核心问题

> **A-2 的 claim coverage 失败，到底发生在管线的哪一层？**

四层诊断管线：每层独立测试，每层有独立的失败签名和指标。

| 层 | 测试内容 | 输入 | 输出 | 评估者 |
|---|---|---|---|---|
| **A Claim Representation** | narration 是否正确分解为 atomic claims | narration | atomic claims 列表 | 人工编辑 |
| **B Representation Selection** | 每个 claim 是否选择了正确的 viz_type | atomic claims | viz_type + layout spec | 分析师 |
| **C Content Binding** | 每个 visual element 是否真正支持对应 claim | claim + viz_type | visual elements + binding | 分析师 |
| **D Final VIZ** | 完整渲染的 VIZ 是否有效传达 claim | rendered VIZ + narration | viewer 理解度评分 | 人工 |

## 停止规则

- 每层独立评估 15 拍；≥10/15 FAIL → 该层为主瓶颈，**停止并报告**
- 报告**最早**出现 ≥10 FAIL 的层——不测试后续层

## Challenger

`deepseek-v4-flash + Max` 已注册但**不执行**。仅在证明架构正确但生成仍失败时使用。

## 冻结

Stage A/A-1/A-2 · EXP-A/B · P-2 · render_163 · 14 冻结件 · correspondence · Stage 18–21：全部不变。

```
STAGE A-3 = READY
PRODUCTION VIZ ROLLOUT = NOT AUTHORIZED
STOP——等待执行授权
```
