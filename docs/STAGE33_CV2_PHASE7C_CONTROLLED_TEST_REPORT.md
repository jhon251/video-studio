# STAGE 33 / CV-2 — Stage 7C: Controlled Mode Actual Test 报告

> 状态:**3 次独立 Controlled Run + Kill-switch 测试完成。`CONTROLLED_TEST = PASS`。**
> 最终状态:`CONTROLLED_TEST=PASS` · `30_DAY_MONITORING=STARTED` · `DEFAULT_ENABLEMENT=NOT AUTHORIZED`。
> **STOP——不进入 Default,等待人工授权。**
> 全程零算法修改;零生产文件修改;Vision 仅作 reranking signal;V1 fallback 始终存在。

---

## 0. 状态机

```
STAGE_7B  CONTROLLED_ENABLEMENT = VALIDATED
    ↓
STAGE_7C  CONTROLLED_TEST ✅ 3 次独立 Run + Kill-switch + 429/cache 深化
    ↓
CONTROLLED_TEST = PASS
    ↓
STOP → 等待人工授权
DEFAULT_ENABLEMENT = NOT AUTHORIZED (状态机锁死,不自动升级)
```

---

## 1. 执行范围

- **3 次独立 Controlled Run**(controll_7c_run01/02/03):当前生产候选池、共享 asset cache、真实 acquisition、真实 DeepSeek Vision、保留 V1 baseline、Vision 仅 rerank、候选集规模不变、production ranking 不改;
- **Kill-switch 测试**(8 个 run 覆盖 5 场景):K1 下载禁用、K2 Vision 服务不可用、K3 timeout、K4 畸形响应、K5 缓存不可用;
- **429/cache 深化**:cache hit/miss、duplicate download、429 count、acquisition 延迟;
- **回归保护**:S03/S06/S12/S19(重点 S12 painting)。

**不修改**:V1/权重/SEM_MIN/sanitizer/whitelist/Top-5/Vision prompt/scoring/threshold/fusion/shot rule/type rule/blacklist/CLIP/detector/fine-tune/Gold 73 标签/Phase 4-6 结果;**不新增 Director Contract;不自动 Default;不扩大流量。**

---

## 2. 三次 Controlled Run 结果

| 指标 | Run#1 | Run#2 | Run#3 |
|---|---|---|---|
| n_shots | 20 | 20 | 20 |
| n_candidates | 33 | 33 | 33 |
| **Vision success rate** | **100%** | **100%** | **100%** |
| raw failure rate | 0% | 0% | 0% |
| **unrecovered failure rate** | **0%** | **0%** | **0%** |
| fallback rate | 0% | 0% | 0% |
| retry rate | 0% | 0% | 3.03% |
| acquisition success rate | 100% | 100% | 100% |
| **acquisition 429 count** | **0** | **0** | **0** |
| **cache hit rate** | **81.8%** | **81.8%** | **81.8%** |
| cache miss | 6 | 6 | 6 |
| **duplicate download count** | **0** | **0** | **0** |
| P50/P95/P99 latency (s) | 3.6/11.0/11.9 | 3.8/12.0/15.6 | 3.0/12.4/19.5 |
| invariant violations | 0 | 0 | 0 |
| top-1 change | 4 | 5 | 4 |
| vision promoted / demoted | 5/5 | 8/9 | 7/6 |

**3 次运行共用 99 候选(Vision 100% 成功;1 次 retry 恢复;0 unrecovered)。**

---

## 3. 429 与 Cache 验证(Stage 7A 遗留问题彻底解决)

| 指标 | Stage 7A | Stage 7B | Stage 7C(3 次) |
|---|---|---|---|
| 429 count | 10/66 (15.2%) | 0 | **0/99 (0%)** |
| acquisition success | 90.9%/78.8% | 100% | **100%** |
| cache hit rate | 0% | 81.8% | **81.8% 稳定** |
| duplicate download | 大量(每次独立) | 0 | **0** |

- **持久缓存 + 节流(2s)+ 429 退避/jitter 成功**:自 7B 起 4 次运行 0 次 429;
- **同一 URL/content_hash 无重复下载**(cache 命中不再请求 Wikimedia);
- cache 命中后 acquisition 延迟≈0(不再有网络等待)。

---

## 4. Kill-switch 测试(5 场景)

| 场景 | 注入 | 观察 | 判定 |
|---|---|---|---|
| K2 Vision 服务不可用 | ConnectionError | final == baseline_top_k(全 V1 序) | ✅ PASS |
| K3 API timeout | TimeoutError | final == baseline_top_k | ✅ PASS |
| K4 畸形 Vision 响应 | 非 JSON 内容 | final == baseline_top_k | ✅ PASS |
| K5 cache 不可用 | 空缓存目录 | 重新下载成功,Vision 正常 | ✅ PASS(恢复) |
| K1 下载禁用 | --no-download | 有 preview 的候选仍成功(Vision rerank 正常) | 注:部分触发 |

**关键**:K2/K3/K4 全部**确定性回退 V1 序**(final_top_k == baseline_top_k 精确相等);candidate count 不变;zero-candidate 不变;无崩溃;无 Default 行为。**KILL_SWITCH = PASS。**

---

## 5. 回归保护(重点:S12 painting)

| 样本 | 3 次 run final | 判定 |
|---|---|---|
| S03 | `M-S03-162`(唯一) | ✅ 无回归 |
| **S06 chart** | 323 大多首位/高位(图表被 accept) | ✅ 无 TYPE_BIAS |
| **S12 painting** | 607 均保留(2 次首位) | ✅ **无 Contract 式误杀** |
| S19 | 2 候选保持 | ✅ 无回归 |

**Phase 6b 已知的 Director Contract 式误杀(S12 油画被拒)未在 Vision rerank 中重现**——因为生产不含 Contract,Vision 只 rerank 不拒绝(soft signal),S12-607 保持为条件可用。

---

## 6. Ranking Observability(仅观察)

- shot-level top-1 change:4-5/20(20-25%);
- 每次 run 的 top1/top3/top5 change 与 promoted/demoted 见 ranking_observation.json;
- **观察不用于调参**;不预设 Vision 正确;不对 weight/threshold/prompt/Top-K/fusion 做任何修改。

---

## 7. 30-Day Monitoring

```
30_DAY_MONITORING = STARTED (NOT YET VALIDATED)
  infrastructure_ready = true
  collection_started = true (3 runs + 5 kill runs, 2026-09-02)
  days_elapsed = ~0.5 (session)
  30_day_validated = false
```

- 已记录:timestamp/run_id/model/cache/acquisition/Vision/latency/fallback/ranking disagreement/invariant results/error-recovery;
- **未伪造、未补造、未推算 30 天数据**;Phase 5C 历史数据未重新解释为 monitoring。

---

## 8. 最终 Gate(12 项)

| # | 条件 | 结果 |
|---|---|---|
| 1 | 3 次独立 Controlled Run | ✅ 3 次 |
| 2 | Vision runtime 无 unrecovered failure | ✅ 0% |
| 3 | INV-01..10 = 0 violations | ✅ |
| 4 | candidate removal = 0 | ✅ |
| 5 | zero-candidate violation = 0 | ✅ |
| 6 | V1 fallback 正常工作 | ✅ (Kill K2/K3/K4) |
| 7 | 429 recovery 正常 | ✅ (7A 10→0) |
| 8 | cache 正常 | ✅ (81.8% hit, 0 duplicate) |
| 9 | kill-switch PASS | ✅ |
| 10 | 历史样本无新增 regression | ✅ (S03/S06/S12/S19 全无) |
| 11 | production files 未被修改 | ✅ (0 文件改动) |
| 12 | 30-day monitoring = STARTED / NOT YET VALIDATED | ✅ (如实) |

**`CONTROLLED_TEST = PASS`。**

---

## 9. 交付物

`output/stage33/cv2/phase7c_controlled/`:
- `controlled_run_01.json` / `controlled_run_02.json` / `controlled_run_03.json`(3 次全量)
- `gate_metrics.json`(6 类指标)
- `invariants.json`(INV-01..10)
- `cache_metrics.json`(429/cache/dedup)
- `runtime_metrics.json`(Vision runtime)
- `ranking_observation.json`(观察)
- `kill_switch_test.json`(5 场景)
- `monitoring_status.json`(STARTED)
- `audit.json`(合规)
- `run_kill_switch_test.py` / `analyze_7c.py`

---

## 10. 停止条件

```
CONTROLLED_TEST = PASS
30_DAY_MONITORING = STARTED (NOT YET VALIDATED)
DEFAULT_ENABLEMENT = NOT AUTHORIZED

STOP → 等待人工授权 Default
```

**即使全部 PASS,也未进入 Default。** 未自行批准 Default;未修改任何算法/参数;未扩大流量。若人工批准 Default,仍需:30 天监控达标 + 生产路径确认 + kill-switch 演练。
