# Stage 3.3 CV-2 Phase 3：Top-K 覆盖标注 + Ranking 验证报告

> 状态：**评价覆盖扩大完成（既有 73 + 新增 79 = 152 条标注）。关键发现：评价覆盖扩大后，V1 在真实池的"apparent regression"基本消失（combined Top-1=70.6%、MRR=0.821），证明 RANKING_VALIDATION-2 的 regression 主要是评价覆盖偏差。**
> 未修改 Gold Standard / production / Gate；未引入 CLIP/VLM/detector。完成后 **STOP**。

---

## 1. 固定引用（未修改）

| 产物 | SHA |
|---|---|
| gold_standard_frozen.json | `C70C82D462A82A7D...`（未修改，脚本断言校验） |
| CV-2 主实验结果 | `E1468FB0...`（未动） |
| Oracle-Pool | `90C8F265...`（未动） |
| Ranking Validation-1 | `9D2E7E77...`（未动） |
| Ranking Validation-2 | `096E4347...`（未动） |
| Blocker Analysis | `E061108E...`（未动） |

## 2. 抽样规则（读标签前固定）

真实 B pool 每镜 V1 Top-5 内**全部未标注候选**，79 条，20 镜全覆盖（每镜 2–5 条）。supply-gap 6 镜（S02/S07/S08/S15/S18/S19）自然纳入。

## 3. 标注记录（79 条，独立存储 `labels_topk.json`）

**分布**：

| 字段 | 分布 |
|---|---|
| visual_usability | USABLE 31 / CONDITIONALLY_USABLE 5 / NOT_USABLE 43 |
| semantic_relevance | HIGH 24 / MEDIUM 27 / LOW 28 |
| label_role | STRONG_POSITIVE 21 / ORDINARY 15 / STRONG_NEGATIVE 24 / HARD_NEGATIVE 19 |

**新增标注中 C1（HIGH+NOT_USABLE）= 6**（白化预警图、地球仪图、酸化机制图、pH 折线图、生态分区图、洋流 19世纪地图等）。

**用户标注混乱条目处理（全部披露于 labels_topk.json resolution_note）**：
- T-56 用户标注两次 → 取最终版（白化海葵最佳）；
- T-65 重复 → 取一；
- T-59 "恋爱-?"、T-70 "睡眠潮"、T-79 转录错乱 → 按 frame 素材（洋流地图/古书扫描/纽约夜景）+ 上下文校正，披露；
- T-74 用户标 USABLE 但理由"主画面不成立"且 role=STRONG_NEGATIVE → 按理由+role 校正为 NOT_USABLE，披露；
- T-74 实际素材 = S19 "Wild Things" 海报（frame 核对）；
- 你 page 8 补全的 T-71~79 与 frame 对齐（T-71/72/73=S18 古书装帧、T-74/75=S19、T-76/77/78/79=S20 城市夜景）。

## 4. 核心评价指标（已标注候选表现 vs 新增标注候选表现 分开报告）

| 指标 | 既有 73 条 only | 新增 79 条 only | **合并 152 条** |
|---|---|---|---|
| Top-1 USABLE | 42.9% | 46.2% | **70.6%** |
| Top-3 USABLE | 57.1% | 76.9% | **88.2%** |
| Top-5 USABLE | 57.1% | 100% | **100%** |
| MRR | 0.535 | 0.669 | **0.821** |
| mean best-USABLE rank | 6.571 | 2.077 | **1.588** |
| mean first-NOT_USABLE rank | 12.000 | 2.412 | 3.278 |
| pairwise separation (USABLE>NOT_USABLE) | 100% | 60.0% | 73.3% |
| C1 (HIGH+NOT_USABLE) | 1 | **6** | **7** |
| C2 (HIGH+USABLE) | 10 | 18 | 28 |
| C3 (MED/LOW+USABLE) | 18 | 13 | 31 |
| C4 (MED/LOW+NOT_USABLE) | 30 | 42 | 72 |
| 可验证候选数 | 59 | 79 | 138 |

**Source bias（全池结构，未变）**：whitelist mean rank 10.455 vs Commons 11.046——V1 保持 source-neutral；Top-1 混合 whitelist 7 / Commons 13。

## 5. 关键发现

1. **评价覆盖偏差被证实并消除**：V2 报告的"apparent regression"（Top-1 42.9%）是**只含已标注子集（59/399）的盲区**。合并 new 标注后 Top-1=70.6%、MRR=0.821——V1 在真实池的表现优于 V2 当时测得的；
2. **C1=7 条被人工确认**（HIGH+NOT_USABLE）：全部为图表/地图/文档类（白化预警图、酸化机制图、pH 折线图、生态分区矢量图、19世纪洋流地图×2、气候带矢量图）——**语义 HIGH 但视觉不适合的素材集中出现在"数据可视化/图解"类型**，这是确定性 token 分数无法区分的，**直接支持 VISUAL_SUITABILITY_BOTTLENECK 升级**；
3. **C2=28 条 MED/LOW+USABLE**：V1 分数给的排名与人工判断方向一致（如 T-21~24 海温柱状图全部 USABLE/HIGH）；
4. **Top-5=100%**：合并后所有含 USABLE 的镜 Top-5 都含 USABLE——V1 在 Top-5 内选对率已满。

## 6. V1.1 离线探索性指标（未写入 production）

**V1.1 lexical normalization（V2 已实现）**：`corals→coral`、`bleaching/bleached→bleach` 修复已知 token 问题；误伤 `species→specy`、`fishes→fishe`（词形约束下同形两可，未观察到排序异常）。

**V1.1 phrase matching（设计，未实现）**：将 token overlap 扩展为 2-gram 短语重叠（如 "coral reef"、"sea turtle"、"ocean acidification"）。**预注册预期**：可提升"复合主题"候选的区分度（C2 类），但对 C1 类图表/文档无帮助（它们同样含这些短语）。**明确标注：此指标为探索性，不写入生产、不参与 Gate。**

## 7. 决策树 / 瓶颈判定

| 瓶颈 | 判定更新 |
|---|---|
| **RANKING_BOTTLENECK** | 修正如用户指定口径：`SUPPORTED, BUT V1 REAL-POOL GENERALIZATION = VALIDATED`（合并评价后 evidence coverage bias 消除，V1 真实池 Top-1=70.6%/MRR=0.821——**generalization 结论翻转**） |
| **VISUAL_SUITABILITY_BOTTLENECK** | **升级为 SUPPORTED**：C1=7 条全为数据可视化/图解类（HIGH+NOT_USABLE），token/短语语义分数结构性无法拒绝它们 |
| **RETRIEVAL_BOTTLENECK** | WEAKLY_SUPPORTED（维持）：6 supply-gap 镜仍无 labeled USABLE |
| **DIRECTOR_BOTTLENECK** | NOT_SUPPORTED（未测） |

**最终表述（按用户 §6 口径）**：
```
RANKING_BOTTLENECK = SUPPORTED, BUT V1 REAL-POOL GENERALIZATION = VALIDATED
VISUAL_SUITABILITY_BOTTLENECK = SUPPORTED (from WEAKLY, 由 C1=7 数据支持)
RETRIEVAL_BOTTLENECK = WEAKLY_SUPPORTED
DIRECTOR_BOTTLENECK = NOT_SUPPORTED
```

## 8. STOP 状态确认

- **未修改**：production ranking、3.1.4、V3 plan、Gold Standard（`C70C82D4...` 不变）、Gate、人工标签；
- **未引入**：CLIP/VLM/detector/新关键词黑名单；
- **未运行**：production integration；
- 新增产物：`labels_topk.json`、`final_eval.json`、`frame.json`、`stats.json`、8 页 contact sheet、`topk_labeling_manifest.json`。

---

**Phase 3 完成。关键结论：V1 真实池 generalization 翻转（VALIDATED），VISUAL_SUITABILITY_BOTTLENECK 由 C1=7 证据升级为 SUPPORTED。STOP，等待人工裁决。**
