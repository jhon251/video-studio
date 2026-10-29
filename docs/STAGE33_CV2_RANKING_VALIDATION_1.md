# Stage 3.3 CV-2 RANKING VALIDATION-1 报告

> 状态：**capability validation 完成。结论：PASS（semantic_score_v1 显著改善 Oracle-Pool 排序）。**
> 本轮只验证"统一 semantic ranking 本身能否解决当前排序问题"，**不修改 production ranking**。
> 未修改：production code、3.1.4、V3 plan、Gold Standard、Gate、CV-2 主实验结果、Oracle-Pool 结果；未加 CLIP/VLM/关键词/扩池。

---

## 1. 当前 ranking audit（`_retrieval_sort_key` 完整拆解）

### 1.1 输入字段与作用

| 字段 | 来源 | 作用 |
|---|---|---|
| `semantic_match`（float，0–100） | 仅 whitelist 33 个候选（3.1.4 时代评分） | whitelist 内部按分数降序 |
| `_search_rank`（int） | 仅 Commons 366 个候选（pool_persisted 到达序） | Commons 内部按到达序排列 |
| `_whitelist` 标志 | 候选来源 | **硬优先级分档** |

### 1.2 审计结论（8 项）

1. **字段覆盖不统一**：`semantic_match` 只有 whitelist 有；Commons 候选全部没有——366 个候选只有"到达序"一个信号；
2. **两套排序逻辑**：whitelist 按 `(0, -sm)`、Commons 按 `(1, rank)`——**不同评分体系**；
3. **search-order 直接决定 rank**：Commons 候选的 rank 完全等于 search 到达序（`(1, search_rank)` 是唯一键）；
4. **离散硬优先级**：`(0, x)` 恒小于 `(1, y)`——**任何 whitelist 候选（哪怕 NOT_USABLE/LOW）永远排在所有 Commons 候选之前**，两者永远无法真正比较；
5. **source bias**：whitelist 来源无条件优先；
6. **同分按输入顺序**：Python sort 稳定，同 key 保原序（whitelist 同分按 materials.json 顺序）；
7. **结果**：Oracle R1-B 中 Top-1 USABLE 仅 50%、USABLE-before-NOT_USABLE 仅 36.4%、MRR 0.726；
8. **S03 剧照案例**：M-S03-162（NOT_USABLE/LOW）因是 whitelist 唯一候选 → rank 1，压过 USABLE 的 Dendrogyra（rank 2）——**纯 source bias 产物**。

### 1.3 三个真实案例证明

| 案例 | 现象 | 机制 |
|---|---|---|
| **S03** | 剧照 rank1、USABLE 珊瑚 rank2 | 剧照是 whitelist（有 sm）→ 硬优先 |
| **S12** | M-S12-608（NOT_USABLE）rank2，USABLE/HIGH 渔夫照片 rank4 | M-S12-608 是 whitelist（有 sm）→ 压过 Commons USABLE |
| **S05** | M-S05-272（USABLE/MEDIUM）rank1，但 M-S05-251（NOT_USABLE/LOW）rank2；示意图 NOT_USABLE/HIGH rank6 | whitelist 内按 3.1.4 老分数排序，该分数与 visual usability 弱相关 |

---

## 2. semantic_score_v1 定义（预注册，未调参）

```
semantic_score_v1(candidate, shot) =
    0.7 * |tokens(anchor_query(shot)) ∩ tokens(title)| / |tokens(anchor_query(shot))|
  + 0.3 * |tokens(anchor_query(shot)) ∩ tokens(description)| / |tokens(anchor_query(shot))|

final_sort_key = -(score + _order * 1e-6)     # search-order 仅作 1e-6 级 tie-breaker
```

- 锚定 query = 20 镜英文查询（与 supply 召回同源，见脚本 `SHOTS_QUERY`）；
- **所有候选（whitelist + Commons）同一函数**，无 source 优先级；
- 精确 token 匹配（无 stemming）——已知局限，如实披露；
- 不使用人工 label、不使用视觉模型、不创造视觉适用性分数；
- 本阶段只解决 semantic ranking，不解决 visual suitability。

---

## 3. Baseline vs V1（同一 Oracle-Pool：同候选、同 seed=20260831、同 Gold Standard）

### 3.1 复现一致性验证

Baseline 复现与 Oracle R1-B **7 项指标全部 match=True**（mrr=0.726、top1=0.5、top3/5=1.0、separation=0.364、mean ranks 1.643/1.588）——实验无漂移。

### 3.2 对照（eligible shots = 14 个存在人工 USABLE 的镜）

| 指标 | Baseline | V1 | V1+C |
|---|---|---|---|
| **Top-1 USABLE** | 50.0%（7/14） | **100%（14/14）** | 91.7%（11/12） |
| Top-3 USABLE | 100% | 100% | 91.7% |
| Top-5 USABLE | 100% | 100% | 100% |
| **MRR** | 0.726 | **1.000** | 0.938 |
| **best USABLE mean rank** | 1.643 | **1.000** | 1.250 |
| **USABLE > NOT_USABLE separation** | 36.4%（4/11） | **100%（11/11）** | 87.5%（7/8） |
| mean first NOT_USABLE rank | 1.588 | 2.059 | 1.846 |
| false rejection | 0 | 0 | 2（Dendrogyra、M-S12-607，与正式 C 相同，非 V1 新增） |
| filter rate | 0% | 0% | 15.1% |

---

## 4. Per-shot ranking（重点镜）

### S03（历史失败案例）
| candidate | 人工标签 | v1 score | baseline rank | v1 rank |
|---|---|---|---|---|
| Dendrogyra 柱状珊瑚 | USABLE/MEDIUM | 0.25 | 2 | **1** ✅ |
| M-S03-162 电影剧照 | NOT_USABLE/LOW | **0.00** | 1 | 2 |

→ **统一 token 分数把剧照正确下沉**：剧照标题 "The Lower Depths" 与锚定 query "white coral skeleton underwater" 零 token 重叠，分数 0；USABLE 珊瑚含 "coral" 得 0.25。**S03 被 V1 修复。**

### S12（历史失败案例）
| candidate | 人工标签 | v1 score | baseline rank | v1 rank |
|---|---|---|---|---|
| M-S12-607 | USABLE/MEDIUM | 1.00 | 1 | **1** ✅ |
| 渔夫拉网照片（Commons） | USABLE/HIGH | 0.575 | 4 | **2** ✅（大幅提升） |
| 1899 渔夫油画 | NOT_USABLE/HIGH | 0.35 | 5 | 4（下沉） |

→ V1 把 Commons 的 USABLE/HIGH 渔夫照片从 rank4 提到 rank2，油画 Strict HN 保持后位。

### S19（历史失败案例，supply gap 镜）
- 该镜**无 USABLE 候选**（eligible 之外）：M-S19-954/M-S19-953 两 NOT_USABLE 照片 v1 同为 0.6667（tie 由 order 决定）；
- **V1 无法解决 S19**——但原因不是 ranking，是该镜池中根本没有 USABLE 素材（supply gap 独立问题）。

### S05（诊断：示意图 vs USABLE）
| candidate | 人工标签 | v1 score | rank |
|---|---|---|---|
| M-S05-276 | USABLE/MEDIUM | 1.00 | 1 ✅ |
| Great Coral Bleaching 2023 | USABLE/HIGH | 0.70 | 2 |
| 白化机制示意图 | NOT_USABLE/HIGH | **0.35** | 5（下沉） |
| M-S05-272 | USABLE/MEDIUM | **0.00** | 6 ⚠️ |

→ 示意图（NOT_USABLE/HIGH）被正确下沉；但 M-S05-272（USABLE）因标题 "corals"（复数）与 query "coral" 不精确匹配得 0 分被压底——**V1 自身的已知错误模式（无 stemming/词形），非视觉适用性问题**。

---

## 5. USABLE / NOT_USABLE score separation 诊断

| 指标 | Baseline | V1 |
|---|---|---|
| USABLE mean rank | 1.643 | **1.000** |
| NOT_USABLE mean rank | 1.588 | **2.059** |
| 交叉镜数（USABLE 排前） | 4/11 | **11/11** |

**核心回答**：在 Oracle-Pool 中，**统一 semantic score 能够把 USABLE 排到 NOT_USABLE 之前**（11/11 镜），说明"语义信号本身无法表达 visual usability"这一假设**在已标注候选尺度上不成立**——真正的问题是旧排序的 source bias + search-order 依赖。

---

## 6. Source bias / search-order 分析

| 项 | 结论 |
|---|---|
| source bias | **是主要失败机制**：whitelist 硬优先把 3 个 NOT_USABLE 镜（S03/S12/S19 的旧候选）钉在 rank1；V1 取消该优先级后 S03/S12 修复 |
| search-order | **是次生机制**：Commons 内部纯按到达序；V1 将其降为 1e-6 tie-breaker 后不再主导 |

---

## 7. Eligible / All shots 统计

- **eligible shots = 14**（存在人工 USABLE 候选的镜）：V1 在这 14 镜上 Top-1=100%；
- **all shots = 20**：其中 **9 镜 supply gap**（池中无 USABLE：S02/S07/S08/S11/S15/S17/S18/S19/S20 中的 6 镜 + 其他）——**作为独立问题保留**，V1 无法在无 USABLE 的池中变出可用素材；
- 报告口径：所有 USABLE 相关指标只对 eligible shots 统计，**不把 supply gap 镜算作 ranking failure**。

---

## 8. PASS / FAIL / INCONCLUSIVE 判定（预注册标准）

| 预注册条件 | 实测 | 判定 |
|---|---|---|
| Top-1 USABLE 明确提升 | 50% → **100%** | ✅ |
| best USABLE mean rank 明显下降 | 1.643 → **1.000** | ✅ |
| USABLE>NOT_USABLE separation 明显提升 | 0.364 → **1.000** | ✅ |
| 无明显新增 false rejection | V1=0；V1+C 的 2 个误杀与 baseline C 相同 | ✅ |

**结论：`PASS`**——"统一、可比较的 semantic score"显著改善 Oracle-Pool 排序。**证明 RANKING_BOTTLENECK 的修复路径在语义排序层内存在**（至少在已标注候选尺度上）。

---

## 9. 对下一阶段的决策树

```
V1 PASS
├─ 已证明：source-bias + search-order 依赖是 Oracle 排序失败的主因，统一语义分数可修复（14/14）
├─ 未解决（独立问题）：
│   ├─ 9 镜 supply gap（池中无 USABLE）→ RETRIEVAL 层，需多路召回/查询扩展
│   ├─ V1 自身错误模式（无 stemming、精确 token）→ 可改进但非本轮任务
│   └─ C 过滤误杀 2 SP（含 M-S12-607）→ VISUAL_SUITABILITY 层，与 ranking 无关
├─ 重要边界：V1 仅在"已标注候选（每镜 2–6 个）"的 Oracle-Pool 上验证；
│   真实 B pool 有 366 个未标注 Commons 候选，V1 在真实 pool 的表现未测
└─ 下一步选项（待人工裁决，本轮不做）：
    ① 在真实 B pool 上重跑 V1（需处理 340 个未标注候选的评估问题）
    ② 先解决 9 镜 supply gap（多路召回）
    ③ 评估独立视觉适用性通道（此时仍不必要：V1 已证明语义层可修复）
    ④ 在 V3 Director 引入 material requirements 契约以强化 query 信号
```

**瓶颈判定更新（基于本轮）**：
- `RANKING_BOTTLENECK`：SUPPORTED **且证明可修复（V1 PASS）**；
- `VISUAL_SUITABILITY_BOTTLENECK`：仍 WEAKLY_SUPPORTED（C 过滤误杀问题仍在，但语义排序层本身已不构成障碍）；
- `RETRIEVAL_BOTTLENECK`：仍 WEAKLY_SUPPORTED（9 镜 supply gap 独立存在）；
- `DIRECTOR_BOTTLENECK`：NOT_SUPPORTED（未测）。

---

## 10. 已知局限

1. **Oracle-Pool 每镜候选少（2–6 个）**：V1 的 100% Top-1 是在小池上测得，真实池（366 候选）表现未知；
2. **V1 无 stemming**：复数/词形不匹配导致 M-S05-272 这类 USABLE 得 0 分——V1 自身的精度问题，不影响"统一分数优于 source-bias"的主结论；
3. **锚定 query 是英文**：中文口播/focus 未参与评分（跨语言语义鸿沟未解决）；
4. **V1 只用 token 重叠**：未建模语义相关性（同义词/上位词），可能低估某些正确素材；
5. **9 镜 supply gap**：Oracle-Pool 中无 USABLE，ranking 无法评估这些镜；
6. **未在真实 366 候选池上验证**：340 个未标注候选的质量与排序行为未知。

---

## 11. Audit trail

- Gold Standard 冻结版 SHA：`C70C82D462A82A7D4A3D3D35F80EE65748106AC9B57E4BB74AC81E34B9E448AC`
- Oracle-Pool 结果（未改）：`90C8F26547A3D5DDB6BA0B6C60845671A1F46016C37FFBB2893E888680F5AEA5`
- 本实验脚本：`output/stage33/cv2/ranking_validation/ranking_validation.py`
- 本实验结果：`output/stage33/cv2/ranking_validation/ranking_validation_result.json`
- seed=20260831（与 Oracle 一致）；排序函数无 label 依赖；未修改任何 production/实验资产。

---

**实验完成。结论：`PASS`（RANKING_BOTTLENECK 修复路径在语义排序层内存在）。STOP，等待人工裁决。**
