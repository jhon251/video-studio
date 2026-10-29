# Stage 3.3 CV-2 Oracle-Pool / Ranking Validation 实验报告

> 状态：**Oracle-Pool 隔离实验完成（只定位瓶颈，不解决瓶颈）。** 未修改生产代码、Gold Standard、Gate、人工标签、CV-2 主实验结果、ranking 权重、任何过滤规则。
> 完成后 **STOP**，等待人工裁决。

---

## 1. 实验目标

回答唯一问题：

> 当系统已经拥有"真正可用素材（USABLE）"和"语义高度相关但视觉不可用素材（NOT_USABLE+HIGH）"时，当前 ranking 能否把真正可用素材排到前面？

用于区分 `RETRIEVAL_BOTTLENECK` / `RANKING_BOTTLENECK` / `VISUAL_SUITABILITY_BOTTLENECK`。

---

## 2. Oracle Pool 构造

| 项 | 值 |
|---|---|
| 来源 | 已冻结 Gold Standard（73 条人工标签），不新增素材 |
| 每 shot pool | 该 shot 在冻结 GS 中的**全部已标注候选**（whitelist + natural commons + constructed probes + historical failure） |
| 打乱 | 固定 seed **20260831**，每 shot 内 `random.Random(seed).shuffle`；不按 label/role/历史结果预排序 |
| 泄漏防护 | 人工 label 只在排序结束后用于 evaluation；排序函数只读 metadata（title/description/artist/source_url/semantic_match/打乱序）；缺失元数据保留缺失，不人为补"视觉类型" |
| Gold Standard SHA | `C70C82D462A82A7D4A3D3D35F80EE65748106AC9B57E4BB74AC81E34B9E448AC` |
| 结果 JSON | `output/stage33/cv2/oracle_pool_result.json`，SHA256 `90C8F26547A3D5DDB6BA0B6C60845671A1F46016C37FFBB2893E888680F5AEA5` |

**候选数量**：20 镜共 73 个已标注候选进入 oracle pool（每镜 1–6 个，多数 2–4 个）。

---

## 3. 三个 Variant

- **R1-A**（whitelist-only）：只保留 whitelist 候选，按 `semantic_match` 降序 —— 排除 Commons search-order 影响；
- **R1-B**（whitelist + search-order）：whitelist 有 `semantic_match` 优先，Commons 按打乱后顺序 —— 与正式 B 的排序结构同构；
- **R1-C**（+ deterministic visual filter）：R1-B + 与正式 C 完全相同的 `_visual_filter_hit`。**未新增任何过滤规则。**

---

## 4. Aggregate Metrics

| 指标 | R1-A | R1-B | R1-C |
|---|---|---|---|
| 有 USABLE 的镜数 | 9 | 14 | 12（2 个被 C 过滤） |
| **Top-1 命中 USABLE** | 6/9 = 66.7% | 7/14 = **50.0%** | 6/12 = 50.0% |
| Top-3 含 USABLE | 100% | 100% | 100% |
| Top-5 含 USABLE | 100% | 100% | 100% |
| MRR（best USABLE） | 0.796 | 0.726 | 0.722 |
| mean best-USABLE rank | 1.56 | 1.64 | 1.67 |
| mean first-NOT_USABLE rank | 1.50 | 1.59 | 1.62 |
| **USABLE 排在 NOT_USABLE 前的镜比例** | 3/6 = 50.0% | 4/11 = **36.4%** | 3/8 = 37.5% |
| false rejection（SP 被过滤） | 0 | 0 | **2**（Dendrogyra、M-S12-607） |
| C filter rate | 0% | 0% | 15.1% |

---

## 5. Per-shot 表（R1-B 主表；完整三变体见 JSON）

| shot | 候选数 | best USABLE rank | first NOT_USABLE rank | Top-1 label | Top-3 含 USABLE | Top-5 含 USABLE |
|---|---|---|---|---|---|---|
| S01 | 2 | 1 | — | USABLE/MEDIUM | ✓ | ✓ |
| S02 | 3 | — | 2 | NOT_USABLE/LOW | — | — |
| S03 ⚑ | 3 | 2 | **1** | **NOT_USABLE/LOW（剧照）** | ✓ | ✓ |
| S04 | 4 | 1 | 2 | USABLE/MEDIUM | ✓ | ✓ |
| S05 | 6 | 2 | 1 | NOT_USABLE/LOW | ✓ | ✓ |
| S06 | 4 | 1 | 3 | USABLE/MEDIUM | ✓ | ✓ |
| S07 | 3 | — | 1 | NOT_USABLE/LOW | — | — |
| S08 | 5 | 3 | 2 | NOT_USABLE/LOW | ✓ | ✓ |
| S09 | 6 | 1 | 2 | USABLE/HIGH | ✓ | ✓ |
| S10 | 2 | 2 | 1 | NOT_USABLE/LOW | ✓ | ✓ |
| S11 | 4 | 1 | 3 | USABLE/MEDIUM | ✓ | ✓ |
| S12 ⚑ | 6 | 1 | — | USABLE/MEDIUM | ✓ | ✓ |
| S13 | 2 | 2 | 1 | NOT_USABLE/LOW | ✓ | ✓ |
| S14 | 3 | 1 | 2 | USABLE/HIGH | ✓ | ✓ |
| S15 | 4 | — | 1 | NOT_USABLE/LOW | — | — |
| S16 | 2 | 2 | 1 | NOT_USABLE/LOW | ✓ | ✓ |
| S17 | 4 | 1 | 2 | USABLE/MEDIUM | ✓ | ✓ |
| S18 | 2 | — | 1 | NOT_USABLE/LOW | — | — |
| S19 ⚑ | 4 | — | 1 | NOT_USABLE/MEDIUM | — | — |
| S20 | 5 | — | 2 | NOT_USABLE/LOW | — | — |

（⚑ = 含 Historical Failure 的镜；"—" = 该镜 oracle pool 中无 USABLE 标注候选，**不参与 USABLE 相关指标**。）

**关键读数**：
- **6 个镜的池中根本没有 USABLE 候选**（S02/S07/S15/S18/S19/S20，加 S10/S13/S16 池中 USABLE 排在 NOT_USABLE 后）——这些镜"给了正确素材"的前提不成立，属于**检索/供给侧缺口**；
- **在"明确给了 USABLE"的镜中，仍有 6/11 镜 NOT_USABLE 排在 USABLE 前面**（S03/S05/S08/S10/S13/S16）——这是 ranking 失败的直接证据。

---

## 6. Historical Failure（三案例 × 三变体）

| Case | 人工标签 | R1-A | R1-B | R1-C |
|---|---|---|---|---|
| S03 × M-S03-162（电影剧照） | NOT_USABLE/LOW | rank 1 | rank 1 | **过滤**（rank null） |
| S12 × M-S12-607（渔民油画） | **USABLE/MEDIUM** | rank 1 | rank 1 | **过滤（误杀 USABLE）** |
| S19 × M-S19-954（沙滩孩子） | NOT_USABLE/MEDIUM | rank 1 | rank 1 | rank 1（未过滤） |

**一致结论**：三个历史失败案例在纯语义排序下全部 rank 1（S12 是人工认为可用所以 rank1 正确；S03/S19 是 NOT_USABLE 却 rank1 = 排序失败）。C 过滤对 S03 有效、对 S12 误杀（人工 USABLE）、对 S19 无效。

---

## 7. Strict HN（n=2 exploratory）

| candidate | R1-B | R1-C |
|---|---|---|
| `S12:1899_Cross_Hauling...Museum_of_Art`（渔夫油画，NOT_USABLE/HIGH） | rank 5 | **过滤** ✅ |
| `S05:The_optical_feedback_loop...`（白化机制示意图，NOT_USABLE/HIGH） | rank 6 | rank 6（**未过滤**）❌ |

与主实验一致：确定性过滤对"标题含 painting/museum 关键词"的陷阱有效，对"图表/示意图"类陷阱无效。

---

## 8. Type Strata（R1-B ranking 下，按人工 visual_type 分组）

| 类型 | n | USABLE | NOT_USABLE | mean rank(USABLE) | mean rank(NOT_USABLE) | Top-1 次数 |
|---|---|---|---|---|---|---|
| photo（海洋自然照片等） | 57 | 23 | 25 | 2.43 | 2.96 | 14 |
| painting/illustration | 2 | 2 | 0 | 2.00 | — | 0 |
| chart/diagram | 8 | 3 | 5 | 2.67 | 2.00 | 3 |
| film_still | 1 | 0 | 1 | — | 1.00 | 1 |
| document（PDF 扫描） | 3 | 0 | 3 | — | 2.00 | 2 |
| vector diagram | 1 | 0 | 1 | — | 6.00 | 0 |
| video | 1 | 1 | 0 | 2.00 | — | 0 |

**发现**：photo 类内部几乎无法区分（USABLE mean rank 2.43 vs NOT_USABLE 2.96，分离微弱）——**当前 ranking 信号对"同为照片"的可用/不可用无辨别力**；chart/diagram 中 NOT_USABLE 反而更靠前；film_still/document 全为 NOT_USABLE 且被置顶。

---

## 9. Failure Pattern（回答"是所有 shot 都差还是特定类型差"）

- **不是所有 shot 都差**：S01/S04/S06/S09/S11/S12/S14/S17 在有 USABLE 时能排进 Top-3；
- **差的是三类**：①池中无 USABLE 的镜（供给缺口，9 镜）；②有 USABLE 但 NOT_USABLE 抢先的镜（S03/S05/S08/S10/S13/S16，排序失败）；③类型陷阱（film_still/document 置顶、chart 混排）；
- **S03 是典型**：池里有 USABLE（Dendrogyra 柱状珊瑚，rank 2），但剧照（NOT_USABLE）仍排 rank 1——**给了正确素材也选不对**。

---

## 10. 证据强度判定

| 瓶颈假设 | 证据 | 判定 |
|---|---|---|
| **RANKING_BOTTLENECK** | 给了 USABLE 仍 50% Top-1 失败；11 镜中 6 镜 NOT_USABLE 排前；photo 类内分离微弱；失败模式与真实 B（SP Top-1 retention 33.3%）一致 | **SUPPORTED** |
| **VISUAL_SUITABILITY_BOTTLENECK**（作为独立层） | C 过滤对 1/2 Strict HN 有效、对 S19 无效、对 photo 类无辨别；但真实视觉理解未测 | **WEAKLY_SUPPORTED**（作为次级瓶颈） |
| RETRIEVAL_BOTTLENECK | 9 镜池中无 USABLE（供给侧确实存在缺口） | **WEAKLY_SUPPORTED**（作为次级瓶颈） |
| DIRECTOR_BOTTLENECK | 本轮无 Director 参与，无证据 | **NOT_SUPPORTED**（未测） |

**最终判定：`RANKING_BOTTLENECK`（SUPPORTED）**

> 定位结论：Oracle-Pool 证明**即使候选池已经包含人工确认可用的素材，当前 semantic ranking 在约一半的镜中仍把视觉不可用素材排在可用素材之前**。因此"真实 B 失败"的主因不是"没有召回好素材"（尽管部分镜确实供给不足），而是**排序信号无法表达 visual usability**——semantic_match 只覆盖 whitelist、Commons 无分数按打乱序、photo 类内无辨别力。

---

## 11. 最终决策树

```
Oracle 结果：情况 B（给了 USABLE 仍常把 NOT_USABLE 排前）+ 情况 C 迹象（A→B Top-1 66.7%→50.0%）+ 情况 D（C false rejection=2 复现）
⇒ RANKING_BOTTLENECK（SUPPORTED）
⇒ 下一步（待人工裁决，本轮不做）：
   ├─ 排序信号重建：为全部候选（含 Commons）建立可比较的语义分数，先于任何视觉模型
   ├─ 若重建后仍无法区分 photo 类内可用性 → 再评估独立视觉适用性通道（非关键词、非 CLIP-B/32）
   └─ 供给缺口（9 镜无 USABLE）单独处理（多路召回/查询扩展），不与排序混为一谈
```

---

## 12. 已知局限

1. **Oracle pool 由"已标注候选"构成**，多数镜仅 2–4 个候选；6 个镜池中无 USABLE 候选（标注覆盖率限制）——这些镜无法用于 ranking 判定，只能反映供给缺口；
2. **R1-A 仅 9 镜有 USABLE**，样本小；R1-B 14 镜同样属小样本实验；
3. **Top-1 口径**：oracle 用"Top-1 是否=USABLE"（binary）；主实验用"labeled Top-5 中 USABLE 占比"——两者不可直接比较，本报告并列呈现；
4. **打乱序模拟 search-order**：Commons 候选的 `_order` 来自固定 seed 打乱，不是真实 Commons search 返回序（后者不可复现且不固定），R1-B 复现的是"无分数候选按到达序排列"这一结构特征；
5. Strict HN n=2，仅探索性。

---

## 13. Audit trail

- Gold Standard 冻结版 SHA：`C70C82D4...`
- Oracle 脚本：`output/stage33/cv2_remediation/oracle_pool.py`（SHA256 `65B0F2CF...`）
- 结果：`output/stage33/cv2/oracle_pool_result.json`（SHA256 `90C8F265...`）
- seed=20260831；排序函数无 label 依赖；未修改任何生产/实验资产。

---

**实验完成。最终判定：`RANKING_BOTTLENECK`（SUPPORTED）。STOP，等待人工裁决。**
