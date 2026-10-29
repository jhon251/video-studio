# Stage 3.3 CV-2 Postmortem / Bottleneck Localization

> 状态：**复盘分析（只读已有实验数据，无新模型、无新实验）。** 正式接受 `SUPPLY_LAYER_PARTIALLY_VALIDATED` 并拆分为存在性/质量选择两个独立命题。
> 完成 **Oracle-Pool 实验设计**（不运行）。完成后 STOP。

---

## 一、正式拆分：两个独立命题（不再合并为"供给失败"）

### 1.1 ✅ SUPPLY_EXISTENCE_VALIDATED（已验证：扩大供给解决了"没有素材"）

| 证据 | A | B |
|---|---|---|
| zero-candidate shot | **7** | **0** |
| retrieval coverage | 0.65（13/20） | **1.00（20/20）** |
| 每镜候选 | 0–3 | 5–23 |
| 7 个历史零候选镜（S01/S02/S10/S13/S15/S16/S18） | 0 候选 | **全部 ≥5（多数 20）** |

**结论**："扩大真实素材供给，消除了'无素材导致的文字卡退化'的供给端原因"——**成立**。

### 1.2 ❌ SUPPLY_QUALITY_SELECTION_NOT_VALIDATED（未验证：更多候选 → 更好的视觉候选）

| 证据 | A | B |
|---|---|---|
| Top-5 usability | 44.9% | **44.2%**（无改善） |
| Top-5 NOT_USABLE（绝对数） | 15 | **26（增加）** |
| SP Top-1 retention | 43.8% | 33.3%（下降） |
| SN suppression | 60.0% | **0.0%（崩溃）** |

**结论**："更多候选 → 系统能选出更可用的视觉证据"——**不成立**。

> **关键纪律**：两个命题必须分开判定。B Gate FAIL 是"质量选择"失败，不是"供给存在性"失败；反之，存在性成立也不能豁免质量选择失败。

---

## 二、A→B 为什么没有提升：逐镜分析（20 shot 全表）

（完整数据：`output/stage33/cv2/postmortem_per_shot.json`）

### 2.1 逐镜摘要（A/B 候选数、Top-5 usability、Top-1 人工标签、B 新增 labeled 质量）

| shot | A→B 候选 | A_u5 | B_u5 | A_Top1 | B_Top1 | B新增(labeled) | B新增USABLE |
|---|---|---|---|---|---|---|---|
| S01 | 0→20 | — | 1.00 | — | USABLE/MED | 2标/20 | **2**（rank1, rank9） |
| S02 | 0→5 | — | 0.00 | — | NOT_USABLE/LOW | 2标/5 | 0 |
| S03 | 1→19 | 0.00 | 0.50 | NOT_USABLE/LOW | NOT_USABLE/LOW | 1标/18 | 1（rank4） |
| S04 | 3→23 | 1.00 | 1.00 | USABLE/MED | USABLE/MED | 1标/20 | 1（rank4） |
| S05 | 3→23 | 0.67 | 0.75 | USABLE/MED | USABLE/MED | 1标/20 | 1（rank4） |
| S06 | 3→23 | 0.33 | 0.50 | NOT_USABLE/LOW | NOT_USABLE/LOW | 1标/20 | 1（rank4） |
| S07 | 2→22 | 0.00 | 0.00 | NOT_USABLE/LOW | NOT_USABLE/LOW | 1标/20 | 0 |
| S08 | 3→23 | 0.00 | 0.00 | NOT_USABLE/LOW | NOT_USABLE/LOW | 1标/20 | 0 |
| S09 | 3→23 | 0.67 | 0.75 | USABLE/HIGH | USABLE/HIGH | 1标/20 | 1（rank4） |
| S10 | 0→20 | — | 0.00 | — | NOT_USABLE/LOW | 2标/20 | 1（rank11） |
| S11 | 3→20 | 0.33 | 0.25 | USABLE/MED | USABLE/MED | 1标/17 | 0 |
| S12 | 3→23 | 0.33 | 0.33 | USABLE/MED | USABLE/MED | 1标/20 | 1（rank8） |
| S13 | 0→20 | — | 0.50 | — | NOT_USABLE/LOW | 2标/20 | 1（rank4） |
| S14 | 2→22 | 1.00 | 1.00 | USABLE/HIGH | USABLE/HIGH | 1标/20 | 1（rank3） |
| S15 | 0→20 | — | 0.00 | — | NOT_USABLE/LOW | 2标/20 | 0 |
| S16 | 0→20 | — | 0.00 | — | NOT_USABLE/LOW | 2标/20 | 1（rank7） |
| S17 | 3→9 | 1.00 | 0.75 | USABLE/MED | USABLE/MED | 1标/6 | 0 |
| S18 | 0→20 | — | 0.00 | — | NOT_USABLE/LOW | 1标/20 | 0 |
| S19 | 2→22 | 0.00 | 0.00 | NOT_USABLE/MED | NOT_USABLE/MED | 1标/20 | 0 |
| S20 | 2→22 | 0.50 | 0.33 | NOT_USABLE/LOW | NOT_USABLE/LOW | 1标/20 | 0 |

### 2.2 核心回答：B 是"没找到更好的素材"还是"找到了但没排上来"？

**从已标注样本看，两者都有，但以"排序问题"为主导：**

- **找到了好素材（供给侧有效）**：B 新增的 26 个 labeled 候选中有 **12 个 USABLE**（46%），且分布在 12 个不同 shot（S01/S03/S04/S05/S06/S09/S10/S12/S13/S14/S16）；
- **但没排上来（排序侧失效）**：这 12 个 USABLE 新增候选中，**只有 1 个进入 Top-1**（S01 的 artificial coral reef pods），**9 个排在 rank 4–11**（大多数 rank=4），2 个 rank 7–9；
- **反向污染**：B 组每镜 20 个候选大多未标注（366 中 340 未标注），它们以 Commons search 原序占据 rank 1–3，把已标注的 USABLE 挤到 rank 4 及以后。

**逐镜证据（典型）**：
- **S01**（A 零候选）：B 新增 20 个，其中 2 个 labeled 全是 USABLE，且 rank1=USABLE → **这是"扩池直接解决"的正例**；
- **S05/S09**（白化/海龟）：A 已有 USABLE（M-S05-276/M-S09-456），B 新增也含 USABLE（Bleached Staghorn rank4、Baby Turtle rank4），但 B Top-1 仍是 A 的旧候选 → 新增好素材在 rank4，**排序未受益**；
- **S02/S07/S08/S11/S15/S17/S18/S19/S20**：B 新增 labeled 中 USABLE=0 或未标注 → 这些镜的 B Top-1 全是不合适素材（NOT_USABLE）→ **供给确实没在这些镜提供足够好素材 + 排序也无力回天**。

**结论**：A→B 未提升 = **"召回有收获（12 个新 USABLE），但 semantic ranking 无法把它们排到 Top-K"**。主因是**排序**，次因是**部分镜头供给本身仍缺好素材**（9/20 镜 B 新增 labeled 无 USABLE）。

---

## 三、Retrieval vs Ranking 判定（Bucket 拆分）

### 3.1 Bucket 1（A 已有 = whitelist 33）vs Bucket 2（B 新增 = Commons 366）

| 指标 | Bucket 1（A） | Bucket 2（B 新增） |
|---|---|---|
| 总数 | 33 | 366 |
| labeled | 33（100%） | **26（7.1%）** ⚠️ |
| USABLE（labeled） | 16（48.5%） | **12（46.2%）** |
| CONDITIONALLY_USABLE | 2 | 3 |
| NOT_USABLE | 15 | 11 |
| 进入 B Top-1（labeled） | 13/33 | 7/26 |
| 进入 B Top-3（labeled） | 33/33 | 10/26 |
| 进入 B Top-5（labeled） | 33/33 | 19/26 |

### 3.2 关键回答

**"扩池以后，是没召回好素材，还是召回了好素材但 ranking 把坏素材排前面？"**

→ **主要是后者：召回了好素材，但 ranking 把它们排在后面。**

证据链：
1. **召回层面没有失败**：B 新增 labeled 候选中 USABLE 占 46.2%（与 A 的 48.5% 几乎持平）——Commons 检索**确实召回了同比例的好素材**；
2. **ranking 层面失败**：新增 USABLE 中仅 1/12 进入 Top-1、5/12 进入 Top-3、10/12 进入 Top-5；而 A 旧候选（含 16 个 USABLE）在 B 排序中 13 个 Top-1、全部 Top-3/5；
3. **根本机制**：`_retrieval_sort_key` 把 whitelist（有 semantic_match 分数）**整体排在 Commons（无分数）之前**（`(0, -sm)` vs `(1, rank)`），而 Commons 候选内部按 **search 原序**排列——search 原序与人工可用性无相关性，导致"坏素材占位 Top-3、好素材沉到 rank4+"。

**必须披露的局限**：Bucket 2 标注覆盖率仅 7.1%（26/366），结论基于已标注子样本，代表的是"标注过的候选"的质量；未标注的 340 个候选质量未知。此局限已在 §9 记录。

---

## 四、C 失败分析（不判"视觉理解不可能"）

### 4.1 实测

| 指标 | B | C |
|---|---|---|
| Top-5 usability | 44.2% | 44.0%（无改善） |
| SP retention（前半） | 95.8% | 83.3%（下降） |
| SP 误杀（false negative） | 0 | **2**（含 M-S12-607） |
| SN suppression | 0.0% | 16.7%（微升） |
| Strict HN 被过滤 | — | **1/2** |

### 4.2 判定

**`DETERMINISTIC_VISUAL_FILTER_V1_NOT_VALIDATED`**（仅此而已）

**严禁由此推出** `VISUAL_UNDERSTANDING_IS_IMPOSSIBLE`，因为：
- 本轮 C 用的是**确定性 metadata/关键词过滤**（标题含 painting/oil/rmg/person 等）；
- CV-1 证明的是 **CLIP ViT-B/32 属性识别**不足；
- **两者是完全不同的能力通道**（规则 vs 视觉模型），本轮结果只证伪了"关键词黑名单式过滤"，未触及"真正的视觉理解"；
- C 确实压下一个 Strict HN（渔夫油画，标题含 painting），说明**"类型关键词过滤"对显式类型有效**，只是覆盖面窄（对示意图/版画/人物照片无效）且误伤（S12 油画被人工判 USABLE 却被杀）。

---

## 五、三个 Historical Failure 深度分析

### 5.1 S03 × M-S03-162（1957 电影剧照；人工：NOT_USABLE/LOW）

**为什么 semantic retrieval 能把它排 Top-1？**
- A/B 组均 rank 1。机制：`_retrieval_sort_key` 里 whitelist 候选按 `semantic_match`（3.1.4 时代评分，M-S03-162 为 50.0）排序，且 S03 的 whitelist 池只有 1 个候选（M-S03-162）→ **无竞争，自动 Top-1**；
- 它当年的 semantic_match=50 恰好过阈，而检索/评分只看文本语义（"深处/下潜"与电影名"Lower Depths"字面相关），**完全没有视觉类型通道**；
- 本质：**这是 ranking 层在"单候选镜"下的结构性缺陷**（无竞争时坏素材自动置顶），也是语义评分把"标题语义"当"画面语义"的缺陷。

### 5.2 S12 × M-S12-607（渔民油画；人工：**USABLE/MEDIUM**；C 过滤误杀）

**为什么人工认为 USABLE，C 又把它过滤？**
- 人工观看画面后判定"渔民拉网"的写实油画**可以承担该镜头**（叙事可用）——这是**人工的视觉适用性判断**；
- C 的 `painting/oil/rmg` 关键词命中标题（RMG BHC0805.tiff）→ 一刀切过滤；
- **这个案例证明**："视觉类型过滤 ≠ 视觉适用性判断"。类型只是适用性的**弱代理**：写实油画在某镜头可能可用，示意图在另一镜头可能不可用。**用类型当适用性 = 用代理变量当真值，必然误伤**。

### 5.3 S19 × M-S19-954（沙滩孩子照片；人工：NOT_USABLE/MEDIUM；三组均 Top-1，C 未过滤）

**为什么照片类人物素材三组都能 Top-1，C 也识别不了？**
- A/B 组：S19 的 whitelist 中 M-S19-954 的 semantic_match 最高 → Top-1；
- C 组：标题 "Kids on the beach" **无 painting/oil/film 关键词**，person 关键词（"kids"）命中但 S19 ∈ PERSON_ALLOWED_SHOTS（人物允许镜）→ 不触发过滤；
- 本质：**人物照片类失败案例落在确定性过滤的盲区**（既是合法类型、又在允许人物镜、标题无异常词），它需要的判断是"照片内容/意境与镜头需求不符"——**这是语义-视觉联合判断，关键词过滤结构上无法表达**。

### 5.4 最终判断：失败主要发生在哪一层？

| 层 | 判定 | 依据 |
|---|---|---|
| **retrieval semantics** | ⚠️ 部分失败 | 召回本身有 46% USABLE（不算失败）；但"标题语义=画面语义"的评分对剧照/油画误判（S03 置顶） |
| **ranking（semantic）** | ❌ **主失败点** | 新增 USABLE 12 个只有 1 个 Top-1；Commons 按 search 原序占位；whitelist 无竞争置顶（S03） |
| **visual suitability judgment** | ❌ **次失败点** | C 的关键词过滤覆盖面窄（1/2 Strict HN）、误伤 SP（S12 油画）、无法处理 S19 意境类 |
| **Director 对 visual role 的建模** | ⚠️ 未测试 | 本轮无 Director 参与，无法从数据判定 |

**瓶颈假设排序**（证据强度从高到低）：
1. **RANKING_BOTTLENECK**（强证据：好素材召回但排不上位）
2. **VISUAL_SUITABILITY_BOTTLENECK**（中强证据：关键词过滤窄且误伤；但"真正的视觉理解"未测）
3. **RETRIEVAL_BOTTLENECK**（弱-中证据：召回同比例好素材，但部分镜头供给仍薄：9/20 镜新增无 USABLE）
4. **DIRECTOR_BOTTLENECK**（无证据，未测）

---

## 六、能力边界诊断（不堆模型，先问反事实）

**下一阶段核心问题**：
> 如果给系统一个**已经包含正确素材**的候选池，它能不能选对？

- 现有证据已给出**部分答案**：A 池（33 个，含 16 USABLE）在 B 排序下 13 个 USABLE 进 Top-1、33/33 进 Top-3 —— **当池里正确素材占优且候选数少时，排序能选对**；
- 但当池变大（B：366，好素材被稀释 + 无分数候选按 search 原序占位）时，排序**选不对**；
- 因此反事实实验的关键变量是**"池内好素材占比"与"排序信号质量"**，而不是"池大小"。

---

## 七、Oracle-Pool / Ranking Validation 实验设计（下一轮最小实验，本轮不运行）

### 7.1 目的
隔离"检索供给"与"排序/视觉判断"：给系统一个已知含正确素材的小池，测它能否选对。

### 7.2 构造（只用已冻结 73 条 Gold Standard，不新增素材）
对每个 shot（有 labeled 候选的）：
1. **放入 ≥1 个人工 USABLE/STRONG_POSITIVE**（来自冻结标签）；
2. **放入若干 semantic HIGH 但视觉 NOT_USABLE**（含 2 个 Strict HN + 3 个 Historical Failure 中 NOT_USABLE 者）；
3. **打乱候选顺序**（固定 seed，记录 SHA）；
4. **系统不知道人工标签**（排序仅用现 retrieval 信号：semantic_match / search rank / 确定性过滤）。

### 7.3 两个问题
- **R1**：当前 semantic ranking 能否把真正 USABLE 排到 Top-1/3/5？
- **R2**：
  - 若不能 → 瓶颈 = **排序/视觉判断**（系统在"已知池含好素材"下仍选错）；
  - 若能 → 原问题主要来自**真实素材池召回不足**（供给端）。

### 7.4 变体（可分层报告）
- V1：只用 whitelist 信号（semantic_match）排序；
- V2：whitelist + Commons search 原序；
- V3：V2 + 确定性视觉过滤（C）；
- 指标：Top-1/3/5 USABLE 命中率、SP retention、SN suppression、Strict HN 下沉（n=2 exploratory）。

### 7.5 纪律
- 隔离实验，不生产实现；不修改 Gold Standard/标签/阈值/生产代码；
- 候选池 = 冻结标签子集（每个 shot ≤ 5–8 个），打乱固定 seed；
- 结果分 natural/constructed/historical 报告。

---

## 八、当前能力瓶颈假设排序（合并结论）

1. **RANKING_BOTTLENECK** — 主瓶颈（新增好素材 46% USABLE 但仅 1/12 进 Top-1；Commons 无分数候选按 search 原序占位；whitelist 单候选镜自动置顶）
2. **VISUAL_SUITABILITY_BOTTLENECK** — 次瓶颈（确定性关键词过滤：1/2 Strict HN、误伤 SP、S19 盲区；"真正的视觉理解"未测，不能判死）
3. **RETRIEVAL_BOTTLENECK** — 部分镜头仍存在（9/20 镜 B 新增 labeled 无 USABLE；但总体召回质量与 A 持平）
4. **DIRECTOR_BOTTLENECK** — 未测（本轮无 Director 参与）

---

## 九、已知局限

1. **Bucket 2 标注覆盖率 7.1%**（26/366）：新增候选质量结论基于已标注子样本，340 个未标注候选质量未知——这是本次 postmortem 最大的数据局限；
2. **SP retention 双口径**（前半 95.8% vs Top-1 33.3%）：Gate 口径未裁定，不影响 Top-5 usability 44.2% 的失败结论；
3. **Strict HN n=2**：仅探索性；
4. **probe rank 在"注入临时池"中测得**：非自然池；
5. **Top-5 usability 分母为 labeled 候选**：稀疏标注偏差；
6. **S03 单候选镜置顶**是 ranking 结构性现象，不是该素材特有的问题。

---

## 十、下一步决策树

```
Oracle-Pool R1 结果
├─ R1 PASS（已知池含好素材时能选对）
│   └─ 瓶颈 = RETRIEVAL（真实池召回不足）
│       └─ 下一步：改善召回路由（多路召回/查询扩展），不碰排序
├─ R1 FAIL（已知池含好素材时仍选错）
│   ├─ 失败模式 = 无分数候选占位 / search 原序
│   │   └─ 瓶颈 = RANKING → 下一步：排序信号重建（语义分数覆盖全部候选），先于任何视觉模型
│   ├─ 失败模式 = 类型陷阱未被过滤
│   │   └─ 瓶颈 = VISUAL_SUITABILITY → 下一步：独立视觉适用性通道（非关键词、非 CLIP-B/32）
│   └─ 失败模式 = 混合
│       └─ MIXED / INCONCLUSIVE → 分层报告，再定
└─ 证据不足 → INCONCLUSIVE
```

**本轮判定（基于现有证据，不运行 Oracle）：`RANKING_BOTTLENECK`（主）+ `VISUAL_SUITABILITY_BOTTLENECK`（次）**

> 最终只允许五选一。基于现有数据（非 Oracle 运行结果），判定为 **`RANKING_BOTTLENECK`**，并明确标注：该判定以"Bucket 2 已标注子样本（7.1% 覆盖率）"为证据基础，**必须由 Oracle-Pool 实验（R1）验证后才能升级为正式结论**；若 Oracle 实验显示"已知池含好素材仍选错"，则按决策树重新定位。

---

**Postmortem 完成。Oracle-Pool 实验仅设计、未运行。STOP，等待人工裁决。**
