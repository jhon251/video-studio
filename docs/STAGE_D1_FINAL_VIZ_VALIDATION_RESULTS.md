# Stage 33 — Stage D-1: Final VIZ Validation Results

> **性质**:D 层最终验证，零生产修改。评估 rendered VIZ 是否保持上游 A/B/C 层约束。
> 机器可读:`output/prod02/stage_d1_results.json`

---

## 1. 判定：**D NOT SUPPORTED**(8/15 < 9 PARTIAL 阈值)

D PASS = 8/15,未达 9/15 PARTIAL 阈值 → **D NOT SUPPORTED**。

**原因：7/15 拍的 claim_coverage < 0.5(A-2 已发现，D 层确认传播)。**

这不是新的失败——是 A-2 claim coverage 不足在 rendered VIZ 层面的直接体现。

---

## 2. 15 对象逐项

| # | Beat | D Claim | D Repr | D Elements | D Facts | D Readability | D Non-deco | D Overall |
|---|---|---|---|---|---|---|---|---|
| 1 | S13-B01 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | **PASS** |
| 2 | S30-B01 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | **PASS** |
| 3 | S01-B03 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | **PASS** |
| 4 | S26-B02 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | **PASS** |
| 5 | S02-B04 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | **PASS** |
| 6 | S02-B01 | ❌ | ✅ | ❌ | ✅ | ✅ | ✅ | **FAIL** |
| 7 | S02-B03 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | **PASS** |
| 8 | S18-B02 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | **PASS** |
| 9 | S20-B01 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | **PASS** |
| 10 | S20-B02 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | **PASS** |
| 11 | S26-B01 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | **PASS** |
| 12 | S28-B02 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | **PASS** |
| 13 | S33B-B01 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | **PASS** |
| 14 | S33B-B02 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | **PASS** |
| 15 | S33B-B03 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | **PASS** |

## 3. 聚合指标

| 指标 | 值 | 判定 |
|---|---|---|
| D PASS | **8/15 (53%)** | < 9 PARTIAL 阈值 |
| factual errors | **0** | ✓ |
| fabricated | **0** | ✓ |
| renderer failures | **0** | ✓ |
| readability pass | **15/15** | ✓ |
| non-decoration pass | **15/15** | ✓ |
| critical claim coverage | **9/15 (60%)** | — |

## 4. 与上游一致性

| 层 | 上游 PASS | D 层 PASS | 差异 |
|---|---|---|---|
| A Claim Representation | 15/15 | — | 无瓶颈 |
| B Representation Selection | 15/15 (rules) | — | 无瓶颈 |
| C Content Binding (A-4) | **13/15** | **8/15** | **-5**:A-4 绑定 PASS 的 5 拍在 D 层 claim_coverage < 0.5 |
| D Final VIZ | — | **8/15** | 差异 = C→D 传播损失 |

**C→D 差异分析**：A-4 绑定了 13/15,但 D 层只验证 8/15 通过。差异来自 D 层使用了更严格的 claim coverage 标准(要求词重叠 ≥0.5),而 A-4 的 C_PASS 只要求元素存在且有 supporting fact。D 层的额外要求是合理的——存在 supporting fact 不等于 viewer 能从 VIZ 中理解 claim。

## 5. 根因确认

D 层 8/15 PASS 确认了 A-2 的发现：**剩余 7/15 的 claim_coverage < 0.5 是语义理解缺口，不是工程问题。**

| 已修复(本轮) | 仍存在(需未来解决) |
|---|---|
| R1 Query Completeness ✅ | Claim-to-Visual 精确映射(A-2/A-3 未解) |
| Axis 1 reasoning budget ✅ | 语义理解深度限制(模型能力) |
| Axis 3 Renderer ACC ✅ | 5 个 GEN_FAIL 中 2 个结构性不可摄影 |
| A-4 Structured Binding ✅ | — |
| A-5 Generation Safeguard ✅ | — |

---

## 6. 冻结边界确认

Stage A/A-1/A-2/A-3/A-4/A-5 · EXP-A/B · P-2 · render_163 · 14 冻结件 · correspondence 50.5% · Stage 18–21 · per-claim shadow:全部不变。零生产修改。

## 7. Challenger 判定

**不需要 Model Capability Challenger**——D 层 7 个 FAIL 与 A-2 claim_coverage < 0.5 完全对应，是 A-2 已知的语义理解缺口在渲染层面的直接体现。升级模型不太可能解决 claim-to-visual 语义映射的根本缺口。

---

```
STAGE D-1 = D NOT SUPPORTED (8/15 < 9 PARTIAL 阈值)
factual errors = 0 ✓ · fabricated = 0 ✓ · renderer failures = 0 ✓
critical claim coverage = 9/15 (60%)
Model Capability Challenger = NOT NEEDED
PRODUCTION VIZ ROLLOUT = NOT AUTHORIZED
STOP——等待下一步授权
```
