# Stage 3.3 Visual Director —— 输入/输出契约 Schema（设计附录 v2）

> 本文件是 `docs/STAGE33_VISUAL_DIRECTOR_DESIGN.md` 的 schema 附录（**v2，含人工观看反馈修订**）。仅设计，不实现。
> 字段来源标记：**U**=上游既有产物（2.x / 3.1.4 / 冻结稿，只读）；**D**=Visual Director（LLM 为主，规则回退）生成；**V**=确定性 Validator 校验/修复/回写；**E**=3.2b 执行层渲染时物化/回写。
> 所有 SHA 为 SHA256 小写十六进制；时间单位为秒。

---

## 0. v2 修订记录

| 版本 | 变化 |
|---|---|
| v1 | 纯规则引擎版（已废弃该定位） |
| v2 | ① LLM 为 Director 主体（创意规划），新增 meta.director_mode/llm_model/llm_seed；② TimelineDecision.reason 拆分为 9 个表达理由字段；③ 新增 NarrativeArc / MotifRegistry / ValidatorLog / ComparativeReport；④ BudgetReport 增加连续文字卡/模板重复/运动多样性下限/修复计数；⑤ 新增 §15 LLM 输入输出协议 |

---

## 1. VisualPlan（3.3 顶层输出）

`output/stage33/<project>/visual_plan.json`

| 字段 | 类型 | 必填 | 来源 | 说明 |
|---|---|---|---|---|
| schema_version | string | 是 | D | 契约版本，如 "3.3-p1-v2" |
| generator_version | string | 是 | D | 生成器版本 |
| project | string | 是 | U | 项目名 |
| meta | PlanMeta | 是 | D/V | 见 §1.1（Director 模式/模型/seed/回退标记） |
| input_fingerprint | string | 是 | D | = sha256(narration_sha + shotlist_sha + package_sha + contract_sha + meta) |
| inputs | object | 是 | D | 上游 SHA 与路径（同 v1） |
| style_contract | StyleContract | 是 | D | 全片风格契约（同 v1） |
| narrative_arc | NarrativeArc | 是 | D | **全片叙事弧**（v2 新增，见 §2） |
| beats | VisualBeat[] | 是 | D | 全片视觉 beat（时间升序） |
| strategies | VisualStrategy[] | 是 | D | 逐镜策略 |
| decisions | TimelineDecision[] | 是 | D | 逐 beat 决策（与 beats 一一对应，v2 字段见 §9） |
| motifs | MotifRegistry | 否 | D | 视觉母题/回收登记（v2 新增，见 §3） |
| chapters | Chapter[] | 否 | D | 章节/强调结构（v2 新增，见 §4） |
| budget_report | BudgetReport | 是 | V | 全局预算/多样性审计（v2 字段见 §10） |
| validator_log | ValidatorLog | 是 | V | **确定性 Validator 全量日志**（v2 新增，见 §5） |
| human_review_flags | string[] | 是 | D/V | 需人工裁决项 |
| plan_sha | string | 否 | E | 回写：本文件 SHA（执行后锁定） |

### 1.1 PlanMeta

| 字段 | 类型 | 来源 | 说明 |
|---|---|---|---|
| director_mode | enum | D | `LLM` / `RULE_FALLBACK`（LLM 不可用或两次被拒时） |
| llm_model | string\|null | D | 如 "Qwen2.5-3B-Instruct-Q4"(本地)；RULE_FALLBACK 时 null |
| llm_seed | int\|null | D | 采样种子（temperature=0 时仅影响顺序） |
| fallback_used | bool | D | 是否使用了规则回退规划器 |
| generated_at | string | D | 生成时间（仅记录，不参与指纹） |

---

## 2. NarrativeArc（全片叙事弧，v2 新增）

> 主题无关；Director 按内容自由安排各段存在性/长度/顺序，**不强制固定结构**；Validator 只检查结构完整性（必须含开场处理与收束处理），不检查"创意对错"。

| 字段 | 类型 | 必填 | 来源 | 说明 |
|---|---|---|---|---|
| arc_id | string | 是 | D | |
| segments | ArcSegment[] | 是 | D | §2.1 |
| intensity_curve | {beat_id: enum(LOW/MED/HIGH)} | 是 | D | 全片强度曲线 |
| pacing_plan | {phase: enum, beat_ids: string[], note: string} | 是 | D | 快/慢/高潮/留白安排（phase ∈ HOOK/CONTEXT/DEVELOPMENT/ESCALATION/TURNING_POINT/CONCLUSION/其他自定义） |
| climax_beat | string | 是 | D | 视觉高潮 beat id |
| whitespace_beats | string[] | 否 | D | 留白/停顿 beat |
| data_plan / human_plan / contrast_plan / graphic_plan | {beat_ids: string[], note: string} | 否 | D | 哪段用数据/人物/对比/图形（Director 决策） |
| callback_plan | {motif_id: string, first_beat: string, callback_beat: string}[] | 是 | D | 视觉元素回收计划（引用 MotifRegistry） |

### 2.1 ArcSegment

`{segment_id, phase: enum, beat_ids: string[], role: enum(ESTABLISH/DEVELOP/ACCELERATE/EMPHASIZE/RELEASE/PAUSE), note: string}`

---

## 3. MotifRegistry（视觉母题，v2 新增）

> 解决"镜头之间缺少视觉关系"：Director 登记跨镜复用/呼应的视觉元素（颜色、图形、构图、icon），结尾回收开场元素（如 coral 开场"褪色的城市"↔ S20"会呼吸的城市"）。

| 字段 | 类型 | 必填 | 来源 | 说明 |
|---|---|---|---|---|
| motif_id | string | 是 | D | |
| kind | enum | 是 | D | COLOR / GRAPHIC / COMPOSITION / ICON / TYPOGRAPHY / ASSET_CALLBACK |
| description | string | 是 | D | 母题说明（可解释性） |
| anchor_beat | string | 是 | D | 首次出现 beat |
| callbacks | string[] | 否 | D | 回收 beat 列表 |
| visual_ref | string | 是 | D | 具体元素引用（色值/模板 id/构图 id/icon id） |

---

## 4. Chapter（章节/强调结构，v2 新增）

`{chapter_id, title: string, title_source: enum(NARRATION_VERBATIM/GENERIC), beat_ids: string[], title_graphic: GraphicSpec|null}`
> title 若非口播稿原文，只能取自通用结构词（"开头/结尾"类），**不得引入新事实**；章节标题图形属 SELF_CREATED。

---

## 5. ValidatorLog（v2 新增）

| 字段 | 类型 | 来源 | 说明 |
|---|---|---|---|
| validator_version | string | V | |
| checks_total / checks_passed / checks_rejected | int | V | |
| field_repairs | {decision_id, field, original, repaired, rule_id}[] | V | **字段级确定性修复**（如非法 motion→HOLD_MICRO、非法转场→HARD_CUT、越界素材→表达阶梯降级） |
| plan_rejects | {attempt, reason}[] | V | 整案拒绝次数（触发回退规划器/LLM 重生成） |
| repair_cap_hit | bool | V | 修复数是否触顶（>5% 决策数 → 整案拒绝） |
| safety_assertions | {rule_id, passed}[] | V | 硬边界断言逐一结果（rights/threshold/事实/稿文未改等） |
| final_gate | enum | V | `PASS` / `PASS_WITH_REPAIRS` / `REJECTED` |

**语义**：PASS→原样执行；PASS_WITH_REPAIRS→按修复后执行（修复全部留痕）；REJECTED→**绝不执行**，走 LLM 重生成（≤2 次）→ 仍拒则规则回退规划器 → 仍拒则该计划停用并报告人工。

---

## 6. VisualBeat（同 v1，v2 微调）

| 字段 | 类型 | 必填 | 来源 | 说明 |
|---|---|---|---|---|
| beat_id | string | 是 | D | |
| shot_id | string | 是 | U | |
| narration_span | {start:int, end:int} | 是 | U | 冻结稿逐字字符区间（只引用不复制） |
| narration_text | string | 是 | U | 该 beat 口播原文（逐字拷贝引用） |
| start / end | float | 是 | U/E | alignment 真值优先；否则比例占位，E 回写 |
| beat_types | enum[] | 是 | D | INFO/CAUSE/EFFECT/CONTRAST/EMOTION/TURN/CONCLUSION/DATA/EXAMPLE/ACTION/TIME_CHANGE/SPACE_CHANGE/EMPHASIS/QUESTION/TRANSITIONAL |
| intensity | enum | 是 | D | LOW/MED/HIGH（须与 NarrativeArc.intensity_curve 一致，Validator 校验） |
| emphasis_target | string\|null | 否 | D | 强调词/数字（**必须为 narration_text 子串**，Validator 校验） |
| truth_dependency | {source:enum, ref:string\|null} | 是 | U/D | NARRATION_VERBATIM / SHOTLIST_EVIDENCE_REF / MATERIAL_PACKAGE（无其他来源） |

> beat 切分：LLM 提议 + Validator 落地。**硬约束**：narration_span 必须落在【Sxx】句内、逐字子串匹配冻结稿；<2.5s 句不切；每镜 ≤3 beats；最小 beat 1.2s；beat 时间=段内字符比例×段时长（E 回写真值）。

---

## 7. VisualStrategy（同 v1，v2 增加 arc 引用）

`{shot_id, shot_role(U), visual_target_hint(U), rhythm_arc_position(D), style_family(D), beat_plan(D), section_mood(D), arc_phase(D, 引用 NarrativeArc)}`

---

## 8. AssetRoleSpec / CompositionSpec / MotionSpec / TransitionSpec / GraphicSpec / AudioCue / FallbackSpec

与 v1 一致（枚举、参数带、硬约束不变），要点保留：

- AssetRole 枚举 14 个；候选**只来自** Material Package 白名单（Validator 二次核对 rights/threshold/sem≥50）；`required_signals/forbidden_signals` 信号匹配；
- Composition：构图格有限集 + 安全区（字幕区永独占）+ 层级；
- Motion：图片 8 种 / 视频 5 种 + 语义方向词典 + 不允许清单（乱晃/高频 zoom/每镜不同/为动而动/破坏事实）；
- Transition：默认 HARD_CUT；理由枚举；密度 cap（dissolve ≤2/10、dip ≤2/片、directional ≤1/10；DATA beat 禁非硬切）；
- GraphicSpec：graphic_type 10 模板；`numbers` 只能正则抽取自 truth_source 原文；<2 点禁趋势图；source_tag 强制；
- AudioCue（P3 起）：mood/intensity/envelope/duck；`SELF_SYNTHESIZED / PACKAGE_CC0_AUDIO / NONE`；VO 可懂度硬规则；
- FallbackSpec：表达阶梯 `SAFE_VIDEO > SAFE_IMAGE > SAFE_COMPOSITE > DATA_GRAPHIC > SELF_CREATED_GRAPHIC > TEXT_CARD`；`declined_reasons` 逐档留痕；`safe_guarantee` 引用 3.1.4 裁决。

---

## 9. TimelineDecision（v2 重大修订：9 个表达理由字段）

| 字段 | 类型 | 必填 | 来源 | 说明 |
|---|---|---|---|---|
| decision_id | string | 是 | D | |
| beat_id | string | 是 | D | |
| expression | enum | 是 | D | 六档表达 |
| semantic_role | enum | 是 | D | AssetRole 14 枚举（**v2 更名：表达角色**） |
| what_to_show | string | 是 | D | **给谁看什么**（LLM 正文：这一段观众应该看到什么） |
| why_this_expression | string | 是 | D | **为什么用这种表达档**（而非其他档） |
| source_material | {material_id:string, shot_id:string} \| null | 是 | U | 素材引用（图形/文字卡为 null；**必须命中白名单**） |
| fallback_reason | string | 是 | D | 若非最高档：逐档降级原因（引用 safe_guarantee） |
| motion_reason | string | 是 | D | 为什么这个运动（含语义方向依据） |
| transition_reason | string | 是 | D | 为什么这个转场（NONE 也须写明"默认硬切"） |
| composition_reason | string | 是 | D | 为什么这么裁/这么摆 |
| decision_chain | string[] | 是 | D/V | 规则/校验 id 链（如 ["BEAT.DATA","ROLE.DATA","EXPR.DATA_GRAPHIC","VALIDATOR.ASSET_OK","TRUTH.VERBATIM"]） |
| graphic | GraphicSpec\|null | 否 | D | |
| composition | CompositionSpec | 是 | D | |
| motion | MotionSpec | 是 | D | |
| transition_in | TransitionSpec | 是 | D | |
| audio | AudioCue | 否 | D | P3 起 |
| fallback | FallbackSpec | 是 | D | |
| duration | float | 是 | U/E | = beat 时长 |
| truth_dependency | {source:enum, ref:string\|null} | 是 | U/D | 与 beat 一致 |
| motif_ref | string\|null | 否 | D | 引用 MotifRegistry |

> 审计口径：任何人对"为什么这张图"可从 what_to_show/why_this_expression/source_material/decision_chain 直接追溯，无需看视频。

---

## 10. BudgetReport（v2 收紧）

| 字段 | 类型 | 来源 | 说明 |
|---|---|---|---|
| total_beats / total_shots | int | V | |
| text_card_rate | float | V | 硬预算 ≤0.30（beats 口径） |
| **consecutive_text_card_max** | int | V | **连续文字卡硬上限 ≤2**（第 3 张强制降级为 SELF_CREATED_GRAPHIC，Validator 执行） |
| **template_repeat_max** | int | V | **同一图形/卡模板连续 ≤2、全片同模板 ≤4** |
| **motion_variety_floor** | int | V | **全片不同 motion 类型 ≥4（beat 数≥8 时）**，不满足 → PASS_WITH_REPAIRS 强制替换 |
| static_image_rate | float | V | 报告值（过高触发 human_review_flag） |
| motion_type_histogram / transition_histogram | map | V | cap 校验结果 |
| duration_stats | {min,max,mean,p90} | V | 节奏审计（p90/p10≤3） |
| graphic_density | float | V | |
| chroma_key_count / audio_cue_count | int | V | P3 |
| **abstract_beat_consecutive_max** | int | V | **连续抽象（EMOTION/CONCLUSION/QUESTION）beat ≥3 时，第 3 张起必须用 COMPOSITE/GRAPHIC/MOTION 变体，禁连续文字卡** |
| violations | string[] | V | 非空 = Gate FAIL |

---

## 11. VisualQCReport 与 VisualQualityScore（同 v1）

10 维（机器分/人工分双列）：Visual Relevance / Visual Storytelling / Composition / Motion / Rhythm / Transition / Visual Variety / Typography / Graphic Quality / Overall Finish。Gate：机器分每维 ≥6/10 且 violations 为空。

---

## 12. ComparativeReport（盲测报告，v2 新增）

| 字段 | 类型 | 说明 |
|---|---|---|
| protocol_version | string | 盲测协议版本 |
| raters | {rater_id, blind_code}[] | 评分者（去标识） |
| pairs | PairResult[] | §12.1 |
| statistics | {non_inferior_proportion, n_pairs, per_dimension_median_delta, exact_95ci_lower} | 统计口径（见设计文档 §18） |
| order_control | {orders: string[], counterbalance_ok: bool} | 顺序平衡校验 |
| guess_check | {guessed_right: int, total: int, bias_note: string} | 事后"你猜哪个是 AI 做的"自检 |
| gate | enum | `PASS` / `FAIL` + 明细 |

### 12.1 PairResult

`{pair_id, topic, order_seen, per_dimension: {dim: {ai: float, jianying: float}}, overall: {ai: float, jianying: float}, non_inferior: bool, comments: string}`

**PASS 判定（设计文档 §18 为准）**：`non_inferior_proportion ≥ 0.70`（n≥10 对）**且** 每维中位数差 |Δ| ≤ 1.0 **且** 无 QC/安全违规。否则 FAIL（如实报告，不调线）。

---

## 13. LLM Director 输入输出协议（v2 新增，安全边界核心）

### 13.1 输入（sanitized context，LLM 唯一可见信息）

```json
{
  "task": "visual_plan_generation",
  "style_contract": {...},
  "narrative_arc_skeleton": {"phases": [...], "climax_candidate_beats": [...]},
  "shots": [{
     "shot_id": "S06", "narration": "海水温度只要升高一两度，珊瑚就会开始发烧。",
     "shot_metadata": {"role": "body", "visual_target_hint": "...", "duration_hint": "9s"},
     "whitelisted_candidates": [   // ← 已过 rights/threshold 的白名单，UNKNOWN/UNSAFE/sem<50 绝不出现
        {"material_id": "M-S06-303", "content_type": "image", "rights_status": "SAFE",
         "semantic_match": 63.8, "visual_description": "Ocean Surface Averages (1850-2014).jpg",
         "resolution": "..."}
     ]
  }],
  "constraints": {...}   // 预算/连续上限/运动与转场语法等（同 Validator 常量）
}
```

### 13.2 输出（LLM 只返回 JSON，禁止其他）

- 每 beat：`beat_id/shot_id/narration_span/beat_types/intensity/emphasis_target/expression/semantic_role/source_material(material_id)/composition/motion/transition_in/graphic(若图形)/what_to_show/why_this_expression/fallback_reason/motion_reason/transition_reason/composition_reason`；
- **LLM 不拥有**：文件系统、FFmpeg、网络、代码执行、素材 URL 原样传递（material_id 引用即可）、除给定 context 外的任何事实。

### 13.3 硬规则（LLM 上下文内明示 + Validator 兜底）

不得改稿文/不得造事实（图形数字必须原文存在）/不得引用白名单外素材/不得改 rights 判定/不得重检索/不得直控 FFmpeg/不得直改视频/只产结构化 JSON。

---

## 14. 字段来源总表（契约边界）

| 层 | 产生/拥有 | 允许 |
|---|---|---|
| 2.x | narration/shotlist/Truth/evidence_refs | 只读引用；不得改文、不得补事实 |
| 3.1.4 | Material Package | 只读白名单（SAFE 或 CONDITIONAL+可商用、sem≥50）；不得重检索、不得翻案 |
| 3.3 Director（LLM 或规则回退） | visual_plan.json 全部创意字段（arc/beat/role/expression/composition/motion/transition/graphic/audio/fallback/理由文案） | 只产计划 JSON |
| 3.3 Validator（Python 确定性） | 校验/修复/拒绝/validator_log/budget_report | 唯一通向执行层的门 |
| 3.2b Executor | 渲染产物/实测时间/QC/manifest 回写 | 只执行通过校验的计划；默认 legacy 路径零改动 |
