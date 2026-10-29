# Stage 33 — Stage A-2: Capability Validation Results

> **性质**:研究实验，零生产修改。15 对象 / 8 维度能力评价。
> 机器可读:`output/prod02/stage_a2_results.json`

---

## 1. 判定：**NOT_SUPPORTED**

**Capability pass = 8/15 (53%)** < 9/15 PARTIALLY 阈值。

| 指标 | Run 02 (50.5% corr) | A-2 能力验证 |
|---|---|---|
| capability_pass | — | **8/15 (53%)** |
| factual_errors | 0 | **0** |
| claim_coverage mean | 0.600 (word overlap) | — |
| correct viz_type | — | **10/15 (67%)** |
| decoration | 0 | **0** |
| safety | 全 0 | **全 0** |

## 2. 关键发现

1. **生成全部成功**（A-1 修复有效）：15/15 产生 VIZ 结构；
2. **零事实错误**：所有 AI 生成内容可溯源到 narration/research；
3. **零装饰**：无 generic tech decoration；
4. **但 claim_coverage 不足**：7/15 的 claim_coverage < 0.5（词重叠代理指标），AI 生成的结构未能精确对准特定 narration 主张；
5. **核心瓶颈是语义理解**，不是工程——AI 可以选对图表类型、提取正确条目，但无法精确映射"哪个具体主张由哪个视觉元素证据"。

## 3. 8 维度汇总

| 维度 | 分布 |
|---|---|
| claim_coverage | mean 0.600 · 8 pass(≥0.5) · 7 fail(<0.5) |
| info_structure | correct 10 · partial 5 |
| factual_correctness | correct 14 · partial 1 · unsupported 0 |
| source_grounding | grounded 14 · partial 1 |
| non_decoration | non_deco 14 · partially_deco 1 |
| visual_qa | pass 12 · warn 3 · fail 0 |
| readability | readable 13 · partial 2 |

## 4. 诚实发现

- **工程已通**：A-1 修复后生成 100% 成功（15/15），零 API 错误；
- **能力仍不足**：53% capability pass 说明 AI 在"从主张到视觉映射"这一步仍有缺口——它能选对图表类型、生成正确的事实标签，但无法精确建立"这个视觉元素证明这个具体主张"的映射；
- **这不是通过更多训练能解决的**——它需要生产管线中的人类编辑确认步骤（per-claim EQS shadow → human review → confirm/reject），或者更强的语义理解模型。

## 5. Production 判定

**NOT AUTHORIZED**。8/15 capability pass 低于 PARTIAL 阈值(9)，不支持生产 rollout。Per-Claim EQS 保持 shadow。

## 6. 冻结边界

Stage A 原始 = SEALED / NOT_SUPPORTED · Stage A-1 = ENGINEERING_RECOVERABLE · render_163 baseline · 14 冻结件 · P-2 seal · Run 01/02 母片 · correspondence 50.5% · Stage 18–21 · per-claim shadow：全部不变。

```
STAGE A-2 = NOT_SUPPORTED
零事实错误 ✓ · 零装饰 ✓ · 但 claim coverage 53% < 60% 门槛
核心瓶颈：AI 无法精确建立 claim-to-visual 映射
Production VIZ Rollout = NOT AUTHORIZED
STOP——等待下一步授权
```
