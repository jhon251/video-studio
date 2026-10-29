# Stage 33 — EXP-B 封存 + 组合结论审计

> **性质**:实验封存 + 只读统计审计。零生产修改。
> 机器可读:`output/prod02/exp_b_sealed.json` · `exp_b_combination_audit.json`

---

## 1. EXP-B 封存

| 项 | 值 |
|---|---|
| 实验 | Visualization Routing Enhancement(15 对象) |
| 状态 | **SEALED — SUPPORTED** |
| Seal SHA256 | `96969e609ec7d812...` |
| 结果 | **15/15 成功**(5 HN→VIZ + 10 existing VIZ enhancement) |
| Safety | 全 0(0 装饰 / 0 来源风险 / 0 诚实违例 / 0 安全违例) |
| 平均信息增益 | 1.53 / 2 |
| HN→VIZ 成功率 | 5/5 |
| Existing VIZ 确认率 | 10/10 |

---

## 2. 组合结论审计(统计口径)

### 四个指标的精确定义与状态

| 指标 | 定义 | Run 01 | Run 02 | EXP-A/B 组合 | 状态 |
|---|---|---|---|---|---|
| **Photographic Correspondence**(冻结) | beat 显示自身 material-chain 资产且冻结 CV2 = USABLE/CU | 98.02% | **50.5%** | 50.5%(不变) | 冻结定义 |
| **Evidence Coverage**(实验指标) | beat 显示任何 information-bearing visual(photo OR VIZ) | — | **61.4%**(51+11) | 61.4%(不变) | 实验指标 |
| **Hypothetical Diagnostic Coverage** | evidence_coverage **如果** EXP-A 5 拍经重新 Assignment | — | — | **66.3%** | **HYPOTHETICAL ONLY** |
| **Multimodal Evidence Coverage** | photo + chart + diagram 全模态 | — | 61.4% | 66.3%(hypothetical) | 实验指标 |

### 审计 7 项发现(全部 CONFIRMED)

1. **Run 02 50.5% 是诚实下界**——不是系统失败;
2. **50.5% + VIZ 11 = 61.4%** 是有效实验指标(多模态证据覆盖);
3. **Run 02 + EXP-A 5 = 66.3% 是 HYPOTHETICAL ONLY**——5 个恢复候选未经重新 Assignment/渲染,不得写成实际 Run 02 Evidence Coverage;
4. **66.3% 不得报告为实际 Run 02 数值**——必须标注 "hypothetical / diagnostic only";
5. **EXP-B 5 HN→VIZ mockup 是分析师生成研究工件**——单评分者;设计循环性;非生产 infographic;
6. **Photographic correspondence 50.5% 不能被 VIZ 提升**——VIZ 是不同模态,correspondence 定义不变;
7. **EXP-A 5 恢复候选若经重新 Assignment,photo corr 可达 ~56.4%**——hypothetical,需授权 + 渲染。

### 核心洞察:四个指标的关系

```text
Photographic Correspondence(冻结,不可变)      Run 01: 98%  |  Run 02: 50.5%
  ↕ 不同概念
Evidence Coverage(实验指标,不冻结)            Run 02: 61.4%(含 VIZ)
  ↕ 不同概念
Hypothetical Coverage(仅诊断)                  Run 02 + EXP-A: 66.3%(hypothetical)
  ↕ 不同概念
Multimodal Evidence Coverage(如果未来正式化)   需 EXP-D(定义扩展)+ 授权
```

---

## 3. 最终能力矩阵(11 项)

| 能力 | 状态 | Production |
|---|---|---|
| Photo retrieval optimization(R1 + entity) | **EXP-A SUPPORTED**(5/7) | R1 已进生产;entity tier 待授权 |
| Claim-centered visualization routing | **EXP-B SUPPORTED**(15/15) | NOT AUTHORIZED |
| Per-Claim EQS(vector/min/critical recall) | **SUPPORTED**(22.9/22.10) | SHADOW ONLY |
| Entity-Class-aware evaluation | **SUPPORTED**(22.7/22.8) | SHADOW ONLY |
| Family Budget | PARTIALLY_SUPPORTED(22.6) | NOT RECOMMENDED |
| Autonomous visualization generation | **NOT VERIFIED** | NOT AUTHORIZED |
| Multi-rater human validation | **BLOCKED**(22.12) | REQUIRED before EQS production |
| Production visualization rollout | **NOT AUTHORIZED** | — |
| Production rollout of per-claim EQS | **NOT AUTHORIZED** | — |
| Intent typing + routing | **SUPPORTED**(EXP-22.1 refined) | requires authorization |
| Correspondence definition expansion | PROPOSED ONLY(EXP-D) | NOT AUTHORIZED |

---

## 4. 下一阶段候选(不执行)

| 选项 | 前置条件 |
|---|---|
| **A** 可视化生成能力建设 | 用户授权;EXP-B 模式已验证 |
| **B** Stage 22.12 人类多评分者验证 | ≥3 名评分者;评分包就绪 |
| **C** Production Rollout 设计 | R1 + routing + VIZ 整合到 Run 03;需全部前置 |
| **D** 新题材 Production Run | 用户授权 + 题材输入 |

## 5. 冻结边界确认

零冻结模块/CV2/Gate/V1/ranking/Assignment/correspondence/baseline/Run 01/Run 02/Stage 18–21/P-2 seal/per-claim shadow 修改;EXP-A seal 不变;EXP-B seal 本轮新建(`96969e60`)。

---

```
EXP-B SEALED = PASS
COMBINATION AUDIT = PASS(7 项发现全部 CONFIRMED;66.3% 正确标记为 hypothetical)
能力矩阵 11 项确认 · 冻结边界确认 · 零生产修改
STOP——等待授权
```
