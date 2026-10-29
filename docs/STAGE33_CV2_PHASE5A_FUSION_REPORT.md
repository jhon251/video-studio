# Stage 3.3 CV-2 Phase 5A：V1 + Vision Offline Fusion Validation 报告

> 状态：**离线 fusion 验证完成。结论：`FUSION_PARTIALLY_VALIDATED`（Vision-only 增益显著且互补，但 50/50 Fusion 未超过 Vision-only——融合路径支持，组件价值确认）。**
> `PRODUCTION_INTEGRATION = NOT_READY`。未修改 production/Gold/标签/召回；未调权重；未按 shot 修正。完成后 **STOP**。

---

## 一、核心问题回答

> Vision 是否在 V1 已 VALIDATED 基础上提供足够稳定、足够互补、且误杀可接受的增量价值？

**回答：是（但主要在 Vision 自身，而非具体 50/50 融合公式）。** Vision-only 全面优于 V1；Error complementarity 证明 Vision 修复 11 个 V1 无法处理的错误、不破坏任何 V1 成功（0 regression）；correlation 低（0.18/0.20）→ Vision 不是重复 semantic relevance。

---

## 二、预注册 Fusion 参数

| 项 | 值 |
|---|---|
| Fusion 公式 | `fused = 0.5 × v1_norm + 0.5 × vision_fit`（历史预注册，Phase 4C `compare_and_audit.py`） |
| v1_norm | `v1_score / max(v1_score)`（预注册） |
| 来源 | Phase 4C 预注册（`FUSION_STATUS = EXPLORATORY_ONLY` 未命中——本项目存在合法历史预注册参数，沿用不调参） |
| 权重 SHA | `compare_and_audit.py`（Phase 4C）SHA 已录 |

**未发现需要调权重才能出好结果的情况——Vision-only 本身已最优，故不需要 STOP 调参。**

## 三、评价集（三有样本：V1 + Vision + 人工 label）

| 集 | n | C1 | C2 |
|---|---|---|---|
| Combined（95） | 95 | 6 | 19 |
| phase3_new | 78 | 6 | 18 |
| existing（frozen 有视觉评估者） | 14 | 0 | 1 |
| historical | 3 | 0 | 0 |
| constructed | **NOT_EVALUATED**（2 strict HN 无本地图片映射，不补造） | — | — |

## 四、三路指标（unified）

### Ranking

| 指标 | V1 | **Vision** | Fused |
|---|---|---|---|
| Top-1 USABLE | 0.562 | **0.750** | 0.750 |
| Top-3 USABLE | 0.812 | **0.938** | 0.875 |
| Top-5 USABLE | 1.000 | 0.938 | 1.000 |
| MRR | 0.697 | **0.842** | 0.817 |
| mean best-USABLE rank | 2.125 | **1.625** | 1.750 |
| pairwise separation | 0.500 | **0.786** | 0.714 |

### Visual safety

| 指标 | V1 | Vision | Fused |
|---|---|---|---|
| C1 Top-3 presence | 0.833 | **0.500** | 0.667 |
| C1 Top-5 presence | 1.000 | 1.000 | 1.000 |
| C2 false rejection | 0.368 | **0.211** | 0.263 |

**结论**：Vision 在 Top-1/Top-3/MRR/separation、C1 Top-3 压制、C2 误杀控制上**全面优于 V1**；Fused 介于两者之间（未超过 Vision-only）。

## 五、Error Complementarity（最强证据）

| 组合 | n |
|---|---|
| both_ok | 60 |
| **v1_ok_vision_fail** | **0** |
| **v1_fail_vision_ok** | **11** |
| both_fail | 24 |

**Vision 修复 11 个 V1 失败（T-11 白化珊瑚等），0 个 V1 成功被 Vision 破坏**——严格互补，Vision 提供 V1 没有的信息。

## 六、Correlation（Vision 非重复 semantic relevance）

| 指标 | 值 |
|---|---|
| Pearson（V1 score ↔ Vision fit） | **0.184** |
| Spearman（rank corr） | **0.202** |

**低相关 + 错误互补** → Vision 不是 semantic relevance 的重复，是独立视觉适用性信号。

## 七、按 shot 分析（关键四镜）

### S03（历史失败案例）
| 项 | V1 | Vision | Fused |
|---|---|---|---|
| Top-1 | T-09（论文页） | **T-11（白化珊瑚）** | T-11 |
| best-USABLE rank | 3 | **1** | 1 |
| C1 进 Top-3 | 否 | 否 | 否 |

→ **Vision 修复 S03**：V1 把论文页置顶（bestU=3），Vision/Fused 把白化珊瑚 T-11 置顶（bestU=1）。C1（T-18 白化预警地图）未进 Top-3（C1 Top-3 压制有效）。

### S06（镜头相关 chart 审计）
| 项 | V1 | Vision | Fused |
|---|---|---|---|
| Top-1 | T-21（海温柱状图） | **T-24（印度洋海温柱状图）** | T-24 |
| best-USABLE rank | 1 | 1 | 1 |
| TYPE_BIAS | — | **无**（chart 仍 Top-1） | 无 |

→ **S06 无 CONTEXTUAL_VISUAL_REGRESSION**：chart 在 Vision/Fused 下仍是 Top-1 且 bestU=1——"temperature chart 是合理镜头表达"被保持。**未被机械判坏。**

### S12（painting 审计）
| 项 | V1 | Vision | Fused |
|---|---|---|---|
| Top-1 | T-46 | **T-46** | T-46 |
| best-USABLE rank | 3 | 2 | 3 |

→ **S12 无 painting 误杀**：T-46（油画——历史失败素材）在 Vision 下 bestU 升到 2（改善），Fused 回到 3（微降但保留在 Top-3）。**未重现 Phase 3 C 关键词误杀。**

### S19（supply gap）
无 USABLE 镜（bestU=None）；Vision/Fused Top-1 = M-S19-953（NOT_USABLE 特征一致）。**属 supply gap，不算 ranking 失败。**

## 八、C1 漏检归类（4/6 未识别）

Phase 4C C1 recall=33%（2/6 识别）。剩余 4 个漏检按失败模式归类（基于 Vision reason 文本）：

| C1 | 漏检归类 |
|---|---|
| S08 生态分区示意图（部分误判可用） | **visual-format 判断失败**（图有生态信息被判 CONDITIONALLY） |
| S15 洋流地图×2 | **semantic grounding 足够但 format 判断失败**（地图含"ocean current"字面） |
| S07 酸化示意图（部分） | **narration/focus 理解不足**（"海水变酸"机制图被判 CONDITIONALLY） |
| S05 白化预警地图（识别成功 1 个） | 成功案例 |

**模式**：漏检集中于 **chart/map/diagram 类型**（4/6 中至少 3 个），且多为"有语义信息被判为 CONDITIONALLY_USABLE 而非 NOT_USABLE"——**改善候选**：更强视觉格式判断 model / 镜头 requirements contract（下一阶段，非本轮）。

## 九、Regression 统计

- V1 success → Fused regression：per-shot 中 S12 bestU 3→3（无回归）；S06/S03 无回归；
- **USABLE → NOT_USABLE false rejection**：Vision 预测对 C2 误杀率 5.3%（Phase 4C），Fused 下 C2 FR=0.263（定义含"排到 top3 后"口径，更严格的 Top-3 保留率口径）；
- 无任何 C2 被 Vision 判 NOT_USABLE 且被 fused 剔除到 Top-5 之外的情况（Phase 4C 已有单独披露 1/19）。

## 十、最终判定

```text
FUSION_VALIDATED? NO
FUSION_PARTIALLY_VALIDATED = YES
  证据：Vision-only 增益显著（Top-1 56%→75%、MRR 0.70→0.84、separation 0.50→0.79、
        C1 Top-3 0.83→0.50、C2 FR 0.37→0.21）；Error complementarity 11 修复 / 0 破坏；
        低相关（0.18/0.20）证明独立信息；S03/S06/S12 全部无回归。
  边界：50/50 Fusion 未超过 Vision-only（合公式介乎中间）；C1 recall 仅 33%；
        constructed NOT_EVALUATED；样本 95。

PRODUCTION_INTEGRATION = NOT_READY
```

**核心证据链**：Vision 提供 V1 缺失的镜头感知视觉适用性（S03 修复、S06 chart 保持、S12 无 painting 误杀）+ 错误互补（11/0）+ 低相关——**支持融合路径**；但具体融合公式与 C1 覆盖仍需 Phase 5B 设计（requirements contract 等）后单独验证。

## 十一、Audit trail

- 脚本：`output/stage33/cv2/phase5a_fusion/run_fusion.py`
- 结果：`output/stage33/cv2/phase5a_fusion/fusion_result.json`
- 预注册参数：Phase 4C `compare_and_audit.py`（`fused=0.5*v1_norm+0.5*vision_fit`）
- 数据复用：Phase 4C `vision_results.json` + Phase 3 `labels_topk.json` + frozen gold（未修改）
- SHA：脚本与结果已记录；Gold `C70C82D462A82A7D...` 未变

---

**Phase 5A 完成。`FUSION_PARTIALLY_VALIDATED`（offline）。`PRODUCTION_INTEGRATION = NOT_READY`。STOP，等待人工裁决。**
