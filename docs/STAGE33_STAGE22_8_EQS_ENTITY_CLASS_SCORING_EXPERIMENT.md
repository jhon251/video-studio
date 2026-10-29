# Stage 33 — STAGE 22.8: EQS Entity-Class Scoring Experiment

> **性质**:研究实验(分析师评分),零生产修改。预注册先于评分(`stage22_8_preregistration.json`)。
> 机器可读:`output/stage22_visual_quality/stage22_8_eqs_entity_class_experiment.json`(评分表:`exp228_scoring.json`,21 行评分 / 14 组主张分解)

## 1. 实验 EQS(实验性公式,预注册)

```text
EQS_exp = 0.50×claim_coverage + 0.05×E1 + 0.10×E4 + 0.10×E5 + 0.25×entity_class_dimensions
honesty gate:证据诚实风险 或 零主张覆盖 → 封顶 0.35
intent wording 永远不是输入;CLAIM SET 从 narration 分解而来
```

Entity-Class 只决定**评价维度是什么**(DATA_CHART=定量正确性/轴标签/主张覆盖;HARDWARE=设备身份/部件/功能相关;PERSON=动作/角色/行为;ABSTRACT_CG=隐喻透明/evidence honesty/**abstraction penalty**…),**不决定分数天然高低**——无任何类别加分/减分项。

## 2. Paired 结果(Old = 冻结 CV2 意图条件判定 vs Exp = Claim-centered)

| 测试 | Old EQS | Exp EQS | 结果 |
|---|---|---|---|
| **P1 实验鼠**(同资产双意图) | 0.62 → **0.95**(措辞一变,swing 0.33) | 稳定低分(~0.21,两个措辞同分) | **意图条件化移除**:鼠不证据“已在人体工作”,措辞不再驱动 |
| **P2 EEG 头带女** | 0.9 / 0.6 / 0.88(三意图三判定) | 0.60(S30-B02 主张)/ 0.11(S17-B03 主张)/ **0.15(大气意图=无主张→装饰/HN 路由)** | generic person 不再被 atmosphere 祝福 |
| **P3 DATA_CHART** | VIZ-1 无法进入生产检索池;stock 图 0.2 | **VIZ-1 timeline 0.93**(覆盖 C2/C3);stock 图 0.10;钟 0.10 | **假阴性修复,且不是图表加分**:错配 stock 图依然低分 |
| **P4 ABSTRACT_CG** | 玻璃瓷砖 USABLE/H 0.85 | **honesty gate 封顶 0.35/0.03** | false HIGH 修正 |
| **P5 HARDWARE** | BrainGate 未入池;DBS 0.95(错配) | **BrainGate 0.95(保留)**;DBS 0.57(中度,见 N1) | 通过(带披露) |

## 3. 聚合指标(预注册清单)

- **意图条件方差**:鼠 Old swing 0.33 → Exp **0.0**;EEG 头带 Old swing 0.30 → Exp 按主张稳定;
- **False HIGH 修正:4 个**——玻璃瓷砖 0.85→0.03 · 车站钟 0.95→0.10 · 化学白板 0.95→0.38 · MRI 诊所 0.90→0.26;
- **DATA_CHART 假阴性修复**:覆盖主张的图表 0.93–0.95;错配 stock 图 0.10;
- **HARDWARE 保留**:BrainGate 0.95;DBS 0.57(见 N1);
- 大气祝福移除:EEG 头带 0.88 → 0.15(装饰/HN 路由)。

## 4. 判定:**SUPPORTED**(预注册标准全项核对)

意图条件化移除(P1/P2)✓ · False HIGH ≥3 修正(实际 4)✓ · DATA_CHART 假阴性修复 ✓ · 真硬件保留 ✓ · Correspondence/证据质量定义零触碰 ✓

## 5. 必须如实披露的发现与局限

1. **N1 混合主张稀释(真负面发现)**:DBS 对 S18-B02 的混合主张集 {读已有/写未解/性质不同} 得 0.57——标量 claim_coverage 把异质主张平均化了,只证据“写”子主张的设备被稀释。真系统 refinement:**per-claim 分数向量 + 主张加权聚合**;
2. **N2 单评分者**:全部 EQS_exp 为单一分析师判定,无评分者间信度检验;
3. **N3 设计循环性**:rubric 由知道失败案例的作者设计——在已知案例上验证了有效性,未做盲泛化;
4. **N4**:生成图表为研究 mockup,生产可视化能力仍未建(EXP-22.5 结论不变)。

## 6. Production 建议

1. 现在不改生产 EQS/CV2;
2. 未来授权的 EQS 线应采纳:主张分解为评分目标、实体类维度选择、honesty gate、per-claim 向量(N1);
3. 单评分者结果需独立评分者复现后才可进入任何生产设计冻结。

## 7. 冻结边界

零冻结模块/CV2/阈值/Gate/Assignment/Correspondence/baseline/Stage 21 EQS 定义/Run 01 母片修改;全部产物在 `output/stage22_visual_quality/`。

```
STAGE 22.8 = EXPERIMENT COMPLETE · STOP
判定 SUPPORTED(预注册标准:意图条件化移除 ✓ / false HIGH 修正 4≥3 ✓ / DATA_CHART 修复 ✓ / 真硬件保留 ✓) ·
诚实披露:N1 混合主张稀释 · N2 单评分者 · N3 设计循环性 · N4 mockup ·
Entity Class 只决定评价维度,不决定分数高低 · 零生产修改
STOP——不自动修改生产系统,等待授权
```
