# Stage 19.6:Minimal Analogue Retrieval 实验报告(4 抽象拍)

> 唯一研究问题:**"现有素材库覆盖受限"能否通过极小规模、同源的新检索,为剩余抽象拍找到合法 Analogue?**
> 冻结链原样:two_pass_material.acquire_beat_material(retrieval → pool_precision → Gate head-6 → V1 → CV-2 top-3;pass-1 空时 pexels pass-2);唯一授权变更 = 检索 query/intent(19.2 Analogue 规则:单主体 + 可观察机制,零概念词)。VerdictCache copy 协议(verdict_store_193 → verdict_store_196)。原 correspondence(60.86%)与 60% 标准原值未动。

## 预注册意图与链(先分级,后测量)

| Beat | query(单主体+机制) | visual_focus(零概念词) | 表征 / 链预分级 |
|---|---|---|---|
| S03-B03 | balance scale weights | 天平特写,砝码使一侧倾斜 | METAPHORICAL(规约载体天平=权衡);链:存在意义转向'定义何为值得'←权衡比较←天平砝码场景 → **complete** |
| S04-B01 | public debate speaker podium | 一个人在讲台上面对听众发言 | ANALOGUE;链:争夺'美好生活'解释权←公共表达与辩论←讲台发言场景 → complete |
| S21-B02 | person working with robotic arm | 一名人员与机械臂在同一工位协同工作 | ANALOGUE(双方同框);链:共生←人机分工协作←同工位协作场景 → complete |
| S28-B02 | courtroom judge gavel bench | 法官在法庭内主持庭审 | ANALOGUE;链:算法决策后的'责任'归属←制度化归责:法庭判决←法官庭审场景 → complete |

## 逐拍双锁裁决(链判定 + CV-2 全量记录在 stage19_6_results.json)

| Beat | 候选(CV-2 top-3) | 锁 1:CV-2 | 锁 2:链/约束审计 | 裁决 |
|---|---|---|---|---|
| S03-B03 | Letter balance and weights ×3(0.0/0.2/**0.6 CU**) | 0.6 ≥ floor 0.6(等值,不牺牲) | 链 complete;新 title 无复用冲突 | ✅ **ADOPTED(干净)** |
| S04-B01 | David Dubinsky waves to JFK(**0.7 CU**,仅 1 候选) | 过 | **链不完整**:政治事件照片 ≠ 预注册讲台辩论场景;且政治人物内容敏感 | ❌ 拒绝 → **伪对应风险证据在案** |
| S21-B02 | LabCoat(**0.95 USABLE**;pass-2 pexels 候选全灭于 Gate/V1) | 过 | 该素材已双用(S32-B02+S34-B01),第三用违反 reuse | ❌ 拒绝(reuse) |
| S28-B02 | Tempi Train Crash Trial courtroom(**0.7 CU**;另两候选 0.0) | 0.7 ≥ 0.45 | 链 complete(制度化归责机制真实呈现);**但系真实重大灾难审判 → 内容风险** | ⚠️ **双锁合法,条件采纳**(待编辑审阅,不入 B/渲染;S33-B02 先例) |

**预注册判定:≥1/4 → 实得 1 干净 + 1 条件 = 2/4 → "素材覆盖存在可验证改善" 成立。PSEUDO 采纳 = 0(S04-B01 的 CV-2 高分按预注册记为伪对应风险证据,未采纳)。** 0.9 分位教训延续:本轮再次出现"CV-2 过但链不成立"(S04-B01)——双锁为必要设计,且链分级全部在测量前预注册。

## B 态采纳与受影响窗 A/B(A = 生产 + 19.3 S03-B02 + 19.4 S27-B03)

采纳 S03-B03 ← 天平(SBQ 0.6→0.6 等值;类 CORRESPONDING 不变;reuse 29→29;相邻重复 0):

| 窗口 | A | B | Δ |
|---|---|---|---|
| W06 | 91.7 | 94.7 | **+3.0** |
| W07 | 85.4 | 88.4 | **+3.0** |
| W08 | 80.5 | 76.9 | **−3.6** |

**诚实披露**:W08 −3.6 为机械后果——天平使 et 从 REAL_EVENT→REAL_METAPHOR,冻结 b3(事件多样性)下降;净 +2.4,非目标窗零回退。这是"表征改善 vs 事件多样性"的真实权衡,已完整披露,供未来阶段复核(如 S04-B02 的改善可恢复 b3)。

## 局部渲染(W07 v2)

`render_196/window1_B_v2_analogue.mp4`(19.20s,与 A 等长;Garner + 天平 + 中性填充)——冻结逐拍管线,字幕烧录成功,0 黑帧,freeze 2 处 = 16.2 设计内 STATIC 槽;对照:`render_191/window1_A_baseline.mp4`(A)、`render_193/window1_B_analogue.mp4`(B v1)。provenance manifest + 信号审计 + 帧在 render_196/。

## RA 平行层更新(原记账不动)

S03-B03:LITERAL → **METAPHORICAL_CORRESPONDING**(完整链,三要素通过)。RA 计数:LITERAL 40 / METAPHORICAL 11 / ANALOGUE 2 / PSEUDO_RISK 6 / HONEST_NEUTRAL 31 → **53/90**(原 56/90)。

## 结论

**同源极小检索可以移除部分覆盖受限**:4 拍中 1 拍获干净合法 analogue 并采纳(天平,零质量成本、净 SQS +2.4)、1 拍双锁合法但内容风险待审(法庭)、2 拍被链审计/reuse 诚实拒绝(证据在案)。剩余约束已从"素材稀缺"转移为"链完整性 + 复用 + 编辑审阅"。不自动扩大拍数、不进入 19.7。

## 产物

本报告;`stage19_6_results.json`(预注册意图/链 + 全候选 CV-2/Gate 记录 + 双锁裁决 + A/B + 门禁);`verdict_store_196.json`(copy 协议,链判定入档);`render_196/`(W07 v2 + manifest + 信号审计 + 帧)。

```
STAGE19.6 = PASS · STOP
预注册 ≥1/4 达成(2/4:1 干净采纳 + 1 条件待审) · PSEUDO 采纳=0(1 例 CV-2 0.7 链不完整记为伪对应风险证据) · S03-B03 天平 0.6 CU 等值采纳,链完整(规约隐喻三要素) · W06/W07 +3.0/+3.0,W08 −3.6 诚实披露(et 重分类机械后果,净 +2.4) · reuse 29→29,原 correspondence 60.86% 未动 · S28-B02 法庭双锁合法但内容风险待编辑审阅 · S21-B02 被复用锁拒绝(链又选中双用 LabCoat) · W07 v2 已渲染(0 黑帧) · 覆盖受限部分可移除,剩余约束=链完整性+复用+编辑审阅
STOP——等待下一步授权(不自动进入 19.7)
```
