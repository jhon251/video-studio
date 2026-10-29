# Stage 33 — STAGE 22: Visual Evidence Bottleneck Diagnostic

> **性质**:只读诊断 / 研究。零冻结修改 · 零生产修改 · 零渲染 · 零 baseline 改动;Entity Query 对照实验严格限于诊断范围,结果不写入生产。
> **对象**:Production Run 01 母片(`output/prod01/render/final_long.mp4`,101 拍)。
> 审片分数(5/10 等)保持 `OBSERVED_BY_REVIEWER` 标签,不自动升级为工程事实。
> 机器可读:`output/stage22_visual_quality/stage22_diagnostic.json`(证据链:`_chain.json` / `_grades.json` / `entity_query_test/`)

## 1. 核心研究问题与一句话答案

> **为什么具备完整链路(Intent → Query → Retrieval → Gate → V1 → CV2 → Assignment)的系统,仍产出大量低信息 generic 画面?**

**答:因为链条的每一环都"忠实执行"了上游给的东西——generic 的最大来源不是链路失灵,而是 Visual Intent 层为元陈述/结构信息型 narration 生成了"cliché 或 CG 型"意图(时钟、白板、大脑模型、抽象渲染),下游检索和判定认真地执行了坏意图。** 次因是检索池的两个工程/结构性问题,第三是族级单调无预算。

## 2. 全片五级分级(诊断口径,analyst 判定)

| 级 | 定义 | 拍数 |
|---|---|---|
| A Strong Evidence | 真实设备/实验室/科研影像,直接承载口播主张 | **23** |
| B Partial Evidence | 领域正确但不承载具体主张 | 66 |
| C Generic but Relevant | 相关域 stock(人+VR 头显等) | 8 |
| D Generic Atmosphere | 填充型 | 4 |
| E Mismatch Risk | 0(CV2 闸住了) | 0 |

审片"大量 generic"在**族级镜头**下成立:PERSON_WEARING_VR 族 **18 拍** + LAB_MEDICAL 族 **19 拍** = 37% 的拍来自两个高度相似家族(字节级 0 重复)——这正是 EXP-21.2b 的族级疲劳在 Run 01 的复现。审片的"A→B→A 循环"在字节级被驳回(adjacent=0, multi_use=2),在族级被证实。

## 3. 视觉证据失败链:20 个坏镜头抽样(全量在 JSON)

每个案例回答了九问(narration 说了什么 / intent 是什么 / query 搜了什么 / 池里有没有 / 为什么没用上 / 谁选的 / 哪层失败)。代表性案例:

| 拍 | 分级 | 根因 | 主张 vs 画面 | 失败机制 |
|---|---|---|---|---|
| S27-B01 | D | **RC1 Intent** | "三种时间尺度" → 车站钟特写 | intent 就写了"时钟画面";CV2 判 USABLE/HIGH 0.95 "正确"执行——但钟表不承载时间尺度比较。**VISUALIZATION_OPPORTUNITY** |
| S29-B04 | D | RC1 Intent | "推测非预测"(元陈述)→ 化学白板 | 元陈述天然非视觉;intent 要白板,池里最好的就是白板 |
| S30-B02 | D | **RC2 Pool** | "神经信号个体差异" → 借来的化学白板 | 自身 query(EEG waves)池空(2 候选全 NOT_USABLE);fallback 借用 ≥2 拍外资产 → 叠加语义错位 |
| S33B-B01 | D | RC1+RC2 | "五层阶梯回顾" → 网线 | 回顾拍无独立证据;own 池全 NOT_USABLE;借用网线(为"延迟"拍检索) |
| S16-B01 | C | **RC2 Pool** | "侵入式 BCI 已在人体工作" → 实验鼠 | query 空间正确;免费图库无 Neuralink/BrainGate 植入照片,池内只有牙科植入/脑CT/老鼠 |
| S17-B03 | C | RC2 Pool | "患者脑控轮椅" → 普通轮椅 stock | 真实证据(清华 NEO 患者)不在免费池 |
| S19-B01 | C | RC1 Intent | "Blindsight 视觉假体" → 3D 抽象脑 | intent 指向模型/CG 而非真实假体试验——正是被禁止的类型 |
| S04-B02 | C | RC2 Pool + **截断** | "MR 透视房间" → AR 沙盘 | plan 里有备选 query 但被 harness 截断;Entity B 找到 **ISS 宇航员 HoloLens(NASA 档案,0.95)** |
| S20-B01 | B | RC1 Intent | "每秒十个比特" → 通用芯片特写 | 定量论据无画面对应。**VISUALIZATION_OPPORTUNITY**(对数图) |
| S32-B02 | C | RC2 Pool | "写入感知接口" → AI 抽象画 | 命中禁止的 AI-render 类型;Entity B 找到 **DBS 电极设备(0.95)** |

其余 10 案(S05-B02/S13-B01/S25B-B01/S06-B01/S09-B02/S10-B01/S15-B01/S24-B02/S28-B02/S33B-B02)详见 JSON,含逐拍九问答案。

## 4. 最重要的答案:C/D 拍是"选错了"还是"没有更好的"?

**两种都存在,约 2:1:**

- **池空组(5/12)**:S30-B02、S33B-B01、S16-B01、S17-B03、S25B-B01——池内根本没有合格相关候选。**对这组优化 CV2 排名毫无意义**;
- **Intent 锁定组(7/12)**:S27-B01、S29-B04、S05-B02、S19-B01、S32-B02、S13-B01、S04-B02——池里有(甚至 USABLE/HIGH)候选,但 intent/query 本身指向 stock 类型,选出来的必然是 generic。**对这组优化检索也无效,必须动 intent。**

## 5. Entity Query 假设验证(10 拍对照实验,49 候选,冻结 CV2 判定)

**结论:PARTIALLY_SUPPORTED——B(实体 query)5 胜 / A 3 胜 / 2 平。**

- **有效域**(机构公开过影像):S17-B03 neurofeedback 患者照(0.9)、S04-B02 ISS 宇航员 HoloLens(0.95,NASA 档案)、S32-B02 DBS 电极设备(0.95)、S19-B01 假体使用者(0.78)、S30-B02 EEG 头带特写(0.9);
- **无效域**(专有影像):S16-B01 "Neuralink implant patient" 命中牙科诊所照(伪匹配)——**实体 query 无法突破版权墙**,该类拍只能 Honest Neutral 或获授权媒体素材;
- **边界确认**:S27-B01(钟表 0.95)用 entity chart query 也只到 CU 0.5——证明该拍瓶颈不在检索层,卡在 intent。

## 6. Visualization Opportunity(仅记录,不实现)

全片 **0 图表/时间轴/示意图**;≥10 拍存在明确制图需求:

| 拍 | 需要的可视化 |
|---|---|
| S27-B01 | Near/Medium/Long 三尺度 **timeline** |
| S20-B01/B02 | 神经接口 10bps vs 视觉通路百万级 **对数比较图** |
| S02-B03 + S33B-B01/02/03 | **五层阶梯 diagram**(全片骨架) |
| S18-B02/B03、S18B-B02 | BCI **读出 vs 写入对比图** |
| S28-B02 | 接口带宽阶梯示意 |
| S26-B01 | "进得去/活得像"两半边并列 |

其余 ~90 拍为实证/事件型,**强制图表会降低信息密度**。结论:图表应是特定 narrative type 的可选能力,不是通用 pipeline 步骤。

## 7. Recurring Anchor 假设(仅分析,不实现)

每个自然锚点在 Run 01 只出现 1 次(NEO→S17、Neuralink→S16、HaptX→S11、ACE→S24)。叙事弧(墙→BCI→AI→时间)本可让 2–3 个真实案例各重访 3 次(如 NEO:现状→读vs写→个体差异)。**PARTIALLY_SUPPORTED**:对科技叙事有效且证据可获得;不通用;且必须遵守 EXP-21.2b 教训——anchor 需要"同对象不同深度/不同画面",否则故事连贯会退化成素材重复。

## 8. P0 / P1 / P2 独立评价

| 提案 | 判定 | 理由 |
|---|---|---|
| **P0 FILLER ≤25%** | 诊断 KPI:PARTIALLY_SUPPORTED;硬 Gate:**NOT_SUPPORTED** | 可测但口径差 9 倍(拍级 D=4% vs 族级 37%),须先定义口径;FILLER 定义与 HONEST_NEUTRAL(合法终态)冲突;硬阈值会诱导系统为避 FILLER 采伪对应——违反冻结诚实原则。建议以族级多样性+证据分布做监测,不设硬上限 |
| **P1 Visualization Step** | PARTIALLY_SUPPORTED | 消解最弱一批拍;但主因 RC1 不因此消失;只应作为特定 narrative type 的可选能力,需新授权研究线 |
| **P2 Recurring Anchor** | PARTIALLY_SUPPORTED | 修复"证据集中/不连贯";不修 pool-empty 与 intent 锁定;不通用;有疲劳风险,需与族级预算联动 |

## 9. Root Cause Ranking(最终)

### ROOT CAUSE #1 — INTENT / PRODUCTION DESIGN 层
Visual Intent 层对元陈述/结构/隐喻型 narration 生成 cliché 或 CG 型意图,下游忠实执行。C/D 拍约 **60%** 归于此(7/12 intent-locked)。这是 Narration 问题(部分拍天然非视觉)与 Production Design 问题(无 intent 类型规范)的合成。

### ROOT CAUSE #2 — RETRIEVAL 层
(a) **检索 harness 截断 bug:91/101 拍未执行全部计划 query**(t1 首查 Wikimedia ≥4 结果即 break,t2/t3 三层设计从未运行)——池多样性被工程性削减;(b) 免费图库对专有科研/临床影像的结构性覆盖缺口。C/D 拍约 **40%** 归于此。

### ROOT CAUSE #3 — ASSIGNMENT / PRODUCTION DESIGN 层
无族级多样性预算与 anchor 设计:字节唯一但族级单调(VR-user 18 拍、LAB_MEDICAL 19 拍)放大"generic 印象";fallback borrow 只保距离不保语义。

**分层归属**:RC2 = Retrieval 问题;RC3 = Assignment 问题;RC1 = Narration + Production Design 问题;P1/P2 = Production Design 能力缺口。

## 10. 可验证的下一步实验建议(全部需授权,未执行)

1. **EXP-22.1** Intent 类型规范:meta/structure 型 narration 默认 Honest Neutral 或 visualization,禁 cliché 检索;
2. **EXP-22.2** Entity query 检索层(已证 5/10 增益)+ 修复 query 截断;
3. **EXP-22.3** 族级多样性预算(同族窗口上限,超限 HN/换族);
4. **EXP-22.4** Anchor 试线(NEO+HaptX+ACE 三锚点 × 3 深度,离线 A/B);
5. **EXP-22.5** 可视化试线(先做 5 个必然图表拍,离线评估)。

## 11. 冻结边界

零冻结模块/Gate/CV2/阈值/Gold/correspondence/Production Entry/Final Gate/baseline 修改;Run 01 母片未动;生产检索未动(entity 实验仅写入 `output/stage22_visual_quality/`);Stage 18–21 关闭线未重开。

```
STAGE 22 = DIAGNOSTIC COMPLETE · STOP
101 拍失败链全建 · 20 坏镜头案例(九问逐拍) · C/D 归因 2:1(intent-locked vs pool-empty) ·
Entity Query 实证 5胜3负2平(有效域=机构公开影像;无效域=专有影像) · 族级重复证实(VR 18 + LAB 19) ·
截断 bug 91/101 · 可视化机会 ≥10 拍 · anchor 候选 4 · P0 部分/P1 部分/P2 部分 ·
Root Cause: #1 INTENT(~60%) > #2 RETRIEVAL(~40%) > #3 ASSIGNMENT/族级预算
STOP——不修复,等待授权
```
