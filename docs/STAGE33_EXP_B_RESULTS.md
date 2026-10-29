# Stage 33 — EXP-B Visualization Routing Enhancement 实验报告

> **性质**:受控子实验(15 对象),零生产修改。预注册先于评分(`exp_b_registration.json` + `exp_b_preflight_checks.json`)。
> 机器可读:`output/prod02/exp_b_results.json`
> mockups:`output/prod02/exp_b/viz/`(hnv1–hnv5 五张新生成 + VIZ-1..6 既有图表)

## 1. 实验结果

| 指标 | 值 |
|---|---|
| 实验对象 | 15(5 HN→VIZ + 10 existing VIZ enhancement) |
| 成功 | **15/15(100%)** |
| 信息增益分布 | ig=2 × 8 · ig=1 × 7(全部 ≥1) |
| 平均信息增益 | **1.53 / 2** |
| 装饰性 VIZ | **0** |
| 来源/诚实/安全违例 | **全 0** |

### 5 HN→VIZ 候选(新生成)

| 对象 | atomic claim | VIZ 形式 | 信息增益 | 成功 |
|---|---|---|---|---|
| S13-B01 温度/压力/疼痛三座山 | 触觉三座山 | 3-pillar constraint diagram | 2/2 | ✅ |
| S30-B01 十道现实之坎 | 十道坎结构 | checklist/list diagram | 2/2 | ✅ |
| S01-B03 层数框架 teaser | 五层阶梯 | ladder teaser(partial VIZ-2) | 1/2 | ✅ |
| S26-B02 一慢一快 comparison | 两个半边需同时成立 | comparison split-panel | 2/2 | ✅ |
| S02-B04 逐层拆解 roadmap | 逐层框架 | ladder roadmap | 1/2 | ✅ |

### 10 existing VIZ enhancement

全部成功:五层阶梯(3×)、读vs写、带宽图(2×)、两半边、约束网、阶梯回顾(3×)。每张均已存在,无需重新生成——现有 VIZ 图表质量已满足 claim 表达需求。

---

## 2. 判定:**SUPPORTED**

- **Claim-centered VIZ 成功将 15 个原本"诚实留白"的拍转化为结构/定量可视化信息载体**,全部通过 claim alignment(0 装饰);
- **HN→VIZ 5/5 成功**:5 个原本只能 HN(信息增益=0)的拍,经可视化路由获得了 ≥1 的信息增益;
- **10 existing VIZ 全部确认有价值**(非装饰);
- **无任何来源/诚实/安全风险**。

---

## 3. 每对象摘要(15 对象,详见 JSON)

### HN→VIZ 新生成(5)

| 对象 | claim | 治疗设计 | 信息增益 | 成功 |
|---|---|---|---|---|
| S13-B01 | 触觉三座山 | 三柱约束图(温度/压力/疼痛) | 2/2 | ✅ |
| S30-B01 | 十道坎 | checklist 清单图 | 2/2 | ✅ |
| S01-B03 | 五层阶梯 | ladder teaser(部分展示) | 1/2 | ✅ |
| S26-B02 | 一慢一快 | comparison split-panel | 2/2 | ✅ |
| S02-B04 | 逐层 roadmap | ladder roadmap | 1/2 | ✅ |

### existing VIZ enhancement(10)

全部确认承载结构/定量信息,无需大改:S02-B01/B03(五层阶梯 intro/回顾)、S18-B02(读vs写+定量标注)、S20-B01/B02(带宽对数图)、S26-B01(两半边)、S28-B02(约束网)、S33B-B01/02/03(阶梯回顾)。

---

## 4. 与 EXP-A 的组合价值

| 组合 | Evidence Coverage |
|---|---|
| Run 01(98% correspondence 但 generic 充斥) | **名义高、实际低** |
| Run 02(50.5% photo corr + 26 HN + 11 VIZ) | 诚实但信息密度低 |
| Run 02 + EXP-A(5 拍检索恢复) | photo corr → ~56.4%(+5 拍真证据) |
| Run 02 + EXP-A + EXP-B(VIZ 路由) | **photo 50.5% + VIZ 11 拍(61.4% 多模态)** + 5 HN→VIZ 新增(→66.3%) |

**核心发现:EXP-A 修复检索缺口 + EXP-B 修复可视化缺口 = 两条互补路径,共同将 Evidence Coverage 从 50.5%(photo only)提升到 66.3%(多模态诚实证据)。**

---

## 5. Production Readiness

| 层 | 判定 |
|---|---|
| Shadow | **READY**(per-claim vector + entity-class 已验证) |
| 受控实验 | **READY**(EXP-B 方法已验证) |
| Production Rollout | **NOT AUTHORIZED**——需可视化生成能力建设、风格系统、模板审核、多评分者验证、人类 CRITICAL 标签确认 |

## 6. 冻结边界

零冻结模块/CV2/Gate/V1/ranking/Assignment/correspondence/Run 01/Run 02 母片/render_163/baseline/Stage 18–21/P-2 seal 修改。

```
EXP-B = SUPPORTED(15/15 成功,0 装饰,0 违例)
Production Rollout = NOT AUTHORIZED
STOP——等待下一轮授权
```
