# Stage 19.4:Analogue Representation + Correspondence Accounting 探查报告

> 冻结全程:Stage 12–18 生产链、Stage 18 Intent Decoupling、Stage 19 A–E 指标、Gate/V1/CV2、Retrieval/Query、Reuse Policy、**原有 correspondence 记账原样未动**、全部阈值/权重/Gold/Prompt。零新检索;A 态基线校验:除 19.3 已采纳的 S03-B02 外,全部窗口与 Stage 19 基线精确一致(漂移 0.000)。

## 第一部分:W50 / W67 只读探查(Representation Decision Policy 逐拍判决)

| Beat | 现状 | 表征判决 | 动作 | 冲突记录 |
|---|---|---|---|---|
| S21-B01 | CORRESPONDING,robot-arm 协助专业人员(0.85) | **REAL_WORLD_ANALOGUE(已是正确 analogue)** | 不变 | ⚠️ 类标签 CORRESPONDING 但 et=ATMOSPHERE → 表征层标 PSEUDO_RISK(待审计) |
| S21-B02 | FALLBACK,MRI 医疗填充 | ANALOGUE(部分:仅"AGI 执行侧") | 不变 | RobotArm 实测 0.92 USABLE/HIGH,但语义链只覆盖命题一半("共生"的人类侧无画面);且 RobotArm 单一用途与 S27-B03 采纳冲突 → **W50 覆盖受限** |
| S22-B01 | CORRESPONDING,街景 | **HONEST_NEUTRAL** | 不变 | 无已持有候选与命题相关 |
| S27-B03 | FALLBACK,斑马线填充(跨拍重复) | **REAL_WORLD_ANALOGUE(采纳)** | **← RobotArm** | 类保持 FALLBACK 而画面已承担叙事功能 → 原记账低估 |
| S28-B01 | CORRESPONDING,交通控制中心 | REAL_WORLD_ANALOGUE(现素材即正确 analogue) | 不变 | 无(et=INDUSTRY_SITE 一致) |
| S28-B02 | FALLBACK,平板课堂(跨拍重复) | **HONEST_NEUTRAL** | 不变 | 19.2 canary 双 focus 皆败;"责任"无诚实视觉 |

测量(冻结 vision_call,已持有未指派素材,无检索):RobotArm("File:Robot arm operates machine in factory setting.jpg",18.1 S30-B01 胜出、存档未渲染=生产未指派):
- **@S27-B03:fit 0.95 USABLE / rel HIGH** — 语义链完整:创造力在依赖中凋零(命题)← 生产与创作劳动被自动化接管、人类退出现场(机制)← 工厂里机械臂独自操作机器(场景);focus 零概念词;
- @S21-B02:fit 0.92 USABLE / rel HIGH — 但链部分(仅执行侧)+单用途冲突,按"不为提高对应率制造半对应"原则不予采纳,记录为覆盖受限证据;
- Martin guitar(19.1 备注提及 0.90):title/thumburl 未持久化,无 provenance 不可再水合(再获取=新检索,禁止)→ 如实排除。

## 第二部分:Representation-aware Correspondence(平行标注层,不改原记账)

五类标签与判定规则:
1. **LITERAL_CORRESPONDING**:CORRESPONDING 且 et∈{REAL_EVENT, INDUSTRY_SITE}(focus=narration 主体+动作);
2. **ANALOGUE_CORRESPONDING**:存在可审计 `narrative_claim → mechanism → visual_scene` 链 + 目标拍冻结 CV-2 合格 + SBQ 不降;
3. **METAPHORICAL_CORRESPONDING**:19.2 三要素(规约关系、主主体、一句话关系可述)——离线不可全量复核者带 `*` 待审计标记;
4. **HONEST_NEUTRAL**:显式中性声明;**不计 correspondence,也不判 INVALID**;
5. **PSEUDO_CORRESPONDING / PSEUDO_RISK**:声称对应但链不成立(et=ATMOSPHERE 却标 CORRESPONDING、概念词 focus、纯装饰)。

**90 拍全量标注结果**:LITERAL 40 · METAPHORICAL* 10 · ANALOGUE 2(S03-B03 Garner 0.82、S27-B03 RobotArm 0.95)· PSEUDO_RISK 6 · HONEST_NEUTRAL 32。
→ 表征感知对应 **52/90 拍 < 原记账 56/90**:新指标**更严格而非注水**(发现原记账 6 处疑似高估 + 2-3 处低估)。**原 60.86% 原值未动,仍是生产验收数**;Stage 13 的 60% 标准不变。

## 第三部分:W50 / W67 离线 A/B

A = 当前生产表示(含 19.3 已采纳 S03-B02);B = 19.2 Policy(唯一合法变更:S27-B03 ← RobotArm):

| 窗口 | A SQS | B SQS | Δ | 变化 |
|---|---|---|---|---|
| **W67** | **68.9** | **85.7** | **+16.8** | SBQ 0.45→0.95;断链对消除 |
| W66 | 80.7 | 91.7 | +11.0 | 正外溢 |
| W65 | 81.0 | 89.0 | +8.0 | 正外溢 |

门禁:①原 correspondence 未修改 ✅ ②零新 PSEUDO ✅(采纳项链完整可审计)③发现 1 个合法改善(S27-B03)+ W50 覆盖受限证明 ✅ ④SQS +16.8 ≥ +10 且原 correspondence 不降 ✅ ⑤reuse **改善**(multi_use 30→29:斑马线跨拍重复组消除;相邻重复 0)✅ ⑥provenance 全量入档 ✅。**W50 无完整合法 B → 不渲染**(如实记录)。

## W67 局部渲染与验证

- `render_194/window3_B_analogue.mp4`(18.60s,与 A 基线等长,timeline 零改动)——冻结逐拍管线(16.2 motion、composition、字幕烧录成功、shot 音频切片);A 对照:`render_191/window3_A_baseline.mp4`;
- 信号审计:0 黑帧;freeze 2 处 = 16.2 设计内 STATIC 槽(与 A 相同);帧文件 b_f*.jpg 存档供人工复核;
- provenance manifest:`render_194/provenance_manifest.json`。

## 问题五的明确判断

**Representation-aware metric 值得作为未来内部质量指标——但只作平行审计层**:它揭示了原记账的双向偏差(低估:承担叙事功能的 analogue 槽计 0;高估:atmosphere 素材挂对应标签),其五类标签 + 链审计 + CV-2 证据规则可程序化执行;但它不应替代原 60.86% 生产验收数,更不允许据此回调 Stage 13 的 60% 标准(本阶段未做任何此类改动)。

## 产物

本报告;`stage19_4_results.json`(测量 + Part1 判决 + A/B + 门禁 + 90 拍标注);`stage19_4_measurements.json`(冻结判定原始记录);`render_194/`(W67 B 视频 + manifest + 信号审计 + 帧)。

```
STAGE19.4 = PASS · STOP
W67 合法 analogue 改善:RobotArm@S27-B03 0.95 USABLE/HIGH(链完整、零伪对应) · W67 68.9→85.7(+16.8≥+10) · W65/W66 +8.0/+11.0 零回退 · reuse 30→29 改善 · 原 correspondence 60.86% 原值未动 · 表征感知标注 52/90 < 56/90(更严不注水;6 PSEUDO_RISK 待审计、2-3 analogue 被低估) · W50 覆盖受限如实记录(RobotArm 链部分 + 单用途冲突;Martin 无 provenance 排除) · W67 B 版已渲染并过信号审计 · 建议表征感知指标仅作平行审计层,Stage 13 60% 标准不变
STOP——等待下一步授权
```
