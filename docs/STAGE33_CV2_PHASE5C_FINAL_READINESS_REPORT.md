# Stage 3.3 CV-2 Phase 5C：Final Readiness 报告

> 状态：**最终生产准入验证完成。结论：`NOT_READY`**（PHASE5C_FINAL_READINESS_GATE = 10 PASS + 2 INCONCLUSIVE，API reliability 为主要 blocker）。
> 本轮只做离线 readiness 验证，**未修改任何 production**。完成后 **STOP**。

---

## 一、最终裁决

```
READY_FOR_PRODUCTION_INTEGRATION?  NO（10 PASS + 2 INCONCLUSIVE 不足以放行）
READY_WITH_EXPLICIT_LIMITATIONS?   NO（API reliability INCONCLUSIVE 无法进入此状态——
                                      该状态要求其他全部 PASS 且限制可枚举）
NOT_READY?                          YES（按 Case C：API reliability 无法证明 → NOT_READY，
                                      不因其他 10 项 PASS 强势放行）
```

## 二、PHASE5C_FINAL_READINESS_GATE（12 项）

| Gate | 判定 | 证据 |
|---|---|---|
| quality_gain | **PASS** | Top-1 75% > 56.2%；MRR 0.842 > 0.697 |
| c1_behavior | **INCONCLUSIVE** | C1 recall 33%（2/6）；漏检 4 例为 C1-C/D（见 §BLOCKER2） |
| c2_false_rejection | **PASS** | 21.1% < V1 36.8% |
| historical_regression | **PASS** | S03/S06/S12/S19 零回归 |
| fallback_safety | **PASS** | 注入最差 = V1；候选不消失；Top-K 合法 |
| **api_reliability** | **INCONCLUSIVE** | 25% retry + 1% final fail；长期监控缺失 |
| cost | **PASS** | Top-5 gating；全池 22min 串行可并发 |
| latency | **PASS** | p50 3.08s / p95 4.62s |
| reproducibility | **PASS** | 温度 0.1、参数冻结、SHA 全录 |
| auditability | **PASS** | prompt audit clean；全字段记录 |
| architecture_determinism | **PASS** | A 为确定性流程 |
| failure_containment | **PASS** | per-candidate 隔离；异常不扩散 |

**10 PASS + 2 INCONCLUSIVE + 0 FAIL。**

## 三、BLOCKER 1：API Reliability（主要 blocker）

### Failure taxonomy（生效）

`SUCCESS / EMPTY_CONTENT / INVALID_JSON / TIMEOUT / IMAGE_UNAVAILABLE / RETRY_SUCCESS / RETRY_EXHAUSTED / BURST_FAILURE`

### 状态机（确定性）

```
request → validate → retry(max 4) → validate → fallback(V1)
```

### Hard safety invariant（全部 VERIFIED）

- `Vision failure → V1 fallback`：✅（任何失败候选按 V1 排序保留）
- **绝不** `Vision failure → candidate removal`：✅（zero-candidate = 0）
- fallback ranking ≥ V1 baseline：✅（最差注入 = V1 56.2% / MRR 0.740）
- Top-K 数量合法：✅
- exception 隔离：✅（per-candidate 独立请求）
- 每次失败有 audit record：✅（attempts 数组全记录）
- retry 次数固定（4）、timeout 固定（180s）、fallback 确定性：✅

### Observed（Phase 4C/5B 真实数据）

| 指标 | 值 | 判定 |
|---|---|---|
| success rate | 98.9%（95/96） | 高 |
| **retry rate** | **25.3%** | 高——**INCONCLUSIVE 主因** |
| final failure rate | 1.0%（1/96 = T-04 持续空 content） | 单个 |

**判定：`API_RELIABILITY = INCONCLUSIVE`**——25% 重试率在无长期监控下无法证明生产级可靠性。**上线前必须补充的监控指标**（如实列出，不假装 PASS）：
1. 连续运行 ≥30 天的 success/retry/fail 分布；
2. 失败分类分布（EMPTY vs TIMEOUT vs INVALID vs BURST）；
3. BURST 检测（连续失败数/窗口）与自动降级；
4. fallback 触发率与 ranking 退化监测；
5. p95 延迟稳定曲线（季节性/并发波动）；
6. 错误码分布（429/5xx/超时）与弹性策略。

## 四、BLOCKER 2：C1 Failure Analysis（核心答案）

```
Q: Vision 是"没看出来"，还是"看出来了但认为可以用"？
A: 看出来了，但认为可以用（4/6 漏检全部为 C1-C / C1-D）。
```

| C1 | 类型 | Vision 输出 | C1 分类 |
|---|---|---|---|
| T-28（酸化机制图） | diagram | NOT_USABLE/fit 0.2 | ✅ 检测成功 |
| T-31（生态分区图） | diagram | NOT_USABLE/fit 0.2 | ✅ 检测成功 |
| T-29（pH 折线图） | chart | **CONDITIONALLY**/fit 0.7 | **C1-C**（信息价值误判：pH 数据→认为可作说明画面） |
| T-57（洋流图 2月） | map | **CONDITIONALLY**/fit 0.45 | **C1-C** |
| T-58（洋流图 8月） | map | **CONDITIONALLY**/fit 0.6 | **C1-D**（reason 已说"无法呈现动态过程"→ 仍输出 CONDITIONALLY） |
| T-59（洋流 1943） | map | **CONDITIONALLY**/fit 0.6 | **C1-D**（reason"缺乏真实可拍摄感"→ 仍 CONDITIONALLY） |

**分类计数**：C1-A 0 / C1-B 0 / **C1-C 2** / **C1-D 2** / C1-E 0。

**本质**：模型识别了"图表/地图类型"与"缺乏真实感"，但认为它们有信息价值（数据说明）→ 输出 CONDITIONALLY（保守型错误）。**不是"没看出来"（类型识别成功），是"格式-镜头匹配的联合判断偏宽松"**。

**`DIRECTOR_REQUIREMENT_SIGNAL = CANDIDATE`**：漏检源于 shot requirement 表达不足（口播"洋流带来营养"未说明"需要动态/实拍画面"）——后续可离线验证 Director/Material Requirements Contract（**本阶段不修改 Director**）。

**禁止 TYPE RULE**：不建立 `chart/map/diagram/document → NOT_USABLE`（S06 实证 chart 可能是正确素材）——保持 `shot requirement × visual content` 联合判断。

## 五、BLOCKER 3：Fusion Rule / Architecture

| 架构 | 状态 |
|---|---|
| **A: `V1 → Top-5 → Vision rerank → Vision fail? → V1 fallback`** | **production candidate（预注册，N=5）** |
| B: `V1 → Top-5 → Vision gate/deterministic tie-break` | **`NO_PRE_REGISTERED_FUSION_RULE`**——无预注册 deterministic 规则，不人为制造 |

- 未搜索权重（40/60、30/70、grid/random/search 全部禁止）；
- N=5：Phase 5B 证明 N=3/5/10 质量一致，选 N=5，不重搜；
- Architecture A 的确定性：Vision 只 rerank Top-5，失败回退 V1，**不删除候选**。

## 六、Production Safety Contract（Architecture A）

```text
Input (399 pool)
  ↓
V1 semantic ranking
  ↓
Top-N = 5
  ↓
Vision evaluation (per candidate, 独立)
  ↓
Vision success?
  ├─ YES → Vision rerank Top-5
  └─ NO  → V1 Top-5 fallback（候选保留，V1 顺序）
  ↓
Final candidates（数量恒定，无删除）
```

- N=5（固定，不搜）
- Failure behavior：any Vision failure → return V1 ranking
- Candidate preservation：Vision 只 rerank/fallback，不删除

## 七、11 问回答

1. **当前最佳 production architecture**：`V1 → Top-5 → Vision rerank → V1 fallback`（A）；
2. **为什么不是 50/50 fusion**：Phase 5A 证明 Vision-only ≥ 50/50 Fused（Top-1 75% vs 75%、MRR 0.842 vs 0.817），且 Fusion 无预注册 D 规则；50/50 是历史参数但不优；
3. **Top-5 gating 为什么安全**：Phase 5B N=3/5/10 与 Vision-all 质量一致；候选不删除；失败回退 V1；
4. **Vision failure fallback**：V1 Top-5 回退（确定性，候选保留）；
5. **API reliability 是否足够**：**不足**（25% retry/1% fail，无长期监控）→ INCONCLUSIVE；
6. **C1 剩余失败**：4/6 为 C1-C/D（看出类型/风险但输出 CONDITIONALLY）——shot requirement 表达不足 + 模型对数据类素材偏宽松；
7. **production safety risk**：无 candidate-removal 类风险（invariant verified），但 API 间歇空响应（T-04）是运行时风险点；
8. **模型能力限制**：C1 漏检（33% recall）——具体是"format-requirement 联合判断"边界；
9. **工程 reliability 问题**：retry 25%、T-04 持续空 content（需监控/网络弹性）；
10. **是否需要继续 CV-2 实验**：需要（针对 API reliability 增加真实运行监控数据 + Director Requirements Contract 离线验证）——但**在本轮报告后停止**，不自动继续；
11. **最终状态**：**`NOT_READY`**。

## 八、Audit Trail

- Phase 5B 数据复用（未重复 API 请求）；Gold `C70C82D4...` 未变；
- 脚本：`run_phase5c.py`、`final_verdict.py`（SHA 录于 audit/）；
- 产物：`phase5c_final_readiness/`（reliability/c1_failure_analysis/architecture/historical/readiness_gate/audit）；
- 未修改：production/3.1.4/V3/Gate/Gold/标签；未调参；未按 shot 修正；无 keyword filter；无 CLIP。

---

**Phase 5C 完成。最终：`NOT_READY`（10 PASS + 2 INCONCLUSIVE；主 blocker = API reliability；次 blocker = C1 33% recall）。STOP，等待人工裁决。**
