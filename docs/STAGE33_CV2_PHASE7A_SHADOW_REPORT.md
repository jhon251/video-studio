# STAGE 33 / CV-2 — Stage 7A: Production Shadow Mode 报告

> 状态:**Shadow Mode 运行完成(2 次全量生产级运行 + 1 次集成测试)。结论:`SHADOW_VALIDATED`。**
> 授权路线:**READY_WITH_EXPLICIT_LIMITATIONS(Option 1)**。
> 全程 Shadow:Vision 只记录,未改变 production ranking。**STOP——不进入 Stage B,等待人工授权。**
> 本轮新增模块 `src/video_studio/stage33/vision_shadow.py`(唯一新增,未修改任何既有 production 文件)。

---

## 0. 摘要

**Stage A Gate(9 项)全部 PASS:**

| Gate | 结果 | 证据 |
|---|---|---|
| G1 Shadow 不改变 production ranking | ✅ | 66 条记录 production_rank == v1_rank(两个 run) |
| G2 Vision 可靠性 | ✅ | 100% success(30/30, 26/26);未恢复 0%;true API failure 0% |
| G3 素材获取安全 | ✅ | 90.9%/78.8% 成功;所有失败=HTTP 429(Wikimedia 限流);无候选删除 |
| G4 Retry 恢复 | ✅ | run_02 retry 3.85%,恢复 100%;run_01 0 retry |
| G5 延迟 | ✅ | p50 3.9s / p95 17.0s / p99 18.4s(57 次调用)< timeout 180s |
| G6 无 invariant 违例 | ✅ | INV-01..INV-10 两个 run 全 true;0 violations |
| G7 可观测性 | ✅ | 13 指标;per-call/per-shot/per-run 日志;监控基础设施就绪 |
| G8 无算法改动 | ✅ | 仅新增 vision_shadow.py;V1/SEM_MIN/sanitizer/Gold/contract 全部未动 |
| G9 可复现 | ✅ | 两次独立运行(独立缓存)一致 |

**状态:`SHADOW_VALIDATED`**(从 `PREFLIGHT_READY_FOR_AUTHORIZATION` 更新)。
**未宣布 Production Ready。未请求 Stage B 授权。**

---

## 1. 执行形态

```
V1 -> Top-5 -> Vision shadow rerank -> 仅记录,不改变 production ranking
```

- **模块**:`src/video_studio/stage33/vision_shadow.py`(新增;复用 `sanitizer.build_context` 只读);
- **素材获取(LIM-06 解决)**:preview_file(本地)→ 独立 image_cache → download_url 下载
  (metadata 反查,不修改 sanitizer);失败不删候选、URL 保留、SHA 记录;
- **Vision**:`deepseek-v4-flash-vision-exp`,Phase 6b 冻结协议(max_tokens=2048/temp 0.1/retry 3/固定鉴权/
  Phase 4C RUBRIC_PROMPT——**未重新设计 prompt**);
- **Audit**:完整 request/response 元数据(http/finish_reason/reasoning_tokens/content_len/latency/分类);
- **输出**:`output/stage33/cv2/phase7a_shadow/`(shadow_records.json + 分析件)。

**Run 边界**:
- Run 0(dry):规划校验(33 记录规划,未调 API);
- Run 0(integration):S03/S06/S12 三镜 7 候选,7/7 成功(链路验证);
- Run 1:全量 20 镜 33 白名单候选(独立缓存);
- Run 2:全量 20 镜 33 候选(独立缓存,**独立重复**)。

**零白名单镜**:S01/S02/S10/S13/S15/S16/S18(7 镜无 SAFE 素材,白名单本身为空,非 Shadow 问题)。

---

## 2. 定义与统计

**失败分类(与 Phase 6b taxonomy 一致)**:L1 HTTP/API / L2 empty / L3 JSON parse /
L4 semantic disagreement(仅记录,不算 failure)/ L5 client / L6 retry recovery。

### Run 1 vs Run 2

| 指标 | Run 1 | Run 2 |
|---|---|---|
| 候选总数 | 33 | 33 |
| Vision 调用 | 30(3 IMAGE_UNAVAILABLE) | 26(7 IMAGE_UNAVAILABLE) |
| **Vision success rate** | **100%**(30/30) | **100%**(26/26) |
| Retry rate | 0% | **3.85%**(1 次恢复,recovery 100%) |
| 未恢复 failure | **0%** | **0%** |
| P50/P95/P99 延迟 | 3.4/15.9/17.0s | 4.2/18.4/19.8s |
| 图像获取成功率 | **90.9%**(30/33) | **78.8%**(26/33) |
| 获取失败 | 3(Wikimedia 429) | 7(Wikimedia 429) |
| 回退率 | 9.1% | 21.2% |
| **Disagreement rate** | **43.3%** | **42.3%** |
| Zero-candidate 违例 | 0 | 0 |
| Candidate loss | 0 | 0 |
| **Invariant violations** | **0** | **0** |
| PRODUCTION RANKING CHANGE | **0** | **0** |

---

## 3. 关键观察(Shadow 价值,仅供 Stage B 参考)

1. **DeepSeek Vision 在 Shadow 环境 100% 稳定**(56 次调用,0% 未恢复)——Phase 6b 声明的协议
   (max_tokens=2048)在真实 production 素材上验证成立;
2. **Wikimedia 429 是唯一失败源**(10/66 候选)——这是**素材下载限流**,不是 Vision API;
   对 Stage B 的启示:需要共享持久缓存 + 节流下载 + jitter 退避(工程项,非算法);
3. **V1 vs Vision 排序不一致 ~43%**——Shadow 确认 rerank 有信号价值空间(与 Phase 5A 的
   Vision-only MRR 0.842 > V1 0.697 一致);但 **Stage A 不利用它**(observational only);
4. **S06 chart / S12 painting** 在 Shadow 中行为正确(S06 图表 fit 0.75-0.9 高;
   S12 油画 fit 0.3-0.6 条件可用)——无 TYPE_BIAS、无类型误杀;
5. **白名单实际候选少**(33 个,多为 1-3 镜)——Sem≥50 过滤 + 权限过滤的结果;
   Vision 空间有限(每镜最多 3 个),Top-5 实际不触发。

---

## 4. 不变式(全部自动断言,两个 run 均 PASS)

```
INV-01 candidate count after == before          ✅ true
INV-02 zero-candidate == 0                      ✅ true(7 镜无白名单为设计,已单独记录)
INV-03 production ranking == V1 ranking         ✅ true
INV-04 Vision failure cannot change prod result ✅ true
INV-05 image download failure cannot change     ✅ true
INV-06 Vision output cannot delete candidate    ✅ true
INV-07 Shadow exception cannot propagate        ✅ true(exception_caught=0)
INV-08 Gold Standard untouched                  ✅ true
INV-09 SEM_MIN remains 50                       ✅ true
INV-10 no prompt/evaluation-label leakage       ✅ true
```

**任意不变量失败 → 立即 STOP** 的规则未触发(0 violations)。

---

## 5. 30 天监控

- **状态:`30_DAY_MONITORING = NOT_YET_OBSERVED`(如实声明)**
- 已完成:**监控基础设施/schema/日志/指标定义就绪**(monitoring_readiness.json;
  13 指标定义于 Phase 7 preflight observability_spec);
- 未做:没有伪造 30 天数据;没有把 Phase 5C 历史观察重新解释为 production monitoring;
- 真实 30 天数据需要 Stage B/持续生产运行授权后采集。

---

## 6. 合规清单(硬约束)

| 约束 | 状态 |
|---|---|
| 修改 V1 ranking 权重 | ❌ 未改 |
| 修改 SEM_MIN | ❌ 未改(仍 50.0) |
| 修改 sanitizer 白名单 | ❌ 未改 |
| 修改 Gold Standard | ❌ 未改(SHA 不变) |
| 修改 Gate | ❌ 未改 |
| 修改人工标签 | ❌ 未改 |
| 修改 Top-5 | ❌ 未改(N=5 冻结) |
| 修改 Vision prompt | ❌ 未改(Phase 4C RUBRIC 冻结) |
| 修改 Vision 模型 | ❌ 未改 |
| 修改 fusion | ❌ 未改 |
| 引入 Director Contract | ❌ 未引入 |
| 引入 CLIP/detector/blacklist | ❌ 未引入 |
| shot 特判 | ❌ 未引入 |
| Shadow 影响 production ranking | ❌ 未发生(0 变更) |

---

## 7. 交付物清单

`output/stage33/cv2/phase7a_shadow/`:
- `shadow_run_01.json` / `shadow_run_02.json`(两次运行全记录)
- `reliability.json`(成功率/重试率/未恢复率)
- `latency.json`(P50/P95/P99)
- `acquisition.json`(获取成功率/429 分析)
- `fallback.json`(回退事件/回退率)
- `invariants.json`(INV-01..10 全 PASS)
- `disagreement.json`(V1/Vision 不一致 43%)
- `audit.json`(审计链路)
- `monitoring_readiness.json`(30 天监控:NOT_YET_OBSERVED)
- `stage7a_result.json`(Stage A 判定 = SHADOW_VALIDATED)
- 子目录:`run_00_dry`、`run_00_integration`、`run_01`、`run_02`(含 image_cache + shadow_records.json)

源码:`src/video_studio/stage33/vision_shadow.py`(新增,唯一 production 目录新增文件)

---

## 8. 结论与 STOP

```
Stage A = SHADOW_VALIDATED
  QUALITY = observational only (43% disagreement observed, NOT applied)
  SAFETY = mandatory (0 invariant violations, 0 candidate loss, 0 ranking change)
  PRODUCTION RANKING CHANGE = 0

下一阶段授权:NOT REQUESTED。
完成 Stage A 后 STOP,等待人工授权 Stage B (Controlled Rollout)。
```

**显式声明**:
- 不自行宣布 `PRODUCTION_READY`;
- 不自动进入 Stage B;
- Stage B 前置(建议但需人工决定):缓存持久化共享、下载节流、Shadow 监控 dash 常驻、
  30 天监控启动(需授权)。
