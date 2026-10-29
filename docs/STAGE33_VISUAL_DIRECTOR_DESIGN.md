# Stage 3.3 Visual Director / Visual Storytelling Layer —— 最终设计（v2 · DESIGN AMENDMENT）

> 状态：**仅设计，不实现**；不改代码、不改任何 SEALED 资产、不进入 P1。
> v2 修订依据：真实人工观看反馈（成片"更像合规素材+文字卡+简单运动的自动装配，而非经过视觉设计的完整视频"）+ 本轮回改指令（10 条）。
> 附录：`docs/STAGE33_SCHEMAS.md`（v2，含 LLM 协议/ValidatorLog/NarrativeArc/盲测报告 schema）。

---

## 0. 修订记录与本版核心变化

| v1 → v2 | 变化 |
|---|---|
| 定位 | 纯规则引擎 → **LLM = Visual Director（创意规划主体）**；确定性 Python/FFmpeg = Validator + Executor |
| 架构 | 新增 **Deterministic Validator / Safety Gate** 作为 LLM 输出到执行层的唯一通道（不通过=拒绝/降级，绝不强行执行） |
| TEXT_CARD | 保持六档阶梯 + ≤30%，**新增**：连续文字卡 ≤2、同模板连续 ≤2/全片 ≤4、连续抽象 beat 第 3 张起强制 COMPOSITE/GRAPHIC/MOTION 变体 |
| 盲测 | 弃用"剪映偏好率 <70%"（方向错误）；改为 **"AI 成片不明显逊于剪映"的非劣判定占比 ≥70%**（n≥10 对、非劣界 δ=1.0、逐维中位数差 ≤1.0、完整统计口径与去偏措施） |
| Coral 失败模式 | 12 个真实失败模式逐条落为设计约束（§22 对照表），杜绝"3.2b+动画"式修修补补 |
| 叙事结构 | 新增 **Visual Narrative Arc**（HOOK→CONTEXT→DEVELOPMENT→ESCALATION→TURNING POINT→CONCLUSION，可自定义、不强制） |
| 可解释性 | TimelineDecision.reason 拆为 **9 个表达理由字段**（what_to_show/why_this_expression/semantic_role/source_material/fallback_reason/motion_reason/transition_reason/composition_reason/decision_chain） |
| 确定性 | 重定义：计划一旦通过校验即**冻结为 SHA 工件**（重放幂等）；LLM 再生成非字节级确定（如实声明），规则回退路径保持字节级确定 |
| 3.2b 重开 | 协议精确化（可改/禁改文件清单、legacy 字节级回归证明、回滚步骤，§23） |
| P1–P4 | 按"视觉质量提升最快"重排：**P1 = Coral Visual Director MVP（先出看得见的改善）**，B/C/D 后移 |

---

## 1. 真实观看反馈（v2 需求基线，逐条对应解决）

> "部分镜头是绿幕+文字，部分是简单图片画面，部分是普通视频素材；整体更像'合规素材+文字卡+简单运动的自动装配'，而不是经过视觉设计的完整视频。机器正确性没问题，视觉表达质量明显不足。"

| # | 观看反馈 | 解决章节（v2） |
|---|---|---|
| 1 | 绿幕+文字廉价 | §15 Chroma（P3）+ §9.3 视频层文字禁令 |
| 2 | 图片只是缓慢 Ken Burns | §10 Motion Grammar（8 种+语义方向+多样性下限） |
| 3 | 视频素材直接播放 | §10.2 视频处理规则（默认非"原样播放"） |
| 4 | 大量深色文字卡 | §8 表达阶梯 + §14 文字卡重定义（连续/模板禁令） |
| 5 | 缺少视觉层级 | §9 Composition 层级/安全区 |
| 6 | 缺少视觉节奏 | §11 Narrative Arc + §12 Rhythm |
| 7 | 缺少"这句话为什么要这样呈现" | §18 可解释性（9 字段，全 beat 必填） |
| 8 | 缺少镜头之间的视觉关系 | §11.3 MotifRegistry（母题/回收）+ 转场匹配 |
| 9 | 缺少数据/因果/对比/空间可视化 | §14 Graphics（beat 类型→表达映射：CAUSE→FLOW_DIAGRAM、CONTRAST→COMPARISON、SPACE→SCHEMATIC_MAP/方向平移、DATA→图表） |
| 10 | 缺少视觉高潮与收束 | §11 Narrative Arc（climax_beat/release）+ 片尾处理 |
| 11 | 缺少片头/片尾/章节结构 | §11.4 Chapter + §20（开场处理/落版/署名 roll/fade） |
| 12 | 没有 BGM/音效，像测试产物 | §16 音频策略（P3）+ P1 即预留 AudioCue 字段 |

**v2 总原则**：3.3 不是"3.2b 加动画"，而是补上**视觉叙事决策层**——先有"这一句该被看见成什么、为什么、和上一镜什么关系、在全片节奏里什么位置"，再有执行。

---

## 2. 根因（不变，v1 §2 结论保持）

机器 Gate 覆盖"技术正确性 + 素材相关性下限"，从未覆盖"视觉表达质量"；3.2b 的视觉决策全集只有"阈值+统一 zoom+硬切+白字卡"。剪映的差距不在素材更多，而在**每一句信息都有一个设计过的视觉表达方案**。3.3 解决的根因 = 补上这个决策层。

---

## 3. 四层架构边界（v2 精确化）

```text
2.x   = WHAT TO SAY            （冻结，只读）
3.1.4 = WHAT SAFE MATERIAL EXISTS（SEALED，只读；白名单化）
3.3   = HOW TO VISUALLY TELL IT  （LLM Director 创意规划 + 确定性 Validator 把关）
3.2b  = HOW TO EXECUTE IT        （执行 + 技术 QC + 真值回写；legacy 路径零改动）
```

**v2 关键分工（用户裁定）**：

```text
LLM（Visual Director / Creative Planner）
   输入：sanitized context（风格契约+口播稿+shotlist 元数据+3.1.4 白名单候选，无 URL、无网络、无文件系统）
   输出：visual_plan.json（只产结构化计划）
   禁止：改稿/造事实/改 rights/重检索/直控 FFmpeg/直改视频
        ↓
Python 确定性 Validator / Safety Gate（唯一通向执行层的门）
   校验：schema、白名单、事实（图形数字⊆原文）、稿文未改、预算 cap、连续/重复禁令、节奏/转场上限
   行为：PASS 原样 / PASS_WITH_REPAIRS 字段级降级修复（留痕）/ REJECTED 拒绝（重生成≤2 次→规则回退规划器→仍拒则停用上报）
        ↓
Python/FFmpeg 确定性 Executor（3.2b plan 模式）
   只执行通过校验的计划；技术 QC 与实测回写；默认 legacy 路径字节级不变
```

---

## 4. 完整架构（v2）

```text
冻结稿/shotlist/2.x Truth ──→ ┌───────────────────────────────┐
3.1.4 Material Package ──────→ │ sanitizer（白名单化：仅 SAFE 或 │
(alignment 真值时间轴, 可选) ─→ │ CONDITIONAL可商用 & sem≥50）    │
                               └──────────┬────────────────────┘
                                          ▼
                    ┌─────────────────────────────────────────┐
                    │ LLM Visual Director（本地模型，见 §5）      │
                    │  Narrative Arc / Beat / Role / Expression │
                    │  Composition / Motion / Transition /      │
                    │  Graphic / Audio / 9 项理由文案            │
                    └──────────┬──────────────────────────────┘
                               ▼
                    ┌─────────────────────────────────────────┐
                    │ Deterministic Validator / Safety Gate     │
                    │ （Python；schema/白名单/事实/预算/禁令/节奏）│
                    │  PASS | PASS_WITH_REPAIRS | REJECTED      │
                    │  回退链：LLM 重生成 ≤2 → 规则回退规划器     │
                    └──────────┬──────────────────────────────┘
                               ▼
                    visual_plan.json（冻结 SHA，重放幂等）
                               ▼
                    ┌─────────────────────────────────────────┐
                    │ 3.2b Executor（plan 模式；legacy 零改动）   │
                    │  渲染 → Visual QC → 技术 QC → 回写实测      │
                    └─────────────────────────────────────────┘
```

模块划分（`src/video_studio/stage33/`，未来实现时）：`sanitizer / director_llm / validator / planner_fallback(规则回退) / schemas / beat_rules / role_rules / motion_rules / transition_rules / rhythm_rules / budget / graphics(执行侧模板渲染) / audio_strategy / visual_qc / quality_score`。**本轮不实现。**

---

## 5. LLM Director 设计（v2 新增核心）

### 5.1 为什么本地模型而非 API

- 项目不变式：不接需要 API key 的商业服务 → 云端 LLM API 排除；
- 无 GPU 约束 → 选 **CPU 可跑的小型中文指令模型**；
- 基准：**Qwen2.5-3B-Instruct（Q4 ≈ 2GB，CPU 4–10 tok/s，plan 生成分钟级）**；候选退路：Qwen2.5-1.5B（更快，JSON 稳定性稍弱）；两者经 hf-mirror + 重试下载脚本（沿用 `_fetch_*` 模式）；
- 只做 JSON 生成（约束提示 + 解析重试 ≤2 次 + 规则回退），**不接任何工具/函数调用**（无代码执行面）。

### 5.2 输入/输出协议（schema §13）

输入= sanitized context（白名单候选 + 稿文 + shotlist 元数据 + 风格契约 + 弧线骨架 + 约束常量）；输出=严格 JSON（字段见 schema §9）。LLM 拿不到：素材 URL、文件系统、网络、FFmpeg、白名单外的任何东西。

### 5.3 回退链（保证"LLM 挂了系统还能出片"）

LLM 不可用 / 输出解析失败 / Validator 两次 REJECTED → **规则回退规划器**（= v1 设计的词典+规则引擎，降级为后备而不是主角）→ 产出标记 `director_mode=RULE_FALLBACK` 的计划。回退计划同样过 Validator。质量预期：回退版 ≈ v1 规则版（明显好于 3.2b，弱于 LLM 版），如实标注。

### 5.4 确定性重定义（诚实声明）

- **工件级确定**：通过校验的 visual_plan.json 一经生成即冻结（SHA + fingerprint），重放/重渲染幂等——这是验收与审计的确定性；
- **生成级确定**：LLM 路径固定 `model 版本 + seed + temperature=0` 近似可复现，但不承诺字节级一致（采样器/运行时差异）；规则回退路径字节级确定；
- 测试口径相应改为：规则回退路径做字节级幂等断言；LLM 路径做"结构合规率 100% + 白名单 0 违规 + 两次生成间字段级差异率报告"。

---

## 6. Deterministic Validator / Safety Gate（v2 新增核心）

### 6.1 校验清单（实现时为确定性断言集，此处列全集）

1. schema/枚举/必填；
2. **白名单**：每处 source_material ∈ sanitizer 白名单（rights SAFE 或 CONDITIONAL+commercial_use，且 sem≥50）；
3. **稿文未改**：narration_span 逐字子串匹配冻结稿（CRLF 归一化口径）；beat 拼接 == 原句；
4. **事实锁**：GraphicSpec.numbers ⊆ 原文正则抽取集；无数值 beat 禁数值模板；emphasis_target ⊆ narration_text；章节标题非原文时仅限通用结构词；
5. **预算/禁令**：text_card_rate ≤30%；连续文字卡 ≤2；同模板连续 ≤2、全片 ≤4；连续抽象 beat ≥3 时第 3 起禁文字卡；motion 多样性 ≥4（beat≥8 时）；同 motion 连续 ≤3；转场密度 cap；p90/p10 ≤3；每镜 ≤3 beats；最小 beat 1.2s；
6. **一致性**：arc.intensity_curve ↔ beat.intensity；beat 时间求和 == 段时长；motif 引用存在；decision 与 beat 一一对应；
7. **安全断言**（不变式复刻）：不重检索（无任何网络调用代码路径）、UNKNOWN/UNSAFE 零出现、threshold 未降低、2.x/3.1.4/冻结稿文件零写入。

### 6.2 拒绝/降级语义（用户裁定原文落实）

- `PASS`：原样执行；
- `PASS_WITH_REPAIRS`：**字段级确定性修复**（非法 motion→HOLD_MICRO、非法转场→HARD_CUT、越白名单素材→按表达阶梯降级、第 3 张连续文字卡→SELF_CREATED_GRAPHIC…），全部写入 `validator_log.field_repairs`；修复数 >5% 决策数 → 整案 `REJECTED`；
- `REJECTED`：**绝不执行** → LLM 重生成（≤2）→ 规则回退规划器 → 仍拒 → 停用计划并上报人工。
- Validator **不评判"创意好坏"**（那是 LLM 的职责、人工的裁决），只评判安全/合规/一致性/上限。

---

## 7. Visual Beat Analysis（v2：LLM 提议 + Validator 落地）

- 线索词词典（v1 §5 全表）作为 **LLM 的提示材料与 Validator 的锚定依据**，不再是唯一决定者；
- LLM 提议切分/类型/强度；Validator 用硬约束落地（span 逐字匹配、<2.5s 不切、≤3/镜、≥1.2s、时间=字符比例）；
- "一句话 ≠ 一个镜头"仍成立：一句话 1–3 beats；视觉切点不必等于句号；
- beat 时间真值仍是 3.2b VO 实测（E 回写）。

---

## 8. 表达选择 + Asset Role（相关 ≠ 适合，保持 v1 + v2 收紧）

### 8.1 六档表达阶梯（顺序保持，TEXT_CARD 明确为**最后一级**）

`SAFE_VIDEO → SAFE_IMAGE → SAFE_COMPOSITE → DATA_GRAPHIC → SELF_CREATED_GRAPHIC → TEXT_CARD`

### 8.2 "素材不足 ≠ 自动文字卡"（v2 新增硬条款）

选择函数（Director 决策 + Validator 校验）：
1. 有白名单素材 → 素材档（VIDEO/IMAGE/COMPOSITE）；
2. 无素材但 beat ∈ DATA 且原文有数值 → DATA_GRAPHIC（Truth 锁）；
3. 无素材且非数据 → **先** SELF_CREATED_GRAPHIC（图标/排版/流程/对比组合），**再** TEXT_CARD；
4. TEXT_CARD 仅当：beat 为纯 INFO 短连接句、无可视化结构、且图形模板均不适用时才允许——每次使用必须在 `why_this_expression` 里写清"为什么图形不适用"。

### 8.3 v2 新增禁令（BudgetReport 强制，Validator 执行）

- 连续 TEXT_CARD ≤2（第 3 张强制降级 SELF_CREATED_GRAPHIC）；
- 同一图形/卡模板：连续 ≤2、全片 ≤4；
- 连续抽象 beat（EMOTION/CONCLUSION/QUESTION）≥3：第 3 张起必须用 COMPOSITE/GRAPHIC/MOTION 变体，禁连续文字卡；
- 全片 motion 类型 ≥4（beat≥8 时），同 motion 连续 ≤3。

### 8.4 Asset Role

14 角色枚举、`required_signals/forbidden_signals` 信号匹配、`role_suitability` 公式（v1 §7 全部保持）。**LLM 只从白名单里选角色与素材；Validator 二次核对。**

---

## 9. Composition 与视觉层级（v2 针对"无层级"）

- 构图格有限集（8 种）+ 安全区（标题区/字幕区永独占/角标区）+ 层级（背景→主体→图形角标→字幕最上）；
- **v2 新增**：单 beat 元素数 ≤3（overload 检查）；每镜构图类型与上一镜不同（除非 motif 有意重复）；视频素材默认禁止全屏文字叠加（文字只进下半安全带或 INSET 框），杜绝"绿幕/杂画面+大字"廉价感（P3 前）。
- 裁剪锚点仍限构图网格点（无感知模型，如实标注）。

---

## 10. Motion Grammar（v2 针对"Ken Burns 单调/视频直放"）

- 图片 8 种 / 视频 5 种、参数带、语义方向词典、不允许清单：全部保持 v1 §9；
- **v2 新增**：
  - **视频默认 ≠ 原样播放**：默认 SLOW_PUSH_IN（1.00→1.04）或 SOURCE_NATIVE 且必须命中理由（ACTION role + 动作完整）；无理由直放 → Validator 修复为 PUSH_IN；
  - **motion_variety_floor ≥4**：全片不同运动类型下限（解决"全部 Ken Burns"）；
  - 每个 motion 必填 `motion_reason`（语义方向/beat 类型/角色之一）；
  - 高潮 beat 运动强度 = 全片最高档（FOCAL_ZOOM/PUSH_IN+速度上沿）；收束 beat = PULL_OUT+HOLD。

---

## 11. Visual Narrative Arc（v2 新增，全片级）

### 11.1 结构骨架（可自定义，不强制）

`HOOK → CONTEXT → DEVELOPMENT → ESCALATION → TURNING POINT → CONCLUSION`

- Director 按内容决定各段存在性/顺序/长度；Validator 只要求"有开场处理 + 有收束处理"；
- 决策字段（schema §2）：`pacing_plan`（哪里快/慢/留白）、`climax_beat`（视觉高潮）、`whitespace_beats`、`data_plan/human_plan/contrast_plan/graphic_plan`（哪段用数据/人物/对比/图形）、`callback_plan`（回收前文视觉元素）。

### 11.2 全片节奏规则（Validator 可校验的下限）

- 首 10% beats=ESTABLISH 档（运动 ≤LOW）；末 10%=RELEASE；
- climax 唯一且强度=HIGH；climax 前必须有 ESCALATION（加速段：平均时长 ≤0.8×全片均值）；
- 留白 beat 至少 1 处（≥0.5s hold）当总长 >60s；
- p90/p10 ≤3；相邻 beat 时长比 ≤3:1。

### 11.3 MotifRegistry（解决"镜头之间无关系"）

Director 登记跨镜视觉母题（颜色/图形/构图/icon/排版/素材呼应），并在 `callback_plan` 里指定回收点（如 coral：开场"慢慢褪色的城市"↔ S20"会呼吸的城市"用同一构图格+同色系收束）。Validator 校验引用存在性与回收点先后关系。

### 11.4 片头/片尾/章节结构

- 片头：开场 beat = ESTABLISHING 处理（hold 0.5s → 标题排版入场）；主题标题 = 冻结稿标题行（逐字）；
- 片尾：CONCLUSION 收束版式 + **fade-out（0.5s）** + 署名 roll（素材 attribution 汇总，来自 3.1.4 字段）+ 落版；
- 章节：arc 段边界可配章节标题图形（SELF_CREATED；标题只能取自原文或通用结构词）。

---

## 12. Rhythm / 13. Transition / 14. Graphics / 15. Chroma / 16. Audio / 17. Style

（v1 内容全部保留，仅列 v2 增补，避免重复）

- **Rhythm**（§12）：保持 v1 §10；增补 §11.2 的可校验规则。
- **Transition**（§13）：保持 v1 §11（默认硬切、理由枚举、密度 cap、DATA 禁非硬切）；v2 增补：转场必须引用 `transition_reason`；DIRECTIONAL 方向必须与因果 beat 的语义方向一致（Validator 检查方向词典）。
- **Graphics**（§14）：10 模板 + Truth 锁 + source_tag（v1 §12.2 全保持）；v2 增补：beat 类型→图形模板的**默认映射**（CAUSE→FLOW_DIAGRAM、CONTRAST→COMPARISON/SPLIT、SPACE→SCHEMATIC_MAP、TIME_CHANGE→TIMELINE、DATA→NUMBER_EMPHASIS/TREND_CHART、QUESTION→QUESTION_CARD、CONCLUSION→CLOSING_CARD）——LLM 可偏离但须在 `why_this_expression` 说明，Validator 不纠美学只纠 Truth。
- **Chroma**（§15）：保持 v1 §13（检测→抠像→合成→校验→INSET 降级；0 全屏绿幕；SHA/attribution/manifest）。P3 实施；P1 起以 §9.3"视频禁全屏文字"先行止血。
- **Audio**（§16）：保持 v1 §14（程序化合成/CC0 门/ducking/SFX 白名单/可懂度硬规则）；P1 起计划中 AudioCue 字段即存在（NONE 显式），避免"测试产物感"在 P3 一次性补齐。
- **Style**（§17）：保持 v1 §15（StyleContract + 3 风格族 + seed 变体 + "一致但不重复"）。

---

## 18. 可解释性（v2：9 个表达理由字段，逐 beat 必填）

`what_to_show / why_this_expression / semantic_role / source_material / fallback_reason / motion_reason / transition_reason / composition_reason / decision_chain`（schema §9）。审计示例：任何决策都能回答"为什么这句话用这张图/这个图形/这个运动/这个转场"——不再需要靠看视频猜。LLM 生成理由文案；Validator 校验"理由字段非空 + decision_chain 与实际校验链一致"（理由内容不做真伪判定，属创意域，由人工抽查）。

---

## 19. 确定性（v2 重定义，见 §5.4）

工件级确定（冻结计划+幂等重放）= 验收口径；规则回退路径字节级幂等；LLM 路径 pinned(model+seed+temp=0) 近似复现，差异率报告。**不虚假承诺字节级生成确定。**

---

## 20. Visual QC 与 Visual Quality Score（v1 §18 保持 + 微调）

- 机器可查 14 项 + 人工必查 6 项：保持；
- v2 增补机器项：`consecutive_text_card ≤2`、`template_repeat ≤2/≤4`、`motion_variety ≥4`、`video_raw_playback_count=0`（未带理由的 SOURCE_NATIVE）、`chapter/open/close_present`、`fade_out_present`；
- Visual Quality Score 10 维双列：保持；Gate：机器分每维 ≥6/10 且 violations 为空。

---

## 21. 盲测统计重设计（v2 修正，替换 v1 §18.4）

### 21.1 目标表述（统计上正确）

> **目标：在成对比较中，"AI 成片不明显逊于剪映文字成视频"的判定占比 ≥ 70%。**

### 21.2 操作化定义

- 每名评分者看一对视频（同主题：我们的成片 vs 人工用剪映文字成视频做的对标片），10 维 1–10 分 + 整体分；
- **非劣判定（per pair）**：`整体分(AI) ≥ 整体分(剪映) − δ`，δ=1.0（10 分制非劣界）；
- **主判据**：非劣占比 = 非劣 pair 数 / 总 pair 数 ≥ **0.70**；
- **辅判据**：10 维中每维中位数差 |Δ| ≤ 1.0（防止"总分靠一维拉回"）；无 QC/安全违规。

### 21.3 样本量与统计口径

- **最小样本 n=10 pairs**（≥5 名评分者 × ≥2 个主题，或 ≥10 人 × 1 主题）；建议 n=20；
- 报告：非劣占比 + **Clopper-Pearson 精确 95% CI** + 逐维中位数差 + 效应量（Cohen's d 或等价非参量）；
- 口径说明：n=10 时 CI 很宽（如实披露）——P2 预演用 n=10 定性，**P4 正式验收目标 n≥20**；单主题珊瑚只能算预演，不能作正式 PASS。

### 21.4 盲测条件与去偏

- 顺序：每名评分者观看顺序随机、全局计数器平衡（一半先看 AI 版）；
- 标签：文件重命名为中性码（R1/R2），脚本生成对照表，评分表不含任何来源信息；片内去除我方工程水印（本系统本无）；剪映水印如无法去除 → 记为已知偏差并在报告披露，评分者被要求忽略平台水印；
- 响度统一：两版先归一化到同一 LUFS（响度偏置是最强混淆变量）；
- 观看条件：同一播放器、耳机、亮度指引；两版间隔 ≥30s 洗脱；
- 评分者：≥一半为非开发者、不了解项目内部实现；10 维锚点描述写在评分表；
- **事后猜源自检**（guess_check）：若评分者正确猜中来源比例显著高于随机，结果标注"可能受预期影响"并在报告披露，不事后剔除。

### 21.5 PASS / FAIL

`PASS = 非劣占比 ≥0.70 且 逐维中位数差 ≤1.0 且 无违规`；否则 FAIL（报告真实分差，**不调线、不换口径、不删离群**）。阶段目标：**不再明显低于剪映**（第二阶段才追求超越）。

---

## 22. Coral 实际失败模式 → 设计约束对照表（v2 核心，回答"改了什么"）

| Coral 成片事实 | 直接对应的 v2 设计约束 |
|---|---|
| 绿幕素材+文字廉价 | §15 绿幕管线（P3）+ §9.3"视频禁全屏文字叠加"（P1 即生效） |
| 图片只是缓慢 Ken Burns | §10 motion 8 种 + 语义方向绑定 + `motion_variety_floor≥4` + 每 motion 必填理由 |
| 视频素材直接播放 | §10.2 视频默认非原样播放；`video_raw_playback_count=0`（QC 项） |
| 大量深色文字卡（9/20） | §8 阶梯 TEXT_CARD 最后一级 + 连续 ≤2 + 同模板 ≤2/≤4 + 抽象 beat 禁连卡 + 排版化卡（非深底白字） |
| 缺少视觉层级 | §9 构图格/安全区/层级/元素数 ≤3 |
| 缺少视觉节奏 | §11 arc + §12 rhythm（加速/高潮/留白/p90p10≤3） |
| 缺少"为什么这样呈现" | §18 九字段逐 beat 必填 + decision_chain |
| 缺少镜头间关系 | §11.3 MotifRegistry + callback_plan + 转场匹配/构图轮换 |
| 缺数据/因果/对比/空间可视化 | §14 默认映射（CAUSE→FLOW、CONTRAST→COMPARISON、SPACE→SCHEMATIC、DATA→图表） |
| 缺高潮与收束 | §11 climax_beat 唯一 HIGH + ESCALATION 前置 + RELEASE 收束 |
| 缺片头/片尾/章节 | §11.4（开场处理/章节标题图形/落版/fade-out/署名 roll） |
| 无 BGM/SFX 像测试产物 | §16 音频策略（P3 实施；P1 起 AudioCue 字段就位）+ 可懂度硬规则 |

**结论**：每一条观看反馈都有**确定的规则/字段/QC 项**接住，而不是"多加动画"。

---

## 23. 3.2b SEALED 重开协议（v2 精确化）

### 23.1 允许修改（仅当 P1 获批后，且只允许"新增"，不允许改既有行）

| 文件 | 允许的操作 |
|---|---|
| `src/video_studio/stage32b/assemble.py` | 仅**新增** plan 模式函数（如 `build_all_plan()`）；legacy 函数体零改动 |
| `src/video_studio/stage32b/render.py` | 仅**新增** plan 模式函数；legacy 函数体零改动 |
| `scripts/run_stage32b.py` | 仅**新增** `--plan` 参数分支（新 else-if 块） |
| `src/video_studio/stage32b/__init__.py` | 仅状态字段：`SEALED → REOPENED_DEV`（注明原因与重开文档），版本号不变 |

### 23.2 绝对禁止修改

`vo.py / alignment.py / subtitle.py / blocked.py / qc.py`；3.2b 的 7 个 manifest、coral 全部产物；2.x / 3.1.4 / 冻结稿 / Material Package；`docs/STAGE32B_SEAL.md`（历史记录不改，只追加重开记录新文档）。

### 23.3 legacy path 未改变的证明（三件套）

1. **事前 SHA**：修改前对 5 个待改文件存档 SHA（记录于重开文档）；
2. **diff 证明**：修改后对 legacy 函数体做行级 diff=0（仅新增行）——无 git，用存档副本 diff；
3. **产物级回归（决定性）**：用**既有 VO 段**重跑 legacy 全链（subtitle→blocked→assemble→render→qc，不重跑 VO、不重检索），断言 `final_preview.mp4 / subtitles.srt / subtitles.ass / voiceover.wav / 7 个 manifest` 的 SHA 与 `docs/STAGE32B_SEAL.md` 固化值**逐字节一致**。

### 23.4 回滚

修改前 5 文件存 `.reopen_bak/`（含 SHA 记录）；任一条回归失败或人工裁决不通过 → 从备份恢复 + `__init__.py` 状态回 `SEALED` + 记录回滚原因。回滚后 3.2b 状态与重开前逐字节一致。

---

## 24. P1–P4 重排（v2：视觉质量提升优先，Coral MVP 先行）

> 排序原则：每一阶段都以"让 Coral 成片**肉眼可见变好**"为验收锚点，而不是按模块完整性机械拆分。

| 阶段 | 目标（杀死什么） | 内容 | Gate | 真实视频验收 |
|---|---|---|---|---|
| **P1 = Coral Visual Director MVP** | 杀死：单调 Ken Burns / 白字卡泛滥 / 无理由呈现 / 无节奏 | LLM Director（Qwen 本地，含协议+回退链）+ Validator（全清单）+ sanitizer + arc/beat/role/expression/composition/motion（图片 8 种、视频默认非原样）+ 3 个图形模板（NUMBER_EMPHASIS/COMPARISON/TYPO_COMPOSITION）+ 文字卡排版化（连续 ≤2）+ 3.2b plan 模式（重开协议）+ Visual QC v1 | ① Validator：PASS 或 PASS_WITH_REPAIRS（修复 ≤5%）② 安全断言 0 违规 ③ legacy 字节级回归（§23）④ 规则回退路径字节级幂等 ⑤ Coral 重渲染：技术 QC 13 项仍全 PASS + 文字卡率 ≤30% + motion 类型 ≥4 | **Coral 人工观看 Round 1**（计划 + 成片并审） |
| **P2 = 图形/转场/节奏完整化** | 杀死：缺数据/因果/对比可视化、硬切无理由、缺章节结构 | 剩余 7 图形模板 + icon 24 + 转场（dissolve/dip/directional/bridge）+ 章节标题图形 + 片头/片尾/fade/署名 roll + 字幕样式升级 + MotifRegistry + Visual QC v2 | 机器 Visual QC 全 PASS；Truth 校验（图形数字==原文数字）；预算/禁令全绿 | **Coral 观看 Round 2 + 盲测预演（n≥10，仅 coral，定性）** |
| **P3 = 绿幕 + 音频 + 调色** | 杀死：绿幕廉价感、无 BGM/SFX 的测试产物感 | Chroma pipeline + 程序化 BGM/SFX + ducking + 全局 grade | 抠像质量校验；混音 QC（BGM≤VO-8dB、无削波）；绿幕 0 全屏 | **Coral 观看 Round 3（听感重点）+ 盲测 #2（coral + B 主题）** |
| **P4 = 广度验证 + 正式盲测 + 收口** | 验证泛化（不靠珊瑚特调）+ 统计上正式的盲测 PASS | Test B/C/D 全链路 + Visual Quality Score 终版 + 盲测正式验收（n≥20 对）+ 验收文档 | 机器分每维 ≥6；盲测 PASS 判定（§21.5）；无违规 | **Test A–D 全过 + 盲测 PASS → 人工最终裁决（不自动 SEAL）** |

- **Coral = 第一验收**（P1 起每阶段都先看它）；B/C/D 不再前置，后移到 P3/P4（B 提前到 P3 盲测，C/D 在 P4）——理由：先把 Coral 的视觉质量做到"肉眼认可"，再花新主题成本验证泛化；
- 每阶段独立 Gate + 人工裁决；P1 未获授权不动 3.2b。

---

## 25. 能力依赖（v2 更新）

| 能力 | 依赖 |
|---|---|
| Director 创意规划 | **本地 LLM（Qwen2.5-3B-Instruct Q4，CPU）**；回退=规则规划器（无 LLM） |
| Validator / 预算 / 白名单 / QC | Python 确定性（无 LLM） |
| 图形/icon/排版 | 程序化绘制（PIL/ffmpeg，无模型） |
| 绿幕抠像 | ffmpeg chromakey（无模型；可选 u2net 增强，非必需） |
| BGM/SFX | numpy 程序化合成 / CC0 门（无模型、无 key） |
| **GPU** | **不需要**（LLM 走 CPU 量化；全链无 GPU 依赖） |
| 新本地模型 | 仅 LLM Director 一个（~2GB Q4）；其余零新增 |
| API key | **零**（本地 LLM + Commons + 程序化音频） |

---

## 26. 风险（v2 更新）

1. **LLM JSON 不稳定** → 解析重试 + 规则回退 + Validator 硬门（三级防线）；
2. **LLM 违反安全边界** → 白名单前滤（LLM 根本看不到 UNKNOWN/UNSAFE）、事实锁、Validator 断言——安全不依赖 LLM"自觉"；
3. **CPU 推理速度** → 3B Q4 分钟级/计划，非实时需求可接受；1.5B 备胎；
4. **生成非字节级确定** → 工件级冻结 + 规则回退字节级（§19 已如实重定义验收口径）；
5. **视觉改善仍是主观题** → 盲测统计（§21）+ 每阶段人工观看 + 不调线；
6. **触碰 SEALED 3.2b** → §23 重开协议（新增-only + 字节级回归 + 备份回滚）；
7. **图形/动效质感仍不及剪映模板** → 目标"不明显低于"（非劣），如实报告分差；
8. **素材天花板仍在** → 表达阶梯 + 图形系统是确定性系统的强项，做精它；
9. **多主题泛化** → Test B/C/D + 禁止主题专用规则；
10. **工量/排期** → 四阶段独立裁决，随时止损；LLM 模型下载与调试列入 P1 首步（hf-mirror 重试）。

---

## 27. 业界参考（保持 v1 §23，不照搬）

FilMaster / Camera Artist / AniME / MAViS / Veo 3.1 presets —— 借鉴点不变："独立 shot-plan 层 + 有限镜头语言 + 一致性契约"；**v2 差异**：参考其"创意规划与约束校验分离"的做法，本设计以 LLM+Validator 实现同等分离（多数参考系统用纯 LLM 规划 + 生成模型执行，本项目以确定性执行层替代生成模型）。

---

## 28. Stage 3.3 完成后的目标效果（v2，10 条可核查）

1. 每句信息有视觉表达方案（素材/图形/排版），且 `why_this_expression` 可审计；
2. 镜头语言有语义理由（升高=上移、强调=推近），无随机晃动、无裸 Ken Burns 全程；
3. 全片有 arc：开场/发展/加速/高潮/收束，切点不必等于句号；
4. 转场克制：默认硬切，时间/话题/因果处少量 dissolve/dip，无每镜一转场；
5. 文字卡率 ≤30% 且连续 ≤2、排版化、微动效；数据/对比/因果/空间信息优先图形化；
6. 全片风格一致（同族配色/字体/图形语言），母题有回收（开场元素在结尾呼应）；
7. 有片头处理与片尾（fade-out + 署名 roll + 落版）；
8. 绿幕 0 全屏；视频素材不裸播、不叠全屏文字；
9. BGM 只衬情绪不抢 VO，SFX 只在有理由处；
10. 全链可审计（计划 SHA + validator_log + decision_chain + 白名单 + Truth 锁），机器分每维 ≥6，盲测"不明显逊于剪映"占比 ≥70%（n≥20 正式验收）。

---

## 29. 范围与停止线（v2）

- 本轮交付：本文档 v2 + `docs/STAGE33_SCHEMAS.md` v2（仅两份文件更新）；
- **不实现、不改代码、不碰 SEALED、不下载模型、不进入 P1**；
- 待人工裁决：① LLM Director + Validator 架构；② 本地 Qwen 模型选型；③ §23 重开协议；④ P1（Coral MVP）是否启动；⑤ 盲测口径（§21）。

---

## 附：20 问速答（v2 口径）

| # | 问题 | 答案 |
|---|---|---|
| 1 | 为什么机器 PASS 却不如剪映 | §2：Gate 覆盖域不含视觉表达；缺表达决策层 |
| 2 | 3.3 根因 | 补上"怎样讲视觉故事"的决策层（LLM 创意 + 确定性把关） |
| 3 | 四层边界 | §3：2.x=说什么 / 3.1.4=有什么安全素材 / 3.3=怎么视觉化 / 3.2b=怎么执行 |
| 4 | 完整架构 | §4（sanitizer→LLM Director→Validator→plan→Executor） |
| 5 | Beat 如何生成 | §7：LLM 提议 + Validator 落地（span 逐字/时长比例） |
| 6 | 选表达而非选素材 | §8：六档阶梯 + TEXT_CARD 最后一级 + 素材不足≠自动卡 |
| 7 | 静态图/文字卡泛滥 | §10 motion 多样性下限 + §8 连续/模板禁令 + §14 图形映射 |
| 8 | 绿幕 | §15（P3）+ §9.3（P1 禁全屏文字先行止血） |
| 9 | motion/transition/graphics | §10/§13/§14（有限语法 + 默认硬切 + Truth 锁） |
| 10 | Truth/Rights/provenance | §5/§6/§14/schema：白名单前滤 + 事实锁 + 断言 + 全链留痕 |
| 11 | Visual QC | §20（机器 14+ 项 / 人工 6 项） |
| 12 | 量化像不像剪映 | §21 盲测：非劣占比 ≥70%（n≥20）+ 逐维差 ≤1.0 |
| 13 | P1–P4 | §24（MVP 先行：P1 Coral 肉眼可见变好） |
| 14 | LLM 依赖 | §25：Director 用本地 LLM；其余零 LLM |
| 15 | 本地模型 | 仅新增 Qwen2.5-3B Q4（~2GB）；可选 u2net |
| 16 | GPU | 不需要 |
| 17 | 代码量 | 待 P1 授权后评估（预计与 v1 同量级 ~10k 行，但顺序重排） |
| 18 | 最大风险 | §26（LLM 稳定性/安全/确定性口径/SEALED 触碰/主观题） |
| 19 | Test A–D | §24：Coral 先行每阶段验收；B 入 P3 盲测；C/D 入 P4 |
| 20 | 最终效果 | §28 十条 |
