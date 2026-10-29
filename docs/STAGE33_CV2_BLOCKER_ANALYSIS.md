# Stage 3.3 CV-2 Top-Blocker 人工标注分析报告（路径1）

> 状态：**诊断完成。答案明确：V1 在真实池中压住已标注 USABLE 的未标注候选，13/18 实际是人工确认 USABLE——V2 的 apparent regression 主要是"V1 排对了"，不是 ranking failure，也**不是** VISUAL_SUITABILITY 升级证据。**
> Gold Standard 未修改（integrity 核验：`C70C82D462A82A7D...` 不变）；production 未修改。完成后 **STOP**。

---

## 1. 抽样框与统计纪律

| 项 | 值 |
|---|---|
| 抽样框 | 真实 399 pool，V1 排序下压在"每镜最靠前 labeled USABLE"之前的**未标注**候选 |
| 抽样规则 | 每 shot 取 rank 前 3 个（机械，读标签前固定）；blocker 少则全取 |
| 候选数 | **20**（18 可验证 + 2 缩略图不可见） |
| 镜头数 | 8 个受影响镜（S01/S03/S04/S06/S09/S10/S13/S16）+ 6 镜 0 blocker |
| 标注覆盖率 | 18/20 = **90%**（BK-13/BK-17 因 Commons 429 无法下载，人工标"不可见/排除"） |
| 标签来源 | 全部人工直接回答（label_role_source=user_direct） |
| Blocker 分布 | natural-unlabeled 100%（非 constructed/非 historical） |
| 素材 SHA | 18 个缩略图 SHA 已录于 manifest |
| **Gold Standard 修改** | **NO**（SHA 前后一致） |
| **production 修改** | **NO** |
| 结果 | `output/stage33/cv2/ranking_validation_v2/blocker_analysis.json`（SHA `E061108E...`） |

---

## 2. Case 分类结果（18 条可验证）

| Case | 定义 | 数量 | 占比 |
|---|---|---|---|
| **C2：HIGH + USABLE** | 高语义且视觉可用 | **8**（BK-05/08/09/10/14/15/16/18） | 44% |
| **C3：MED/LOW + USABLE** | 中低语义但视觉可用 | **5**（BK-01/02/03/06/12） | 28% |
| C4：MED/LOW + NOT_USABLE | 中低语义且不可用 | 5（BK-04/07/11/19/20） | 28% |
| **C1：HIGH + NOT_USABLE** | 高语义但不可用 | **0** | 0% |

**总可用 13/18 = 72%；总不可用 5/18 = 28%；严格 C1 = 0。** 用户直标 HARD_NEGATIVE 1 条（BK-19 气候分区示意图，但 B=MEDIUM，不满足严格 C1 定义）。

---

## 3. 八个诊断问题的回答

1. **V1 压住已标注 USABLE 的未标注候选中有多少实际上 USABLE？**
   → **13/18（72%）** 是人工确认 USABLE。

2. **有多少是 NOT_USABLE？**
   → 5/18（28%）：BK-04（论文页）、BK-07（论文页）、BK-11（珠宝执法图）、BK-19（气候分区示意图）、BK-20（FAQ 文档）。

3. **HIGH + NOT_USABLE 的比例是多少？**
   → **0/18（0%）**。没有任何 blocker 同时满足高语义+不可用。

4. **如果大量 blocker 是 USABLE：→ 不得继续宣称 VISUAL_SUITABILITY_BOTTLENECK。**
   → **成立**。13/18 是 USABLE 说明 V1 把真实池中"标题词面匹配更优"的候选排前，**而这些候选人工确认其实是好素材**。V2 的"apparent regression"（Top-1 57%→43%）的主要解释是：**V1 把未标注好素材排到了已标注 USABLE 之前**——这是"排对了"，不是"排序坏了"。

5. **如果大量 blocker 是 HIGH + NOT_USABLE：→ 升级 VISUAL_SUITABILITY。**
   → **不成立**（C1=0）。**VISUAL_SUITABILITY_BOTTLENECK 维持 WEAKLY_SUPPORTED，不升级。**

6. **如果大量 blocker 是 LOW/MEDIUM + USABLE：→ 优先考虑 semantic ranking 的召回表达问题。**
   → **部分成立（C3=5，28%）**：BK-01/02/03（水下城市/礁盘/潜水员）、BK-06（鱼群）、BK-12（海龟）在人工判定下 visual usability=USABLE 但语义只是 MEDIUM——说明 V1 的 token 分数对"画面可用但语义非直接匹配"的候选仍给了高排名（因为 title 词面命中）。这是**语义分数召回表达不足**的信号，但非主要问题（C3 仅 28%）。

7. **分 natural/constructed/historical？**
   → 全部为 **natural-unlabeled**（真实池未标注候选）；constructed/historical 不参与（blocker 定义仅针对未标注候选）。

8. **新瓶颈判定？**
   → 见 §4。

---

## 4. 新瓶颈判定（证据强度标注）

| 瓶颈 | 判定 | 证据 |
|---|---|---|
| **RANKING_BOTTLENECK** | **SUPPORTED（保留）但性质修正** | V2 的 regression 不是"V1 选错"，而是"V1 在真实池中把未标注好素材排前、被评估基准（只含已标注子集）误判为回归"。**排序器用统一语义分数后，其在真实池的行为与人工判断方向一致**（13/18 blocker 确实 USABLE）——ranking 修复路径有效，但需要"未标注候选"进入评价视野 |
| **VISUAL_SUITABILITY_BOTTLENECK** | **WEAKLY_SUPPORTED（不升级，维持）** | C1=0 无法升级；5 个 NOT_USABLE blocker（论文页×2、珠宝图、气候示意图、FAQ 文档）说明**仍存在"词面命中但视觉不适合"的残余**（BK-19 用户直标 HN），但占比 28% 且非高语义，属弱证据 |
| **RETRIEVAL_BOTTLENECK** | **WEAKLY_SUPPORTED（维持）** | 6 个 supply-gap 镜（S02/S07/S08/S15/S18/S19）真实池中无人工确认 USABLE；不受本轮影响 |
| **DIRECTOR_BOTTLENECK** | NOT_SUPPORTED（未测） | — |

---

## 5. 关键结论

**RANKING VALIDATION-2 的 apparent regression 被本诊断解释为：**

> V1 在真实 399 池中把"标题词面匹配更优"的候选排前，而人工审阅确认这些候选 **72% 是真正可用的素材**（8 条 HIGH+USABLE、5 条 MED+USABLE）。V1 的行为与人工视觉判断方向一致——**V2 报告的"回归"主要源于评价基准只覆盖已标注子集（26/366），未标注的好素材被排到前面反而说明 V1 在真实池中"选对了"**。

**因此：**
1. 不因 V2 regression 否定 V1 的修复方向（Oracle 100% + 真实池 72% blocker 可用 = 排序方向正确）；
2. **不得**把 VISUAL_SUITABILITY_BOTTLENECK 升级为 SUPPORTED（C1=0）；
3. 剩余的 VISUAL_SUITABILITY 弱证据（28% NOT_USABLE blocker，其中 1 个用户直标 HN）支持"词面匹配仍无法完全排除视觉不适合素材"——需要**语义分数的表达力提升**（短语/语义匹配而非纯 token）或**独立视觉适用性通道**（后续评估，非本轮）；
4. **评价基准缺口**：真实池 340 个未标注候选是 V2 评估盲区——下一阶段应扩大标注覆盖（至少对 top-K 候选），否则无法判定"ranking 是否真正修复"。

---

## 6. 统计声明

- 抽样框、抽样规则、候选数、镜头数、标注覆盖率、label distribution、素材 SHA：见 §1 与 `blocker_frame.json`/`blocker_analysis.json`；
- **本结果仅基于 20 个 blocker 采样，代表"V1 排前列的未标注候选"的质量分布，不外推为整个 399 池的总体视觉质量**；
- Gold Standard 修改：**NO**（SHA `C70C82D462A82A7D...` 前后一致）；
- production 修改：**NO**。

---

**诊断完成。结论：V1 在真实池的 regression 主要是"排对了"（72% blocker 可用）；VISUAL_SUITABILITY 不升级；RANKING 修复方向保留。STOP，等待人工裁决。**
