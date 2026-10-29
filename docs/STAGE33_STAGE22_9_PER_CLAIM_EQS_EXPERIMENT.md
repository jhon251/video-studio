# Stage 33 — STAGE 22.9: Per-Claim Evidence Quality Vector Experiment

> **性质**:研究实验(分析师评分,离线),零生产修改。预注册先于评分(`stage22_9_preregistration.json`)。
> 机器可读:`output/stage22_visual_quality/stage22_9_per_claim_eqs_experiment.json`(主张向量:`stage22_9_claim_vectors.json`,13 拍 / 36 原子主张)

## 1. 实验设计

13 个 Run 01 真实拍(覆盖 A–L 全部类别)+ 4 个研究构造配对案例(基于真实资产,如实披露)。每拍分解为原子主张向量(claim_id / text / type / importance / coverage / evidence_quality / specificity / information_gain / narrative_function;**claim 只从 narration 分解,intent 措辞绝不参与**)。对比三种表示:**V1 标量 mean**(22.8 口径)、**V2 完整向量**、**V3 聚合(mean / min / importance-weighted)**。

## 2. 核心结果

### H1(scalar 均值掩盖局部失败):CONFIRMED

| 聚合 | Critical Claim Recall(关键主张缺失被暴露) |
|---|---|
| mean | 8/9 |
| **min** | **9/9** |
| importance-weighted | 8/9 |

**旗舰案例 = DBS/N1 复核(S18-B02,生产实拍)**:6 条原子主张中,F1 设备身份 1.0、F2 人体植入 1.0、F4 写入侧硬件 1.0、F3 机制 0.5、F6 不对称 0.5——**而 F5“完整感觉写入仍无可验证方案”(importance 1.0,正是这句 narration 的核心点)= 0.0**。mean = 0.667、weighted = 0.633,都读作“中等质量”;**只有 min = 0.0 或向量暴露 F5 完全未被证明**。

### SCALAR_INFORMATION_LOSS:SUPPORTED

配对构造(Case1 设备强+机制缺失 vs Case2 设备缺失+机制强,基于真实 BrainGate 照片与 VIZ-4 图):**mean 0.500 vs 0.475 几乎相同、min 都是 0.05——只有向量记录了“哪个主张未被证明”**。

## 3. 负面控制(6 项全按预期)

NC-A 全强:三者皆高,无误报 ✓;NC-B 全弱:三者皆低,无膨胀 ✓;**NC-C 关键缺失+次强:mean 0.63 掩盖 / min、weighted 暴露**(关键判别测试)✓;**NC-D 次要缺失+关键强:min 过度惩罚(0.05),weighted 正确**——min 是“审计安全但作分数不安全”✓;NC-E 主张数偏差:min 对长主张列表更苛刻,mean 稳定 ✓;NC-F 意图措辞变更:全部聚合不变(claim-centered 继承)✓。

## 4. DBS/N1 复核结论(授权要求)

0.57 **确系真实 mixed-claim dilution**:4 条已覆盖主张(其中两条 1.0)平均掉了关键主张 F5 = 0.0。被覆盖:设备身份/人体使用/写入侧硬件存在;未覆盖:**F5 完整感觉写入(关键)+ F3 机制细节**。per-claim 向量更符合纪录片证据审计——它回答的是“**哪句主张没被证明**”,而这正是审片的中央问题。

## 5. 判定与四个子答案

**分类:SUPPORTED**(H1 实锤 + CCR(min) 9/9 > mean 8/9 + 负控全符合)

1. **H1 成立**;
2. **scalar EQS 存在实际信息损失**(配对实证 + DBS 实拍实证);
3. **per-claim vector 具有诊断价值**(唯一保留“哪个主张缺失”的表示);
4. **值得进入下一阶段工程化——但仅限 Shadow/Offline Evaluation**;
5. **不允许直接进入 production**(需多评分者验证 + 生产级 claims 分解能力)。

## 6. 限制(全量披露)

单评分者(无信度检验)· 主张分解与重要性权重为分析师判断 · Case1/2 为研究构造(基于真实资产)· min 的过度惩罚风险在真实样本中为 0/0(仅合成 NC-D 证明)· 生成图表为 mockup · **未证明任何真实世界 production uplift**。

## 7. Production 建议

1. 若授权下一阶段:**仅限“Shadow / Offline Evaluation of Per-Claim EQS”**——对新生产候选离线运行主张分解+向量,对比 scalar 的审计价值;
2. Shadow 阶段的聚合指引:同时报告 mean / min / 向量;**min 越线作为审计旗标,绝不做自动拒绝**;
3. min 过度惩罚与主张数偏差需以重要性加权 + 主张数归一化处理后,分数才可用;
4. 不重开 Stage 18–21,不建可视化生产能力(EXP-22.5 结论独立)。

## 8. 冻结边界

零冻结模块/CV2/Gate/V1/Assignment/correspondence/EQS 定义/Stage 22.3 修复/Stage 22.5 结论/baseline/Run 01 母片修改;全部产物在 `output/stage22_visual_quality/`。

```
STAGE 22.9 = EXPERIMENT COMPLETE · STOP
H1 CONFIRMED(DBS 0.57 = 4 覆盖掩盖 F5 关键缺失;mean/weighted 双双 0.63-0.67 掩盖) ·
SCALAR_INFORMATION_LOSS SUPPORTED(0.5 vs 0.475 掩盖"哪个主张缺失") · CCR: min 9/9 > weighted 8/9 = mean 8/9 ·
min 过惩罚风险披露 · 判定 SUPPORTED → 下一阶段仅限 Shadow/Offline Evaluation · 零生产修改
STOP——等待授权
```
