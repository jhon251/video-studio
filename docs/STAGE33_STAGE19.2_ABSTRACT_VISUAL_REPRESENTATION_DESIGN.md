# Stage 19.2:Abstract Narrative → Visual Representation 中间层设计

> 阶段性质:设计 + 只读诊断。零生产代码/零检索/零渲染/零 Prompt·权重·阈值改动;Stage 18 CLOSED 状态不变。诊断产物:`stage19_experiment/stage19_2_classification.json`(90 拍分类)、`stage19_2_canary.json`(零检索 Canary)、`stage19_2_diagnostic.json`(汇总)。

## 1. 研究问题

当 narration 是"价值定义/共生生态/责任/权力/风险/意义"等抽象命题时,系统如何把它转换成**可承担叙事功能的视觉证据**,而不是无关具体照片或连续 fallback?核心:区分"素材本身质量"与"抽象命题在序列中的**表征功能**"。

## 2. 90 拍抽象度分类(程序化,确定性词表规则)

| 类 | 定义 | 数量 | 备注 |
|---|---|---|---|
| ABSTRACT_PURE | 含抽象概念词且无具体可观察锚点 | **29** | 其中 12 拍 sbq=0.45(grade 垫底)、多扇 worst-window 成员 |
| ABSTRACT_MIXED | 抽象命题 + 具体机制锚点(如"从城市交通到司法判决") | **9** | analogue 首选对象 |
| CONCRETE | 具体可观察命题 | 52 | 现行管线服务良好 |

**关键事实**:29 个 ABSTRACT_PURE 拍中,most worst-window 成员(S03-B02 win60.5、S03-B03 63.1、S21-B02 65.9、S04-B01 71.6、S22-B01 72.2、S27-B03 76.9、S28-B02 77.0)——Stage 19/19.1 的序列病灶与抽象命题高度重合。

## 3. 三种表示策略定义

### 3.1 Literal Evidence
- **适用条件**:narration 本身断言可观察事件/行为(具体主语+动作);
- **evidence core**:直接从 narration 抽取(主体+动作+现场),即 Stage 18 链路原样;
- **focus**:单主体+单动作;
- **query 承担**:该主体+动作的实拍证据;
- **防伪**:CV-2 fit + rel 双门槛;与现行一致。

### 3.2 Real-world Analogue(现实机制证据)
- **适用条件**:narration 抽象,但概念存在**现实对应机制/场景/结果**(如"非人类决策者→交通控制中心/司法系统";"价值定义→人类协商决策现场");
- **evidence core 生成**:narration → 抽取"该命题在现实中由什么机制承载" → 机制场景的单主体+单动作描述;机制链接必须写入 provenance(命题 X ←机制 M← 场景 S);
- **focus**:机制场景(具体、可观察、可拍摄),**概念词不得进入 focus**;
- **query 承担**:机制场景的主体+动作(与 Stage 18 单主体 Query 规则同型);
- **防"名词命中但语义不成立"**:focus 程序化审计 = 必须含具体主语+可观察动作/现场,禁止纯概念词;CV-2 实测为最终门槛(19.1 证明概念词 focus 下具体素材全灭 0.0–0.2,本层 focus 是翻转点);
- **与冻结链对接**:focus 作为 `intent["visual_intent"]` 字符串进入——Gate/CV2 零改动(intent 是数据,Stage 18 已验证)。

### 3.3 Metaphorical / Symbolic Evidence
- **适用条件**:概念存在**规约化视觉隐喻**(文化上稳定的符号关系:天平↔权衡、十字路口↔选择、黎明↔希望、提线木偶↔被操纵、枯萎↔凋零);
- **evidence core / focus**:隐喻载体(vehicles)的单主体呈现;
- **防"无关氛围图"**:三重测试——(a) 规约关系词典命中(隐喻必须是该文化中稳定的符号,不是"看着像");(b) 隐喻载体是画面**主主体**(CV-2 reason 主语核查),不是背景;(c) 载体与命题的语义关系可在一句话内写清并落 provenance。三者缺一 = ATMOSPHERE 降级候选(拒绝);
- **禁止纯装饰**:无关系可述的天空/城市/光斑一律不入此策略。

### 3.4 HONEST_NEUTRAL(中性画面)
- **适用条件**:概念无现实机制锚点、无规约隐喻,或任何转换都会制造伪对应;
- **定位**:一等合法结果,不是失败;宁要诚实中性,不要伪对应;
- 与现行 fallback 的区别:fallback 是"池空后的被动填充",HONEST_NEUTRAL 是"表征层判定后主动声明",带决策 provenance。

## 4. 10 个最典型抽象 narration 与策略指派

| # | Beat | narration(摘) | 概念 | 策略 | 依据 |
|---|---|---|---|---|---|
| 1 | S03-B02 | 颠覆不在失业率,而在价值定义 | 价值定义 | **REAL_WORLD_ANALOGUE** | 机制=人类协商决策;Canary:Garner@analogue focus=**0.78 USABLE**(已持有素材!) |
| 2 | S03-B03 | 存在意义从"做事"转向"定义何为值得" | 意义/值得 | METAPHORICAL(天平/权衡)→ 否则 HONEST_NEUTRAL | 规约隐喻存在;未持有,需未来授权 |
| 3 | S21-B02 | 人类定义价值,AGI 执行优化,共生生态 | 共生 | **METAPHORICAL(structural)**:人机并排各司其职 | Canary:LabCoat analogue focus=0.35 CU(边缘合格;结构对应"共生") |
| 4 | S04-B01 | 争夺对"美好生活"的解释权 | 解释权 | **HONEST_NEUTRAL** | 无机制/无规约隐喻;强行=伪对应(Canary 同族全败) |
| 5 | S22-B01 | 共生并非乌托邦 | 乌托邦否定 | HONEST_NEUTRAL(短过渡命题) | 弱断言,中性画面即诚实 |
| 6 | S27-B03 | 创造力是否会在依赖中凋零 | 凋零 | METAPHORICAL(枯萎)→ 未持有 → **当前 HONEST_NEUTRAL** | 规约隐喻存在但需新检索 |
| 7 | S28-B01 | 首个"非人类"决策者——城市交通到司法判决 | 决策者 | **REAL_WORLD_ANALOGUE** | 叙述自带机制锚点;现素材(control room 0.65)已是正确 analogue ✓ 在用成功案例 |
| 8 | S28-B02 | 算法逻辑取代直觉判断,而"责任"二字 | 责任 | **HONEST_NEUTRAL** | Canary 双路皆败(0.3/0.3);责任无诚实视觉 |
| 9 | S10-B01 | 权力的天平将倾斜 | 权力/天平 | METAPHORICAL(天平) | 规约隐喻,需未来授权检索 |
| 10 | S17-B01 | 自由选择是否只是幻觉? | 自由意志 | METAPHORICAL(提线木偶)→ 否则 HONEST_NEUTRAL | 规约隐喻存在;未持有 |

**在档成功佐证**:S13-B02(叙述"重新审视自由、公平与意义"=抽象)在 18.1 用 analogue focus"人群围坐讨论"得 **0.90 USABLE**——抽象命题+机制场景 focus 的完整成功先例,已在案。

## 5. Representation Decision Policy(决策次序,程序化可审计)

```
对每个 ABSTRACT_PURE/MIXED 拍:
 1. narration 含具体机制锚点?      → REAL_WORLD_ANALOGUE(锚点场景=focus)
 2. 存在规约化隐喻(词典+主主体测试)? → METAPHORICAL(载体=focus)
 3. 已持有素材能通过目标拍冻结 CV-2? → 采用(SBQ 不得低于现状)
 4. 以上皆否                        → HONEST_NEUTRAL(记录原因)
```
- **不以"必须找到素材"为目标**:第 4 步是合法出口;
- **禁止伪对应**:focus 程序化审计(具体主语+可观察动作,概念词禁入);Canary 反例已证明"抽象视觉表达"式 focus 虽可刷高 fit(0.95)但不可审计、制造伪对应,策略上明令禁止;
- **抽象概念不得同名图片充数**:概念词检索路径封死;
- **每拍决策记录**:narration → 概念 → 策略 → focus → (测量) → 原因,全量 provenance。

**降级的程序化控制(核心问题的回答)**:直接证据 → 现实机制证据/视觉隐喻的"降级"是**逐拍显式决策**,不是隐式退化:每拍必须携带四类表征状态之一(LITERAL/ANALOGUE/METAPHORICAL/HONEST_NEUTRAL)+ 决策依据;evidence_type 枚举扩展(ANALOGUE/METAPHORICAL),SBQ 仍走同一冻结 CV-2 门槛——**降级改变的是证据类型,不放宽任何质量判定,不改变 correspondence 记账**。无状态拍(既非 literal 又未声明 neutral)即审计违规。

## 6. 零检索 Canary(已持有素材 × 两类 focus,冻结 vision_call)

| Beat | 候选(已持有未指派) | 19.1 抽象 intent 下 | analogue focus(本层生成) | 概念词 focus |
|---|---|---|---|---|
| S03-B02 | Garner(0.90@S13-B02) | 0.0 NU | **0.78 USABLE** ✅ | 0.1 NU |
| S21-B02 | LabCoat(0.75@S34-B01) | 0.2 NU | 0.35 CU(边缘) | 0.95 USABLE(伪对应通道,禁用) |
| S28-B02 | CERN(0.95@S08-B03) | 0.0 NU | 0.3 NU | 0.3 NU → **HONEST_NEUTRAL** |

**结论**:focus 生成方式(而非新素材)是抽象拍的翻转变量;2/3 已持有素材在 analogue focus 下转为合格——**W07 的 S03-B02 因此重新获得合规修复路径**(0.78 ≥ 现状 0.45,SBQ 不降)。

## 7. 五问评估

**A. 中间层能否解决"抽象叙事→fallback"?** 能解决其可解部分:焦点生成(数据层)使已持有素材在抽象拍变为合法可用(S03-B02 实证);无机制锚点、无规约隐喻的概念(责任/解释权)转入 HONEST_NEUTRAL——这是**诚实收敛**而非失败。fallback 病灶从"被动填充"变为"主动声明的表征决策"。

**B. 是否需要"抽象 beat 专用检索"?与 Stage 18 CLOSED 的边界?** 需要与否取决于策略分布:本次 10 典型中 4 拍的所需隐喻/analogue 素材未持有(天平/枯萎/木偶/协商决策)。边界区别:Stage 18 关闭的是**既有 intent 数据下的 Query/Retrieval 优化**;本层产生的是**新表征类型(ANALOGUE/METAPHORICAL)引出的新证据需求**——不是重启旧线,而是新数据层的合法下游。但同理:无显式授权不得执行;且授权应限定"仅 ABSTRACT 拍、仅规约隐喻/机制场景 query、同源"。

**C. 若允许新检索,最小实验对象?** 仅 S03 块(S03-B02/B03/S04-B01,最差窗口群)+ S10-B01/S27-B03 的规约隐喻载体(天平/枯萎)——5 拍以内,单主体 query,走完整冻结链。

**D. 无需新检索的 Canary?** 已完成(§6):已持有素材 × 本层 focus,2/3 翻转,另附 S13-B02 在档成功案例(0.90)。

**E. 是否值得进入 19.3?** 值得,且最小实验已经明确:以 S03-B02 为单点 Canary → 若目标拍判定保持合格(SBQ 0.78 ≥ 0.45),将 19.1 的 W07 窗口重指派在 analogue focus 下重测(预期 S03-B02←Garner 合规),SQS 复算 → 达 +10 则渲染 W07 局部测试版。全程零生产改动、同源、冻结链原样。

## 8. 产物与合规

- 本设计文档;`stage19_2_classification.json`(90 拍)、`stage19_2_canary.json`(3 组双 focus 实测)、`stage19_2_diagnostic.json`(汇总);
- 零生产代码 / 零检索 / 零渲染 / 零 Prompt·权重·阈值改动;Stage 18 CLOSED 未动。

```
STAGE19.2 = PASS · STOP
90 拍分类:ABSTRACT_PURE 29 / MIXED 9 / CONCRETE 52 · 三策略+HONEST_NEUTRAL 完整定义 · 10 典型拍策略指派(3 analogue/3 metaphorical-conditional/4 honest-neutral) · 零检索 Canary 2/3 翻转(Garner@S03-B02 0.0→0.78 USABLE) · 降级=显式四态决策非隐式退化 · 19.3 最小实验:S03-B02 单点 Canary→W07 重测(零新检索即可起步)
STOP——等待下一步授权
```
