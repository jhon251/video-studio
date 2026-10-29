# 6-A 设计审计报告：Production Integrity + Directorial Quality（**只读，零改动**）

- 日期: 2026-09-23
- 阶段: **6-A（仅方案/现状审计）** —— **禁止修改代码、禁止重渲染、禁止修改 baseline**
- 审计对象: `p_96efdc03e1aa` 的 **v9 成片** `t_d0a54bdf1810_draft.mp4`（人工验片判定 **FAIL**，不得作为发布候选）
- 前置状态（本轮**保持不动**）：5-M 工程门禁 **PASS**；基线 `5.x-post-final-maintenance-baseline-r3` **保持冻结**；
  `5.x-final-baseline` 未被触碰
- 本轮产物（全部在 `docs/`，**不在基线内**）：本文、`PHASE6A_PLAN_DOD.md`、`logs/phase6a_audit.json`、
  `logs/phase6a_extra.json`、`logs/phase6a_frames/*.png`
- **零改动证明**：见 §5（代码/测试指纹与基线校验在审计前后一致）

---

## 0. 结论摘要

| 维度 | 实测结论 |
|---|---|
| TTS 覆盖率 | **62.77%**（旁白 961.656 s / 时间轴 1532.0 s） |
| 音频断裂 | **精确定位**：`silencedetect` 仅 1 段静音，**961.14 s → 1532.01 s（570.87 s，占全片 37.26%）**，即人工所说 **16:01** 处 |
| apad 掩盖 | **确认**：既有契约把"旁白较短"定义为**允许并由 `apad` 补静音**（`core/narration.py:157-161`），渲染前闸门只拦"旁白**过长**"（`agents/editing/agent.py:565-568`） |
| 字幕覆盖/孤儿 | 216 条 cue、覆盖 **64.46%**；**73 条（33.8%）落在静音区**（首条 orphan 967.4 s） |
| 视觉重复 | 21 镜仅 **4 个唯一素材**（5/6/3/7 镜）；平均静态保持 **73.0 s**；**17/21 镜 > 60 s**；镜变密度 **0.82 次/分钟** |
| 全片"动"的部分 | `freezedetect`：冻结占比 **99.46%**、389 块、最长同像素段 **10.8 s**（≈ 字幕刷新间隔）→ **除字幕外画面几乎全程静止** |
| 旁白↔画面 | 只读多模态：4-B `MATCH2/MISMATCH0/UNKNOWN19`；5-A `1/3/17`；5-D `1/2/18`；Judge 最终 `1/2/18`（MISMATCH=S05,S11；18 UNKNOWN 中 14 为 `JUDGE_UNKNOWN_DOMAIN`） |
| 高潮 | 20/21 镜命中核心论点关键词，但**只有 4 个素材** → **无视觉高潮** |
| 片尾 | **无 outro 段**（关键词仅句中"最后/关注"）；末镜为"刻意没有写死的地方"限制声明；**570.3 s 静音尾** |
| 质量闸门 | 语音完整性 ✓、渲染前旁白闸门（只拦过长）✓、成片响度 ✓、QA（3 项技术检查）pass、compliance pass（**其 summary 与事实不符，见 §4 注**）、critic_final **REWORK**（人工裁决接受为 DRAFT）；**多模态评估层（4-B/5-A/5-D/5-E/5-F）全部未接入生产（#49 BY DESIGN）** |

---

## 1. Production Integrity（现状实测 + 应否成为硬门）

### 1.1 TTS 实际覆盖率

| 指标 | 实测 | 证据 |
|---|---|---|
| 段落数（脚本 / 语音） | 21 / 21（全部 SUCCESS，0 失败段） | `voice_output.segment_details` |
| 逐段真实 TTS 时长合计 | **961.656 s** | `voice_output.narration_duration_s` |
| 时间轴总长 | **1532.0 s** | `render_output.duration_contract.timeline_duration_s` |
| **覆盖率** | **62.77%** | `logs/phase6a_audit.json` → `narration_alignment.coverage_ratio` |
| 单段时长对比（脚本 vs TTS） | 40.0→30.1、85.0→66.6、80.0→51.0、85.0→44.9、65.0→48.8 … | 同上 `per_scene` |

> 结论：合成**没有失败**，问题是**脚本时长（1532 s）与实际口播时长（961.7 s）不匹配**，且**没有任何门检查下界**。

### 1.2 TTS ↔ 时间轴 duration mismatch（错位曲线）

| 镜头 | 脚本起点 | 语音起点 | 累计漂移 |
|---|---|---|---|
| S01 | 0.0 s | 0.0 s | 0.0 s |
| S06 | 300.0 s | 218.1 s | **−81.9 s** |
| S11 | 690.0 s | 480.1 s | **−209.9 s** |
| S16 | 1080.0 s | 710.7 s | **−369.3 s** |
| S21 | 1465.0 s | 912.8 s | **−552.2 s** |

> 影响：① 画面/字幕（脚本时基）与语音（连续拼接旁白）**越走越偏**，末段偏差约 **9.2 分钟**；
> ② 由于旁白是"连续拼接 + 尾部 apad"，**语音在 961.7 s 处直接结束**，之后 570.3 s 无音。

### 1.3 音频中途断裂 / 长静音（成片实测）

`ffmpeg silencedetect(noise=-45dB,d=2)` 对 v9 成片：

```
silence_start: 961.14  silence_end: 1532.01  silence_duration: 570.87
```

- **静音块数 = 1**（无内部碎断，说明断点就是"旁白结束"这一点）
- **静音占比 37.26%**、**最长静音 570.87 s**
- 与人工"16:01 音频断裂"**完全一致**（16:01 = 961 s）

### 1.4 narration 缺失是否被 apad/补静音掩盖 —— **确认被掩盖**

| 层 | 事实 |
|---|---|
| 契约定义 | `core/narration.py::duration_contract`：`shortfall_s = max(-delta,0)`、`audio_padded_to_timeline = delta < 0`，注释即写明"**较短→静音补齐**"、"**较长→超容差则阻断**" |
| 渲染前闸门 | `agents/editing/agent.py:560-568` 仅在三种情况下阻断：① voice 产物不完整；② 旁白时长不可探测；③ **`excess_s > 0 且超容差`**（旁白比时间轴长）。**没有短差（覆盖不足）任何条件** |
| 产物记录 | `voice_output.duration_ok = False`、`render.duration_contract.within_tolerance = False`、`shortfall_s = 570.344` —— **被记录但无人消费** |
| 音频链 | `[..]loudnorm,alimiter,aresample=24000,apad[aout]` → **apad 把静音补到 1532 s** |
| 成片闸门 | 仅 `enforce_loudness_on_film`（整体响度）。实测 −16.1 LUFS / TP −2.5 dBFS **达标** → 静音不触发任何失败 |

### 1.5 subtitle coverage / orphan

| 指标 | 实测 |
|---|---|
| cue 数 / 显示总时长 | 216 / 987.6 s |
| 覆盖率 | **64.46%** |
| **落在静音区的 orphan cue** | **73 条（33.8%）**，首条 **967.4 s** |
| 根因 | 字幕时间基 = **脚本/时间轴**（`core/captions.build_cues` 按段落时长累计），而语音是**连续拼接**且 961.7 s 结束 |

### 1.6 timeline gap（镜头边界 vs 语音边界）

- 21 个镜头时长 40–95 s，语音段 30.1–66.6 s → 每个镜头末尾都有 10–40 s **无旁白画面**；
- 累计到末镜：**552.2 s** 画面无旁白；全片静音尾 **570.3 s**。

### 1.7 render 后实际音视频轨验证（现状 vs 应有口径）

| 项 | 现状实测（v9） | 现有门是否检查 | 应有口径（建议） |
|---|---|---|---|
| 容器 / 视频轨 / 音频轨 | 1532.0 / **1531.96** / 1532.0 s | ✅（`video_duration_ok`） | 保留 |
| 帧数 / fps / 分辨率 | 38,300 / 25 / 1920×1080 | 部分（抽帧核验） | 保留 |
| **音频连续性（最长静音/静音占比）** | **570.87 s / 37.26%** | ❌ **无任何检查** | **硬门** |
| **旁白覆盖率（成片实测）** | **62.77%** | ❌ | **硬门** |
| 音视频轨差值 | 0.04 s（1 帧） | ❌（仅容器时长） | advisory |
| 字幕覆盖 / orphan 比例 | 64.46% / 33.8% | ❌ | **硬门（orphan ≤ X%）** |

### 1.8 建议的硬门 / advisory 分级（**仅为设计建议，需授权后才实施**）

| 编号 | 门 | 口径（可度量） | 级别 |
|---|---|---|---|
| PI-1 | 旁白覆盖率下界 | `narration_duration_s / timeline_duration_s ≥ 0.90`（或导演口径的自定义值） | **HARD（渲染前）** |
| PI-2 | 时长契约双侧 | 同时拦 `excess`（已有）与 `shortfall`（新增）；`within_tolerance=false` 且 `shortfall > 阈值` → BLOCKED | **HARD（渲染前）** |
| PI-3 | 成片音频连续性 | 最长静音 ≤ 8 s（可配）；静音占比 ≤ 10%；无"旁白结束后仍 ≥ X s 静音" | **HARD（渲染后实测）** |
| PI-4 | 成片音视频轨一致性 | `abs(video_s − timeline) ≤ 1 帧` 且 `abs(video_s − audio_s) ≤ 0.5 s` | advisory → 可升 HARD |
| PI-5 | 字幕时间基一致性 | cue 必须落在"语音有效区间"内；`orphan_share ≤ 2%` | **HARD** |
| PI-6 | 字幕覆盖率 | `cue_display_s / narration_duration_s` 在 [0.6, 1.1]（避免字幕早于/晚于语音） | advisory |

---

## 2. Directorial Quality（只读诊断）

### 2.1 Hook 视觉相关性 —— **错位（人工发现 VERIFIED）**

- Hook 旁白（0–40 s）："假设有一天，一个 AI 交出一份三千页的证明。它通过了所有机器检查…"
- 实际画面（抽帧 `logs/phase6a_frames/v9_t00005s.png`）：**一群中学生举塞尔维亚国旗的合影**（`MGB - IMO 2010` 照片）
- 该素材来源为 local_ingest，语义与 hook 无对应关系；多模态层对 S01 的判定为 `UNKNOWN`（4-B/5-A/5-D 均未给 MATCH）

### 2.2 visual repetition / reuse —— **严重（VERIFIED）**

| 素材 | 上屏镜数 | 上屏秒数 | 占比 |
|---|---|---|---|
| `asset_3f0b94a3f2ac` Close-packed spheres.jpg | **7** | 485.0 s | 31.7% |
| `asset_30dd89a16713` Four color theorem map of Germany 3.png | **6** | 435.0 s | 28.4% |
| `asset_432cd85be6f1` MGB - IMO 2010 pic3.jpg | **5** | 350.0 s | 22.8% |
| `asset_23e71bc8a864` Postal Meter Strip（四色定理邮票） | **3** | 205.0 s | 13.4% |

- **21 镜 / 4 唯一素材**；镜头变化密度 **0.82 次/分钟**；唯一素材密度 0.16/分钟。

### 2.3 static-hold duration —— **全片近乎静止（VERIFIED）**

- 逐镜静态保持：40–95 s，**均值 73.0 s**，**17/21 镜 > 60 s**；
- 成片级 `freezedetect`：**冻结占比 99.46%**、389 块、**最长同像素段 10.8 s**（该 10.8 s ≈ 字幕最长显示时长）
  → **画面本身全程静止，唯一在动的是字幕**。

### 2.4 visual density

- 0.82 镜变/分钟（≈ 每 73 s 才换一次画面）；对照一般科普/纪录片节奏（数秒~十几秒一个视觉信息单元）严重偏低。

### 2.5 narration ↔ visual alignment（复用 5.x 只读评估证据）

| 层 | MATCH | MISMATCH | UNKNOWN |
|---|---|---|---|
| 4-B 文本语义 | 2 | 0 | 19 |
| 5-A 单帧 CLIP | 1 | **3** | 17 |
| 5-D 多帧/时序 | 1 | **2** | 18 |
| **Judge（最终）** | **1（S03）** | **2（S05、S11）** | **18** |

- 18 个 UNKNOWN 中 **14 个是 `JUDGE_UNKNOWN_DOMAIN`**（旁白推不出期望语义域 → 已知 #23/#43 词典覆盖限制）；
- **这些层均未接入生产判定链（#49 BY DESIGN）** → 对成片没有阻断力。

### 2.6 climax visual coverage —— **无视觉高潮（VERIFIED）**

- 命中核心论点关键词（AlphaGeometry/Lean/mathlib/四色定理/开普勒/机器/形式化…）的镜头 **20/21**；
- 但这些镜头所属素材仍只是那 **4 张图**（`distinct_assets_in_core = 4`），且图与论点无对应关系
  （例：S07"两种立场/AlphaGeometry/Lean"用的仍是四色定理地图）；
- 全片没有"视觉信息升级"（无示意图、无数据可视化、无演示动画、无片段切换节奏变化）。

### 2.7 ending / outro completeness —— **缺片尾（VERIFIED）**

- 末镜 S21（1465–1532 s）旁白为**限制声明**（"这一期里有一堆我刻意没有写死的地方…"），非收束；
- **无 outro/结束卡**（关键词命中仅为句中"最后/关注"）；
- 旁白在 **961.7 s** 结束 → 末 **570.3 s** 只有静态图 + 字幕（其中 73 条字幕落在静音区）。

---

## 3. 人工 6 项发现逐条核实

| # | 人工发现 | 实测 | 判定 | 证据 |
|---|---|---|---|---|
| 1 | 16:01 音频断裂 | 静音起点 **961.14 s**（=16:01.1），持续 570.87 s（37.26%） | **VERIFIED** | `phase6a_audit.json → audio_silence` |
| 2 | 21 场景仅少量静态图重复 | 21 镜 / **4 素材**（5/6/3/7）；冻结占比 99.46%；17/21 镜 > 60 s | **VERIFIED** | `visual`、`video_freeze` |
| 3 | Hook 视觉错位 | hook 用"学生举旗合影"，与"AI 证明"无关；多模态 S01=UNKNOWN | **VERIFIED** | 抽帧 `v9_t00005s.png` + `audit_p96efdc_mm.json` |
| 4 | AlphaGeometry/核心论点缺少视觉高潮 | 20/21 镜命中核心词但仅 4 素材、无视觉升级 | **VERIFIED** | `core_argument_scenes` |
| 5 | 缺片尾 | 无 outro 段/结束卡；末镜为限制声明；570.3 s 静音尾 | **VERIFIED** | `ending`、`outro_keyword_hits` |
| 6 | 字幕断行问题 | 5-M 已把"整段居中铺满"改为底部逐条（≤2 行、标点优先断行），但**仍有 33.8% 字幕落在静音区**、且长句被折成两行时语义切割仍可优化（如"…无法完整 / 地参与理解…"类） | **PARTIAL（已改善，仍有残留问题）** | `subtitles`、5-M 报告 §2 |

> 补充：人工判 **v9 = FAIL（不得作为发布候选）** 与工程门禁 **5-M PASS** 并不矛盾——5-M 的 DoD 只覆盖"字幕呈现改造 + 回归不退化"；
> **"能否发布"属于导演/内容质量维度，5.x 至今没有可度量的发布门**（这正是 6-A 要补的）。

---

## 4. 追因：音频断裂为何没有被现有 5.x 闸门阻止，应在哪一层拦截

| 层（代码位置） | 现有闸门 | 判据 | 本例结果 | 缺口 |
|---|---|---|---|---|
| 语音 Agent `agents/voice/agent.py:116-146` | 段落完整性 + 记录时长契约 | `complete`（21/21 ✓）；`duration_ok` 仅**记录** | 任务 SUCCEEDED；`duration_ok=False` 入产物但**不阻断** | 下界（覆盖不足）不构成失败 |
| 渲染前闸门 `agents/editing/agent.py:547-581` | `NarrationIncompleteError` | 仅：不完整 / 不可探测 / **旁白过长超容差** | 通过（旁白"过短"是设计允许） | **无覆盖率下界** |
| 音频链 `agents/editing/agent.py:1289-1354` | `apad` | 静音补齐到时间轴 | 570.3 s 静音被"合法"补齐 | 补齐**掩盖**了内容缺口 |
| 成片闸门 `core/audio.py:339+` | `enforce_loudness_on_film` | 整体 −16 LUFS / TP ≤ −1.5 dBTP | 通过（−16.1 / −2.5） | **不检连续性/覆盖** |
| QA `agents/qa/agent.py` | 3 项技术检查（流/时长/…) | 存在视频流/音频流/时长 | pass | 无内容/覆盖/静音检查 |
| compliance `agents/compliance/agent.py` | 版权/敏感 | 素材许可、字体、AIGC 标识 | pass（**注**：其 summary 称"视觉为纯色底字幕卡、未使用第三方图像"，与本片实际使用 4 张 Wikimedia 素材 **不符**） | 报告与事实脱节（登记项） |
| critic_final `agents/critic/agent.py` | 交付一致性/事实质疑 | 针对 render_output + attribution | **REWORK**（1 major + 3 minor）；后经人工裁决接受为 DRAFT | 有"质疑"但**非阻断门**、且不看音视频完整性 |
| 多模态层（4-B/5-A/5-D/5-E/5-F） | 只读裁决 | Judge J0–J6 | `MISMATCH 2 / UNKNOWN 18` | **#49 BY DESIGN：未接入生产判定链** → 无阻断力 |
| HITL 闸门（topic/structure/script/materials/final_cut/publish） | 人工审批 | 人工 | 4 闸 approve（`editing_plan_APPROVED` 的 rationale 写的是"25 镜占位卡方案"，**与最终 4 素材成片不一致**） | 人工闸门缺"成片复核"口径与检查单 |

**应在哪一层拦截（建议）**

1. **第一拦截点（必须，渲染前）**：在语音→渲染之间新增 **PI-2 双侧时长契约**：`shortfall_s` 超阈值即 `BLOCKED`（与既有 `excess` 对称），
   证据沿用 `core/narration.duration_contract`（已具备字段，只缺判定与阻断）。
2. **第二拦截点（必须，渲染前）**：**PI-1 覆盖率硬门**（`narration/timeline ≥ 0.90`），失败即 BLOCKED 并把"需延长旁白或压缩时间轴"写入 error/事件。
3. **第三拦截点（必须，渲染后实测）**：**PI-3 成片音频完整性**（`silencedetect` 最长静音/占比）+ **PI-5 字幕 orphan 比例**，
   不达标 → 交付物标记 `NOT_DELIVERABLE`（不改文件、不自动重渲，只 fail-closed 并交人工）。
4. **第四拦截点（建议 advisory→HARD 分级）**：**Directorial Quality 红线**（唯一素材数下限、单镜静态保持上限、高潮覆盖、片尾存在性），
   第一版只输出**只读诊断报告**给人工裁决（授权要求：不自动换素材、不自动剪辑、不自动发布）。
5. **第五条（流程）**：把"人工验片"变成**结构化闸门**（`final_cut`/`publish` 前必须提交验片结论 + 依据 6-A 检查单），
   并把 `editing_plan_APPROVED` 的"方案 vs 最终成片"一致性纳入复核（本例两者已不一致）。

---

## 5. 零改动证明（本轮边界遵守）

| 证明项 | 方法 | 结果 |
|---|---|---|
| 未修改代码/测试 | `phase5m_code_fingerprint.py now` 与冻结时指纹比对 | 待复核输出（见下） |
| 未修改基线 | `verify_baseline.py 5.x-post-final-maintenance-baseline-r3` | 期望 **MATCH**（missing 0 / drift 0） |
| 未重渲染 | 本项目 output 目录成片 mtime/sha 未变 | 见复核输出 |
| 未触碰 5.x Final | `5.x-final-baseline.zip` sha256 | 期望 `be1717b9…` |

> 复核命令与结果附于 `PHASE6A_PLAN_DOD.md` §6 与本次会话输出（审计脚本本身只写 `docs/`）。

---

## 6. 证据索引

- 实测 JSON：`docs/regression_2x/logs/phase6a_audit.json`（silence/freeze/视觉/漂移/字幕/orphan/高潮/片尾/各 Agent 报告）
- 补充 JSON：`docs/regression_2x/logs/phase6a_extra.json`（片尾关键词、裁决记录、质量任务状态、阻断事件、多模态汇总）
- 抽帧：`docs/regression_2x/logs/phase6a_frames/v9_t{00005,00040,00961,00990,01512}s.png`
- 既有只读证据：`logs/audit_p96efdc_mm.json`（4-B/5-A/5-D/Judge 逐镜）、`logs/audit_p96efdc_film_check.json`（成片探针）
- 审计脚本（只读）：`docs/regression_2x/phase6a_audit.py`、`phase6a_extra.py`
