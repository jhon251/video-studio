# Stage 3.3 CV-2 实验协议 Amendment v2（Strict HN 门槛修订）

> 状态：**协议修订（只改文档/协议，未运行 A/B/C，未改生产代码）。**
> 本文档是 amendment，不覆盖原预注册协议；原协议保留于 `STAGE33_CV2_MATERIAL_SUPPLY_STRESS_TEST.md` §四/§五/§十，本文档记录修改理由、证据与时间戳，构成 audit trail。

---

## 一、版本与时间戳

| 项 | 值 |
|---|---|
| 协议版本 | CV-2 Experiment Protocol **v2**（amendment 于 v1 之后） |
| v1（原预注册） | `STAGE33_CV2_MATERIAL_SUPPLY_STRESS_TEST.md`（成功线：Top-5 usability ≥60% ∧ rights=0 ∧ SP-retention ≥80%；HN≥10 作为标签集最低量） |
| 修订时间 | 2026-08-31（本次） |
| 修订性质 | 取消 Strict HN≥10 作为**实验运行前置门槛**，改为**测试覆盖度/置信度指标**；不降低任何结果判定阈值 |
| 修订授权 | 人工（用户）明确裁决，方案④ |

---

## 二、修改理由（必须如实记录，非为"更容易 PASS"）

经过 **73 条人工标注**（59 自然候选 + 14 定向构造候选）后：

1. **严格 HN 只有 2 个**（定义不变：`visual_usability=NOT_USABLE ∧ semantic_relevance=HIGH`）；
2. 定向构造已覆盖预注册 9 类失败模式（人物剧照/油画/人物照片/古书扫描/主体错误/构图不适合/风格冲突/图表用于非图表镜/字面陷阱），每类 1–2 个，仍只产出 2 个严格 HN；
3. 结论：在人工判定口径下，"语义 HIGH 且视觉 NOT_USABLE"本身就是**稀有组合**——大量"看起来像陷阱"的素材在人工观看后被判为 B=MEDIUM/LOW（语义不直接对应）或 A=CONDITIONALLY_USABLE（可用但需处理），而非严格 HN；
4. **继续人为扩大 HN 样本的边际收益不足**，且可能引入**分布偏移**（构造集过度代表陷阱类型，使 HN 下沉率虚高/失真）；
5. 因此将 HN 从"能否运行实验"的硬门槛改为"测试覆盖度/置信度指标"——这是对**测量现实**的承认，不是放松 PASS 标准。**HN 的 suppression/ranking 结果仍作为探索性结果单独报告，不设硬 PASS 阈值。**

**明确定义不变**：Strict HN = `visual_usability = NOT_USABLE` **AND** `semantic_relevance = HIGH`。两者缺一不可。

---

## 三、修改前后门槛差异（audit trail）

| 项 | v1（原预注册） | v2（本次修订） |
|---|---|---|
| SP 最低量 | ≥20，冻结前置 | **不变**（≥20，冻结前置） |
| SN 最低量 | ≥20，冻结前置 | **不变**（≥20，冻结前置） |
| Gold Standard 全部候选人工标注 | （隐含） | **明确为冻结前置** |
| Strict HN 最低量 | **≥10，冻结前置（门槛）** | **取消门槛；改为"测试覆盖度/置信度指标"，如实报告** |
| Strict HN 结果 | 参与 hard-negative sink 指标 | **探索性结果，不设硬 PASS 阈值** |
| 成功线（Gate） | B 组 Top-5≥60% ∧ rights=0 ∧ SP-retention≥80% | **结果判定阈值不变** |
| HN 报告方式 | 单一口径 | **分 natural / constructed / historical 三类分别报告，禁止混成一个数字** |

---

## 四、实验集正式拆分（v2）

| 集 | 数量 | 说明 |
|---|---|---|
| A. Strong Positive | 24 | 冻结前置，SP-retention 指标样本 |
| B. Strong Negative | 24 | 冻结前置，SN-sink 指标样本 |
| C. Strict Hard Negative | **2** | 探索性样本（小样本，如实标注） |
| D. Historical Failure Regression Set | 3 | S03×M-S03-162、S12×M-S12-607、S19×M-S19-954（人工实际标签，非 HN 伪装） |
| E. Ordinary / 其他 | 其余 | 中间态 |

---

## 五、重新定义的实验评价（v2）

| Gate | 内容 | 阈值 |
|---|---|---|
| **Gate A** | 供给存在性、候选覆盖率（20 镜有候选）、rights（应为 0）、下载可靠性 | 报告，不设硬 PASS（作为供给层事实证据） |
| **Gate B** | Strong Positive retention | **≥80%（目标，沿用预注册）** |
| **Gate C** | Strict HN + Historical Failure 的视觉陷阱 suppression/ranking | **探索性结果，不设硬 PASS 阈值；分 natural/constructed/historical 分别报告** |
| 结果判定 | B 达标→SUPPLY_IS_PRIMARY_BOTTLENECK；B 不+C 达标→SUPPLY_PLUS_VISUAL_UNDERSTANDING；B/C 均不→讨论；证据不足→INCONCLUSIVE | 沿用 §五/§十 判定树 |

---

## 六、Strict HN = 2 完整列表

1. `S12 : 1899_Cross_Hauling_the_Nets_Tel_Aviv_Museum_of_Art_anagoria.jpg`（渔夫拉网油画；constructed_hn_candidate）— `NOT_USABLE / HIGH`
2. `S05 : The_optical_feedback_loop_driving_colourful_coral_bleaching.jpg`（白化机制科研示意图；constructed_hn_candidate）— `NOT_USABLE / HIGH`

（均来自构造集；自然集 59 条中严格 HN = 0。）

---

## 七、Historical Failure Regression Set = 3 完整列表

1. `S03 × M-S03-162`（1957 电影剧照）— 人工实际标签：`NOT_USABLE / LOW`（**非严格 HN**，B=LOW）
2. `S12 × M-S12-607`（渔民油画）— 人工实际标签：`USABLE / MEDIUM`（**非严格 HN**，人工判定可用，A=USABLE）
3. `S19 × M-S19-954`（沙滩孩子照片）— 人工实际标签：`NOT_USABLE / MEDIUM`（**非严格 HN**，B=MEDIUM）

**回归集定义**：无论其 A/B 为何，这 3 个 (shot, material) 对必须**永远保留**在测试集，且其 ranking/suppression 结果单独报告。它们衡量的是"历史失败案例能否被排低/过滤"，不代表它们满足严格 HN 定义。

---

## 八、为什么现在可以进入 A/B/C（v2 冻结前置已满足）

- SP = 24 ≥ 20 ✅
- SN = 24 ≥ 20 ✅
- Gold Standard 73 条**全部人工标注完成** ✅（59 自然 + 14 构造，无任何 null 判断字段）
- Strict HN 不再作为运行前置门槛 ✅（v2 修订）
- 标签未冻结之前不得运行——需人工在下一步明确授权冻结 + 运行

---

## 九、标签污染检查结论

- **无任何已有人工标签被修改**（73 条全部为人工原答；`label_role` 用户直标 + 我仅做定义推导对照，未改用户值）；
- **无** LOW/MEDIUM 被提升为 HIGH；
- **无** CONDITIONALLY_USABLE 被改为 NOT_USABLE；
- **无** 为凑数量追加候选（14 个构造候选为预注册 9 类覆盖，机械选取，标签由人工冻结）；
- **无** 把历史失败案例伪装成 Strict HN（§七已如实标注其 A/B）；
- 未改生产代码、V3 plan、P1/3.2b/3.1.4 baseline。

---

## 十、audit trail 保留声明

- 原预注册协议 **未被覆盖/删除**，仍保留于 `STAGE33_CV2_MATERIAL_SUPPLY_STRESS_TEST.md`；
- 本文档作为 **amendment**，以 version 递增方式记录（v1 → v2）；
- 修改理由、证据（73 条标注 + 定向构造覆盖 9 类 + 严格 HN=2）、时间戳均已记录。

**本轮 STOP。下一步由人工授权"冻结 Gold Standard + 运行正式 A/B/C"，本轮不运行。**
