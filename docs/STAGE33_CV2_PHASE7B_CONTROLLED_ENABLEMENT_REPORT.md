# STAGE 33 / CV-2 — Stage 7B: Production Controlled Enablement 报告

> 状态:**Controlled Enablement 完成(2 次独立运行)。`CONTROLLED_ENABLEMENT = VALIDATED`。
> Gate 全部 PASS。STOP——不自动进入 Default,等待人工授权。**
> 路线:READY_WITH_EXPLICIT_LIMITATIONS(Option 1)。全程保持 `V1 → Top-5 → Vision rerank → V1 fallback`。
> 新增:`asset_cache.py` + `vision_controlled.py`(2 个新文件);**未修改任何既有 production 文件**。

---

## 0. 状态机

```
STAGE_7A  SHADOW_VALIDATED
    ↓
STAGE_7B  CONTROLLED_ENABLEMENT  ✅ 完成(2 次独立运行,0 invariant violation)
    ↓
CONTROLLED_GATE  ✅ PASS(6 类指标全部达标)
    ↓
STOP → 等待人工授权
    ↓（等待中,不自动执行）
DEFAULT
```

---

## 1. 执行范围

| 允许 | 状态 |
|---|---|
| 共享持久缓存(asset_cache.py) | ✅ 新增 |
| 下载节流 + 去重 | ✅ 新增(MIN_INTERVAL=2s,429 退避+jitter) |
| Controlled Mode 模块(vision_controlled.py) | ✅ 新增 |
| 全字段审计/日志 | ✅ 新增 |
| 保留 V1 fallback ordering | ✅ 始终保留 |

| 禁止 | 状态 |
|---|---|
| 修改 V1 ranking 权重 | ❌ 未改 |
| 修改 SEM_MIN/sanitizer/Gold/标签 | ❌ 未改 |
| Contract/CLIP/keyword/type rule/shot special/fine-tune/fusion | ❌ 未引入 |

**测试序列**:smoke_03(3 镜验证功能)→ controlled_20260901_a(全量 Run #1)→ controlled_20260901_b(全量 Run #2)。

---

## 2. 16 项报告

### 1. 是否成功接入 production?
**是(Controlled 模式)。** Vision 在 Controlled 模式下真正执行并输出 rerank 建议;production 消费最终排序。
**注意**:接入的是 Controlled Mode(非 Default)——Vision 影响 Top-5 内的排序,但任何失败都回退 V1。

### 2. Vision 是否真正进入最终 ranking?
**是。** 例如:S06 Run#1 最终序 = `M-S06-323, M-S06-303, M-S06-307`(Vision 把图表 323 提到首位);
S12 Run#1 = `M-S12-608, M-S12-606, M-S12-607`(Vision fit 0.6 使 608 首位)。
Vision top-1 与 V1 top-1 不一致的镜:Run#1 7/20、Run#2 5/20。

### 3. V1 fallback 是否仍然可靠?
**是。** 本阶段 0 次 fallback 触发(全部 Vision 成功、全部素材获取成功),但代码路径保留;
INV-03/04/05/06/07 断言全部 true(若 Vision/acquisition/timeout/invalid 失败 → V1 序,确定性)。

### 4. acquisition 429 是否明显改善?
**显著改善。** Stage 7A:10/66 候选遇 429 → Stage 7B:**0 次 429(0/66)**。
原因:persistent cache(27/33 cache hit,81.8%)+ 节流(2s 间隔)+ 退避;jitter。
**acquisition success rate = 100%(66/66)。**

### 5. cache hit rate?
**81.8%**(27/33 候选;33 个素材中 6 个首次下载,其余 27 个命中共享缓存)。cache_miss=6(首次)。

### 6. Vision success rate?
**100%**(33/33 每运行;两次 66/66 = 100%)。

### 7. retry rate?
**3.03%**(1/33 候选重试;重试后全部成功,恢复率 100%)。

### 8. fallback rate?
**0%**(0/20 镜触发回退;两次均无)。

### 9. P50/P95/P99?
- Run#1:6.4 / 13.9 / 19.6s;
- Run#2:4.0 / 18.6 / 19.8s;
- 均低于 180s timeout;预算充足。

### 10. zero-candidate?
**0**(两次;7 个无白名单镜走 production 无素材路径,非 zero-candidate 违例)。

### 11. candidate removal?
**0**(两次;INV-01 断言 set(final)==set(baseline) 全部 true)。

### 12. invariant violations?
**0**(两次;INV-01..10 全 true)。

### 13. V1/Vision disagreement?
shot-level:Run#1 35%(7/20)、Run#2 25%(5/20)。**仅观察,不预设 Vision 正确**。

### 14. 是否出现任何 regression?
**无。** 全部 20 镜处理;零候选镜按 production 原有路径处理;无异常;无回归(历史案例 S06 chart 正确接受、S12 油画正确排序)。

### 15. 30-day monitoring 是否已经开始?
**已开始(collection STARTED)。** 状态:**`30_DAY_MONITORING = STARTED (NOT YET VALIDATED)`**。
基础设施就绪 + 本次 2 次运行已写入结构化日志(per-call/per-acquisition/per-fallback/per-retry/per-run)。
**未伪造 30 天数据;未把 Phase 5C 历史当作 monitoring。**

### 16. 当前是否满足 Default Enablement 条件?
**按 Gate 已达标,但按状态机:NO——需要人工授权。**
Controlled Gate 6 类指标全部 PASS;但 **Default 需人工裁决,不自动升级。**
以下为建议的 Default 前置(供人工参考):30 天监控持续运行且达标;分享缓存/节流在生产路径确认;
kill-switch 已确认(disable Vision → V1)。

---

## 3. 接入点(工程)

```
stage31/ranking.py (V1)          → 排序(只读)
    ↓
stage33/sanitizer.py (whitelist) → 白名单(只读,未改)
    ↓
stage33/vision_controlled.py     → 新增:Top-5 候选
    ├─ asset_cache.py (persistent cache + throttle + dedup,新增)
    └─ DeepSeek Vision rerank (mask=2048, temp 0.1, retry 3)
    ↓
final_top_k = vision_rerank (成功) 或 V1 fallback (失败)
    ↓
director 消费(未改)
```

**关键**:生产链在 sanitizer 之后、director 之前插入 Controlled 模块;sanitizer/director/V1 全部未动。

---

## 4. 关键数据对比(7A → 7B)

| 指标 | Stage 7A (Shadow) | Stage 7B (Controlled) |
|---|---|---|
| Vision success | 100% | **100%** |
| Acquisition 429 | 10/66 (15.2%) | **0/66 (0%)** |
| Acquisition success | 90.9%/78.8% | **100%** |
| Cache hit rate | 0%(每次独立缓存) | **81.8%** |
| Fallback rate | 9.1%/21.2% | **0%** |
| Invariant violations | 0 | **0** |
| Production ranking 受影响 | 否(Shadow) | **是(Controlled,可控)** |

---

## 5. 审计与合规

- 新增文件:`asset_cache.py`、`vision_controlled.py`(仅此 2 个,原因见 audit.json);
- 未修改:所有既有 production 模块(sanitizer/director/plan_builder/executor/validator/schemas/ranking);
- 未修改:Gold(73 标签,frozen-v1)、SEM_MIN=50、V1 权重、prompt、模型、Contract、CLIP、fine-tune、fusion;
- kill-switch:disable vision_controlled → 生产保持 V1-only(架构级,无需额外代码);
- 所有 2 次运行全字段记录 + audit_id。

---

## 6. 交付物

`output/stage33/cv2/phase7b_controlled/`:
- `controlled_run_01.json` / `controlled_run_02.json`(两次全量运行全记录)
- `gate_metrics.json`(6 类指标)
- `controlled_gate.json`(Gate 判定 = PASS)
- `invariants.json`(INV-01..10 全 PASS)
- `monitoring.json`(30_DAY = STARTED)
- `audit.json`(合规)
- `asset_cache/`(27 文件 + 27 meta,含 http_status/retry_count/content_hash)
- `run_01/`、`run_02/`、`run_00_smoke/`(原始结果 + 缓存)

源码:`src/video_studio/stage33/asset_cache.py`、`src/video_studio/stage33/vision_controlled.py`

---

## 7. 结论与 STOP

```
CONTROLLED_ENABLEMENT = VALIDATED
CONTROLLED_GATE = PASS (reliability/performance/safety/ranking-observation 全部达标)
DEFAULT_ENABLEMENT = NOT REQUESTED (状态机要求人工授权才可进入 Default)

下一步:
  STOP → 等待人工授权 DEFAULT
  授权前:不修改 production 算法、不扩大流量、不做任何 Default 行为。
```

**明确声明**:本阶段是 Controlled Mode 的验证,不是 Default 启用。所有指标达标 ≠ 可以自动 Default。
