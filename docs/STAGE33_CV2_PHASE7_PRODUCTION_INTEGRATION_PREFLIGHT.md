# STAGE 33 / CV-2 — Phase 7: Production Integration Preflight(设计预检)

> 状态:**Preflight 完成(设计先行)。未修改任何 production 代码。**
> 路线:**READY_WITH_EXPLICIT_LIMITATIONS(Option 1:不引入 Director Requirements Contract)**。
> 依据:Phase 6b 最终裁决(API_RELIABILITY=VALIDATED;CONTRACT=NOT_VALIDATED→排除出生产)。
> 本轮只产出设计/规格/审计,不执行生产修改;执行需人工授权(见 §7)。

---

## 0. 审计背景(生产现状只读检查)

| 环节 | 现状 | 结论 |
|---|---|---|
| V1 语义排序 | `stage31/ranking.py`(semantic_match + final_score,3.1.4 权重冻结) | ✅ 生产已有 V1 排序 |
| 素材包 | `stage31_realworld/coral/material_pkg_real/`(metadata/materials.json + shot_mapping/all_shots.json) | ✅ 每镜 primary/alternatives |
| 白名单 | `stage33/sanitizer.py`:`rights∈{SAFE,CONDITIONAL∧commercial_use}` ∧ `semantic_match≥SEM_MIN(50)` | ✅ 安全边界(3.1.4) |
| **Vision rerank** | **production 无此环节** | ⚠️ 待集成 |
| Director | `stage33/director.py`(v3-mvp,吃 whitelisted_candidates) | 不受影响 |
| 素材本地图像 | `material_pkg_real/materials/` **仅 7 个预览图**;多数候选只有 source/download URL | ⚠️ LIM-06 工程缺口 |

**集成点**:`sanitizer.build_whitelist()` 产出每镜 `whitelisted_candidates` 之后、`plan_builder/director` 消费之前,
按 V1 序取 Top-5 送入 Vision rerank(soft signal)。

---

## 1. 冻结架构(严格)

```
V1 semantic ranking → Top-5 gating → DeepSeek Vision rerank → V1 deterministic fallback
```

- **V1**:召回/一阶排序(3.1.4 冻结权重,不改);
- **Top-5**:每镜最多 5 候选送 Vision(N=5 预注册,Phase 5B R5 已证 N=3/5/10 无损,不重搜);
- **Vision**:仅 Top-5 内 **soft rerank signal**;
- **Fallback**:任何 failure/timeout/empty/invalid/image-missing/exception → 完整回退 V1 原序;
- 禁止:删除候选 / zero-candidate / 劣于 V1 / 50/50 fusion / 未预注册权重 / CLIP / detector /
  黑名单 / Director Contract / shot-specific rule / 改 Gold/标签/Gate/历史结果。

详见 `phase7_production_integration/architecture.json`。

---

## 2. Vision 的 production role(关键语义)

```
Vision = soft ranking signal / reranking signal
       ≠ hard visual safety filter
```

**明确禁止**:
- `NOT_USABLE → 删除候选`;
- `HIGH + 某媒介 → 自动拒绝`;
- `chart/map/diagram → 自动拒绝`;
- 按 narration 类型建立硬编码媒体规则;
- 按历史失败案例建立特判。

**必须保留的已验证行为**:S06 chart 接受、S12 painting 条件接受、M-S03-162 剧照拒绝(内容否定,非类型规则)。

正确生产语义:

> **Vision 可以改善排序,但不能保证视觉素材绝对适用。**

---

## 3. 已知限制(显式写入 limitation_registry.json)

| ID | 限制 | 严重度 |
|---|---|---|
| LIM-01 | C1 recall ≈ 33%(模型边界,Phase 5C) | 已知模型边界,接受(Option 1) |
| LIM-02 | Vision 不是完整 visual suitability classifier | 已知模型边界 |
| LIM-03 | Vision score 是 soft signal,非"视觉安全证明" | 信号使用边界 |
| LIM-04 | 对 chart/map/diagram 存在"看见内容仍认为可用"边界(C1-C/D) | 已知模型边界 |
| LIM-05 | Director Requirements Contract:V1.1 NOT_VALIDATED → **不进入生产** | 设计未就绪(排除) |
| LIM-06 | 素材本地图像缺口(仅 7 个预览图,多数需下载) | 工程缺口 |
| LIM-07 | 部分镜候选 < 5(如 S01 仅 1 个) | 工程注意 |
| LIM-08 | C2 false rejection 21.1%(Phase 5A 冻结) | 已知模型边界(由于"仅 rerank+fallback 保留全部候选",候选不消失) |

生产系统正确理解:
- 不保证所有 HIGH semantic relevance 的视觉不适素材都会被过滤;
- 不把 Vision 分数解释成"视觉安全证明"。

---

## 4. API 可靠性(Phase 6b 已验证基线)

| 指标 | 值 | 来源 |
|---|---|---|
| final success rate | 20/20 = 100% | Phase 6b reliability_postfix |
| raw failure rate(首尝试) | 5% | 同上(model reasoning 波动,L2→L3→恢复) |
| protocol/client failure rate | 0% | 同上 |
| true API failure rate | 0% | 同上 |
| recovery rate | 100% | 同上 |
| final unrecovered failure rate | 0% | 同上 |

**生产协议参数(不得恢复旧误配)**:
`max_tokens=2048`(覆盖 hidden reasoning + JSON)、`temperature=0.1`、`max_retries=3`、`timeout=180s`、
固定 `Authorization`(无变量遮蔽)、原始图像字节(不重编码)。

**废弃数据声明**:Phase 5B 的 25.3% retry / 1% final fail 与 Phase 6 Track A 的 20% retry / 5% fail
**全部是 max_tokens=128/512 配置问题的表象**,已由 Phase 6 根因诊断 + Phase 6b 复测推翻。
**不再作为当前 API reliability 结论使用**。

详见 `runtime_contract.json`。

---

## 5. 可观测性(13 项指标 + 运行时不变量)

指标(observability_spec.json):请求计数 / success-retry-fallback 计数 / latency P50P95P99 /
empty-content 计数 / invalid-JSON 计数 / timeout 计数 / image-missing 计数 / fallback rate /
Top-5 gating rate / rerank rate / V1-Vision rank disagreement rate / candidate-count invariant /
zero-candidate invariant。

**运行时不变量(hard)**:
```
Vision failure MUST NOT make ranking worse than V1 fallback
```
(Phase 5B R3 注入已证:所有失败场景 ranking ≥ V1 基线 56.2% / MRR 0.740)

详见 `observability_spec.json` + `invariants.json` + `fallback_contract.json`。

---

## 6. 生产 rollout(分阶段,不一步到位)

| 阶段 | 描述 | Gate |
|---|---|---|
| **A. Shadow Mode** | Vision 全量运行但**不影响** production ranking;记录 V1/Vision ranking、disagreement、latency、failure、fallback | 线上协议稳定:success≥98%、true API failure=0%、unrecovered=0%、zero-candidate=0、p95≤5s;≥2 次生产运行 |
| **B. Controlled Enablement** | Vision 允许影响 Top-5 rerank,V1 fallback 保持;监控 + kill-switch | 无 invariant 违规;rerank 发生;fallback 在阈值内;质量无回归;≥2 次 |
| **C. Production Default** | 仅 A+B 全部 PASS 后,成为默认路径 | 30 天连续监控(Phase 5C 要求)达标 |

详见 `rollout_plan.json`。**任何一环 Gate 不满足 → STOP 并报告,不强制推进。**

---

## 7. 预检结论(preflight_result.json)

```
PREFLIGHT = PASS(设计层面)
PRODUCTION_INTEGRATION = 待人工授权(设计已完成,未执行任何生产修改)
```

| 检查项 | 结果 |
|---|---|
| 架构冻结 | ✅ 严格 `V1 → Top-5 → Vision rerank → V1 fallback` |
| 无算法改动 | ✅ 未调 threshold/weight/N/prompt;未加 blacklist/contract/CLIP;未重跑 Phase 4–6 |
| 已知限制写入 | ✅ limitation_registry.json(8 项) |
| API 协议冻结 | ✅ max_tokens=2048 / temp 0.1 / retry 3;废弃旧参数 |
| 可靠性基线 | ✅ Phase 6b 20/20;true API failure 0%;unrecovered 0% |
| 回退安全 | ✅ Phase 5B 注入:所有场景 ≥ V1 基线 |
| 可观测性 | ✅ 13 指标 + 硬不变量 |
| Rollout 分级 | ✅ Shadow → Controlled → Default,每级有 gate |
| 生产未修改 | ✅ 仅 output/ 设计产物 |

**剩余授权缺口(非算法,执行层面)**:
1. **LIM-06 素材图像落地**:Vision 需要本地像素;集成前需"下载缩略图"步骤(复用 stage32b `_ensure_material` 模式);下载失败 → IMAGE_UNAVAILABLE → V1 fallback(不崩溃、不删候选);
2. **Stage A 影子运行**:需生产环境授权(在线,含 API 调用);
3. **30 天监控采集**:Phase 5C 要求仍未采集(rollout Stage C gate 已定义)。

---

## 8. 五状态(本次 Preflight 最终)

| 状态 | 值 | 依据 |
|---|---|---|
| VISION_CHANNEL | **VALIDATED** | Phase 5A/5C 冻结(75% Top-1,MRR 0.842,Top-5 0.938) |
| RANKING_CHANNEL | **VALIDATED** | V1 语义排序,real pool 399 |
| DIRECTOR_REQUIREMENT_CONTRACT | **NOT_VALIDATED(排除出生产)** | Phase 6b V1.1 失败;Option 1 采纳 |
| API_RELIABILITY | **VALIDATED** | Phase 6b 20/20;true API failure 0%;unrecovered 0% |
| PRODUCTION_INTEGRATION | **PREFLIGHT_READY_FOR_AUTHORIZATION(未激活)** | 设计完成;需人工授权 → Stage A |

---

## 9. 请求人工裁决 / 授权

以下步骤需要授权才能执行(本轮未执行):

1. **批准 Stage A(Shadow Mode)实施**:在 production 环境中集成 Vision 影子运行(只记录,不影响 ranking),
   先解决 LIM-06(素材图像下载)并完成 ≥2 次生产运行;
2. **批准 30 天监控采集**(Phase 5C 要求),作为 Stage C 的 gate 依据;
3. **批准后才允许 Stage B(Controlled)**,并建立 kill-switch。

在授权前:**不修改 production、不启动任何生产运行、不改变任何算法。STOP。**

---

## 10. Audit trail

- 所有规格件:`output/stage33/cv2/phase7_production_integration/`
  (`architecture.json` / `runtime_contract.json` / `fallback_contract.json` /
  `observability_spec.json` / `rollout_plan.json` / `invariants.json` /
  `limitation_registry.json` / `preflight_result.json`);
- 基线数据来源(均已冻结):Phase 5A(75% / 0.842 / 0.211)、Phase 5B(注入 ≥ V1)、
  Phase 5C(C1 33%)、Phase 6b(20/20、0% true API failure)——**全部引用,未重跑、未改写**;
- 未修改:production 代码、Gold `C70C82D4...448AC`、Gate、人工标签、历史结果;
- 无阈值/权重调整;无 prompt 搜索;无 Director Contract;无 media blacklist;无 CLIP;
  无 shot-specific 规则;无 50/50 fusion。
