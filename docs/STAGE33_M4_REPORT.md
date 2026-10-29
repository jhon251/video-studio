# Stage 3.3 P1-M3/M4 报告（Legacy 回归 + Visual 执行渲染）

> 状态：M3 PASS、M4 机器 Gate 全 PASS；**人工观看裁决（2026-08-30）= FAIL / NOT_MEANINGFULLY_BETTER，禁止进入 P2**。
> 失败归因与 v3 重新设计：`docs/STAGE33_P1_FAILURE_REVIEW.md`；本报告及 M4 产物保留为失败基线。

## 1. M3 Legacy Byte-Level Regression —— **PASS**

- 按 Preflight 流程对原始 Coral 重跑 legacy 链：`subtitle → blocked → assemble → render → qc`（--force，复用既有 VO，不重跑 TTS、不重检索）；
- 各阶段 Gate 全绿（P0-3/P0-4/P0-5/P0-6/P0-7）；
- **146/146 文件 SHA 与 M1 baseline 逐字节一致**（含 final_preview.mp4=3C629B62…、subtitles.srt/ass、voiceover.wav、7 个 manifest、20 镜 shots、素材文件）→ 3.2b legacy 路径字节级稳定得证，**Stage 3.3 未对 3.2b 造成任何影响**；
- 3.2b/3.1.4/2.x/冻结稿全程只读；备份 `coral_backup/` 未动用（无需回滚）。

## 2. M4 执行链（visual_plan → executor → 3.2b 兼容工件 → render → QC）

- 输入：冻结 `visual_plan.json`（plan_sha=b122f0bd…，25 beats/20 镜）；
- 新增模块：`stage33/graphics.py`（3 图形模板+3 排版卡，PIL 确定性）、`stage33/executor.py`（beat clip→镜→3.2b 兼容工件→import 3.2b render/qc）、`stage33/visual_qc.py`、`run_stage33.py`（execute/visual-review）；
- 25 个 beat clip 全部渲染（18 张图形 PNG、7 张素材图、2 个视频素材）；4 个需下载素材经 429 退避后全部落地（最终 0 降级）；
- **3.2b 零修改**：executor 产出同布局工件后仅 import 调用 `render.build_final` / `qc.run_qc`。

### 机器 Gate（全 PASS）

| Gate | 结果 |
|---|---|
| P0-6 Render Gate（10 项） | **PASS**（102.2s / 1080p / 25fps / 48kHz / 字幕烧录） |
| P0-7 技术 QC（13 项） | **PASS**（无黑帧/冻结帧、无异常静音、I=-17.7 LUFS、峰值 -2.0dB、字幕逐字/同步/无越界、provenance+output SHA 一致） |

### 对照双件（唯一变量=视觉表达）

| 件 | 路径 | 参数 |
|---|---|---|
| 3.3 P1 | `output/stage33/coral/stage33_p1_m4.mp4`（17.4MB） | 102.20s / 1920×1080 / 25fps / aac 48kHz mono |
| 3.2b legacy | `output/stage33/coral/legacy_3.2b.mp4`（25.7MB） | 102.10s / 1920×1080 / 25fps / aac 48kHz mono |

同冻结稿、同 VO（音轨字节同源）、同字幕、同 20 镜、同时长口径、同分辨率/fps、同响度链（loudnorm+alimiter）——画面表达是唯一差异。

## 3. 机器视觉证据（`output/stage33/coral/visual_qc.json` + `docs/STAGE33_M4_VISUAL_REVIEW.md`）

- beats 25/25 渲染、无黑帧、无缺 clip；motion 渲染确认 22/25；
- **TEXT_CARD 12.0%（3.2b=45%）**、视频裸播 0、绿幕叠字 0（P1 规则）；
- 开场 SLOW_PUSH_IN / 收束 SLOW_PULL_OUT（Validator 归一）；climax B022（intensity HIGH）；motif M-OPENING-CLOSING（B001→B025 首尾呼应）；
- 运动语义审计：PAN_V 方向 100% 与口播语义词对应（B001 DOWN"海水下面"、B011 UP"绑在架子上"、B012 DOWN"水下"）。

### 如实上报的机器发现（供人工裁决，不擅自改）

1. **连续同构图**：B007–B010 四连 FULL_BLEED（最长 6 连段 B010）——P1 Validator 只约束"全片 ≥2 种构图"，未约束连续；建议 P2 加"连续同构图 ≤3"禁令；
2. **数据图形化**：8 个 DATA 型 beat 用 SELF_CREATED_GRAPHIC/排版卡而非图表（如 B022「十年的选择」）——其中多数是"数字只作强调词"，是否值得图表由人工看片裁决；
3. **motion 渲染确认 3 例"人工看"均为解释性误报**：B007/B023 是视频素材自身内容运动（非镜头运动），B016 是 pull-out 幅度天然小（8% zoom 的帧差 <1.5 阈值）——机器口径已记录，不作缺陷；
4. M2 授权修复项全部落地并通过回归测试：NUM_RE 量词（"一座/一个"不再当数字）、beat_types 枚举、climax_beat 引用、SAFE_IMAGE 素材硬校验、emphasis_target 子串、callback 具体性、**跨镜理由剔除**（S20 引入 S19 内容已修复）、中英混写检测（human_review_flags 标记）。

## 4. 人工观看（本轮 STOP 点）

请依次观看（各 102s）：
1. `output/stage33/coral/legacy_3.2b.mp4`
2. `output/stage33/coral/stage33_p1_m4.mp4`
3. 对照 `docs/STAGE33_M4_VISUAL_REVIEW.md`（逐镜"意图→决策→实际画面"表 + 12 项失败模式检查 + 运动语义审计）

裁决问题：**「3.3 P1 是否真的让 Coral 肉眼可见地变好了？」**
- 是 → 授权 P1 收口评估（是否 SEAL P1、是否进入 P2 修复列表：连续构图禁令、图表档扩展、motion 分布）；
- 否/部分 → 只报告问题，不自行修改、不调阈值、不进 P2。

**STOP。**
