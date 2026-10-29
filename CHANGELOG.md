# Changelog

本文件记录版本级变更与 Bug 修复（防止升级回归）。运行时决策/变更审计另见数据库 changelog 表。

> **编号说明（5-K 补记，2026-09-21）**：5-H / 5-I / 5-J / 5.x Final / 5-K 五个阶段**未自报** `V2.5.x` 版本号
> （仅在阶段报告中以 `Phase5H`…`5-K` 命名），故本文件按**官方阶段名**排列条目，**未回填、未重编号**任何历史 `V2.x` 编号；
> `V2.5.7`（5-G）保持原编号，仅由文件末尾移回倒序位置（原文未改）。

## Phase 60 — **解释级可视化生成器 MVP**（语义驱动解释动画 · F17 端到端）（2026-10-17）

- **新增模块 `core/explain_viz.py`**（P59 审计缺口 #1 的最小可验证实现）：
  输入 = 旁白 cue 时间轴 + 显式语义节拍计划（逐拍 narration/semantic_tag/
  explanation_goal/expected_understanding/词锚）；`validate_beat_plan` 校验
  （旁白引用逐拍比对 cue、解释拍必须带 goal、节拍空隙 ≤3s，失败 fail-closed
  拒绝渲染）→ 确定性模板渲染（coloring/counting/checklist/collapse/timeline/hold）
  → mp4。同输入同输出（T6 sha 一致），无网络无随机（地图种子固定）。
- **Bug 修复（`_tpl_coloring` 解包错位）**：`regions` 元素为 `(rid, col, poly)`
  三元组，旧代码按二元组解包导致多边形坐标损坏（历史渲染为几何垃圾帧且无
  像素级检查可拦）。修复冲突描边同错；新增测试 **T9 渲染级像素门**（区域质心
  必须等于调色板色）封堵该类缺陷；新增 **T10 真实交付计划契约校验**。
  `tests/explain_viz_test.py` 8→**10 项全过**。
- **F17 端到端（解释动画接入真实工作流）**：`docs/regression_2x/p60_2_render_f17.py`
  修复景窗假窗口（48.6s → EP2 真实 61.74s，此前 NARRATION_INCOMPLETE BLOCKED 的
  根因）+ 词级清单越界裁剪。3 景 × 3 段解释动画经项目级 pins 钉定，既有管线
  （PI 门 / P58-2 视频通道 / 词级字幕烧录 / H7）零改动出片：
  `projects/p_f084eb26e184/output/t_4f182e0dbe7c_draft_with_outro_v2.mp4`
  （63.767s）。签名门 10 cues 全 word_exact / 分配指纹 3/3 / **独立四门 9/9**
  （覆盖 99.8%、句起点同步 median 0.0000s）。
- **A/B 对照与语义同步验证**（`docs/regression_2x/p60_3_ab_verify.py`，5/5）：
  同旁白同音频（wav sha 级同源），像素级证明冲突红描边只出现在「相邻」词锚
  窗口内（11.64–14.14s）、着色推进单调、终态绿清单锚定「跑完」60.85s。
  产物 `output/p60_ep2/`（beat_plan_v2 / render_evidence_v2 / ab_stats_v2 /
  ab_frames/ / fixture_f17.json / 进度报告 P60_PROGRESS_REPORT.md）。

## Phase 58 — **视频素材接入**（垂直切片 + F14 全片视频版）（2026-10-11）

- **P58-1 采集**：Pexels Videos（`stage33/pexels_source.py` 适配器首次接入生产）；
  8 景人工精选英文查询 → 8 个横幅 mp4 入池
  （`projects/p_3e9292101f10/media/p58_videos/`，payload `logs/p58_video_payload.json`）。
- **P58-2 建池/渲染**（`agents/editing/agent.py`）：候选 `media_type=video` 显式声明
  才收；可用性 = ffprobe（宽/高/时长 ≥3s，坏文件 fail-closed）；逐景装配支持
  **视频条**：`-ss 0 -t ceil(d)+2` 输入 + `trim→tpad=stop_mode=clone→trim` 滤镜链
  （素材短于景长**定格末帧**、时长契约在视频轨成立）；视频音轨不进 filter_complex
  ⇒ 旁白优先语义不变；视频景**禁用运动层**（素材自带运动，且避免覆盖 tpad 链）。
- **P58-3 门适配**：`_verify_scene_frames` 对视频素材**抽首帧作参照**
  （缓存 `<video>.ref.jpg`），修复「PIL 打不开视频 ⇒ 无参照 ⇒ 假失败」。
- **验证**：`tests/p58_video_material_test.py` **10/10**（可用性/坏文件/混排装配/
  时长契约/真实运动/定格/参照帧）；真实 Pexels 视频 1080p 探针 rc=0、时长 11.0s；
  既有套件无回归。
- **P58-4 F14 全片视频版**：15 景 × 1 条**专属** Pexels 视频（按逐景旁白语义精选
  查询、视频 id 全局去重、时长 ≥ 景长）；`_verify_scene_frames` 视频参照改
  **按取样时刻抽源帧**（`ref_<t>.jpg`，运动视频不再假失败）；`render_arbitration`
  对视频素材用参照图送 VLM；仲裁 2 景救回 / 0 失败。**36 景 = 36 独立素材（复用 0）**：
  10 黑板主线 + 11 锚定史证图 + 15 视频。四门 9/9；成片
  `t_7968f9ac5fe7_draft_with_outro_v2.mp4`（697.534s / 113.5 MB），渲染 366s。

## Phase 57 — **生产 cue 路径修复**（测试修了、生产没接 · 第五例）+ **F12 烧录实测验证**（2026-10-11）

**P57-1 生产 cue 路径修复（`agents/editing/agent.py` + `core/captions.py`）**
- **缺陷（F10.1 105-cue-178s 的直接死因）**：`_narration_args` 内 cue **第二套分发**
  用旧词级路径 `build_cues_from_words` **无条件覆盖** P55-1 `build_cues_from_words_exact`
  的产物（voice 产物不带 `audio_time_base_s` ⇒ `segment_windows=[]` ⇒ `windows=None`
  ⇒ 词的段内时钟无窗裁剪）——烧录 ASS 105 条压缩在 0.1–178.363s（median 1.0s、
  102 条 1.0s 钳制、cue2 58.6s），178.4s 后 519s 零字幕；dump 的 `cue_source` 标签
  与逐条 `source` 不符即铁证。**「测试修了、生产没接」第五例**。
- **修复**：① cue **单一分发链** word_exact → audio_anchor → uniform（plan-only），
  旧词级路径生产退役（函数保留供历史测试，不保留双路径）；② **生产断言**
  `core.captions.production_cue_violations`（构建后烧录前 fail-closed：跨度 ≈ 实测
  音频 ±2s / median ≥3s / 重叠 0 / 条数 101–111，违规即 TASK_BLOCKED 不渲染）；
  ③ dump 增记 `cue_gate` 与逐条 `source`（标签/实际不符在 dump 层即可发现）。
- **连带修复（本轮实测照出的静默缺陷，`logs/p57_erratum.json` D1–D5）**：
  - **D2**：P56-2 pins 块 `_AL` UnboundLocalError 被 except 吞掉 ⇒ **钉定机制自
    P56-2 登记起从未生效**（F10.1 的 36/36 实为确定性求解器复现）。修复：块内
    显式导入 + `applied/missing` 留痕 + 求解器**之后** pins 终局强制（锚定守卫复跑）。
  - **D3**：`build_cues_from_words_exact` 钳制依据由**句首词所在窗**改为
    **句末词所在窗**——v6.5 静音吸附切景存在句中切景，旧依据致句尾语音无字幕
    （实测 31 处 / 61.45s，覆盖 89.5% < 95%）。
  - **D4**：`_walk_match` 尾句重分——TTS WordBoundary 文本每段比旁白少 2–6 字，
    主循环耗尽词流时末尾 1–2 句无自己的 cue（全片 10 句、起点偏差 >1s 达 9 句）；
    改为末组延伸到最后一词后**按字符比例重分**（每句 ≥1 词）。
- **测试**：`tests/p57_cue_contract_test.py`（8/8）——**before 夹具永久留档**
  F10.1 烧录 ASS 的 105-cue-178s 签名，并断言生产门必须拦下它、
  `_narration_args` 不再调用旧词级路径。

**P57-2/P57-3/P57-4 F12 渲染 + 烧录实测验证 + 登记**
- F12 = 沙箱 `p_3e9292101f10` 重跑 editing（v6.5 音频／分配／画面**零改动**：
  分配指纹 **36/36** 与 F10.1 一致，H7 音轨逐字节一致）⇒
  `t_3553b076b02d_draft_with_outro_v2.mp4`（697.534s）。
- **四门（烧录 ASS / 成片混音独立口径，禁止循环）9/9**：覆盖 **100.0%** /
  median **5.400s** / 1.0s±0.1 cue **0** / 同时活跃 max 1 重叠 **0** /
  句起点同步 median **0.0030s**、>1s **0**（句 111）＋ 3 景帧检 3/3。
- **erratum（循环论证第四例）**：F6–F10.1 字幕门全系构建器输出自测；
  **F12 起以烧录 ASS 为唯一字幕口径**。登记 `logs/p57_erratum.json`、
  候选 `logs/p57_4_delivery_candidate.jsonl`（append-only、零 promotion）。
- 预算：LLM ≈$0.006（VLM 仲裁 13 调用）/ 渲染 7 次 ≈38 分钟。中间 4 轮无效
  渲染隔离于 `output/_quarantine_p57_*`（含一次 VLM PROVIDER_TIMEOUT 阻断，
  fail-closed 正确）。

## Phase 56 — **分配可复现**（正确性缺陷修复）+ **F10.1 单变量字幕版**（2026-10-03）

**P56-1 分配确定性修复（监理升格为正确性缺陷）**
- **缺陷**：**分配不可复现** —— P47-3 我加的「种子若越份额门则**丢弃**」使
  **种子是否被丢取决于输入状态** ⇒ **同输入两次运行的解不同**
  ⇒ P55 实测 F10 与 F9 画面**仅 4/36 景一致** ⇒ **单变量对照失效**。
- **修法（授权书 §1）**
  1. **废除越界弃种**：保留 `initial` 种子；份额越门则**求解后如实报告**
     —— **门的裁决权在门，不在求解器的自我审查**；
  2. **固定搜索预算与 seed**：`solver_seed=20261002`、`restarts=40`、`iters=1500`；
  3. **harness 前置断言**：同输入**连跑两次**求解，`assignment_fingerprint`
     （新增 `core/allocation.py::assignment_fingerprint`，逐景 `scene=asset` sha256）
     必须一致；**不一致 ⇒ 渲染前 fail-closed**。
- **实测**：`deterministic=True`；两次指纹 `f7ef66b900b3df43` **完全相同**；
  `seed_rejected` **已消失**（种子被保留使用）。

**P56-2 F10.1 单变量字幕版登记**
- **机制**：外部开关 `logs/p56_2_f9_pins.json`（存在即生效）把 **F9 逐景已选素材
  强制写回** `selected_asset`，位置在**锚定守卫之前** ⇒ 锚定仍可兜底。
- **★ 单变量成立：与 F9 逐景素材 36 / 36 景一致（不一致 0）**
  ⇒ **F10.1 与 F9 的唯一差异 = 字幕层**。
- `projects/p_47a8cc7c1703/output/t_e2334dafa442_draft_with_outro_v2.mp4`
  （**32,454,252 B**，697.534s）；**`render_output` = `a_842a53e24b4f`**；
  `logs/p56_2_delivery_candidate.jsonl`（append-only、零 promotion）。
- **全门**：时长 697.534s（契约 695.528±1）✔｜**A2 Δ 0.000s** ✔｜满覆盖 ✔｜音轨逐字节一致 ✔｜
  **逐景 36/36、0 失败** ✔｜**DQ-2 PASS（唯一素材 30；max_share 0.0667）** ✔｜
  **DQ-3 PASS** ✔｜**DQ-3e PASS（0 处）** ✔｜**重叠门 3/3（max 1 / 重叠 0）** ✔｜
  **覆盖门 4/4（99.3%；median 5.720s；clamp 0）** ✔｜**锚定 4/4** ✔｜
  **内容排除 4/4** ✔｜**name 中立 3/3** ✔｜**no_picture 2/2** ✔｜**比喻配额 7/7** ✔｜
  **分配求解器 7/7** ✔｜**确定性断言 PASS** ✔。
- **对照声明写入登记**：`per_scene_table`（36 行逐景对照）+ 唯一差异 = 字幕层。

**F9 / F10 / F10.1 关系**
| 版本 | 字幕 | assignment | 与 F9 画面 | 用途 |
|---|---|---|---|---|
| **F9** | 音频锚定 | 不可复现（当时未察） | — | 字幕层四幕终章 |
| **F10** | 词级精确 | 重算 | **仅 4/36 一致** | **单变量失效** |
| **F10.1** | 词级精确 | **钉定 F9** | **36/36 一致** | **★ 单变量字幕验证版** |

**P56-3 收尾**：材料包 `logs/phase56_promotion_package.json`；全量回归 ——
**94/94 rc=0，0 失败（2126.3s）** ✔。

**⚠ P56 首轮回归的 10 个失败 —— 全部源于本轮引入的代码，非产品缺陷（已修）**
- **缺陷 1｜词覆盖断言过严**：`build_cues_from_words_exact` 的断言 d 在
  **段级 / 空 manifest** 的单测夹具下误判（`assigned=0` 是**输入没有可用词**，
  不是归属缺陷）⇒ 6 个套件从绿转红。
  **修法**：加**适用条件**（`total_words>0` **且** `covered_paras>0` 才断言；
  真实渲染路径照常执行）。**复验**：`scene_assembly_test` **15/15**、
  `narration_contract_test` **45/45**、`integrity_truth_test` **243/243**。
- **缺陷 2｜fail-closed 分支 `engine.emit` 未守护**：测试桩 `Eng` 没有 `emit`
  ⇒ **原始错误被替换成 `AttributeError`，掩盖真实原因**。
  **修法**：`getattr(engine,"emit",None)` + `callable` 守护，
  **无论 emit 成败都继续 raise 原异常**（不吞错、不改语义）。**复验** 15/15。
- **修复后重渲内容与已登记 F10.1 等价**：与 F9 逐景素材 **36/36 一致**、
  `deterministic=True` ⇒ **确定性修复生效**（这正是 P56-1 的目标产物）。
- **教训（与 P53 规则同族）**：两处都是**把「生产路径的假设」直接搬进可被单测复用的
  构建器**（生产有齐备 manifest、有 `emit`；单测没有）⇒ 构建器被复用时必须
  **显式声明输入前提**，并区分「前提不满足(SKIP)」与「真实缺陷(FAIL)」。
  账本：`logs/p56_2b_self_defect_fixes.json`。

**黑板基底**：待用户从 v1/v2/v3 选定；主线批量生成排 **Phase 57**。
**边界**：LLM **$0**、网络 0、生成 ¥0、渲染 2 次；
`config.json` / `core/materials.py` **pin 校验未改**；**未 promotion、未发布**。

## Phase 53 — **agent 调用形状统一**（消灭 per-scene 分叉）+ 穿透式验证规则 + F9 登记（2026-10-03）

**P53-1 转储定案（根因，机械确认 —— 与监理预判一致）**
- **窗对齐越界**：`segment_windows`（来自 `narration_plan`）长度 = **段数 9**，
  而 `segments` 是**景数 36** ⇒ `si >= 9` 时 `windows[si]` **越界** ⇒
  静默回落 `w0=0 / w1=None` ⇒ 该景 cue 用**景内局部时刻**、**不被窗裁剪**、
  `end` 变成时长。
- 实测 cue 转储（写盘前）：`P04_2 start=0.0`、`P08_2 dur=-2.023`（**负值**）、
  段序错乱（index0=P04_2、index1=P08_2 —— 未按 start 排序）。
  ⇒ 烧录 ASS 呈现 `start=上条 end`、`end=下条时长` 的交错。
- **修法**：窗口改从**景自身**取权威字段 `segment['audio_window_s']`（36 条），
  与内联测试**形状一致**（36 景 ↔ 36 窗），**一次全片调用**；
  缺字段时按 `actual_tts_duration_s` 累积回退。**per-scene 分叉已消灭。**
- **验证**：修复后 cue 转储 `index0 = P01_1 / start=0.196 / end=5.529 / dur=5.333`（正）；
  **烧录 ASS 与转储逐条一致**。

**P53-2 F9 登记**（复测对象 = **烧录产物**，非构建器输出）
`projects/p_fa647ea270d9/output/t_ac3f73f3710a_draft_with_outro_v2.mp4`
（**33,107,713 B**，697.534s）；**`render_output` = `a_c5cdd706962e`** + `attribution`；
`logs/p53_2_delivery_candidate.jsonl`（append-only、零 promotion）。
**全门**：时长 697.534s（契约 695.528±1）✔｜**A2 Δ 0.000s** ✔｜满覆盖 ✔｜音轨逐字节一致 ✔｜
**逐景 36/36、0 失败** ✔｜**DQ-2 PASS（唯一素材 30；max_share 0.0667）** ✔｜**DQ-3 PASS** ✔｜
**DQ-3e PASS（0 处）** ✔｜
**重叠门 3/3**（烧录 ASS `max_concurrent 1`、重叠时刻 **0 / 6933 采样**；F7.1 为 41 / 1033）✔｜
**覆盖门 4/4**（覆盖 **99.3%** ← F8 14.2%；median **5.720s** ← F8 1.0s；
**clamp 0** ← F8 102；同步 **100.0%**）✔｜**锚定 4/4** ✔｜**内容排除 4/4** ✔｜
**name 中立 3/3** ✔｜**no_picture 2/2** ✔｜**比喻配额 7/7** ✔｜
**分配求解器 7/7（`pass=True`）** ✔。三指标按停用口径不通过（冻结 79.6%，阈值未改）。

**P53-3 两条系统规则（入 ops / tests 惯例）**
- **① 验证必须穿透生产入口**：tests 必须经 **agent 真实调用路径**运行
  （同一函数、同一入参形状），**禁止平行构造**；新门一律**对烧录产物**断言。
  **三案同族**（同一失效模式 = *测试与生产走了不同形状* ⇒ 测试全绿而产物坏）：
  · **P48** id 命名空间（独立路径 `asset_gen_*`、生产 `asset_<sha12>`）
  · **P52** 循环论证（用切片边界自测恢复点）
  · **P53** 调用形状（36 景 vs 9 窗越界 ⇒ 静默回落局部时刻）
- **② 回归窗口内冻结一切写库/渲染操作，串行执行**。
  **原因（P52 实测）**：我在回归期间并发跑渲染并新增
  `RENDER_ARBITRATION_DETAIL` 事件 ⇒ 三个只读套件
  （`mm_quality_test` / `mm_temporal_test` / `multimodal_test`）的
  「真实 DB 字节与五张表行数前后一致」断言被我的写入打破 ⇒
  **90/93，3 个失败全是我造成的，非产品缺陷**。

**字幕层四幕处置链（终章）**
| 幕 | 阶段 | 动作 | 结果 |
|---|---|---|---|
| 一 | F6 | 用户投诉「报幕」观感 | **我误诊为素材层（公式墙）** |
| 二 | P51 | 监理帧检定位 **cue 重叠** ⇒ 排他修复 | max 同时活跃 **41 → 1** |
| 三 | P52 | 覆盖门揭示 **14.2%** 覆盖、97% cue 被 clamp ⇒ 音频锚定（独立信号源） | 构建器输出 **99.3%** |
| 四 | **P53** | 烧录 ASS 复测仍坏 ⇒ 转储定案 **36 景 vs 9 窗越界** ⇒ 调用形状统一 | **烧录产物 max 1 / 覆盖 99.3%** |

**收尾**：材料包 **v5 终版** `logs/phase53_promotion_package.json`；
全量回归 —— **94/94 rc=0，0 失败（2644.5s）** ✔
（含新增 `caption_overlap_test` **3/3**、`caption_coverage_test` **4/4**、
`asset_name_neutral_test` **3/3**、`anchor_policy_test` **4/4** 等）。

**回归的两项未决：均已收敛，且根因比初判更精确**
- **未决 1｜`caption_overlap_test` 作用域（已修）**：原 `latest_ass()`
  “找不到就 glob 全库取最新” ⇒ 回归期间**读到别的工程产物**（同一份 ASS 独立复跑
  **3/3 PASS**、回归内 **1/3 FAIL**）。改为**只认 fixture 指定工程**并**显式打印读数来源**
  （`来源 fixture:<pid>`）⇒ 回归内 **PASS**。
  **这正是 P53 新规则①「验证必须穿透生产入口、禁止平行构造」的落地**。
- **未决 2｜`mm_quality_test` 的 DB 只读断言（已收敛，无需改代码）**：
  **真正根因 = 两个回归并发运行**。我先前那次“干净回归”（92/94）实际与
  **F9 的回归（`pwsh-2081`）时间窗重叠**，两个 runner 同时写库 ⇒ 只读断言被对方打破。
  **本次 F9 回归在完全独占条件下运行 ⇒ `mm_quality_test` PASS**
  ⇒ **证实该项不是产品缺陷，而是“并发回归互相干扰”**。
- **最终结论：94/94 全绿**。教训修正：纪律层“我回归期间不写库”是
  **必要但不充分** —— 还必须保证**同一时刻只有一个回归在跑**（runner 层互斥），
  否则**两个 runner 会互相打破对方的只读断言**。

**边界**：LLM **$0**、网络 0、渲染 2 次；
`config.json` / `core/materials.py` **pin 校验未改**；**未 promotion、未发布**。

## Phase 52 — 词时刻**音频锚定**（独立信号源）+ 覆盖门；F9 **fail-closed**（2026-10-03）

## Phase 51 — 词级 **cue 排他修复** + **重叠不变量门** + F8 登记（2026-10-03）

**⚠ 报幕真因（用户自 F6 起反复报告，我误诊了 5 个阶段）**
- **真因 = 字幕 cue 大面积重叠**，**不是素材问题**。
- **根因**：`core/captions.py::build_cues_from_words` 把**段内局部**词偏移当成
  **景内局部**偏移，再加景窗起点 ⇒ **同一段的 N 个景各自重放整段词**。
  （词级 manifest 以**段** `P01` 为键，而一段切成 4 个景 `P01_1..P01_4`。）
- **实测 F7.1 烧录 ASS：`max` 同时活跃 **41 条** / **1033** 个采样时刻重叠 /
  最长重叠区间 **103.28s**。**

**P51-1 修复（`build_cues_from_words`）**
1. 词偏移换算为**全片绝对时刻**（= 该段**起始景**窗起点 + 词偏移）；
2. **按景窗切分词**（只保留落在本窗内的词）；
3. 施加**排他规则**（授权书 §1）：
   `cue_k = [max(句首词时刻, cue_{k-1}.end), min(句末词结束+hold, 下一句起点)]`。
- **效果**：**`max` 同时活跃 41 → 1**；**重叠采样时刻 1033 → 0**；
  **最长重叠区间 103.28s → 0.00s**；**词级同步门仍 2/2 PASS**
  （median **0.0305s**、覆盖 **97.0%**）⇒ **两门并存**。

**P51-1 新门 `tests/caption_overlap_test.py`（重叠不变量门，3/3 PASS）**
对**最终烧录的 ASS** 以 **0.1s 步进**扫描同时对活跃 cue 数；判据**运行前写死**：
O1 `max_concurrent == 1`；O2 重叠采样时刻 `== 0`；
O3 相对 **F7.1 夹具（41 / 1033）**必须有改善。
（新增扫描器 `docs/regression_2x/ass_overlap_scan.py`。）

**P51-2 F8 登记**
`projects/p_379bd4637469/output/t_bfe0eb0375b0_draft_with_outro_v2.mp4`
（**30,159,527 B**，697.534s）；**`render_output` = `a_319817fca45c`** + `attribution`；
`logs/p51_2_delivery_candidate.jsonl`（append-only、零 promotion）。
**全门**：时长 697.534s（契约 695.528±1）✔｜**A2 Δ 0.000s** ✔｜满覆盖 ✔｜音轨逐字节一致 ✔｜
**逐景 36/36、0 失败** ✔｜**DQ-2 PASS（唯一素材 31；max_share 0.0663）** ✔｜**DQ-3 PASS** ✔｜
**DQ-3e PASS（0 处）** ✔｜**重叠门 3/3** ✔｜**词级同步 2/2** ✔｜**锚定 4/4** ✔｜
**内容排除 4/4** ✔｜**name 中立 3/3** ✔｜**no_picture 2/2** ✔｜**比喻配额 7/7** ✔｜
**分配求解器 7/7（`pass=True`）** ✔。三指标按停用口径不通过（冻结 80.3%，阈值未改）。

**P51-3 两条 erratum**
- **① 我在 F6 阶段的误诊**：「报幕」观感我归因为**『公式墙类素材过多』**，
  据此做了 P44 锚定表、P46 双轨家族门等 —— **连续 5 个阶段在素材层工作，
  绕过了真因（字幕层）**。
  **教训**：**用户反复报告同一观感问题时，应优先排查该观感所在层**，而非先改上游。
- **② P50 报告与实绑不符**：P50 报告重生成的三张图中 **只有 P09_5 真正上屏**
  （实绑 `a0350ad6c921` = 重生成图）；
  **P01_1 实绑 `14bc28bf68eb`（Pexels 6238050 by Monstera 实拍）、
  P07_3 实绑 `a3aff2f300eb`（Pexels 22690748 by Vitaly Gariev）**
  —— 系**重求解后重新分配**所致。
  **绑定现状保持不变**（按授权书交用户终审裁决去留）；
  生成图与实拍图**均已入池**，用户可裁决 P01_1 开场 hook 用哪张。

**收尾**：材料包 **v5 终版** `logs/phase51_promotion_package.json`；全量回归一次。
**边界**：LLM **$0**、网络 0、渲染 1 次；
`config.json` / `core/materials.py` **pin 校验未改**；**未 promotion、未发布**。

## Phase 50 — 生成插图**去文字伪影** + **F7.1 登记** + 两个补课项（2026-10-03）

**P50-1 文字伪影重生成**
- 监理帧检确认 10 张生成插图**风格统一**，但：
  **P01_1（开场 hook）乱码文字墙必须重生成**、**P07_3（乱码标注）/ P09_5（伪公式）**
  一并重生成；其余 **7 张接受为纹理**。
- 机制：提示词追加**冻结的 `no_text` 风格变体**
  （纯几何线稿、无文字/字母/数字/书写痕迹，sha256 `84fa45c758e60e80`）
  + **强化负向提示词**（显式列 `text/letters/numbers/formula/gibberish/pseudo-text`…）。
- **3/3 一次通过**（各 1 次尝试，未用满授权书允许的 ≤2 次）；旧图存为 `*.v1.png` 供对照。
- sha 变更：`P01_1 6bc2321dd55f→27f9d79a7512`、`P07_3 19df2f12d711→3f84af39f689`、
  `P09_5 1c3a5c4bfd25→a0350ad6c921` ⇒ **`config/family_map.json` 的 G 家族 sha 前缀表同步更新**。
- **目验**：三张均为纯几何线稿（同心圆 / 交叉准星 / 网格+叠圆），**无文字、无数字**。

**P50-2 F7.1 登记**
`projects/p_06e490c43f6f/output/t_b4b8433327d4_draft_with_outro_v2.mp4`
（**31,918,843 B**，697.534s）；**`render_output` = `a_ae7a41fb1ce5`** + `attribution`；
`logs/p50_2_delivery_candidate.jsonl`（append-only、零 promotion）。
**全门**：时长 697.534s（契约 695.528±1）✔｜**A2 Δ 0.000s** ✔｜满覆盖 ✔｜音轨逐字节一致 ✔｜
**逐景 36/36、0 失败** ✔｜**DQ-2 PASS（唯一素材 30；max_share 0.0697）** ✔｜**DQ-3 PASS** ✔｜
**DQ-3e PASS（0 处）** ✔｜**词级同步金门 2/2** ✔｜**锚定 4/4** ✔｜**内容排除 4/4** ✔｜
**name 中立 3/3** ✔｜**no_picture 2/2** ✔｜**比喻配额 7/7** ✔｜**分配求解器 7/7** ✔。
求解器 **`pass=True`**；**双轨家族门** A **22.2%** ≤33% ✔｜E **44.4%** ≤45% ✔｜
G **22.2%** ≤33% ✔。三指标按停用口径不通过（冻结 90.0%，阈值未改）。
**F7 保留为证据**（授权书 §2）。

**P50-3 两个补课项**
- **① 仲裁逐景 VLM 调用明细落账**：新增独立事件 **`RENDER_ARBITRATION_DETAIL`**
  （**不改**既有 `RENDER_ARBITRATION` 字段）。实测落账 2 景，字段含
  `scene_id / arbitration / final / cost_usd / vlm.model / vlm.prompt_version /
  vlm.presence / vlm.cache_hit / vlm.error_code / vlm.frame_sha256 / vlm.asset_sha256`
  ⇒ **关闭 P49-2 审计 A1「逐笔对照不可完成」**。
  **根因说明**：`core/render_arbitration.py::apply_arbitration` **本来就**逐景算好了
  `records`（含 model / cache_hit / error_code / 处置态），只是**从未落账** ——
  故本次为**纯落账补齐**，未改仲裁逻辑。
- **② `load_env` 凭据健全性告警**：新增 `core/env.py::check_credentials()`
  —— `*_API_KEY` / `*_TOKEN` / `*_SECRET` 值若含**非 ASCII 或控制字符**、
  **空白**、或长度 **< 16** ⇒ 产出 `warning`（**不回显密钥值**，只报名称与问题类型）
  ⇒ 关闭 P47-D1 那类**静默污染**的复发风险。实测当前**告警 0 条**。

**收尾**：材料包 **v5 终版** `logs/phase50_promotion_package.json`；全量回归 ——
**92/92 rc=0，0 失败（2586.8s）** ✔
（含 `asset_name_neutral_test` **3/3**、`anchor_policy_test` **4/4**、
`caption_word_sync_test` **2/2**、`allocation_solver_test` **7/7**、`dq3e` **2/2**）。

**边界**：LLM **$0**、生成 3 张（≈¥1.5，≤¥2）✔、VLM ≤$0.2、渲染 3 次；
`config.json` / `core/materials.py` **pin 校验未改**；**未 promotion、未发布**。

## Phase 49 — 生成素材 **name 中立化** + **F7 登记** + **VLM 凭据只读审计**（2026-10-03）

## Phase 49 — 生成素材 **name 中立化** + **F7 登记** + **VLM 凭据只读审计**（2026-10-03）

**P49-1 name 投毒根因修复**
- 生成素材 `name`：`Generated concept illustration for <sid> (<旁白原文>)`
  → **`GenConcept <sid> <sha12>`（语言中立）**；`visual_hint` 另存为
  **不参与匹配**的语义字段。
- **新设计规则**：**匹配器消费的元数据字段（`name` / `relative_path`）必须语言中立**，
  禁止把 v6.5 语料 CJK 内容写进这些字段。
- **新增门** `tests/asset_name_neutral_test.py`（**3/3 PASS**）：
  N1 生成素材 `name`/`relative_path` 无 CJK（违规 0）；
  N2 全池 44 张 `name`/`relative_path` 对 **846 个 8 字旁白片段**零命中；
  N3 `visual_hint` 允许保留 CJK（证明规则是**字段级**而非全禁 CJK）。
- **修复效果（实测）**：求解器 **`pass=True`**；G 份额 **72.2% → 27.8%**；
  cap / 间距 / 相邻同素材 / 相邻同家族 / **子族相邻** 全部 **0**；锚定真越界 **0**。

**P49-1 F7 登记**
`projects/p_fd7db560531c/output/t_cfe2c5585e03_draft_with_outro_v2.mp4`
（**31,196,324 B**，697.534s）；**`render_output` = `a_345c8596c787`** + `attribution`；
`logs/p49_1_delivery_candidate.jsonl`（append-only、零 promotion）。
**全门**：时长 697.534s（契约 695.528±1）✔｜**A2 Δ 0.000s** ✔｜满覆盖 ✔｜音轨逐字节一致 ✔｜
**逐景 36/36、0 失败** ✔｜**DQ-2 PASS（唯一素材 27 → 30；max_share 0.0769）** ✔｜
**DQ-3 PASS** ✔｜**DQ-3e PASS（0 处）** ✔｜**词级同步金门 2/2** ✔｜**锚定 4/4** ✔｜
**内容排除 4/4**（三处禁入上屏 0）✔｜**name 中立 3/3** ✔｜**no_picture 2/2** ✔｜
**比喻配额 7/7** ✔｜**分配求解器 7/7** ✔。
**双轨家族门**：A **25.0%** ≤33% ✔｜E **33.3%** ≤45% ✔｜G **27.8%** ≤33% ✔。
三指标按停用口径不通过（冻结 89.7%，阈值未改）。

**P49-2 VLM 凭据健全性只读审计**（F–F6 全部渲染的仲裁记录 + 事件表全量字段）
- **A1 逐笔对照：不可完成（留档粒度不足）** —— `RENDER_ARBITRATION` payload 只含
  `arbitrated` / `still_failed` / `cost_usd` / `prompt_version`；逐景明细字段为
  `{scene_id, expected, best, corr_expected, corr_best, sample_t, fallback_state}`，
  **不含模型名 / HTTP 状态 / 是否缓存命中 / 是否降级**，且**只有失败或仲裁过的景进入明细**
  ⇒「每笔 present 裁定 ⇔ 有效 VLM 调用」**无法机械核验** ⇒ 结论「**未决**」。
- **A2 fail-closed 未被绕过（已验证，非假设）**：各候选仲裁后 `still_failed` **全 0**；
  F7 阶段**两次实测** `ASSET_INSUFFICIENT` **成功阻断**渲染（状态 `BLOCKED`，未静默放行
  无素材的景）；F4 之前 DQ-3e 门如实报 4 处违例而未放行。
- **A3 结论**：未完全证实、**未发现违例**。由 A2，误判若存在**方向应为「过严」**
  （把有效素材判为未出现 ⇒ 阻断）而非「过宽」⇒ **对交付不构成放行风险**。
  **违例 0 条 ⇒ 无需逐景重跑建议；未自动重渲任何候选。**
- **污染时点无法从只读证据反推**（`.env` 无版本历史）⇒ 如实登记为**不确定**；
  可确定边界：`urllib` 直到 P47 才第一次用该 key ⇒ **污染并非 P47 才发生，
  只可能在 P47 才显形**。
- **建议**：① 为仲裁补**逐景 VLM 调用明细**落账（模型/HTTP 状态/缓存命中/降级），
  使「每笔裁定 ⇔ 有效调用」可机械核验；② `load_env` 增加**凭据健全性告警**
  （含非 ASCII 即 warn），防再次静默污染。

**P49-3 F6 家族报告 erratum（补记，不改写数值）**
D2 —— 检索池 **12 张历史素材 `asset_id` 为 `None`**（只有 sha256）⇒
`_family_of(None, …)` 恒返回 `None` ⇒ 这些素材**绕过家族约束**；
**F5/F6 登记里的「家族份额」只统计了有 asset_id 的那部分资产**，**口径不完整**。
**F5/F6 已登记数值不改写**（历史留痕），erratum 随 F7 登记补记；
**F7 起为归一化口径**（agent 边界按 `asset_<sha12>` 补齐 `asset_id`）。

**收尾**：材料包 `logs/phase49_promotion_package.json`；全量回归 ——
**92/92 rc=0，0 失败（2453.6s）** ✔
（含新增 `asset_name_neutral_test` **3/3**；`anchor_policy_test` **4/4**、
`caption_word_sync_test` **2/2**、`allocation_solver_test` **7/7**、`dq3e` **2/2**）。

**边界**：LLM **$0**、生成 ¥0（未补图）、VLM $0、**网络 0**、渲染 2 次；
`config.json` / `core/materials.py` **pin 校验 MATCH（未改）**；**未 promotion、未发布**。

## Phase 48 — **生产/独立求解路径差异定位**（输入转储法）；F7 仍 fail-closed（2026-10-03）

## Phase 48 — **生产/独立求解路径差异定位**（输入转储法）；F7 仍 fail-closed（2026-10-03）

**方法（授权书 §1 硬要求）**：新增 `docs/regression_2x/solver_input_dump.py`，
两条路径**共用同一转储器**。生产路径在 `_AL.satisfy` 调用前落盘完整输入 JSON
（逐景候选域**保序**、`family_map`、锚定排除、cap/gap/家族阈值、seed/restarts/iters、
`initial` 指纹），独立路径同款落盘，再逐字段 `diff()`。
**禁止读代码猜测定案 ⇒ 以 diff 为准。**

**diff 结果**：`options` **36/36 景全部不同**；`input_fingerprint` 生产 `88a2e91e…`
vs 独立 `a667c5e6…`。报告 `logs/p48_1_input_diff.json`。

**⚠ 监理预判不成立**：既不是「锚定排除把抽象景削成 G-only」，也不是
「锚定×家族×cap 联合过约束」⇒ **预授权（A ≤40%）的前提未成立，未使用放宽，保持 A ≤33%**。

**真因（两段）**
1. **id 命名空间曾错配**：独立路径喂检索池的 `asset_gen_p01_1`，生产路径用时间轴的
   `asset_<sha12>`，而家族/锚定**全按前缀匹配** ⇒ 两套 id 不可互换。
   **这解释了 P47 的假象**——当时「独立路径 pass=True、G=11」是**测了另一套 id**，
   **并非可行解证据**。统一命名空间后**两条路径都失败**（生产 G=26/72.2%、
   独立 G=28/77.8%）⇒ **不存在「生产 vs 独立」的算法差异**，P47 该项推测被 diff **否定**。
2. **真正根因：P47-2 生成素材的 `name` 内嵌了本片中文旁白原文** ⇒ 中文关键词匹配器在
   **36/36 景**都给生成素材最高分（实测抽景 `P01_2`：素材分=19、命中=证明/人/从/到/字/完）
   ⇒ `_cur` 全片为 G 且被置于候选域**首位** ⇒ 求解器从「G 全置首」出发 ⇒ G 份额 72.2%。
   **根因在我的数据构造，与约束/求解器/锚定无关。**

**D1 矛盾闭环（同一 DashScope key 修复前后连通实测）**
- **修复前**：值长 162、含 23 个非 ASCII（行尾粘了中文注释）⇒ `urllib` 直接
  `UnicodeEncodeError: 'latin-1' codec can't encode`，**请求未发出**。
- **修复后**：`core/env.py::_clean_value()` 剥离行内注释 ⇒ 值长 116、非 ASCII 0 ⇒
  wanx 提交立即返回 `task_id`（`task_status: PENDING`）。
- **历史为何不报错**：① 值是在**某个时点**被污染的（污染前 P33–P46 调用正常）；
  ② 污染后走 `requests`/`httpx` 的路径会**发出坏凭据而静默 401**（错误被上层当
  「VLM 不可用」吞掉），而走 `urllib` 的**新增生成 provider** 才把异常抛出。
  **即「不是 key 变了，而是污染时点 + HTTP 客户端错误处理差异」。**
- ⚠ **待办**：对历史 VLM 调用做**凭据健全性复核**（排查静默 401 造成的漏检）。

**F7 状态**：能力已建成（`provider_gen` + 冻结风格 + 15 张概念插图全部上屏）、渲染
`SUCCEEDED`（残留卡景 0、满覆盖），但**家族份额门未达标**（G 72.2% ≫ 33%）+
cap 4 / gap 2 / 家族相邻 17 ⇒ **不作为交付候选接受**（fail-closed）。
**交付候选保持 F / F2 / F3 / F4 / F5 / F6**；零 promotion、零发布。

**下一轮**：① 生成素材 `name` 改**语言中立**（不含旁白原文）；② 重跑求解；
③ 全门 → 登记第七部候选 F7；④ 补记 **F6 家族报告 erratum**
（D2：12 张 `asset_id=None` 的历史素材曾**绕过家族约束** ⇒ F5/F6 的家族份额只统计了
有 id 的那部分）。

## Phase 47 — 文生图能力（gen provider）+ 抽象段视觉重做；F7 **fail-closed**（2026-10-02）

## Phase 46 — **具名绑定×锚定交互修复** + **双轨家族门** + **F6 终渲**；登记第六部候选 F6（2026-10-02）

**P46-1 根因修复（两条，均为真实缺陷）**
- **① Pexels 条目不携带 `name` / `relative_path`**：
  `_build_material_timeline` 的匹配打分（`agent.py` L265-266）**硬取 `a["name"]`**
  （非 `.get`）⇒ `KeyError: 'name'`；且 `relative_path` 缺失使资产定位退回
  **被截断的 `path`**（实测 `.../f0cd2a28016d82a17daa9cbce6`，**无扩展名**）
  ⇒ 渲染期素材取不到 ⇒ `corr_best` 坍塌到 0.063 ⇒ **`ASSET_INSUFFICIENT` 阻断渲染**。
  **修复**：合并池为 14 张 Pexels 条目补齐 `name` / `relative_path` / `origin` / `media_type`。
- **② 具名绑定被锚定守卫拒绝** ⇒ 回退到未渲染素材（`P02_2`）。
  **修复（授权书 §1 语义：具名绑定 > 锚定守卫 > 回退）**：具名绑定景
  **豁免锚定守卫**（`_bound_scenes`），**渲染后核验照常**（corr/仲裁不过照样报）。
  非具名景维持锚定约束。
- **⇒ 阻断景 2 → 0**（`P02_2` 由 ② 修好、`P08_3` 由 ① 修好）。
- **技术性排除（分开记账）**：旧素材 `f0cd2a28016d` 因 `frame_pearson_48x48`
  **恒判失败**（`corr_best` 恒 0.063，**跨景恒定**，文件完好 293,234 B）而
  `ASSET_INSUFFICIENT`；记账于 `content_exclusions.json::technical_exclusions`
  （`kind=technical`），**不是内容裁定**，渲染链路根因待修。

**P46-2 双轨家族门**
- `config/family_map.json`：`max_share_by_family` = A **0.33** / E **0.45**（其余仍 0.33）。
- **E 内拆子族**：`E1_黑板粉笔`（10 张）/ `E2_概念科技`（4 张：
  `82d1e3ba`/`bbc8bc56`/`a3506d60`/`313508b6`），**E 内相邻禁同子族**。
- **语境限位**：`82d1e3ba`（画面 1+1=3，错误等式）**仅限「错误/信任失效」语境景**（白名单单列）。
- `core/allocation.satisfy` 新增 `max_share_by_family` / `sub_map` /
  `forbid_adjacent_same_sub`；`_violations` 增 `adjacent_same_sub_family`。
- **求解器 `pass=True`**：cap 0 / 间距 0 / 相邻同素材 0 / 相邻同家族 0 / **子族相邻 0** / 份额 0。

**P46-2 F6 登记**
`projects/p_b9af7fc42237/output/t_cfe72e5a624e_draft_with_outro_v2.mp4`
（**29,547,561 B**，697.534s）；**`render_output` = `a_b6a10af7b180`** + `attribution`；
`logs/p46_2_delivery_candidate.jsonl`（append-only、零 promotion）。
**全门**：时长 697.534s（契约 695.528±1）✔｜**A2 Δ 0.000s** ✔｜满覆盖 ✔｜音轨逐字节一致 ✔｜
**逐景 36/36、0 失败**（仲裁 0 景）✔｜**DQ-2 PASS（唯一素材 16 → 27；max_share 0.0953）** ✔｜
**DQ-3 PASS** ✔｜**DQ-3e PASS（0 处）** ✔｜
**词级同步金门 2/2（median 0.0000s / 覆盖 100% / max |lag| 0.0000s）** ✔｜
**锚定 4/4（真越界 0；具名绑定豁免 1 处单列报告）** ✔｜**内容排除 4/4**（含技术性排除）✔｜
**no_picture 2/2** ✔｜**比喻配额 7/7** ✔｜**分配求解器 7/7** ✔。
三指标按停用口径不通过（冻结 90.0%，阈值未改）。

**轨迹（八版对比择要）**
| 版本 | 池 | cap | 间距 | 相邻 | DQ-3e | 螺壳 | 字幕滞后 | A 家族 |
|---|---|---|---|---|---|---|---|---|
| F | 17 | 4 | 10 | 4 | 4 | 2 | 1.14s | — |
| F5 | 16 | 3 | 0 | 0 | 0 | 0 | 0.000s | 41.7% |
| **F6** | **29** | **3** | **0** | **0** | **0** | **0** | **0.000s** | **30.6%** |

**P46-3 收尾**：材料包 **v5 终版** `logs/phase46_promotion_package.json`；
全量回归 —— **91/91 rc=0，0 失败（1455.1s）** ✔。
- **回归债清理**：`tests/caption_sync_test.py`（**Phase 45 授权书已废止**的恢复点口径）
  在 F6 状态下报 0/3 FAIL。本次将其改为**历史留档 + 委托生效门**
  （仍复算并打印废止口径的实测值供审计：cue 161 条 vs 恢复点 241 个、
  median 0.757→0.797s，并断言 `caption_word_sync_test.py` rc=0），
  **不再作为通过/失败门**。首轮回归 90/91 的唯一失败即此项，现已消除。

**边界**：**LLM $0**、网络累计 5 次（≤20）、渲染 ≤3h；
`config.json` 与 `core/materials.py` **pin 校验 MATCH（未改）**；**未 promotion、未发布**。

## Phase 45 — **Pexels 第二受治源** + **词级重配音（O-voice）** + **锚定修订**；F6 结构全达标但被渲染门阻断（2026-10-02）

## Phase 45 — **Pexels 第二受治源** + **词级重配音（O-voice）** + **锚定修订**；F6 结构全达标但被渲染门阻断（2026-10-02）

**P45-1 Pexels 治理接入（冻结栈零改动）**
- **未改** `core/materials.py`（pin 校验 MATCH）。
- 关键发现：`classify_license("Pexels License")` → **UNKNOWN** ⇒ 直接用声明字段会被
  `license_block_reason` 拦下；但候选消费点（`materials.py` L163-166）
  **优先读候选自带的 `license_class` / `license_cleared`**
  （`klass = candidate.get("license_class") or classify_license(declared)[0]`）
  ⇒ **overlay 携带 provider-verified 值即可放行**，与 Phase 12
  `docs/regression_2x/logs/license_overlay_v1.json` 同款结构。
- 既有可复用实现：`src/video_studio/stage33/pexels_source.py`（**未硬编码 key**）。
- 凭据：`PEXELS_API_KEY` 由用户写入 `.env`（**首轮缺失 ⇒ 曾 fail-closed 报告**）。

**P45-2 定向获取（抽象段视觉语言）**
- **5 / 20 请求、14 / 14 张入池、拒收 0、失败 0**。
- 完整校验链：magic bytes / 大小下限 / **PIL 完整解码（verify + load）** / 尺寸下限 640×360。
- 台账：摄影师署名（courtesy）+ `source_url` + `sha256` + `provider` 全链留痕。
- 新增**家族 E**：`E_黑板粉笔与数学工作场景`（14 张）——与 A『纸面符号』视觉语言不同，
  **真正增加轮换多样性**（分派待监理复核）。

**P45-3 词级重配音（O-voice）**
- 9 段同音色（`zh-CN-XiaoxiaoNeural`）同文本（v6.5）重合成，强制 IPv4；
  **逐段时长偏差 0.00%**（要求 ≤2%）、**文本 sha 守恒**。
- **实盘踩坑**：edge-tts 7.2.8 的 `boundary` 参数**默认 `SentenceBoundary`** ⇒ 只吐句界、
  **不吐词界**，首版 9 段全部「未捕获到 WordBoundary」而 **fail-closed**；
  显式传 `boundary="WordBoundary"` 后捕获 **1,964 词**。
- 新增 `core.captions.build_cues_from_words`：**cue 起点 = 句首词发音时刻**
  （**构造保证滞后 = 0**），不再依赖静音检测；**105 句 cue、文本守恒 OK**。
- **新同步金门** `tests/caption_word_sync_test.py`（阈值运行前写死：
  median ≤0.15s、≥95% 句 |lag| ≤0.35s）：**2/2 PASS**，
  实测 median **0.0000s**、覆盖 **100%**、max |lag| **0.0000s**。

**P45-4 锚定修订 + 全链重跑**
- **锚定越界 = 0**（修掉 Phase 44 的 4 处越界：`P02_3`/`P03_4`/`P05_1`/`P05_3`）。
- **cap 0 / 间距 0 / 相邻同素材 0 / 相邻同家族 0** —— Phase 44 的结构性冲突**已解除**
  （扩池后 22 张未锚定 × cap3 = **66 景位 ≥ 36 景**）。
- **Pexels 14 张全部上屏**；两处禁入（螺壳 `2442c39e` / 举旗照 `432cd85b`）上屏 **0**。
- 家族份额：A 41.7% → **36.1%**，新增 E **38.9%** ⇒ 仍**未达 33%**（待监理裁定阈值口径）。

**⛔ 阻断（fail-closed）**：渲染被 **`ASSET_INSUFFICIENT`** 阻断 —— `P02_2` / `P08_3`
的分配素材**未出现在其镜头窗口内**（`corr_expected 0.199` vs `corr_best 0.063`，
`method=frame_pearson_48x48`）。其中 **`P02_2` 是具名绑定景**（P34 owner-approved 5 景之一）
⇒ **真实缺陷**，门禁正确拦截。按授权书「任一断言不可满足 ⇒ STOP 报告」，
**F6 不作为交付候选接受**，**无最终片**（`with_outro` 未生成）。
交付候选保持 **F / F2 / F3 / F4 / F5**；零 promotion、零发布。
账本：`logs/p45_4_delivery_candidate.jsonl`。

## Phase 44 — **语义锚定分配**（36 景裁决表）+ 字幕句级吸附；**FAIL-CLOSED，未登记候选**（2026-10-02）

## Phase 43 — **字幕句界同步**（cue 吸附语音恢复点）+ **感知家族约束** + **举旗照禁入**；登记第八部候选 F5（2026-10-02）

**P43-1 字幕句界同步（主交付）**
- `core.captions.build_cues` 新增 `recoveries=` / `snap_tol_s=` / `snap_stats=`：
  cue **切换点**在 **±0.4s** 内**吸附到语音恢复点**（`silencedetect(noise=-35dB, d=0.28)`
  的 `silence_end`）；**超界保留原位并计数**（`snap_stats`）。
- 恢复点由 `docs/regression_2x/p44_2_recoveries.py` 预生成（**36 景 / 259 恢复点**），
  渲染时放入项目媒体目录供 `editing` agent 读取。
- **根因**：原实现按**字数**在窗口内**均匀铺排**（`gap=(window-total)/n`），
  真实句界**不均匀** ⇒ 语音恢复点上 cue 中位滞后 1.14s、>1s 者 66 处、77 条提前出现。
- **修复效果（实测）**：median 滞后 **1.14s → 0.000s**；>1s **66 → 0 处**；
  停顿中提前出现 **77 → 0**；吸附 61 / 超界 64。
- **独立验证（关键）**：**实际烧录的 ASS**（`_captions_t_c07b7af1b558.ass`，161 条 cue）
  对恢复点 **median 滞后 0.003s** ⇒ 修复**确已入片**，不只是测试口径。
- **新硬门 `tests/caption_sync_test.py`（3/3 PASS）**，阈值**运行前写死**：
  median ≤0.3s、>1s 占比 ≤10%、提前 ≥0.3s = 0。

**实盘踩坑（如实登记，教训）**
改 `build_cues` 时我一度**按段重置**内部游标 ⇒ 破坏「段间累积 gap」的既有行为
⇒ 一次性打挂 `captions_test` 的 **C3a/C3c/C8**（21 → 18）。查明原实现为**双规则**：
① **新段在游标落后时复位到窗口起点**（否则字幕在切镜后出现空白）；
② **但绝不早于上一条 cue 的结束**（否则跨段时间倒流）。
按此修复 ⇒ **captions_test 21/21 回到全绿**。
**M3 口径修正**（非放宽）：授权书原文是「停顿中提前出现的 **cue 切换**」——
**景首条 cue 是切镜点锚定**（吸附会让切镜处出现空隙）⇒ 不计入；实测被计提前的
**11 条全部是景首条**，提前量仅 0.31–0.35s（源于 `silencedetect` 把切镜静音尾算入恢复点）。

**P43-2 感知家族约束**
- 新增外部开关 **`config/family_map.json`**（家族 A 纸面符号 8 张 / B 人物照片 3 /
  C 3D物件 2 / D 图表界面 2；**监理人工标定**，举旗照已按 P43-3 移除）；
  `core.allocation.satisfy` 新增 `fam_map` / `max_family_share`。
- **相邻禁同家族：0 违例（达标 ✔）**
- **同家族份额 ≤33%：未达标** —— 实测 **A_纸面符号 15 景 = 41.7%**。
  按授权书「不可行则如实报告」登记于 `logs/p43_2_family_feasibility.json`：
  **不是纯容量算术**（素材位充裕：其余家族景位上限 39 ≥ 所需 25）；
  `AL.satisfy` 在 **33% / 36% / 40% / 45% / 50% 各档均不可满足** ⇒ 系
  **候选域 + cap=3 + gap=3 的联合紧约束**。**未静默、未硬造**。
  破局建议：扩池（补家族 B/C/D 可用素材）或放宽 `min_scene_gap`。

**P43-3 举旗照禁入**
`asset_432cd85be6f1`（举旗照）按 P42 螺壳先例入 `config/content_exclusions.json`
（理由：**A 审人工点名「hook 画面与主题错位」**，人工目验在案）⇒ **上屏 0 次** ✔
（两处禁入均在**候选层**与**上屏层**为 0）。

**P43-4 F5 登记**：`projects/p_2efe950ee6a9/output/t_c07b7af1b558_draft_with_outro_v2.mp4`
（**30,245,303 B**，697.534s）；**`render_output` = `a_4efdd914c092`** + `attribution`；
`logs/p43_4_delivery_candidate.jsonl`（append-only、零 promotion）。
**全门**：时长 697.534s（契约 695.528±1）✔｜**A2 Δ 0.000s** ✔｜满覆盖 ✔｜
音轨逐字节一致 ✔｜**逐景 36/36、0 失败**（仲裁 2 景）✔｜**DQ-2 PASS** ✔｜**DQ-3 PASS** ✔｜
**DQ-3e PASS（0 处）** ✔｜**字幕同步 3/3** ✔｜**内容排除 4/4** ✔｜**no_picture 2/2** ✔｜
**比喻配额 7/7** ✔｜**分配求解器 7/7** ✔。
**唯一未达标**：家族份额（结构性，如上）。三指标按停用口径不通过（阈值未改）。

**P43-4/5 收尾**：材料包 **v5** `logs/phase43_promotion_package.json`；
全量回归 —— **89/89 rc=0，0 失败（1337.1s）** ✔
（含新增 `caption_sync_test` **3/3**；`captions_test` 在修复跨段游标后回到 **21/21**）。

**边界**：**LLM $0**、VLM ≈$0.0015、**网络 0**、渲染 2 次（第二次 660.2s）；
`config.json` 与 `core/materials.py`（冻结钉定）**未碰**；**未 promotion、未发布**。

## Phase 42 — **螺壳素材内容级排除**（片级禁用，走 decisions 通道）；登记第七部候选 F4（2026-10-02）

**P41 的疏漏（本轮确认并整改）**
P41 的「螺壳段必须换出」只在 **ID 层**兑现（`cfae038f` → `2442c39e`），**画面家族没换**
⇒ 该素材在 F3 中仍**上屏 3 次**：P04_3（有限单群段）、P06_3（Flyspeck 段）、
**P08_2（机器出题段）** —— 监理计 2 次，**实测 3 次**，第 3 处如实登记。

**P42-1 片级内容排除（走既有 decisions 通道）**
- 新增外部开关 **`config/content_exclusions.json`**（与 `render_motion.json` /
  `frame_match.json` **同款模式** ⇒ **`config.json` 零改动**）。
- 登记字段：`asset_id` / `sha256_prefix` / `name` / `picture_family` / `reason` /
  `observed_placements` / `approved_by=human:project-owner` /
  `approval_document=Phase 42 授权书（监理代行内容裁定）` / `authorized_by=supervisor` /
  `registered_format=13-C 双字段转录` / `scope=film_level`。
- 语义 = 被禁素材在本片**全部景的候选域中排除**；**在候选层生效**（不只是"不选"）：
  `_build_material_timeline` 逐景过滤 `candidates` 并记 `content_excluded_candidates`；
  全被排除 ⇒ 该景**空域**（如实登记，**不硬造候选**）。
- 实测：池 **17 → 16**；`2442c39e` 在**候选域**与**上屏**均为 **0**。

**P42-2 F4 全门通过**
时长 **697.534s**（契约 695.528±1）✔｜**A2 Δ 0.000s** ✔｜视频轨**满覆盖** ✔｜
音轨**逐字节一致** ✔｜**逐景 36/36、0 失败**（仲裁 2 景）✔｜
**DQ-2 PASS（0.0876 / 16 唯一）** ✔｜**DQ-3 PASS（0/36 超 25s）** ✔｜
**DQ-3e PASS（0 处）** ✔｜**no_picture 2/2** ✔｜**比喻配额 7/7** ✔｜
**内容排除门 `tests/content_exclusion_test.py` 4/4 PASS（螺壳上屏 0、候选域 0、证据在案、未误杀整池）** ✔｜
**分配求解器 7/7** ✔。三指标按停用口径不通过（`freeze_ratio 73.2%`，阈值未改）。

**登记**：`projects/p_f468518368bc/output/t_e410b35cf9cf_draft_with_outro_v2.mp4`
（**27,799,409 B**，697.534s）；**`render_output` = `a_23bc1d0b6f6f`** + `attribution`；
`logs/p42_2_delivery_candidate.jsonl`（append-only、零 promotion）。

**螺壳处置链（F → F4）**
| 版本 | 螺壳上屏 |
|---|---|
| F | 2 处（P04_3 / P06_3） |
| F2 | 2 处（ID 未变） |
| F3 | **3 处**（换 ID 但**画面家族未换**） |
| **F4** | **0 处**（片级内容排除） |

**轨迹（分配质量）**
| 指标 | F | F2 | F3 | **F4** |
|---|---|---|---|---|
| cap 最大景/素材 | 4 | 3 | 3 | **3** |
| 间距违例 | 10 | 8 | 0 | **0** |
| 相邻违例 | 4 | 3 | 0 | **0** |
| DQ-3e >25s | 4 | 3 | 0 | **0** |
| 螺壳上屏 | 2 | 2 | 3 | **0** |

**P42-3 收尾**：材料包更新（**F/F2/F3/F4 四行并列** + 螺壳处置链 + `trajectory`）
`logs/phase42_promotion_package.json`；全量回归 —— **88/88 rc=0，0 失败（2052.2s）** ✔
（含新增 `content_exclusion_test` **4/4**、`allocation_solver_test` **7/7**、
`dq3e_effective_hold_test` **2/2**）。

**边界**：**LLM $0**、VLM ≈$0.0、**网络 0**、渲染 1 次（762.1s）；
`config.json` 与 `core/materials.py`（冻结钉定）**未碰**；**未 promotion、未发布**。

## Phase 41 — **派生景候选传播**（父候选列表下沉）+ 全局约束分配；**残留清零**，登记第六部候选 F3（2026-10-02）

**P41-1 候选传播（方案 a，替代 P28-1 硬继承）**
- `_build_material_timeline` 派生景：由「**硬继承父景单一素材**」改为
  「**继承父景候选列表**」——父景 `candidates` 本已通过**相关度 + 许可**双门；
  派生景文本 = 父景文本子集 ⇒ 语义可传递；由分配器在全局约束下**选派**。
- **不改检索逻辑、不加网络**；逐项**携带既有许可/完整性状态**（禁止改写这些字段）。
- **fail-closed**：许可未清（`license_cleared=False`）/ `usable=False` / 缺 `path`
  的候选**一律不入围**；若全部不入围 ⇒ 记 `P41-1 fail-closed` 并保持纯色卡。
- **父景无候选** ⇒ **不硬造**，回退其已选素材并登记 **`STRUCTURAL_SINGLETON`**（域=1）。
- 实测：**19 个派生景**经传播获得候选；`STRUCTURAL_SINGLETON` 仅 **4 个**
  （P02_1/P02_2/P02_3/P09_1）；候选域分布 `{0:4, 5:19, 13:1, 17:12}`。

**P40-1 全局求解器在传播后一次通过**
`global_satisfy pass=True`：**cap 违例 0 / 间距违例 0 / 相邻违例 0 / max 3 景每素材**。

**三处残留景对全部换出（含授权书点名必换者）**
| 景对 | 换出前 | 换出后 |
|---|---|---|
| P03_2/P03_3 | 同素材 | `301ff850→51441395` ✔ |
| **P04_2/P04_3（螺壳段，点名必换）** | 同素材 | **`cfae038f→2442c39e`** ✔ |
| P06_3/P06_4 | 同素材 | `2442c39e→33b360a5` ✔ |

⇒ **无需登记 LIMITATION**（两者均已换出且 DQ-3e 达标）。

**P40-2 DQ-3e 门：2/2 PASS** —— 合并后 **36 段全部 ≤25s（0 处违例，最长 25.0s）**；
即 **P40 抽检的 4 处 >25s（45.8/45.5/39.3/26.5s）已全部清零**。

**轨迹（F → F2 → F3）**
| 指标 | F | F2 | **F3** |
|---|---|---|---|
| cap 最大景/素材 | 4 | 3 | **3** |
| 间距违例 | 10 | 8 | **0** |
| 相邻违例 | 4 | 3 | **0** |
| DQ-3e >25s | 4 | 3 | **0** |
| DQ-2 最大 share | 0.1214 | 0.0877 | **0.0826** |

**P41-2 F3 登记**：`projects/p_1cabad28f7ad/output/t_6efe463cee17_draft_with_outro_v2.mp4`
（**29,136,994 B**，697.534s）；**`render_output` = `a_1ffbdcb06a21`** + `attribution`；
`logs/p41_2_delivery_candidate.jsonl`（append-only、零 promotion）。
**全门通过**：时长 697.534s（契约 695.528±1）✔｜**A2 Δ 0.000s** ✔｜满覆盖 ✔｜
音轨逐字节一致 ✔｜**逐景 36/36、0 失败**（仲裁 3 景）✔｜**DQ-2 PASS（0.0826/17）** ✔｜
**DQ-3 PASS（0/36 超 25s）** ✔｜**DQ-3e PASS（0 处）** ✔｜**no_picture 2/2** ✔｜
**比喻配额 7/7** ✔｜**分配求解器 7/7** ✔。
三指标按停用口径不通过（`freeze_ratio 73.0%`，阈值未改）。

**测试修正（如实登记）**
`tests/allocation_solver_test.py::S5` 原以「当前时间轴」为夹具 ⇒ F3 修好后该时间轴
**已无违例**，S5 的 `before` 前提消失而**误报 FAIL**（这正是"测试与实盘耦合"的再一次教训）。
已改为三断言：**S5** 历史缺陷基线在案（读 P40-3 登记记录的 `before` = **1/10/4**）；
**S5b** 求解器可彻底归零；**S5c 回归守卫** 当前时间轴已无违例 ⇒ **7/7 PASS**。

**P41-3 收尾**：材料包 v4 更新（**F / F2 / F3 三行并列** + 三处残留处置对照 + `trajectory`）
`logs/phase41_promotion_package.json`；全量回归 —— **87/87 rc=0，0 失败（2028.5s）** ✔
（含新增 `allocation_solver_test` **7/7**、`dq3e_effective_hold_test` **2/2 PASS**）。
> 对照：上一轮（F2 状态）为 **86/87**，唯一 FAIL 即 DQ-3e 门**正确报告**残留违例；
> 本轮 F3 残留清零 ⇒ 该门转 PASS ⇒ **回归全绿**。

**边界**：**LLM $0**、VLM ≈$0.0007、**网络 0**、渲染 1 次（1645.7s）；
`config.json` 与 `core/materials.py`（冻结钉定）**未碰**；**未 promotion、未发布**。

## Phase 40 — **分配器全局约束修复**（替代单步贪心）+ **DQ-3e 有效静止门**；登记第五部候选 F2（2026-10-02）

**P40-1 分配器修复（全局约束满足）**
- **新增 `src/video_studio/core/allocation.py::satisfy`**：**最小冲突局部搜索**
  （固定 `seed=20261002`），把「相邻禁同 / 同素材间距 ≥3 / 每素材 ≤3」编码为**硬约束代价**；
  **不可行时返回最小违例解 + 违例清单**（不静默违反）。`_build_material_timeline` 在
  纪律启用时调用其后处理，证据存入 `alloc["global_satisfy"]`。
- **根因定位（两处真实缺陷，非参数问题）**：
  1. 原「单步贪心」遇冲突**只试一次**替代，无解即记 `unresolved` 并**保留违反分配**；
  2. **P36 的具名绑定表本身违反约束** —— 按「语义取首选」生成，把 `301ff850be9c`
     同时绑给 **4 个景**（P01_1/P01_2/P01_3/P09_1）⇒ 直接造成 cap 4>3 与相邻违例。
     处置：改为**以实盘时间轴为基准的约束感知指派**（固定景=非绑定景，待绑景参与搜索）。
- **修复效果（F → F2，同一文本同一音频，零改动）**：
  **cap 违例 1→0（max 4→3）**｜间距违例 10→**8**｜相邻违例 4→**3**｜
  **DQ-3e >25s 由 4 处 → 3 处**｜**DQ-2 最大 share 0.1214→0.0877**。
- **`low_discriminative` 追查（如实登记差异）**：全库检索该标记**仅命中 Phase 19 期历史脚本**；
  当前代码与本案池（`phase33_retrieval_payload`）**均无该字段** ⇒ 按**通用复用平方惩罚**
  实现（覆盖同一现象），差异登记于 `logs/p40_allocation.json`。
- **新增单测 `tests/allocation_solver_test.py`（5/5 PASS）**：S1 可行⇒违例全 0；
  S2 不可行⇒最小违例解+清单；S3 确定性；S4 已满足⇒不改动；
  **S5 用 F 实盘缺陷复现（cap/gap/adj = 1/10/4）并修复为 0/0/0**。

**P40-2 DQ-3e 有效静止门（新门）** `tests/dq3e_effective_hold_test.py`
- 定义（**运行前写死**）：**合并相邻同素材后的有效静止段 ≤25s**；逐景 DQ-3 降为**诊断层**。
- **实测精确复现监理抽检**：45.8 / 45.5 / 39.3 / 26.5s，景对一致
  （P01_2/3、P03_2/3、P04_2/3、P06_3/4）⇒ 盲区已被门捕获。
- 与 `no_picture` / `DQ-2` 共同构成交付门的**观感三角**。

**❗残留未归零（如实登记：结构性不可行）**
- **3 处** DQ-3e 违例（**45.8 / 39.3 / 26.5s**）**全部是「父景绑定回退」产生的兄弟景对**
  （P03_2/P03_3、P04_2/P04_3、P06_3/P06_4）；这些景 **`candidates = 0`** ⇒
  **分配器空域、无法改派**。**不是贪心问题、也不是参数问题。**
- 破局需改 `_build_material_timeline` 的**父景回退行为**（派生景应携带候选而非硬继承），
  或扩池（**网络 0，未触发 §1b 获取**）⇒ 已登记，交人工终审裁定。

**P40-3 F2 登记**：`projects/p_41fd3896a307/output/t_8387790499b3_draft_with_outro_v2.mp4`
（**29,847,698 B**，697.534s）；**`render_output` = `a_2452f1608f65`** + `attribution`；
`logs/p40_3_delivery_candidate.jsonl`（append-only、零 promotion）。
全门：时长 697.534s（契约 695.528±1）✔｜**A2 Δ 0.000s** ✔｜满覆盖 ✔｜音轨逐字节一致 ✔｜
**逐景 36/36、0 失败**（仲裁 2 景）✔｜**no_picture 2/2** ✔｜**比喻配额 7/7** ✔｜
**DQ-2 PASS（0.0877/17）** ✔｜**DQ-3 PASS（0/36 超 25s，max 24.996s）** ✔｜
**DQ-3e FAIL（3 处，结构性）**｜三指标按停用口径不通过（`freeze_ratio 72.9%`，阈值未改）。

**P40-4 收尾**：材料包 v4 更新（**F 与 F2 并列** + 分配约束满足报告）
`logs/phase40_promotion_package.json`；全量回归一次 —— **86/87 rc=0**，
**唯一 FAIL = `dq3e_effective_hold_test`**（新门**正确报告**仍未解决的 3 处结构性违例；
**门在工作，非回归破损**）。

**边界**：**LLM $0**、VLM ≈$0.0015、**网络 0**、渲染 1 次（1533.9s）；
`config.json` 与 `core/materials.py`（冻结钉定）**未碰**；**未 promotion、未发布**。

## Phase 36 — **v6 单线重构「凭什么信」**（九拍节表 + 钩子衔接门）+ **段落级 TTS** + **静音吸附切景**（36 景、句中切分 0）；登记第四部交付级候选（2026-10-02）

**文本线（五轮人审：v5 → v5.1 → v5.2 → v6 → v6.3 → v6.4 → v6.5）**
- **P35**：v5 **全文重写**（故事脊柱：Appel&Haken 豪赌 → Tymozko 换地基 → 单群僵局 →
  开普勒 99% → Hales 十六年 → Lean 折进 LTE → AlphaGeometry 反转 → 三代封条）；
  `fact_risks` 由 14 条底账 **+1 条**（段1 事实风险虚拟语气化）⇒ **15 条**；
  与王骁参照 **n-gram(8) 重合 0**（机制继承、**句子零抄**）。
- **P36**：**九拍节表**（`logs/phase36_beatsheet.json`，B1-B9，单一脊柱「凭什么信」）；
  新增 **钩子衔接门**（8 对全部承接、BROKEN=0）；**禁报幕式段首**；Lean/mathlib **折进 LTE 情节**。
- **P37**：**抽象名词链清剿**（四个定点 + 新信号 **k**：抽象名词密度，阈值**运行前写死**）。
- **P38**：监理**逐句处方**（去文青）+ **比喻配额门**；两处**处方自身冲突**（沙漠筛沙跨度只给一半、
  白名单 6 名目 vs 阈值 ≤5）经裁定后落实（配额重定义为「原创物件比喻 ≤5；家常习语不计」）。
- **P39**：**语域对齐**入册 `config/style_target_wangxiao_v1.md` → **v1.1**（机制⑧）；
  「菲尔兹奖得主」头衔给足（守恒并集有据：v4.1 原文）；§0 自检 2 处逐条登记。

**P36-4 配音 + 切景（新工艺）**
- **段落级 TTS**：9 段**整段合成**（`zh-CN-XiaoxiaoNeural`，9/9 成功、0 重试），
  **Σ实测 = 693.528s**（实测踩坑：字符估算口径曾给 647s ⇒ **以实测为权威**）。
- **静音吸附切景**：`silencedetect` → 句末时刻**吸附**真实静音（silence **98** / ratio **6**）
  → 贪心装箱 ⇒ **36 景**、单景最长 **25.00s**、**句中切分 = 0**（构造断言）。
- **新时基 `p36-v65-timebase-v1` = 695.528s**；**文本守恒**：逐景拼接 == v6.5 全文（3,448 字）。

**P36-4 全门**：时长 **697.534s**（契约 695.528 ±1）✔｜**A2 Δ 0.000s** ✔｜视频轨**满覆盖** ✔｜
音轨**逐字节一致** ✔｜**逐景 36/36、0 失败**（VLM 仲裁 3 景）✔｜
**no_picture 门 PASS（卡景 0；纯色帧 0s）** ✔｜**DQ-2 PASS（0.1214 / 17 唯一）** ✔｜
**DQ-3 PASS（0/36 超 25s；max 24.996s）** ✔｜**比喻配额门 7/7** ✔。
**登记**：`projects/p_93f362b26cff/output/t_9a408309d9b2_draft_with_outro_v2.mp4`（**28,199,188 B**）；
`render_output` = **`a_1bcbfd23b77a`** + `attribution`；`logs/p36_4_delivery_candidate.jsonl`（append-only）。

**❗两处如实登记为未达标（缺陷，不隐藏）**
1. **分配纪律未真正执行**：声明 `cap=3` ⇒ **实测 max 4 景/素材**；声明 `min_scene_gap=3` ⇒
   **实测 10 处违例**；`unresolved` **12** 景。根因：17 张池对 36 景同时满足
   「≤3 景/素材 **且** 间距≥3」是**紧约束**，贪心改选 overshoot 且**不回退**。
   **分类为缺陷**：`allocation_discipline_test` 在**独立桩**下通过、在**实盘**下不通过
   （测试与实盘行为不一致）。
2. **三指标按停用口径不通过**（`freeze_ratio 73.3%`）：运动停用的直接后果
   （P34-2 口径变更已登记，**阈值未改**）。

**修正的测试假阳性（如实登记）**
- `tests/no_picture_scan_test.py::N2` 首版断言「声明 == 生效」⇒ 对全声明者报
  「声明 36 / 生效 14」「声明 8 / 生效 5」**假阳性**。实盘里**绑定只在自动选材未命中时被消耗**，
  自动命中则声明项不被消耗**并非缺陷**。改为**正确硬不变量**：
  *任何被声明绑定、且其场景**没有** selected_asset 的景，都必须由该绑定救到*。
- `p41_4` 首版对**全部 36 景**声明绑定 ⇒ 与「只在未命中时介入」的机制不符；
  改为**干跑生产选材找出会落卡的景**（实测 **8 景**）后**只对这些景声明** ⇒ 声明与生效一致。

**P36-5**：材料包 **v4（六版对比）** `logs/phase36_promotion_package.json`；
全量回归 `logs/phase36_suites_summary.json` —— **85/85 rc=0（0 失败，2001.1s）** ✔
（新增 `metaphor_quota_test`、`no_picture_scan_test` 计入）。

**边界**：**LLM $0**（纯机械 + TTS）、VLM ≈$0.0022、渲染 3 次；`config.json` 与
`core/materials.py`（冻结钉定）**未碰**；池 **17 张**（按裁定接受）；**未 promotion、未发布**。
候选交人工**第四次终审**（看 + 听 + 读）。

## Phase 34 — 观感快修包：**无画面清零**（8 卡景具名绑定、纯色帧 18s→0s）+ **运动默认关** + **v4.2 净稿**（元叙述 22 处清零、实体 0 违例）；登记第三部交付级候选（2026-10-01）

**P34-1 无画面清零（先诊断后修）**
诊断 v4.1 成片：**8 个「有旁白 + 纯色卡」景**（S03p1/S05p1/S05p2/S13p1/S16p1/S17p1/S17p2/S21p1，
**≈129s**，全部 `NO_CANDIDATE`）+ 6 段 >3s 近黑窗口（最长 **85s**）+ 纯色帧 **18s**。
**根因**：这些段落是**抽象解说**（"机器能不能验证数学""工作量大头在翻译"），池内**无字面可命名之物**
⇒ 关键词匹配**结构上必然落空**（`match_score` 全 0）⇒ 合法落入纯色卡。
**处置**：新增 **`config.editing.explicit_bindings`**（**内存注入**，`config.json` 不落盘）——
`_build_material_timeline` 在自动选材**未命中**时按**具名绑定**取值，**绕过匹配分阈值**
（语义相关性由**人工判定**，不由阈值伪造），并在 `fallback_reason`/`selection_reason` 留痕
（含 `approval_document` = 授权书）；**命中时不动**（不覆盖既有语义）。8 景各绑定语义相配素材。
**结果**：**残留卡景 0**、**纯色帧 18s → 0s** ✔、最长连续近黑 **85s → 19s**。
**新门** `tests/no_picture_scan_test.py`（**2/2**）：N1「有旁白 + 纯色卡 = 0」**构造硬门**、
N2 具名绑定声明=生效（8/8）、N3 像素辅助。
**残留 3 段 18–19s 近黑窗口**（[53,71)/[482,501)/[533,551)）实测 **std≈54.4 / uniq=256**
⇒ **有完整图像内容**，判为**内容性暗场**留证复验（非「无画面」）。

**P34-2 运动默认关**
`config/render_motion.json` → **`enabled=false`**（附裁定理由：慢速推拉 × 细节类静态图观感不可接受；
动感由**切镜**承担，40 景 / 630s ≈ 15.7s/景）。**能力保留**：`core/motion.py` 与
`tests/motion_quality_test.py`（8/8）**未动**，未来仅对**摄影类素材**经**人工样片批准**后启用。
**口径变更登记**：运动停用后 `freeze_ratio` 度量的是**切镜密度**而非运动幅度 ⇒
本片实测 **68.7% > 50%**，**按现口径不通过**（**阈值未改**，如实登记）。

**P34-3 v4.2 净稿**
硬规则执行：① **元叙述 22 处跨度级清零**（"回查原文/先不给/必须标清楚/这一版不给数字/
说一下是哪几处/我会说清楚/要核原文"及同族）；② 不确定性**自然口语化**
（"我看到的是转述，要核原文" → **"有说法是转述"**）；③ **数字/实体守恒 0 违例**
（首版曾因删除带走 `Lean`/`AlphaGeometry`/`Liquid Tensor Experiment`/`IMO` 而 4 违例 ⇒
改为**保留实体的自然陈述**）；④ **fact_risks**：本谱系**无该字段** ⇒ 按
**「红线在账上不在嘴上」**保留 `claims` 映射与 `content_conclusions_inherited`，
**未新增**叙事性免责；⑤ retention 机械层实体/数字保留 **100%**；⑥ 字数 **3,468 → 3,201（−7.7%）**；
⑦ n-gram：与 v4.1 的 8-gram 重合 **92.8%** —— **同谱系修订、无外部来源** ⇒ 不作抄袭判据（已登记口径）。
**片尾 CTA 保留**（§0②），仅去"先核到"的核查腔。
**LLM $0（未调用，如实登记）**：以**规则 + 全量守恒校验**完成（零幻觉风险）；如要求以 LLM
降低与 v4.1 的文本重合，请单独授权。
**重配音**：逐段 edge-tts（原音色）**40/40 SUCCESS、0 重试**，`Σ实测语音 = 626.760s`
⇒ **新时基 `p34-v42-timebase-v1` = 628.760s**（授权书预期 ~650s，实测更短，已登记）；
**一致性门 6/6 PASS**（cue sha == 脚本 sha、时基 Δ0.0s、全段 status 合法）。

**P34-4 重渲 + 登记（全门）**
H7 片尾卡（in-window overlay，时长不变）+ 终渲染（v4.2 × 窗口 × 池 17 × **运动停用** × 仲裁 ×
绑定回退 × 构造断言 × 分配纪律 × 具名绑定 × bank v2）。
**已过**：时长 **630.800s**（新契约 628.760±1）✔｜**A2 Δ 0.000s** ✔｜视频轨**满覆盖** ✔｜
音轨**逐字节一致** ✔｜**逐景 40/40、0 失败**（仲裁 **3 景**放行）✔｜**no_picture 门 PASS** ✔｜
**DQ-2 PASS（`max_asset_share 0.0881` / `unique_assets 17`）** ✔｜**每素材最大景数 3** ✔｜
**DQ-3 PASS（`share_over 0.0`，**0/40** 超 25s；`max_hold 22.896s`）** ✔｜一致性门 6/6 ✔。
**按现口径不通过**：三指标 `freeze_ratio 68.7%`（运动停用的直接后果；`longest_static 6.0s` ✔、
`opening_changes 38` ✔）。
**登记**：`projects/p_932e24cb9d04/output/t_77b2538135de_draft_with_outro_v2.mp4`（**27,492,109 B**）；
生产链登记 **`render_output` = `a_2403c35e6535`** + `attribution`；
`logs/p34_4_delivery_candidate.jsonl`（**append-only、零 promotion**）。

**P34-5 材料包 v3 + 回归**
`logs/phase34_promotion_package.json`：**五版本对比**（A/P19 21 景、B/P16-C、C/P32 旧音频、
D/P33 v4.1、**E/P34 v4.2 净稿**）+ **三条终审意见处置记录** + **两项口径变更登记**
（近黑指标、运动指标）+ 推荐序与限制清单；`zero_promotion=true`。
全量回归 `logs/phase34_suites_summary.json` —— **84/84 rc=0（0 失败，1564.6s）** ✔
（新增 `no_picture_scan_test` 计入）。其中 **`motion_test::5b-2` 断言与已授权状态变更冲突**：
P34-2 依授权把 `render_motion.json` 置 `enabled=false`，而该断言写死 `enabled is True` ⇒ 误报。
**修正（不放宽）**：改为**读该文件取期望值再比对** ⇒ 既验证"外部链确实生效"，又**不绑定取值**
（启用/停用两态皆可，强度更高）；修后 **23/23 PASS**。

**边界**：LLM **$0**、VLM **≈$0.0044**、网络 **0**、渲染 3 次；
`config.json`（已复原）与 `core/materials.py`（冻结钉定）复核 **MATCH**；
DB schema、PI 阈值与判定语义、corr 阈值（0.30）、motion POLICY 常量、`mm_*`、词表、baseline、
母片、既有候选**均未改**；未做图内元素动画、视频素材接入、句中拆分、promotion、发布。

## Phase 33 — 观感修复包：运动方向平衡 + 池 17（+5 获取）+ **v4.1 首次入片**（逐段 edge-tts，新时基 685.592s）+ 文本一致性门；**DQ-3 42.5% → 2.5%**；登记第二部交付级候选（2026-10-01）

**P33-1 运动质量（三项诊断 + 一项修复 + 新门）**
诊断（v4.1 全 40 景、逐帧纯函数）：① zoom **居中锚定本就成立**（`x0/y0 ≡ (src−w)/2`）；
② 逐帧位置**符号翻转 = 0**（无颤动）；③ **确认真缺陷** —— 19 个 `SLOW_PAN` 景**全部** `(+56,0)`，
即 `direction` 恒为默认 `"RIGHT"`、`build_plan` 从未按景给方向。
**修复**：`build_plan` 按景序号**确定性交替**方向（父景序号偶数 RIGHT / 奇数 LEFT，同父景一致）
⇒ 实测 **LEFT 9 / RIGHT 10**；**幅度上限（3% 画面宽）与整数帧纪律不变**。
① ② **未做无效改动**（诊断证明已成立），并写入新门以防回潮。
**新门** `tests/motion_quality_test.py`（**8/8**）：Q1 无往复振荡（≤2 翻转/景）｜Q2 净漂移 ≤ 宣称幅度｜
Q3 居中锚定｜Q4 方向平衡（差 ≤1）｜Q4b 同向不连续 >2｜Q5 闭式⇔逐帧全等｜Q6 头静止+单调+末帧到位｜
Q7 幅度上限未放宽。

**P33-2 池扩容 + 分配纪律（部分达成，如实）**
受治理获取（仅 Wikimedia、许可门逐张不放宽）：**10 次请求已用满**，`VERIFIED` **5 张**
（`Graph example (Graph theory)`、`A History Of Mathematical Notations Vol I`、
`Obelus discogranulatus 01.JPG`、`Pure-mathematics-formulæ-blackboard.jpg`、
`Natalia Krizhanovskaya writes mathematical formulae`）；另 2 次搜索因 **IPv6 超时**失败、
3 张被许可/尺寸门拒收 ⇒ 池 **12 → 17**，**目标 ≥20 未达成**（差额登记，未绕过上限）。
**分配纪律**：`core/materials.DEFAULT_POLICY` 新增 `max_scenes_per_asset`（默认 `None`）与
`forbid_adjacent_same_asset`（默认 `False`）—— **默认关闭 ⇒ 既有行为逐字不变**；
`_build_material_timeline` 在自动选材后施加，两级偏好（严格 → 放宽），无解则记 `unresolved`
并**保留原分配**。**新门** `tests/allocation_discipline_test.py`（**7/7**，被测对象为生产函数）。
实测渲染中**每素材最大景数 6 → 3**。

**P33-3 v4.1 配音入库（本阶段核心）**
`.venv_tts` **未装** edge-tts；GPT-SoVITS runtime 内 **6.1.5 已失效**（微软新增 `Sec-MS-GEC` ⇒ **403**）
⇒ 升级 **edge-tts 7.2.8** 并**强制 IPv4**（本机可解析 AAAA 但无 IPv6 出口）。
**40/40 SUCCESS、0 重试**，`Σ实测语音 = 683.592s`；`voice_output` 契约（逐段状态/字节/时长/文本哈希）
+ 逐段台账；**任一段失败 ⇒ fail-closed**。
**新时基 `p33-v41-timebase-v1` = 685.592s**（`Σ实测 + trailing 2.0`，**逐边界 pause = 0**）；
**旧 978.7±1 契约随 v3/V20 谱系废止**（登记版本与理由）。
**新门** `tests/script_media_consistency_test.py`（**6/6**）：C1 逐段 cue 文本 == narration（空白规整）｜
C2 音频 `text_sha256` == 脚本 `narration_sha256`｜C3 整片文本守恒｜C4 时基一致性（±0.1s）｜
C5 cue 落在声明窗口｜C6 全段 status 合法。
**LIMITATION（如实）**：v4.1 事实核查链**未独立重跑**（#76 口径延续），`claims` 为**命题保持映射**，
发布前需人工终审。

**实测踩坑（5 处，均已修正并登记）**
① v4.1 脚本 `duration_s` 仍是**旧谱系规划值** ⇒ 渲染前闸门**正确 fail-closed**
（PI-1 覆盖 0.7125、PI-2 shortfall 281.97s）⇒ 按授权书 §3 重算新时基；
② `narration_plan` 无 `pause_attribution` 时回落冻结常量 `PAUSE_BUDGET_S=0.75` ⇒ **+16.25s 幻影膨胀**
（#75.2 老病）⇒ voice 产物**必须携带归因表**；
③ 边界 pause 使**音频比时间轴长 11.07s**（尾部静音）⇒ 权威口径定为**段间不留额外静音**；
④ `policy_from_config` 缺 `None` 默认分支 ⇒ 分配纪律配置被**静默丢弃**（已补分支）；
⑤ `list` **无 `__dict__`** ⇒ `scenes.allocation` 赋值抛 `AttributeError` 被 `try/except` 吞掉、
**证据静默丢失**（P28 §0 禁止）⇒ 新增 `MaterialTimeline(list)` 子类承载证据。

**P33-4 终渲染 + 登记（全门通过）**
H7 片尾卡（in-window overlay，**时长不变**，音轨按母版流复制）+ 终渲染
（v4.1 音频 × 新窗口 × 池 17 × 运动质量修复版 × 仲裁 × 绑定回退 × 构造断言 × 分配纪律 × bank v2）。
**已过门**：时长 **687.590s**（新契约 685.592±1）✔｜**构造断言 A2 Δ 0.000s** ✔｜音轨**逐字节一致** ✔｜
**逐景核验 40/40、0 失败**（仲裁 **5 景**放行）✔｜三指标 **13.0% / 5.0s / 81 全过** ✔（阈值不变）｜
**DQ-2 PASS（`max_asset_share 0.1864`、`unique_assets 18`）** ✔｜**每素材最大景数 3** ✔｜
**DQ-3 PASS（`share_over 0.025`、`max_hold 27.216s`、`mean 17.14s`）** —— 由旧口径 **42.5% 改善至 2.5%** ✔。
**登记**：`projects/p_37a4ede06517/output/t_71d2d02bd3cd_draft_with_outro_v2.mp4`（**30,943,397 B**）；
生产链自行登记 **`render_output` = `a_805f101f9a9f`** + `attribution`；
`logs/p33_4_delivery_candidate.jsonl`（**append-only、零 promotion**）。
**遗留（如实）**：**相邻同素材仍有 2 处**未解（该两景候选集内已无"未超限且不与邻居相同"的素材），
代码按设计记 `unresolved` 并保留原分配；归零需继续扩池。

**P33-5 材料包 + 回归**
`logs/phase33_promotion_package.json`（**材料包 v2**：A/P19 21 景、B/P16-C、C/P32 旧音频、
**D/P33 v4.1 首次入片** 四版并列 + **新旧对比** + **四项终审问题处置记录**；`zero_promotion=true`）；
完整回归 `logs/phase33_suites_summary.json` —— **83/83 rc=0（0 失败，1614.0s）** ✔
（新增 3 套件计入：`motion_quality_test` 8/8、`allocation_discipline_test` 7/7、
`script_media_consistency_test` 6/6）。
**两处冻结不变式（实测踩坑，已复原/更新）**：① **`core/materials.py` 逐字节复原** ——
该文件属 `tests/maintenance_fixes_test.py::M8a` 的 **"thresholds" 冻结守卫组**，被 5.x 基线
manifest 逐字节钉定；P33-2 首版在其 `DEFAULT_POLICY` / `policy_from_config` 加键 ⇒ **M8a FAIL**
⇒ 从基线 ZIP **逐字节复原**（sha `253b628c2d0b1348…`，复核 MATCH），并把分配纪律开关改由
**agent 层**从 `config.editing` 透传（保住冻结不变式与 P33-2 能力）。
② **`tests/asset_candidate_test.py::10` 测试契约更新（非业务语义变更）**：该断言把真实素材索引
钉为"8 个视觉候选（6 项目 + 2 H5）"，P33-2 受治理获取 **+5 张**落入项目媒体目录 ⇒ 索引 **13**；
改为**不少于**钉定的 8 个、`visual == len(candidates)`、`decode_failed == 0`（强度不变）。

**边界**：LLM **$0**、VLM **≈$0.010**、网络 **10 次获取请求 + 40 次 TTS 调用**、渲染 **5 次**；
`config.json`（**已复原，本阶段未再碰**）、DB schema、PI 阈值与判定语义、corr **阈值（0.30）**、
motion POLICY 常量（幅度上限未放宽）、`mm_*` 冻结栈、词表、baseline、母片、既有候选**零改动**；
**未改旁白文本**；未做图内元素动画、视频素材接入、句中拆分、promotion、发布。

## Phase 32 — config.json **复原**（sha 7b03424846f1）+ `bank-derived-v2`（192/步进≤170px，修复静默降级）+ H7 片尾卡 + 终渲染：**全门通过、登记交付级候选**（2026-10-01）

**P32-1 config.json 复原 + 开关迁移。** 从冻结基线 ZIP（`5.x-post-final-maintenance-baseline.zip`）
**逐字节复原** `config/config.json` ⇒ sha256 **`7b03424846f15efc…`** 与 manifest 钉定值一致 ✔
（复原前 `a3624a2dc3f56baa…`）。复原前该文件中的 `tools.frame_match.bank_derived=true` 在基线版本里
**并不存在**（P27 新增）⇒ 即漂移来源。`bank_derived` **迁移到外部文件链
`config/frame_match.json`**（同 `render_motion.json` 模式），新增
`core/corr_diagnostics.resolve_config()` / `bank_version_of()`；**默认关闭语义不变**。
**教训入制**：钉定文件只有"改/未改"两态；本阶段**只复原、不追加键**；报告内为 `config.json` 记录 sha256。

**P32-2 `bank-derived-v2`（采纳）。** 探针 **48→192**、尺度扩到 9 档（含 0.9 / **0.72**）、
网格**自适应**保证 **x/y 步进 ≤170px**（全池 12 张实测 130–170px ✔）、**阈值 0.30 不变**；
版本标签 `bank-derived-v2`。**步进断言运行前写死**（`grid_step_px`）。
**发现并修复一处静默降级缺陷**：生产链统一以 `gray48`（48×48）取帧、v2 需 192×192 ⇒ `_corr`
形状不匹配抛 `ValueError`，被**裸 `except` 吞掉**并回退到全图口径（**P28 §0 明令禁止的"静默回落"**）。
修复 ①`bank_score_of` 内置 `_as_res()` 自动规整分辨率；②`_verify_scene_frames` 在 v2 下
**以 192 重新载入画面**（非上采样 48）；③该分支 `except` 改为**记录 `bank_error`**（不再静默）。
**生产实测（40 景）**：含 `corr_bank` **0/40 → 32/40**、`bank_error` **0**、
**S11p2 0.0914→0.3199 ✔**、**S13p2 0.0834→0.3332 ✔**（均过阈）、需 VLM 仲裁景 **12→2**、逐景 `failed` **0**。
**如实限定**：P17 历史手工语料正门 v2 **14/17**、**冻结 v1 亦仅 13/17**
（`S07 frame_50` 0.2766 在 v1/v2/SSIM 三口径下均 <0.30）⇒ **采纳依据为生产实测**，非该手工语料；反门语料
已**去污染**（排除"同素材复用"误判为负例），v1/v2 均有误通过项 ⇒ **不以反门作为采纳理由**、未改口径。

**P32-2 必答澄清：P31 仲裁层"被调用但 VLM 未接线"。** P31 沙箱的 `RENDER_ARBITRATION` 事件为
`{"arbitrated": [], "still_failed": [S11p2, S13p2], "cost_usd": 0.0}` ⇒ 两景走
`SKIPPED_NOT_CONFIGURED`，**未做任何语义判定**。根因：阶段脚本直接 `build_engine`，
**未执行 `run.py` 顶部的 `load_env(.env)`** ⇒ `vlm_judge.available()=False / PROVIDER_NOT_CONFIGURED`；
`.env` 内确含 `VLM_API_KEY`，**加载后 `available=True`**。
⇒ **不存在"VLM 判 absent 而素材在屏"的存在层假阴性**：P27 事后链**曾对 S11p2 判 `present`**，
`S13p2` **从未被 VLM 判定过**。**本阶段已把 `.env` 加载补进渲染脚本**，P32 终渲染 VLM 实际可用
（2 景命中缓存，成本记 0；另一轮记 $0.0084）。

**P32-3 `cap=2` 废除。** 算术不可达：40 景、cap=2 ⇒ 需 **≥20 唯一素材**；现有池 **12**
＋授权上限 **6** ＝ **18 < 20**（12 张全用满也只覆盖 24 景）。代码中**并无** cap 常量
（`asset_reuse_policy="prefer_unused"`）⇒ cap=2 属授权新引入。替代硬门保留
**DQ-2（share ≤0.35 且 unique ≥6）＋ `prefer_unused`**；**6 张获取授权撤回**
（网络用量 P29–P32 全 0）。登记 `logs/p32_3_cap2_abolition.json`。

**P32-4 H7 片尾卡 + 终渲染 + 交付级登记。** 终渲染：
`v4.1 × 40 景 × 运动 1.25（守卫）× 仲裁 × 绑定回退 × pause 真实化 × bank-derived-v2`。
H7 按冻结 `exec_add_outro_card` 语义为**末景窗口内**叠加（drawtext 中文、显式字体 `msyh.ttc`、
缺字体 fail-closed），未触及区段流复制 + **母版整条音轨流复制** ⇒ **总时长不变**（不触发时长例外）。
**⚠️ 踩坑并修正（如实登记）**：首版用 MP4 `-c copy` concat ⇒ **接头时间戳断裂**、
成片**视频轨仅 975.73s**（容器/音频 977.88s）＝末 2.1s 变成"无新帧"补齐区（构造断言 A1 不成立）。
改用 **MPEG-TS** 中间格式后：**容器 977.934s**、**视频轨 977.933s（满覆盖）**、**音轨 streamhash 逐字节一致**。
首版产物**已弃用**，不作候选。
**全门通过**：时长 **977.934s ∈ 978.7±1** ✔｜响度 **−16.1 LUFS / −2.4 dBTP** ✔｜
**逐景核验 40/40（checked 32 + placeholder 8）、`failed=0`** ✔（含 S11p2/S13p2）｜
三指标 **11.9% / 6.0s / 83 全过** ✔（阈值不变）｜构造断言 **A2 Δ0.000s** ✔（A1 满覆盖 ✔）｜
**DQ-2 PASS（0.3341 / 13）** ✔｜DQ-3 **报改善**（42.5%、max 37.201s——**不报 PASS**）。
**登记交付级候选**：以生产链自行登记 **`render_output`（`a_7e1321d4f5cb`）+ `attribution`**
（本项目口径：「未登记 `render_output` ⇒ 非交付物」，见 Phase 19 记录）；
记录 `logs/p32_4_delivery_candidate.jsonl`（**append-only、零 promotion**）。
**候选**：`projects/p_9b64253cb240/output/t_b30f05769dd3_draft_with_outro_v2.mp4`（42,911,958 B）。
**promotion 基线不变**：A（P19 21 景）。

**像素证据补全（闭合 P29/P30 口径疑点）**：末段 **976.0s mean 134.56**、**977.0s mean 117.31（亮）**；
S21p2 窗口内 961.5 / 965–975 均 **uniq=256（有内容）**、963.0 为**素材内平坦区**（`std 0.36 / uniq 4`）
⇒ 与 P31 结论一致：**末段深色＝素材固有暗色＋内容性暗场，非技术性黑板**；
**全片技术性黑板 = 0**（A1/A2 成立）。**KNOWN_ISSUES #80 → `NOT_A_DEFECT`（关闭）**。

**P32-5 材料包 + 回归。** 三版材料包终版 `logs/phase32_promotion_package.json`
（含 **#80 全处置链**、**cap=2 废除记录**、`#78.3`、`edge-tts`、`#76 事实核查 LIMITATION`、
推荐序与限制清单；**`zero_promotion=true`**）；完整回归 `logs/phase32_suites_summary.json`
**80/80 rc=0（0 失败、1532.8s）** ✔。`config.json` 复原后**3 项先存失败全部转绿**：
`metrics_test`（`M5d` config sha，18/18）、`offline_mock_test`（`L7b`/`L2c`，23/23）、
`motion_test`（23/23）。其中 **`motion_test::5b` 属测试自身缺陷**：原断言以**真实仓库根**
调用 `resolve_config` 却期望 `{"enabled": False}`/`default`，而真实根下
`config/render_motion.json` **存在且 enabled=true**（P13-E 授权开启）⇒ 该断言在**任何已完成阶段
都必然失败**（把"环境状态"当成"解析器默认行为"）。**修正（不放宽）**：`5b` 改用**空临时目录**
检验"无外部文件 ⇒ off/default"，并**新增 `5b-2`** 断言"真实根 + 外部开关 ⇒ enabled 且来源为外部文件"
⇒ 结果 **23/23**，且**同时覆盖"有/无外部文件"两侧，断言强度提高**。

**边界**：LLM **$0**、VLM **≤$0.0084**、网络 **0**（VLM 调用除外）、渲染 **2 次 ≈6 min（≤3h）**；
`config.json`（**仅按授权复原至钉定值**）、DB schema、**PI 阈值与判定语义**、**corr 度量阈值（0.30 未动）**、
**motion POLICY 常量**、`mm_*` 冻结栈、词表、baseline、母片、既有候选**零改动**；**未改旁白文本**；
未做图内元素动画、视频素材接入、句中拆分、promotion、发布。

## Phase 31（执行轮）— 构造断言 A1/A2/A3 纳入 tests；§1 改动确认 **no-op**；DQ-2 实测更正为 **PASS(0.3341/13)**；终渲染**逐景门 fail-closed（2 景）**⇒ 未登记交付级候选（2026-10-01）

**P31-1 DONE —— §0(a) 落地（旧「近黑」指标废弃，改构造断言）**
新套件 `tests/no_completion_blackboard_test.py`（**15/15 PASS**）实现运行前写死的三条断言：
**A1** 逐景视频窗口覆盖声明时间窗（素材持住：`-loop 1` + `trim=duration=d`）；
**A2** 视频轨无补齐段（`Σ视频轨 == 声明时基`，容差 0.1s）；
**A3** 像素暗度**仅作 scene-relative 辅助证据**（**不作门禁**）。
**实测 A2：977.884s == 977.884s（Δ 0.000s）✔**。测试含**源码契约断言**（防"延长素材窗口"类改动回潮）
与「无素材景=显式纯色卡 `color=c=0x0b1226`」区分断言（该色**不是**补齐黑板）。
**§1「S21p2 延长素材窗口」= no-op**：`-loop 1` + `trim=duration=d` 已保证素材持住整个窗口 ⇒ **未做无效改动**。

**P31-2 —— DQ-2 实测 PASS，并更正文档旧值；cap=2 不可达（如实）**
按**渲染实际使用的时间轴**复算：`max_asset_share` **0.3638 → 0.3341**、`unique_assets` **11 → 13**、
主导素材 **15 景/353.17s → 14 景/326.75s**，**state = PASS**。旧值溯源为
`logs/phase27_p27_3_verification.json` 的**历史绑定**（含 E1 片尾卡窗口口径）；
**注意** `retrieval_candidates` 的 `_p30_binding` 是**选材前提案**（与渲染实际决策 31/40 不一致），
**不得**用于 DQ-2 结论。
**池内重选已穷举证明对本轮阻断项无效**：两景的期望素材为**全池最高分**（其余 11 张 ≤0.197）。
**cap=2 数学不可达**：40 景需 ≥20 唯一素材；现有 12 + 授权上限 6 = **18**（代码中本无该约束，
`asset_reuse_policy=prefer_unused` 未改）。**受治理获取未执行（网络 0/6）**：根因是
「素材几何 × 冻结子窗口库」，新素材无法把两景推过 0.30 ⇒ 属无收益网络支出，已如实登记。

**P31-3 —— 已渲染（1 次 / 136.1s）但**逐景核验门** fail-closed（2 景）**
沙箱 `p_aafdd21cbb9d`、`t_eb5bd3ef934f_draft.mp4`（**42,209,378 B**）。
**已过门**：时长 **977.880s ∈ 978.7±1 ✔**｜三指标 **11.9% / 6.0s / 82 全过 ✔**｜
**DQ-2 PASS（0.3341 / 13 唯一）✔**｜构造断言 **A1/A2 全成立（Δ0.000s）✔**｜
DQ-3 **报改善**（`share_over 0.425`、`max_hold 37.201s`；A 版 100%/67.374s）。
**阻断**：`ASSET_INSUFFICIENT` —— `S11p2` corr **0.270**、`S13p2` **0.285** < 冻结阈值 **0.30**。
**根因（可复算）**：两景期望素材 `301ff850be9c` **确实在屏且为全池最高分**；
**手工细网格**在其**真实呈现窗口**（素材宽 ≈72%、居中）得 corr **0.688 / 0.728**
⇒ 低分来自**冻结 `bank_score` 子窗口库覆盖不足**（`BANK_SCALES` 受该素材 1404×696 真实宽高比限制：
16:9 窗口最大 0.8 宽 × 0.745 高；`BANK_GRID=5` x 步距 ≈281px ⇒ 取不到 x0≈246）。
属 Phase 17 已登记的**度量伪影**（稀疏线稿 48×48 塌陷 + 运动缩放）残留。
**阈值与 corr 口径零改动**（授权禁改）；建议按 Phase 17 既有建议**提高分辨率重验同一 bank 形式**。

**H7 片尾卡：设计已定、未落地成片（如实）**：按冻结 `ops/execution.py::exec_add_outro_card` 语义为
**末镜窗口内**叠加 ⇒ **总时长不变**（977.880s 仍 ∈ 978.7±1）⇒ **不触发**授权书 §3 的时长例外；
因候选已 fail-closed、追加不改变门禁结论，**未做无收益重渲**。

**P31-4 / P31-5 DONE**：三版本材料包 `logs/phase31_promotion_package.json`（**zero_promotion=true**，
含推荐序与限制清单）；完整回归 `logs/phase31_suites_summary.json` **80 套 → 77/80 rc=0**（1336.4s）。
3 项失败**同一非本阶段根因**：Phase 27 授权的 `tools.frame_match.bank_derived=true` 使
`config/config.json` 与冻结基线 manifest 不一致（`a3624a2dc3f5…` vs `7b03424846f1…`），
并连带 `offline_mock_test L7b/L2c` 与 `motion_test 5b`（环境项）。**本阶段未改动 config**。

**依授权书**：不可解 fail-closed ⇒ **如实 STOP**，**未登记交付级候选**；
promotion 基线仍为 **P19 21 景版** `projects/p_50e10b27b44d/output/t_a4d8c1aafd04_draft.mp4`。

**边界**：LLM **$0**、VLM **$0**、网络 **$0**、渲染 **136.1s（1 次）**；`config.json`、DB schema、
**PI 阈值与判定语义**、**corr 度量与仲裁语义**、**motion POLICY 常量**、`mm_*` 冻结栈、词表、baseline、
母片、既有候选**零改动**；**未改旁白文本**；未做图内元素动画、视频素材接入、句中拆分、promotion、发布。
**KNOWN_ISSUES #80** 追加 §80.10（A1/A2/A3 落地 + DQ-2 更正）与 §80.11（逐景门度量边界）。

## Phase 31 — 末段"深色"核查结论 = **非缺陷**（素材持住、暗度系素材固有）；旧「近黑」指标口径废弃，改为 A1/A2/A3 构造断言（2026-10-01）

**P31-1 核查结论：§0(b) 的前提不成立，末段无需修复。**
**构造侧（代码事实）**：`agents/editing/agent.py` L1565–1577 —— 每个有素材的景，其视频输入为
`-loop 1 -framerate 1 -t {ceil(d)+2.0} -i <asset>`，随后滤镜
`scale,crop,setsar=1,fps={fps},trim=duration={d:.3f},setpts=PTS-STARTPTS`
⇒ **素材以 `-loop` 循环输入、输入时长（`ceil(d)+2`）≥ 窗口时长 `d`、随后精确裁到 `d`**
⇒ **设计上素材必然持住整个窗口**；**"窗口 > 视频内容"的景在当前实现里不会出现**
⇒ 授权书 §0(b) 要求的"延长素材窗口覆盖全时间窗"**不改变任何像素**，故**未施加该改动**。

**像素侧（判据 = std/uniq，而非平均亮度）**：S21p2 窗口内逐秒抽帧 ——
`t=963.0s` mean 17.85 / **std 0.36 / uniq 4**（**纯色，属素材内平坦区，非补齐**）；
**`t=965/967/969s` mean 18.79 / `std 14.92` / `uniq 256`**、
**`t=971/973/975s` mean 18.61 / `std 13.37` / `uniq 256`** ⇒ **有完整图像内容，只是整体偏暗**；
`t=977.0s` mean **113.44**（片尾本就有明亮的收束画面）。
该段沿用池内**最暗素材** `Close-packed spheres.jpg`（固有 **mean 42.54**），
经 1.25 推近聚焦暗区后探针 mean≈18 ⇒ **末段深色 = 素材固有暗色，不是技术性黑板**。

**指标口径更正（§0(a) 落地）。** **旧指标「全片无 ≥3s 连续近黑」废弃**：
它把"**内容性暗场**"与"**技术性黑板**"混为一谈（实测 978 抽帧中近黑 **204s**、最长连续 **41s**，
**其中含正常的暗色素材段 S17p1–S18p1**）。**混淆原因（登记）**：以**平均亮度**作唯一判据，
未区分"**低亮度但有内容**"（std/uniq 高）与"**无内容补齐**"（std≈0、uniq≈1）。
**替代构造断言（运行前写死，建议纳入 tests）**：
**A1** 逐景视频窗口覆盖其声明时间窗（素材持住）—— 当前实现**恒成立**；
**A2** 视频轨无补齐段（`Σ视频轨时长 == Σ声明窗口时长`，容差 0.1s）—— 实测 **977.867 vs 977.880** ✔；
**A3** 像素暗度**仅作 scene-relative 辅助证据**（对比**素材固有亮度**，差异 >30% 才报警，**不作门禁**）。

**P31-2 / P31-3 / P31-4 / P31-5：NOT_EXECUTED。** 受治理获取与 `cap=2` 重分配未做
（**网络用量 0/6**）；S11p2/S13p2/S14p1 池内重选未做；**未渲染** ——
§0(b) 的改动经核查**无效且前提不成立**，在裁定"是否仍追加 H7 片尾卡"之前不重渲，
避免产出与既有 P30 成片**逐像素相同**的候选。**既有 P30 成片仍在**
`projects/p_8b48148d4bf3/output/t_9eb07fd396ea_draft.mp4`（44,550,231 B）。
三版材料包与**完整回归**未做（已知最近一次完整跑：**Phase 25 = 81/81 rc=0**）。

**依授权书**：不可解 fail-closed ⇒ **如实 STOP**，**P19 21 景版转正**
（`projects/p_50e10b27b44d/output/t_a4d8c1aafd04_draft.mp4`）。

**待监理裁定（三项）**：① 是否确认 **#80 = `NOT_A_DEFECT`**（若确认，交付线**只剩 DQ-2 一项**）；
② **H7 片尾卡是否仍追加**（不影响黑板；追加会使总时长超 978.7±1s，需按 P30 已授权口径登记显式例外）；
③ 是否授权 **P31-2**（cap=2 + 池补齐 ≤6 张）—— **唯一**能把 DQ-2 从 **0.3638** 拉进 PASS（<0.35）的动作。

**边界**：LLM **$0**、VLM **$0**、网络 **$0**、**未渲染**；`config.json`、DB schema、
**PI 阈值与判定语义**、**corr 度量与仲裁语义**、**motion POLICY 常量**、`mm_*` 冻结栈、词表、
baseline、母片、既有候选**零改动**；**未改旁白文本**；未做图内元素动画、视频素材接入、句中拆分、
promotion、发布。**KNOWN_ISSUES #80 → `NOT_A_DEFECT`**（含 §80.8 核查结论与 §80.9 口径更正）。

## Phase 30 — pause 真实化（选项①）DONE ✔；但黑板未变 ⇒ #80 诊断**再更正**（根因在视频侧、多数深色为素材固有）（2026-10-01）

**P30-1 pause 真实化 DONE（音频侧，按 §0 裁定：非旁白重配）。** 按 pause 归因表插入**真实静音**：
**19 个原始边界 × 0.75s = 14.250s**、**20 个派生边界 × 0**；
**trailing pad 2.0s 亦真实化**（仅拼「段 + 停顿」实测 **975.936s** ＝ 961.634 内容 + 14.250 停顿，
**比声明时基少 2.0s** ⇒ 用 `apad` 把 trailing 也落成音频尾部静音）。
**运行前写死断言：拼接后音频实测 = 977.884 ± 0.1s ⇒ 实测 977.952s 通过 ✔**。
**零 TTS 重合成、零文本改动、零语速调整**；逐段 `sha256` + 拼接规则版本
`p30-pause-materialize-v1:silence-by-attribution-table` + 源音频 `sha256` 入 provenance。
产物 `output/phase30_audio/narration_p30.mp3`。

**⚠️ 但黑板逐点未变 ⇒ #80 诊断在两处被本轮更正（如实登记）。**
用与 Phase 29 **完全相同的时刻**复测（旧版 vs P30 版）：940/946/952/955s 的 mean 与
958/961/964/967/970/973/975s 的 mean（18.63/18.19/18.79/18.79/18.60/18.61/18.61）**完全相同**
⇒ **pause 真实化对黑板区零影响**。
**更正 ①**：**Phase 29 的因果归因不完整** —— 它判「时基比内容长 16.25s ⇒ 视频轨补黑」，
但音频侧补齐后黑板不变 ⇒ **根因在视频侧**（末段素材窗口未覆盖其时间窗），**不是**音频/时基缺口；
Phase 29 的**量化**（时基 977.884 vs 内容 961.634）**仍然正确**，但把它当**根因**是**不完整的**。
**更正 ②**：**多数「深色画面」是素材固有暗色，不是技术性黑板** —— 全片 1 fps 灰度扫描 + 逐景对照：
S16p2 = 246.63（亮）｜**S17p1/S17p2/S18p1 = 18.00/18.87/18.41（暗）**｜
S18p2/S19p1/S19p2/S20/S21p1 = 136.28/136.16/134.03/136.57/136.40（有内容）｜**S21p2 = 18.60**。
**池内素材固有亮度**：`Close-packed spheres.jpg` = **mean 42.54**（全片最暗），经 1.25 推近后
在探针尺度约 **18**，**与 S17p1/S17p2/S18p1 的观测值一致** ⇒ 这三景是**正常的暗色素材内容**
（"密堆球"示意），**不是缺陷**；Phase 28/29 把它们与"纯蓝/黑板"混为一谈是错的。
**真正缺陷收窄为 `S21p2` 的尾部区间**（窗口 `[961.35, 978.63]`，视频内容 ~961.4s 即结束
⇒ **黑板尾长 16–17s，仅此一处**）—— **授权书要求的「H7 片尾卡追加于 S21p2 之后」正是其正解**。

**⚠️ 验收指标口径需裁定。** 授权书要求「全片无 ≥3s 连续近黑（motion_metrics 同源采样法）」；
**实测 978 张抽帧中近黑 204 秒（20.9%）、最长连续近黑 41s** ⇒ 按现口径**不通过**；
但该 41s **包含正常的暗色素材内容**（密堆球示意段 S17p1–S18p1 连续约 41s）
⇒ **该指标把"内容性暗场"与"技术性黑板"混为一谈**，按现口径**不应通过**。
建议改为「**尾部区间**（最后一段窗口）无 ≥3s 补齐黑板」或
「逐景暗度与**素材固有暗度**一致（而非纯黑 mean<5）」。

**P30-2 / P30-4 / P30-5：NOT_EXECUTED。** 受治理获取与 `cap=2` 重分配未做
（**网络用量 0/6**）；S14p1 池内重选未做；三版材料包与**完整回归**未做。
已知最近一次完整跑：**Phase 25 = 81/81 rc=0**。

**P30-3：已渲染、未完成片尾卡。** 沙箱 `p_8b48148d4bf3`、任务 `t_9eb07fd396ea`、**176.9 s**；
成片 `projects/p_8b48148d4bf3/output/t_9eb07fd396ea_draft.mp4`（**44,550,231 B**），
**未登记 `render_output`**（fail-closed）；**运动 40/40、0 fallback**；**H7 片尾卡未追加**。
逐景失败已降至 **2 景**（`S11p2` 0.270 / `S13p2` 0.285，贴近 0.30 阈值，属仲裁可兜底的边缘）。
**已过门**：时长 **977.880 s** ✔｜三指标 **11.9% / 6.0s / 82 次** 全过 ✔（阈值不变）。

**依授权书**：全门过才登记交付级候选；本轮 **fail-closed ⇒ 如实 STOP**，
**P19 21 景版自动转正**（`projects/p_50e10b27b44d/output/t_a4d8c1aafd04_draft.mp4`）。

**边界**：LLM **$0**、VLM **$0**、网络 **$0**、渲染 176.9 s；`config.json`、DB schema、
**PI 阈值与判定语义**、**corr 度量与仲裁语义**、**motion POLICY 常量**、`mm_*` 冻结栈、词表、
baseline、母片、既有候选**零改动**；**未改旁白文本**（逐段 sha256 可证）、**无重合成/变速**；
未做图内元素动画、视频素材接入、句中拆分、promotion、发布。
**KNOWN_ISSUES #80** 登记 §80.6（两处再更正）与 §80.7（pause 真实化完成）。

## Phase 29 — #80 末段深色画面**根因定位**：时基比内容长 16.25s 致视频轨补黑（2026-10-01）

**P29-1 #80 诊断 DONE（根因 = 授权书未列的第 4 类）。** 按授权书排序（诊断先行）执行逐景取证：
抽帧亮度扫描 + 末段窗口对齐 + 旁白归属 + 绑定链核对。

**量化根因**：voice 40 段**内容实测 Σ = 961.634 s**；pause 归因表合计 **14.250 s**（39 个边界）；
trailing pad **2.000 s** ⇒ 声明 `audio_time_base_s` = **977.884 s**；
**内容耗尽点 = 963.634 s** ⇒ **黑板尾长 14.250 s**（+结尾 2 s，合计约 **16.25 s 无内容**）。
机理：40 段 v2.1 时基把「39 个边界 × pause」计入时间轴，而 `narration.mp3` 实际只有 961.634 s
⇒ **时基比内容长 16.25 s ⇒ 视频轨内容用尽后被补黑到音频时基** ⇒ 末段观看为"纯深蓝 / 深色画面"。

**实测印证**：尾段亮度扫描 —— 940–956 s `mean≈136.3`（有内容）｜**958–974 s `mean≈18.6`（近黑）**｜
976 s 回落 136.75。**首个近黑时刻 958.0 s** 落在 **`S21p1`** 声明窗口 `[942.47, 961.35]`；
`S21p2` 窗口中点 969.99 s ⇒ `mean 18.60` —— **与 Phase 28 仲裁层 VLM 读出的
「纯深蓝色画面」（S21p2）与「深色背景加一行字幕」（S18p1）完全吻合**。

**假设裁定（按授权书三条分支逐条给出证据）**：a) **窗口映射越界 不成立**（映射表 40/40 条、
文本守恒 **3468==3468**、`assert_lineage` 通过、末段窗口连续无缝）；
b) **绑定链断裂 不成立**（Phase 28 已修，逐景 `checked` 达 40/40）；
c) **旁白无素材可配 不成立**（末段有绑定；`corr=0.000` 是"近黑画面 vs 素材"的比较结果）；
**d)（新增，成立）时基 > 内容 ⇒ 视频轨补黑**。

**附带查明**：`S21p1` 在 Phase 28「未调用仲裁」的原因 = 其 `corr` 为 `None`
⇒ 仲裁层按 `SKIPPED_MISSING_INPUT` 处理（**不是仲裁逻辑缺陷**，而是该景本身落在近黑区）。
另：`t=976 s` 亮度回落到 136.75 ⇒ **片尾最后 ~1–2 s 存在一段非黑画面**，
与「在 `S21p2` 之后追加 H7 片尾卡」的意图恰好一致。

**修复建议（待裁定）**：① **把 pause 落成真实静音**（**推荐**：重切/重拼旁白音频，**零文本改动**）；
② 让 pause 不进时间轴（需改 `PAUSE_BUDGET_S` 时基语义 ⇒ **超授权**）；
③ 缩短时基到内容长度（**破 978.7±1 时长契约**）；
④ 仅追加片尾卡（**只能覆盖 ~2–4 s，无法覆盖 14.25 s 黑板 ⇒ 不能根治**）。

**P29-2 / P29-3 / P29-4 / P29-5：NOT_EXECUTED（如实说明）。** 授权书排序为诊断先行；
诊断结论**改变了 P29-3 的做法**——若按原计划只追加片尾卡，**14.25 s 黑板依然存在**
⇒ 直接重渲只会得到一个**仍然 fail-closed** 的候选，白耗一次渲染与预算；
且修复选项 ① 涉及**旁白音频重切/重拼**（"旁白重配"范畴），**需先取得授权确认**。
因此本阶段**未执行**：cap=2 与池补齐（网络用量 **0/6**）、终渲染与 H7 片尾卡、
三版材料包、完整回归。**已知最近一次完整跑：Phase 25 = 81/81 rc=0**。

**边界**：LLM **$0**、VLM **$0**、网络 **$0**、未渲染；`config.json`、DB schema、
**PI 阈值与判定语义**、**corr 度量与仲裁语义**、**motion POLICY 常量**、`mm_*` 冻结栈、词表、
baseline、母片、既有候选**零改动**；**未改旁白文本**；未做图内元素动画、视频素材接入、句中拆分、
promotion、发布。**KNOWN_ISSUES #80 → DIAGNOSED**（含根因、假设裁定与四选项）。

## Phase 28 — 绑定回退（#79）修复：核验失败 17→4、DQ-2 0.9369→0.3638；门仍 fail-closed（4 景）致未登记交付级候选（2026-10-01）

**§0 教训入制（流程守卫，本阶段新增）。** **规则：任何"修复类"交付必须在生产路径上加探针测试**；
仅"模块 + 离线脚本验证"**不算落地**。**为什么**：本会话已两次踩坑——Phase 22 的 bank 口径修复
（模块与双门证据都在，但 `_verify_scene_frames` 从未引用 ⇒ Phase 20 在 40 段上 33 处误报）、
Phase 21 的"绑定展开"（只做在**离线复验脚本**里 ⇒ Phase 27 逐景 `checked 2/40`、17 景失败）
——均表现为"**产物在位但未接入生产链**"。**落地**：修复类测试必须**穿过生产调用点**并覆盖
**fail-closed 分支**；修复类报告必须写明"生产路径探针测试"的位置（本次示例：绑定回退测试走
`EditingAgent._build_material_timeline`）。

**P28-1 绑定回退 DONE（根因比授权书判断更深）。** 授权书假设「闸门按派生 id 查不到 ⇒ 按
`parent_scene_id` 回退查绑定」；**实测根因更深**：`_build_material_timeline` **在 L167 丢弃了脚本
自带的 `scene_id`**、改用**序号合成** `scene_id = "S{:02d}".format(i+1)` ⇒ 40 段派生脚本的
`S02p1…` 被替换成 `S01…S40` ⇒ **决策按合成 id 落库、闸门按派生 id 查**，两边 id 空间不一致
（Phase 27 的 `checked 2/40` 即来源：只有 id 形式相同的 `S01`/`S20` 蒙对）。
**修复（最小改动，不动 DB 写入路径）**：① **保留真实 id**
（新增 `script_scene_id`/`parent_scene_id`/`bind_scene_id`；**裁决仍用合成 `scene_id`**
⇒ 既有选材/分类语义**逐字不变**；timeline 行改用 `bind_scene_id` 并附
`scene_id_synthetic`/`parent_scene_id`/`binding_source` 供审计）；
② **父景绑定回退**（**内存表** `parent_asset`，**不写 DB**）：派生段解析不到素材时按
`parent_scene_id` 回退到父景绑定（同一素材、两侧继承），标记 `binding_source="parent_fallback"`
并写 `fallback_reason`；**无父景绑定可回退 ⇒ 保持原状（fail-closed）**；
③ `_bank_derived` 门控语义不变（Phase 26 §0 已双门验证）。

**实测净收益（如实量化）**：逐景 `checked` **2/40 → 40/40**；失败 **17 → 4 景**；
DQ-2 `max_asset_share` **0.9369 → 0.3638**（阈值 0.35，**仅差 +0.0138**）、
`unique_assets` **3 → 11**；三指标 **15.2%/6.0s/69 → 11.9%/6.0s/82**（保持全过且更好）。
附带修正：v2 运动滤镜的 `//`（ffmpeg 不支持）→ `floor(a/b)`；并修正一处**Python 侧误用 `floor()`**
（`//` 在 Python 合法、仅发给 ffmpeg 的字符串里不合法）。

**P28-3 终渲染：已执行，门仍 fail-closed。** 沙箱 `p_ddb17cfbacf8`、任务 `t_5f76c2d95573`、
**177.0 s**；成片 `projects/p_ddb17cfbacf8/output/t_5f76c2d95573_draft.mp4`（**44,535,732 B**），
**未登记 `render_output`**（fail-closed）。**运动 40/40 启用、0 fallback**。
**已过门**：时长 **977.88s**（978.7±1 ✔）｜响度 **−16.1 LUFS / −2.5 dBTP** ✔｜
PI 渲染前/后全 PASS 且 `promote_blocked=False` ✔｜字幕 `SUBTITLE_ALIGNED`
（171 cue、语音内 1.0、越界 0s）✔｜MOTION_VERIFIED ✔｜**三指标 11.9% / 6.0s / 82 次全过** ✔（阈值不变）。
**仍阻断 4 景（真实内容问题，非绑定问题）**：仲裁层 **4 放行 / 4 阻断** ——
放行（VLM 判 `present`）：S04p1 0.277、S10p2 0.299、S11p1 0.250、S11p2 0.286（**边缘属正常**，
bank 口径 + 仲裁兜底按设计工作）；阻断（VLM 判 `absent`）：**S14p1** 0.209（分支图 vs 邮票）、
**S18p1** 0.055「**深色背景加一行字幕**」、**S21p1**（未调用）、**S21p2** 0.000「**纯深蓝色画面**」
⇒ **S21p1/S21p2 为全片末段，疑与 40 段时基下末段窗口/时长边界有关**，**登记 KNOWN_ISSUES #80**。
**DQ-2** `0.3638 > 0.35` ⇒ FAIL（**差 +0.0138**，正是 `cap=2` 要解决的复用集中度）；
**DQ-3** `share 0.45 / max 36.836s` ⇒ 显著改善但未达 ≤20%（报改善、不报 PASS）。

**P28-2 / P28-4 / P28-5：NOT_EXECUTED。** 受治理获取（**网络用量 0/6**）与 `cap=2` 分配未做
（错配排除保持生效）；H7 片尾卡未执行；三版材料包与**完整回归**未执行
（依授权书**预算纪律**：渲染证据与阻塞诊断优先）。已知最近一次完整跑：**Phase 25 = 81/81 rc=0**。
**本阶段相关套件实测**：`motion_metrics_test` **28/28**、`motion_guard_test` **27/27**、
`corr_metric_diagnostics_test` **29/29**、`material_taxonomy_test` **40/40**、
`visual_binding_test` **38/38**、40 景 crop 滤镜 **0 失败**；
`motion_test` **21/22**（唯一失败 `5b` 为**环境项**：`render_motion.json` 在场时
"默认解析 ⇒ off"必然不成立，Phase 13 起即为已知环境依赖）。

**依授权书**：全门过才登记交付级候选；本轮 **fail-closed ⇒ 如实 STOP**，
**P19 21 景版自动转正**（`projects/p_50e10b27b44d/output/t_a4d8c1aafd04_draft.mp4`）。

**边界**：LLM **$0**、VLM **$0.0049**、网络 **$0**、渲染 177.0 s；DB schema、
**PI 阈值与判定语义**、**corr 度量与仲裁语义**、**motion POLICY 常量**、`mm_*` 冻结栈、词表、
baseline、母片、既有候选**均未改**；`config.json` 仅保留 Phase 27 授权的
`tools.frame_match.bank_derived=true`；未做图内元素动画、视频素材接入、句中拆分、改旁白文本、
promotion、发布。**KNOWN_ISSUES #79 → RESOLVED**（含 §0 教训入制）；新增 **#80**（末段画面异常）。

## Phase 27 — 底片组装（v4.1 文本 × 40 景）+ 错配清除 + 交付级渲染：**三指标首次全过**，但派生段绑定未落渲染致门 fail-closed（2026-10-01）

**P27-1 底片组装 DONE。** 40 景 v2.1 时间轴 + P20-1 voice 切片 + **Phase 23 v4.1 定稿稿文本**。
**v4.1（8 段）↔ 40 段窗口映射表**落盘 `logs/phase27_p27_1_mapping.json`：因**分段数不符**（8 vs 21 父景 /
40 子段），按授权要求**按句界/窗口对齐规则映射并登记规则** ——「先把 v4.1 全文按**父景累计时长比例**
切到 21 个父景，再按**子段时长比例**切到 40 子段；切点**吸附在最接近的句/子句边界**；字符区间偏移
⇒ **逐字保留**」。**文本零改动硬校验：3468 → 3468 字符（相等）**；逐段 `text_sha256` 记录；
父景级与子段级**双重守恒**断言通过。产物 `output/phase27_script_sandbox/script_p27_v41_40seg.json`
（40 段 · 978.634s）。**`assert_lineage` 通过**（时基差 0.75s < 1.0）。
**`frame_match.bank_derived = true` 已开启**（`config.json` 的 `tools.frame_match` **追加**该键，
**默认仍为 false**；关闭路径逐字节兼容性已于 Phase 26 §0 证明）。

**P27-2 错配清除 + 池补齐（部分 DONE）。** 错配素材（P24-2 点名的旗帜照）**已在池内排除**
（`EXCLUDE_NAME_HINTS`）；标记素材（`low_crop_safety`/`low_discriminative`）**降权重选 4 处**
（S02/S03/S05/S08，替换后立即计入复用计数以免 DQ-2 恶化）。**未执行**：
**受治理获取 ≤6 张（网络用量 0/6）**、**`cap=2` 新口径分配**。

**P27-3 交付级渲染（成片已产出）。** 沙箱 `p_c7d6b1f4dab2`、任务 `t_649df0e2f014`、**172.9 s**；
成片 `projects/p_c7d6b1f4dab2/output/t_649df0e2f014_draft.mp4`（**43,185,500 B**），
**未登记 `render_output`**（fail-closed，非交付物）；**运动 `{enabled: 40, fallback: 0, scenes: 40}`**。
**✅ 三指标在真实 40 景成片（非探针）上首次全过**：冻结占比 **15.2%**（<50%）、
最长连续静止 **6.0s**（<25s）、开场 90s 变化 **69 次**（≥3）⇒ **Phase 24 提出的观感目标达成**
（对比 P24：73.7% / 9.0s / 5 次）。其余门禁全过：时长 **977.88s**（978.7±1 ✔）、
响度 **−16.1 LUFS / −2.5 dBTP** ✔、PI 渲染前/后全 PASS 且 `promote_blocked=False` ✔、
字幕 `SUBTITLE_ALIGNED`（**171 cue**、语音内 **1.0**、越界 **0 s**）✔。

**⚠️ 阻塞（唯一）：派生段素材绑定未落到渲染。** `bank_derived` 确实生效
（`summary.bank_derived=true`），但**仅 2/40 景有 `expected_asset_id`**（`S01`/`S20`，父景 id）；
其余 **38 个派生段**（`S02p1`…）为 `None` ⇒ 落入"占位镜头"分支 ⇒ **逐景失败 17 景**
（`corr_expected=None`）；**连带 DQ-2 FAIL**（`max_asset_share 0.9369`、`unique_assets 3`，
政策 ≤0.35 / ≥6）。**根因**：`MATERIAL_TIMELINE` 的 decisions **按父景 ID 落库**，
而闸门按**派生 ID** 查绑定 ⇒ 查不到。**这是与 Phase 26 §0「产物在位但未接入」同一模式的第二次出现**
（Phase 21 的"绑定展开"只做在**离线复验脚本**里，未进入渲染链）。
**修复（推荐）**：闸门按 `parent_scene_id` **回退查绑定**（改动最小、不动 DB 写入路径），
或把父景绑定**展开**进 `MATERIAL_TIMELINE`。**DQ-3**：`share 0.45`、`max_hold 36.836s`
⇒ **显著改善但未达 ≤20%**（按口径报改善、不报 PASS）。**仲裁层**：仅 1 景进入 VLM 核验（判 `absent`）
⇒ 未放行；成本 **$0.0007**。

**🔧 顺带修掉一个真 bug（如实登记）。** v2 运动闭式（平移与缩放）原用 `//` 做整数除，
而 **ffmpeg 表达式解析器不支持 `//`**（报 `Undefined constant or missing '(' in '/519)'`）
⇒ 首轮渲染 **19/40 景 crop 配置失败**、**-22 Invalid argument**、成片 **0 B**。
已改为 `floor(a/b)`，重测 **40/40 滤镜全部通过**（`logs/phase27_crop_diag.json`）。
**为何 Phase 24/25 未发现**：那两阶段只渲染**单段探针**（S01 走 zoom 分支，且 24s 场景恰好
未触发平移分支的 `//` 路径）⇒ **只有 40 景全片渲染才暴露**。

**P27-4 / P27-5：NOT_EXECUTED。** 终版 promotion 材料包未生成（候选未成立）；
**完整回归未跑**（依授权书**预算纪律**：渲染证据未完整落盘前不把预算花在回归上；
本轮虽已落盘但门未过，仍如实优先报告）。已知最近一次完整跑：**Phase 25 = 81/81 rc=0**。

**依授权书**：全门过才登记交付级候选；本轮 **fail-closed ⇒ 如实 STOP**，
**P19 21 景版自动转正**（`projects/p_50e10b27b44d/output/t_a4d8c1aafd04_draft.mp4`）。

**边界**：LLM **$0**、VLM **$0.0007**、网络 **$0**、渲染 172.9 s；DB schema、
**PI 阈值与判定语义**、**corr 度量与仲裁语义**、**motion POLICY 常量**、`mm_*` 冻结栈、词表、
baseline、母片、既有候选**均未改**；`config.json` 仅**追加** `tools.frame_match.bank_derived=true`
（P27-1 授权项，**默认仍 false**）；未做图内元素动画、视频素材接入、句中拆分、改旁白文本、
promotion、发布。**KNOWN_ISSUES #79** 登记派生段绑定阻塞、`//` 缺陷与三指标达成。

## Phase 26 — §0 前置核查完成：把 Phase 22 的 bank 核验修复**正式接入编辑链**（双门全过）；P26-1/2/3 未执行（2026-10-01）

**§0 核查发现一处必须补的落地。** Phase 22/18 的 bank 口径修复**产物一直在位**
（`core/corr_diagnostics.py::bank_score`/`present_test`、`tests/corr_metric_diagnostics_test.py`、
`logs/phase18_p18_1_present_fix.json`、`logs/phase21_p21_1_2_build.json`），
但**从未接入编辑链** —— `agents/editing/agent.py::_verify_scene_frames` 仍走「帧 vs 素材**全图**」。
**这正是 Phase 20 在 40 段上产生 33 处误报的直接原因。** 依 §0「未落地 ⇒ 本阶段先完成其双门验证」，
本阶段先做该落地。Phase 23 v4.1 定稿稿核查在位（sha256 `228d3f54…`、`checks_passed=true`、`ai_flavor=0.0`）。

**落地（加法、门控、默认关闭）。** `_verify_scene_frames` 新增 **`bank_derived`** 门控，
读取 `config.tools.frame_match.bank_derived`（**默认 `false`** ⇒ 关闭时行为与既有**逐字节一致**）。
开启时期望素材改用 `corr_diagnostics.bank_score` 的**子窗口 bank 最大 corr**；
对照上限 `corr_best` 取池内**其它**素材的最大全图 corr（**避免自比恒等**）；
池内无可比对象时按"素材在屏即通过"处理。逐景留痕 `row.corr_bank` / `row.bank_window`，
`summary.bank_derived` 标记口径。

**双门验证（修正版）全过。** 正门（帧 vs **实际在屏**素材）**52/52 = 100%**
（bank 分布 min 0.5151 / 中位 0.8804 / max 0.9996）；反门（帧 vs 其它素材）
**0 / 572 误通过**（bank 分布 min 0.0683 / 中位 0.2029 / p95 0.5277 / max 0.5833）⇒ **双门全过**，
口径可接入（受门控、默认关闭）。证据 `logs/phase26_p26_0_bank_dual_gate_v2.json`。

**⚠️ 测试方法学更正（如实登记）。** 首版双门测试用 Phase 20 `fixture.binding` 当期望素材，
得出「正门 42.5%、反门 100/440 误通过」的**失败**结论。复查发现
**Phase 20 渲染时的实际素材 ≠ fixture 记录的绑定**：实测 `_frame_S10p1.png` 与 Postal
全图 corr **0.9304**（该帧**就是** Postal）⇒ 首版把**真正的在屏素材**混进了"无关素材"，**结论无效**。
已按「期望素材 = 该帧的**全图 argmax**（≥0.50 才计入）」重做。首版证据
（`phase26_p26_0_bank_dual_gate.json`）与退化窗口诊断（`phase26_p26_0_bank_degenerate.json`）**留档以备案**。

**⚠️ LIMITATION（KNOWN_ISSUES #78.3）：bank 判别裕度为负。** 在屏素材 bank 最低 **0.5151** <
无关素材 **p95 0.5277**（判别间隔 **−0.0126**）⇒ 两分布**有重叠区**。因判据阈值 0.30 远低于两者分布，
双门仍全过；但**若后续上调阈值、或用于更严的存在性判定，该重叠会先失效**。
建议（未做）：加**最小方差门**（丢弃近常量子窗口）或改用 bank/全图混合判据。

**P26-1 / P26-2 / P26-3：NOT_EXECUTED（如实）。** 底片组装（40 景 v2.1 时间轴 + P20-1 voice 切片 +
**v4.1 ↔ 40 段窗口映射表** + 逐段 sha256 + `assert_lineage`）、错配景重选与池补齐
（**未发起任何网络请求，网络用量 0/6**）、H7 片尾卡与**交付级渲染**、终版 promotion 材料包**均未执行**。
**⟹ 未产出交付级候选**；依授权书「再触发不可解 fail-closed ⇒ 如实 STOP，P19 21 景版自动转正」，
**可用候选为 P19 的 21 景版**（`projects/p_50e10b27b44d/output/t_a4d8c1aafd04_draft.mp4`）。

**回归（如实）。** `corr_metric_diagnostics_test` **29/29**、`motion_guard_test` **27/27**、
`motion_metrics_test` **28/28**、`motion_test` **22/22** 全绿；
**完整 83 套全量回归本阶段未跑完**（我因预算耗尽**主动终止**后台作业，`logs/phase26_suites.log` 为空）
—— **不宣称全绿**；上一轮（Phase 25）完整跑为 **81/81 rc=0**。开关已还原
（`motion: True, arbitration: True`）；`MAX_ZOOM_END=1.25 / V1=1.08 / guard=0.30` 在位。
**IMMUTABLE_OK**（`editing_agent_py` 属授权加法）。

**边界**：LLM **$0**、VLM **$0**、网络 **$0**、**未渲染成片**；`config.json`、DB schema、
**PI 阈值与判定语义**、**corr 度量与仲裁语义**（只改"期望素材的对比口径"，**不改阈值**）、
**motion POLICY 常量**、`mm_*` 冻结栈、词表、baseline、母片、既有候选**均未改**；
未做图内元素动画、视频素材接入、句中拆分、改旁白文本、promotion、发布。
**KNOWN_ISSUES #78** 登记接入修复、双门结果、判别裕度 LIMITATION 与方法学更正。

## Phase 25 — 运动 v2.1（幅度 1.25 + 每景 corr 守卫）：Phase 24 的约束冲突解除，三指标实测全过（2026-10-01）

**Phase 24 阻塞解除。** `core/motion.py` 的 `MAX_ZOOM_END` 由 **1.08 上修到 1.25**（授权 P25-1），
并使 `plan_scene` 的 `zoom_end` 不再硬编码 1.08（新增 `zoom_max` 参数，缺省 1.25）；
保留 **`MAX_ZOOM_END_V1 = 1.08`** 作为**每景 corr 守卫的降级目标**。
总推进由 **142px → 384px**（1920 基准，2.7×），探针尺度每秒可见变化跨过可测阈值。
**实测**（探针短片，320×180 MAD 法、阈值运行前写死）：**冻结占比 73.7% → 0.0%**、
**最长静止 9.0s → 0.0s**、**开场 90s 变化 5 → 23 次**、MAD 中位数 **0.0 → 10.23** ⇒ **三指标全过**。

**P25-1 每景 corr 守卫（硬性，新增 `core/motion_guard.py`）。** 渲染后逐景复核 corr：
`corr < CORR_GUARD_MIN(0.30)` ⇒ **该景幅度自动降回 `MAX_ZOOM_END_V1(1.08)` 重渲**，
并登记 **`MOTION_DOWNGRADED`**（附 from/to 幅度与实测 corr）；仲裁层（`core/render_arbitration.py`）
照旧兜底。`guarded_scenes()` 给出确定性降级集合，`rebuild_plan_with_guard()` 按降级集重算计划
（未降级景**不受影响**，`plan.counts.downgraded` 一致，内嵌 `plan.guard` 摘要）。
**边界**：恰等于 0.30 ⇒ **不降级**；corr **缺失** ⇒ `KEEP_UNKNOWN`（登记但不降级，待复核）。
**守卫只调运动参数**，不改 corr 判定阈值、不改仲裁语义（授权边界）。
40 景演习：启用 **40/40**、降级 **13**、降级景幅度均 ≤1.08 ✔。

**顺带修掉一个 P25 才暴露的 bug。** `build_plan` 原用 `int(str(scene_id).lstrip("S"))` 解析父景序号，
对**派生段 id**（`S02p1`，40 景底片必然出现）抛 `ValueError` ⇒ 新增 `_scene_ordinal()`
（正则取前导数字、异常返回 0）。P24 的单段测试**覆盖不到**该路径。

**tests（三套全绿，共 77 项）**：新增 `tests/motion_guard_test.py` **27/27**
（降级/保持/未知/边界、计划重建、派生段 id 解析、三指标口径写死、确定性）；
`tests/motion_metrics_test.py` 更新为 **28/28**（幅度 384px vs 142px、探针 320×180）；
`tests/motion_test.py` 常量断言更新 **22/22**。

**⚠️ 两处如实更正。** ① **P24 的归因过强**：P24 曾把失败归因于「探针分辨率 + 幅度上限的双重约束」
并写下「分辨率决定成败」；P25 实测 **1.25 幅度下 160×90 / 320×180 / 480×270 三种探针全部通过**
（冻结均 0.0%）⇒ **主因是幅度**（1.08 的 142px 太小），分辨率只是**敏感度系数**，
P24 的该表述**已更正**（`freezedetect` 不可用作内容运动度量这一更正**仍然成立**）。
② **与授权书推导的差异**：授权书写「1.25 幅度 ⇒ 480px 推进」；本实现 `w_end = out_w/zoom_end = 1536`
⇒ 总推进 **384px**（480 对应 `w_end=1440`，即 1.333 倍）。倍数关系一致（×1.25），仅"幅度"基准不同；
**384px 已足够**（三指标全过）⇒ **未改语义**。

**P25-2 / P25-3 / P25-4：NOT_EXECUTED（诚实说明）。** 本阶段预算集中在 **P25-1**——它是授权的前置阻塞
解除项，且其"三指标可达"结论**必须实测**而非推断（P24 的教训：纸面推导与实测不符）。
因此本阶段**未**完成：Phase 22「派生段 bank 核验修复」的落地核查、40 景 v2.1 底片与
**v4.1 ↔ 40 段窗口映射**、**受治理获取**（≤6 张 Wikimedia）、P24-2 错配景重选提案、
H7 片尾卡与**交付级渲染**。**⟹ 未产出交付级候选**；可用候选仍是 **P19 的 21 景版**
（`projects/p_50e10b27b44d/output/t_a4d8c1aafd04_draft.mp4`）。

**边界**：LLM **$0**、VLM **$0**、网络 **$0**、**未渲染成片**（仅探针短片）；
`config.json`、DB schema、**PI 阈值与判定语义**、**corr 度量与仲裁语义**、`mm_*` 冻结栈、词表、
baseline、母片、既有候选**均未改**；未做图内元素动画、视频素材接入、句中拆分、改旁白文本、
promotion、发布。**完整回归 80 套一次跑完、未中途停止**（`logs/phase25_suites.log`）；
**IMMUTABLE_OK**。**KNOWN_ISSUES #77 → RESOLVED**（含上述两处更正）。

## Phase 24 — 运动策略 v2（全镜缓推）+ 冻结占比度量：三指标与授权幅度上限数学冲突，STOP 未产出交付级候选（2026-10-01）

**P24-1 运动策略 v2 DONE（代码 + 度量 + 测试）。** `core/motion.py`：
运动从「景头 ≤`MOTION_WINDOW_MAX_FRAMES`(150) 帧窗口、窗口外静止」改为 **全镜缓推**
（`motion = n_frames − STATIC_HEAD_TAIL_FRAMES`，摊满整景）；启用比例上限 `0.6 → MAX_ENABLED_RATIO_V2 = 1.0`
⇒ 全片 **21/21 景启用**；新增 **`force_hook`**（S01 强制启用，即使被 cap 排在之外）；
**幅度上限 `MAX_ZOOM_END = 1.08` 不变**；`<10s` 仍 prefer-STATIC。步长改为**直接 Q8 进度插值**
（`w(n)=w_end+(motion−c)·Δ/motion`，绕过"单位"量化）⇒ `evaluate_closed_form` / `crop_filter`
与逐帧 `rects` **逐帧一致（0 处不一致）**、唯一宽度值 **143**。

**过程中修掉两个真 bug（如实登记）**：① v1 的 `_stage_frames` 是 50/75/25 的 ≤150 帧窗口分配，
沿用到整景只使用 742 帧 ⇒ **推进在景末前停止**（终点宽 1885 ≠ `w_end` 1778）⇒ 改为三阶段铺满整景并
收敛到恰好 `motion` 帧；② 8% 幅度 = 142px = **71 个单位**（`ZOOM_STEP_PX=2`），摊到 750 帧时
**整数单位步长只能是 0 或 1** ⇒ 要么头 142 帧走完其余静止、要么走不满 ⇒ 改为在**像素精度上按帧插值**。

**新增 `core/motion_metrics.py`（逐秒差分法，授权书口径）**：1fps 抽帧 → 160×90 灰度 → 相邻抽帧 MAD；
`MAD < 0.05` 判该秒冻结；三指标阈值**运行前写死**（冻结占比 <50%、最长连续静止 <25s、开场 90s 内变化 ≥3 次）。
新增 `tests/motion_metrics_test.py`（**26/26 通过**，含合成静止片/运动片的方向性验证、确定性、
以及数学上界的防漂移回归）。
**重要口径更正（如实登记）**：实测 `freezedetect` 在 H.264 CRF20 下对**真实冻结画面也报 0%**
（6 组 noise/scale 配置全部 0.00s，见 `logs/phase24_p24_1_probe.json`）——编码噪声抖动持续超过噪声阈值。
⇒ 它是「**噪声阈值**」度量，而非「**内容运动**」度量；**监理的 94.8% 基线并非由该方法得出**。

**⚠️ 核心结论：三指标与授权幅度上限数学不相容（`logs/phase24_p24_1_motion_v2.json`）**
`zoom ≤1.08` ⇒ 1920px 画布总推进仅 **142px**；探针宽 160px ⇒ 每 1px 探针变化需全分辨率 **12px** 推进；
整景探针上总变化 **≈11.8px** ⇒ 摊满 20s 只有 **0.59 px/秒 << 1px/s**；
要在 20s 内每秒产生 ≥1px（探针）变化需累计放大约 **112%**，远超 1.08 上限。
**实测 20s 探针：冻结占比 73.7% ✘｜最长静止 9.0s ✔｜开场变化 5 次 ✔（MAD 中位数 0.0）。**
⇒ 冻结占比由「每秒可见内容变化」决定，而该变化**上界被幅度上限锁定**：
授权同时要求的「zoom ≤1.08 / pan ≤3%」与「冻结占比 <50%」在**低细节静态图片**素材上**不可兼得**。

**P24-2 / P24-3 / P24-4 / P24-5：NOT_EXECUTED。** 依授权书"完成即 STOP"——四件套共享同一次渲染，
而该渲染的核心验收指标不可达 ⇒ 执行会产生**注定被弃的候选**，以免占用 promotion 评审注意力。
附注：P24-3 的 `per-asset cap = 2 景` 对 21 景需 **≥11 张**素材，当前池 **unique = 10** ⇒ **缺 1 张**；
本阶段**未触发受治理获取**（依授权书，缺口应如实报告）。

**待裁定（阻塞后续四项）**：① 放宽幅度上限（zoom ≤1.25 或允许**整幅平移**动画）；
② 换素材策略（含运动视频素材 / 多图快切）；③ **图内元素动画**（图注/箭头/高亮逐段揭示）；
④ 重定义指标（如按 5s 窗口计冻结；不改变观众实际观感）。**本阶段未自行放宽任何阈值、未改口径。**

**边界**：LLM **$0**、VLM **$0**、网络 **$0**、**未渲染成片**（仅 20s 探针短片）；
`config.json`、DB schema、**PI 阈值**、`mm_*` 冻结栈、词表、baseline、母片**均未改**；
`corr`/仲裁链**零改动**；字幕避让后置**未做**；**零 promotion / 未发布**。
**KNOWN_ISSUES #77** 登记约束冲突、`freezedetect` 口径更正与 `cap=2` 池缺口。

## Phase 23 收尾 — 盲测达标（q1=B/q2=B）⇒ q3 四条处置 + v4.1 定稿（2026-10-01）

**盲测结果**：项目所有者判定 **q1 = B（更像目标机制）、q2 = B（人味更重）** ⇒ 两问均判 v4；
机器信号同向（v4 `ai_flavor` **0.0000** vs v3 **4.5298**）⇒ **达标**。

**q3 清单 4 条逐条处置（纯文本处置，零额外 LLM 调用）**
| # | 用户圈出的问题 | 处置 |
|---|---|---|
| ① | 路线图报幕段 | **删除** seg1 的时间线报幕句与"承诺说清"句；保留反方立场句 |
| ② | 「钉死/交代清楚/标清楚」类元叙述过多 | **保留 2 处**（≤2 上限：seg5「这里有两处得说清楚」、seg4「这句话得说清楚来源」）；seg1/seg2/seg4/seg6 共 **4 处折入正文** |
| ③ | 「不满足这个框架」书面腔 | 改口语「**套不进这个二选一**」 |
| ④ | 「问题有两层」枚举式 | 改口语句式并折入正文（"两件事都躲不开"） |

**处置后复跑（确认无回退）**：六项机械校验**全过** —— 数字保真 ✔、命名实体保真 ✔、
`fact_risks` **13 条不减** ✔、retention 机械分 **1.0** ✔、字数比 **1.0000** ✔、
**n-gram 守卫与参照文本最长公共 0** ✔。信号：**`ai_flavor` 0.0000 保持**（推进词 0.2997→0.2995、
句长 CV 0.5608→0.5590、冒号/破折号/限定语堆叠均维持 0）；字数 3337→3339。

**v4.1 定稿**：`logs/phase23_v4_1_script.json`（sha256 `228d3f541a7d0522dc7073ced42b715420b54cde800e07f8f45e05a2cacc9ba1`）—— **供 Phase 24 渲染使用**。
处置台账：`logs/phase23_q3_disposition.json`（含四条的 user_instruction → action 映射与信号对比）。

**盲区口径**：q3 的 4 条**全部落在信号可覆盖范围**（元叙述／报幕／书面腔／枚举）⇒
**本轮未新增信号盲区实例**；KNOWN_ISSUES **#76** 中"信号盲区"五类（语义空转／伪具体化／
立场虚化／听觉节奏／视角跳变）仍为**待观察**。**#76 状态 `OPEN` → `MITIGATED`**。

**成本**：Phase 23 全程 LLM **$0.01852 / $0.50**（q3 处置 **$0**，未调用 LLM）；VLM $0。

## Phase 23 — 文案风格重写（目标=王骁式说书机制）：信号层 + 2 轮重写，v4 ai_flavor 4.53→0.00，待用户盲测（2026-09-30）

**P23-1 参照处理与机制拆解 DONE。** 通读人工提供的王骁真实口播字幕
（`config/human_style_refs/wangxiao_zhongdong_科威特.txt` 160 行、
`..._埃及.txt` 599 行），产出 **`config/style_target_wangxiao_v1.md`**：
授权书 7 条机制为底，每条配 **规则 / 参照实证例句（机制→例句映射）/ 机理 / 对 v3 的应用**，
外加固规则 8 条 + 机械校验 6 项。**从参照补强 4 项发现**：① 参照文本**零冒号、零破折号**
（v3 有 21 个冒号 + 8 个破折号）；② 开场即**冲突对话引用**；③ 抽象概念在**同段内**给世俗类比；
④ 数据后给**即时反应句**（如「很多人都看愣了」）而不只是翻译。**铁律**：只学机制不抄句子，
例句仅供内部参照、一律不入稿；**文档待所有者确认后正式冻结 sha256**。

**P23-2 AI 味信号层 DONE。** 新增 `src/video_studio/core/ai_flavor.py`（机械、确定性、零 LLM）：
8 项信号（推进词密度／「不是A而是B」频率／设问自答／句长 CV／冒号展开／破折号补充／限定语堆叠／
段落对称性）+ `POLICY` 逐项机理 + 中文数字归一 + 数字保真 + 命名实体保真 + **n-gram 守卫** +
retention 机械层。**一次自我修正（如实登记）**：初版综合分把 8 项简单加权求和，被 `para_symmetry`
的参照基线（**1.0**，因参照是逐行字幕、无空行分段）主导，且"优于参照"也被扣分 ⇒
改为 **「相对参照均值的正向偏离加权和」**（`SCORE_WEIGHTS` / `HIGHER_IS_BETTER`）⇒ **优于参照不扣分**。
**基线**（`logs/phase23_flavor_baseline.json`）：v2 **6.3552**、v3 **4.5298**、参照为基准。
新增 `tests/ai_flavor_test.py`（**29/29 通过**）。

**P23-3 全文重写管线 DONE（真实 LLM 2 轮）。** 输入 v3 稿（8 段/3201 字），
system = style target 机制 + 硬规则 10 条；每轮后 6 项机械校验，**违反即回滚该轮**。
第 1 轮 **ROLLED_BACK**（数字新增 `20`、实体丢失 `这个猜想`，ai_flavor 0.2985）；
**第 2 轮 ACCEPTED（ai_flavor 0.0000）**，六项校验全过：数字保真 ✔、实体保真 ✔、
fact_risks 13 条不减少 ✔、retention 机械分 **0.6→1.0** ✔、字数比 **1.0006** ✔、
**n-gram 守卫与参照文本最长公共 0** ✔。
**v4 开场**：「1977 年，Appel 和 Haken 宣布四色定理被证出来了，数学界那会儿的第一反应不是鼓掌。」
（事实切入 + 态度外露，替换 v3 的「先做一个假设」）；「几十万行」后紧跟**人话翻译**
（「你一行一秒往下读，好几天不睡觉也读不完，人脑扛不住」）。
**三处故障与处置（如实登记）**：① `max_tokens=16384` 被 reasoning 吃满致 content 为空
（`LLM_REASONING_BUDGET_EXHAUSTED`，与 Phase 8 v3 同一现象）⇒ 提高至 **32768**；
② **prompt 瘦身**：参照例句**不入 prompt**（① 体积；② 反而诱导抄参照），改由机械 n-gram 守卫负责防抄；
③ **实体检测器误判**：初版把引号内纯中文描述性引语（如「被读完并被理解」）当命名实体 ⇒
加**专名性判定**（引号内须含拉丁/数字或以机构/定理后缀结尾），并把被丢弃项记入
`quoted_dropped_descriptive` 以便审计。**成本 $0.01852 / $0.50**。

**P23-4 用户盲测验收（待回答，未作达标声明）。** 盲测包 `logs/phase23_blind_pack.json`
（A/B **已打乱**，明文对照封存于 `logs/phase23_blind_answer_key.json`，验收前请勿查看），
参照文本**并列**在包内；含三问（q1 更像目标机制／q2 人味更重／q3 圈出仍有 AI 味的句子）。
**达标线运行前写死**：q1 与 q2 **都判 v4 或持平** + 机器信号同向（v4 4.5298→0.0000，**已满足**）
+ 圈出句子逐条处置。未达标 ⇒ 带清单迭代一轮；仍不达标 ⇒ STOP 并转「人工执笔兜底路线」提案。

**边界**：LLM **$0.01852**、VLM **$0**；`config.json`、DB schema、门禁、`mm_*` 冻结栈、词表、
baseline、渲染素材**均未改**；**未重跑 claim/事实核查链**（v4 内容结论继承 v3 谱系，按继承方法登记
LIMITATION）；**未抄任何创作者口头禅**（n-gram 守卫机械保证 0）。回归 **78/78 rc=0**、**IMMUTABLE_OK**。
**KNOWN_ISSUES #76** 登记盲测待办、信号盲区（语义空转／伪具体化／立场虚化／听觉节奏／视角跳变）与口径限制。

## Phase 21 — 派生段时基与绑定收口：#75.2/#75.3 双修复达成，派生段核验误报 33 处致门仍 fail-closed（2026-09-30）

**P21-1 `time_base_policy=v2.1`（pause 归因策略）DONE。#75.2 修复。** 新增
`core/narration.py::pause_attribution()` / `_pauses()`：**原始段边界**保持 `PAUSE_BUDGET_S=0.75`
（**常量数值与语义零改动**，指纹断言通过），**经静音吸附的派生边界 `pause=0`**
（依据：`silencedetect` 实测停顿**已被切片吸收**，再计即"幻影膨胀"——#75.2 根因）；
`audio_time_base_s()` / `audio_segment_windows()` **消费该表**，逐边界登记 `original|derived` + 依据引用。
**双路径硬验收**：21 段**无表**路径 **978.656s 逐字节兼容**（表为 None 亦然）；
40 段**无表**复现旧膨胀 **992.884s**（证明修复真实生效）；40 段**有表** **977.884s ∈ 978.7±1**（−15.0s）。
**与授权书预期差异（如实登记）**：授权书预期 978.634 系按 **20** 个原始边界；实测 **19** 个
（21 景 → 20 次父景切换，但 40 段序列**以派生段结尾**，末边界不计 pause）⇒ 977.884，Δ−0.75s，仍 ∈ 容差。

**P21-2 素材绑定展开到派生段 DONE。#75.3 修复。** `material_timeline` 展开 **40 条**，
每条带 `parent_scene_id` + 子窗口 + `selected_asset`（**两侧素材继承**）。
**fail-closed**：全部派生段可解析父绑定（**0 失败**）。
**DQ-2 按 `direction.DEFAULT_POLICY`（share ≤0.35 / unique ≥6）复算**：
由 P20 的 **FAIL**（`max_asset_share=0.9369`、`unique_assets=3`）恢复为
**PASS**（`max_asset_share=0.1778`、`unique_assets=10`、最大复用 **8 景**）；
**逐景核验覆盖 2/40 → 40/40**。

**P21-3 渲染 + 全门 + DQ 复算。** 沙箱 `p_96ee06071dde`、任务 `t_1033b541c548`、**131.9 s**；
候选 `projects/p_96ee06071dde/output/t_1033b541c548_draft.mp4`（43,875,812 B），
**未登记 `render_output`**（fail-closed）。**时长 977.88s ✔**｜响度 **−16.1 LUFS / −2.5 dBTP** ✔｜
PI 渲染前全 PASS（PI-1/2/6 + G-TL/G-PAD/G-SUB）｜PI 渲染后全 PASS 且 `promote_blocked=False` ✔｜
字幕 `SUBTITLE_ALIGNED`（216 cue、语音内 1.0、越界 0s）✔｜MOTION_VERIFIED（40 景中 24 景启用、0 fallback）✔｜
**DQ-2 PASS** ✔｜**DQ-3 42.5%**（17/40、max 37.201s；A 版 100%/67.374s）⇒ **显著改善、未达 ≤20%**（按口径报改善）。
**⚠️ 新发现（OPEN）**：**派生段逐景核验误报 33 处** —— 派生段窗口只含父素材**局部裁切**，
核验以 **48×48 与素材全图**比较 ⇒ 子窗口天然低分（KNOWN_ISSUES #74 "中心裁切/局部化呈现"盲区重现）；
门内仲裁层将需 **33 次 VLM**（21 段版仅 4 次）⇒ **门仍 fail-closed，未登记交付级候选**。
**建议修复**：派生段改用 P18-1 `bank_score` 子窗口口径（**零 VLM 成本、确定性、与既有修复同源**）。
**预案执行**：依授权书，**21 景版 `p_50e10b27b44d` 自动转正为 promotion 基线**。
**三版本材料包** `logs/phase21_promotion_package.json`（观看推荐序 **A → C（修核验后）→ B**）。

**登记**：KNOWN_ISSUES **#75.4**（75.2/75.3 RESOLVED、75.1 维持 OPEN、派生段核验误报 OPEN）
与 **#75.5**（P19-2「素材-素材」指标盲区 **LIMITATION**：`301ff850be9c` 该指标仅 0.0574
却对成片帧达 ~0.35 ⇒ 标记有用但不充分）。

**边界**：LLM **$0**、VLM **$0.0007**、网络 **0**、渲染 131.9 s；`config.json`、DB schema、
**PI 阈值与判定语义**、`mm_*` 冻结栈、词表、baseline、母片与既有候选、冻结真值**均未改**；
**未执行句中拆分、未改一字旁白（4927→4927 字符）、未重跑 claim/事实核查链、零 promotion、未发布**。

## Phase 20 — 句界拆分 × 旁白切片同阶段收口：P20-1 完成、P20-2 fail-closed（40 段时基×pause 结构冲突）（2026-09-30）

**§0 裁定范围。** 只执行**句界拆分**（P19-3 第 1 轮 19 条提案，21→40 景，切点全在旁白句边界）；
第 2/3 轮**句中切点**提案登记 **NOT_EXECUTED**（理由：句中切点的段文本无法整句切分 ⇒
字幕对齐风险 > DQ-3 边际收益 38.1% vs 45.0%），入 KNOWN_ISSUES #75 作设计债。目标：DQ-3 **显著改善**，不追 ≤20%。

**P20-1 40 段 voice 产物派生（沙箱、确定性、零重合成）DONE。** 输入既有 21 段 `voice_output`
（`segments_manifest` + `narration.mp3` 实测 961.656s）与第 1 轮句界拆分时间轴；
**纯音频切片**出 40 段，每段文本按句界**逐字继承**（**4927→4927 字符相等**，逐段 `text_sha256` 记录）；
切点在父景窗内用 `silencedetect` 的**实测静音中点吸附**（19/19 切点落在真实停顿上）；
`audio_time_base_s = 978.634s`（Δ−0.022）。**provenance**：`derived_from`（voice 产物 sha256 +
拆镜台账 sha256 + source audio sha256）、切片规则版本 `p20-voice-slice-v1:sentence-boundary+silence-snap`、逐段 sha256。
**fail-closed 实际触发两次并修正（如实登记）**：① 首版每边界给 0.75s pause ⇒ 时基 +14.2s（`TIME_BASE_DRIFT`）⇒
改**pause 总量守恒**（父级 15.0s 摊到 39 边界）后消除；② 末段切片越过音频 EOF（961.656s）⇒ 实测时长不符
（`DURATION_MISMATCH`）⇒ 加 **EOF 夹取**后消除。

**P20-2 交付级渲染已执行（122.6s）但 fail-closed，未产生交付级候选。**
沙箱 `p_2b99e67181ce`、任务 `t_63e1aa25069d`；40 段派生脚本（`script_dcv2_p20_40seg.json`，
总时长 978.634s == voice 时基）+ 40 段 voice 派生产物 + 池素材 10 张（P19-4 的 4 处标记素材降权重选沿用）；
运动 enabled + 仲裁层 enabled。候选 `projects/p_2b99e67181ce/output/t_63e1aa25069d_draft.mp4`（44,465,324 B）。
**⚠️ 关键发现（阻塞 DQ-3 收口，如实报告）**：**40 段结构下时长契约不可能同时成立** ——
`core/narration.py::PAUSE_BUDGET_S = 0.75` 为**冻结常量**，`audio_time_base_s = Σ段实测 + pause×(段数−1) + trailing(2.0)`；
**21 段 = 961.656 + 0.75×20 + 2.0 = 978.656s** ✔，**40 段 = 961.634 + 0.75×39 + 2.0 = 992.884s** ⇒
实测成片 **992.88s**，**超 978.7±1s 达 +14.2s** ✘。要回 978.7s 需 `pause ≈ 0.3852s/边界`，
而那等于**改 PI 时基语义**（超授权）；数学不变量 `内容 = 976.656 − 0.75×(段数−1)` ⇒ 40 段要求旁白内容仅
**946.4s**，实际 **961.634s**（4927 字，不可压缩/不可改写）⇒ **15.2s 无解**。
**⚠️ 第二处缺口**：40 段派生后 `MATERIAL_TIMELINE` decisions **仅覆盖 21 个父景 ID** ⇒ 派生段
`expected_asset_id` 为空、落入"占位镜头"分支 ⇒ **逐景核验 `checked_scenes` 仅 2/40（近乎空转）**；
拆镜到 40 段**必须同步把素材绑定展开到每个派生段 ID**。
**已通过的门（如实并列）**：响度 **−16.1 LUFS / −2.5 dBTP** ✔｜PI 渲染前全 PASS（PI-1/2/6 + G-TL/G-PAD/G-SUB）｜
PI 渲染后全 PASS 且 `promote_blocked=False` ✔｜字幕 `SUBTITLE_ALIGNED`（216 cue、语音内占比 1.0、越界 0s）✔｜
MOTION_VERIFIED（40 景中 **24 景**启用运动、**0 fallback**）✔｜**DQ-2 FAIL**（max_asset_share 0.9369 > 0.35、unique_assets 3 < 6——派生段未绑定素材）✘。
**DQ 复算**：**DQ-3 = 45.0%（18/40）、max_hold 36.836s**（原 100%、67.374s）⇒ **显著改善，但未达 ≤20%**，
按授权口径报"改善幅度"、**不报 PASS**。
**交付级判定**：**未登记交付级候选**（时长契约不通过 + 核验空转）；**21 景版 `p_50e10b27b44d` 仍是目前唯一全门通过的候选**。

**边界**：LLM **$0**、VLM **$0.0007**、网络 **0**、渲染 122.6 s；`config.json`、DB schema、
**PI 阈值与判定语义**、`mm_*` 冻结栈、词表、baseline、母片与既有候选、冻结真值**均未改**；
**未执行句中拆分、未改一字旁白文本、未重跑 claim/事实核查链、零 promotion、未发布**。
设计债入 **KNOWN_ISSUES #75**。

## Phase 19 — 拆镜批执行 + VLM 仲裁生产接线 + 交付级最终渲染：全门通过 + DQ-2 PASS，DQ-3 零改善（2026-09-30）

**P19-1 VLM 仲裁层生产接线（加法、配置门控、默认关闭）。** 新增 `src/video_studio/core/render_arbitration.py`，
接线于 `agents/editing/agent.py` 渲染后逐景核验门处。开关链同 `config/render_motion.json` 模式
（外部文件 `config/render_arbitration.json`，**默认 off**；**`config.json` 零改动**）。
语义：仅当 `corr < 0.30` 时调 `vlm-presence-verify-v1`；`present` ⇒ **PASS_VLM_PRESENT**（放行，附 VLM 证据/
prompt_version/模型名/成本）；`absent`/`uncertain`/调用失败 ⇒ **维持阻断**（fail-closed 语义零改动）。
**硬验收**：门控关闭时 `apply_arbitration` **原样返回入参对象**（实测 `out is verification == True`，
`failed_scenes` 未被触碰）⇒ 核验行为与现状**逐字节一致**。测试覆盖 `uncertain ⇒ 阻断` 与默认关闭一致性。
**生产路径实测**：用生产纯函数 `EditingAgent._verify_scene_frames` 复现核验后跑仲裁 ⇒
**4 个失败景全部核验为 present 并放行**（S06 0.242、S11 0.153、S13 0.006、S18 0.253），成本 **$0.0021**。

**P19-2 素材误导倾向标记。** `discriminative_score` = 该素材在 48×48 灰度下与**池内其它素材**的最大 corr；
**≥0.35 ⇒ `low_discriminative`**（短名单降权、不硬拒）。12 张全量登记，
**标记 2 张**（`23e71bc8a864` ↔ `432cd85be6f1` 互达 **0.4797**），无一张同时命中 `low_crop_safety`。
**口径局限（如实登记）**：本指标是「素材 vs 素材」，**不能**捕获「素材 vs 任意成片帧」的误吸引机制——
Phase 18 的 2 条反门误通过来源 `301ff850be9c` 在本表仅 **0.0574**（却对 S02/S07 成片帧达 ~0.35）⇒
标记**有用但不充分**；覆盖后一现象需另立「素材 vs 历史帧包」吸引度指标（**本阶段未做，登记为后续项**）。

**P19-3 拆镜批执行（DQ-3 未达 ≤20%，如实登记）。** 19 条 P17-4 提案按 **13-C 双字段**转录批准
（`authorized_by=human:project-owner`、`approval_document=Phase 19 授权书`），并**逐条绑定 proposal sha256**
（append-only 台账）。两轮拆分：第 1 轮（≤35s，切点取旁白句边界）景数 21→**40**、超限占比 100%→**45.0%**；
第 2 轮（≤25s）→ 景数 **42**、占比 **38.1%**；第 3 轮**无变化 ⇒ 切点耗尽**。
**未达 ≤20%**，按授权口径**不按固定秒数硬切**（会破坏旁白-画面对齐），如实报改善幅度并登记 LIMITATION。
**文本零改动硬校验通过**：4927→4927 字符、978.656→978.656 s。派生脚本 v2：
`output/phase19_script_sandbox/script_dcv2_split_v2.json`（42 段）。
**⚠️ 关键兼容性发现**：**拆镜后 42 段时基与既有 `voice_output`（21 段）冲突** —— 渲染前闸门报
`voice 产物不完整：缺少合法音频的段落 [21..41]` + `G-SUB FAIL` ⇒ **拆镜执行必须与旁白重配/音频重切同阶段进行**。
这是 P19-4 沿用 21 段时基、以及 **DQ-3 本阶段零改善**的直接原因。

**P19-4 交付级最终渲染（已执行）。** 沙箱 `p_50e10b27b44d`、任务 `t_a4d8c1aafd04`、**115.1 s**；
运动 `enabled=true`（12/21 景、**0 fallback**）+ **仲裁层 `enabled=true`**；
标记素材重选 **4 处**（S02 `a3f0e27204cd`→`301ff850be9c`、S03 `432cd85be6f1`→`33b360a5363c`、
S05 `23e71bc8a864`→`3f0b94a3f2ac`、S08 `5144139591a0`→`65377b888b77`；**每次替换后立即计入复用计数以免 DQ-2 恶化**）。
候选 `projects/p_50e10b27b44d/output/t_a4d8c1aafd04_draft.mp4`（41,263,003 B），
**未登记 `render_output`/`attribution`**（首跑被核验门阻断 ⇒ fail-closed）⇒ **非交付物**。
**全门复验**：时长 **978.66 s**（978.7±1 ✔，Δ−0.04）｜响度 **−16.1 LUFS / −2.5 dBTP** ✔｜
PI 渲染前全 PASS（PI-1/2/6 + G-TL/G-PAD/G-SUB）｜PI 渲染后全 PASS 且 `promote_blocked=False` ✔｜
字幕 `SUBTITLE_ALIGNED`（216 cue、语音内占比 1.0、越界 0 s）✔｜逐景核验+仲裁 **仲裁前失败 4 → 仲裁后失败 0** ✔｜
MOTION_VERIFIED **12/12**、0 fallback ✔。
**DQ 复算**：**DQ-2 PASS**（10 唯一素材；单素材最大复用 **5 景** = `23e71bc8a864`）；
**DQ-3 FAIL 且零改善**（max_hold 67.374 s、21/21 超 25 s）—— 因 §P19-3 的 voice 时基冲突，渲染实际沿用 21 段时基。
**交付级判定**：全门通过 + DQ-2 PASS **均满足**，但 **DQ-3 零改善**（授权书要求"显著改善+如实报告"）
且候选**未登记 render_output** ⇒ **登记为「全门通过的候选」，不登记为"交付级候选 PASS"**；promotion 交人工。

**边界**：LLM **$0**、VLM **$0.0201**（P18-3 $0.0180 + P19-4 仲裁 $0.0021；≤$0.5）、网络 **0**、渲染 115.1 s；
`config.json`、DB schema、**PI 阈值与判定语义**、`mm_*` 冻结栈、词表、baseline、冻结真值、v9/H5 母片与既有候选**均未改**；
**零 promotion**、未发布、**未自动改旁白文本**（字符数与时长效验通过）、未跳过任何人工批准。

## Phase 18 — 度量收口：present_test 修复（4/5）、corr v3 未采纳、VLM 在屏核验层达标并落地为仲裁层（2026-09-30）

**P18-1 `present_test` 口径修复（真 bug）DONE。** 缺陷（P17 实证）：旧版以「画面 vs 素材**全图**」比较，
对**局部化/裁切/放大**呈现结构失效。修复：比较基准改为**多尺度 16:9 子窗口 bank**
（`core/corr_diagnostics.py::bank_score`，尺度 {1.0,0.8,0.6,0.45,0.35}×5×5），池内其它素材同样按 bank 比较；
`bank=False` 保留旧口径以便对照复现。**实测**：S08 rank **4→1**（0.0581→0.7705）、S13 rank **5→1**（0.0062→0.3763）
⇒ 证实"全图口径"确为 bug；**但在屏数 3/5 → 4/5，未达授权书要求的 5/5**：
**S07 由 argmax 退化为 rank 4**（bank 最佳 0.2766 < 误导素材 `301ff850be9c` 0.352）——
多面板素材的子窗口只覆盖局部所致。**未调参补救、未掩盖**；缺口由 P18-2/P18-3 处理。

**P18-2 corr v3：未采纳（双门未全过）。** 阈值 **0.30 不变**；双门运行前写死（正门 5 景 100% PASS、
反门 55 条构造负例 0 误通过）。变体实测：`bank192` 正门 3/5·反门 **0/55**；
**`edge192`（Sobel/FIND_EDGES 边缘口径）正门 5/5 但反门 35/55 ⇒ 稀疏线稿"到处都是边"、口径无区分力，否决**；
最佳 `max(bank48,bank192)` **正门 4/5·反门 2/55**（唯一失分 S07=0.2766；2 条误通过均为 `301ff850be9c`）。
⇒ **未落地 v3、未版本化、未改任何门禁**。
**LIMITATION（如实登记）**：反门语料**仅含构造错配**；旧 S05 鲨鱼照等真实历史错配素材在本仓**不存在**
（全盘检索无该文件，仅存文件名/哈希）⇒ 反门强度受限，**但未以此为由放宽反门**。

**P18-3 VLM 在屏核验层：达标 ⇒ 落地为仲裁层。** 任务边界 = **视觉存在性**（"帧中是否出现该素材的任何部分"，
允许裁切/缩放/局部），**不判**"配不配/合不合适"——与 KNOWN_ISSUES #73（语义相关性判据不同源）**无关**。
新增 `vlm_judge.judge_presence`（prompt `vlm-presence-verify-v1`，两图输入，输出 present/absent/uncertain + 理由；
**沿用 P14-1 文件缓存**，键含模型+两图 sha+prompt_version）。评测集冻结：正例 15（P17 五景×10/50/90% 帧）
+ 负例 10（同帧 vs 池内 bank48 最高分素材，确定性抽样）。**实测：与人工目视一致 25/25 = 100%、
false-present 0、uncertain 0，成本 $0.0180（≤$0.5）**。
**关键能力**：S07（corr 0.2766，确定性失败）VLM 判 **present** 并准确描述「完整抛物线、三点连线、
坐标标注及虚线结构，仅底部叠加字幕」；S08 进一步指出「仅缺失顶点 D 与底部 F 点」。
**仲裁层**（`logs/phase18_p18_3_arbitration.json`）：`corr<0.30` ⇒ VLM 核验 ⇒
**present ⇒ 放行**（附 VLM 证据/prompt_version/模型名）；**absent / uncertain / 调用失败 ⇒ 维持阻断**（fail-closed）。
**五景最终 5/5 放行、0 阻断**（4 景确定性 + S07 经 VLM）。

**P18-4 落地与登记。** 报告均带 `corr_metric` 版本与出处（确定性部分为**候选** `v3`，未采纳；
采纳部分为 **VLM 仲裁层 `vlm-presence-verify-v1`**）。KNOWN_ISSUES 更新三类盲区（稀疏线稿塌陷 /
中心裁切·局部化呈现 / 运动缩放）的处置：**统一由 VLM 仲裁层兜底**，**非**放宽阈值。
`tests/corr_metric_diagnostics_test.py` 扩至 **29/29 通过**（诊断函数 + P18-1 bank 口径 +
双向验证运行器 + P18-3 仲裁逻辑含 uncertain⇒阻断）。

**边界**：LLM **$0**、VLM **$0.0180**、网络 **0**；`config.json`、DB schema、**PI 门禁逻辑与阈值**、
`mm_*` 冻结栈、词表、baseline、执行链、拆镜提案（P17-4 保持只备不改）**均未改**；
**未渲染成片、未执行拆镜、未放宽阈值、未跳过双门**。

## Phase 17 — 渲染后核验度量专项：五景归因（5/5 在屏）、v2 未采纳、裁切安全预筛、19 条拆镜提案（2026-09-30）

**P17-1 五景归因 DONE。** 新增纯函数模块 `src/video_studio/core/corr_diagnostics.py`（裁切/密度/运动/字幕/
区域最优匹配五假设 + `present_test` 同分辨率 argmax 判定）。对象：Phase 16 渲染后核验门失败的
S02/S06/S07/S08/S13。**机器归因**：S02/S06/S07 = `sampling_artifact`/`crop_artifact`（同分辨率 argmax，确认在屏）；
**S08/S13 = `possible_real_mismatch`**（rank 4/12、5/12；依授权书不得裁定为在屏）。
**人工帧包目视**（`output/phase17_attr_pack/<景>/{frame_10,50,90,asset}.png`）显示 S08/S13 画面
即被分配素材的**裁切/放大局部**（S08=欧拉四边形图 Fig.7 裁掉 D/F；S13=Lean UI 右侧被放大）。
**两种口径差异已定位**：`present_test` 以「画面 vs 素材**全图**」比较 ⇒ 对**局部化画面失效**（argmax 偏向其它稀疏线稿）。
低 corr 的三种**度量伪影**：① **稀疏线稿在 48×48 下塌陷**（S07/S08/S13）；
② **16:9 中心裁切**（S02 1200×1560 竖多面板、S08 885×1033）；③ **运动缩放**（画面=素材子窗口）。
归因报告 `logs/phase17_attribution.json`；分布 `{crop_artifact:1, sampling_artifact:2, possible_real_mismatch:2}`。
**未动阈值、未改门禁**。

**P17-2 度量 v2：未采纳。** 候选 `corr_effective = max(corr_res48(全图,画面), max over 尺度{1.0,0.8,0.6,0.45,0.35}×5×5 网格
的 corr_res48(画面, 素材 16:9 子窗口))`，**阈值 0.30 不变**。分离度实测：正集（在屏 5 景）通过 **0/5 → 4/5**；
负集（画面 vs 池内其它素材，55 对）误通过 **0/55 → 2/55**（最大 0.3542，同一稀疏线稿素材）。
**双向门（运行前写死）**：正门需 100% PASS ⇒ 实测 4/5（S07 0.2766<0.30）**不过**；
反门需已知错配 100% FAIL ⇒ 冻结语料**不全**（旧 S05 鲨鱼照等素材在本仓不存在，仅存文件名/哈希）**不过**。
依授权书「任一门不过 ⇒ 不采纳，如实报告」，**未落地 corr_metric=v2、未改任何门禁、阈值仍 0.30**。
证据 `logs/phase17_metric_v2_experiment.json`、`logs/phase17_metric_prototype.json`。
建议下阶段：提高分辨率（如 192）重验同一 bank 形式 / 引入边缘图或结构相似口径 / **补齐反门语料**后再裁定。

**P17-3 裁切安全预筛 DONE。** `crop_safety = corr_48(全图, scale=1920:1080:force_original_aspect_ratio=increase,
crop=1920:1080)` 对全部 12 张池素材计算；**2 张 <0.30 标记 `low_crop_safety`**
（`5144139591a0` 0.0906、`a3f0e27204cd` 0.1397，均 P16-3 获取）⇒ 短名单**降权、不硬拒**（人工仍可选）。
登记 `logs/phase17_crop_safety_registry.json`；Phase 16 两张失真素材已随表留档。

**P17-4 拆长镜提案 DONE（只备不改）。** 按 DQ-3 口径（`max_hold_s=25s`）对 >35s 场景生成
**19 条** 6-B `split_scene` 格式提案（覆盖 S02–S19、S21），拆分点取**旁白句边界**（无边界则均分），
每条附拆分窗口、**两侧素材继承**（DQ-2 复用关系不变）与 DQ-2/DQ-3 预期影响。
登记 `logs/phase17_split_proposals.json`；`execution.executed=false` ⇒ **不执行、不渲染**。

**测试**：新增 `tests/corr_metric_diagnostics_test.py`（覆盖诊断函数性质 + **P17-2 双向验证运行器**）**19/19 通过**。

**边界**：LLM **$0**、VLM **$0**、网络 **0**；`config.json`、DB schema、`mm_*` 冻结栈、词表、baseline、
**PI 门禁逻辑**、执行链**均未改**；**未渲染成片、未执行拆镜、未放宽任何阈值**。

## Phase 16 — 素材池扩充：池 6→12、DQ-2 转 PASS；P16-1 过滤器 FAIL（回退人工短名单）；P16-5 渲染后核验门阻断（2026-09-30）

**P16-1 负例过滤器验证（硬门）：FAIL。** 冻结评测集 `tests/fixtures/p16_negative_filter_eval_v1.json`
（sha256 `fceeae24b6ee9e44…`）= **负例 20**（人工 3 + 已知陷阱 10 + **构造跨景 7**）+ **误杀测试集 24**（真值集全部正例）。
达标线**运行前写死**（捕获率 ≥60%、误杀率 ≤5%、每条 DENY 附理由）。真实 VLM 实测：
**负例捕获 11/20 = 55.00%（FAIL）**、**正例误杀 13/24 = 54.17%（FAIL）**、DENY 全部附理由 ✔、成本 $0.0131。
**关键发现**：误杀 13 条与 P14-2 门禁失配（24 正例中机器判 IRRELEVANT 亦 13 条）**是同一统计量**
⇒ "作负例过滤器"与"≥90% 一致"**互斥**（同一根因 KNOWN_ISSUES #73）。**未调参救援**（误杀 13>允许 1，
后验阈值调整属运行后调参）。**回退路径**：P16-3 预筛 = **人工短名单（provider 元数据）**，过滤器**不接线**。

**P16-2 本地素材登记（零网络/零推断）：DONE。** 只登记 Phase 12 覆盖层**已有许可记录**的素材 ⇒
登记 **2 张**（`Russell_PM_1+1=2.png` PD-US；`S11-D0_…p08_tactic-state-rw.png` CC BY 4.0），
文件入 `projects/p_96efdc03e1aa/media/registered/` 并复核 sha256 一致；**未登记 15 张**（无许可记录，
逐条留原因）。台账 `logs/phase16_local_registry.json`。

**P16-3 受治理获取（P7-5 路径，仅 Wikimedia）：DONE。** 目标 = DQ-2/DQ-3 点名场景 S03/S06/S07；
**8 次网络请求 / 失败 0**；**4 张 VERIFIED**（`ScienceOfMathematicsComte.jpg` PD；`Jensen's Inequality…` CC BY-SA 4.0；
`Euler proof…` CC0；`Comparison of simple power law curves…` CC BY-SA 4.0）；许可门**逐张不放宽**
（候选许可分布 PD 25 / FREE 31，被拒均为 `ASSET_OVERSIZE`(>8MiB) 与 `ASSET_DANGEROUS_FILENAME`）。
**池 6 → 12 张唯一图像**。逐请求留痕 `logs/phase16_acquisition_ledger.json`。

**P16-4 S03 重选：DONE（扩池后选材重解）。** 不硬编码指定，把全部 12 张作为候选池让引擎**确定性重解**：
S03 由 13-E 的稀疏线稿（corr 0.153，13-E 阻断根因）换为 `432cd85be6f1`，**成片 corr 0.569 ⇒ 达标**，
**13-E 线稿盲区消除**。选材多样性 **5 → 12 种**，单素材最大复用 **10 → 5 景**。

**P16-5 交付级重渲染：已执行，渲染后核验门阻断。** 沙箱 `p_32aded38172b` / 任务 `t_8364252d64f1`，
**173 s**；运动 `enabled=true`；派生脚本文本零改动。候选 `t_8364252d64f1_draft.mp4`（39,946,220 B），
**未登记 `render_output`/`attribution`**（fail-closed）⇒ 非交付物。**失败 5 景**：
S02(0.122)/S06(0.242)/S07(0.078)/S08(0.058)/S13(0.006)（`frame_pearson_48x48, min_corr=0.30`）。
**根因（独立复核 + 人工看图）**：1920×1080 模板**中心裁切** vs 全图 —— 2 张**多面板/竖构图**素材
`a3f0e27204cd`(1200×1560)、`5144139591a0`(885×1033) 的 `corr(全图, 裁切画面)` = **0.140 / 0.091**（<0.30）；
**人工看图证实素材确实在屏**（S02 成片帧即被分配素材，仅裁掉中段）。**未调阈值、未改模板**。
S06/S07/S13 另源（其素材裁切安全度 0.72/0.92/0.76）⇒ **未归因，如实登记**。

**DQ 复算（生产度量，同口径对比 13-E）**：唯一素材 **5→12**；**DQ-2 FAIL → PASS**（最大复用 10→5 景）；
**DQ-3 仍 FAIL**（max_hold 67.374s，21/21 景超 25s 上限）且**不可由换素材修复** ⇒ 需拆分长镜（6-B），
**不在本次授权范围**。**未达成"交付级候选" ⇒ 未登记、零 promotion。**

**边界**：LLM **$0**、VLM **$0.0131**（≤$1）、网络**仅 Wikimedia 8 次**且逐请求记账；`config.json`、DB schema、
PI/DQ 阈值与判定逻辑、`mm_*` 冻结栈、词表、baseline、6-B 执行链语义、frozen 真值（只读引用）**均未改**；
**未放宽许可门**、**未用机器 RELEVANT 放行任何绑定**、**未跳过人工短名单**、**未自动 promotion**。

## Phase 14 — VLM 视觉相关性判定：P14-1 **DONE**；P14-2 真实评测门禁 **FAIL（11.11%）⇒ 不集成**（2026-09-30）

**P14-1 provider（DONE）**：新增 `src/video_studio/tools/vlm_judge.py`，按 `PHASE14_REPORT.md` §4 冻结设计落地：
OpenAI 兼容 `chat/completions` + 图像输入；**确定性降采样**（最长边 ≤768px、JPEG q80、`LANCZOS`，参数入 `POLICY` 并注明依据=成本控制）；
`temperature=0`；JSON 输出 + Schema 校验（label 枚举/reason/confidence）；超时 90 s + 重试 2 次 + 指数退避；
`PROVIDER_*` fail-closed（10 个错误码，失败不抛异常、label 置 `NOT_ASSESSABLE`）；**文件缓存**
`output/vlm_judge_cache/<sha256[:32]>.json`（键 = `prompt_version|model|image_sha256|need_text_sha256`，命中即 $0）；
`resolve_config` 三级链（内存 `config.tools.vlm_judge` → `config/vlm_judge.json` → 默认 `{"enabled": false}`），
key **只从环境变量**读；**判定独立性**（单次只看一个 (需求, 候选图) 对，prompt 刻意不含同景其它候选/分数/任何既有结论）。
另新增 `tools/vlm_eval.py`、只读 CLI `run.py vlm-eval`、`config/vlm_judge.example.json`。
**未改 `config.json`、未接线任何生产 agent。**

**P14-2 冻结真值集**：`tests/fixtures/vlm_relevance_truth_v1.json`，**27 对**（RELEVANT 24 / IRRELEVANT 3），
sha256 `6104cfc202113510…`，逐对带 provenance（来源文件 + 定位字段 + **人工原文理由**）与 requirement 快照。
**⚠️ 未达授权要求的 ≥30 对**：全仓仅存在 27 对带显式人工正/负证据的 (镜头, 素材) 对；缺口**运行前登记并保留**，
**未**用机器判定充数。`selection_override` 541 条中约 516 条为鉴权测试，其 `before_asset_id` 混杂后期**许可/镜次身份**
替换且与同对正例标签**自相矛盾**，故**排除**。达标线**运行前写死**：`agreement ≥ 90%` 且
`人工 IRRELEVANT→机器 RELEVANT = 0`；归一规则写死：`PARTIAL`/`NOT_ASSESSABLE`（含失败）**一律计为不一致**。

**P14-2 实测（真实 API）**：`agreement = 3/27 = 11.11%` ⇒ **FAIL**；`人工 IRRELEVANT→机器 RELEVANT = 0` ⇒ 通过；
正例误判 RELEVANT→IRRELEVANT 13；非二值 10。成本 **$0.0202**（上限 $2）。二次运行走缓存 ⇒ **$0 且报告 sha256 逐字节一致**（已实测）。

**P14-3（集成 + 143 对 NA 实测）：未执行** —— 按授权书「严禁在门禁未通过前接线」，**未改任何生产链**、
**未产出** `logs/phase14_na_resolution.json`。

**失配根因（有证据，未调参掩饰）**：`visual_goal` 派生自脚本/分镜的**生成式画面描述**
（如 S01「暗背景，长串无法辨识的证明步骤缓慢滚动」），而人工 operator 的理由是**叙事/主题切题性**
（如 S01「真实 IMO 数学国家队合影，契合『数学与人类』主题」）⇒ **判据不同源**。模型理由逐条精确
（S08 球堆↔开普勒判 RELEVANT；S03「与四色定理相关，但未体现『空椅子与屏幕光』」判 PARTIAL），
属**按字面正确执行**。诊断提示词变体（口径改为「话题同一性」，**明确不参与门禁**）仅把一致率提到 **25.93%**
（`logs/phase14_eval_diag_anchor.json`）⇒ **失配不是提示词措辞造成的**。
**关键不对称（可用于生产设计）**：两个变体下「人工 IRRELEVANT→机器 RELEVANT」**均为 0**、机器仅 1–5 次判 RELEVANT
⇒ 该 VLM 在此设定下是**可靠的拒绝器、不可靠的确认器**。

**成本/边界**：总 API 花费 **$0.0368**（门禁 27 对 $0.0201 + 诊断 27 对 $0.0167 + 连通性探针 $0.0006），上限 $2 ✔；
单价表 `verified=False`（**未按真实账单核对**，成本为估算，不参与任何判定）。**未改** `config.json`、**未写 DB**、
**未接线** agent、**未放宽**任何阈值、**零 promotion**；冻结产物（母片/DCv2/baseline/真值）**零改动**。

## Phase 13-E 最终执行 — ① DCv2 脚本产物合成 **DONE**（纯派生/文本逐字）；② 全片运动候选渲染 **PENDING（未启动）**（2026-09-30）

**① DCv2 脚本产物合成（DONE，授权 ①）**：沙箱新文件 `output/phase13e_script_sandbox/script_dcv2_derived_v1.json`
（sha256 `8ac58983624f6ff9…`；21 段；**总时长 978.656 s** = 权威底片 978.7 s；**零覆盖**）。
- **纯派生**：旁白文本**逐字**沿用 `a_49b58fb3dc01`（sha256 `3d76f4bc798b67f0…`）——**文本逐字校验 True**
  （`text_hash_original == text_hash_derived`，4947 字符，含标点空白均未改）；段时长 = `remapping_21_segments.new_timeline_window_s`；
  音频为事实来源（`new_audio_window_s` + `pause_budget_s`）；`synthesis_rule_version = dcv2-script-derivation-v1:verbatim-text+remapping-windows`。
- **不重跑内容链**：**内容结论继承自 a_49b58fb3dc01 谱系**（未重做 claim 提取/事实核查/结构审）。
- **provenance 完整**：`logs/phase13e_script_derivation_provenance.json`（derived_from + 源 sha256 + remapping 源文件/sha256 +
  规则版本 + 时间证据 + H5 素材绑定继承 + 零覆盖标记）。
- **映射证据（关键）**：v9 脚本 21 段**无 `scene_id` 字段** ⇒ 采用**段序↔景序**映射并以**时长证据**证实：
  **20/21 逐段吻合**（段时长 == `old_timeline_window_s` == v9 渲染时间轴窗口）；唯一偏差 **S21：65.0 s vs 67.0 s（Δ=2.0 s）**
  系已知 **E1 片尾卡插入**的时长差 ⇒ 属**时长差异而非文本对齐问题** ⇒ **无需改写任何文本**，
  故**未触发**授权 (a) 的 "STOP 并报告" 条件。
**② 全片运动候选渲染（PENDING，未启动）**：未产出。**已就绪输入**：派生脚本、运动开关 `config/render_motion.json`（`enabled=true`）、
H5 素材绑定（S05=Russell 页，sha256 已核验）、权威底片（守卫 `LINEAGE_OK`）。**未启动原因**：管线级渲染需先构建 **Engine 夹具**
（项目 + `script_output`(=派生脚本) + `retrieval` 载荷/素材池 + 旁白音频），再跑 `editing._render`（运动 enabled），
随后执行全门复验（PI 全门 / 响度契约 / 时长 978.7±1 s / 逐景 corr（**S06 小裕度如实记录、不调阈值**） / 字幕与旁白对齐）、
**DQ 双口径**（**不宣称 PASS**）与逐景 **MOTION_VERIFIED**；单次渲染 ≤3 h。配方 §8.3；就绪输入 `logs/phase13e_p13e3_final_state.json`。
**口径/边界**：回归（含守卫套件）**77 套件 / 77 rc=0 / FAILED: []**；LLM **$0**、网络 **0**、**未执行渲染**、**零 promotion**、
**未放宽任何 PI/DQ 阈值**；权威底片/v9 底片/既有脚本产物/`config.json`/P7-6 产物/13-D 台账与报告**均未改**。

## Phase 13-E 收官 — P13E-3 运动臂全片候选：就绪度 DONE；渲染 **PENDING（前置缺口：DCv2 谱系无脚本产物）**（2026-09-30）

**已完成（实测，全部只读或授权允许的开关文件）**：
- **底片守卫**：`assert_lineage(output/phase6g_exec_h5/20260929_151026/out/H5_rp-0ebebb71f99c.mp4)` ⇒ `LINEAGE_OK`（978.7 s，sha256 `3b61dafd…`）。
- **运动开关**（授权明确允许的**渲染开关文件**，非用户钉定配置）：新建 `config/render_motion.json`（`enabled=true`）；
  `core.motion.resolve_config()` 解析 ⇒ `{"enabled": true}`，来源 `render_motion.json`；**`config.json` 未改动**。
- **策略出处**：`core/motion.py POLICY[…]`（zoom ≤1.08 / 平移 ≤画面 3% / <10s 静止 / 启用 ≤60% / 窗口 ≤150 帧）——**未放宽任何阈值**。
- **DCv2 权威窗口**：`logs/phase6f_rebuild_plan_v2.json#remapping_21_segments`（21 条）合计 **978.7 s**，与权威底片**完全一致**（S05=[181.776, 221.862]）。
- **S05/Russell 绑定已在权威底片**（H5 `binding={"S05":"asset_h5_S05_65377b888b778226",…}` + `asset_records` + `replaced_all` 门禁）⇒ 无需替换。
**前置缺口（本阶段新发现，未擅自补）**：项目内唯一 `script_output` = `a_49b58fb3dc01`（21 段、**1530.0 s = v9 谱系**）
⇒ **不存在总时长 ≈978.7 s 的 DCv2 脚本**；而**管线级端到端渲染需要脚本**，若用 v9 脚本渲染则产出 **v9 1530 s 片**，
按 Phase 13-E 谱系纪律**禁止**（会重现 #65/#67 度量伪影）⇒ **本阶段不做该渲染**，如实 PENDING。
登记为 **KNOWN_ISSUES 候选 #72**：*权威（DCv2/H5）谱系产物不完整——重建只产出时基计划与成片，未产出对应 `script_output`*。
**P13E-3 配方（已固化）**：产物 `logs/phase13e_p13e3_readiness.json`（逐景 21 条 new 窗口 + TTS 时长 + pause 预算）——
守卫 → 按 `remapping_21_segments` **合成 DCv2 脚本**（段时长 = `new_timeline_window_s` 合计 978.7 s；旁白**文本**沿用既有脚本、
**音频为事实来源**，按 `new_audio_window_s`+`pause_budget_s` 放置）→ 素材绑定沿用 H5 `binding` → Engine/editing `_render` 渲染
（运动 `enabled=true`）→ 复验（PI 全门 / 响度契约 / 时长契约 978.7±1 s / **逐景抽帧 corr（S06 小裕度如实记录、不调阈值）** / 字幕与旁白对齐）
→ **DQ 双口径**（原口径复算 + DQ-3 `freezedetect` 语义并列，**不宣称 PASS**）→ 逐景 **MOTION_VERIFIED**（`render/motion_evidence.json` +
场景 10%/90% 抽帧像素差）→ 零 promotion、后台作业、单次 ≤3 h、超限先报告实际增速。
**边界/预算**：LLM **$0**、网络 **0**、**未执行全片渲染**；**未放宽任何 PI/DQ 阈值**；权威底片/v9 底片/现有脚本产物/`config.json`/
P7-6 产物/13-D 台账与报告**均未改**；新增仅 `config/render_motion.json`（授权允许）与 `logs/phase13e_p13e3_readiness.json`。
**回归（含守卫套件）**：**77 套件 / 77 rc=0 / FAILED: []**（本阶段未改被测代码）。

## Phase 13-E 续跑 — 守卫入套件（回归 77 全绿）+ P13E-2 结论（权威底片已含 S05 替换 ⇒ no-op）；P13E-3 PENDING（2026-09-30）

**① 守卫入 `tests/` 套件（先做）**：新增 `src/video_studio/core/lineage_guard.py`
（`AUTHORITATIVE_LINEAGE`(DCv2/H5 978.7 s, sha256 `3b61dafd…`, timeline_source, s05_window=[181.776,221.862]) /
`LEGACY_LINEAGE`(v9 1532 s, `22705c7d…`, #65/#67 缺陷清单) 常量 + `check_lineage()`/`assert_lineage()`/
`load_authoritative_timeline()`；**sha256 + 时长 ±1 s 双校验**，不符即拒绝构建 ctx）与 `tests/lineage_guard_test.py`
（**10/10 PASS**：权威底片 `LINEAGE_OK`；**v9 底片 `LINEAGE_MISMATCH` 且守卫抛错**；缺失 ⇒ `FILM_MISSING`；
权威轴 21 景且 S05=[181.776,221.862]；与 Phase 13-E 结论 JSON 一致；模块不触碰 PI/DQ 阈值、不写文件）。
**真实缺陷（仓库静态守卫抓出、已修）**：`subprocess_encoding_test` 报 `core/lineage_guard.py:56`（`subprocess(text=True)` 缺 `encoding`）
⇒ 补 `encoding="utf-8", errors="replace"`，该套件 6/6 PASS。
**全量回归：77 套件 / 77 rc=0 / FAILED: []** ✔（口径由 76 → **77**）。
**② P13E-2 结论（no-op on authoritative base）**：以权威底片 `H5_rp-0ebebb71f99c.mp4`（978.7 s，守卫 `LINEAGE_OK`）核验：
- DCv2 权威时间轴（`phase6f_rebuild_plan_v2.json#new_production_timeline`，21 景，S05=[181.776,221.862]）是
  **纯时基计划**——`selected_asset/asset_id` 全为 null，**不含素材绑定**；
- **H5 谱系已绑定 S05 = Russell 页**：`asset_records[0] = {asset_id: "asset_h5_S05_65377b888b778226",
  path: C:\\mp4agent\\h5_asset_candidates\\S05\\Russell_PM_1+1=2.png, sha256: "65377b888b778226…"}`；
  `binding = {"S05": "asset_h5_S05_65377b888b778226", "S11": "asset_h5_S11_1e9d2ab4e64ef982"}`；
- 相关门禁 **全 PASS**：`P0-S05 素材存在且 sha256 与人工验收一致`、**`C1 内置逐镜替换证据：S05/S11 均已替换（replaced_all）`**、
  **`B1 逐镜窗口 ASS == DCv2 表（2 文件，覆盖 ['S05','S11']）`**；PI 历史 pre/post 全 PASS。
⇒ **P13-4 的目标（权威底片上 S05=Russell + replaced 证据 + PI 通过）已在该母片达成**；在正确底片上重复同一 REPLACE
只会产出等价重复件 ⇒ **判定 no-op，不做重复渲染**（证据/理由：`logs/phase13e_p13e2_finding.json`）。
**副产物登记**：H5 报告顶层**未持久化** `_caption_time_base`/`timeline_identity`（其校验为执行期）⇒ 未来若需在权威底片上
做真实拼接，须先定位该时基持久化来源；**未绕过该门禁**。
**③ P13E-3（PENDING，未执行）**：运动臂全片候选（S05 已替换 + 运动层 enabled，管线级端到端）未产出 ⇒ 需一次全片渲染 +
全门复验（PI 全门/响度/时长/逐景 corr（**S06 小裕度如实记录、不调阈值**）/字幕与旁白对齐）+ DQ 双口径（DQ-3 不宣称 PASS）；
零 promotion、后台作业、单次 ≤3 h、超限先报告。
**边界/预算**：LLM **$0**、网络 **0**、**零渲染**；**未放宽任何 PI/DQ 阈值**；权威底片/v9 底片/`config.json`/P7-6 产物/
13-D 台账与报告**均未改**。**产物**：`src/video_studio/core/lineage_guard.py`、`tests/lineage_guard_test.py`、
`logs/phase13e_p13e2_finding.json`、`docs/regression_2x/PHASE13E_REPORT.md`（§7 续跑章节）。

## Phase 13-E — P13D-OPEN-1 根因重定向：底片谱系核正（结论 A）；P13E-2/P13E-3 PENDING（2026-09-30）

**P13E-1（DONE，只读核验）**：
- **权威底片 = DCv2/H5 978.7 s 谱系**：`output/phase6g_exec_h5/20260929_151026/out/H5_rp-0ebebb71f99c.mp4`
  （sha256 `3b61dafda11c1b9d22381833a00645670ec8b4f25b8fccca813bb7ac63cee0be`）；时间轴 =
  `logs/phase6f_rebuild_plan_v2.json#new_production_timeline`（21 景，**S05=[181.776, 221.862]**）；
  **PI 历史全 PASS**（pre：PI-1/2/6 + PLANNING_DRIFT/G-TL/G-PAD/G-SUB；post：PI-3/4/5 + frozen_recheck）。
- **v9 历史底片 = 1532.0 s**：`projects/p_96efdc03e1aa/output/t_d0a54bdf1810_draft.mp4`
  （sha256 `22705c7d7ea20b40…`）；其 `render_output`(t_d0a54bdf1810) 时间轴 **S05=[245.0, 300.0]**。
- **13-D 实际使用窗口 [245.0, 300.0]** ⇒ 与 **v9 轴逐值一致**、与 DCv2 轴**不一致** ⇒ **确证 ctx 误绑 v9 底片**。
- **指纹吻合**：PI-1 **0.6277 = 961.7/1532**（v9 历史值 #65）；PI-2/PI-3 **570.344/570.874 s**、PI-5 **73 条/33.8%**（v9 #67）；
  PI-6 漂移 **552.16 ≈ 1532.0 − 978.7 = 553.3 s** ⇒ 五门 FAIL 系**底片选择错误的度量伪影**，**非 S05 替换所致**。
- **结论：(A)** 权威底片 = 978.7 s DCv2/H5 谱系。
**两个假设的裁定**：监理备择假设（底片谱系绑定错误）**成立**；我方 Phase 13-D 的「ctx 时基/字幕基未附着」假设**证伪**
（原文登记保留、**不改写**，本阶段追加最终根因）。
**6-C 成因重定调（只登记不改写）**：6-C 的 **4/4 BLOCKED 同源**（同样以 v9 1532 s draft 为 `FILM`）⇒ 成因重定调为**底片谱系选择**；
`phase6c_approvals.jsonl`/`phase6c_execution_ledger.jsonl`/报告原文**一律未改**。
**底片谱系守卫（已实现 + 自检通过，stage 层）**：`docs/regression_2x/phase13e_p13e1_conclusion.py::assert_lineage()`
—— 以 `AUTHORITATIVE_LINEAGE`（film/sha256/duration_s/timeline_source/s05_window）做 **sha256 + 时长(±1 s) 双校验**，
不符即拒绝构建 ctx；自检 = 权威底片 `LINEAGE_OK`、**v9 底片 `REJECTED（守卫正确拦截）`**。
**操作守则**：任何 REPLACE/ADD 类修订候选的 ctx **必须以 DCv2/H5 978.7 s 谱系为底片**，构建前必须过 `assert_lineage()`。
**未做（如实 PENDING）**：① 守卫**未加入 `tests/` 套件**（加入后回归口径将变为 77 套件，需重跑全量）；
② **P13E-2**（DCv2 轴重建 ctx + 派生执行提案 `derived_from=bp-6320bf486a082901`（注明底片谱系变更）+ 转录批准 +
新沙箱 label `13e` 幂等重跑 P13-4 + PI-1…PI-6 强制复核 + `replaced=true` 抽帧比对）**未执行**；
③ **P13E-3**（运动臂全片候选 + 全门复验 + DQ 双口径，DQ-3 不宣称 PASS）**未执行**。
**口径与边界**：**未放宽任何 PI/DQ 阈值**；LLM **$0**、网络 **0**、**零渲染**；**未改 `src/`**、未改 `tests/`、未改 `config.json`；
权威底片/v9 底片/P7-6 产物/13-D 台账与报告**均未改**。
**产物**：`docs/regression_2x/PHASE13E_REPORT.md`、`docs/regression_2x/logs/phase13e_p13e1_conclusion.json`、
`docs/regression_2x/phase13e_p13e1_conclusion.py`（含守卫）。

## Phase 14 — VLM 视觉相关性判定：§0/§1 核对 DONE；P14-1…P14-4 **PENDING（阻塞：无 VLM 凭据）**（2026-09-30）

**§0 前置**：**Phase 13-E 无任何产物**（`*13e*` 全空）⇒ 不在进行中，本阶段不受其写操作阻塞。
**§1 开工核对（DONE）**：
- P7-4 相关性门禁 = `core/visual_relevance.py`：词表 `RELEVANT/PARTIAL/IRRELEVANT/NOT_ASSESSABLE`、
  `DECISION_PRECEDENCE=(IRRELEVANT,RELEVANT,PARTIAL,NOT_ASSESSABLE)`、规则链 `R0_L1_IDENTITY` → `R1_HUMAN_NEGATIVE` → `R2_HUMAN_POSITIVE`…；
  **实测 `logs/visual_relevance.json`（21 景）= RELEVANT 22 / NOT_ASSESSABLE 143 / IRRELEVANT 3** ⇒ 与授权书"**143 对 NA**"完全吻合（P14-3 可测目标）。
- 人工真值来源逐条定位：**M2 台账** `phase6b_m2_review_ledger_v9.jsonl`（11 条 REJECT 7/DEFER 4；
  字段 `finding_id/scene_id/asset_id/decision/decided_by/decided_at/entry_sha256`）、**mm 真值集** `phase5d_mmt_truth.json`
  （6 景 MATCH 4/MISMATCH 2；`verdict/narration_text/expected_domain/reason`）、**H5 人工接受**
  `phase6g_exec_h5.json#human_decision`（`"D0 / S05 PD-US（人工已接受地域）"`）、**DB `decisions`**（`selection_override` 529；
  `made_by` human 2440 / human:tester 504 / human:operator 21 / human:project-owner 4）、**已知陷阱对**（PICO/鲨鱼词法陷阱 + S05 四色地图人工否决）。
- 先例：`llm_judge_cache`（缓存键范式，本阶段改**文件缓存**，不新增 DB 表）、`LLM_REASONING_BUDGET_EXHAUSTED`（`max_tokens` 预算与显式错误码）、
  `tools/material_provider.py`（`PROVIDER_*` fail-closed 分类学）。
**差异登记（现实优先）**：授权书称 mm 真值含 `content_label`；**实测所有 `*truth*.json` 均无该字段** ⇒ 标签字段为 **`verdict`（MATCH/MISMATCH）**，
`phase6b_m2/m3_truth_freeze.json` 亦仅**冻结清单**（truth_file_sha256/truth_path/case_ids）⇒ P14-2 标签自上述来源逐条取用并记 provenance。
**决定性阻塞（未执行的原因）**：环境**无任何 VLM/视觉凭据**（`.env` 仅 `TAVILY_API_KEY`/`DEEPSEEK_API_KEY`）⇒ P14-2 的 ≥30 对真实评测**无法运行**；
按授权书"评测门禁前置、未达标不进入 P14-3"，**不写集成代码**，如实 STOP（**不伪造评测结果**）。
**解除所需（人工提供）**：`.env` 增 `VLM_API_KEY`（名称可配）+ `base_url`（OpenAI 兼容，便宜视觉档如 qwen-vl-flash/glm-4v-flash 一类）+ `model`；
配置落点 = 可选外部文件 `config/vlm_judge.json`（三级链：内存 `config.tools.vlm_judge` → 外部文件 → 默认 `{"enabled": false}`），**`config.json` 零改动**。
**P14-1 设计已冻结（报告 §4）**：确定性降采样（最长边 ≤768px、JPEG q80，入 `POLICY` 注明依据）、`temperature=0`、JSON+Schema 校验、
超时/重试与 `PROVIDER_*` 错误码、**文件缓存**（键 = `prompt_version|model|image_sha256|need_text_sha256`，命中 $0 复用）、
单次只看一个 (需求, 候选图) 对的独立性、`run.py vlm-eval`（一致性 + 混淆矩阵 + 成本；二次运行 $0 且逐字节一致）。
**达标线（运行前写死，不得事后调整）**：overall agreement ≥ 90% **且**「人工 IRRELEVANT → 机器 RELEVANT」= **0**。
**预算/边界**：本阶段 API **$0**、网络 **0 次**、**未改 `src/`**、未改 `config.json`、未改 DB；
仅新增只读盘点脚本 `docs/regression_2x/phase14_truth_inventory.py` 与 `docs/regression_2x/PHASE14_REPORT.md`；
Phase 7–13 产物/母片/冻结真值零改动；回归沿用 Phase 13 口径 76 套件全绿（未改被测代码，未重跑）。

## Phase 13-D — ctx 构建 + P13-4 执行（执行 SUCCEEDED，**PI 复核 BLOCKED**）；P13-5 PENDING（2026-09-30）

**ctx（DONE）**：6-C 同款 —— 权威 21 景 `material_timeline`（`t_d0a54bdf1810`，`timeline_duration_s=1532.0`）、
母片 `t_d0a54bdf1810_draft.mp4`（sha256 `22705c7d7ea20b40…`）、`ops_direction` 证据、`core_captions` cues、
**并入 P7-2 索引 + Phase 12 许可覆盖层**的素材注册表（13 条，含 Russell 页 `PUBLIC_DOMAIN`）、`prepare_sandbox`（copy-on-write）。
**设计决定登记**：6-B 执行器需 `affected_scope`/`proposed_change`，而 P7-6 提案内容被批准 `proposal_sha256` 绑定 ⇒ **不可改内容**；
故派生执行提案 `bp-5923b15f5201e666`（`derived_from=bp-6320bf486a082901` + sha256 + deterministic_hash）+ 派生批准
`ap-b182acf5bfa8`（`human:project-owner`，`verify_approval ok=true`）。
**P13-4 执行**：真实 6-B/6-C 执行器 **`SUCCEEDED`**（80.5 s）——窗口 `[245,300]s` 素材校验（sha256 一致/可解码/许可不受限）→
重编码（字幕重烧）→ 母版音轨流复制 → 头尾 stream copy；候选
`output/phase6b_m4_sandbox/p_96efdc03e1aa_13d/output/t_d0a54bdf1810_draft_m5_bp-5923b15f5201e666_replace.mp4`
（84,996,782 B，sha256 `b5f8d9850d0f819a80d50e46185d3b829703a6a595071f250e46fb2112a090c0`）；
**源项目/母片未触碰、零 promotion**。
**PI 强制复核 `BLOCKED`（未通过，如实登记）**：PI-1 FAIL（旁白覆盖 0.6277<0.9）、PI-2 FAIL（时长 shortfall **570.344 s**）、
PI-3 FAIL（尾部静音 570.874 s、占比 0.3726）、PI-5 FAIL（字幕 orphan 73、0.338>0.02）、PI-6 FAIL（边界漂移 **552.16 s**>5 s），
仅 PI-4 PASS ⇒ `[PROMOTE_BLOCKED]`；**DQ overall FAIL**（DQ-2/3/4/5/6/8 FAIL、DQ-1 UNKNOWN；DQ-3 `mean_hold 72.952 / max 95.0`）。
**未定位项 `P13D-OPEN-1`（UNRESOLVED）**：570 s 量级缺口/静音/漂移远超本次 55 s 窗口编辑 ⇒ 疑为沙箱 ctx 时基/字幕基
未完整附着（6-C 实跑与可见 `build_ctx()` 差异）；**不得**据此判定替换本身有问题，**不得**把 BLOCKED 写成 PASS，**未调任何阈值**。
**P13-5**：全片合成候选（S05 替换 + 运动层）**PENDING 未执行**（前置阻塞 `P13D-OPEN-1`；运动开关已就绪，默认 off）。
**DQ-3 口径**：运动使 `freezedetect` 不再触发 ≠ 结构变化 ⇒ 不得宣称 DQ-3 PASS。
**预算/边界**：LLM **$0**、网络 **0**；耗时 80.5 s（窗口拼接，非全片渲染）；**未改 `src/`**；母片/`config.json`/P7-6 产物/Russell 页素材未变。
**产物**：`docs/regression_2x/PHASE13D_REPORT.md`、`logs/phase13d_execution_ledger.jsonl`（hash chain seq=1）、
`logs/phase13d_approvals.jsonl`、`logs/phase13d_p13_4.json`。

## Phase 13-C — S05 REPLACE 执行批准：6-B 链登记 DONE；渲染类交付 PENDING（2026-09-30）

**§0 闸门解除（人工书面）**：项目所有者（`human:project-owner`）明确授权 Agent **通过 6-B 提案审批链转录并登记**
本条批准，`approval_document="Phase 13-C 授权书 §0 + 本消息（human:project-owner 签发）"` ⇒ Phase 13-C §0 所述
"系统/Agent 不得代写、不得自动写入 APPROVED"（`docs/PRODUCTION_RUN01_HUMAN_PREFLIGHT_CHECKLIST.md` L4/L78）
在本条批准范围内**由本人解除**；登记保留 `recorded_by=agent:transcription`、`human_note.authorized_by`，不冒充签名。
**批准登记（DONE）**：新增 `docs/regression_2x/logs/phase13c_approvals.jsonl`（**新文件**，6-C 台账未触碰）——
`approval_id=ap-0850dfa8c52f`、`proposal_id=bp-6320bf486a082901`、`proposal_sha256=8fc618a0cbe816c837d94bb2…`、
`approved_by=human:project-owner`、`approved_at=2026-09-30T02:57:25Z`、`decision=APPROVE`、`auto_approved=false`、
hash chain `seq=1`；**`verify_approval` ⇒ `{"ok": true, "code": "APPROVED"}`**（proposal_id + 内容指纹双绑定）。
**附加登记（DONE）**：真实 integration debt 入 `docs/KNOWN_ISSUES.md` **#71（`OPEN`）**——4-C `select-candidate`
只接受该场景 4-C 候选池的 `asset_*`（`core/selection_review.py:129`），而 P7-2/P7-6 使用 `ast-*` ⇒ 人工在 4-C 入口
**不可达** `ast-*` 素材（Phase 13-C §0"解除路径①"实测失败）；建议统一人工入口或声明 6-B 链为唯一入口（需新授权）。
**PENDING（不伪造 PASS）**：**P13-4** S05 修订候选渲染（Engine/editing 生产路径）+ PI-1…PI-6 + DQ 复核 +
`replaced=true` 抽帧比对；**P13-5** 全片合成候选（S05 替换 + 运动层，管线级端到端）+ 强制复验（PI 全门/响度契约/
时长契约/逐景 corr（**S06=0.3244 小裕度如实记录、不调阈值**）/字幕与旁白对齐）+ DQ 双口径报告。
**DQ-3 口径**：运动使 `freezedetect` 不再触发 ≠ 结构变化 ⇒ **不得**宣称 DQ-3 PASS；本阶段未产出 DQ 报告、
未对 DQ-3 作判定。
**边界/预算**：本阶段**未改 `src/` 代码**、未渲染、未写候选、零 promotion；母片/`config.json`/P7-6 产物零改动；
**LLM $0、网络 0**。报告：`docs/regression_2x/PHASE13C_REPORT.md`。

## Phase 13-C — S05 REPLACE 执行批准：按 §0 明文规则 **STOP**（未执行）（2026-09-30）

**结果**：**未执行批准登记，未渲染任何候选，未产出全片候选**（P13-4 / P13-5 仍为 **PENDING**）。
**原因（§0 触发）**：仓库存在明文规则——`docs/PRODUCTION_RUN01_HUMAN_PREFLIGHT_CHECKLIST.md`
（sha256 `08fb23aaa536aa06…`）：**L4**「三项确认记录必须由项目负责人本人签发；系统/Agent **不得代写**、不得自动批准」、
**L78**「记录必须由项目负责人本人签发；Agent/系统**不得代写结论、不得自动写入 APPROVED**」、
L43「不得修改 ledger 既有记录，只能以新签核记录追加」、L3「本文档…不构成任何 APPROVED 记录」。
授权书 §0 明定：存在此类规则则**不执行、登记出处后 STOP** ⇒ 依令停止，**不代写 human 身份批准记录**。
**范围/冲突登记**：该规则属 Production Run 01 人工前置项**分项规则**（针对其三项人工签核记录），非全仓通用条款；
但其措辞直接约束 Agent 对 human 签核记录的写入行为。既有先例 `phase6c_approvals.jsonl`（`approved_by=human:director(6-C)`，
由阶段执行器在**项目所有者授权书**基础上登记）与"必须本人签发"存在口径冲突 ⇒ 按铁律"现实与描述冲突时以现实为准并登记差异"处理。
**本阶段动作**：仅**只读**核对（规则检索、提案哈希复核、许可覆盖层一致性、替换素材 sha256）；
未写 decisions/changelog 中任何 human 批准记录、未改任何母片/候选/Phase 7–12 产物/`config.json`。
**登记产物**：`docs/regression_2x/logs/phase13c_stop_decision.json`（规则原文引用 + 范围分析 + 先例对照 +
未执行清单 + **解除路径**）。
**解除路径（人工选择）**：① 项目负责人本人执行 `python run.py select-candidate p_96efdc03e1aa --scene S05
--asset ast-92ca33138ffe64f4 --by human:project-owner --reason "…"`（既有"人工归属决定"通道）；
② 或人工**显式授权 Agent 转录**本节批准（解除该规则适用范围）。

## Phase 13 — 运动层生产接线（Ken Burns，默认关闭）｜S05 REPLACE 状态（2026-09-30）

**范围**：把 stage33 实验验证过的**整数帧 pan/zoom** 能力提炼为生产模块，接入渲染链（**默认关闭、fail-closed**），
解决成片"全静止 PPT 轮播"（DQ-3 静态保持 73s 的根因）；Part B（S05 REPLACE 执行与全片候选）本阶段**未执行**。
**零 LLM、零网络**；**`config.json` / `config.example.json` 零改动**；母片/既有候选/Phase 7–12 产物/stage33 文件零改动。

**逐项结论（如实）**：**P13-1 DONE ｜ P13-2 DONE ｜ P13-3 DONE（组件级真实渲染）｜ P13-4 PENDING ｜ P13-5 PENDING**。

**改法**：
- **P13-1** 新增 `src/video_studio/core/motion.py`（纯函数、确定性、零 I/O）：输入场景 → 输出**逐帧整数矩形** +
  ffmpeg `crop` 表达式 + 运动参数；策略常量**逐条注明依据**（zoom ≤1.08、平移 ≤画面 3%、<10s 静止、启用 ≤60%、
  头尾静止 8 帧、缩放偶数步长 2px、平移 ≥1px/帧）；`evaluate_closed_form()` 与真实矩形**逐帧 0 处不一致**。
  **差异登记**：只用 `crop` 表达式（`zoompan` 为亚像素浮点，违背整数帧纪律）；stage33 的"恒定步长贯穿整场景"与
  授权书幅度上限在长场景下不可兼得 ⇒ **运动集中在 ≤150 帧（6s）窗口**（幅度上限与整数帧纪律不变）。
- **P13-2** `agents/editing/agent.py`：`_narration_args` 中**加法**接入运动层——命中策略的场景把静态 `scale/crop`
  换成"放大画布 + 逐帧 crop 表达式"（**concat 之前**）；开关走 `core/motion.resolve_config()` 三级链
  （内存 → 可选外部文件 `config/render_motion.json` → **默认 off**）；**fail-closed**：构造失败 ⇒ 该场景回退静态 +
  `MOTION_FALLBACK_STATIC` 登记（证据落 `<project>/render/motion_evidence.json`）；新增示例 `config/render_motion.example.json`
  （不参与读取）。字幕/混音/时基语句逐字未改；关闭时静态模板逐字节保留。
- **P13-3** 真实渲染验证（组件级）：6 景（3 运动 + 3 静止对照），真实 ffmpeg 执行生产滤镜串与生产静态模板
  ⇒ `logs/phase13_motion_render_verify.json`：时长 Δ=0.0s；运动在屏实证 23.07/13.30/24.22（静止 0.04–0.39）；
  corr 全部 ≥0.30（0.3102–0.8020）；耗时增量 −1.17…+1.06 s/景。
  **真实渲染发现并修复 2 个真实缺陷**：① `min/max` 逗号未加引号 ⇒ `No such filter: '0)'`；
  ② pan 的 `x` 拼成 `x0*(c)`（乘法）⇒ 位移在 n≈20 后停止（实测 31.42 vs 0.011），改加法后 13.96、端到端 13.30。

**验证**：新增 `tests/motion_test.py` **22/22**；完整回归 ****76 套件 / 76 rc=0 / FAILED: []****；`IMMUTABLE_OK`（含 stage33 两文件与 S05 替换素材未变）。
**PENDING（不伪造 PASS）**：全 agent 管线级端到端渲染；**P13-4** S05 REPLACE 的批准登记/修订候选/PI-DQ 复核/`replaced=true` 抽帧比对；
**P13-5** 全片合成候选（并预告 DQ-3 语义变化：`freezedetect` 不触发 ≠ 结构变化，不得宣称 DQ-3 PASS）。

**产物**：`src/video_studio/core/motion.py`、`config/render_motion.example.json`、`tests/motion_test.py`、
`docs/regression_2x/logs/phase13_motion_render_verify.json`、`docs/regression_2x/PHASE13_REPORT.md`；
修改：`src/video_studio/agents/editing/agent.py`（授权加法、默认关闭）。

## Phase 12 — 素材索引许可数据 join（记录在案的许可进入绑定门禁）（2026-09-30）

**范围**：把**系统内已记录**的许可/署名声明 join 进素材索引视图，生成**可选增强覆盖层**，
并在**只读绑定模拟**中验证效果。**零 LLM、零网络、零执行**；**`config.json` / `config.example.json` 零改动**。

**问题（Phase 7 P7-6 暴露）**：5 个 HITL 绑定场景（S01、S13–S16）的根因是外部 Wikimedia 素材在 P7-2
AssetIndex 中 `license=UNKNOWN`（**下载缓存 `.index.json` 只记 bytes/cached_at/file，未 join 署名台账**），
许可门禁只能要求人工确认；而系统内其实**已有**这些素材的许可记录（attribution 产物 / render timeline）。

**改法**：
- **P12-1** 只读审计许可记录存放处 ⇒ `logs/phase12_license_sources.json`：**实测 DB 无素材/下载专表**
  （`artifacts.license` 列 18,147 行全 NULL = 负证据）；记录实际在 attribution 产物、
  `render_output.material_timeline[].selected_asset`、`phase6g_exec_h5.json::asset_records`、
  `retrieval_candidates` 产物；8 资产三态 **HAS_RECORD 5 / MISSING 3 / CONFLICT 0**。
- **P12-2** 新增 `src/video_studio/core/asset_license_join.py`（纯函数 join + 只读编排 `collect_records()`；
  精确键匹配；判类**调用** `classify_license`（语义零改动）；冲突 ⇒ `CONFLICT` 且不择一采信；
  缺失/记录自称 unknown ⇒ `MISSING` 保持 `UNKNOWN`）⇒ 覆盖层 artifact `logs/license_overlay_v1.json`
  （canonical JSON + sha256；**P7-2 原索引零改动**，CLI 前后 sha256 相同）；新增只读 CLI
  `run.py build-license-overlay`（人工触发，仅写覆盖层）。
- **P12-3** `ops/visual_binding.py::build(..., overlay=None)` **加法、默认关闭**：覆盖层非空时仅对
  `HAS_RECORD` 资产替换 license/class/attribution，并在候选/提案留 `license_provenance`（含 `source_of_record`）；
  **未改** `core/materials.py` 语义、任何门禁阈值、DQ/PI。
- **P12-4** 只读前后对照 ⇒ `logs/phase12_coverage_after.json`：无覆盖层重跑与 P7-6 产物**逐字节一致**；
  有覆盖层则 **S01/S13–S16 五景全部解锁**（`HITL_REQUIRED→KEEP`，覆盖 `COVERED 16→21`、`HITL_REQUIRED 5→0`），
  **S05 保持 REPLACE 提案态**；**零执行**（未写 ledger、未渲染、未替换素材、未动 6-G）。

**验证**：新增 `tests/asset_license_join_test.py` **19/19**；**完整既有回归 75 套件全绿**；`IMMUTABLE_OK`
（P7-2 索引与 `asset_diversity.json` 历史记录一致、P7-6 产物与 Phase 10 记录一致、6-G/baseline/config 钉定值一致、
`core/materials.py` 与 `phase4x_audit.json` 指纹一致）。**成本 $0、网络 0 次**。
**授权变更登记**：`ops/visual_binding.py` 哈希 `f8a48a4bfbcd… → d5017ef42b87…`（P12-3 加法、默认关闭，
向后兼容由臂 A 五项比较全 true 证明）。

**产物**：`src/video_studio/core/asset_license_join.py`、`tests/asset_license_join_test.py`、
`docs/regression_2x/logs/phase12_license_sources.json`、`docs/regression_2x/logs/license_overlay_v1.json`、
`docs/regression_2x/logs/phase12_coverage_after.json`、`docs/regression_2x/PHASE12_REPORT.md`；
修改：`src/video_studio/ops/visual_binding.py`（加法）、`src/video_studio/cli.py`（只读子命令）。

## Phase 11 — 标题与封面候选工程（吸睛但不失实）（2026-09-30）

**范围**：只改 metadata/thumbnail 两个 agent 的输出能力（**加法**）+ 新增只读标题校验器；
**未碰**发布链（platform agent / publish 工具）、image/video provider（封面仍概念态）、
script/structure/topic agent、critic/retention 既有维度与阈值（P11-1 仅改 CTA 缺席语义）。
**`config.json` / `config.example.json` 零改动**（P10 教训：其 sha256 被有效基线 manifest 逐字节钉定；
本阶段不变量断言见 `phase11_immutable_check.py`）。

**问题（先取证）**：metadata agent 原 prompt 仅写"禁止标题党"、schema 只有 `platforms[]`（6 平台标题），
**没有**"吸睛手法/引用出处/数字可溯"任何结构化字段 ⇒ 无法机械验证"不失实"，也无法度量吸引力设计；
旧基线产物 `a_e0ec01d11b5a.json` 即此形态（无 `title_candidates`）。另 Phase 10 遗留：无 CTA 稿件的
CTA 维度出现"仅 1/3 采样给分、median=1.0"的不一致。

**改法**：
- **P11-1** `ops/retention.py`：机械层判定 0 CTA ⇒ CTA 维度对全部采样一致 `NOT_ASSESSABLE`
  （`score=null`/`agreement=NOT_ASSESSABLE`/`scored_samples=0`，原始采样值留档）；
  有 CTA 稿件不受影响；单采样同样应用。
- **P11-2** 新增 `config/metadata_style_guide.md`（与 script 规范分离）：手法白名单 6 种（含好例/坏例）、
  **失实红线（优先级高于吸睛）**、平台规格（主标 ≤40 字 / 封面 12 字 / 变体 ≥2 / 多样性 ≥3）；
  `agents/metadata/agent.py`：schema 加法新增 `title_candidates[]`（`text/technique/evidence_refs/
  number_sources/why_win/disappointment_risk`）+ `ab_plan`（`execution="manual"`），prompt 重写为
  "吸睛手法最大化 ∩ 失实红线零违反" + 8 条硬性规则（**`platforms[]`/required 未改未删**）；
  `agents/thumbnail/agent.py`：加法新增 `cover_text_candidates[]`（≤12 字 + 互补/递进/反差 + pairing_note），
  仍为概念方案不出图。
- **P11-3** 新增 `core/title_check.py`（纯函数、零 LLM、确定性；14 违规码 + `OLD_FORMAT` 结构码；
  数字可溯性为核心门，含中文数字归一化）+ CLI `run.py title-check --script <path> [--metadata] [--json]
  [--no-timestamp]`（只读、不建 engine、零写入、逐字节可复现）。

**验证**：新增 `tests/title_check_test.py` **30/30**；`tests/strip_v2_test.py` 扩展至 **29/29**
（P11 计划数据不入 TTS/SRT/ASS/朗读稿/发布面正文字段；并显式断言发布清单按设计内嵌计划数据）；
`tests/retention_check_test.py` 扩展至 **40/40**；**完整既有回归 74 套件全绿**；`IMMUTABLE_OK`
（`config.json` 仍为钉定值 `7b03424846f1…`）。
**真实回测**（`logs/phase11_title_ab.json`）：判据① 5/5 机械门通过 + **数字可溯性 100%** + 手法覆盖 5 种 +
封面 3/3；判据② 对旧基线 `OLD_FORMAT` 的**能力增量**成立；判据③ 3 条抽检**留待人工确认**
（不宣称语义级不失实已自动化）；判据④ `ab_plan.execution=manual`。**成本 $0.0266**（上限 $0.15）；网络 0。
**实测标定两处（均登记）**：回声门改用 **LCS≥12 或 3-gram 重合率>0.5**（旧基线 6 条单字重合率全 >0.8 ⇒
误报泛滥，改后 0 误报）；数字抽取的**计量性 precision 修正**（「一步/一遍/这一环/一份」不再计为数字断言，
真实数量表达仍受门）——使回测判据①由 2/5 变 5/5，原因在**校验器质量**而非放宽标准。

**产物**：`config/metadata_style_guide.md`、`src/video_studio/core/title_check.py`、
`tests/title_check_test.py`、`docs/regression_2x/PHASE11_REPORT.md`、
`docs/regression_2x/logs/phase11_title_ab.json`；修改：`agents/metadata/agent.py`、`agents/thumbnail/agent.py`、
`cli.py`、`ops/retention.py`（P11-1）、`tests/strip_v2_test.py`、`tests/retention_check_test.py`。

## Phase 10 — 数据驱动选题（topic signals）+ retention 评分器硬化（2026-09-30）

**范围**：新增**选题信号层**（`tools/topic_signals.py` + `run.py fetch-signals`）并让 topic agent 以**加法**方式消费信号；
同时硬化 Phase 9 遗留两项（多采样聚合、`cta_plan[].at_segment` 0-based 钉死）。
**未加管线阶段**、**未改** `pipeline/lifecycle.py`、**未改** topic 人工闸门、**未碰** search provider 配置与 LLM 档位配置。

**问题（先取证）**：① 选题长期靠"一句话方向 + 头脑风暴"，无任何真实热度/竞品输入（`agents/topic/agent.py` 41 行、无数据字段），
LLM 可自由编造"某题材很火"；② Phase 9 的 LLM rubric 为单样本估计（实测 σ≈0.32/5 分、判据达成率 4/5），
且 `cta_plan[].at_segment` 的 0-based/1-based 语义未被 schema 钉住（v3 A/B 稿出现 `at_segment=8` 而段数为 8）。

**改法**：
- **P10-1** ① `ops/retention.py`：`judge_script(samples=N)` 多采样聚合（median + 全距 + agreement，
  全距 ≤1.0 ⇒ STABLE）+ `scored_samples/sample_coverage/coverage_note`；**缓存键含 sample 序号**；
  **单采样路径输出结构与 Phase 9 完全一致**；CLI `retention-check --samples N`（默认 3）。
  ② `cta_plan[].at_segment` **钉死 0-based**：`agents/script/agent.py` 字段 description、
  `config/script_style_guide.md` v3 §2.3 注脚、`core/retention.py` 新增结构违规码
  `CTA_AT_SEGMENT_OUT_OF_RANGE` / `CTA_AT_SEGMENT_INVALID`（越界/非整数 ⇒ WARN，不计 FAIL）。
- **P10-2** 新增 `src/video_studio/tools/topic_signals.py`：`manual` / `bilibili_popular` 两 provider 同一快照 schema；
  归一化条目 + 上限 100 + url/bvid 去重 + 必填缺失丢弃披露 + **fail-closed `PROVIDER_*`**（沿用素材 provider 分类学，
  **零伪造条目**）；**快照模式**：`run.py fetch-signals --provider bilibili_popular [--out]`（人工触发单次拉取）
  ⇒ `signals/snapshot_<provider>_<UTC>.json`，topic agent **运行期只读快照、绝不联网**；
  `config.json`/`config.example.json` 加法新增 `tools.topic_signals`（**默认 provider=none**）。
  **现实差异登记**：授权书要求写进 `config.json`，但仓库硬契约（`metrics_test` M5d / `offline_mock_test` L7b /
  `phase5l_evidence`）把 `config/config.json` 的**逐字节 sha256** 钉在"当前有效基线"manifest（`7b03424846f1…`）
  ⇒ 改写会使三处契约转红（实测 71/73），唯一修法"重钉基线 manifest"被本阶段边界禁止。
  故 `config.json` **逐字节未改**（曾改写，已从基线 ZIP 精确复原并核验），配置改由
  `topic_signals.resolve_config()` 解析：`config.tools.topic_signals`（向前兼容）→ **可选外部文件**
  `config/topic_signals.json`（默认不存在 ⇒ none）→ 内置默认；附 `config/topic_signals.example.json`（示例，不参与读取）。
  修复后 `metrics_test` 18/18、`offline_mock_test` 23/23 恢复。
- **P10-3** `agents/topic/agent.py` 加法：schema 新增 `proposals[].{signal_refs,why_now,angle_gap}` 与顶层 `signals_digest`；
  prompt 新增信号规则四条（引用真实条目 / why_now 基于真实数据 / angle_gap 非复述热点 / **无信号禁编造热度**且 note 必须含
  「无数据信号，本提案为纯头脑风暴」）；运行期在 **agent 工具层**加载信号并注入 prompt，产物内 `signals_digest` 由 agent
  **从快照计算覆盖** LLM 复述，`signals_context` 留存快照 sha256 与 `signal_refs` 校验结果（**不自动改稿**）。

**验证**：`tests/topic_signals_test.py` **23/23**（归一化/去重/丢弃/上限、6 类 provider 失败路径 + **两种 data 形态**、
快照确定性、只读加载、`signal_refs` 三类违规码、无信号披露、schema 加法不变式）；`retention_check_test` 增补 3e/3f；
`creator_style_v3_test` 增补 1f/1g；**完整既有回归 73 套件全绿**（见 suites_summary.json）。
**retention 3 采样**（`logs/phase10_retention_3sample.json`）：v2 hook 4.0/CTA 1.0(1/3 采样)/张力 3.5，
**v3 4.5/4.5/3.5**，生产稿 4.0/NOT_ASSESSABLE/3.5 ⇒ **v3 median ≥ v2 median 全满足**。
**真实 A/B**（`logs/phase10_topic_ab.json`）：带信号 5/5 提案 `signal_refs` 合法 + why_now/angle_gap 齐备；
不带信号走披露路径；**两臂零编造热度数字** ⇒ `all_ok=true`。**成本 $0.136497**（上限 $0.20）；网络 bilibili 1 次。
**如实登记**：授权书称接口 `data:[...]`，**实测为 `data:{list:[...],no_more}`** ⇒ provider 兼容两形态并记录 `data_shape`；
Phase 8 的 A/B v3 稿因 `at_segment=8` 在 P10-1 后机械层 cta PASS→WARN、score 87.5→80.0（新规则检出既有歧义，非回归，冻结产物未改）。

**产物**：`src/video_studio/tools/topic_signals.py`、`src/video_studio/agents/topic/agent.py`、
`tests/topic_signals_test.py`、`signals/snapshot_bilibili_popular_20260929T153554Z.json`（运行时数据）、
`docs/regression_2x/PHASE10_REPORT.md`、`docs/regression_2x/logs/phase10_topic_ab.json`、
`docs/regression_2x/logs/phase10_retention_3sample.json`（+ `phase10_retention_cache.json`）；
修改：`src/video_studio/cli.py`（`fetch-signals` + `--samples`）、`src/video_studio/ops/retention.py`（多采样聚合）、
`src/video_studio/core/retention.py`（at_segment 校验）、`src/video_studio/agents/script/agent.py`（字段 description）、
`config/script_style_guide.md`（注脚）、`config/topic_signals.example.json`（新增示例，不参与读取）。
**（`config/config.json` 与 `config.example.json` 最终逐字节未改——见上"现实差异登记"。）**

## Phase 9 — retention-critic（内容留存质量评分器：机械层 + LLM 评审层，只读）（2026-09-30）

**范围**：新增只读评分器（`core/retention.py` 机械层 + `ops/retention.py` LLM 编排 + `run.py retention-check` CLI），
并落地一项 router 可诊断错误码（P9-1）。**未接入生产判定链**、**未改** `agents/critic/agent.py`（职责边界：
critic 管事实红线、retention 管留存，二者互不替代）、未改任何既有闸门阈值、未改 LLM 档位配置。

**问题（先取证）**：Phase 8 发现 `deepseek-flash` 为推理模型，`reasoning_content` 与 `content` **共享 max_tokens**，
预算被推理吃满时 content 为空、上层只能看到"JSON 解析失败"；同时系统缺少对"好不好看"（hook/节奏/情绪/CTA）的
可复算度量 —— 生产正片稿（21 段/1530 s）无 v3 元数据可评估项，只有人工观感。

**改法**：
- **P9-1** `llm/router.py`：200 响应后新增判定 —— `content` 空且 `reasoning_tokens>0` ⇒
  `LLMError("LLM_REASONING_BUDGET_EXHAUSTED")`，异常附 `usage`（含 `max_tokens_requested`）与 `model`。
  **不改档位/不改既有错误语义/不自动加大预算/不重试**；`content` 非空时行为完全不变。
- **P9-2** `core/retention.py`（新，纯函数、零 LLM、零 I/O）：六维机械评分（hook 结构/hook 间隔/情绪节拍/CTA/
  节奏/结尾），阈值**全部镜像 style guide v3 留存工程节**（每项带 `basis`，不发明新数）；证据为**段落下标+原文引用**；
  缺 v3 元数据 ⇒ 结构码 `V3_METADATA_ABSENT` **单独计数、不计 FAIL**、该维度 NOT_ASSESSABLE 且不进评分分母；
  `mechanical_score` 权重显式；明确 `out_of_scope`（不评事实对错）。
- **P9-3** `ops/retention.py`（新，**严格只读**）:`tier=R`、`temperature=0`（子类 `TemperatureZeroClient` 实现，
  父类行为不变——授权书限定 router 改动仅限 P9-1，**差异已登记**）、`prompt_version=retention-judge-v2`；
  rubric（hook 强度/CTA 自然度/张力曲线 各 0-5，**必附原文引用**）+ 逐段张力与低谷定位 + top-3 改稿建议（只建议）；
  缓存键 `prompt_version+model+script_sha256`（沿用 `llm_judge_cache` 先例，ops 只读缓存、不落盘）；
  LLM 不可用/异常/输出非法 ⇒ `PARTIAL` **且无任何分数（不编造）**；校验器拒绝"PARTIAL 带分数"与"有分无证据"。
- **P9-4** `cli.py`：`retention-check <pid> [--task]` / `--script <path>`（`--json/--no-llm/--cache/--no-timestamp`），
  加入只读命令白名单（不建 engine）；DB `mode=ro`+`query_only`、零写入、不派任务；`--json --no-timestamp` 逐字节可复现。

**验证**：`tests/retention_check_test.py` **34/34**（机械层逐维度用 Phase 8 两版真稿夹具、结构码路径、
5 开场+5 CTA 黑名单变体、机械层与 CLI 确定性、P9-1 三场景、LLM 纪律、只读静态证据）；维护守卫 **30/30**
（`ops/retention.py` 登记只读白名单）；**完整既有回归 72 套件 / 72 rc=0 / FAILED: []**。
**区分度回测（真实 LLM，权威样本第 5 轮）**：判据①机械层逐维度 v3≥v2 ✔；判据②v3 hook 4.0 ≥ v2 3.5 且 v2 有 2 条
可执行 hook 建议 ✔；判据③不评事实 ✔；判据④生产基线 机械层 85.7 + rubric(hook 4.0/CTA null/张力 3.5) ✔；
二次运行全部命中缓存且判定内容逐字节一致 ✔（`artifact_hash` 因按设计含成本证据字段而不同，已登记）。
**成本**：6 轮真实调用合计 **$0.185178**（上限 $0.30）。
**如实登记**：轮次 B 曾 v2=4.5 > v3=3.5（判据②该轮**未达成**，未改写）；5 次采样 hook 分布
v2=[4.5,4,4,4,3.5]、v3=[3.5,4,4.0,4.5,4]（σ 0.316，配对达成率 0.8）⇒ LLM rubric 为单样本估计，
建议下一阶段多采样聚合；轮次 A 的 prod 于 8192 截断 ⇒ 如实 PARTIAL。

**产物**：`src/video_studio/core/retention.py`、`src/video_studio/ops/retention.py`、`tests/retention_check_test.py`、
`docs/regression_2x/PHASE9_REPORT.md`、`docs/regression_2x/logs/phase9_backtest_{v2,v3,prod,summary}.json`、
`docs/regression_2x/logs/phase9_retention_variance.json`（+ 5 份采样缓存）；修改：`src/video_studio/llm/router.py`（仅 P9-1）、
`src/video_studio/cli.py`（两个只读子命令）、`tests/maintenance_fixes_test.py`（只读 ops 白名单登记一行）。

## Phase 8 — Creator Style v3（事实红线 + 留存工程）（2026-09-30）

**范围**：只改**内容创作层**（创作规范文本 + script/structure 两个 agent 的 schema 与提示词）与**对应测试**。
**未改**管线结构、渲染、评测栈、素材 provider、**LLM 档位配置**；**未做**素材替换（S05 的 REPLACE 保持提案态）、重渲、发布、critic 改造、视觉层改动。

**问题（先取证）**：v2 把优先级写成单条线性链（Truth > Claim 边界 > 事实准确性 > 逻辑完整性 > 叙事效果 > 文风 > 华丽表达），
实践结果是所有项可互相权衡、"严谨"压过一切：`p_96efdc03e1aa` v9（1532 s，真实素材+真实旁白）**无情绪节拍、无互动引导、
结尾刻意反高潮**，人工验片 **FAIL**（`docs/KNOWN_ISSUES.md` **#67**，与工程门禁 PASS 并存不矛盾）——"严谨但没人看完"。

**改法**：
- `config/script_style_guide.md` 升级 **v3**：优先级改**两层结构**——**红线层**（Truth/Evidence、Claim 边界、事实准确性，准入条件、不参与权衡）
  与**优化层**（完播/留存 > 叙事张力 > 文风）；总纲「宁可少说，不可说错；在不说错的前提下，一切技巧为留存服务」。
  新增**留存工程**章节：① Hook 纪律（前 20-40 s 认知冲突 + **每 60-90 s 一个信息增量点/悬念/反转**，空泛悬念不算）；
  ② 情绪节拍（`emotion_beat ∈ {curiosity,tension,payoff,calm,surprise}`，**全篇不得连续 3 个同类**，节拍是元数据不入正文）；
  ③ CTA 纪律（全片 **1-2 处**、必须与内容强绑定、**禁裸话术**；结尾由纯反高潮改为「收束观点 + 至多 1 句内容型互动」）；
  ④ 留存不得越界（禁假钩子/夸大证据/把推测写成事实/删限定词/制造不存在因果）。**v2 全部条款逐条保留**（反 AI 腔、反营销腔、
  【事实】【推断】【观点】【争议】分区、口头禅清单、自检 10 项），v2 原文另存快照 `docs/regression_2x/phase8_style_v2_snapshot.md`
  （sha256 `17e6439271dcfed835581cf04d2119d8a773c30191baf10ad53f610dbdfd8465`）。
- `src/video_studio/agents/script/agent.py`：**加法** schema —— `segments[].emotion_beat`（enum 强制）/`segments[].retention_device`、
  顶层 `cta_plan[]`（`{at_segment,type,line}`）/`hook_map[]`（3 项备选各自钩子类型）；提示词载入 v3 并新增「留存元数据纪律」4 条
  （含 **"新增字段是元数据，绝不写进 narration 文本本身"**）。**既有字段与 required 一律未改未删**。
- `src/video_studio/agents/structure/agent.py`：**加法** schema —— 每章 `hook`/`hook_interval_ok`；提示词新增
  「章节间必须有钩子衔接；**连续 90 秒无信息增量点视为结构缺陷**（如实标注，**不得改数据凑通过**）」；既有约束（不改人类已确认核心观点）保留。

**验证**：
- 新增 `tests/creator_style_v3_test.py` **27/27**：schema 加法与既有字段未删、`emotion_beat` 枚举被 schema 强制、
  v3 规范文本不变量（含 **v2 关键条款逐条机器比对**，不靠人工眼力）、**留存元数据 7 类违规码**
  （`V3_BEAT_ENUM`/`V3_BEAT_RUN3`/`V3_CTA_TOO_MANY`/`V3_CTA_BARE`/`V3_CTA_NO_TYPE`/`V3_HOOK_MAP_SIZE`/`V3_META_IN_NARRATION`）、
  哨兵值下游隔离（voice 计划/SRT/SRT 文件/ASS/metadata 正文）。
- **扩展**（不新造链路）：`tests/strip_v2_test.py` **21/21**（脚本夹具加入 v3 元数据+哨兵，新增 7 项隔离断言，并证明内部产物仍保留元数据可追溯）；
  `tests/pipeline_mock.py` **14/14**（26 任务全管线，扫描全部用户可见产物+ASS 的 v3 泄漏守卫）。
- `tests/dq_truth_test.py` **122/122**；**完整既有回归 71 套件 / 71 rc=0 / FAILED: []**（Phase 8 前 70 套件 rc=0）。
- **离线 A/B（真实 `deepseek-flash`，同一简报）**：四轮尝试成本全部计入 **$0.04128**（上限 $0.30 未触）；最终两臂各 8 段合法 JSON，
  v3 新增 `hook_map` 3 / `emotion_beat` 覆盖 1.0 / `retention_device` 8 / CTA 2（**无裸话术、内容绑定**），
  且 `fact_risks` 12→13、claim 边界措辞 3→3 ⇒ **事实纪律未退化**；产物 `docs/regression_2x/logs/phase8_ab_v2.json`、
  `phase8_ab_v3.json`（两臂全文留档供 retention-critic）+ `phase8_ab_crosscheck.json`（v3 真实输出零违规）。
- **真实技术发现（非规范差异，档位配置未改）**：`deepseek-flash` 是**推理模型**，`reasoning_content` 与 `content` **共享 `max_tokens`**；
  轮次 1（4096）/2（8192）预算被推理吃满 ⇒ `content` 为空（两臂同等，4 份失败尝试证据已留档）；
  建议下一阶段在 `llm/router.py` 增加"content 空但 reasoning_tokens>0"的可诊断错误码（**本阶段未改 router**，属越界）。

**产物**：`config/script_style_guide.md`(v3)、`src/video_studio/agents/script/agent.py`、`src/video_studio/agents/structure/agent.py`、
`tests/creator_style_v3_test.py`、`tests/strip_v2_test.py`、`tests/pipeline_mock.py`、`docs/CREATOR_STYLE_V3_UPGRADE.md`、
`docs/regression_2x/PHASE8_REPORT.md`、`docs/regression_2x/phase8_style_v2_snapshot.md`、`docs/regression_2x/logs/phase8_ab_*.json`。

**登记差异（Phase 7）**：CHANGELOG/STATUS 此前无 Phase 7（P7-1…P7-6）条目；依据用户验收记录
（`P7_1_ACCEPTED`…`P7_6_ACCEPTED`，6 份产物 + 回归 70 套件 rc=0）判定其**已完成并验收、仅登记缺失**，不擅自补写历史条目。

## 5-M 成片字幕化（画面内整段文案 → 底部逐条字幕）（2026-09-21）

**范围**：只改**字幕呈现**。**未新增**视频能力 / Judge 能力 / truth set / 阈值 / 自动选材 / 自动发布；时长契约、音频母带链、素材装配、HITL 与人工决策链**未改**。

**问题（先取证）**：旧实现 `agents/editing/agent.py::_narration_args` 对**每个脚本段落**生成一条 `drawtext`：
按文本长度自适应字号（28/34/42）、按字符数硬折行（26/20/16 字/行）、**画面正中**（`x=(w-text_w)/2:y=(h-text_h)/2`）、
`enable` 覆盖整段时长 → 成片等于把**整段旁白铺满画面中部**（`p_96efdc03e1aa` t=20s 实测 7 行文字块），而不是字幕（登记 #66）。

**改法**：
- **新增** `src/video_studio/core/captions.py`（**纯函数单一事实源**）：按句末标点切句 → 按停顿标点细分（每条 ≤36 字）→
  按**视觉宽度**折 ≤2 行（优先在标点处断、行首不放标点）→ 单条显示时长 = `字数/5.0` clamp **[1.0 s, 8.0 s]**，
  并在**镜头窗口内均匀铺开**（剩余时间为静默间隔；超出窗口则按比例压缩，绝不越界/重叠）；
  输出 `to_srt`（**每条单行**，保持文本可检索）与 `to_ass`（PlayRes=分辨率、**底部居中 Alignment=2**、描边 Outline=3、
  字号=高度×4.2%、MarginV=高度×5%）。
- `agents/subtitle/agent.py`：改用 `core.captions` 产出 **cue 化 SRT**（产物新增 `cues` 字段；`segments` 仍为段数，向后兼容）。
- `agents/editing/agent.py`：删除"每段一条 drawtext"的旧烧录，改为**一次 `ass=filename='…':fontsdir='C\:/Windows/Fonts'`**
  （libass；本项目 ffmpeg 构建含 `--enable-libass --enable-fontconfig`，实测 `ass`/`subtitles` 滤镜可用）烧录切分后的字幕；
  滤镜位置不变（`concat` 之后、`fade` 之前）。

**验证**：新增 `tests/captions_test.py`（**21/21**：切句/折行/排布/SRT/ASS/确定性/真实脚本 21 段全量不变量/边界）；
视觉探针（真实素材 + 真实脚本 + 同款滤镜）单行与两行字幕底部居中、无溢出、CJK 字形正常；
真实成片 **render v9 = `t_d0a54bdf1810`**：容器 1532.0 s / **视频轨 1531.96 s**（残差 1 帧）/ 38,300 帧 /
独立 `ebur128` **−16.1 LUFS / TP −2.5 dBFS**；字幕产物 21 段 → **216 条 cue**；
`topic/script/claims_map/editing_plan/structure/research/voice` 产物 sha256 与 claims/decisions 计数**全同**（内容未变）；
v1–v8 成片全部保留（append-only）。
字幕节奏实测：**覆盖率 64.5%**、静默间隔均值 2.5 s / **最大 4.6 s**、单条 1.0–8.0 s（原因见登记 #65：旁白 961.7 s vs 时间轴 1532 s）。

**回归**：5-M 电池 = 与 5-F/5-G/5-J/5-L **同一步骤序列**（25 步）→ **25/25 步 rc=0**（`all_rc_zero_raw=True`，4,397 s）；
批次 **24/24 符合预期**（`phase2e_real_provider` 13/13、`metrics_readonly` 18/18、`run_ingest_test` PASS）；
单元套件 **49/49 rc=0**（含新增 `captions_test`）；`e2e_mechanical` **3/3 SETTLED**；
冻结证据日志恢复 **drift 0 / missing 0**（163 改写回拷 / 0 新增 / 0 删除）；
代码/测试指纹冻结时与电池后一致（`c495dd64913c…`）。明细见 `PHASE5M_REPORT.md` §4 与 `logs/phase5m_evidence.json`。
**如实披露的自身缺陷**（两处，均已修正并复跑全绿）：① 首版用 `task["task_id"]` 命名 ASS，导致以"最小 task 字典"直接调用
`_narration_args` 的 `scene_assembly_test`/`narration_contract_test` 出现 `KeyError` → 改为 `task.get("task_id") or "adhoc"`
（不影响已渲染成片）；② `strip_v2_test` 的"烧录字幕源"断言原 glob 旧 `_seg*.txt` → 按测试契约改为 `_captions_*.ass`（断言意图不变）。

**基线**：`5.x-post-final-maintenance-baseline-r3`（`PHASE5M_REPORT.md` / `BASELINE_README.md`）；**不覆盖** r1/r2 与 `5.x-final-baseline`。

## 5-L 5-K 已确认失败项修复（离线 mock 独立化 + M5d 钉定换代 + 重渲染收口）（2026-09-21）

**范围**：只修 5-K 已确认失败项；**生产默认仍为真实 DeepSeek**；**未新增**视频能力 / Judge 能力 / truth set / 阈值 / 自动选材 / 自动发布。

**① 生产默认（不变）**：`config/config.json` 保持真实 DeepSeek（M/F=`deepseek-flash`、R=`deepseek-v4-pro`，含 `pricing`/`max_total_usd`），
**不含** `llm.mock`；`cli.load_config(None)` 仍解析它。

**② 新增独立离线 mock 配置（新）**：`config/config.mock.json` = 生产配置**逐字副本 + 仅追加** `llm.mock`
（responses 15 个角色 + default）；mock 段来源 = 冻结 `5.x-final-baseline` 内的 config，溯源写在文件自身 `_offline` 块
（purpose / production_default / mock_source / zip sha256 / 段 sha256 / generated_at / 不变式）。

**③ 离线用例显式使用 mock（修改 4 处 + 新增 1 套件）**：`tests/cost_accounting_test.py`、`tests/pipeline_mock.py`（加载 mock 配置）、
`docs/regression_2x/run_ingest_test.py` 与 `docs/regression_2x/run_all_tests.py`（机械 E2E，`run.py --config config/config.mock.json`）；
新增 `tests/offline_mock_test.py`（**23/23**）守卫：生产配置无 mock、mock 配置只多出 mock、**mock 不是默认**、
离线用例显式引用、生产代码零引用、mock 的 tiers/pricing/provider 与生产逐字一致、真实链路用例仍走真实配置、旧基线 sha256 未变。

**④ 测试/证据契约换代（不改业务语义）**：`tests/metrics_test.py` M5d 由**早已过期**的 `3.x-final-baseline`
改钉**当前有效基线** `5.x-post-final-maintenance-baseline`（**断言强度不变**：仍要求逐字节 sha256 相等）；
`docs/regression_2x/phase4ab_evidence.py` 同步改钉。

**⑤ 测试契约更新（1 处，公开说明理由）**：`tests/cost_accounting_test.py` 的「mock 运行费用为 0」改为
「mock 调用按价目表**如实计价**并写回任务（>0 且模型在价目表内）」+「逐任务非负、与 `compute_cost` 同源可复算」。
原因：旧断言成立的前提是"mock 模型恰好不在价目表内"（历史 `deepseek-chat`），配置换代后前提消失；
「价目未知不猜价（0 + `unknown_pricing` 标记）」仍由同文件独立检查保证（未削弱）。

**⑥ 重渲染（既有产物收口）**：`p_96efdc03e1aa` 以 5-K 修正后的渲染参数重渲染 → render **v8** `t_30070f93a77e`：
**视频轨 1511.0 s → 1531.96 s**（时间轴 1532.0 s，残差 1 帧）、独立 `ebur128` **−16.1 LUFS / TP −2.5 dBFS**、
attribution 21 镜 1:1（sha 0 处不符）；**旧 v7 成片 sha256 未变**（append-only）；
**topic / script / claims / 人工素材决策全部未变**（136 VERIFIED claim 与 id 全同、125 条决策与 `made_by` 分布全同）。
如实披露：执行 `redo` + `run` 时调度器先拾取了**陈旧 PENDING 分支 v5**（`t_a881aee95cf3`），使其转为 SUCCEEDED
并覆盖了该路径上的**孤儿文件**（82,655,278 B → 48,856,295 B；该文件此前不对应任何成功产物）。

**⑦ 未处理项（按授权）**：provenance 四件套未动；登记保持 `docs/KNOWN_ISSUES.md` §18 **#52–#64**（未新增、未改写）。

**回归**：5-L 电池 = 与 5-F/5-G/5-J **同一步骤序列**（25 步，脚本以 AST 解析步骤表比对一致）→ **25/25 步 rc=0**
（`all_rc_zero_raw=True`，4,260.9 s）；批次 **24/24 符合预期**；单元套件 **48/48 rc=0**；
`e2e_mechanical` **3/3 SETTLED**；`run_ingest_test` **VERDICT PASS**；`phase2e_real_provider` **13/13**；
针对性 **28/28 + 23/23**；冻结证据日志恢复 **drift 0 / missing 0**（162 个改写回拷 / 1 个新增保留）。
**基线**：`5.x-post-final-maintenance-baseline-r2`（387 文件，`verify_baseline` → **MATCH**），
**不覆盖** r1 与 `5.x-final-baseline`（旧 Final sha256 `be1717b9…` **未变**）。

## 5-K 收尾后维护（Post-Final Maintenance，2026-09-21）—— 形式采纳 2 处 post-final 改动（含缺陷修正）+ 当前官方模型默认 + 针对性回归 + CHANGELOG 补齐 + 杂物清理 + 审计只登记 + 新基线（**未改写 5.x Final**）

**授权边界**：基线 `5.x-final-baseline`（sha256 `be1717b9…`）**禁止修改/覆盖/重写** —— 本阶段复核：ZIP 哈希不变、384 条目不变、manifest==ZIP 条目、missing 0。
本阶段只做十项授权动作；**禁止**新增视频能力，**禁止**修改 Judge / truth set / threshold / multimodal evaluator / human decision chain
（守卫实测：上述文件与 5.x Final **逐字节一致**）。

**① 正式采纳静态图输入 1fps 取帧，并修正其缺陷**：`src/video_studio/agents/editing/agent.py` 图片分支改为
`-loop 1 -framerate 1 -t {ceil(d)+2} -i <img>`，每段滤镜追加 `fps={fps},trim=duration={d:.3f},setpts=PTS-STARTPTS`。
post-final 漂移版的原形态是 `-framerate 1 -t {d}`：1 fps 图片源在 `-t d` 下只产出约 d−1 帧，**每镜静默短 ~1 s**。
三种形态同条件实测（`tests/maintenance_fixes_test.py` M2，真实 ffmpeg）：

| 镜头时长 d | S0 冻结基线形态 | S1 漂移形态（缺陷） | S4 5-K 修正形态 | S4 帧数 / 标称率 |
|---|---|---|---|---|
| 2.0 s | 1.967 s | 1.000 s（**−0.967**） | 1.967 s（Δ=0.000） | 60 / 30-1 |
| 2.5 s | 2.467 s | 2.000 s（**−0.467**） | 2.467 s（Δ=0.000） | 75 / 30-1 |
| 20.0 s | 19.967 s | 19.000 s（**−0.967**） | 19.967 s（Δ=0.000） | 600 / 30-1 |
| 73.4 s | 73.367 s | 72.000 s（**−1.367**） | 73.367 s（Δ=0.000） | 2202 / 30-1 |

片级同条件对比（3 镜 7.0+5.5+9.25=21.75 s）：修正形态视频轨 **21.733 s**、漂移形态 **19.000 s**（**短 2.733 s**）。
既有产物 `p_96efdc03e1aa` v7 成片 **视频轨 1511.0 s vs 时间轴 1532.0 s（短 21 s）**，因容器时长由音轨 `apad` 占满而长期未暴露；
**该既有产物不回溯重制**（登记 #56 RESOLVED / #57 OPEN）。

**② 正式采纳 ffmpeg 超时 1800 → 7200 s（两处）**：`src/video_studio/tools/ffmpeg_tool.py` 的 `raw` 与 `render`（响度重编码）两处 `timeout=7200`；
`probe=120` / `concat=600` / ffprobe 校验 `60` **未改动**（只放宽等待上限，**不放松任何质量契约**）。

**③ 采用当前官方模型默认配置**：`config/config.json` tiers：M/F=`deepseek-flash`（当前官方 DeepSeek-V4.1-Flash）、R=`deepseek-v4-pro`（含 `pricing`、`max_total_usd`）；
`src/video_studio/llm/router.py` 回退由历史别名 `deepseek-chat` 改为 `CURRENT_OFFICIAL_MODELS["routine"]`，
历史别名（`deepseek-chat`/`deepseek-reasoner`/`deepseek-v4-flash-vision-exp`）登记为 `LEGACY_MODEL_IDS` 且**不猜价**（`unknown_pricing`）。
冻结判定模块内的硬编码旧 id **不改**（登记 #59）。
**代价（如实披露，登记 #62/#63/#64）**：被采纳的配置**移除了内联 `llm.mock.responses`**（旧 config 用于离线回归），
使原 mock 驱动的离线路径改走**真实 API**：`run_ingest_test` 转红（真实模型产出 4 条 UNSUPPORTED claim，被**冻结的生产闸门**按其 fail-closed 设计阻塞）、
`e2e_mechanical` 结果由 SETTLED 变为 MAXROUNDS/BLOCKED、3 个基线内套件因 `KeyError: 'mock'` 转红、当日回归真实计费 **$0.23852**。

**④ 针对性回归（新增）**：`tests/maintenance_fixes_test.py` **28/28**：源码形态 M1a–M1f、段级 S0/S1/S4 三形态对比 M2a–M2d、
片级装配与缺陷复现 M3a–M3d、**视频输入路径不受影响反证 M4a/M4b**（2.0 s / 30 fps / 命令中无 `-framerate`/`-loop`）、
超时 M5a–M5c、官方模型 M6a–M6c、清理留痕 M7a/M7b、禁改守卫 M8a–M8d。

**⑤ CHANGELOG 补齐与排序**：补 5-H / 5-I / 5-J / 5.x Final / 本阶段条目，`V2.5.7`（5-G）由文件末尾移回倒序位置；
新增"编号说明"（上述阶段未自报 `V2.5.x`，**未回填、未重编号**）。

**⑥ 杂物清理**：`config/config.mock.json.bak`（6,423 B / `b2646445…`）与 `output/run05/fix1_backup_orchestrator_core.py.bak`
（45,798 B / `09204d62…`）移入 `output/_quarantine_20260921/` + `MANIFEST.json`（原路径/大小/sha256 可回溯）；`config/` 内无 `*.bak/*.tmp/*.orig`。

**⑦ 审计发现只登记不修复**：`docs/KNOWN_ISSUES.md` §18 新增 **#52–#64**（悬空候选引用 13 条、陈旧 `external/.index.json` 11 条、
素材编辑缺一等溯源、邮票 sha 不明变化、运维旁路、回归覆盖缺口、跨文档口径不一致、本次配置副作用三项等）。

**⑧ 回归（如实，含红项；"未全绿"不得表述为通过）**：
- 针对性套件 **28/28** ✅；
- 全量批次 **24 项 → 21 项符合预期 / 3 项红**：`metrics_readonly`（17/18，M5d 钉定目标过期）、`run_ingest_test`（#62）、
  `phase2e_real_provider`（`[PROVIDER_TIMEOUT] _ssl.c:1011: The handshake operation timed out`，**环境**）；
- 单元套件 **48 个 → 45 个 rc=0 / 3 个红**：`cost_accounting_test`、`pipeline_mock`（均 `KeyError: 'mock'`）、`metrics_test`（17/18）；
- `e2e_mechanical` rc=0 但结果为 `A/B=MAXROUNDS`、`C=BLOCKED`（冻结时代为 3/3 SETTLED）→ **实质退化**（#63）；
- 当日回归真实模型成本合计 **$0.23852**（48 个项目）；
- 红项根因全部为 item ③ 的配置副作用或环境网络，**与 ①②④ 的代码改动无关**（M2/M3/M4/M5/M8 反证）。

**⑨ 新基线**：`5.x-post-final-maintenance-baseline`（ZIP + manifest + `verify_baseline.py` → **MATCH**，sha256 与文件数见
`docs/regression_2x/BASELINE_README.md`；回归状态另见同目录 `baseline_status_5.x-post-final-maintenance-baseline.json`，
**明示为未全绿**）；快照 `snapshots/5.x-post-final-maintenance-20260921`；`5.x-final-baseline` **未被改写**（哈希不变）。
本基线按授权 item ⑨ 冻结，但**不满足项目既有"电池全绿才冻结"的 DoD 前置条件**（差异已在该 status 文件与阶段报告中显式标注）。

**⑩ 判定**：见 `docs/regression_2x/PHASE5K_REPORT.md`（只报 PASS/PENDING/FAILED）；**STOP**。

## 5.x Final 收口与冻结（2026-09-19）—— 5-A～5-J 全部 PASS/CLOSED，`5.x-final-baseline` **FROZEN**

**范围**：5.x 阶段最终收口（汇总 5-A…5-J）。当时明文纪律：**不进入 5-K、不新增能力、不修改任何冻结件**。

**冻结基线**：`5.x-final-baseline`，`5.x-final-baseline.zip` sha256 `be1717b9c7fe9ed9124be3876db64b5893915a4d0ffad56bd37eded5e6e2141e`，
**384 文件 / 6,146,189 B**，`verify_baseline.py` → **MATCH（missing 0 / drifted 0）**；相对 `5.x-phase5g-baseline` delta = 修改 2 / 新增 2 / 删除 0；
快照 `snapshots/5.x-final-20260919.{zip,db,json}`。

**收口内容（5-J 落地）**：新增 `src/video_studio/ops/mm_review_confirm.py`（人工决策**记录**：三态 accept/replace/keep_unknown、
append-only JSONL、fail-closed）+ `src/video_studio/ops/test_review_confirm.py`；修改 `src/video_studio/cli.py`、`src/video_studio/ops/report.py`。
评估子系统（`mm_judge` / `mm_quality` / `multimodal` / `mm_temporal` / 词表）**零改动**（sha256 前缀 `bb882fb7…` / `d7a78587…`）。

**回归（阶段自报）**：电池 **25/25 步 rc=0**（`BATTERY_EXIT=0`）、套件 **46/46 rc=0**（含 `subprocess_encoding_test` 6/6 GBK 口径）、
R1–R8 **8/8**、`mm_quality` **34/34**、`mm_judge` **43/43**、编排器 **17/17**、冻结证据 **DRIFT 0**；
生产母片 Run01–04 哈希不变（`ff119fcd` / `ad52a0c0` / `871489f9` / `2f0e6687`）；
人工决策记录 **19 条** append-only JSONL（13 accept + 6 keep_unknown）。

**判定**：`5.x FINAL = COMPLETE / FROZEN`；`5-A～5-J = 全部 PASS/CLOSED`；
`LIMITATION = 运动素材 0 + Wikimedia 网络 PENDING + 实例粒度分歧 2 例（已人工裁决）`。

**口径说明（5-K 补记，未回改历史文档）**：本条目按**阶段报告自报**记录；5-G/5-H/5-I/5-J/5.x Final 五份文档之间存在若干口径不一致
（批次 `25/25` 与 `24/25`、v2 真值集 sha `8adc2985…` 与 `a9fc7379…`、Run04 域一致 `60` 与 `67`、决策记录 `18` 与 `19`、
5-H 报告/收尾的实现与覆盖口径、5-J FD11 自相矛盾等），**只登记不修改**，清单见 `docs/KNOWN_ISSUES.md` §18 #61。

## 5-J Final Gate（生产母片验收 + 人工决策记录闭环）（2026-09-19）

**范围**：5.x 最终闸门。新增 `src/video_studio/ops/mm_review_confirm.py`（**人工决策记录**，非自动拦截）+
`cli.py` 调度：`run.py mm-review-confirm <project_id> --decisions <file> --judge-json <file> --truth-set <file> --decided-by <who>`，
三态 `accept / replace / keep_unknown`、**append-only JSONL**、fail-closed；`tests/fixtures/mm_truth_set_v2.json` 于 5-G 期间重建。
**评估子系统零改动**（不改判定逻辑/阈值/真值集语义）。

**关键数字（阶段自报）**：电池 **25/25 步 rc=0**（`all_rc_zero_raw=True`、`BATTERY_EXIT=0`）；套件 **46/46**；
`mm-review-confirm` 测试 **8/8**（accept / replace / keep_unknown / append-only / fail-closed ×4）；编排器 T1–T14 **17/17**；
R1–R8 **8/8**；模块单测 **12/12**；冻结指纹 **14/14**（12 精确 + 2 已知 Phase 1.1 旧值）。
生产母片 `RUN04_PROD_G10_20260910_01`（sha256 `2f0e6687…`）：101 拍、域一致 CORRESPONDING **60**（≥60 新口径 ✅）、
HN/FALLBACK **34（33.7%，全角标）**、`ABAB/ABA/A?A/adjacent = 0/0/0/0`、`violations / ns_leakage = 0 / 0`、
A/V delta **0.15 s**、黑帧 **0** / 字幕 **100%**、`CV2/Retrieval 调用 = 0（冻结）`。
FD8 人工决策 **18 条**（12 `p_ab2b` accept + 6 `p_8f05` keep_unknown）。

**判定**：`5.x Final Gate = ALL PASS`；`5.x Final = 未宣布（等待人工确认后由人工宣布）`；`STOP`。
FD11 在 §2 表（`待更新`）与 §8（`✅`）**自相矛盾**（5-K 登记 #61，未回改）。

## 5-I v2 多模态评估结果的生产报告可见性（2026-09-19）

**范围**：把 **v2（32 例 / 3 项目）** 冻结评估结果接进生产报告咨询节。实现改动 = `src/video_studio/ops/report.py` 的
`format_mm_advisory` **重写为多文件聚合**；数据来源 = 冻结 Quality JSON（`phase5g_quality_p_*.json` ×3），**零实时计算**；
评估/判定逻辑零改动。（口径差异：5-I 报告称「**一个文件**」，5-I 计划另列 `cli.py` ✅ —— 5-K 登记 #61，未回改。）

**关键数字（阶段自报）**：咨询节输出 `覆盖: 32 例 / 3 项目`、`层判定汇总: MATCH=35 | MISMATCH=19 | UNKNOWN=13 | 无证据=6`、
`状态: OK=24 | VIOLATION=2 | UNRESOLVED=6`、`阈值: 未触碰 | UNKNOWN 为合法最终结果`；
DoD D9 电池 **25/25 rc=0** + 套件 **46/46**；D8 `mm_judge/mm_quality` sha 不变（`bb882fb7` / `d7a78587`）；
D12 v2 全量对账 ✅（14 + 18 = 32）；冻结 14/14（12 精确 + 2 Phase 1.1 旧值）；Run01–04 母片哈希不变。

**判定**：`5-I = PASS`（v2 全量 32 例/3 项目报告可见性完成；v1 零回归；评估子系统零改动）；`5.x Final = 未进入`；`STOP`。
遗留：`pre-existing environmental PENDING`；`#47` 保留；`#49` BY DESIGN（未授权）。

## 5-H 生产报告多模态质量咨询节（R4 + R6 落地）（2026-09-19）

**范围**：新增生产报告的**多模态质量咨询节**（只读展示，不驱动任何自动动作）。实现 = `src/video_studio/ops/report.py`
的 `format_mm_advisory` + `src/video_studio/cli.py` 的 `--mm-advisory`。**评估子系统零改动**
（`mm_judge` / `mm_quality` / `multimodal` / `mm_temporal` / `semantics` / 词表 / 阈值 / 生产 DB / Run01–04 母片）。

**两种口径（5-K 如实并列登记，未回改）**：
- `PHASE5H_REPORT.md`：读取**冻结 Judge JSON**、覆盖 **14 例**、汇总行 `4/3/6`（v1 真值集口径）；D3 `结构性 2 / 证据不足 2 / 环境 2`。
- `PHASE5H_CLOSEOUT.md`：读取**冻结 Quality JSON（逐项目）**、覆盖 **32 例 / 3 项目**、**57 行输出**、32 例全呈现；
  汇总 `层判定 MATCH=35 / MISMATCH=19 / UNKNOWN=13 / 无证据=6`、`状态 OK=24 / VIOLATION=2 / UNRESOLVED=6`
  （`p_ab2b` 7 MATCH + 4 MISMATCH 域边界 + 1 UNKNOWN）。

**回归（阶段自报）**：电池 **25/25**（5-H 两份文档记 `24/25`，唯一红项 `phase3a_regression_batch` rc=1，
根因网络依赖 / GBK stderr 编码，**pre-existing**，非本阶段代码回归）；套件 **46/46**；`mm_judge` 43/43；真值 14/14；DoD 12/12；
`mm_quality` 34/34；D8 `mm_judge/mm_quality` sha 不变 ✅；Run01–04 母片哈希不变（`ff119fcd` / `ad52a0c0` / `871489f9` / `2f0e6687`）。

**判定**：`5-H = PASS（实现完成 · 咨询节正确 · 零回归 · 网络红项 pre-existing）`；`MOTHER_RENDERED = N/A`；`5.x Final = 未进入`；`STOP`。
遗留：`#47` 保留、`#49` BY DESIGN、2 项网络依赖 `PENDING`、S06/S12 待人工裁决、运动素材 0（LIMITATION）。

## V2.5.7（2026-09-19）—— 5.x Phase 5-G：多模态真值集 v2

- 新增 `tests/fixtures/mm_truth_set_v2.json`（schema mm-truth-set-v2）：**32 例 / 3 个真实项目**（v1 14 例原样并入；
  新增 p_ab2b352e06b8 12 段多镜头旁白成片用例 7 MATCH / 4 MISMATCH 域边界；p_8f054c227bd4 6 段纯色底 UNKNOWN fail-closed）。
  运动素材覆盖 = 0（全库 1592 项目 0 视频资产，LIMITATION 如实记录，未虚构）。
- 新增逐项目子集 `mm_truth_set_v2_p_*.json` ×3（校准/Judge 评估流按项目运行）。
- `core/mm_quality.py`：`validate_truth_set` 增加 mm-truth-set-v2 分支（projects_min / multi_shot_min /
  fail_closed 维度 / motion_footage LIMITATION 披露必填；subset scope 豁免全矩阵）——评分/分级/可解释链逻辑零改动。
- 复验：v1 14 例零回归（judge 与 5-F 冻结一致）；p_ab2b 2 处实例粒度层-人分歧如实披露（S06/S12）；
  纯色底 6 拍层全部拒绝发证（fail-closed 正确）。
- 回归：电池 25/25 rc=0、套件 46/46 rc=0（含 subprocess_encoding_test 6/6 GBK 口径）。
- 基线：`5.x-phase5g-baseline`（sha256 见 BASELINE_README 5-G 行）。

## V2.5.6-Phase5F 多模态证据 Judge 收敛与最终边界验证（只读裁决层）（2026-09-17）

**范围**：5-F —— 确定 4-B/5-A/5-D 在最终系统中的**职责边界**，**不追求提高 MATCH 率**：
在冻结 14 例真值集上建立**最终 Judge/证据融合规则**（J0–J6 + 证据优先级 + 冲突处理），
明确 MATCH/MISMATCH/UNKNOWN 的最终条件，**UNKNOWN 作为合法最终结果**保留。
**只读、零动作、无阈值参数**；只判定与解释，不换材/选材/redo、不改时间轴、不写库。

**新增（3 个源码/数据 + 1 个测试 + 2 个证据脚本 + 1 份 DoD）**：
- `src/video_studio/core/mm_judge.py`（**新**）：规则表 `J0_FAIL_CLOSED` / `J1_STRUCTURAL_UNKNOWN` /
  `J2_EVIDENCE_CONFLICT` / `J3_MISMATCH` / `J4_UNANIMOUS_MATCH` / `J5_INSUFFICIENT_LAYERS` / `J6_UNRESOLVED`、
  5 级**证据优先级**、10 个理由码、`judge_scene`（纯函数）、逐例评估、DoD 生成、#43–#48 处置表、R1–R6 判定表、
  职责边界（`deliverable_scope`）；**不含任何阈值参数**。
- `tests/fixtures/mm_judge_truth_v1.json`（**新，冻结**，sha256 `a6332858a94d4a7f…`）：Judge 真值覆盖层 —— 按
  **同一批 case id** 引用 5-E 冻结真值集（`7eb952f2…`，**未修改**），追加"最终 Judge 应当输出什么 + 理由"；
  `unknown_policy` 要求最终 UNKNOWN ≥ 5 例。
- `src/video_studio/ops/mm_judge.py`（**新**）：只读编排（`mode=ro` → 三层证据 → 融合 → DoD）。
- `tests/mm_judge_test.py`（**新，43/43**）：覆盖层 fail-closed/指纹、J0–J6 规则单测、逐例评估、
  live + `--from-calibration` 一致性、DoD 12 条、处置完整性、零写与"无阈值参数"静态证明、职责边界。
- `docs/regression_2x/PHASE5F_MULTIMODAL_DOD.md`（**新**）：**最终多模态 DoD**（D1–D12 可度量条款 +
  组件级验收 + Out of scope + 限制 + R1–R6 处置）。
- `docs/regression_2x/phase5f_{evidence,regression}.py`（docs 不入基线）。

**修改（1 个文件，加法）**：`src/video_studio/cli.py` 新增只读子命令
`run.py mm-judge <pid> [--json] [--from-calibration] [--truth-set] [--judge-truth] [--out] [--frames-dir]`
（加入既有只读白名单，**不经过** `build_engine()`）。

**最终判定语义（收敛结果）**：
- `MISMATCH` = **任一层报 MISMATCH 且无 MATCH**（错配必须被拦住）；
- `MATCH` = **全部可用层一致 MATCH（≥2 层）**（MATCH 是断言；单层/部分层一致不足）；
- `UNKNOWN` = 其余（结构性 UNKNOWN / 冲突 / 部分层 UNKNOWN / 期望域缺失 / 模型不可用）——**合法最终结果**。
- 冻结 14 例结果：**14/14 满足 Judge 真值（0 违例 / 0 未解决）**，
  最终 `MATCH=4 / MISMATCH=3 / UNKNOWN=6`（≥ 下限 5）；S05 与 S06(side) 由"4-B MATCH + 像素层 UNKNOWN"
  收敛为**最终 UNKNOWN**（**未**为提升通过率放宽任何条件）。

**#43–#48 处置**：#45（保守 UNKNOWN）**解决**（固化为最终判据 J6）；#46（阈值敏感性）**解决**
（Judge 无阈值参数 + DoD D7 禁止路径）；#48 **解决**（留痕 + 双指纹钉定）；#43/#44/#47 **保留**为最终已知问题
（受素材与样本量限制）。新增登记 **#49**（Judge 未接入生产判定链，BY DESIGN）与 **#50**
（最终 MATCH 需全层一致 → MATCH 数低于 5-A 单独判定，BY DESIGN，不追求 MATCH 率）。

**R1–R6 判定（均未在 5-F 实施）**：**进最终产品**：R3（扩充真值集，评估侧）、R4（报告层区分 UNKNOWN 两种语义；
5-F 已以理由码实现等价物）、R6（top-1 一致性仅作展示）；**未来研究项**：R1（字幕掩码）、R2（候选成片口径预测量）；
**产品决策（非技术）**：R5（S06 是否换回 front，须人工决定 + redo）。

**只读与不覆盖**：DB 字节/五张表行数、项目 78 文件（含 6 成片）未变；静态扫描无写调用；
`core/multimodal.py`、`core/mm_temporal.py`、`core/mm_quality.py`、`core/semantics.py`、词表与冻结真值集
sha256 与 5-E 基线**逐字节一致**；重跑三层与 5-C/5-D/5-E 冻结证据一致（原结果未被覆盖）。

**回归**：单元套件 **46/46 rc=0**；批次 **24/24**；3-A **16/16**；3-B ×2 rc=0；4-A…4-G/5-A/5-B 证据 rc=0；
5-C 只读脚本全 rc=0；5-D **53/53**；5-E **34/34**；5-F **43/43**；冻结证据日志回归后**原样恢复**（drift 0）。
基线：`5.x-phase5f-baseline`（零漂移 MATCH，见 `docs/regression_2x/BASELINE_README.md`）。

## V2.5.5-Phase5E 多模态证据质量校准与可解释性（只读评估层）（2026-09-17）

**范围**：5-E —— 在**不改变自动选材与既有判定逻辑**的前提下，评估 5-A/5-D（以及 4-B）多模态证据的
**可靠性、边界与可解释性**：建立**冻结小型真值集**、三层**并列**评估、margin/top-k/投票/一致性/视角/阈值敏感性分析、
明确区分**模型证据 / 规则推断 / 工程阈值 / UNKNOWN**。**只读、零写、不调阈值**；只提出 5-F 建议，未实施。

**新增（3 个源码/数据 + 1 个测试 + 2 个证据脚本）**：
- `tests/fixtures/mm_truth_set_v1.json`（**冻结真值集，14 例**；sha256 `7eb952f2797e180c…`）：覆盖
  **S04/S05/S06**、**MATCH/MISMATCH/UNCERTAIN**、**视角差异（front vs side）**、**时序切换夹具**、
  阈值边界（近/远）、fail-closed（期望域缺失/模型不可用/帧数不足）；每例含
  `content_label`（来自 4-B 真值钉定或 4-C/5-C 人工决定，**不是模型输出**）+ `content_label_provenance`（出处）
  + `expect.allow / must_not / require_code_any / require_not_code_any / require_stability`。
- `src/video_studio/core/mm_quality.py`（**新**）：真值集加载/结构校验/**覆盖度**/指纹钉定、用例评估
  （allow/must_not/code/stability）、**边界距离**、**证据分级**（`MODEL_EVIDENCE`/`RULE_INFERENCE`/
  `ENGINEERING_THRESHOLD`/`UNKNOWN`）、**可解释链**、指标聚合（精确率/召回/UNKNOWN/违例）、**层间冲突检测**、
  **阈值敏感性**（只披露）、fail-closed 码表、**5-F 建议清单**（`implemented_in_5e=False`）。
- `src/video_studio/ops/mm_quality.py`（**新**）：只读编排（`mode=ro` → 冻结真值集 → 三层并列评估 → 报告）。
- `tests/mm_quality_test.py`（**新，34/34**）：A 真值集/覆盖度/指纹、B 评估逻辑与边界/解释链、C 指标与冲突、
  D 敏感性（含"放宽 margin −0.01 会把 UNKNOWN 变 MATCH"的反证）、E **真实校准 14/14**、F 只读与不覆盖、G 5-F 建议。
- `docs/regression_2x/phase5e_{evidence,regression,report_data}.py`（docs 不入基线）。

**修改（1 个文件，加法）**：`src/video_studio/cli.py` 新增只读子命令
`run.py mm-quality <pid> [--json] [--truth-set] [--out] [--frames-dir] [--no-layers]`
（加入既有只读白名单，**不经过** `build_engine()`）。

**校准结果（真实项目 + 真实 CLIP；14/14 用例满足真值集要求，0 违例 / 0 UNRESOLVED / 0 冲突）**：
- **MATCH 精确率 = 1.0（三层）**：没有任何一层把内容为 MISMATCH 的用例判成 MATCH（零误报）；
- 4-B：8 例（MATCH=6/MISMATCH=2），MATCH 召回 1.0、MISMATCH 召回 1.0；
- 5-A：10 例（MATCH=4/MISMATCH=2/**UNKNOWN=4**），MATCH 召回 0.667 —— UNKNOWN 只落在
  **"内容为 MATCH 但证据弱"** 的 T06(S05)/T08(S06 side) 上（保守，非误判）；
- 5-D：13 例（MATCH=4/MISMATCH=3/UNKNOWN=6）；其**原始** MISMATCH 召回 0.667 的唯一"漏项"是
  T10（镜头内切图夹具）——该例**要求**的正是 `UNKNOWN/MMT_TEMPORAL_SPLIT`（fail-closed），非漏判；
- **边界距离分析**：清晰 MATCH 用例的 `|中位边际|−阈值` = +0.040/+0.070/+0.055（S01/S02/S06-front）；
  T05(S04)=+0.008 贴边；T06(S05)=−0.0029、T08(S06-side)=−0.0139 贴边另一侧 → 与判定完全吻合；
- **top-k 分析**：全部内容-MATCH 用例的**期望域均为 top-1**（S01/S02/S04/S05/S06），
  而内容-MISMATCH 用例（鲨鱼照）的 top-1 是 `wildlife`（期望域不在 top-1）→ top-1 一致性与内容标签
  在本真值集上**完全一致**（仅作解释性指标，**未**据此改规则）；
- **敏感性（只披露）**：`margin` 收紧 +0.02/+0.04 会把 T02/T05/T01/T03 由 MATCH 变 UNKNOWN；
  **`margin` 放宽 −0.01 会把 T06(S05) 由 UNKNOWN 变 MATCH**（"不能靠调阈值"的直接证据）；
  `min_stability_cos` ±0.05 **对任何用例都无影响**；**S06(side) 与全部 fail-closed 用例永不翻转**。
- **证据分级**：`MODEL_EVIDENCE` 16 项字段、`RULE_INFERENCE` 8 项、`ENGINEERING_THRESHOLD` 8 项、`UNKNOWN` 2 项；
  每个用例都给出**四段式可解释链**（模型数值 → 工程阈值 → 规则推断 → 与真值是否一致）。

**边界与不确定性**：真值集小且**全部来自静态素材项目**（#42）；`UNCERTAIN` 标签仅 4 例；
T1/T2 分支靠受控夹具覆盖，**不可外推**。**未改动** 4-B 词表/真值、5-A 阈值、5-D 规则、许可门禁、
append-only、HITL；4-B/5-A/5-D 的判定模块与词表 sha256 与 5-D 基线**逐字节一致**，重跑结果与冻结证据一致。

**5-F 建议（**仅建议，均未实施**）**：R1 字幕区域掩码后再算帧间一致性；R2 候选的"成片抽帧口径"预测量；
R3 扩充真值集到多镜头/运动素材与更多项目；R4 报告层强制区分 UNKNOWN 的两种语义（"稳定不确定" vs "模型不可用"）；
R5 S06 素材是否换回 front（产品取舍，须人工决定）；R6 把 **top-1 域一致性** 作为**解释性指标**纳入报告
（本真值集上 100% 与内容标签一致，但样本小，**不足以**支撑规则变更）。

**回归**：单元套件 **45/45 rc=0**；批次 **24/24 as_expected**；3-A **16/16**；3-B ×2 rc=0；
4-A…4-G/5-A/5-B 证据 rc=0；**5-C 只读脚本全 rc=0**（append-only/库级 append-only/成片核验/fail-closed/断点检查）；
5-D 测试 **53/53**；5-E 测试 **34/34**；既有冻结证据日志回归后**原样恢复**（drift 0）。
基线：`5.x-phase5e-baseline`（零漂移 MATCH，见 `docs/regression_2x/BASELINE_README.md`）。

## V2.5.4-Phase5D 多帧/时序多模态证据增强（只读平行证据层）（2026-09-17）

**范围**：5-D —— 解决 5-A **单帧（3 帧平均）CLIP** 导致的 `MATCH/UNKNOWN` 不稳定：新增**加密多帧
（默认 7 帧）+ 帧间时序一致性**证据层，输出**逐帧证据 + 聚合规则 + 三态 + 置信度**。
**只读、默认关闭、fail-closed**；**不改 4-B / 5-A 结果**（平行证据），**不换材、不选材、不 redo、不改时间轴**。

**新增（3 个源码 + 1 个测试 + 1 个证据脚本）**：
- `src/video_studio/core/mm_temporal.py`（**新**）：`mmt_settings`（缺省关闭、非法值回退、`min_sim`/`margin`
  与 5-A 同值）、`temporal_metrics`（逐帧 argmax/期望相似度分布/边际分布/**相邻帧余弦**/散布/投票）、
  `classify_stability`（STABLE/MODERATE/SPLIT）、`temporal_verdict`（**T0–T7 规则** + 三态 + 置信度）、
  `run_temporal_worker`（同一 CLIP worker，`return_embeddings=true`）、`validate_temporal`（报告）。
- `src/video_studio/ops/mm_temporal.py`（**新**）：**只读**编排（`mode=ro` 读库 → 加密抽帧 → CLIP →
  时序报告 + **5-A 引用副本** `five_a_reference`，不改写 5-A 报告/日志）。
- `src/video_studio/core/mm_worker_clip.py`（**加法式修改**）：新增 `return_embeddings`（**默认 false**）
  → 为 true 时额外返回 512 维逐图视觉嵌入；**默认路径的输出与 5-A 逐字节不变**（已由 H5/I1 断言）。
- `tests/mm_temporal_test.py`（**新，53/53**）：A 默认关闭/配置、B 时序指标纯函数、C **T0–T7 规则**、
  D fail-closed、E 真实模型回归、F **S06 视角解释**、G **真实模型受控时序切换夹具**、H 只读/不覆盖、
  I 确定性。
- `docs/regression_2x/phase5d_evidence.py`（新，docs 不入基线）：证据汇编（含阈值敏感性）。

**修改（1 个文件，加法）**：`src/video_studio/cli.py` 新增只读子命令
`run.py mm-temporal <pid> [--json] [--artifact] [--out] [--frames-dir] [--no-five-a]`
（与 `multimodal-check`/`mm-review` 同列，**不经过** `build_engine()`）。

**真实结果（项目 `p_f4b466a4a024`，v6 成片 7 帧/镜头 = 42 帧）**：
S01–S04 `MATCH`（`T3_CONSISTENT_MATCH`；S01/S02 `HIGH`、S03/S04 `MEDIUM`）、S05/S06
`UNKNOWN / MMT_AMBIGUOUS`（`T7_AMBIGUOUS`，`MEDIUM`）；计数 **MATCH=4 / MISMATCH=0 / UNKNOWN=2**
与 5-A 同向；**全部镜头 `STABLE`**（无镜头内切换）。冻结 4-B 真值产物上 S04/S06 判 **MISMATCH（`T4`，wildlife）**，
与 4-B 方向一致。

**S06（5-C 退化）解释**：v5（front）`MATCH/HIGH`（中位边际 **0.0745**）→ v6（side）`UNKNOWN/MEDIUM`
（中位边际 **0.0061**）；两版**逐帧 argmax 全部为期望域、投票均 1.0**、帧间一致性 0.975/0.969（`STABLE`、无 split）
⇒ 该退化**不是时序/视角抖动造成的单帧噪声**，而是该视角画面在 CLIP 12 域上与 `vehicle` 域的区分度本身低于阈值；
时序层把结论从"不确定"变为**"多帧一致的稳定不确定"**，**未**（也不能）改判为 MATCH。

**fail-closed**：模型目录缺失 → 逐镜头 `UNKNOWN` + `MM_MODEL_MISSING`（**无** MATCH/MISMATCH）；无帧 →
`MMT_NO_FRAMES`；worker 失败/超时/非法 JSON → `MM_WORKER_FAILED`/`MM_TIMEOUT`/`MM_PARSE_FAILED`；
帧数不足 → `MMT_INSUFFICIENT_FRAMES`；期望域推不出 → `MMT_UNKNOWN_DOMAIN`。

**只读与不覆盖**：DB 字节与五张表行数、项目 78 个文件（含 6 个成片）逐字节未变；静态扫描无任何写库/写产物/
触发 redo 的调用形态；`core/multimodal.py`（5-A）sha256 与 5-C 基线一致；对同一产物重跑 `multimodal-check`
与 5-C 冻结证据一致（**5-A 结果未被覆盖**）。

**回归**：单元套件 **44/44 rc=0**（新增 `mm_temporal_test` 53/53）；3-A **16/16 PASS**；3-B 两脚本 rc=0；
4-A…4-G、5-A、5-B 证据脚本 rc=0；**5-C 只读脚本（append-only / 库级 append-only / 成片核验 / fail-closed /
断点检查）rc=0**；批次 23/24 as_expected（唯一非预期项 = 依赖真实网络的 `phase2e_real_provider`，
与冻结 `PENDING（环境）` 一致，**未改写状态**）；既有冻结证据日志回归后**原样恢复**（drift 0）。
基线：`5.x-phase5d-baseline`（零漂移 MATCH，见 `docs/regression_2x/BASELINE_README.md`）。

## V2.5.3-Phase5C 人工候选替换生效 + 全链复验（5-C）（2026-09-16）

**范围**：5-C —— **人工明确选定** 5-B 候选后，复用 4-C 既有闭环（`select-candidate` → `decisions`/`changelog`
→ 人工 `redo` version+1 → `run`）让替换**真实生效**，并对 4-B / 5-A / 3-A / 3-B / attribution / 许可门禁 /
版本链 / append-only / 未授权镜头 / fail-closed 做**替换后全量复验**。
**未新增任何写入口、未改动任何产品代码与契约阈值**；未进入 5-D。

**替换（人工决定，唯一写入口）**：
- `python run.py select-candidate p_f4b466a4a024 --scene S06 --asset asset_f3cf2b80432d --by human:project-owner --reason "…"`
  → decision `d_5ffb9971d5a3`（`node=selection_override`、`state=approved`）+ changelog **#902**（`human_confirmed=1`）；
- 素材：`asset_edece2b357f1`（`Meta Quest 3 front View.jpg`）→ **`asset_f3cf2b80432d`**（`Meta Quest 3 side View.jpg`，
  CLIP 视觉相似度 0.2886 为 5-B 排序第一，`FREE_ATTRIBUTION`、`source_id=139518403`）；
- `python run.py redo t_b8f866ddc062` → **v6 `t_6d692b93e342` SUCCEEDED**（v1–v5 全部保留）。

**替换后复验（全部通过，证据见 `docs/regression_2x/logs/phase5c_*.json`）**：
- 成片：`t_6d692b93e342_draft.mp4` 6,027,761 B sha256 `1c5759229cab328e985c10f1efd480e4ddc0d0409640c655092f14bfcfd1beef`；
  h264 High 1920×1080（3114 帧）+ aac LC 24 kHz；时长 104.0 s（== 时间轴，未变）；
- 响度：**独立 `ffmpeg ebur128` 复测 −16.1 LUFS / TP −2.7 dBTP**（契约 −16±1 / ≤−1.5），与渲染记录一致；
- 抽帧：6/6 镜头 corr_ok（S06 **0.354** > front 0.215，**像素级证明替换确实进入交付画面**）；
- 4-B：`MATCH=6 / MISMATCH=0 / UNKNOWN=0`；5-B：S05/S06 `CANDIDATES_READY`（只读，`db_writes=0`、`redo_triggered=0`）；
- attribution↔时间轴 **1:1（6/6）**、sha256 逐一相符；许可门禁以真实函数复核 6/6 通过、`licence_blocked_candidates=[]`；
- **append-only（库级最强口径）**：与 5-B 冻结 DB 快照逐表逐行比对 → 删除 **0**、改写 **0**；唯一就地改动是 `redo`
  的设计语义（6 个下游任务的 `dependencies` 由 v5 重指到 v6，白名单精确断言）；本次应有新行（v6 任务/两条产物/
  1 条 decision/1 条 changelog）确实存在；
- **未授权镜头未动**：仅 S06 变化，S01–S05 素材与全部时间窗完全一致；
- **fail-closed 负向验证 N1–N5 全 PASS**：不在候选池 / 无人工归属 / 无理由 → 拒绝且**零写入**；视觉模型不可用 →
  `UNKNOWN:MMC_MM_UNAVAILABLE` / `MM_MODEL_MISSING`，**零候选、零自动回退**。

**如实登记的退化**：S06 的 5-A 判定由 `MATCH`（Δ=0.0742）变为 **`UNKNOWN / MM_AMBIGUOUS`**（Δ=0.0061 < 0.02，
`xr_device 0.2248` vs `vehicle 0.2188`）→ v6 成片 5-A 计数 `MATCH 5→4 / UNKNOWN 1→2`，**未产生 MISMATCH**，
4-B 仍 `MATCH=6`。**未通过调阈值或改判定逻辑消除**（`KNOWN_ISSUES.md` #32/#33）。

**修改（1 个文件，测试校准）**：`tests/multimodal_test.py` 的 F2 断言由写死「5 个成片」改为
「成片字典逐字节未变 **且** 成片条数 == DB 中成功渲染版本数」（新增 `successful_render_versions()`）；
原因：5-C 授权替换使该项目由 5 个成片变为 6 个，原断言为**过期校准**（首轮 **42/43**）；新断言**更严**（未放宽只读规则）。
首轮失败证据留档 `logs/phase5c_rerun/PRESERVED_suite_multimodal_test_failed_20260916.log`。登记为 `KNOWN_ISSUES.md` #37。

**新增（docs 下，按 `--no-docs` 口径不入基线）**：只读证据脚本 `docs/regression_2x/phase5c_*.py`、
报告 `PHASE5C_REPORT.md`、断点卡 `PHASE5C_CHECKPOINT.md`、`RUNBOOK.md` §4i、`KNOWN_ISSUES.md` #32–#37。

**回归**：套件 **43/43 rc=0（FAILED: []）**；批次 **23/24 as_expected**（唯一非预期项 = 依赖真实网络的
`phase2e_real_provider`，本轮 Wikimedia TLS 握手超时 `PROVIDER_TIMEOUT` → 与冻结的 `PENDING（环境）` 一致，
**未改写其状态**）；3-A **16/16 PASS**；3-B 两脚本 rc=0；4-A/4-B/4-C/4-D/4-E/4-F/4-G/5-A/5-B 证据脚本全部 rc=0。
5-A/5-B 等**冻结证据日志在回归后已原样恢复**（`logs_5b_frozen/` 备份 + 逐文件哈希校验 → **drift 0**），
本轮结果另存 `logs/phase5c_rerun/`。基线：`5.x-phase5c-baseline`（零漂移 MATCH，见 `docs/regression_2x/BASELINE_README.md`）。

## V2.5.2-Phase5B 多模态候选生成（只生成候选，人审闭环）（2026-09-16）

**范围**：5-B —— 基于 5-A 的三态判定与视觉证据，为 **MISMATCH/低置信**镜头生成**可解释候选**；
**只生成候选**：不自动选材、不自动替换、不自动 redo、不写库、不写生产产物；生产变更仍走 4-C 的
「人工确认 → `select-candidate` → decision/changelog → redo」闭环（本阶段**未调用**这些写入口）。
**未进入 5-C**；许可闸门、append-only、版本链、attribution 1:1、HITL 均未改动。

**新增（2 个源码 + 1 个测试 + 1 个证据脚本）**：
- `src/video_studio/core/mm_candidates.py`：候选池归一（`verified=True` 且**本地存在**）、`asset_id`（`asset_+sha256[:12]`）、
  许可机械判类与门禁结论、**视觉证据**（同一 CLIP 模型对候选图片按 12 域打分）、期望域相似度、资格判定与**排除原因码**
  （`LOW_VISUAL_SIM` / `LICENSE_NOT_CLEAR` / `CURRENT_ASSET` / `USED_BY_OTHER_SCENE`）、候选清单与报告。
- `src/video_studio/ops/mm_candidates.py`：**只读**编排（`mode=ro` → 5-A 判定 → 候选池 → CLIP 打分 → 报告 +
  人工确认命令**文本**）。
- `tests/mm_candidates_test.py`（新，**29/29**）：默认关闭/配置、纯函数资格判定、**真实 S04/S06 回归**、
  三类路径、fail-closed、只读与确定性、历史证据保留。
- `docs/regression_2x/phase5b_evidence.py`（新，docs 不入基线）：真实候选证据 + 三路径 + 4-C 交叉核对 + 只读/确定性。

**修改（1 个文件，加法）**：`src/video_studio/cli.py` 新增只读子命令 `run.py mm-review <pid> [--json] [--artifact] [--out]`
（与 `report`/`metrics`/`semantic-check`/`rhythm`/`multimodal-check` 同列，**不经过** `build_engine()`）。

**真实回归（S04/S06）**：在 4-B 真值 + 5-A MISMATCH 的冻结产物 `a_2ed5f41d6b58` 上，两个镜头均
**`CANDIDATES_READY`**，各 3 条合格候选（`Meta Quest 3 side View.jpg` **0.2886**、`front View.jpg` **0.2817**、
`Visitor…` **0.2788**，全部 `FREE_ATTRIBUTION` 且来源可溯）；当前鲨鱼素材被排除并给出
`CURRENT_ASSET; LOW_VISUAL_SIM(0.1628<0.22)`；候选**包含 4-C 历史人工选定的素材**（S04→`asset_4f49f4c7edd0`、
S06→`asset_edece2b357f1`）→ 与历史闭环一致。

**三条路径**：① 有合格候选 → `CANDIDATES_READY`；② 无合格候选（空池）→ **`BLOCKED/MMC_NO_CANDIDATES`**；
③ 许可不合格（仅 `fair use` 素材）→ **`BLOCKED/MMC_NO_LICENSED_CANDIDATE`**（附 `excluded_reasons`）；
另覆盖模型不可用 → `UNKNOWN/MMC_MM_UNAVAILABLE`、期望域推不出 → `UNKNOWN/MMC_UNKNOWN_DOMAIN`（均零候选、不猜测）。

**只读与确定性**：运行前后真实 DB 字节未变、五张表行数（含 `decisions`/`changelog`）未变、
项目 74 个文件（含 5 个成片）逐字节未变；两次运行报告逐字节一致；`select_candidate_called=0`、`redo_triggered=0`。

**回归**：套件 **43/43 rc=0（FAILED: []）**；批次 **24/24 as_expected（非预期 0）**；3-A **16/16 PASS**；3-B **32/32 + 12/12**；
4-A **18/18**、4-B **29/29**、4-C **18/18**、4-D **55/55**、4-E **35/35**、4-F **48/48**、4-G **34/34**、5-A **34/34**。
**2 项 Wikimedia 真实网络项仍记 `PENDING（环境）`（状态与期望值未改）**。

**登记**：授权书基线文件名笔误（`svg5.x-…`）已在报告 §0 与 `KNOWN_ISSUES.md` #31 如实登记（按 SHA256 判定为同一基线）。

## V2.5.1-Phase5A 多模态语义验证器（真实视觉模型 CLIP，只读）（2026-09-16）

**范围**：只做 5-A —— 引入**真实视觉模型**对「旁白/镜头语义 ↔ 实际画面」做**只读**验证；
输出 `MATCH/MISMATCH/UNKNOWN` + 证据/置信度/模型版本/输入指纹；**保留 4-B 结果**（不覆盖、不删除，作为新增证据层）；
不自动改选材/时间轴、不自动 redo、不写生产决策；**默认关闭**；不可用/超时/解析失败一律 `UNKNOWN`（fail-closed，禁止伪造）。
**未进入 5-B/自动换材。**

**新增（3 个源码 + 1 个测试 + 1 个证据脚本）**：
- `src/video_studio/core/multimodal.py`：配置（缺省关闭）、期望域推导（4-B 词表为主 / 4-E 检索词典回退，
  拉丁形式**按词边界**命中，修正 `car`⊂`Cardboard` 类缺陷）、抽帧计划、三态判定规则、worker 调用与 fail-closed 码表、报告组装。
- `src/video_studio/core/mm_worker_clip.py`：**真实 CLIP worker**（本地权重 `clip-vit-base-patch32`，离线 CPU 单线程，
  `.venv_tts` 的 torch 2.13.0+cpu / transformers 4.57.6）——只返回相似度与版本信息，不编造结果。
- `src/video_studio/ops/multimodal.py`：**只读**编排（`mode=ro` 读库 → ffmpeg 抽帧到临时目录 → 判定 → 人读/JSON 报告）。
- `tests/multimodal_test.py`（新，**34/34**）：默认关闭/配置、纯函数规则、**真值回归**、明确 MATCH/MISMATCH/UNKNOWN、
  fail-closed 四例、确定性、只读、不覆盖 4-B、模型与输入指纹。
- `docs/regression_2x/phase5a_evidence.py`（新，docs 不入基线）：两版成片证据 + **4-B 并列对照** + 确定性/只读/fail-closed。

**修改（1 个文件，加法）**：`src/video_studio/cli.py` 新增只读子命令 `run.py multimodal-check <pid> [--json] [--artifact] [--out]`
（与 `report`/`metrics`/`semantic-check`/`rhythm` 同列：**不经过** `build_engine()`，无副作用）。

**真实模型与判定**：CLIP ViT-B/32（权重 sha256 `a63082132ba4f97a…`、config `b575ef3c36f2a057…`，快照 `3d74acf9a28c…`）；
每镜头按窗口 25/50/75% 抽 3 帧，对 12 个语义域的英文提示词打分 → 期望域（旁白词表推导）是否就是画面最像的域：
`expected_sim ≥ 0.20` 且领先 ≥ `0.02` → MATCH；被反超 ≥ `0.02` → MISMATCH；其余 → UNKNOWN（`MM_LOW_SIGNAL`/`MM_AMBIGUOUS`）。

**真值回归（授权第 6 项）**：在 **4-B 真值钉定的冻结产物 `a_2ed5f41d6b58`** 上，多模态层独立判出
**S04 MISMATCH（Δ=−0.0574，画面像 wildlife）与 S06 MISMATCH（Δ=−0.0381）**，与 4-B 的 `R3_DOMAIN_DISJOINT`/`R2_SENSE_CONFLICT`
**6/6 判定方向完全一致**；当前修复后成片（v5）多模态 **MATCH=5 / UNKNOWN=1（S05 边际不足 0.0175<0.02）**、
4-B `MATCH=6`（方向一致、本层更保守）。

**只读与不覆盖 4-B**：运行前后真实 DB 字节未变、五张表行数未变、项目 74 个文件（含 5 个成片）逐字节未变；
4-B 词表（sha256 前缀 `083e8d55c9899706`）与真值钉定未改；报告声明 `overwrites_4b_results=false`、`writes_to_db=false`；
源码静态检查无写库/写产物/调度器/redo 路径。

**回归**：套件 **42/42 rc=0（FAILED: []）**；批次 **24/24 as_expected（非预期 0）**；3-A **16/16 PASS**；3-B **32/32 + 12/12**；
4-A **18/18**、4-B **29/29**、4-C **18/18**、4-D **55/55**、4-E **35/35**、4-F **48/48**、4-G **34/34**。
**2 项 Wikimedia 真实网络项仍记 `PENDING（环境）`（状态与期望值未改）**。

## V2.4.7-Phase4X 4.x 最终收口与审计（2026-09-16，**无产品代码改动**）

**范围**：4.x Final Consolidation / Audit —— 对照 4.x 总 DoD 逐项审计 4-A～4-G、全量回归、冻结底座审计、
LRA 语义判定、4-G 只读复核、网络 PENDING 诚实性核查、最终文档/台账/DoD 矩阵与基线。**不进入 5.x、不做 UI。**

**本轮结论：`PASS WITH FOLLOW-UP`**（详见 `docs/regression_2x/PHASE4X_FINAL_AUDIT.md`）。

**关键审计发现（LRA 语义，授权第 5 项）**：`TARGET_LRA = 11` 是 ffmpeg `loudnorm` 的**目标参数** +
契约字典的**参考/复现值**，**不是硬门槛** —— 证据：① `check_contract()` 源码无 LRA；
② 把实测 LRA 设为 99 LU 或 0.5 LU，闸门结论都不变；③ 硬门槛只有集成响度 -16±1 LU 与真峰 ≤ -1.5 dBTP。
实测：4-C v5 成片 **LRA 2.0 LU**；4-F 含 BGM 预混输入 **18.30 LU** → 两遍母带后与交付成片 **13.8 LU**。
**故 4-F 的"LRA≈18"与 `LRA=11` 之间不存在违约；本轮未修改音频链、未改契约常量。**

**本轮仅文档级修正（无代码/契约变更）**：`docs/RUNBOOK.md` 新增 §4f（LRA 语义）；
`docs/KNOWN_ISSUES.md` 新增 4.x 小节 #14–#22（含 LRA 门槛策略待决策 #15、两遍母带方法 #16、
缓存新鲜度 #17、词典覆盖 #18、节奏阈值 #19 等）；`PHASE4F_REPORT.md` §6 更正"LRA 记录在 audio_loudness 证据中"
的不准确表述；新增 `docs/regression_2x/PHASE4X_FINAL_AUDIT.md`（DoD 矩阵 + 冻结底座审计 + 证据索引）。

**审计证据（可复算）**：`python docs/regression_2x/phase4x_audit.py` →
`logs/phase4x_audit.json`（LRA 审计 / 冻结底座逐字节对比 / 4-G 只读复核 / 网络 PENDING 核查）。
冻结底座（4.x 起点对比，字节 sha256）：`config/config.json`、`db/schema.py`、`core/materials.py`、
`core/narration.py`、`core/semantics.py` + `semantics_v1.json`、`agents/voice/agent.py` **逐字节未改**；
其余改动文件均为**加法/默认关闭**（无函数被删除，逐条登记在 `logs/phase4[acdefg]_change_list.json`）。

**回归**：套件 **41/41 rc=0（FAILED: []）**；批次 **24/24 as_expected（非预期 0）**；3-A **16/16 PASS**；
3-B **32/32** + **12/12**；4-A **18/18**、4-B **29/29**、4-C **18/18**、4-D **55/55**、4-E **35/35**、4-F **48/48**、4-G **34/34**。
**4-G 复核**：11 条建议全部 `status=SUGGESTION/applied=false/executed=false`、`applied_changes=0`、
DB/行数/74 个项目文件未变。**网络 PENDING**：`STATUS.md` 基线内 11 条 PENDING 记录**全部保留**（仅追加本轮观察），
本轮网络用例 rc=0 **仅作观察**，历史验收状态与期望值**未改写**。

## V2.4.6-Phase4G 只读节奏分析与人工建议（2026-09-16）

**范围**：只实现**只读**节奏分析与人工建议；**不**自动改时间轴/镜头时长/旁白/素材/BGM、**不**自动 redo、
**不**自动语义改选材；保持 3.x 时间轴权威时长、旁白完整性、响度契约与 4-A～4-F 逻辑不变；不改数据库结构。

**新增（2 个源码 + 1 个测试 + 1 个证据脚本）**：
- `src/video_studio/core/rhythm.py`（新，纯函数、只依赖标准库）：`rhythm-advisor-v1` 分析器 —— 10 条规则
  （镜头过短/过长、旁白段落过短/过长、切换落在旁白句中、切换密度过高/过低、旁白超时轴被裁、
  可疑静态画面持续、BGM duck 碎片化）+ 6 类 `UNKNOWN`（时长缺失/旁白不可用/素材类型未知/成片时长缺失/
  旁白总时长缺失/BGM 未生效）；**无法判断时只记 UNKNOWN，不给建议**；阈值可由 `tools.rhythm` 覆盖（默认见下）。
- `src/video_studio/ops/rhythm.py`（新，只读）：`readonly_connection`（`mode=ro`）+ 读取既有
  `render_output`/`voice_output` → 组装输入 → 调用分析器；输出含**输入指纹**（产物 id + sha256），可复算。
- `tests/rhythm_advisor_test.py`（新，**34/34**）：正常/过短/过长/边界异常/BGM 关·开/空旁白·异常时长/无法判断/
  确定性/只读验证/五项显式证明。
- `docs/regression_2x/phase4g_evidence.py`（新，docs 不入基线）：场景矩阵 + 真实项目只读报告 + 只读与确定性证明。

**修改（1 个文件，加法）**：`src/video_studio/cli.py` 新增只读子命令 `run.py rhythm <pid> [--json] [--artifact]`
（与 `report`/`metrics`/`semantic-check` 同列：**不经过** `build_engine()`，无任何副作用）。

**默认阈值**：`min_scene_s=3.0`、`max_scene_s=20.0`、`static_warn_s=15.0`、`min/max_cuts_per_min=2/12`、
`narration_boundary_tolerance_s=0.5`、`narration_seg_min/max_s=4/30`、`bgm_duck_transitions_warn=2`。

**每条建议包含**：`scene_id`、当前时长、触发规则、具体证据（实测值/阈值/差值或时间窗）、建议动作、风险与限制、
置信度（HIGH/MEDIUM）；`status=SUGGESTION`、`applied=false`、`executed=false`、`requires_human_decision=true`；
报告级 `applied_changes=0` 与 `policy`（不写库/不写产物/不改时间轴·时长·旁白·素材·BGM/不触发 redo/不绕过 HITL）。

**真实项目实测（`p_f4b466a4a024`，只读）**：成片 104.0s / 6 镜头 / 5 次切换（2.885 cuts/min）/ 旁白 112.728s（6 段）→
**11 条建议、0 条 UNKNOWN**：6× `R_CUT_MID_NARRATION`（切换落在旁白句中，tail_s 2.8–8.7s）、
3× `R_STATIC_HOLD`（20/20/25s 单张静态素材）、1× `R_SCENE_TOO_LONG`（S04 25s > 20s）、
1× `R_NARRATION_TRIMMED`（旁白 112.728s > 成片 104s，超 8.728s 被契约裁剪）；BGM 关闭 → 无 BGM 建议。

**只读与确定性证明**：真实 DB 字节与 `tasks/artifacts/events/decisions/changelog` 行数在运行前后**完全一致**；
项目内 74 个文件（含 5 个成片）逐字节未变；只读连接写入被 SQLite 拒绝（`OperationalError`）；
`run.py rhythm --json` 多次运行输出**逐字节一致**；代码静态证明不含写库/写产物/调度器/redo 调用路径。

**回归**：套件 **41/41 rc=0（FAILED: []）**；批次 **24/24 rc=0（非预期 0）**；3-A **16/16 PASS**；3-B **32/32** + **12/12**；
4-A **18/18**、4-B **29/29**、4-C **18/18**、4-D **55/55**、4-E **35/35**、4-F **48/48**。
**2 项 Wikimedia 真实网络项仍记 `PENDING（环境）`（状态与期望值未改）**。

## V2.4.5-Phase4F 可选 BGM + 旁白 ducking（2026-09-16）

**范围**：只做**可选 BGM + 旁白 ducking**；BGM 默认关闭；不做节奏自动改时长、自动语义改选材、第二 Provider、
UI/自动发布/5.x；不改数据库结构；**BGM 失败一律 fail-closed，不静默降级为未声明的音频输出**。

**新增（2 个代码/测试文件 + 1 个证据脚本）**：
- `src/video_studio/core/bgm.py`（新）：开关（默认关闭）、BGM 全量校验（来源/sha256/音频流/解码/时长/响度/
  静音/异常响度/**许可门禁**/**attribution 必填**）、ducking 规则（旁白时间段由 voice 逐段真实时长累加；
  期间 `duck_db`、之外 `bed_db`、边界 `ramp_ms` **线性**过渡、提前 ramp 进入 duck、重叠区间合并）、
  混音片段构造（`amix normalize=0` 保证旁白电平不变；过长 `atrim`、过短 `apad`）。
- `tests/bgm_ducking_test.py`（新，**48/48**）：A 默认关闭 / B ducking 规则 / C 十一类校验 /
  D 引擎级渲染（关闭·过长·过短·静音被拒·受限许可被拒）/ E ducking 实测 / F 契约 / G credits 一致性。
- `docs/regression_2x/phase4f_evidence.py`（新，docs 不入基线）：证据收集。

**修改（2 个文件）**：
- `src/video_studio/agents/editing/agent.py`（**加法 + 默认关闭**）：渲染前 BGM 校验闸门（失败 → `TASK_BLOCKED`
  + `[BGM_REJECTED] <code>`，**不调用 ffmpeg**）→ 预混（旁白 + 带包络的 BGM）→ BGM 路径两遍母带 →
  交给**原有**渲染分支；`render_output` 新增 `bgm` 证据块，`attribution` 新增 `bgm` 与 `audio_config`，
  credits 增加 BGM 段（**仅开启时**）。
- `src/video_studio/core/audio.py`（**纯加法**）：新增 `measure_loudnorm_input()` 与 `normalize_two_pass()`
  （仅 BGM 路径使用）；`measure_loudness` / `check_contract` / `mastering_chain` / `enforce_loudness_on_film`
  **一字未改**。

**为什么需要两遍母带（工程事实，如实记录）**：含 BGM 的混音动态更大（LRA≈18 LU），**单遍动态** loudnorm
实测只到 **-19.5 LUFS**（偏差 3.5 LU > 既有 3 LU 收尾校正上限 → 按契约 fail-closed）；改为**两遍线性**
loudnorm（同一契约常量 `-16 / TP -1.5 / LRA 11`）后实测 **-15.9 LUFS / TP -8.0 dBTP**。BGM 关闭时**不启用**该路径。

**十条路径**：关闭 / 开启且合规 / 缺失 / 校验失败 / 许可不明或受限 / 重叠 ducking / 结束恢复 /
过长·过短·静音·异常响度 / 渲染失败 fail-closed / attribution·credits 一致 —— **全部有实测证据**
（`logs/phase4f_bgm_evidence.json`）。ducking 实测深度 **6.0 dB**（旁白期间 -57.1 dB vs 之外 -51.1 dB），
旁白窗口电平与旁白单独**完全一致**（-33.1 dB vs -33.1 dB）。

**回归**：套件 **40/40 rc=0（FAILED: []）**；3-B **32/32** + 失败路径 **12/12**；批次 **24/24 rc=0（非预期 0）**；
3-A **16/16 PASS**；4-A **18/18**、4-B **29/29**、4-C **18/18**、4-D **55/55**、4-E **35/35**。
**2 项 Wikimedia 真实网络项仍记 `PENDING（环境）`（状态与期望值未改）**。

## V2.4.4-Phase4E 检索质量量化与改进（2026-09-16）

**范围**：只做检索质量量化（固定测试集 + 中文/多语言 A/B 基准 + TP/FP/UNKNOWN 指标），**不做自动改选材**；
不接第二 Provider、不做 BGM/UI/节奏/自动发布、不改数据库结构、不改 4-B 真值 `a_2ed5f41d6b58`、
不改 4-D 的缓存/重试/fail-closed 行为、默认 `provider=none` 与默认检索行为不变。

**新增（4 个文件）**：
- `src/video_studio/core/retrieval_quality.py`（新）：分词 v2（复数归一 / 中文去虚词单字 / **保留 2 字符缩写** vr·hmd）、
  **词边界**拉丁匹配（防 `es`⊂`Azores` 碎片桥）、概念扩展打分 `score_v2`、zh→en 查询扩展 `expand_query_latin`、
  指标计算 `evaluate`/`ab_compare`（TP/FP/UNKNOWN/FN + precision/domain_hit/top1/empty_correct）、
  配置读取 `retrieval_settings`（缺省 = v1 + 不扩展）；v1 打分器**直接 import 既有实现**（未复制改写）。
- `src/video_studio/core/lexicons/retrieval_synonyms_v1.json`（新）：12 概念对齐 4-B 的 12 个语义域，
  中英（含少量西语）表面形式 + **歧义形式登记**（pico/quest/galaxy…）→ 歧义命中在评测中记 UNKNOWN。
- `tests/retrieval_bench_v1.json`（新，**入基线**）：固定测试集 = 23 条素材名称语料（标注域 + 人工可解释 label_basis，
  区分 `real_*` / `label_only`）+ 21 条查询（zh/en/syn/weak/none/amb 六组）+ k=5。
- `tests/retrieval_quality_test.py`（新，**35/35**）：词典/分词/词边界、v1 缺陷证据、A/B 数值冻结断言、
  分组结果、无结果与歧义行为、**不绕过** 4-B·许可·素材校验、默认行为与离线复算。

**修改（1 个文件，加法 + 默认关闭）**：`src/video_studio/agents/retrieval/agent.py`
（读 `tools.retrieval.scoring|query_expansion`；缺省 v1/不扩展 = 既有行为；启用扩展时 provider 侧关键词同步重算；
检索产物新增加法字段 `retrieval_config`）。

**A/B 结果（固定测试集，数值已冻结进套件断言）**：

| 指标 | A（v1 冻结） | B（v2 改进） |
|---|---|---|
| TP / FP / UNKNOWN | 19 / 39 / 10 | **43 / 18 / 10** |
| `precision_strict` | 0.2794 | **0.6056** |
| `domain_hit_rate` | 0.6875 | **1.0** |
| `top1_correct_rate` | 0.5625 | **1.0** |
| `empty_correct_rate` | 0.6667 | **1.0** |
| 中文组（zh）域命中 | 0.40（TP 3） | **1.00（TP 14）** |
| 无结果组假匹配 FP | 4 | **0** |
| 歧义组 | UNKNOWN 10、TP 0 | UNKNOWN 10、TP 0（**不把歧义洗成正确**） |

**发现的既有缺陷（可复现证据）**：v1 的 `kw_tokens` 对去空格文本取 `set()`，**拉丁文本贡献单字母**、
中文贡献单字，产生字符级假匹配（`score_v1("Meta Quest 3 front View.jpg","zzzq 不存在的主题内容")==1`，
命中字母 `q`）；且中文查询无法命中英文命名语料（`zh_02/zh_03/zh_05/en_02` 出现 0 候选 FN）。
v2 通过"词典概念对齐 + 词边界匹配 + 2 字符缩写保留"把 FN 降到 0、FP 由 39 降到 18。

**真实网络佐证（环境相关，仅记录）**：3 条中文查询在 Wikimedia Commons 上，原查询形状 `cjk_only` → **0 候选**，
加 4-E 扩展词后 → **各 8 候选**（含目标素材；同时如实记录伪友 `Picea glauca` 与域内泛化案例）。

**门禁不绕过（引擎级断言）**：启用 v2 + 查询扩展后，中文查询能检索到英文命名素材并通过全量校验（`external_verified=1`），
但同批的 `fair use` 素材仍被拒（`ASSET_LICENSE_RESTRICTED`）、截断文件仍被拒（`ASSET_TRUNCATED`）；
检索层**不导入** `core.semantics`、不产出语义 verdict；4-B 词表与其真值钉定**未改动**。

**回归**：套件 **39/39 rc=0（FAILED: []）**；批次 **24/24 rc=0（非预期 0）**；3-A 真实链路 **16/16 PASS**；
3-B **32/32** + 失败路径 **12/12**；4-A **18/18**；4-B **29/29**；4-C **18/18**；4-D **55/55** 且八条路径 fail-closed 8/8。
**2 项 Wikimedia 真实网络项仍记 `PENDING（环境）`（状态与期望值未改，仅记录本轮实测通过）**。

## V2.4.3-Phase4D 供给韧性底座（2026-09-16）

**范围**：只做供给韧性的**最小增量**——供给缓存、限流/超时分类、失败可解释、可控降级；
不接第二 Provider、不做 BGM/UI/节奏自动改时长/自动发布、不改数据库结构、不改冻结契约。

**新增（3 个文件）**：
- `src/video_studio/core/supply.py`（新，纯函数/离线/只读）：失败分类表（**32 个既有错误码** →
  `TRANSIENT`/`PERMANENT`/`POLICY`/`LICENSE`/`UNKNOWN` + 是否可重试 + 处置动作；未登记码一律 `UNKNOWN` 保守处理）、
  有界确定性重试计划 `retry_decision()`（**无随机抖动**，429 线性 10/20/30s、其它 0.2s 线性且 ≤2s、
  `Retry-After` 只在 30s 上限内采纳）、供给缓存 `SupplyCache`（**只存候选元数据**，TTL/损坏/schema/策略指纹全处理）、
  可控降级阶梯 `degradation_plan()`（EXTERNAL_VERIFIED → LOCAL_INGEST → THEME_FALLBACK →
  SOLID_COLOR_CARD → BLOCKED_FOR_HUMAN + 三条不变量）。
- `src/video_studio/tools/supply.py`（新）：`ResilientSupply` façade（搜索缓存 / 逐候选失败归类 / 结构化
  `report()`），`verified_only()` 是**唯一**允许进入素材池的出口；缓存恢复出的候选一律重置为
  `status=CANDIDATE / download_status=NOT_DOWNLOADED / license_cleared=False`——**缓存无法提升素材可信度**。
- `tests/supply_resilience_test.py`（新，**55/55**）：A 分类表 / B 重试计划 / C 缓存 / D 八条路径 /
  E 降级阶梯 / F 引擎级 fail-closed 与不污染 / G 默认配置不变。

**修改（2 个文件，均为加法）**：
- `src/video_studio/tools/material_provider.py`：`TransportError` 增加可选 `retry_after_s`；`UrllibTransport`
  在 429 时解析 `Retry-After`（上限内采纳）；下载重试判定/退避改由 `core.supply.retry_decision` **统一给出**
  （默认策略下与 2-D/2-E **逐值一致**）；`DEFAULT_POLICY` 增加 3 个开关
  （`supply_cache=False`、`supply_cache_ttl_s=900`、`retry_after_max_s=30`）。
- `src/video_studio/agents/retrieval/agent.py`：外部候选获取外层包 `ResilientSupply`（缓存 + 分类 + 诊断），
  检索产物新增**纯加法**字段 `external_provider.supply` / `external_provider.supply_report`。
  候选是否入池的判定**未改**（仍由 `verify_material` + 许可门禁给出）。

**默认行为不变（可核对）**：`tools.material.provider` 仍为 `none`；供给缓存**默认关闭**；
`config/config.json` 逐字节未改（sha256 `b264644539b2adbb…` 与基线 manifest 一致）；
下载重试次数（1+max_retries）与退避值不变；**未**新增数据库表/列；**未**改动 4-A/4-B/4-C 判定逻辑与阈值。

**验证结论**：八条路径（正常 / 缓存命中 / 429 / 超时 / 空候选 / 下载失败 / 校验失败 / 许可不明）**全部 fail-closed**；
引擎级 429 与超时 → render `BLOCKED`、无成片、无 `render_output`/`attribution` 产物；
既有项目文件逐字节未变、任务/产物/事件计数不变、`decisions`/`changelog` 零新增、真实 `projects/video_studio.db` 字节未变；
套件 **38/38 rc=0（FAILED: []）**；回归批次 **24/24 rc=0（非预期 0）**；3-A 真实链路 **16/16 PASS**（S05 仍 0.355）。

## V2.4.2-Phase4CFix 4-C 收尾修复：S05 复用连带 MISMATCH（2026-09-16，**无代码改动**）

**问题（4-C 审阅发现）**：4-C 首轮人工替换 S04/S06 后，`asset_reuse_policy=prefer_unused` 把"被释放的鲨鱼照"
确定性路由给 **S05** → 语义 `MISMATCH` 由 S04/S06 **转移**到 S05（计数 2 → 1，未归零）。

**修复方式（人工决定，非自动）**：经 `run.py review` 展示 S05 候选池（3 个已验证/许可清晰的 VR 素材 +
当前鲨鱼照；其余 6 个候选因 `ASSET_OVERSIZE`/429 被拒不可选），由人工明确选定
**`asset_f3cf2b80432d`（Meta Quest 3 side View.jpg）**：
- `decisions`：`d_a683da3c5d3b`（`node=selection_override`、`state=approved`、`made_by=human:project-owner`）
- `changelog`：`#820`（`human_confirmed=1`）
- 生效：`run.py redo t_1dbf3c1bc6f7` → render **v5 `t_b8f866ddc062`**（v1–v4 全部保留，append-only/version+1）

**结果**：语义核验（4-B，对 v5 成片）**`MATCH=6 / MISMATCH=0 / UNKNOWN=0`** —— S05 的 MISMATCH **消除**；
**未出现新的连带问题**：与上一版相比**仅 S05 变化**，鲨鱼素材 `asset_28160d959ed5` 被释放且**未被任何镜头接管**，
三个 VR 素材复用计数均衡为**各 2 镜**；复核队列待办 **0**。
新成片 `t_b8f866ddc062_draft.mp4`：h264+aac / **104.000s** / 响度 **-16.1 LUFS、TP -2.7 dBTP**（达标）/
逐镜头抽帧 **6/6 在屏 0 失败**（S01 0.459、S02 0.921、S03 0.348、**S04 0.472**、**S05 0.355**、**S06 0.919**）。

**本修复为纯数据/决定变更：代码增量 = 修改 0 / 新增 0 / 删除 0**（`baseline_delta.py` 实测；文件级差异仅
`CHANGELOG.md`、`STATUS.md` 两处**文档登记**）。未改数据库结构、未改 4-A/4-B 判定逻辑与任何冻结契约、未自动选材。

**回归（代码未变，已按修复后的产物重跑）**：套件 **37/37 rc=0（FAILED: []）**；3-B 契约 **32/32**、
失败路径 **12/12**；4-A（含 `provider=none` 证据）**18/18**；4-B 真值 **29/29**（仍钉在 3-A 冻结产物）；
4-C 机制 **18/18**；3-A 关键断言 **16/16 PASS**。2 项 Wikimedia 真实网络回归**仍记 `PENDING（环境）`（状态未改）**。

**未做**：未进入 4-D/4-E/4-F；未接第二 Provider；未做 BGM/UI/节奏自动改时长/Git tag。

## V2.4.1-Phase4C 人审候选替换闭环（4.x，2026-09-15）

**授权范围**：只做"人工明确选定 → 既有 redo 生效"的闭环；不自动改选材、不接第二 Provider、不做 BGM/UI、
不改数据库结构、不改 4-A/4-B 判定逻辑与冻结契约。

**实现（复用既有机制，不新增表/列）**：
- `core/selection_review.py`（新）：人工选定校验（候选池成员 / 可用性 / 许可门禁，直连 `core.materials`
  既有规则，**未修改**任何门禁逻辑）+ `decisions` 行构造 + 只读读取"每镜头最新一条已批准选定"。
  错误码：`HUMAN_SELECTION_EMPTY_POOL` / `_NOT_IN_POOL` / `_UNUSABLE` / `_LICENSE_BLOCKED` /
  `_NO_REVIEWER` / `_NO_REASON`。
- `ops/selection_review.py`（新）：`review_queue()` 只读复核队列（候选池 + 许可/验证状态 + 已拒候选 +
  必须 BLOCKED 标记）与 `record_selection()`（先只读校验，通过后才写 **既有** `decisions` + `changelog`
  （`human_confirmed=1`）；失败则**不写任何东西**）。
- `cli.py`（改）：新增 `review`、`select-candidate` 两个子命令（与其他只读命令一样不经过 `build_engine()`）。
- `agents/editing/agent.py`（改）：渲染侧**只读**消费人工选定 → 选中即为 `selection_source="human_review"`，
  写 `human_selection{decision_id,decided_by,reason,decided_at}`；**校验不过即 fail-closed**（`TASK_BLOCKED` +
  `MaterialInsufficientError`），**绝不静默回退**到自动选材。

**真实替换（项目 `p_f4b466a4a024`，人工决策者 `human:project-owner`）**：
S04 鲨鱼照 → `Visitor using a Meta Quest 3 VR headset…`（decision `d_a74b1d9f5ab6` / changelog #798）；
S06 鲨鱼照 → `Meta Quest 3 front View.jpg`（decision `d_9a7600dfeebf` / changelog #799）；
经 `redo t_b7a62ec8e29a` 产生 **render v4 `t_1dbf3c1bc6f7`**（v1–v3 全部保留，append-only）。
新成片：**104.000s / h264+aac / 响度 -16.1 LUFS、TP -2.7 dBTP（达标）/ 抽帧 6/6 且在屏
（S04 corr 0.472、S06 0.919）/ attribution ⟷ 新时间轴逐条 1:1（6 条）**；3-A 关键断言复核 **16/16 PASS**。

**连带效应（如实记录，未自动处理）**：`asset_reuse_policy=prefer_unused` 使"被释放的鲨鱼照"被确定性路由到
**S05**（原用 Visitor 图，该图现被 S04 占用）→ 语义 `MISMATCH` 由 S04/S06 转移到 S05（MISMATCH 2 → 1）。
这属策略后果而非自动改选材；**未**自动再处理，需人工再下一条决定（机制已就绪：`review` → `select-candidate` → `redo`）。

**测试**：新增 `tests/human_selection_test.py` **18/18**（无人工决定行为不变 / 人工选定生效 / 池外与不可用
fail-closed / 池空 BLOCKED / 投影键一致 / 台账 1:1 / 只动 decisions+changelog / 缺 --by 与 --reason 拒绝）。
顺带修复：`latest_selections_from_conn` 原用列名索引（普通连接会静默返回空）→ 改为位置索引（由测试 H2c 抓到）。

**未做（授权边界）**：第二 Provider、BGM、UI、自动语义改选材、节奏自动改时长、Git tag、数据库结构变更、
4-A/4-B 判定逻辑与 Claim/HITL·append-only·redo·时间轴权威时长·旁白完整性·响度契约·素材验证·许可台账均未改动。
**未进入 4-D/4-E/4-F。** 2 项 Wikimedia 真实网络回归仍为 `PENDING（环境）`，状态未改。

## V2.4.0-Phase4AB 只读质量指标 + 离线三态语义核验（4.x 第一阶段，2026-09-15）

**授权范围（4-A + 4-B）**：只允许新增只读 metrics 与离线只读三态语义验证器；不得接第二 Provider、
不得改默认配置与冻结契约、不得自动改选材/改成片、不得改数据库结构。

**4-A 只读质量/成本指标**（`src/video_studio/ops/metrics.py`；`python run.py metrics <pid> | --all`）：
候选有效率、上屏率与 corr、时长/响度契约、旁白完整性、外部素材**用量**（非计费）、LLM 成本**估算**（非账单）、
人工介入，以及语义核验三态计数。**确定性**：无时间戳、排序固定 → 同一数据两次运行**逐字节一致**（已断言）。
**只读**：`mode=ro` 连接（写入被 SQLite 拒绝）、不调用引擎、不派发任务、前后 DB sha256/行数不变。

**4-B 离线三态语义验证器**（`src/video_studio/core/semantics.py` + 知识库
`src/video_studio/core/lexicons/semantics_v1.json`；`python run.py semantic-check <pid>`）：
逐镜头输出 `MATCH` / `MISMATCH` / `UNKNOWN`，附**规则 ID**、**命中关键词/标记**、**共享词分类**
（词级桥 vs 拉丁 2 字符字面碎片）与域投票明细。判定为**类别式规则**（域交集 / 域不相交且无词级桥 / 同形词义冲突），
**没有任何数值阈值**（因此不存在"下调阈值凑通过"的空间）；无法判断一律 `UNKNOWN`，**绝不当作 `MATCH`**。

- **同形词义解析**：知识库对 `pico/quest/valve/index/apple/galaxy/surface/pixel/vision/rift/cardboard` 等
  词条登记"词义 + 语境标记"，按**整词/短语**匹配上下文判定词义（如 `pico` 在 `PICO 4` 语境=brand_xr，
  在 `Azores/islas/canal` 语境=place_nature）；无标记或并列最高 → `sense=None`（不猜）。
- **根因发现（写进报告）**：3-A 的 S04/S06 误选并非"品牌同形词"，而是匹配器 `kw_tokens` 的**2 字符字面碎片**
  （实测 `matched_tokens=["IP","Me","Qu","es","et","st","ta","ue"]`，`es` 落在 *Azores* 内部）——
  因此把"碎片桥不算语义支持"作为判据之一是必要的。

**新命令接线**：`cli.py` 新增 `metrics` 与 `semantic-check` 子命令（与 `report` 一样**不经过 `build_engine()`**，
无任何副作用）；非只读路径与默认配置 `config/config.json` **未改动**（sha256 与冻结基线 manifest 一致，已断言）。

**验收（授权指定真值表）**：3-A 项目 `p_f4b466a4a024` → **S04/S06 = MISMATCH（TP=2）**、
**S01/S02/S03/S05 = MATCH（FP=0）**、`FN=0`、`UNKNOWN=0`。判定规则分别命中 `R3_DOMAIN_DISJOINT`（S04）与
`R2_SENSE_CONFLICT`（S06），两条独立规则各抓一个。
**测试**：`tests/semantic_check_test.py` **28/28**（含确定性/离线（禁 socket 仍可运行）/只读/可解释性断言）、
`tests/metrics_test.py` **18/18**（含两次输出逐字节一致、`provider=none` 回归证据、与 `report` 口径一致）。

**未做/已知限制（如实登记）**：语义核验只**检测**不改片——3-A 成片中的 S04/S06 素材**仍在片内**
（替换属 4-C，未授权）；知识库 v1 覆盖有限（全库 294 镜头中 `UNKNOWN=168`，13 个历史镜头被标记 `MISMATCH`
但**无标注、仅待人工复核**）；lexicon 未收录 `keyboard` 等其它同形词（已用测试固定其观察行为）；
未实现 LLM 语义判定（优先离线确定性方案）；判定结果不落库（新增 artifact 类型未获授权）。

**未做（授权边界）**：第二 Provider、BGM、UI、节奏自动改时长、Git tag、自动改选材/生成替换候选、改数据库结构、
改 Claim/HITL·append-only·redo·时间轴权威时长·旁白完整性·响度契约·素材验证·许可台账。**未进入 4-C。**

## V2.3.0-Phase3C 最终运维与成本收口（3.x Final，2026-09-15，阶段判定 **PASS**）

**新增只读命令 `run.py report <project_id> [--json]`**：
- 实现 `src/video_studio/ops/report.py`（`build_report` / `format_report` / `readonly_connection`）；
  `cli.py` 新增 `report` 子命令，**不经过 `build_engine()`**（不建库、不建目录、不派发任务）；
- 内容：任务状态分布 + 待审批 + 未派发 / 失败与阻断原因（任务行 + 最近事件）/ 产物清单与关键产物指纹 /
  **成本（LLM，估算）** / **外部素材用量（非计费）** / 成片时长契约 / **响度实测（目标/误差/校正/原因）** /
  抽帧核验与上屏 / 旁白状态 / 署名台账 / 质检结论；
- **只读保证**：DB 以 `file:<db>?mode=ro` 打开（写操作抛 `OperationalError: readonly`）；
  实测 DB sha256/大小与六表行数在报告前后**完全不变**（连续 3 次仍不变）；不存在项目 → rc=2 且不崩溃。

**成本边界收口**（`docs/COST_BOUNDARY.md`、`docs/regression_2x/phase3c_cost_boundary.py`）：
- **口径 A（LLM，估算）**：全库任务行 `cost_usd` 合计 $71.57108（含 V1/V2 历史阶段：`deepseek-chat` $36 +
  `deepseek-reasoner` $35）；3.x 当前线（`deepseek-flash` + `deepseek-v4-pro`）合计 **$0.5711**；
  `LLM_CALL` 事件 **1,032 次 / 847,319 tokens**（in 302,598 / out 544,721），事件内成本合计 $0.544703
  ——与任务行**口径不同**（前者逐次调用记账、后者由 Agent 写入），**不是漏账证据**；单次运行完整性由
  `tests/cost_accounting_test.py` 的 `client.calls == LLM_CALL 事件数` 守卫断言。
- **口径 B（外部素材，用量非计费）**：请求 71（失败 0）、真实下载 **65,079,590 B**、**429 限流 144 次**、
  本地缓存 122 文件 / 78,921,883 B、**金额 $0.00**（Wikimedia 免费、无 key）。
- **口径 C（账户余额）**：免费只读接口；**零本地 LLM 调用**窗口内余额仍由 8.79 → 8.53 CNY（**-0.26**），
  而本地 `LLM_CALL` 与事件计数均未变 → 复现"余额变化不可归因于本地调用"。
- **Phase 1.1 残余 ≈¥3.24 的正式结论**：**`NOT_ATTRIBUTABLE_CLIENT_SIDE`**（估算差额；既不是账单，
  也不是台账算错；人民币依赖 7.1 的换算率）。候选原因：同一 key 被其它调用方使用 / 更早窗口仍在异步批量结算 /
  客户端不可观测的计价细节。**未修改任何数字去凑平**。

**运维手册与台账**：`docs/RUNBOOK.md`（正式入口；`resume` ↔ `redo retrieval` ↔ `redo render` ↔ 验证命令的区别；
真实 LLM/TTS/Provider/ffmpeg 前置条件；Wikimedia 429/超时/下载失败/域名不可达处理；常见失败与恢复；检索 0 命中排查）、
`docs/KNOWN_ISSUES.md`（**13 项**已知问题：S04/S06 语义误选、2-E 历史成片不可完全复原、`stage32b` +0.4 dB 补偿、
中文-only 查询命中率低、429 常态、本地素材不做许可门禁、响度契约可配置、成本仅估算、失败路径合成契约等；
全部标 `LIMITATION`/`BY DESIGN`/`ENV`，**无一项被改写为 PASS**）。

**顺带修掉的真实缺陷**：CLI 在管道/重定向下按 locale（本机 cp936）输出中文 → 外部按 UTF-8 读取乱码/解码失败；
已在 `cli.main()` 起始处把 `stdout/stderr` 固定为 UTF-8（`_force_utf8_io()`，异常安全）。属代码修复而非测试适配。

**回归（最终代码）**：**34/34 套件 rc=0**（新增 `report_command_test` **18/18**）；回归批次 **21/21 rc=0**
且分类判读**非预期结果 = 0**；3-A 真实链路复核 **16/16**；3-B 响度 **32/32** + 失败路径 **12/12**；
2-C 38/38、2-C 故障矩阵 A/C 出片 B/D BLOCKED、2-D 40/40 + 12/12、2-E 13/13 + 29/29、ingest PASS、
E2E A/B/C SETTLED、2-A/B 验收 PASS、真实小测 PASS（MockLLM=0）、二进制真实性 PASS。

**未做（授权边界）**：BGM、第二 Provider、语义自动改选材、自动发布、UI、Git tag、修改默认 `provider=none`、
Claim/HITL·append-only·恢复·任务/产物/event 契约、大规模重构、4.x 功能。**3.x Final 收口完成，STOP。**

## V2.2.6-Phase3B 音频响度契约统一与落地（2026-09-15，阶段判定 **PASS**）

**契约**（授权指定，单一事实源 `core/audio.py`）：成片 **-16 LUFS（±1 LU）**、**真峰 ≤ -1.5 dBTP**、
LRA 11；两条渲染路径（正式 Agent 链 + `stage32b`）共用同一条母带链
`loudnorm=I=-16:TP=-1.5:LRA=11` → `alimiter=limit=0.7079:attack=1:release=10:level=false`。

**审计（真实实测，`logs/phase3b_audit.json`）**：
- 正式 Agent 链此前**只做 `apad`、无任何响度处理** → 成片实测 **-19.7 LUFS**（2-E 项目成片 -22.0）；
- `stage32b` 有链但单遍 `loudnorm` 落在 **-17.7 LUFS**，且其 QC 断言是 `-18…-14`（±2 LU 旧口径）→ 从未发现；
- 音频 Agent 的 `audio_plan` 宣称 `-14 LUFS` + BGM 闪避，与实现/交付物**都不符**。

**落地**：
1. `core/audio.py`（新）：契约常量、`loudnorm_filter/limiter_filter/mastering_chain`（支持 `sample_rate`
   与 `post_gain_db`）、`measure_loudness`（真实 `ebur128=peak=true` 实测集成响度与真峰）、`check_contract`
   （测不到即不通过）、`verify_file`（证据块）、`contract_from_config`/`mastering_enabled_from_config`、
   `enforce_loudness_on_film`（成片级 fail-closed 强制）。
2. `agents/editing/agent.py`：母带链进入**所有脚本渲染分支**（多镜头 concat / 单背景 / 纯色底），
   并 `aresample` 复原输入采样率；渲染后实测成片 → 不达标 `TASK_BLOCKED` + `LoudnessContractError`；
   `render_output.audio_loudness` 记录目标/实测/误差/方法/链/校正次数/逐次尝试。
3. `agents/audio/agent.py`：方案目标值改由契约生成，如实标注"母带链在渲染阶段真实执行"与"BGM 未实现"。
4. `stage32b/{vo,render,qc}.py`：复用同一母带链；`qc` 响度断言由 **±2 LU 收紧为统一 ±1 LU**；
   render 对成片做同样实测（小残差收尾校正）。
5. `tools/ffmpeg_tool.py`：probe 新增 `sample_rate/channels`（纯新增字段）——采样率复原需要它。

**fail-closed 语义**：偏差 ≤3 LU → 允许 1–2 次**只重编音频**（`-c:v copy`，不改采样率/时长）的收尾校正；
**偏差 >3 LU → 拒绝静默校正、直接 BLOCKED**（大幅偏差意味着母带链没生效，静默修好会掩盖故障）；
测不到（无音轨/无 ffmpeg）同样不合格；不达标不写 `render_output`。

**真实测量证据**：3-A 真实项目（104.0s，真实 TTS + 真实 Wikimedia 素材）重渲染后
**I=-16.1 LUFS / TP=-2.7 dBTP（Δ -0.1 LU，corrections=0）**，音轨保持 aac 24000 Hz 单声道；
`stage32b` 交付成片重跑后 **-16.8 LUFS / TP -1.9 dBTP**，其 QC Gate PASS。

**测试**：新增 `tests/audio_loudness_test.py` **32/32**（契约原语 + 真实音频三向验证 + 成片强制语义 +
正式引擎渲染 + 故障注入）与 `docs/regression_2x/phase3b_failure_paths.py` **12/12**
（真实渲染：关母带链 / 不可能的真峰上限 / 真实静音旁白 → 全部 BLOCKED 且不交付成片）。

**本阶段修的真实缺陷（6 项）**：①正式链无响度处理；②`loudnorm` 输出 192 kHz 导致采样率被改
（测试 D9 抓到 film=96000 vs narration=24000）；③stage32b QC 口径过松；④`audio_plan` 与实现不符；
⑤我第一版"自动校正"会掩盖故障注入（改为 >3 LU 拒绝校正）；⑥测试首版就地校正了 2-E 历史成片
（已改为只操作副本，并用 `phase3b_restore_2e_film.py` 把其集成响度还原为 -22.0 LUFS；有损重编不可逆，
TP 由 -13.0 变 -3.5 dBTP 已如实记录）。

**未做（授权边界）**：BGM、第二 Provider、语义级改选材、UI、`run.py report`、成本对账、Git tag、
大规模重构、默认 `provider=none` 与 Claim/HITL/append-only/恢复/任务与产物/event 契约均未改动。**未进入 3-C。**

## V2.2.5-Phase3A 许可合规交付（署名台账）+ 真实链路端到端验收（2026-09-13/15，阶段判定 **PASS**）

**新增只读交付物**：渲染任务新增 `attribution` 产物（由 `render_output.material_timeline` 逐条派生，不重新推断）
+ 人可读 `output/credits_<task_id>.txt`。字段：`provider / source_id / source_url / license / license_class /
usage_restrictions / attribution / selected_asset{asset_id,name,sha256,path,bytes,width,height} / 镜头与时间窗 /
appears_in_film / film_evidence`；并给出 `entry_count / distinct_assets / license_classes_used /
restricted_or_unknown_in_film(+_scope) / licence_blocked_candidates`。**产物顺序契约不变**：
`render_output` 仍是渲染任务 `artifacts[0]`，`attribution` 先写文件、后挂载（供 `render_output.attribution_artifact` 引用）。

**许可机械分类与门禁单一事实源**（`core/materials.py`）：`LICENSE_CLASSES`/`classify_license`/
`license_block_reason` 移到 core，`tools/material_provider.py` 复用（消除重复实现）；
**适用范围 = 外部 provider 素材**（新增 `license_gate_applies`/`is_external_candidate`）：`RESTRICTED`/`UNKNOWN`
不得入片，provider 层 + `classify_scene` 分类阶段双重执行；**本地自带素材不适用**（无提供方声明可查，
只原样记录，不做法律判断——这也是 2.x/3.x 本地素材契约不回归的前提）。

**本阶段修复的缺陷（9 项）**：
1. **许可门禁过度适用（真实回归）**：分类阶段门禁把 `local_ingest` 自带素材（`license="unchecked"`，无 provider）
   判为 `ASSET_LICENSE_MISSING` → 冻结套件 `material_taxonomy_test` / `scene_assembly_test` / `pipeline_mock`
   失败（29/32）。→ 收窄为"外部素材"范围后**恢复 32/32**。
2. **artifact 顺序破坏**：`attribution` 先挂载使 `render_output` 不再是 `artifacts[0]`（`pipeline_mock` KeyError）
   → 改为先写 attribution 文件、后挂载，`render_output` 保持 `[0]`。
3. **通用 provider 误放行 `fair use`**：基类 `_license_flags()` 只要"非空即清权" → 改用 `classify_license` 机械分类。
4. **`selected_asset` 投影缺 `license_class`** → 补齐（交付物与断言需要）。
5. **`film_evidence` 缺 `corr_expected/corr_best`** → 写回（"上屏"证据可核）。
6. **中文查询对 Commons 0 命中（真实链路暴露）**：中文旁白无空格被当成整块词 → 查询整形改为**语料偏好**
   `latin_preferred`（优先取拉丁/数字词），无拉丁词时退回 `cjk_only`；离线证明 `logs/phase3a_shaping_rules.txt`。
7. **credits 文本行标签写错**（把本地路径标成 `license_url/来源页`）→ 改为"本地文件"。
8. **`phase2d_provider_e2e` D3 断言**未接受 2-E 引入的 `ASSET_TRUNCATED` → 断言更新（非放宽：截断仍拒收）。
9. **跨镜头品牌被 AND 成一个查询（第二个查询整形缺陷，真实搜索暴露）**：retrieval 把全部镜头文本拼成
   2,000 字符查询，整形后 `Quest PSVR2 PICO Valve` 四词 AND → Commons **0 命中**（实测 4 词 0、3 词 0、
   2 词 1 条非图片、单词 8；`logs/phase3a_query_ladder.txt`）→ 新增 `shape_queries()`：按**拉丁词簇**
   （源码位置连续才算一簇 = "品牌+型号"）多词簇优先逐条查询、拿到足够候选即停，`query_shaping.attempts[]`
   全程留痕。实测 `["Quest 3","PICO 4","PSVR2"]` → 2 次请求 16 条候选、4 个通过全部校验。

**阶段判定：PASS**。真实项目 `p_f4b466a4a024` 全链路核验 **16/16 PASS / 0 FAIL / 0 PENDING**：
真实 LLM（$0.00371196）→ **真实搜索**（2 次请求 16 条候选）→ **真实下载 11,543,130 字节**
（4 个通过容器完整性/ffprobe/ffmpeg/PIL/尺寸/许可证；6 个被拒带明确错误码：`ASSET_OVERSIZE`+5×`PROVIDER_RATE_LIMITED`）
→ 真实 TTS 6/6（112.728s）→ 旁白闸门 → 时间轴权威时长 104.0s → 渲染 6 镜头全外部素材/2 流/decode rc=0
→ **抽帧 6/6 `appears_in_film=true`**（corr 0.459–0.921）→ `attribution` 台账 6 条与时间轴 **1:1**、
`restricted_or_unknown_in_film == []`、credits 随片落盘。

**过程留痕（不掩盖）**：首轮执行时 Wikimedia 曾被网络链路阻断（TLS 握手超时；TCP 可连 0.2s、DNS 为真实
Wikimedia 网段 `103.102.166.0/24`、TLS1.2/1.3 均超时、其他站点 HTTPS 正常），该项当时如实记 **PENDING**、
**未冒充 PASS**；网络恢复后重跑，暴露并修复缺陷 9 后才转成 PASS。真实下载字节上的补充验证
（Phase 2-E 缓存字节，sha256 可核，来源已标注）**13/13 PASS**。

**已知限制（未动判据）**：词法匹配会选到语义无关素材——6 个镜头里 2 个选中 `Tiburón azul … Fayal-**Pico** …`
（鲨鱼），因旁白品牌 `PICO` 与西班牙语 `Pico` 词法同形；合规成立但内容相关性不对，语义级改选材属 4.x/受限版。

## V2.2.4-Phase2E 单一真实外部 Provider 接入与真实网络验证（2026-09-13，仅此一项）

**接入的唯一真实 Provider**：Wikimedia Commons（免费、**无需 API key**、无付费授权、无不可逆额度消耗）。
选型依据实测可达性（`logs/provider_reachability.txt`：Commons 200/3.7s/3882 hits；Openverse 超时；Met/NASA 可用）。
默认 `config/config.json` 仍是 `provider=none`，**未接第二个 Provider**、未做多 Provider 竞价/复杂排序。

**凭据隔离**：token/密钥**只能**来自环境变量或项目根 `.env`（复用 `core.env.load_env`），代码中无硬编码；
`auth.require_key=true` 且无凭据 → `PROVIDER_NOT_CONFIGURED`（不构造 provider、不伪造候选）；
证据只记 `token_present`，**从不记录 token 内容**。API：`https://commons.wikimedia.org/w/api.php`
（`generator=search` + `prop=imageinfo` + `extmetadata` 许可证字段），只收 `upload.wikimedia.org` 直链且 `image/*`。

**查询整形（机械规则，非语义）**：实测完整旁白拼接查询 → **0 命中**，去重取前 3–4 词 → 命中理想结果
（`logs/query_shaping_probe.txt`）；中文查询对 Commons 命中率低（实测 0 命中）——如实记录，不做语言猜测。

**本阶段发现并修复的真实缺陷（6 项，全部由真实网络暴露）**：
1. **截断文件骗过全部旧检查**：真实 JPEG 截断到 2 KB 后 magic bytes / ffprobe / ffmpeg 解码 rc=0 /
   `PIL.verify()` 全部通过 → 新增 `container_integrity()`（JPEG `FFD9`、PNG `IEND`、WEBP RIFF 长度）
   + `PIL.load()` 完整解码 → 新错误码 **`ASSET_TRUNCATED`**。
2. **检索层塌缩错误码** → 透传 `TransportError.code`（`PROVIDER_AUTH_FAILED` / `PROVIDER_RATE_LIMITED` /
   `PROVIDER_TIMEOUT` / `PROVIDER_SEARCH_FAILED`）。
3. **中文查询 `UnicodeEncodeError`**（URL 未编码）→ `urlencode(quote_via=quote_plus)`。
4. **文件名白名单过严**（真实素材名含逗号被误判 `ASSET_DANGEROUS_FILENAME`）→ 改为危险字符黑名单
   （路径分隔符/盘符/通配符/控制字符/保留设备名/可执行扩展名/超长仍拒）。
5. **下载腿无节流** → `_throttle()`（请求与下载共用最小间隔）+ 429 专用退避与重试预算
   （`rate_limit_backoff_s` / `rate_limit_retries`；限流次数计入 `stats.rate_limited`）。
6. **抽帧判据过严**（两张相似真实照片导致"期望素材非 argmax"误判失败）→ 改为"期望素材相关度达标且不低于
   最高者 margin 0.15"，并把 `corr_expected / corr_best` 写入证据。

**真实网络验证**：`phase2e_real_provider.py` **13/13**——真实搜索 8 条候选（`Public domain` / `CC BY 4.0` /
`CC BY-SA 4.0`，含真实 attribution）→ 真实下载（3,636,037 字节；另一轮 21,772 字节且 `rate_limited=21`
后退避重试成功）→ 校验 → timeline → 成片 **10.000s / 2 流 / decode rc=0**，**抽帧证实真实远端素材上屏**
（corr **0.486 / 0.996**，`appears_in_film=true`），`provider/source_id/source_url/license/attribution` 全部保留。
失败路径 `phase2e_failure_paths.py` **29/29**：未配置 key / **真实 401** / 429 / **真实搜索超时** / 下载超时 /
截断损坏 / 许可证缺失（含受限分类）/ 真实素材被策略上限拒绝 → 全部有明确错误码、不落盘、不当命中、
**无成片且 render BLOCKED**。

**回归**：**31/31 套件 rc=0**（含 `material_provider_test` **46/46**）；3 机械 E2E 全 SETTLED；
真实小测 PASS 且 **MockLLM=0**；ingest PASS；Phase 2-C 故障矩阵未退化（A/C 出片、B/D BLOCKED）、
追溯 38/38；Phase 2-A/B 验收仍 PASS（438.0s、12/12 在屏）；Phase 2-D 边界矩阵 **40/40**。
详见 `docs/regression_2x/PHASE2E_REPORT.md` 与 `PHASE2E_FAULT_REPORT.md`。

**未改**：Claim/HITL 核心、append-only、exec isolation、断点恢复、既有 task/artifact/event 契约
（未新增事件/artifact 类型）、narration gate、timeline 权威时长、Phase 2-C 分类学、local_ingest 行为、
默认 `provider=none`。**未做**：BGM、自动发布、UI 大改、语义级对齐、成本对账、Git tag、第二个 Provider。

## V2.2.3-Phase2D 外部素材 Provider 接入前的边界设计与实现（2026-09-13，仅此一项）

**定位**：只做**边界层**，不接任何真实外部服务（默认 `provider=none`，现有 local_ingest 行为不变）。

**Provider 抽象**（新增 `tools/material_provider.py`）：`search/fetch/capabilities` 统一接口；
实现 `LocalIngestProvider`（现有 local_ingest 的**兼容实现**，就地校验不复制）、`LocalCatalogProvider`
（本地目录 + catalogue.json，验收用 fake/local provider）、`HttpCatalogProvider`（真实外部形态，
`require_https` 默认开、禁跳转、transport 可注入）。配置 `tools.material.*`（超时/大小/重试/并发/缓存/
白名单/尺寸下限/许可证必需），provider 选择顺序 `tools.material.provider` → 既有 `tools.image.provider` → none。

**结果标准化**：候选字段 `provider/source_id/source_url/name/ext/license/attribution/usage_restrictions/
bytes/sha256/downloaded_path/download_status/probe_result/decodable/media_type/status/error_code/
needs_hitl/license_cleared`；`to_candidate()` 输出**现有素材候选结构** → 外部素材**必须经过** Phase 2-C
分类学（不可绕过 LOW_MATCH/ASSET_UNUSABLE/ASSET_CONFLICT/ASSET_EXHAUSTED）。`retrieval_candidates` 新增
`external_provider/external_verified/external_rejected/external_error/material_provided`，`material_mode`
扩展为 `local_ingest|external|mixed|none|external_configured_no_candidate`（原取值语义不变）。

**下载与校验边界**：传输（超时/404/5xx/空响应/重试耗尽）→ 危险文件名与路径穿越 → 扩展名白名单（含可执行类
一律拒）→ 大小上限（流式中断）与空文件 → **magic bytes 实际类型**（不看扩展名）→ ffprobe 有效图像流与尺寸 →
ffmpeg 解码 rc=0 → PIL 装载 → 尺寸下限 → 许可证。任一失败即 `REJECTED` 且带明确错误码，**不落盘、不进 ffmpeg**。

**许可证与归属**：缺失/不明确 → `license_cleared=false` + `needs_hitl=true` 且**在 provider 层拒收**
（即便文件合法）→ 不进入正常素材路径；`license/attribution/usage_restrictions` 原样记录，**不猜测不生成**；
被拒候选若本可命中某镜头，写入该镜头 `excluded_candidates` 并置 `license_pending=true`。

**安全与资源**：落盘名由 sha256 生成（绝不使用远端路径）、`.part`+原子替换、`(provider,source_id)` 索引
**先查后下**（防重复下载）、缓存上限拒绝而非静默淘汰、并发上限、从不执行下载内容；外部失败可降级到
local_ingest，完全无可用素材 → Phase 2-C `ASSEMBLY_BLOCKED` → render 阻断。

**同时修正自身两处缺陷**：① URL 分支"先下载后算 sha"导致重复下载 → 改为索引先查后下，并把缓存上限补到
本地目录分支；② `material_mode` 未计 `tools.material.provider`、`assembly_class()` 仍用旧判据 → 外部候选
全被拒时错误产出纯色底成片（应为 BLOCKED）→ 统一为 `material_provided`（本地索引非空 **或** 外部返回过候选）。

**验证**：单测 `tests/material_provider_test.py` **46/46**；端到端 `phase2d_provider_e2e.py` **12/12**
（外部素材 `provider/source_id/source_url/license/sha256` 入 timeline 且**抽帧证实上屏** corr 0.696；
许可证未明候选被拒 → 占位 + HITL + `license_pending`）；故障矩阵
`phase2d_boundary_matrix.py` **40/40**（10 类故障：明确错误码、不落盘、不当命中、9 类无成片且 BLOCKED、
许可证类降级到 local_ingest 并出片）；回归 **31/31 套件 rc=0**、3 机械 E2E 全 SETTLED、真实小测
**MockLLM=0**、本地 ingest PASS、ffprobe 真实性 PASS；Phase 2-A/B 验收仍 PASS、Phase 2-C 追溯 38/38。
详见 `docs/regression_2x/PHASE2D_REPORT.md` 与 `PHASE2D_FAULT_REPORT.md`。

**未改**：Claim/HITL 核心、append-only、exec isolation、断点恢复、既有 task/artifact/event 契约
（未新增事件/artifact 类型）、narration gate、timeline 权威时长、Phase 2-C 分类学、local_ingest 行为。
**未做**：BGM、自动发布、UI 大改、语义级对齐、自动许可证判定、多 Provider 竞价、大规模缓存、新 Agent。

## V2.2.2-Phase2C 素材不足降级分类学 + 完整可追溯（2026-09-13，仅此一项）

**分类学（新增 `core/materials.py`）**：镜头找不到足够匹配的真实素材时，必须**可审计降级**，不得静默用错素材、
伪造命中或产出无法解释的成片。两级字段：`insufficiency_class`（诊断）∈ NONE / NO_CANDIDATE / LOW_MATCH /
ASSET_UNUSABLE / ASSET_CONFLICT / ASSET_EXHAUSTED；`fallback_state`（动作）∈ LOCAL_INGEST（正常命中）/
THEME_FALLBACK（同主题降级）/ SOLID_COLOR_CARD（安全占位）/ BLOCKED_FOR_HUMAN；装配级 `assembly_class` ∈
NONE / ASSEMBLY_BLOCKED（已提供本地素材却无任何镜头能把真实素材上屏 → render 阻断）。

**降级策略（可配，缺省保持既有行为）**：`config.editing.{min_match_score=3, low_match_policy=theme_fallback,
zero_match_policy=placeholder, unusable_policy, conflict_policy, exhausted_policy, asset_reuse_policy=prefer_unused,
block_when_all_degraded=true, min_asset_width/height=320x180, frame_verify, frame_match_min_corr=0.30}`。
每个镜头记录 `fallback_state / fallback_reason / original_requirement / selected_asset|null / selection_reason /
needs_hitl / allowed_in_final_render`。`needs_hitl` 为**记录/建议**字段，不改动 HITL 闸门与任务审批顺序。

**禁止静默降级的代码级保证**：① 降级必写分类+原因（含实际分数与阈值）；② 占位场景 `selected_asset=null`，
且成片抽帧核验确认该窗口**不匹配任何素材**；③ 不可用素材（解码失败/尺寸不合格）在池构建阶段即排除，
**绝不进入 ffmpeg**；④ 素材不足 → render 抛 `[ASSET_INSUFFICIENT]` → FAILED→重试→**BLOCKED**（终态保留）；
⑤ render 产出后**逐镜头抽帧核验**（`scene_evidence`），把 `appears_in_film` 写回时间轴，"分配了素材却在该窗口
看不到它" 判渲染失败。

**完整可追溯**：逐镜头 `scene_id / original_requirement / candidates[]（分数·命中·可用性·占用情况·冲突命中）/
selected_asset（含 sha256/path/bytes）/ insufficiency_class / fallback_state / fallback_reason / selection_reason /
entered_timeline + 窗口 / appears_in_film + film_evidence / material_verification`；阻断项目的追溯写在 render 前的
`MATERIAL_TIMELINE` 事件（既有事件类型，字段纯新增；**未新增事件/artifact 类型**）。

**同时修复两处缺陷**：① 消费者读 `artifacts[0]` → 引擎重试任务时每次 attach 新产物，导致 render 读到失败轮次的
INCOMPLETE 产物而误阻断（实测机械 E2E A 组 BLOCKED）；已改为**最新优先**（`editing`/`voice`/`qa`）。
② Phase 2-C 初版误改 `_kw_tokens`/`_match_score` 匹配语义 → 已从 `3.x-phase2b1-baseline.zip` 取回冻结实现
逐字还原（diff=0），并停止把 `style_constraint` 混入匹配查询（它只用于约束冲突判定）。

**验证**：真实 LLM 项目 `p_ab2b352e06b8` 成片 25,033,388 bytes / 438.000s / 2 流 / 解码 rc=0，**12/12 镜头
LOCAL_INGEST 且逐镜头抽帧全部命中**（0.670–0.745），未渲染 0 个；素材分配与 2-B.1 **逐一致**（S01/S02/S03
相关 0.672/0.744/0.684）。故障矩阵 4 个真实项目：A 正常命中+占位（10.0s 出片，抽帧证实占位不是素材）、
B 无候选 → **BLOCKED 无成片**、C 低匹配（分数 1<3）→ THEME_FALLBACK **降级素材在屏且标注为降级**、
D 损坏素材 → **ASSET_UNUSABLE + BLOCKED，损坏文件从未进 ffmpeg**。回归：**30/30 套件 rc=0**（含新增
`tests/material_taxonomy_test.py` 40/40）、3 机械 E2E 全 SETTLED、真实小测 $0.002188 且 **MockLLM=0**、
本地 ingest PASS、ffprobe 真实性 PASS、追溯核对 **38/38**。详见 `docs/regression_2x/PHASE2C_REPORT.md`
与 `PHASE2C_FAULT_REPORT.md`。

**未改**：Claim/HITL 核心、append-only、exec isolation、断点恢复、既有 task/artifact/event 契约、
Phase 2-B.1 旁白完整性闸门与 timeline 权威时长契约。**未做**：外部素材 Provider、BGM、自动发布、UI 大改、
新 Agent、语义级镜头↔旁白对齐、成本对账、Git tag。

## V2.2.1-Phase2B1 音频完整性与渲染时长契约（2026-09-13，仅此一项）

**修复的真实缺陷**（Phase 2-A/B 报告中列为唯一关键 PENDING）：`VoiceAgent` 逐段 TTS 失败只记 `errors`
后继续，任务仍报 SUCCEEDED/`confidence=1.0`，`narration.mp3` 只覆盖成功段（实测 12 段仅成功 1/12、9/12、7/12）；
`render` 以 `-t {total} -shortest` 收尾 → 成片被音轨长度截短（438s 时间轴只出 238.5s），S09–S12 未进成片。

**实现**（新增 `core/narration.py` 作为契约单一来源）：

1. **分段状态真实化**：`voice_output.segment_details[]` 逐段记录
   `status(SUCCESS/REUSED/FAILED) / attempts / bytes / duration_s / text_sha256 / errors[{code,retryable,attempt,error}]`；
   全段齐备才 `complete=True`、`confidence=1.0`；否则任务失败（FAILED→重试→BLOCKED），产物为 `status=INCOMPLETE`。
2. **失败段独立重试 + 成功段复用**：错误分类 `TTS_NETWORK`(retryable) / `TTS_SYNTHESIS_FAILED` /
   `TTS_INVALID_AUDIO` / `TTS_CONCAT_FAILED`（保留原始异常文本）；可重试错误按
   `tools.tts.max_attempts`（默认 3）退避重试；`media/voice/segments_manifest.json` 记录
   文本哈希+音色+provider+时长，命中即复用（**不再调用 TTS**）。仅当全段齐备才重建 `narration.mp3`
   （**不覆盖**已有的完整旧音轨）。
3. **narration 完整性 gate**：`expected_segments / successful_segments / failed_segments / reused_segments /
   narration_duration_s / script_time_base_s / duration_contract` 全部落盘，可外部验证。
4. **时长契约（timeline 权威）**：权威时长 = `Σ max(duration_s,3.0) + 2.0`（= 时间轴末镜头 `end_s`）；
   旁白较短 → `apad` 静音补齐，**视频不缩短**；旁白偏长 → 容差内按时间轴裁尾并记录，**超容差（默认 10%）阻断**；
   **移除 `-shortest`**（三个渲染分支全部改为 `-t total`）；render **调用 ffmpeg 之前**做完整性闸门，
   产出后再校验 `|成片时长 - 时间轴| ≤ 1.0s`，不符即任务失败 → **不再产出"成功但被截短"的成片**。

**验证**：真实项目 `p_ab2b352e06b8` 受控注入第 4 段永久网络失败 → voice **BLOCKED**（`[NARRATION_INCOMPLETE]`，
逐段 `TTS_NETWORK`×3、其余 11 段 REUSED）、render **BLOCKED**（未产生新成片）；清除注入后 voice **12/12 COMPLETE**
（仅补 seg04，real TTS 调用=1）→ `narration.mp3` **439.056s** vs 时间轴 **438.0s（偏差 0.24%，容差 10%）** →
成片 `t_dba5c8008b82_draft.mp4` **438.000s** / 25,033,388 bytes / 2 流（video 13128 帧、audio 24000Hz）/ 解码 rc=0 →
**S01–S12 全部抽帧命中各自素材**（corr 0.670–0.745，未渲染镜头 0 个）。回归：**29/29 套件 rc=0**（含新增
`tests/narration_contract_test.py` 40/40）、3 机械 E2E 全 SETTLED（17.000s、24000Hz 真实旁白）、真实小测
$0.002967 且 **MockLLM=0**、本地 ingest PASS（17.000s，抽帧 0.747）。详见 `docs/regression_2x/PHASE2B1_REPORT.md`。

**未改**：Claim/HITL 闸门、append-only、exec isolation、断点恢复、既有 task/artifact/事件契约（未新增事件类型；
`voice_output`/`render_output`/`probe` 结果仅**新增字段**）。**未开发** Phase 2-C、素材不足降级、外部 provider、BGM、UI。

## V2.2.0-Phase2A/B 镜头级素材装配 + 素材时间轴（2026-09-13，仅 2-A + 2-B）

**2-A 镜头级素材装配**（`EditingAgent`）：
- 新增 `_build_material_timeline(script, shots, asset_pool)`：把脚本段落切成镜头，逐镜头**确定性**分配素材，
  记录 `scene_id / start_s / end_s / retrieval_query / matched_tokens / selected_asset{asset_id,name,source,
  sha256,path,relative_path,bytes,retrieval_match_score} / selection_reason / fallback_state`。
  规则：词法混合打分（CJK 二元组×2 + 单字×1 + 拉丁词(≥3)×2）→ 优先**未使用**素材中分最高者 → 命中分 0 则
  `fallback_state=SOLID_COLOR_CARD` 且 `selected_asset=None`（不伪造）。
- `_narration_args(..., timeline=)` 走**逐镜头多输入装配**：每镜头 `-loop 1 -t {窗口长} -i 素材`
  （无素材则 lavfi 纯色）→ `scale/crop/setsar/fps` 统一规格 → `concat=n=N:v=1:a=0` → 逐段 drawtext + fade → 混入旁白；
  无任何素材命中时退回 Phase 1 的单图背景 / 纯色底路径（行为不变）。
- `render_output` 新增 `material_timeline / assets_used / scene_count / scenes_with_asset / fallback_scenes /
  material_assembly ∈ {SUCCEEDED,PARTIAL,PENDING} / visual_source ∈ {material_timeline,
  solid_color_subtitle_card, ingested_material_background}`；新增 `MATERIAL_TIMELINE` 事件（仅新增类型）。
- 修复真实缺陷：渲染分支里 `img` 误用未导入的 `Path`（`name 'Path' is not defined`）。

**2-B 素材时间轴**：时间轴即上面的逐镜头记录，秒级窗口 + 素材 sha256 可追溯；`render` 按该时间轴出片。

**检索侧**（`RetrievalAgent`）：词法混合打分 + `matched_tokens` 落盘；索引解析优先"文件最多的 asset_index"
（修复：`asset_audit` 早于 ingest 时读到**过期空索引**）；查询缺省回退依赖产物；`material_mode ∈
{local_ingest, none, external_configured_no_candidate}`。

**验证**：真实项目 `p_ab2b352e06b8`（真实 LLM）——12 镜头、3 个不同 `local_ingest` 素材（检索命中 25/22/14）、
`material_assembly=SUCCEEDED`；成片 14,825,389 bytes / 238.5s / h264 1920×1080 30fps 7155 帧 / aac 24k 单声道，
ffmpeg 解码 rc=0；逐镜头抽帧 8 个已渲染镜头**全部**命中各自素材（corr 0.672–0.744），**不同素材**镜头对最大相关
**0.099**（同素材复用 ≈0.991 属预期）。回归：28/28 套件 rc=0、3 组机械 E2E 出片、真实小测 $0.002558、本地 ingest
链路含**抽帧核验** PASS、ffprobe 真实性 PASS。详见 `docs/regression_2x/PHASE2_REPORT.md`。

**PENDING（未伪造 PASS）**：成片 238.5s < 时间轴 438s，S09–S12 未渲染；根因是**音频阶段**——`voice` 三次真实运行
仅合成 1/12、9/12、7/12 段（`speech.platform.bing.com` 间歇性连不上），`VoiceAgent` 失败开放（仍 SUCCEEDED、
confidence=1.0，注释显示为**有意设计**，故未擅自更改）；渲染端 `-shortest` 使成片被截到音轨长度。素材装配侧无缺陷。
另有：fallback 分类学（2-C）、语义级镜头↔旁白对齐、成本残余 ¥3.24、GBK 触发点、Git tag（无仓库）等延续项。

## V2.1.1-Phase1.1 成本计量与稳定性收口（2026-09-13，仅三项）

**① LLM 费用对账**（差额机制查明，金额**未**强行凑平）：
- 核查结论：台账内部自洽——token 取自 API `usage`；实测 `completion_tokens ⊇ reasoning_tokens`（探针 28/26）；
  时段判定与官方中文价目页一致（高峰=北京周一至周五 9:00-12:00、14:00-18:00；本会话 49 次调用均为空闲时段）；
  单价取自官方页（flash 未命中 ¥1/¥2、输出 ¥4/¥8；v4-pro ¥4.5/¥9.0、¥13.5/¥27.0 每 1M）。
- **实测发现 provider 余额异步/批量结算**：3 分钟内**零 API 调用**，余额仍分三步下降 ¥0.79
  （11.96→11.84→11.67→11.17）；单次理论 ¥0.3926 的调用在 20s 后仅扣 ¥0.04（0.10x）。
- 残余 ≈¥3.24 无法在客户端归因（候选：同一 key 的其它调用方、更早窗口费用仍在结算、换算率/舍入不可观测）
  → 记为 **PENDING（PARTIALLY_EXPLAINED）**。
- 修复一条**真实漏账通道**：三个 judge 工具（`evidence_signal` / `llm_semantic_judge` / `sufficiency_judge`）
  用 `router.client.complete(...)` 直连，绕过 `Router.complete` → 无费用、无 `LLM_CALL` 事件。新增
  `Router.account_direct_call()` 并在三处调用后记账，`cost_usd` 同时写入 `llm_judge_cache` 行。
  本轮该通道未被触发（`llm_judge_cache` 0 行），属**风险消除**而非已发生漏账的追补。
- 新增 `tests/cost_accounting_test.py`（19 项）：计价数学、峰谷边界、未知模型不猜价、
  Schema 修复重试各记一条、预算闸门在发请求前拦截、**台账完整性守卫（client.calls == LLM_CALL 事件数）**、
  **judge 直连通道记账守卫**。

**② GBK 异常**：
- 本机默认编码 cp936；观测到的一次 `UnicodeDecodeError: 'gbk' codec can't decode byte 0x8c …`
  **未落库、未复现** → 该次具体触发点记为 **ROOT_CAUSE_NOT_REPRODUCED**（不伪造归因）。
- 风险类别已定位：`subprocess.run(..., text=True)` 未指定 `encoding=` 时用本地编码解码子进程输出。
  全量 AST 扫描 `src/video_studio` 共 15 处此类调用，补齐全 15 处 `encoding="utf-8", errors="replace"`
  （本轮补 9 处：stage32b/assemble、qc、render×3；stage33/asset_render_resolver、executor、subtitle_pipeline×2）。
- 新增 `tests/subprocess_encoding_test.py`（6 项）：默认编码断言、GBK 解码失败演示、
  **AST 静态守卫（所有 subprocess(text=True) 必须带 encoding）**、守卫覆盖度、中文路径运行时探测、
  失败时给出可诊断 `ToolError`。

**③ 语义级分镜↔旁白**：**仅方案设计，未实现**。保留现有结构化检查；跨模态 2-gram 重叠仅作信息项。
方案见 `docs/regression_2x/PHASE1_1_REPORT.md` §3（首选复用本地文本嵌入 + 人工复核；前置条件是先落
`shot→segment` 映射）。

**回归**：27/27 测试套件 rc=0（含 2 个新测试）；三组机械 E2E 各 SETTLED 出片；本地素材装配 PASS；
真实 LLM 小测 2 次调用 / 5,565 tokens / $0.003037（**任务行累计 == 台账合计**，MockLLM=0）；
ffprobe 真实性 PASS；6 个成片 ffmpeg 解码 rc=0；关键帧抽检完成。

## V2.1.0-Phase1 真实内容保真 + 本地素材最小装配（2026-09-13，3.x Phase 1）

**Part A 真实 LLM 内容保真**（新增 `config/config.real.json`，不删 `config.json` 的 mock 段）：

1. **Schema 未传达给模型（阻断级）**：agent 提示词只写"输出严格 JSON"，从不给出 `output_schema` 的键，
   Mock 下预置答复恰好合法故 2.x 从未暴露；真实模型自造键名 → `plan 缺 $.summary`、`topic 缺 $.proposals`。
   现 `Router` 统一把 Schema 注入提示词，并在校验失败时做**一次修复重试**。
2. **费用/审计**：`cost_usd` 原本写的是**档位 budget 上限**而非实际费用；现按官方价目表（peak/off_peak）
   实算、HTTP 返回即记账（失败调用也计费）、按调用**累加**写回任务，并逐调用发 `LLM_CALL` 事件
   （模型/tier/token/缓存/reasoning/延迟/重试次数/时段/费用）。
3. **显式错误与重试**：新增 `LLMError`（`LLM_AUTH/LLM_BALANCE/LLM_BAD_REQUEST/LLM_RATE_LIMIT/LLM_SERVER/
   LLM_TIMEOUT/LLM_CONNECTION/LLM_BUDGET_EXCEEDED`）；对 429/5xx/超时/连接失败退避重试 2 次；
   运行级预算闸门 `llm.max_total_usd`（超限不发请求）。
4. **跨项目记忆污染 + 上游产物缺失（主题漂移根因）**：`working_context` 以 `project_id=None` 取
   **跨项目**最近 3 条 agent_note（实测把上一项目的黑洞/脑机接口主题带进新项目），且任务 `inputs`
   只带 `{"phase": ...}`、没有任何产物引用 → 下游 agent 看不到上游内容。现：注入依赖产物内容（按上限）、
   自我记忆**仅限本项目**、只把 `a_*` 当产物引用。

**Part B 本地素材最小装配**：`editing` 渲染阶段读取 `retrieval_candidates` 命中的本地 ingest 图片，
作为全片背景（等比铺满 + 居中裁剪）替代纯色底；`render_output` 记录
`visual_source=ingested_material_background` / `material_assembly=SUCCEEDED` / `material_used{name,sha256,score}` /
`material_appearances`；无可用图片素材时保持 `PENDING` 不伪造。并对 LLM 给出的 `render_params`
做白名单归一化（实测 `"H.264 (libx264, High profile, CRF 18, yuv420p)"` 会导致 `Unknown encoder`）。

**修复的其他真实缺陷**：
- `redo` 只建新版本任务、**不重连下游依赖** → 旧任务停在 BLOCKED 使 `deps_ok` 永假、链路永久停摆
  （实测 C 组 7 个下游任务 40 轮不派发）；现 `redo` 调用 `rewire_dependents`（新增 `TASK_DEPENDENCY_REWIRED` 事件），
  且 `update_task` 允许更新 `dependencies`。
- `tools/ffmpeg_tool.py` 6 处 `subprocess(text=True)` 未指定编码 → Windows GBK 解码 UTF-8 输出时
  偶发 `UnicodeDecodeError`；现统一 `encoding="utf-8", errors="replace"`。
- M 档 `max_tokens` 8192 → 16384（实测 `script` 长 JSON 在 8192 处被截断成非法 JSON）。

**验证**：三组真实选材各自 26/26 任务、真实 API（MockLLM 调用 0）并出片；主题一致、B 三态标记 2/31/31、
C 六项约束全满足（62s vs 60s，偏差 3%）、三组字幕文本 Jaccard 2.6–6.5%（不再相同）；
本地素材装配帧相关性 +0.773（对照 +0.000）；25/25 套件 rc=0；三组机械 E2E 出片。详见
`docs/regression_2x/PHASE1_REPORT.md`。

**PENDING**：费用对账差额（台账 $0.1517 vs 余额减少 ≈$0.51）；分镜↔旁白语义级对齐（仅结构化检查）；
一次未复现的 GBK 解码异常（已加固编码）；真实素材/BGM 仍未接入（本阶段明确不开发 BGM）。

## V2.0.4 3.x-Preflight 基础设施修复（2026-09-13，不新增业务功能）

**背景**：2.x 基线验收通过后进入 3.x 前的 Preflight，只做基础设施修复与基线加固。

1. **假 ffprobe 修复（P1）**：`bin/ffprobe.exe` 原为 `bin/ffmpeg.exe` 的**字节副本**
   （同 SHA256 `2CE797A0F88D7F06…`），`-v quiet … -show_streams` 返回非 0 被静默降级到
   `ffmpeg -i` 解析；换参数则返回"Output file does not contain any stream"这类**误导结果**。
   现替换为真实 ffprobe（`2DA5B980A9A14A80…`，ffprobe 2022 full build；本次 gyan/GitHub 下载被网络阻断）。
2. **工具层二进制真实性检查**：`tools/ffmpeg_tool.py` 新增 `verify_ffprobe()`——
   ① 与 ffmpeg 字节级比对（同文件即判非法）② `-version` 必须自述 ffprobe；结果按 (size,mtime) 缓存。
   `probe` 检测到非法 ffprobe 时**直接抛 `ToolError("FFPROBE_INVALID")`**，不再返回误导结果；
   ffprobe 缺失时保留原 `ffmpeg -i` 降级，并在结果中标注 `probe_engine`。
   新增 `scripts/check_binaries.py`（可作启动/CI 自检）。
3. **素材能力边界显式化（P1，加法字段、不改契约）**：`asset_index` / `retrieval_candidates` /
   `render_output` 增加 `material_mode`（`local_ingest` / `none` / `external_configured_no_candidate`）、
   `material_providers`、`material_assembly="PENDING"`、`visual_source="solid_color_subtitle_card"` 等字段，
   区分「有真实素材 / 本地 ingest 素材 / 无素材仅字幕底片」，并写明 provider=`none` 时**不伪造候选**。
4. **本地 ingest 路径修复（P2）**：`retrieval` 任务原无 query 且**读不到 asset_index**
   （`asset_audit` 是它的兄弟节点而非祖先，依赖链 BFS 永远找不到）→ 即使 `run.py ingest` 了素材也恒为 0 候选。
   现：query 为空时回退到依赖产物文本（`visual_plan` 镜头描述 / `script` 旁白）；
   索引解析顺序为 `inputs.asset_index_ref → 依赖产物 → 本项目最新 asset_index`，并记录 `query_source` / `index_source` / `indexed_files`。
5. **文档**：README 补全 HITL 全流程（含**不可省略的 `approve-claim`**、`run/status/recover/redo` 顺序、素材三态表）；
   新增 `docs/regression_2x/BASELINE_README.md`（基线身份/测试命令/已知问题/3.x 安全边界）。

**回归证据**：25/25 套件 rc=0；三组选材 E2E 全新项目各 26/26 并出片（h264 1280×720 + aac 24k 单声道，解码 rc=0）；
本地 ingest 全链 PASS（`material_mode=local_ingest`、候选 1、`material_assembly=PENDING`）；
二进制检查 PASS 且假 ffprobe 触发 `FFPROBE_INVALID`。基线：`2.x-preflight-baseline.zip`
（文件数/SHA256/逐文件 manifest 见 `docs/regression_2x/BASELINE_README.md`；该 zip 排除 `docs/`，
故本文档不内嵌自身哈希，避免自指循环）。

**仍未修（PENDING）**：Mock 内容与选材无关（需真实 API 额度）；素材不上屏（渲染器未实现装配）；
无 BGM 能力（仅方案）；ffprobe 与 ffmpeg 版本不同代。

## V2.0.3 配音默认音色修复（2026-09-13，阻断级回归修复）

**缺陷（2.x 核心闭环被阻断）**：全新项目走文档快速开始（`run.py init/plan/run`）时，
`voice` 任务必然失败 `Invalid voice 'default'.` → `audio_mix`/`render` 无依赖满足 →
**永远产不出视频**。复现证据：CLI 路径 26 任务卡在 14 成功 / 12 PENDING（连续 29 轮 run 执行 0 任务）；
项目自带集成测试 `tests/pipeline_mock.py` 由 12/12 退化为 **5/8**（"全部任务完成""render 成功" FAIL）。

**根因链（三处叠加）**：

1. `config/config.json` 的 `tools.tts` 只有 `provider`，缺 `voice_type`；
2. `agents/voice/agent.py` 回退成**字面量 `"default"`**（真值），使 `tts_tool` 内置的合法默认音色
   `zh-CN-XiaoxiaoNeural` 失效，被 edge-tts 判为非法音色；
3. `tools/tts_tool.py` 未把 edge-tts 的异常包成 `ToolError`，导致 VoiceAgent 的
   `except ToolError` 优雅降级（`_plan_only`）路径失效，任务**硬失败并阻塞全链**。

**修复（3 处，最小改动）**：

1. `config/config.json`：`tools.tts` 增加 `"voice_type": "zh-CN-XiaoxiaoNeural"`；
2. `agents/voice/agent.py`：两处回退由 `"default"` 改为 `""`（空串让工具用自身默认音色）；
3. `tools/tts_tool.py`：`asyncio.run(_run())` 包 `try/except Exception` → `ToolError("TTS_FAILED", …)`。

**验证**：`tests/pipeline_mock.py` 12/12（真实产出 draft.mp4）、`tests/smoke_mock.py` 12/12；
三组真实选材 CLI 端到端（黑洞 / 脑机接口 / 60 秒科普）各 26/26 任务成功并产出可解码 mp4
（H.264 1280×720 + AAC 24k 单声道，ffprobe 交叉验证 + 抽帧 + 音轨电平 -3.9 dBpk/-20.0 dBFS）；
全量 25 个测试套件 rc=0。详见 `docs/regression_2x/REGRESSION_REPORT.md`。

**未修复/待办（写入已知问题）**：`bin/ffprobe.exe` 实为 `ffmpeg.exe` 的副本（同 SHA256），
`FFmpegTool.probe` 仅靠 `ffmpeg -i` stderr 降级路径可用；Mock 模式下内容与选材无关（三组成片字节相同）；
素材 provider 为 `none`，成片画面为深色底+烧录字幕（无真实素材）。

## V2.0.2 人工来源语义修正（2026-08，V2.0.1 之上增量）

**修正**：added_by=human / manual_sources 只代表"来源由人工提供"，不代表该来源直接支持 Claim。
人工来源仍必须经过 source reliability + relevance + support_level 判断；不得因"人工提供"提高核查结论。

1. **evidence Agent**：manual_sources 的 support_level 不再默认 DIRECT_SUPPORT——显式标注逐条透传，
   未标注 = 未评估（存 NULL）。
2. **schema**：evidence.support_level 改为可空（未评估=NULL）；migrate() 对 V2.0.1 的
   NOT NULL 旧约束自动重建表为可空（历史行已存值原样保留，V2.0.0 老库加列为可空、历史行 NULL）；
   insert_evidence 不再隐式补 DIRECT_SUPPORT。
3. **fact_check**：support_level 为 NULL 的证据不参与综合；若 Claim 仅有未评估证据 →
   Unsupported + 人工，verification_path=`UNEVALUATED_MANUAL`（与无来源 NO_RELIABLE_SOURCE 可区分），
   reasoning 注明需按 reliability + relevance + support_level 人工判定。结论枚举与状态机不变。

**专项测试**（tests/search_quality_v2_test.py 组 5，全文件 38→51 项）：
同一个人工来源（同一 source、added_by=human）三态 + 未标注：
DIRECT_SUPPORT→Confirmed、PARTIAL_SUPPORT→Mostly Confirmed、CONTRADICTS→Disputed（三者结论互异，
不被统一视为 DIRECT）；未标注的高质量来源→Unsupported+人工+UNEVALUATED_MANUAL；
登记链路 manual_sources support_level 逐条透传、未标注存 NULL。

**回归依据**：全量 8 套全绿（smoke 12 / pipeline 12 / schema_v2 10 / agents_v2 28 /
factcheck_v2 23 / strip_v2 14 / hitl_v2 19 / search_quality_v2 51）；
《永生》62 Claim 离线基线复验 10/10 不变（Unsupported 52 / Mostly 10 / Confirmed 0、NEEDS_HUMAN 51）；
运行时库 projects/video_studio.db 已自动迁移（列可空，历史 23 条已存值原样保留）。
factcheck_v2_test 证据桩与 hitl_v2_test 补证据用例改为显式标注 support_level（语义：测试桩模拟已评估证据）。

## V2.0.1 搜索证据质量层（2026-08，V2.0.0 之上增量，不动 V2 核心架构）

**功能**（设计依据 docs/搜索证据质量层设计.md，四层 4→1→3→2 实施）：

1. **layer 4 配置**：config/search_quality.json——域名黑名单/pattern、来源优先级
   （official>academic>regulatory>database>media>encyclopedia>forum>unknown）、
   claim 类型来源偏好、否定词表、相关性阈值。
2. **layer 1 搜索层**：SearchResult.domain、EvidenceCandidate.support_level
   （DIRECT_SUPPORT/PARTIAL_SUPPORT/CONTEXT_ONLY/CONTRADICTS/IRRELEVANT）；
   filter_candidates 候选预筛（URL 有效性/黑名单/关键词重叠——仅预筛，不证明语义支持）；
   order_candidates 来源优先级排序；_extract_from_page 讨论级提取
   （否定语境→CONTRADICTS；多关键词+关键数字→DIRECT；≥3 关键词→DIRECT；2 关键词/数字→PARTIAL；
   1 关键词→CONTEXT_ONLY；无/过短→IRRELEVANT）；中文 2 字滑动窗口切词（无空格中文的关键词匹配）。
3. **layer 3 schema**：evidence 表新增 support_level 列 + migrate() 旧库自动加列；
   缺省值 DIRECT_SUPPORT 仅历史兼容，不代表历史证据已通过新评估。
4. **layer 2 fact_check**：结论综合 = support_level + reliability + source_count +
   diversity + type + risk（support_level 只描述支持关系，不等同事实真假）：
   - CONTRADICTS/登记冲突 → Disputed + 人工（禁止自动判 False）
   - DIRECT_SUPPORT 不自动判 Confirmed（需官方/学术 high 或多 direct 或多源 high）
   - HIGH 仅 PARTIAL、CRITICAL 无强来源 → 保留人工（搜到证据不绕过人工闸门）
   - verification_path 区分 5 种无证据原因（SEARCH_FAILED/FETCH_FAILED/
     NO_RELEVANT_RESULT/NO_RELIABLE_SOURCE/INSUFFICIENT_EVIDENCE）；
     SEARCH_EVIDENCE 事件 payload 可追溯到 claim_id（query/provider/relevant/fetched/usable）
   - IRRELEVANT/CONTEXT_ONLY 候选不入证据库；evidence Agent 显式 support_level
     （资料卡→PARTIAL_SUPPORT 默认、人工来源→DIRECT_SUPPORT 默认，可显式指定）

**Bug 修复**：

1. **中文 Claim 关键词预筛失效**（重要）
   - 原因：_claim_tokens 把连续中文按整串切为一个词元，中文无空格导致
     关键词重叠预筛几乎必然 NO_KEYWORD_OVERLAP，讨论级提取退化为 CONTEXT_ONLY
   - 方案：中文连续串改按 2 字滑动窗口切词（英文 3+ 字母、数字 2+ 位不变）
   - 回归依据：factcheck_v2_test 23/23（在线桩场景恢复）、search_quality_v2_test 38/38

**测试与验收**：
- 新增 tests/search_quality_v2_test.py 38/38；factcheck_v2_test 显式矛盾断言
  False→Disputed（按"CONTRADICTS≠自动 False"硬约束更新）
- 全量回归 8 套全绿：smoke 12、pipeline 12、schema_v2 10、agents_v2 28、
  factcheck_v2 23、strip_v2 14、hitl_v2 19、search_quality_v2 38
- 《永生》62 Claim 离线质量层模拟 scripts/verify_yongsheng_offline.py 10/10：
  分布与离线基线一致（Unsupported 52 / Mostly Confirmed 10 / Confirmed 0、
  NEEDS_HUMAN 51、证据登记 0）→ 新质量层无异常放行
- Tavily 未接线（等用户提供 Key；在线通道 bing/baidu 免密钥回退保留）

## V2.0.0（2026-08-15，验收通过封版）

**功能**：V1 → V2 迭代升级（详见 docs/V2_SPEC.md 与 docs/RELEASE_V2.0.md）：
- 22 → 25 Agent（+claim_extractor / evidence / conflict_detector）
- 事实核查系统：claims/evidence/claim_evidence/conflicts/changelog 五表、
  Claim 提取与风险分级（CRITICAL 绝对化识别）、逐 Claim 证据核查、
  SearchProvider 抽象（在线可插拔 / 无 Key 自动离线）、来源冲突检测（必审）
- Skeptic 升级：7 类攻击指向 claim_id；fatal 强制人工但绝不改事实结论
- Claim 级人工审核闭环（approve/reject/revise + 生产闸门）
- strip_claims 全链路标记剥离（TTS/SRT/烧录/发布稿/朗读稿/metadata）
- Memory V2 8 层 + 全局规则统一加载

**Bug 修复（验收阶段发现，修复原因与方案记录如下，升级时禁止回归）**：

1. **claim_id 跨项目撞号**（严重）
   - 原因：claim_id 按"项目内计数"生成（每项目从 c_001 起），但主键全局唯一；
     第二个含 Claim 的项目必然触发 UNIQUE constraint，claim 提取任务重试后 BLOCKED
   - 方案：自动编号改为全局计数（COUNT 全表 + 1）；标记路径 [CLAIM:nnn] 遇已占用
     时追加项目后缀 `_pXXXXXX` 去重
   - 回归依据：agents_v2_test 27/27（标记复用 c_007 断言保留）

2. **evidence_index 时序缺陷**（严重）
   - 原因：证据登记任务原依赖 p1 任务（research/source_verify），在 Claim 提取
     之前执行，导致"证据→Claim 关联"循环面对空 claims 表，全部落空（带证据 Claim=0）
   - 方案：evidence_index 依赖增加 claim_extract（与 V2_SPEC 顺序
     script→claim_extractor→evidence 一致），保证登记时 claims 已存在
   - 回归依据：验收实测 9 条 Claim 带证据（c_161 Confirmed ← 动画官方设定 2012）

3. **生产闸门与未审核状态收口**（重要）
   - 原因：闸门初版只拦 NEEDS_HUMAN；reject 重建链产生的新 UNVERIFIED claim 会漏网，
     违反"未通过审核的 Claim 不得进入生产"
   - 方案：闸门收紧为"全部 claim 处于 PASSED（VERIFIED/REJECTED）才放行"；
     strip_v2_test 相应补充模拟人工批准步骤（剥离断言强度不变）
   - 回归依据：hitl_v2_test 19/19、strip_v2_test 14/14

## V1（2026-08-15 之前）

- V1 完整交付：22 Agent 生产团队、SQLite 总线、工具层、6 任务闸门、渲染/TTS/字幕链路
- V1 真实项目：58 秒版 / 10 分钟版 / 王骁风格版 / 新规范版（4 个 SAO 项目留存于 projects/）
