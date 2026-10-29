# Stage 33 — STAGE 22.6: RC3 Semantic Family Budget Experiment

> **性质**:离线模拟实验,零生产修改。只用 Run 01 指派 + 生产池 + 冻结 CV2 判定;无新检索、无 CV2 调用、无阈值改动。
> 预注册先于模拟:`output/stage22_visual_quality/stage22_6_preregistration.json`
> 机器可读:`output/stage22_visual_quality/stage22_6_family_budget_experiment.json`(模拟:`exp226_simulation.json`)

## 1. 实验设置

**Group A** = Run 01 现状指派。**Group B** = 在其上加族级预算约束:滑动窗口 10 拍、每族 ≤3 槽;超限时只从**该拍自己的生产池**中改选(rank 不劣于现任、relevance≠LOW、族在预算内);无替代则豁免。不触碰 Intent/Query/Retrieval/Gate/V1/CV2。

族分类:标题 token 分类器(与 EXP-21.2b 同族方法)。Run 01 采用族普查:OTHER 35 · LAB_MEDICAL 19 · PERSON_WEARING_VR 18 · BRAIN_NEURO 8 · HANDS_SCREEN 6。

## 2. A/B 结果

| 指标 | A 现状 | B 预算 | Δ |
|---|---|---|---|
| F1 同族同功能重复事件 | 9 | **5** | **−44%** |
| F0 同资产同功能 | 0 | 0 | = |
| 最长同族连跑 | 7 | **5** | −2 |
| 窗口违规 | 73 | 65 | −8 |
| Correspondence | 99 | **99** | **0** |
| USABLE/HIGH 采纳 | 85 | **85** | **0** |
| LOW 采纳 | 0 | 0 | = |
| 相邻同素材 | 0 | 0 | = |
| 交换次数 | — | 10 | — |

## 3. 信息增益逐条审查(10 次交换,全保留)

- **POSITIVE 2**:#6 S17-B01 眼科无关照→手术内窥镜照(贴近“电极放硬脑膜外”);#10 S04B-B01 通用 VR 玩家→**Holodance 节奏游戏实拍**(直接证据“从节奏光剑到健身应用”);
- **NEGATIVE 2**:#7 S18-B01 EEG 头带(切题)→临床论文图(错位,预算压力所致);#3 S07-B02 1990s Virtuality 街机柜(“体积价格进不了家庭”的更好证据)→普通街机儿童照(历史具体性损失);
- **NEUTRAL 6**:同族内换图(chip→chip、arcade→arcade、VR 用户→VR 用户),信息零增量。

## 4. 判定:**PARTIALLY_SUPPORTED**(预注册标准间隙如实披露)

- 达标:F1 −44% ✓ · 最长连跑不增 ✓ · Correspondence 99→99 ✓ · 证据质量 85→85 ✓ · LOW 0 ✓;
- 未达标:预注册 SUPPORTED 要求**信息增益零降级**——实际 2 降 2 升 6 中性(净中性);
- **标准间隙披露**:预注册未定义“净中性”桶。疲劳/质量侧全部达标、信息增益非下降,故诚实落位 PARTIALLY_SUPPORTED(而非 SUPPORTED 或 NOT_SUPPORTED)。

## 5. 四个负面发现(决定 RC3 的真实形态)

1. **N1 池深是预算的先决条件**:73 个违规拍只有 10 个能换——多数拍自己的池里没有异族合格候选。**族级预算修不了池覆盖问题(RC2 依赖)**;
2. **N2 粗分类稀释预算**:OTHER 桶 35 拍吸收了大量重复,违规只降 73→65——**分类学质量是预算有效性的前提**;
3. **N3 分类器误归箱造成坏交换**(Braille Glove 被记 OTHER;1990s 街机柜被记 OTHER);
4. **N4 族预算 ≠ 信息增益**:10 次交换中 2 次是同观感族内换图,零信息增量——**F2/F3 角色变化感知比族计数更重要**。

## 6. 反例测试(按预注册保留)

- **Case 1 保留**:BRAIN_NEURO 三拍(S16 植入/S18 fMRI/S28 显微)各证不同主张,预算未强制替换 ✓;
- **Case 2 确认**:chip→chip、arcade→arcade——“形式不同、信息相同”被正确识别为零增益 ✓;
- **Case 3**:Run 01 无 F0 事件(R1 时代池结构不同),无需保留场景,已如实记录。

## 7. RC3 状态更新与建议

**RC3 维持 #3,但补救方案被实验重定义**:单纯族预算不足——需要 (a) 更细的族分类学(拆 OTHER),(b) 更深的池(RC2 联动),(c) F2/F3 角色变化感知的交换目标。**不建议现在采纳朴素族预算**(2 个负交换证明无角色感知的预算不安全)。

优先序不变:RC1 intent typing/routing(EXP-22.1 修正版)+ 实体类维度进 EQS → 然后 RC3 工程化。

## 8. 冻结边界

生产 Assignment 未修改(模拟只写 `exp226_simulation.json`);零冻结/零阈值/零 baseline 改动;Run 01 母片未动。

```
STAGE 22.6 = EXPERIMENT COMPLETE · STOP
判定 PARTIALLY_SUPPORTED(F1 −44% / 最长连跑 7→5 / corr 与 USABLE-HIGH 不变 / 信息增益净中性) ·
负面发现 4 条(池深前置 / OTHER 稀释 / 分类噪声 / 预算≠增益) · 反例三案按预注册处理 ·
朴素族预算不建议进生产 · RC3 维持 #3,补救重定义
STOP——不自行进入下一阶段
```
