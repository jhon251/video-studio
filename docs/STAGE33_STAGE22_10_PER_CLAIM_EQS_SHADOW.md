# Stage 33 — STAGE 22.10: Per-Claim EQS Shadow / Offline Evaluation

> **性质**:Shadow 离线评估,零生产修改。预注册先于评分(`stage22_10_preregistration.json`)。
> 机器可读:`output/stage22_visual_quality/stage22_10_per_claim_eqs_shadow.json`(原始数据:`exp2210_shadow_raw.json` / `exp2210_analysis.json` / `exp2210/claims_decomposition.json`)

## 1. Shadow 设计与规模

- **盲式主张分解**(先于候选评分,仅从 narration):27 个分层抽样拍,**47 条主张(33 CRITICAL / 12 IMPORTANT / 2 SECONDARY)**;
- **84 个真实候选**通过三路评分:A 冻结标量(frozen CV2)/ B 实体感知标量(22.8)/ C 向量(22.9,C1 mean / C2 weighted-W2 / C2' weighted-W3 / C3 min);
- 覆盖全部指定旗舰:DBS、BrainGate、EEG 头带、实验鼠、DATA_CHART、ABSTRACT_CG、≥3 PERSON atmosphere、≥3 HARDWARE、≥3 mixed-claim。
- **EVALUATOR_LEAKAGE = PRESENT**(单一分析师,对池有先验知识)——结论强度相应下调,已如实记录。

## 2. 核心结果:关键主张缺口的暴露率

| 评分方式 | 暴露缺口 / 63 | 暴露率 |
|---|---|---|
| **A 冻结标量(生产)** | **30** | **47.6%** |
| B 实体感知标量 mean | 60 | 95.2% |
| C2 weighted(W2 预注册权重) | 62 | 98.4% |
| C2' weighted(W3 关键强调) | 62 | 98.4% |
| **C3 min(仅审计旗标)** | **63** | **100%(构造性)** |

## 3. AUDIT DISCOVERY RATE = **0.524**

63 个关键主张缺口中,**33 个(52.4%)坐在冻结标量的 HIGH/USABLE 判定后面**——被生产评分完全掩盖。CASE_A 目录(前 10 例):VR 用户照片三连(S01-B02,fit 0.90–0.95,主张覆盖 0)、VINCENTvr(0.95)、Braille Glove(0.95)、发光机械手(0.95)、眼科无关照(0.95)、论文图(0.90)…… **全部是 scalar HIGH 而 critical coverage = 0**。

## 4. 各专项复核(指定旗舰全覆盖)

- **S18-B02 DBS**:scalar 0.95 vs 关键主张 F5“完整感觉写入未解决”覆盖 0.0 → 向量/min 暴露缺口;
- **S16-B01 BrainGate vs 鼠**:BrainGate 覆盖 1/1/1;鼠 0.5/0/0.5——向量分离了标量几乎同分的两个候选;
- **EEG 头带女**:三意图三判定(0.9/0.6/0.88)——claim-centered 评分意图无关,稳定;
- **DATA_CHART**:VIZ-1/VIZ-3 在 META_QUANT 意图下 0.95,错配 stock 图 0.10——主张覆盖而非图表加分;
- **ABSTRACT_CG**:S19-B01 3D 脑 scalar HIGH 而三条关键主张全 0 → CASE_A。

## 5. 权重敏感性与 min 审计

- **权重敏感性 = LOW**:W2 vs W3 Spearman ρ = 0.994;暴露率同为 62/63;false LOW 同为 9/21——**结论不依赖权重选择**(重要性标签本身仍是分析师判断);
- **min 审计旗标**:63 旗 / 63 真实关键缺失 / **0 误报**;旗标分布跨 1/2/3 主张拍(27/21/15)无明显数量依赖。**判定:min 适合作为“需人工检查”触发器**(构造性 recall=1.0,分析师覆盖评分是质量上限);**不适合自动拒绝**(NC-D 过度惩罚已在 22.9 记录);
- false LOW:W2/W3 各 9/21(无关键缺失却低于阈值)——即加权分数仍有 ~43% 的假低,支持“min 旗标 + 人工复核”而非“分数自动决策”。

## 6. 判定:**SUPPORTED**(预注册口径:ADR 0.524 ≥ 0.5 ✓ · 84 ≥ 30 ✓ · CCR 提升 0.476→0.984/1.0 ✓ · min 误报 0 ≤ 0.5 ✓)

**A** 向量在真实素材中发现了 33 个标量未暴露的关键缺口 ✓ · **B** CCR 稳定提升 ✓ · **C** min 适合审计旗标 ✓ · **D** 权重主观性对结论影响低(但标签本身是分析师判断)✓ · **E** 值得工程化(offline/shadow 审计能力)✓ · **F** Production Rollout:**不允许**(需生产级 claims 分解能力 + 多评分者验证 + 显式授权)

## 7. 冻结边界

零冻结模块/CV2/Gate/ranking/Assignment/correspondence/baseline/Run 01 母片修改;Stage 22.3 修复与 22.5 结论未触碰;22.8/22.9 工件原样;全部 shadow 结果只写入 `output/stage22_visual_quality/`。

```
STAGE 22.10 = EXPERIMENT COMPLETE · STOP
84 候选 / 27 拍 / 47 主张(33C/12I/2S) · ADR 0.524(33 缺口藏在 scalar HIGH 后) ·
暴露率:scalar 0.476 → mean 0.952 → weighted 0.984 → min 1.0 · 权重敏感性 LOW(ρ 0.994) ·
min 审计旗标 63/63 真 / 0 误报 · CASE_A 33 例目录 · EVALUATOR_LEAKAGE = PRESENT(如实降级) ·
判定 SUPPORTED · Production Rollout 不允许
STOP——等待授权
```
