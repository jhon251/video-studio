# RUN 02 失败归因 + 下一阶段实验设计

> **性质**:只读分析 + 实验设计,零生产修改。预注册口径,失败不重写。
> 机器可读:`output/prod02/run02_fail_attribution.json` · `fail_attribution.py`(可复现)

## 1. 三层诊断矩阵

| 层 | 路由 | 拍数 | 摄影对应 | 证据覆盖 | 叙事功能 |
|---|---|---|---|---|---|
| EVIDENCE | 64 | 51 CORRESPONDING + 13 FALLBACK | 51 照片证据 | 51 证明 + 13 缺口 | 51 证明/建立 + 13 填充 |
| VIZ | 11 | 11 VISUALIZATION_EXP | 0 照片 | 11 结构图表 | 11 解释/比较/结构 |
| HN | 26 | 26 HONEST_NEUTRAL | 0 | 0 | 26 诚实留白 |
| **合计** | **101** | **51 photo-corr (50.5%)** | **51+11=62 info-bearing (61.4%)** | — | — |

## 2. 50 个非对应拍归因(逐拍三层)

| 归因 | 拍数 | 层 | 说明 |
|---|---|---|---|
| **结构性诚实(路由正确)** | **21** | HN | 元陈述/问句/否定/推测——不存在摄影可证据主张,HN 是唯一诚实终态 |
| **检索失败(可修复)** | **7** | FALLBACK | 主张可摄影证据化但 query/池未命中:room-scale VR、摘下头显瞬间、动捕、康复机器人、VR 拳击、写入接口、影视动捕 |
| **池覆盖缺口** | **6** | FALLBACK | BCI/神经/植入体:免费图库结构性缺口(BrainGate 在 Run 01 池但未入 Run 02 query) |
| **VIZ 正确路由** | **11** | VIZ | 结构/定量/对比主张 → 可视化是正确形式(VIZ-1..6 已就绪) |
| **可视化可改善的 HN** | **5** | HN→VIZ 候选 | 三座山(3-pillar)、十道坎(list)、一慢一快(comparison)、层数 teaser、拆解 meta |

**关键发现:13 个 FALLBACK 中 7 个属于检索失败(真实照片存在但未命中)——这是最大可行动缺口。6 个属于池覆盖缺口(免费图库结构性不足)——不可通过改 query 修复。**

## 3. Capability Matrix(按 claim 类型)

| Claim 类型 | Photo | Archive | Data/Chart | Diagram/Viz | HN | 缺口 |
|---|---|---|---|---|---|---|
| 真实设备(HW) | ✅ stock 存在 | 有限 | ✗ | ✗ | ✗ | 检索 query 太泛/太窄 |
| 临床/患者 | 隐私限制 | 有限 | ✗ | ✗ | 可能 | 池覆盖:医疗隐私限制 stock |
| 脑/神经解剖 | ✅ stock | 有限 | 有限 | 有限 | ✗ | 轻微 |
| 定量(带宽/数量/价格) | ✗ | ✗ | **✅** | **✅** | ✗ | **能力缺口:图表生成** |
| 结构(阶梯/分类/对比) | ✗ | ✗ | 有限 | **✅** | ✗ | **能力缺口:图示生成** |
| 元/推测/开放问题 | ✗ | ✗ | ✗ | ✗ | **✅** | 无——HN 正确 |
| 时间(何时/十年/一代人) | ✗ | 有限 | 有限 | **✅ timeline** | 可能 | VIZ timeline 或 HN |
| 历史(90s VR/早期 BCI) | ✅ archive | **✅** | ✗ | ✗ | ✗ | 检索:archive query 缺失 |
| 因果(瓶颈/连锁) | ✗ | ✗ | 有限 | **✅** | 可能 | VIZ flow/constraint |

## 4. Root Cause Ranking(最终)

| 排名 | 归因 | 拍数 | 可修复性 |
|---|---|---|---|
| **#1** | **结构性诚实(路由正确)**:37 拍 narration 无摄影可证据主张 | 37(HN 26 + VIZ 11) | 不可修——这是诚实路由的正确行为;VIZ 可覆盖其中 ~11 个结构/定量拍 |
| **#2** | **检索失败(可修复)**:7 个证据拍 query/池未命中真实存在的照片 | 7 | **可通过 entity-specific + archive query 修复** |
| **#3** | **池覆盖缺口**:BCI/临床/专有设备的免费图库结构性不足 | ~6 | 部分可修(archive query);部分不可修(隐私/专有) |

**归因分类**:RC2 = Retrieval 问题 · RC1 = Production Design 问题(intent/routing 正确但需要补可视化能力)· RC3 = Retrieval + 结构性限制。

## 5. 下一实验推荐

### 首选:EXP-A(Evidence Retrieval Optimization)

**为什么比修改 correspondence 更有价值**:EXP-A 针对 7 个已证实的检索失败拍——这些拍的**真实照片确定存在**(room-scale VR、动捕、摘下头显、康复机器人、VR 拳击)但 query 未命中。修复它们可以直接增加 7 个真正的照片证据拍,同时不影响诚实性(不是往池里塞 generic 图)。

**EXP-A 要素**:
- 变量:claim-derived entity-specific query(继承 22.2 已证方案)
- Control:Run 02 现有 query/pool
- Treatment:entity + archive query 变体
- 冻结:Gate/V1/CV2/Assignment 全部不变
- 指标:7 个目标拍获得 USABLE/CU 候选数
- 成本:~30 query + ~50 download + ~50 CV2 ≈ 30 min
- 成功标准:≥5/7 拍获得合格候选

### 配合实验

- **EXP-B**(VIZ routing):5 个 HN→VIZ 候选(三座山/十道坎/一慢一快)——与 EXP-A 并行不冲突
- **EXP-E**(multi-modal EQS):在 EXP-A/B 之后评价总体证据覆盖

## 6. 冻结边界

Run 01 / Run 02 / baseline / 冻结件 / Gate / correspondence / P-2 seal 全部未动。

```
RUN 02 FAIL 归因完成 · 三层矩阵建立 · 50 非对应拍逐拍归因 ·
RC1 结构性诚实 37 拍(路由正确) · RC2 检索失败 7 拍(可修) · RC3 池覆盖 ~6 拍(部分可修) ·
Capability Matrix 按 claim 类型建出 · 5 个实验候选设计完毕 ·
首选 EXP-A(检索优化):7 个可修拍 + 零冻结触碰 + 最低成本
STOP——等待授权
```
