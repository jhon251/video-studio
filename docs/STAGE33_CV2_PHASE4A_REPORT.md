# Stage 3.3 CV-2 Phase 4A：V1.1 Phrase Matching 离线验证报告

> 状态：**离线验证完成。结论：`RANKING_V1.1 = NOT_VALIDATED`（在 152 条标注集上，V1.1 全面劣于 V1，且原因可解释）。**
> 未修改 production / Gold Standard / Gate / 人工标签；未引入 CLIP/VLM/detector。完成后 **STOP**。

---

## 1. 实验设计

- 候选池：**同一 399 真实池**（whitelist 33 + Commons 366），与 V1/V2 完全相同；
- seed：20260831（与 V1/V2 一致）；锚定 query：20 镜英文查询（与 V1/V2 同源）；
- evaluation subset：152 条人工标注（冻结 73 + Phase 3 新增 79）；
- 三 ranking：
  - **A. Baseline**：production 只读复制（whitelist semantic_match 优先 + Commons search-order）；
  - **B. V1**：normalized token overlap（`0.7*title + 0.3*desc`，`semantic_score_v2` 原样）；
  - **C. V1.1**：`0.5 * bigram_phrase_overlap + 0.5 * normalized_token_overlap`；tiebreak `_order*1e-6`；
- **规则预注册**：不用任何 label 参与排序；不对失败案例手工加规则；不反向调参。

**V1.1 设计公式**：
```
semantic_score_v11 = 0.5 * |2-gram(anchor_query) ∩ 2-gram(title+desc)| / |2-gram(anchor_query)|
                   + 0.5 * semantic_score_v2
```

---

## 2. V1 vs V1.1 完整结果（三口径）

### 2.1 combined（152 条）

| 指标 | Baseline | V1 | V1.1 |
|---|---|---|---|
| Top-1 USABLE | 47.1% | **70.6%** | 52.9% |
| Top-3 USABLE | 58.8% | **88.2%** | 82.4% |
| Top-5 USABLE | 58.8% | **100%** | 100% |
| MRR | 0.585 | **0.821** | 0.707 |
| mean best-USABLE rank | — | 1.588 | 1.882 |
| pairwise separation | 40.0% | **73.3%** | 60.0% |
| **C1 total / C1 in Top-5** | 6 / **0** | 6 / **6（全部进 Top-5）** | 6 / 6 |

### 2.2 existing（73 条）

| 指标 | Baseline | V1 | V1.1 |
|---|---|---|---|
| Top-1 | 57.1% | 42.9% | 28.6% |
| MRR | 0.683 | 0.535 | 0.437 |
| separation | 45.5% | 100% | 100% |

### 2.3 new（79 条）

| 指标 | Baseline | V1 | V1.1 |
|---|---|---|---|
| Top-1 | 0.0% | 46.2% | 38.5% |
| MRR | 0.088 | 0.669 | 0.605 |
| separation | 60.0% | 60.0% | 40.0% |

**判定依据**：V1.1 在全部三个口径、全部核心指标（Top-1/MRR/separation）上均**低于 V1**——符合"明显恶化"的判据 → `RANKING_V1.1 = NOT_VALIDATED`。

---

## 3. Normalization / Phrase Matching 的收益与副作用

### 3.1 词形归一化（V1.1 与 V1 共用 V2 层）

| 原始 → 归一化 | 类别 | 影响 |
|---|---|---|
| corals → coral | ✅ 修复 | 直接解决 V1 已知缺陷 |
| bleaching/bleached → bleach | ✅ | 词形统一 |
| snorkeling → snorkel | ✅ | 词形统一 |
| species → specy | ⚠️ 误伤 | 词根受损（species 应与 specie 归并） |
| fishes → fishe | ⚠️ 误伤 | 词根受损 |
| beaches → beache | ⚠️ 误伤 | 词根受损 |

**副作用评估**：误伤为系统性（同一规则作用于 query 与候选两侧，同形可匹配），但 `species→specy` 类降低了"物种/鱼类"语义的表达完整性。**归一化本身是净收益（V1 已用），不是 V1.1 失败的原因。**

### 3.2 Phrase matching 的失败机制（已实证）

**2-gram 极端稀疏**——每镜锚定 query 的 2-gram 仅 1–3 个：

| shot | query | 2-grams |
|---|---|---|
| S05 | coral bleaching | `{'coral bleach'}`（仅 1 个） |
| S07/S11/S14/S15 | ocean acidification / coral restoration / clownfish anemone / ocean current | 各 1 个 |
| S12 | fishermen hauling nets shore | `{'net shore', 'haul net', 'fishermen haul'}` |

且**短语要求连续词序完全一致**：标题 "Fishing Village on the South Coast of Ternate" 的 2-gram 为 "fishing village"、"village on"… 而 query "fishing village coast" 的 2-gram 为 `{'fish village', 'village coast'}`——**词序变换即失配**（"fishing village" 要被归一化后对比，"Fish Village" 与 "fishing village" 候选侧出现在 "Fishing Village on..." 中，但 query 侧是 "fishing village" → "fish village"；候选是 "fishing village" → 归一化后 "fish village"... 实际应命中——但其他短语如 "village coast" 候选侧需出现 "village coast" 连续词序才命中，多数标题无此序列）。

**结论**：phrase 分量在大多数候选上命中率为 0 → V1.1 分数 ≈ 0.5*V2 + 0（对大量候选），而 0.5 的权重把 token 分数**压缩了一半**，使原本 V1 能区分的分数差距减半，排序退化为带噪声的 token 项 → **整体劣化**。

---

## 4. Failure Cases

1. **S12（渔民拉网）**：query 2-gram `{'net shore', 'haul net', 'fishermen haul'}`；真实照片标题 "Fishermen hauling a beach seine ashore at El Manglillo Bay" 归一化后 2-gram 含 "fishermen haul" ✅ 命中，但油画 "Fishermen on Shore Hauling in their Nets" 仅 "shore haul"? 不命中（"shore"+"hauling" 顺序在 normalized 后为 "shore haul"≠"haul net"）→ V1.1 无法区分两者；
2. **S16（海洋天气）**：TRMM 云图（USABLE）标题 2-gram 与 query "ocean weather climate" 的 `{'ocean weather', 'weather climate'}` 无连续词序命中 → V1.1 把它从前排拉低；
3. **C1 恶化**：6 个 C1（HIGH+NOT_USABLE，全为图表/地图/文档）在 V1 下已全部进入 Top-5，V1.1 同样 6/6 进 Top-5——**phrase 对 C1 无改善**（这些素材标题同样含 "coral bleaching"、"ocean acidification" 等短语短语），符合"phrase 无法拒绝图表类"的预期。

---

## 5. 是否值得进入下一轮

**V1.1 不值得继续。** 理由：
- 数据：三口径全部劣于 V1（Top-1 -17.7pp、MRR -0.114、separation -13.3pp，combined 口径）；
- 机制：2-gram 稀疏 + 词序严格匹配是结构性缺陷，非参数问题（调权重=反向调参，禁止）；
- 意义：V1.1 尝试证明"纯文本语义信号改进"无法解决 C1（图表/地图/文档类）——**这正是 VISUAL_SUITABILITY_BOTTLENECK 升级的证据，而不是排名器可修复的**。

**下一步候选（待人工裁决，本轮不做）**：
1. 独立视觉适用性通道（VLM/classifier/detector 的对比评估）——现已有 C1=7 的升级证据；
2. 若仍要文本层：放弃短语，保留 V1（纯 token+归一化），其 generalization 已 VALIDATED（Top-1 70.6%、MRR 0.821）；
3. supply-gap 6 镜（S02/S07/S08/S15/S18/S19）独立处理（RETRIEVAL 层）。

---

## 6. 对 VISUAL_SUITABILITY bottleneck 的影响

**无改变（维持 SUPPORTED）**，且 V1.1 的结果**进一步强化**它：
- C1 计数口径披露：**主池可见 C1=6**（Phase 4A combined 口径，topk_new 全为图表/文档类）；**全域 C1=7**（含冻结 GS 中 2 个 strict HN——`1899_Cross_Hauling`（渔夫油画）、`The_optical_feedback_loop`（白化机制示意图）——但这两个 constructed 探针不在真实 399 主池，故主池口径为 6）；
- 6 个主池 C1 全部为"语义 HIGH + 视觉 NOT_USABLE"的图表/地图/文档类；
- V1.1 的短语分量对这些候选无能为力（标题同样含命中短语）；
- **结论：视觉适合性判断需要语义信号之外的通道——文本层（token/短语）已达上限。**

---

## 7. Audit trail

- 实验脚本：`output/stage33/cv2/ranking_validation_v4/run_phase4a.py`
- 结果：`output/stage33/cv2/ranking_validation_v4/result.json`
- 复用：V2 的 `semantic_score_v2`/`build_real_pool`/`SHOTS_QUERY`（未修改）；冻结 GS `C70C82D4...`（未修改，脚本未触碰）
- 未修改任何 production 资产。

---

**Phase 4A 完成。结论：`RANKING_V1.1 = NOT_VALIDATED`（离线，不进入 production）。STOP，等待人工裁决。**

> 底层含义：文本语义信号（token/短语）对"视觉适合性"的表达已达上限；C1=6–7 的图表/地图/文档类素材是确定性语义排序无法拒绝的结构性盲区——下一轮可行方向是**独立视觉适用性通道**的评估（需另行授权），或转 RETRIEVAL（supply-gap）分支。
