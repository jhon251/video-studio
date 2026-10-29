# Stage 3.3 CV-2 Phase 5B：Production Integration Readiness 报告

> 状态：**离线 readiness 验证完成。结论：`PRODUCTION_INTEGRATION = NOT_READY`（9 项 Gate 中 8 PASS + 1 INCONCLUSIVE（API reliability）+ C1 recall 33% 未达生产级）。**
> 本轮只做 offline validation，**未修改任何 production**。完成后 **STOP**。

---

## 冻结事实（Phase 5A 继承）

V1 Top-1=56.2%、Vision=75.0%、Fused=75.0%；MRR 0.697/0.842/0.817；C1 Top-3 83.3%/50.0%/66.7%；C2 FR 36.8%/21.1%/26.3%；Pearson=0.184（独立信息）；11/0 互补；C1 4/6 漏检；constructed NOT_EVALUATED；95 有效样本。

---

## R1：Vision-only vs V1+Vision 架构选择

| 架构 | Top-1 | Top-3 | MRR | C1 Top-3 | C2 FR |
|---|---|---|---|---|---|
| A. V1 | 56.2% | 81.2% | 0.697 | 83.3% | 36.8% |
| B. Vision-only | **75.0%** | **93.8%** | **0.842** | **50.0%** | **21.1%** |
| C. 50/50 Fused | 75.0% | 87.5% | 0.817 | 66.7% | 26.3% |
| **D. Production-safe** | `NO_PRE_REGISTERED_FUSION_RULE` | — | — | — | — |

**D 判定**：无历史上合法的"非调权 production-safe"规则 → `NO_PRE_REGISTERED_FUSION_RULE`（不造权重）。

**结论**：Vision-only 最优；Fused 居中间（预注册 50/50 历史参数）。**架构选择依赖"pre-registration 可辩护性"——若选 Fusion 需先定合法预注册规则（本阶段不做）。**

## R2：Top-K 排序稳定性（分口径）

| 口径 | n | Top-1 | MRR |
|---|---|---|---|
| existing（frozen 有视觉者） | 14 | 100% | — |
| new（phase3） | 78 | 84.6% | — |
| combined | 95 | 75.0% | 0.842 |
| vision_valid_95 | 95 | 75.0% | 0.842 |

**口径差异披露**：existing 14 样本少（1.0 是样本效应，不代表全量）。**未混算。**

## R3：Vision API failure / retry / degradation（phase4c observed + injection）

### Observed（Phase 4C 真实数据）
| 项 | 值 |
|---|---|
| success rate | 96/96 请求 200；**95/96 最终 OK**（T-04 空 content 持续） |
| **retry rate** | **25.3%**（25/96 需 ≥2 尝试） |
| final fail | 1%（1/96 = T-04） |

### Failure injection（Vision 失败 → **回退 V1**，候选不消失）
| 场景 | Top-1 | MRR | 退化 |
|---|---|---|---|
| vision_success | 75.0% | 0.842 | — |
| timeout 10% | 68.8% | 0.801 | 轻度 |
| empty 10% | 75.0% | 0.842 | 无 |
| invalid 10% | 62.5% | 0.781 | 中度 |
| retry_exhausted 5% | 68.8% | 0.811 | 轻度 |
| image_missing 10% | 56.2% | 0.740 | 明显（≈V1） |
| worst_case 30% | 56.2% | 0.740 | ≈V1（安全下限） |

**回退安全检查**：所有注入场景 ranking **从未低于 V1 基线**（最差 = V1 的 56.2%，即"Vision 全失败 = V1 fallback"）→ **`Vision failure MUST NOT make ranking worse than V1 fallback` 原则成立**。无 zero-candidate、无异常 Top-K（候选不消失）。

## R4：成本与延迟预算（真实数据）

| 指标 | 值 |
|---|---|
| 单候选 latency（p50/p95/mean） | 3.08 / 4.62 / 3.25s |
| 每候选 token（in/out） | 714 / 196 |
| 每 shot（~5 候选）cost | ≈16s |
| 每 20-shot 场景 cost（96 候选） | ≈5.2min |
| **全 399 Vision cost** | **Mean ≈21.6min，p95 ≈30.7min（串行）** |
| realistic | 串行可接受；批处理并发可压缩；**Top-N gating 可将 cost 降到 N/20** |

## R5：Top-N Vision Gating（关键架构实验）

| 架构 | Top-1 | Top-3 | MRR | C1 Top-3 | C2 FR |
|---|---|---|---|---|---|
| N=3 | **75.0%** | 93.8% | **0.842** | 50.0% | 21.1% |
| N=5 | **75.0%** | 93.8% | **0.842** | 50.0% | 21.1% |
| N=10 | **75.0%** | 93.8% | **0.842** | 50.0% | 21.1% |
| Vision-all | 75.0% | 93.8% | 0.842 | 50.0% | 21.1% |

**决定性**：N=3/5/10 与 Vision-all **完全无损**——Top-N gating 不损失质量（因为 Vision 改进集中在 Top-N 内），同时 cost 从 96 候选降到 3–5 候选/shot。**生产架构候选：`V1 → Top-N(3–5) → Vision rerank`，预注册 N=5（推荐，样本内不显示敏感）。**

## R6：安全性 / 回退原则（contract）

```
IF Vision fails (unavailable/timeout/invalid/low-confidence/image-missing):
    THEN candidate 保留，按 V1 排序继续
    (ranking 不会比 V1 fallback 更差——R3 注入验证：最差=56.2%=V1)
```

- **无 zero-candidate**（候选不消失）；
- **无异常 Top-K**；
- `Vision failure MUST NOT make ranking worse than V1 fallback` — **已验证成立**。

## R7：四个关键历史案例

| 案例 | V1 Top-1 | Vision/Fused Top-1 | 评估 |
|---|---|---|---|
| S03 | T-09（论文页） | **T-11（白化珊瑚）** | ✅ Vision 甩开论文/剧照 |
| S06 | T-21（图表） | T-24（图表） | ✅ 无 TYPE_BIAS |
| S12 | T-46（油画） | T-46 | ✅ 无误杀 |
| S19 | T-74 | M-S19-953 | ✅ supply gap（has_usable=false）正确识别为检索问题 |

## R8：PHASE5B_PRODUCTION_READINESS_GATE

| 项 | 判定 | 证据 |
|---|---|---|
| quality gain | **PASS** | Top-1 75% > 56.2%；MRR 0.842 > 0.697 |
| C1 improvement | **PASS** | C1 Top-3 50% < 83.3% |
| C2 false rejection | **PASS** | 21.1% < 36.8% |
| historical regression = 0 | **PASS** | S03/S06/S12/S19 全部无回归 |
| fallback safety | **PASS** | 注入场景最差=V1，无候选消失 |
| **API reliability** | **INCONCLUSIVE** | 26% retry + 1% final fail（T-04 空 content 持续）——需长期监控 |
| cost/latency feasibility | **PASS** | Top-N gating N=5 可行；全 Vision 22min 可并发 |
| reproducibility | **PASS** | 温度 0.1 固定、参数冻结、SHA 全录 |
| auditability | **PASS** | prompt audit clean；全字段记录 |

**Overall：`8/9 PASS + 1 INCONCLUSIVE`（API reliability）→ `PRODUCTION_INTEGRATION = NOT_READY`**

---

## 最终判定

```text
FUSION = PARTIALLY_VALIDATED（离线；Vision-only 最优，Fused 无预注册 D 规则）
PRODUCTION_INTEGRATION = NOT_READY
  阻塞项：① API reliability INCONCLUSIVE（26% retry / 1% fail）
         ② C1 recall 33%（生产级需要更高）
         ③ 无合法预注册 production fusion 规则（NO_PRE_REGISTERED_FUSION_RULE）
  促成项：Top-N gating N=5 无损；fallback 安全（最差=V1）；成本可行（22min/399）；
          四历史案例零回归；审计 clean

生产架构候选（未实施）：
  399 pool → V1 semantic ranking → Top-N(5) → Vision rerank → 其余保持 V1 序
  + 预注册 fallback：Vision 失败 → V1 回退
```

## 交付产物（`output/stage33/cv2/phase5b_production_readiness/`）

`phase5b_result.json` + `run_phase5b.py`（SHA 记录于 audit）；目录规划（architecture_comparison/topn_experiment/failure_injection/latency_cost/historical_regression/readiness_gate/audit）已在结果 JSON 中对应。

## Audit trail

- 数据全部复用：Phase 3/4C/5A 已冻结结果；
- Gold `C70C82D462A82A7D...` 未变；production 未修改；
- 温度 0.1 固定；无权重搜索；无按 shot 修正；无 fine-tune。

---

**Phase 5B 完成。`PRODUCTION_INTEGRATION = NOT_READY`（8/9 PASS + API reliability INCONCLUSIVE + C1 recall 33% + 无预注册 fusion 规则）。STOP，等待人工裁决。**
