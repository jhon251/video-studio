# Stage 3.3 V3-M3 Remediation R2 报告（G5/G6/G7 全 PASS）

> 状态：C revision 生成，机器 Gate 全 PASS，**STOP 等待人工观看裁决**（不进入 P2、不盲测、不 SEAL、不代判审美）。

## 1. R2 修复内容（只修 executor/审计，plan 未重跑）

| 项 | 修复 | 验证 |
|---|---|---|
| **F1 executor 分层 bug** | material beat 存在有效素材时底色层不再参与合成（底色只作无素材背板；z-order：底色 < 素材 < 色块 < 锚点词） | 新测试 `stage33_executor_layers_test.py`：素材 beat luma=136.1/std=41.2（不再退化为底色 34.6）、锚点可见、color-only 行为不变，5/5 PASS |
| **F2 jitter 三源分口径** | `transform_delta`（spec 轨迹：HOLD 必须全 0、运动必须整数单调）/ `content_delta`（视频素材内容，不算 camera jitter）/ `alpha_delta`（显隐台阶，按 alpha_frames 实际变化判定，stage 名仅提示）；尖峰检测排除 alpha 渐变边界 ±1 帧（appearance 量化台阶 ≠ geometric jitter）；0↔N 交替判据收紧为"中间帧 < 阈值×0.5"（防阈值边缘闪烁误报，真 0/1.84/0 模式仍必检） | 33/33 beats HOLD_OK |
| **F3 G7 文本检测** | 全分辨率（1920×1080）抽帧 + 调色板双色（白 #F4F8F9 与高亮橙 #FFB74D）检测；素材纹理判定 std<30 为缺失 | g7 PASS |
| **substring 审计** | NFKC 归一 + 全/半角标点都剥离 + 空白归一（此前 NFKC 把全角逗号转半角导致漏剥） | statement PASS |

## 2. 机器 Gate 终态（全 PASS）

| Gate | 结果 | 数据 |
|---|---|---|
| G5 jitter=0 | **PASS** | 33/33 HOLD_OK；transform 位移=0（HOLD 全恒定）；无 0↔N 交替；无方向反转；无尖峰（alpha 台阶已排除并记录） |
| G6 技术 QC | **PASS** | P0-6 10 项 + P0-7 13 项全绿：102.2s vs 102.199、VO↔字幕同步 0 违规、无黑帧/冻结、I=-17.7 LUFS、峰值 -2.1dB、字幕逐字/无越界、provenance+output SHA 一致 |
| G7 statement→frame | **PASS** | 素材纹理真实可见（F1 修复后）、锚点词调色板像素存在、enter 时序文字增长、层职责渲染 |
| anti_template | **PASS** | 0 违规 |
| statement | **PASS** | attention_target/graphic/锚点 全部原文真实 substring |

**分类栏（R2 要求）**：`REAL_RENDER_DEFECT = 0`；`AUDIT_TRUE_POSITIVE = 0`；`AUDIT_FALSE_POSITIVE = 0`（最终一轮审计无任何违规记录）。

## 3. 最终产物与 A/B/C 基线

| 版 | 路径 | SHA256 | 规格 |
|---|---|---|---|
| A = 3.2b legacy | `output/stage33/coral/legacy_3.2b.mp4` | 3C629B62…（SEAL 固化） | 102.10s / 1080p25 / aac 48k mono |
| B = P1 | `output/stage33/coral/stage33_p1_m4.mp4` | 56B1668A… | 102.20s / 同上 |
| **C = V3-MVP（本 revision）** | `output/stage33/coral/stage33_p1_v3.mp4` | **729814CB86C8160E945E94D376ABD5BF17731FF0EB5163CF61EB6782555FCAC1** | 102.20s / 同上（视频码率 583 kb/s——画面以静止为主，压缩效率正常） |

三版同冻结稿/VO/字幕/20 镜/时长口径/规格/响度链——**唯一变量=视觉表达**。
关键 SHA：plan_sha=`8262bb40…`（未变）；fingerprint=`35ad4b26…`；executor.py=`ACAF4BDD…`；motion.py=`2BACEFE9…`；visual_qc.py=`DFAC26D6…`。
失败的 duration C 已保留为 `stage33_p1_v3_INVALID_duration.mp4`（诊断物）。

## 4. 人工观看材料

- 抽帧（20 镜中帧 5×4，三版各一张）：
  - `output/stage33/coral/v3/review/sheet_A_legacy_20shots.png`
  - `…/sheet_B_p1_20shots.png`、`…/sheet_C_v3_20shots.png`
- 逐镜对照（statement → 画面机器证据 + attention handoff + 12 项失败模式 + 8 维评分表 + 三档裁决栏）：`docs/STAGE33_V3_MVP_VISUAL_REVIEW.md`
- 机器证据：`output/stage33/coral/v3/v3_gate.json`

## 5. 如实预告（机器不能代判的部分）

- C 版运动极克制：33 beats 中 21 个设计性静止 + 12 个"意图运动但能力降级→HOLD"——**画面以静止构图+锚点词淡入为主**。这是"静止优先 + 1px/帧整数门槛"的既定结果，但"大量静止是否有明确视觉焦点与层级"必须由您观看裁决（重点镜 S01/S06/S08/S10/S13–S16/S18/S20）；
- 机器 Gate 只证明"正确地执行了计划"，不证明"好看"；
- 最终问题仍是：**V3 的实际画面有没有真正摆脱 P1 的"PPT + 无意义运动"？**

## 6. STOP

- 不进入 P2；不做盲测；不自动 SEAL；不代判审美。
- 等待您的三档人工裁决：`CLEARLY_BETTER` / `BETTER_BUT_NOT_ENOUGH` / `NOT_MEANINGFULLY_BETTER`（附证据镜头）。
- 若裁决"不明显优于 P1"，按既定纪律转入能力天花板诊断（素材供给 → 视觉理解 → 生成/画面供给 → 摄影剪辑先验 → 视觉质量评估 → 渲染表现层），不再堆模板/规则。
