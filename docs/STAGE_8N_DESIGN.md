# Stage 8N：Visual Planning Optimization — 设计

> 状态：**设计待裁决**。只定义优化设计与验收标准，不实现。
> 约束：不接视频生成；不接素材库；不新增 Agent；不修改 Evidence/Truth Layer；不扩大系统边界。

## 1. 背景：Stage 8M 暴露的两个生产质量问题

| 问题 | 8M 实测 | 根因（已定位） |
|---|---|---|
| P1 时长超目标 | VIDEO-10=1194s（目标 540-660s，+81%）；VIDEO-15=1686s（目标 810-990s，+70%） | 高事实密度 claim 被过度拆分：每个被覆盖的数字生成 1 条独立"事实核查"段落（SC-HD 达 8 条），单 claim 平均 15.6 段（设计估算 7 段）；duration=shot_seconds×强度 在 78/107 镜上聚合放大 |
| P2 视觉重复 | 最大同型连串 23；连串≥3 占比 55.1%/50.5%（阈值提示 max≤5、≤40%） | visual_target 仅由段落 role 决定，长视频拼接后同 role 场景连续出现 |

## 2. 优化边界（硬约束）

| 允许 | 禁止 |
|---|---|
| 修改 `visual_planning.py`（8L 层本身，非冻结层） | 修改 Evidence/Truth Layer（8D-8F 冻结） |
| 在层内加：Scene 预算、事实合并、视觉多样性、密度加权时长 | 新增 Agent / 新层 / 新系统能力 |
| 确定性规则（无 LLM、无随机） | 接视频生成 / 素材库 / TTS / 发布 |
| 长视频组装仍为 test-side 编排（层只接受"更长的脚本"） | 针对具体网站/domain/claim 写特例 |

**要点**：优化发生在 scene 生成逻辑内部（`build_scene_blueprint` / `build_production_plan`），输入仍是"风格化脚本的段落序列"，输出仍是 Scene Blueprint——不扩大系统边界；Evidence 引用、参考来源、[EDIT]/[待补] 语义原样保留。

## 3. A. Scene Budget Control 设计

### A1. 块（Claim）到 Scene 数量限制

层将 `transition` 段落视为**块边界**；每块（一条 claim）的 scene 预算：

| 段落 role | 预算 | 压缩规则 |
|---|---|---|
| hook + hook_alt | 1 scene | hook_alt 并入 hook scene 的 `hook_alternates` 字段（不独立成镜） |
| conclusion_first | 1 scene（可并入结论段，见 B2） | — |
| body（子命题） | **≤3 scene** | 超过 3 个主体段时，第 4 段起并入第 3 个 body scene（文本以"；"连接，`source_paragraphs` 记录合并范围） |
| fact（事实核查） | **≤1 scene** | 全部 fact 段合并为 1 个"事实核查"scene；单 scene 至多列 4 条事实，溢出记"…等 N 项"，**所有 [n] 引用全部保留**（`fact_refs` 数组） |
| gap | ≤1 scene | — |
| conclusion | 1 scene | — |
| transition | 1 scene（块间） | 视觉改为"转场字幕卡"（新增映射条目） |

**每块上限 = 8 scene**（hook1 + conclusion_first1 + body3 + fact1 + gap1 + conclusion1）。
8M 实测 15.6 段/claim → 压缩后 ≤8 scene/claim，VIDEO-10/15 的场景数由 78/107 降至约 **≤45/≤70**。

### A2. 高事实密度压缩规则（针对 P1 根因）

1. **fact 合并**：同一块内所有"事实核查"段落合并为一个 scene，`fact_refs: [{fact, ref_index}]` 全量保留（SC-HD 的 8 条 → 1 条）。
2. **fact 紧跟 body**（B2）：合并后的 fact scene 紧随该块最后一个 body scene，形成"论证→核查"单元，不再散落。
3. **body 合并**：子命题 >3 时合并且不丢文本——每个 scene 的 `source_paragraphs` 记录合并的源段落索引，保证覆盖可审计。

### A3. 信息密度与时长平衡

**时长模型**（确定性，无随机）：

1. **无目标时长**（默认，兼容 8L 单 claim 行为）：`dur = shot_seconds × intensity`，**保持不变**。
2. **有目标时长**（长视频，`build_production_plan(..., target_seconds=600)`）：
   - 密度权重：`w_i = 1 + len(subtitle_emphasis_i) + len(script_text_i)/50`（复用 8M B8 密度定义）；
   - 按权重分配：`dur_i = target_seconds × w_i / Σw`；
   - clamp 到 `[4s, 30s]`；
   - 残差二次分配（clamp 造成的缺额/超额按剩余权重再摊一次），保证 Σdur 收敛于 target ±2%。

该模型直接实现"高密度场景占更多时长、低密度场景压缩"，同时满足 P1 的时长预算。

## 4. B. Visual Diversity Constraint 设计

### B1. 连续同视觉类型限制

- 参数 `MAX_VISUAL_RUN = 3`：同 `visual_target` 连续出现 ≤3 次。
- 每个 role 的视觉**变体池**（按序轮换，超过连串上限时取下一变体）：

| role | 变体池 |
|---|---|
| hook | 口播+大字标题卡 → 快切素材+大字标题卡 → 口播+全屏数字卡 |
| body | 数据可视化+证据截图 → 概念动画+口播 → 实拍素材+数据角标 |
| fact | 事实核查字幕卡 → 来源截图+引注 → 核查清单卡 |
| conclusion | 结论大字卡+落版 → 结论口播+呼应画面 |
| transition | 转场字幕卡（固定） |

- 连串计数**跨块连续**（transition 的"转场字幕卡"天然断串）；应用变体后连串归 1。
- B-roll 需求保持随 role 不变（只变画面主类型，不新增素材库依赖）。

### B2. Role 转换规则

1. fact scene 必须紧随本块最后一个 body scene（"论证→核查"单元）。
2. gap scene 必须在 conclusion 之前（提示缺口后再收束）。
3. conclusion_first（若存在）紧随 hook；若块内无 gap 且 body≤1，conclusion_first 与 conclusion 合并为一个"结论"scene（`source_paragraphs` 含两段），节省 1 镜。
4. transition 段落必须位于块首（test-side 组装已保证；层侧校验并原样映射）。

### B3. 长视频节奏控制

1. 每块 ≤8 scene（A1）+ 块间 transition（断串 + 情绪锚点）。
2. 视觉连串 ≤3（B1）跨块生效。
3. 密度加权时长（A3）使高密度段不拥挤、低密度段不拖沓；8M B8"密度-节奏失配 ≤10%"继续作为验收。
4. 情绪曲线沿用 8J 输出，8M B6"块内情绪跳变 ≤2"继续验收（本优化不改情绪层）。

## 5. 验收指标与成功阈值

| # | 指标 | 成功阈值 |
|---|---|---|
| 1 | 时长达成率（P1 修复） | VIDEO-10 B站总时长 ∈ **[540,660]s**；VIDEO-15 ∈ **[810,990]s**（±10% 含界） |
| 2 | Scene 预算 | 每块 scene ≤8；VIDEO-10/15 scene 数 ≤45/≤70（报告，不硬卡） |
| 3 | 视觉重复（P2 修复） | 最大同型连串 **≤3**；连串≥3 占比 **≤20%** |
| 4 | Script-Scene 覆盖完整性（替代 8L 的 1:1 映射） | 每 scene 的 `source_paragraphs` 并集覆盖全部段落、无重叠遗漏 = **100%** |
| 5 | Evidence-Visual 引用保持 | 每 scene 引用与源段落引用一致；全局参考表 [1..N] 唯一连续 = **100%**（长视频与单 claim 均测） |
| 6 | Production Plan 可执行性 | 每 scene 含 visual_target/subtitle_emphasis/duration_hint = **100%** |
| 7 | 字幕重点标注准确性 | 5 条 stress claims must-contain 全中 + 无"是不是"误标 |
| 8 | 信息密度与节奏匹配 | 高密度+短时长失配率 **≤10%**（8M B8 口径） |
| 9 | Scene 一致性（8M B6） | id 唯一连续 + 全局编号唯一 + 块内情绪跳变 0 + transition 定位正确，全过 |
| 10 | 人工制作成本估算 | 报告型：输出 VIDEO-10/15 总工时与每千秒工时，与 8M（14.7h/19.8h）对比变化量 |
| 11 | 冻结回归 | 15 套件 0 失败 + `semantic_judge.py` SHA256 不变 |

**指标 4 的说明（需知悉）**：8L 的"Script-Scene 1:1 映射"因合并压缩而不再成立，正式替换为"覆盖完整性"（source_paragraphs 可审计）。此为本次优化对验收口径的既定变更。

## 6. 回归方案

1. **冻结回归**：15 套件全绿 + SHA256 校验（Evidence/Truth 层零改动）。
2. **8L 短 claim 回归**：49 条既有 claim 重跑 8G→8L（优化后），按新口径（指标 4-7）验收：覆盖完整性 100%、引用保持 100%、可执行性 100%、字幕 must-contain；单 claim 时长公式（无 target 分支）应与 8L 一致（不回归）。
3. **8M 压力回归**：5 条 stress claims + VIDEO-10/15 重跑，按 §5 全部阈值验收（重点：指标 1、3）。
4. **证据零漂移校验**：对比优化前后各 scene 的 evidence_refs 与 [n] 引用集合一致（只允许段落合并，不允许引用丢失/改写）。
5. 失败项只报告事实/数据/根因，**不自动二次修复**（阈值不达标 → 报告并停）。

## 7. 不做什么

- 不实现（本阶段仅设计）；实现待裁决后单次执行。
- 不接视频生成/素材库/TTS/发布；不新增 Agent；不改 Evidence/Truth Layer；不扩大系统边界。
- 不用 LLM/随机（全部确定性规则）；不针对具体 claim/site 写特例。

## 8. 实施步骤（裁决后执行）

1. 修改 `visual_planning.py`：A1/A2（块预算+fact 合并）、A3（密度加权时长）、B1（变体池+连串上限）、B2（role 转换）、transition 视觉条目。
2. 更新 `scripts/eval_stage8l.py` 口径（映射→覆盖）并重跑 49 claim。
3. 更新 `scripts/eval_stage8m.py`（目标时长参数 + 新阈值）并重跑 stress + VIDEO-10/15。
4. 15 套件回归 + SHA256。
5. 产出 `r1_stage8n_report.md`，逐项对照 §5 阈值，停止等待裁决。
