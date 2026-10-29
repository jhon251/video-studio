# RUN 03 POSTMORTEM + SYSTEM DECISION

---

## 1. Run 03 Production Summary

| 指标 | Run 01 | Run 03 | 差异 |
|---|---|---|---|
| 拍数 | 101 | 101 | = |
| 时长 | 526.17s | 526.17s | = |
| Correspondence | 98.02% | **50.5%** | -47.5pp |
| Factual errors | 0 | **0** | = |
| Fabricated | 0 | **0** | = |
| Misleading coverage | 高（generic-as-evidence） | **0%** | Run 03 优 |
| Evidence honesty | 低（generic 充当 evidence） | **高**（诚实标注） | Run 03 优 |
| HN route | 无 | **26 拍** | Run 03 新增 |
| VIZ route | 无 | **11 拍** | Run 03 新增 |
| Retrieval completeness | 51.8% | **100%** | R1 修复 |
| EVI mean | 未测 | **1.70** | 新指标 |
| NIS mean | 未测 | **1.66** | 新指标 |
| VIS mean | 未测 | **1.53** | 新指标 |

---

## 2. KPI Hierarchy（正式）

### Engineering KPI（已有，全部通过）

- retrieval completeness: 100%
- render success: 100%
- A/V sync: 0.2s
- subtitle: 100%

### Evidence KPI（新增，核心）

| 指标 | Run 01 | Run 03 | 更优 |
|---|---|---|---|
| Real Evidence Coverage | ~50% | **50.5%** | = |
| Honest Coverage | 不可测（无标注） | **83.2%** | Run 03 |
| Misleading Coverage | 高 | **0%** | Run 03 |
| Provenance Integrity | 部分 | **100%** | Run 03 |

### Visual Value KPI（新增）

| 指标 | Run 01 | Run 03 |
|---|---|---|
| EVI mean | 未测 | 1.70 |
| NIS mean | 未测 | 1.66 |
| VIS mean | 未测 | 1.53 |
| generic rate | 高 | **0%** |

### Production KPI

| 指标 | Run 01 | Run 03 |
|---|---|---|
| Narrative clarity | 中 | 中 |
| Pacing | 中 | 中 |
| Scientific credibility | 中 | **高**（全溯源） |

---

## 3. 最终结论

### Run01 vs Run03

**Run 03 represents a better production philosophy for the final system.**

- Run 01 的 98.02% correspondence 虚高：generic 被计入对应
- Run 03 的 50.5% 是诚实下界：每个对应都有真实照片证据
- Run 03 新增了诚实标注系统（角标/HN），使观众能区分证据与氛围

### 优化方向

**Evidence Value × Narrative Information ↑**

不是 Correspondence ↑。

---

## 4. P-2 Seal Delta Audit

| 字段 | 旧值 | 新值 | 变更原因 |
|---|---|---|---|
| old hash | `036d564a` | — | Stage A-1 前状态 |
| new hash | — | `8281f4ec` | A-1 人类确认后状态 |
| change reason | 人类确认 importance | | |
| exact changed fields | `human_confirmed_importance` (76 条 CRITICAL→确认/降级) | | |
| who authorized | 用户（项目负责者） | | |
| timestamp | 2026-09-06 | | |
| downstream affected | Run 02/03 assignment 均不受影响（P-2 仅存储 importance 标签） | | |
| production artifact invalidated | **无** | | |
| P2 UPDATE = | **NON-PRODUCTION-BREAKING** | | |

---

## 5. 剩余瓶颈

| 排名 | 瓶颈 | 证据 | 可修性 |
|---|---|---|---|
| 1 | Claim-to-Visual 语义映射精度（AI 无法精确建立 claim-element 绑定） | A-2: 7/15 cc<0.5 | 需更强模型或人类编辑 |
| 2 | 生成侧空元素列表 | S02-B01/S18-B02 | 可通过 safeguard 部分修复（A-5 已验证） |
| 3 | 免费图库覆盖缺口（BCI/临床/专有设备） | S16/S17/S32 | 不可通过 query 修复；需授权素材 |

---

## 6. 候选下一阶段（按 expected value 排序）

| 排名 | 候选 | 预期价值 | 成本 | 建议 |
|---|---|---|---|---|
| **1** | **可视化生成能力建设** | 高——11 个 VIZ 拍已确认有价值，但生产能力未建 | 中 | 需授权 |
| **2** | **Stage 22.12 人类评分者** | 高——验证 per-claim EQS 可靠性 | 低 | 需评分者到位 |
| **3** | **Claim-to-Visual 精度改进** | 中——改进 prompt/schema 提高精确映射率 | 低-中 | 可与 1 并行 |
| 4 | Retrieval precision | 低——R1 已修复，entity query 已验证 | 低 | 可选 |
| 5 | Production Run 04 | 取决于 1-3 | 高 | 等 1-3 完成 |

---

## 7. 最终建议

**不启动 Run 04。**

原因：Run 02/03 已确认两个关键结论——
1. 诚实路由 + 可视化路由是正确方向
2. 剩余瓶颈在 claim-to-visual 映射精度和可视化生产能力

下一步应先建设**可视化生成能力**（最高 ROI），同时完成**人类评分验证**（Stage 22.12），然后再进入 Run 04。

---

```
RUN 03 POSTMORTEM = COMPLETE
KPI Hierarchy 建立 · P-2 Seal Delta 审计完成 · 剩余瓶颈定位 ·
推荐：可视化生成能力建设 + 人类评分验证 → 然后 Run 04
STOP——等待授权
```
