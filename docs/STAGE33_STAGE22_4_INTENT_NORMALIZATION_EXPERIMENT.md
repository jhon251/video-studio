# Stage 33 — STAGE 22.4: EXP-22.1 Intent Normalization Controlled Experiment

> **性质**:受控研究实验,零生产修改。预注册口径先于判定落盘(`exp221_preregistered.json`),失败案例全保留。
> **控制**:narration/beat 不变;下游 = R1 修复后完整执行 harness;Gate/V1/CV2/评分/阈值全部冻结原样。
> 机器可读:`output/stage22_visual_quality/stage22_4_intent_experiment.json`(原始数据:`exp221/`)

## 1. 实验设计

6 类 × 2 臂(CURRENT = 生产 query + 生产池 + 冻结判定;EO = 证据导向 query,每类 top-3 下载 + 冻结 CV2)。实际调用:18 查询 / 53 候选 / 18 下载 / **18 次 CV2**(在授权预算内)。

## 2. 逐类结果(预注册指标 EBCR = USABLE/CU 且 relevance=HIGH 且非 CG/abstract)

| 类型 | A EBCR | EO EBCR | Δ | 判定 |
|---|---|---|---|---|
| T1 什么时候实现 | 0.75(钟表) | **0.00** | −0.75 | **A_BETTER** |
| T2 五层技术 | 0.33 | **1.00** | +0.67 | **EO_BETTER** |
| T3 推测而非预测 | 0.67 | 0.67 | 0 | TIE |
| T4 技术瓶颈 | 0.80 | **0.00** | −0.80 | **A_BETTER** |
| T5 抽象概念 | 0.00 | **0.33** | +0.33 | **EO_BETTER** |
| T6 读 vs 写 | 0.67 | 0.33 | −0.33 | A_BETTER |

**聚合:EBCR A 0.536 vs EO 0.389(Δ −0.147);EO 达标胜出仅 2/6。**

## 3. 预注册分类:**NOT_SUPPORTED**

按事先固定的规则(需 ≥4/6 类型胜出且聚合 Δ ≥ +0.10),**evidence-oriented intent 作为普适规范化规则不被支持**。不强行升级。

## 4. 但实验揭示了三个更重要的结构事实(全失败案例保留)

1. **T1/T4 = 结构性无证据**:“三种时间尺度”(TRL 图)与“微电极阵列特写”在免费图库中**不存在**——EO 查询返回商业计划图/抽象 LED,全部 NOT_USABLE。对这类 narration,**任何 intent 措辞都造不出证据**;正确终态是 Honest Neutral 或 EXP-22.5 可视化。
2. **EO 的两处真实胜利是域特定的**:T2 `brain computer interface laboratory` 找到 **DARPA SyNAPSE 芯片板 + 神经工程实验室**(真实 BCI 硬件/现场);T5 `removing VR headset` 找到**摘下头显的转折瞬间**(USABLE/HIGH)。→ 证据导向措辞只在“真实研究场景/真实转折时刻”类 intent 上有效。
3. **CV2 意图条件化噪声(新发现)**:同一张实验鼠照片,Run 01 intent 下 CU/M 0.62,EXP-22.1 intent 下 **USABLE/HIGH 0.95**;“玻璃瓷砖抽象几何”在“微电极特写”意图下获 **USABLE/HIGH 0.85**。冻结 rubric **没有实体类维度**——intent 预设可以祝福 generic/CG 图像。这强化 RC1(下游放大 intent,包括其错误),并为 Stage 21 EQS 设计提供一个新输入(实体类维度),**不是现在调阈值**。

## 5. 对 RC1 的最终修正

- **朴素形式("把 intent 改成 evidence-oriented 就会变好"):NOT_SUPPORTED**;
- **精炼形式:SUPPORTED**——主导失败是 meta/定量/结构型 narration **根本没有摄影证据**;生产设计答案是 **intent TYPING + 路由**(meta/定量 → Honest Neutral 或可视化;evidence 型 → 证据导向措辞),而不是一刀切改措辞;
- **RC1 排名维持 #1,但补救方案被重新定义**。

## 6. 失败案例(全保留,含机制)

- T1:TRL chart → 军队工艺照/商业计划图(全 NOT_USABLE);
- T4:microelectrode closeup → 抽象 LED/热沉;玻璃瓷砖获 CV2 USABLE/HIGH(假阳性);
- T6:`BrainGate electrode array` 在 Pexels 语义误命中(心脏检查照片 USABLE/HIGH);真实 BrainGate 图在普通 query `brain implant` 下(22.1 已证)——**entity query 在此不优于普通 query**;
- T2 内部:实验室鼠 USABLE/HIGH 为 CV2 假阳性。

## 7. Production 建议

1. **不采纳**一刀切的 evidence-oriented intent 改写(预注册标准失败);
2. **采纳方向(需授权)**:intent **TYPING**——narration 先分类(evidence/meta/structure),meta+定量型路由到 Honest Neutral 或可视化,evidence 型才做证据导向措辞;
3. CV2 意图条件化噪声记入 Stage 21 EQS 设计输入(实体类维度),现在不动任何阈值。

## 8. 冻结边界

零冻结模块/零阈值/零生产修改;Run 01 母片未动;全部数据在 `output/stage22_visual_quality/exp221/` 与预注册文件。

```
STAGE 22.4 = EXPERIMENT COMPLETE · STOP
分类 NOT_SUPPORTED(预注册口径,2/6 胜,聚合 Δ −0.147) · 域条件效应确认(真实场景/转折时刻 intent 有效) ·
结构性无证据类型确认(T1/T4) · CV2 意图条件化噪声新发现(鼠 0.62→0.95;玻璃瓷砖 0.85) ·
RC1 维持 #1,补救从"改措辞"修正为"分类+路由" · 可视化/HN 是 meta 型拍的正解
STOP——不自行进入 Stage 22.5
```
