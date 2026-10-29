# Stage 33 — STAGE 22.11: Blind Multi-Rater Per-Claim EQS Validation

> **性质**:盲态多评分者验证,零生产修改。预注册先于盲评(`stage22_11_preregistration.json`)。
> 机器可读:`stage22_11_blind_multi_rater_validation.json` · `stage22_11_rater_scores.json` · `stage22_11_reliability.json` · `stage22_11_blind_cases.json`

## 1. 必须先声明的强制限制

**MODEL_RATERS_NOT_HUMAN**:本环境无法获得 3 名人类独立评分者。替代方案为 3 个**独立盲态 LLM 评分者实例**(DeepSeek 视觉,独立上下文,temp 0.2/0.4/0.6,提示中无任何既有分数/标签/CASE_A/实体预期),且其中 1 个评分者与冻结 CV2 同源模型族——**存在关联偏差风险**。按预注册设计,此限制将分类**封顶于 PARTIALLY_SUPPORTED**;人类多评分者验证仍是必需的未来步骤。

## 2. 盲评设计

38 拍 / 75 真实候选(系统步长抽样 + 必要旗舰,旗舰占比 **18.4% ≤ 30%** ✓);评分者只见:**原子主张文本 + 候选图像**(Protocol-1;Protocol-2 实体类 priming 子集**未执行**,如实记录)。重要性标注为独立 pass:仅见 narration 文本,不见图像、不见他人标签。64/75 候选获得三评分者完整覆盖;39 条 (beat, slot, claim) 行构成信度/ADR 核心(如实计数)。

## 3. 信度(核心正结果)

| 统计 | 值 |
|---|---|
| **Fleiss κ(coverage 二值,3 评分者)** | **0.809(优秀)** |
| pairwise Spearman(coverage) | 0.745 / 0.668 / 0.845 |
| pairwise Spearman(evidence quality) | 0.799 / 0.685 / 0.892 |
| 重要性盲标 vs 分析师预注册标签一致率 | 17/30 = **0.567(弱项)** |

κ 0.809 证明:**盲态评分者能够一致地应用 claim-centered rubric**。但重要性标注一致率弱 → 任何生产设计中 CRITICAL 标签应路由给**人工编辑判断**。

## 4. 盲态 ADR 与 CCR

- 盲共识下的关键主张缺口:**16 处**;其中 **6 处(ADR 0.375)坐在冻结标量 HIGH/USABLE 后面**——方向性发现**在盲条件下存活**;
- **CCR(盲)**:scalar 暴露 **0.375** vs mean/weighted **0.938** / min **1.0**——向量族仍压倒性优于标量;
- 与 22.10 对比(23 个重叠拍):已知(分析师)crit_min 均值 0.022 vs 盲共识 0.167,Spearman 仅 0.276——**分析师显著更严苛**,22.10 的量级部分来自 evaluator leakage,但**方向不受影响**。

## 5. 权重敏感性与 min 审计

- 权重:W1/W2/W3 候选级暴露均 **12/13**——**敏感性 LOW,结论稳定**;
- min 审计旗标:TP 13 / FP 7 / FN **0** / TN 6 → **precision 0.65,recall 1.0**——recall 完美、precision 中等 → **维持“AUDIT FLAG ONLY”**,不可自动拒绝(NC-D 过度惩罚已证);7 个误报即“需要人工看一眼”的合理成本。

## 6. NC / 协议覆盖

NC1/NC2/NC3/NC4 均有真实案例并按预期表现;NC5(同资产换措辞)仅跨实验方向一致(PARTIAL);NC6(异类同覆盖)**INSUFFICIENT SAMPLE**;Protocol-2 **NOT EXECUTED**(如实记录)。

## 7. 判定:**PARTIALLY_SUPPORTED**(预注册规则)

- 盲 ADR 0.375 ∈ [0.25, 0.4) → SUPPORTED 档(≥0.4)**未达**;
- κ 0.809 ✓ · CCR 方向性改善 ✓ · 权重稳定 ✓ · min audit-only 确认 ✓;
- **封顶原因**:非人类评分者 + 重要性标签一致率弱 + 盲验幅度衰减。

## 8. Production Decision

Per-Claim EQS **保留进入 engineering design / shadow integration 的验证证据**;**Production rollout 未获授权**。人类多评分者验证 + CRITICAL 标签的人工评审机制是前置条件。

## 9. 冻结边界

零冻结模块/CV2/Gate/ranking/Assignment/EQS/baseline/Run 01 母片修改;全部产物在 `output/stage22_visual_quality/`。

```
STAGE 22.11 = VALIDATION COMPLETE · STOP
盲 ADR 0.375(6/16) · κ 0.809 · CCR scalar 0.375 vs vector 族 0.938-1.0 · 权重稳定 ·
min = audit flag 确认(precision 0.65 / recall 1.0) · MODEL_RATERS_NOT_HUMAN 封顶 PARTIALLY_SUPPORTED ·
盲验后方向存活、量级衰减(leakage 部分证实) · Production rollout 不授权
STOP——等待授权
```
