# Stage 33 — STAGE 22.7: Entity-Class × Intent × Evidence Quality Diagnostic

> **性质**:只读诊断。零 CV2/Gate/ranking/Assignment/EQS/baseline 修改;新增 CV2 调用仅 3 次(授权 4 次,BrainGate P3 路径未解析,如实记录)。
> 数据集:**499 行已判定候选**(Run 01 cv2 429 + EXP-22.1 entity test + EXP-22.4 EO + EXP-22.5 图表)。
> 预注册先于配对调用:`stage22_7_preregistration.json`。机器可读:`stage22_7_entity_class_eqs_diagnostic.json` + `exp227_matrix_stats.json` + `exp227_shifts.json`

## 1. 判定:**SUPPORTED**(预注册口径)

Entity-Class Blindness 在评价栈中**系统性、跨类别、可重复地存在**,并含 ≥2 个同素材跨意图判定跃迁(≥1 个可用性等级)。

## 2. 五个 Case 的实证

| Case | 实证 | 结论 |
|---|---|---|
| **A: ABSTRACT_CG 被祝福** | ABSTRACT_CG 在 EVIDENCE 意图下(n=32):usable **75%**、HIGH 50%;旗舰:玻璃瓷砖抽象几何在“微电极特写”意图下 **USABLE/HIGH 0.85**(该拍最优候选) | CONFIRMED |
| **B: DATA_CHART 意图条件化** | **VIZ-1 timeline / VIZ-3 带宽图 在 META_QUANT 意图下 USABLE/HIGH 0.95**;同类图表在 EVIDENCE 意图下 NOT_USABLE(B2B 图 0.15、人工耳蜗 0.0) | CONFIRMED(意图条件形式) |
| **C: HARDWARE 合理** | BrainGate 0.85、DBS 设备 0.95——真实硬件得分可辩护,未发现祝福方向的失真 | CONFIRMED(正常) |
| **D: PERSON/PLACE 大气祝福** | PERSON 在 EVIDENCE 意图下 usable 84.8%/HIGH 71.2%(n=66);EEG 头带女在**大气意图**下 USABLE/HIGH 0.88——与证据意图同分 | CONFIRMED |
| **E: SCIENTIFIC_SPECIMEN 意图迁移** | 实验鼠:EVIDENCE 意图 CU/M 0.62 vs STRUCTURAL 意图 **USABLE/H 0.95**(同一文件) | CONFIRMED |

## 3. INTENT-CONDITIONED SCORING RISK(同素材配对)

1. **实验鼠**:CU/M 0.62(EVIDENCE“neural implant device”)→ USABLE/H 0.95(STRUCTURAL“BCI laboratory”)——**更模糊的意图得了更高的分**;
2. **EEG 头带女**:USABLE/H 0.9(EEG-cap 意图)→ CU/M 0.6(BrainGate 意图)→ **USABLE/H 0.88(ATMOSPHERE 意图)**——三个意图三种判定,大气意图恢复了高分;
3. 方向性说明:跃迁与“意图具体性”**非单调**——与“意图预设驱动的评价”一致,而非“主张控制的评价”。

记录为 **INTENT-CONDITIONED SCORING RISK**;不据此判定 rubric“错误”——它按自己的 rubric 一致工作,rubric 本身缺维度。

## 4. DATA_CHART 的精确读法(防过度声明)

图表惩罚是**意图条件 + 主张特异**的复合:EVIDENCE 意图下随机/错配图表被罚(NOT_USABLE);META_QUANT 意图下**为该主张构建的**图表得 0.95。DATA_CHART×META_QUANT 细胞(n=3)中 2 个是错配 stock 图(NOT_USABLE)——图表本身不自动通过,必须匹配主张。因此正确的生产方向是 22.5 的 typed routing + 未来 EQS 的主张覆盖维度,**而非“给图表加分”**。

## 5. Stage 21 EQS 缺口映射(PROPOSED FUTURE DIMENSIONS,不改 EQS)

| Entity Class | 建议未来维度 |
|---|---|
| DATA_CHART | quantitative correctness(数字与口播主张一致?)· axis/label adequacy · claim coverage |
| HARDWARE | device identity(哪个系统?)· component specificity · functional relevance |
| PERSON | action specificity · role specificity(研究者/患者/消费者)· behavior relevance |
| ABSTRACT_CG | metaphor transparency · evidence honesty(不得读作文档)· **abstraction penalty 默认** |
| 全体 | entity-class prior · **意图解耦:按 CLAIM 评分,不按 intent 措辞评分** |

## 6. INSUFFICIENT SAMPLE 细胞(如实)

ABSTRACT_CG×STRUCTURAL 同资产对(仅单意图)、HARDWARE×STRUCTURAL 同资产对(P3 未执行)、DATA_CHART×META_QUANT(n=3)、SCIENTIFIC_SPECIMEN×META_QUANT(n=1)、PLACE/SOFTWARE_UI/DOCUMENT_ARCHIVE 稀疏;UNKNOWN 桶 282 行未计入类统计。

## 7. Production 建议

1. 实体类维度 + **意图解耦评分**(按 CLAIM 而非 intent 措辞)应进入 Stage 21 EQS 实验设计(需授权);
2. CV2 rubric 现在不改;22.5 的 typed routing 与本发现一致(META_QUANT 意图合法通过图表);
3. 本判定**不授权任何生产 rubric 变更**。

## 8. 冻结边界

零冻结模块/零阈值/零 Gate/零 Assignment/零 baseline/零 Run 01 改动;EQS 未动;全部产物在 `output/stage22_visual_quality/`。

```
STAGE 22.7 = DIAGNOSTIC COMPLETE · STOP
499 行数据集 · 5 Case 全实证 · 同素材意图跃迁 ×2(鼠 CU→USABLE;EEG 头带 H→CU→H) ·
DATA_CHART 意图条件化精读(主张匹配图 0.95 vs 错配 NOT_USABLE) · EQS 缺口映射(PROPOSED) ·
分类 SUPPORTED(诊断成立,不授权生产变更)
STOP——等待授权
```
