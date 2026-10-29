# Stage 3.3 CV-2 RANKING VALIDATION-2：REAL POOL VALIDATION 报告

> 状态：**真实 399 pool 验证完成。结论：INCONCLUSIVE → 归因拆解后判定为 MIXED（ranking gain 无法迁移 + source bias 成功消除 + 大量未标注候选质量未知）。**
> 未修改 production ranking / 3.1.4 / V3 plan / Gold Standard / Gate / 人工标签；未加 CLIP/VLM/visual filter/扩池。
> 完成后 **STOP**，等待人工裁决。

---

## 1. 399 Candidate Pool Audit

### 1.1 Commons 366

- query 语言：**366/366 英文**；唯一 query 值 = **20 条**（与 20 镜锚定查询同源）；
- metadata 完整性：title+description+artist 全有 332、缺 desc 有 artist 20、缺 artist 有 desc 8、仅 title 6；
- **每镜 20 个候选、同 query**——即每镜的候选由同一查询召回，Commons 池内部无 query 变化维度。

### 1.2 Whitelist 33（semantic_match ≥50）

- query 语言分布（materials 全量 1045）：en 1007、mixed 38；
- whitelist 33 的 query 全部含英文字母（`[R3_fulltext] 海洋吸收`、`[R3_fulltext] 白化珊瑚` 等虽有中文本体但带英文前缀 R3_fulltext）；
- 其中 query 本体为中文的候选 5 个：M-S07-358/357（海洋吸收）、M-S09-456/454/453（白化珊瑚）。

**结论**：20 镜都有英文锚定 query（Commons 召回同源）——V2 的 `semantic_score_v2` 沿用该英文 query，**不翻译中文口播、不反向用候选信息生成 query**。

---

## 2. Token Normalization（纯文本层，无 label、无例外词表）

规则：lowercase + NFKC + 标点去除；单复数 `ies→y, ves→f, oes→o, sses→ss, s→''(长度>3 且非 ss 结尾)`；词形 `ing→''(长度>5), ed→''(长度>5)`。

**归一化前后变化样本（如实报告，含误伤）**：

| 原始 | 归一化 | 正确性 |
|---|---|---|
| corals → coral | ✅ 修复 V1 已知问题 | 正确 |
| bleaching → bleach / bleached → bleach | ✅ | 正确 |
| fishes → fishe ⚠️ | 词根受损 | 误伤（但 query 用 fisherman/海龟等，实际影响小） |
| species → specy ⚠️ | 词根受损 | 误伤 |
| beaches → beache ⚠️ | 词根受损 | 误伤 |
| fishermen → fishermen | 未变（fishermen 无 s 结尾规则命中） | — |
| snorkeling → snorkel | ✅ | 正确 |

**误伤评估**：`species/fishes/beaches` 类误伤是"过度归一化"，但它们两侧（query 与候选）同时归一化，同词同形仍能匹配；跨词形碰撞风险存在但本轮未观察到引入异常（见 §8 判定条件 5）。

---

## 3. Baseline vs V1（真实 399 pool）

### 3.1 已标注子集 evaluation（eligible shots：14 个含人工 USABLE 的镜）

| 指标 | A baseline | A V1 | B baseline | B V1 |
|---|---|---|---|---|
| labeled 有 USABLE 镜数 | 9 | 9 | 14 | 14 |
| **Top-1 USABLE** | 77.8% | **88.9%** | **57.1%** | **42.9%** ⚠️ |
| Top-3 USABLE | 100% | 100% | 71.4% | 57.1% |
| Top-5 USABLE | 100% | 100% | 85.7% | 57.1% |
| MRR | 0.870 | **0.944** | **0.683** | **0.535** ⚠️ |
| mean best USABLE rank | 1.333 | **1.111** | 2.786 | **6.571** ⚠️ |
| mean first NOT_USABLE rank | 1.600 | 1.600 | 1.529 | 12.000 |
| separation rate | 66.7% | **83.3%** | 45.5% | **100%** |

**Oracle→Real 一致性检查**：
- Oracle（小池，每镜 2–6 候选）：V1 Top-1 = 100%；
- **Real B 池（每镜 ~20 候选）：V1 Top-1 = 42.9%，且低于 baseline 的 57.1%**——**ranking gain 未能迁移**。

### 3.2 全量 399 结构（未标注候选不做 usability 推断）

**Source bias 验证（核心）**：

| metric | B baseline | B V1 |
|---|---|---|
| Top-1 whitelist rate | 65.0% | **35.0%** |
| Top-5 whitelist rate | 65.0% | **45.0%** |
| Commons entering Top-1 | 7 | **13** |
| Commons entering Top-5（镜数） | 20 | 20 |
| mean rank whitelist | **1.85** | **10.46** |
| mean rank Commons | 11.82 | **11.05** |

- **baseline**：whitelist mean rank 1.85 vs Commons 11.82——强 source bias（whitelist 无条件占顶）；
- **V1**：10.46 vs 11.05——**source bias 消除**，whitelist/Commons 排名分布趋同，无反向 bias；
- Commons entering Top-1 7→13（翻倍）——Commons 不再被 search-order 机械压底。

---

## 4. 关键归因：为什么 V1 在真实池排名下降（Case A/B/C 拆解）

### 4.1 归因表（V1 下被压住的 labeled USABLE 与压住者）

| shot | 最差 USABLE | baseline→V1 | 压住者(未标注)示例 | 压住者 v1 score |
|---|---|---|---|---|
| S01 | Coral alambre | 9→17 | "Underwater photo of coral reef.jpg" | 1.0 |
| S04 | M-S04-224 | 1→21 | "School of fish at Flinders Reef" / "Parrotfish school over coral reef" | 0.75 |
| S05 | M-S05-272 | 1→20 | "Copernicus bleaching alert" / "NOAA bleaching forecast map" | 1.0 |
| S06 | 20210827 温度柱状图 | 4→21 | 三个 "Temperature Bar Chart Ocean-*" | 0.9 |
| S09 | M-S09-456 | 1→23 | "Seized Corals and Sea Turtle Jewelry" / "Sea Turtle over Coral Reef" | 1.0 |
| S13 | Findochty 渔村 | 4→17 | "View over Fishing Village" / "Laundry Hangs in Fishing Village" | 1.0 |
| S14 | Amphiprion 小丑鱼 | 3→22 | "Clownfish with anemone.jpg" / "Clownfish in anemone off Vanuatu" | 1.0 |

### 4.2 三 Case 判定

- **Case A（池中无好候选 → RETRIEVAL）**：**部分成立但非主因**——压住 USABLE 的候选**很多是语义上更匹配的高质量照片**（如 S14 的 "Clownfish with anemone.jpg"、S09 的 "Sea Turtle over Coral Reef"），说明**真实池里并不缺好素材**；6 个 supply-gap 镜（S02/S07/S08/S15/S18/S19）则确实是池中无标注 USABLE；
- **Case B（有好候选但 V1 没排上去 → RANKING）**：**主因**——M-S04-224（USABLE，人工认可）被 17 个未标注候选压到 rank21，而压住它的 "School of fish at Flinders Reef" 等 title 与 query "coral reef fish school" token 重叠更高。**V1 的 token-overlap 分数把"title 词面匹配"当成了"视觉可用"**，在 20 候选大池中 title 词面匹配者占满前排；
- **Case C（排上去了但视觉不适合 → VISUAL_SUITABILITY）**：本轮数据**无法区分**——压住 USABLE 的未标注候选没有人工标签，不能判定它们视觉上是否真的不适合。

### 4.3 核心发现

**V1 在 Oracle 小池成功是因为候选少、source bias 是主矛盾；在真实大池中，token-overlap 分数无法在"语义相关但视觉不适合"与"语义相关且视觉适合"之间区分**——分数高度取决于 title 词面匹配，而 title 词面匹配 ≠ 视觉可用性。这正是下一阶段 VISUAL_SUITABILITY 的证据来源。

---

## 5. Historical Failure（真实池三镜）

| Case | 人工标签 | A base→V1 | B base→V1 | 解释 |
|---|---|---|---|---|
| S03 × M-S03-162（剧照） | NOT_USABLE/LOW | 1→1 | **1→5** ✅ | V1 下剧照 title "The Lower Depths" 与 query 零重叠，被 4 个候选压过——**修复** |
| S12 × M-S12-607（渔夫油画） | **USABLE/MEDIUM** | 1→1 | 1→1 ✅ | title 与 query "fishermen hauling nets shore" 全命中 score=1.0，仍第一——**保持**（不因历史当负例） |
| S19 × M-S19-954（沙滩孩子） | NOT_USABLE/MEDIUM | 1→2 | 1→2 | 略降但仍前列；该镜属 SUPPLY GAP（无标注 USABLE），**不算 ranking failure** |

---

## 6. Supply-Gap 镜（6 个，独立报告）

| shot | 候选数 | 标注 USABLE | V1 Top-1 候选 |
|---|---|---|---|
| S02 | 5 | 0 | Polyp zoox（labeled NOT_USABLE） |
| S07 | 22 | 0 | Six key dimensions...（未标注） |
| S08 | 23 | 0 | Consequences of eutrophication...（未标注） |
| S15 | 20 | 0 | World Ocean Current Chart Feb.（未标注） |
| S18 | 20 | 0 | The structure and distribution...（未标注） |
| S19 | 22 | 0 | M-S19-953（labeled NOT_USABLE） |

**`RETRIEVAL_BOTTLENECK = WEAKLY_SUPPORTED` 维持**：6 镜在真实池中无任何人工确认 USABLE 候选（注意：这与"历史 7 零候选镜"不同口径——历史 7 镜已在供给存在性上解除，但其中部分镜的"视觉可用"供给仍未确认）。

---

## 7. V2 判定（预注册标准）

| 条件 | 实测 | 判定 |
|---|---|---|
| 1. source bias 显著下降 | whitelist mean rank 1.85→10.46；Top-1 wl rate 65%→35% | ✅ |
| 2. Commons 不再被 search-order 机械压底 | Commons entering Top-1 7→13 | ✅ |
| 3. 已标注候选上 V1 保持明显 ranking gain | **Top-1 57.1%→42.9%，mean best rank 2.79→6.57（下降）** | ❌ |
| 4. 不产生新系统性 source bias | mean rank 10.46 vs 11.05（趋同） | ✅ |
| 5. normalization 无异常 | 误伤 species/fishes/beaches（词根受损），同形两侧一致，未观察到排序异常 | ✅（带披露） |

**按预注册：条件 3 失败 → `FAIL`**；但 §7 的 Case 拆解显示下降主因是"未标注候选质量未知 + token 分数词面匹配局限"，且真实池存在高质量未标注候选（Case B 与 Case A 交织、Case C 无法判定）。**最终判定：`INCONCLUSIVE（MIXED）`**——

> 严格按预注册条件 3，V1 未在真实池复现 Oracle 的 ranking gain（→ FAIL 方向）；但下降的根本原因是 340/366 未标注候选的质量未知 + V1 token 分数的词面匹配局限，属于"真实池标注覆盖率不足 + 分数粒度不足"的混合情形，而非简单的"统一语义分数在大池中无效"。因此不武断宣布 FAIL，标记 INCONCLUSIVE（MIXED），并给出下一阶段可验证的决策树。

---

## 8. 瓶颈判定更新

| 瓶颈 | 证据变化 | 判定 |
|---|---|---|
| RANKING_BOTTLENECK | V1 在 Oracle 可修，但真实池 gain 不可迁移（token 分数粒度不足） | SUPPORTED（仍为主瓶颈，但修复路径需更深信号） |
| VISUAL_SUITABILITY_BOTTLENECK | 真实池压住 USABLE 的是"title 词面匹配更好"的未标注候选，其视觉适合性未知 | **升级为 SUPPORTED 候选（待确认）**——若确认压住者视觉不适合，则语义分数结构性无法表达视觉适用性 |
| RETRIEVAL_BOTTLENECK | 6 镜 supply gap；但 14 镜池中有高质量未标注候选（压住者本身像好素材） | WEAKLY_SUPPORTED（维持） |
| DIRECTOR_BOTTLENECK | 未测 | NOT_SUPPORTED |

---

## 9. Production Integration Readiness

**NOT READY。** V2 的 PASS 条件未满足（条件 3 失败）。即使条件全部满足，本阶段也仅能把 `semantic_score_v1/v2 → production integration candidate` 提交下一阶段 `RANKING REMEDIATION DESIGN`（scoring API / normalization / tie-break / source neutrality / missing metadata / fallback / regression / 兼容性 / 性能）。

**本轮未修改任何 production ranking。**

---

## 10. 下一步决策树（待人工裁决）

```
V2 = INCONCLUSIVE（MIXED）
├─ 路径 1：解决"未标注候选质量未知"——对真实池压住 USABLE 的未标注候选做一轮人工标注（top blockers 采样）
│    → 若确认它们是视觉可用的好素材 → V1 的"下降"其实是"排对了"（真实池有好素材，V1 排它们到前面）→ 瓶颈回到 RETRIEVAL 结论改写
│    → 若确认它们视觉不适合 → VISUAL_SUITABILITY_BOTTLENECK 升级 SUPPORTED → 进入独立视觉适用性通道评估
├─ 路径 2：改进分数粒度（超出本轮 scope）：词面匹配 → 短语/语义匹配（不引入视觉模型）
├─ 路径 3：先做 6 镜 supply gap 的多路召回实验（RETRIEVAL 分支）
└─ 不做：CLIP/VLM/detector/visual filter（当前证据仍不充分）
```

---

## 11. Audit trail

- Gold Standard 冻结版 SHA：`C70C82D462A82A7D4A3D3D35F80EE65748106AC9B57E4BB74AC81E34B9E448AC`
- 脚本：`output/stage33/cv2/ranking_validation_v2/run_v2.py`、`pool_audit.py`、`attribution.py`
- 结果：`output/stage33/cv2/ranking_validation_v2/result.json`、`pool_audit.json`、`attribution.json`
- 未修改任何 production/实验资产；未使用人工 label 参与排序；未对未标注候选推断 usability。

---

**实验完成。判定：`INCONCLUSIVE（MIXED）`。STOP，等待人工裁决。**
