# Stage 3.3 V3-M2 Remediation 报告（Truth 校验扩展 + 计划重生成）

> 状态：Remediation 完成，新 plan 已冻结；旧 plan 已 superseded。**STOP 等待 V3-M3 授权。**

## 1. 修复内容

| 项 | 实现 |
|---|---|
| **G3 Truth 校验扩展**（`stage_truth_text`） | 遍历 statement **全部文本字段**（attention_target/path/visual_evidence/visual_metaphor/layers[*]/shot_language/temporal_stages/graphic_layer/relations/director_note/motion 字段），任何数字/数值/统计 token（西方数字含小数单位、中文数词+单位）必须**逐字存在于口播原文**，否则确定性剔除 + `TRUTH.FACT_INVENTED` 留痕（junk 类）；素材 ID 内数字作为资源引用豁免；剔除后残留 `±≈~` 一并清理，visual_evidence 剔除后为空则回填 grounded 文本 |
| **placeholder 封死**（`stage_consistency`） | `第一眼看X→第二眼理解Y` 等 X/Y 占位符模式 → 确定性改写为具体内容（`SEMANTIC.PLACEHOLDER`） |
| **path/target 一致性** | attention_target 非数字而 path 提及"数字" → 改写为 `先看「target」，再理解它与全句的关系`（`SEMANTIC.PATH_TARGET`） |
| **motion 三态一致性** | intent≠none 但 necessity 声称静止 → intent=none；intent=none 但 necessity 声称删掉有损失 → 改写静止理由（`SEMANTIC.MOTION_CONSIST`）；realizer 降级时在 statement.motion 记录 **`planned_behavior → capability_limit → actual_behavior=HOLD` 完整链** |
| **HOLD_reason_quality 指标** | 三分桶：静止设计（intent=none 且理由≥8字）/ 意图运动但能力降级（链记录）/ 规则回退静止；报告内逐 beat 列 ID |

## 2. 新 plan 冻结（旧 plan 已 superseded）

| 项 | 值 |
|---|---|
| visual_plan.json | `output/stage33/coral/v3/visual_plan.json`（33 beats / 20 镜） |
| **plan_sha** | `8262bb4075af4e505f7aa629e8b268bfb1da3641f127e77de428aac502cfd37c` |
| input_fingerprint | `35ad4b267fca03a8` |
| 旧 plan | 重命名为 `visual_plan_superseded_d60e60f7.json`（保留备查，不作为 M3 输入） |
| director_mode | LLM；**按镜回退 9**（S02/S03/S04/S05/S06/S07/S17/S19/S20）——强化后的 Validator 拦截了更多 LLM 输出质量问题，回退较首轮（5）增多，属严格 Gate 的诚实代价 |
| 耗时 | 40.7 分钟 |

## 3. 验收条件逐项核验（用户六项清单）

| 条件 | 结果 |
|---|---|
| G1 PASS | ✓ PASS_WITH_REPAIRS（修复 12：PLACEHOLDER ×5、ATTENTION_TARGET ×5、GRAPHIC_TEXT ×1、NOTE_LEN ×1；junk=0、rejects=0） |
| G2 PASS | ✓ 模板名/句式/全文复制/幻觉计划违规 = **0** |
| G3 PASS 且 Truth 新校验 0 violation | ✓ **`TRUTH.FACT_INVENTED = 0`**（新校验已生效；B010 的 `0.457 ±0.068°C` 类问题在最终计划中不存在） |
| G4 PASS | ✓ 无幻觉计划；12 处意图运动→能力降级全部带 `planned→capability_limit→actual=HOLD` 链 |
| placeholder = 0 | ✓（5 处已确定性改写，最终计划无 X/Y 占位符） |
| target/path consistency = 100% | ✓（最终计划 0 处 PATH_TARGET 违规残留） |
| motion contradiction = 0 | ✓（最终计划 0 处矛盾残留；一致性修复已生效） |
| hallucinated fact = 0 | ✓ |
| 旧 plan superseded | ✓ |
| 新 plan SHA 冻结 | ✓ |
| 3.2b/3.1.4/2.x/P1 基线未修改 | ✓（P1 抽查 stage33_p1_m4.mp4 SHA 不变；服务器已停） |

## 4. HOLD_reason_quality（新指标，人工可读）

- **静止设计（intent=none 且理由 ≥8 字）：21/33**（含回退镜的规则静止——理由均充分）
- **意图运动但能力降级（完整链记录）：12/33**（如 B011：planned=attention_shift → capability_limit="平移速度不足 1px/帧 → HOLD（静止优先）" → actual=HOLD）
- **规则回退静止（无理由）：0**
- 结论：**不存在"无意义静止"**——每个静止 beat 要么是设计选择（有理由）、要么是能力降级（有链）。1px/帧门槛未放宽、zoompan/亚像素/正弦未恢复、jitter Gate 未动。

## 5. 如实说明

- 回退镜从 5 → 9：强化 Truth 校验后，LLM 在 9 个镜上反复产出违规内容（自造数字/占位符/一致性错误），按纪律重试 2 次仍失败 → 规则回退。**这是 Gate 在真实约束 Director，不是指标变差**；代价是 9 镜使用规则命题（诚实标注）。
- release_beats 仍为空：LLM arc 未提供 release 镜，按纪律不人为填充；报告注明"收束由末镜静止+锚点实现"。
- 33 beats 中 12 个 attention_shift 全部降级 HOLD：真实运动将非常少——这是 1px/帧整数轨迹门槛的必然结果，未为"看起来丰富"放宽任何阈值。

## 6. 停止线

- 不渲染、不进入 M3、不 SEAL、不动任何冻结物。
- 待裁决：① Remediation 结果是否接受；② 是否授权 V3-M3（execute 渲染 C 版 + jitter=0 硬 Gate + 技术 QC）。
- **STOP。**
