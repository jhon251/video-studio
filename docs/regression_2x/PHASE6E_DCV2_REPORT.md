# Duration Contract v2 实施报告（Pipeline Duration Contract v2）

- 阶段：**6-E / Duration Contract v2 实施**（方案 A：**真实 TTS actual duration 成为 narration 事实时基**）
- 授权前提：`declared_duration` = 规划估计；`actual TTS duration` = narration 事实；
  `audio_time_base` = 生产权威；**不**为匹配 declared 而拉伸/填充真实旁白。
- 本阶段**只修 pipeline**：不重制 v9、不执行 E1/E2/E3/E4/E5、不改历史 baseline/tag、不 promote。
- 结论：**实现完成；真实 E2E（真实 edge-tts + 真实渲染 + 真实 PI）21/21 通过**；受影响既有套件全部恢复绿。

---

## 1. 修改文件清单

指纹：`6e2 → 422 文件 2c6c7ab9d056be52` → **`dcv2b → 423 文件 b8dff1a8b496b339`**

| 类型 | 文件 | 说明 |
| --- | --- | --- |
| 改 | `src/video_studio/core/narration.py` | v2 权威层：`audio_time_base_s` / `audio_segment_windows` / `segment_drift` / `cumulative_drift` / `planning_drift_report`（PLANNING_DRIFT，**不阻断**）/ `narration_plan` / `check_narration_padding` / `timeline_audio_consistency` / `subtitle_alignment`；`script_time_base_s` 降级为 **planning-only** |
| 改 | `src/video_studio/agents/voice/agent.py` | 记录真实时长 + `audio_time_base_s` / `audio_segment_windows` / `planning_drift` / `padding_budget_s`；**fail-closed**：实际时长不可测（`NARRATION_DURATION_UNMEASURABLE`）或拼接不一致（`NARRATION_CONCAT_MISMATCH`）⇒ 不得声称完整 |
| 改 | `src/video_studio/agents/editing/agent.py` | 时间轴权威切到 `audio_time_base`；场景窗口由实际时长派生（`segment_durations`）；字幕用实际音频窗口；`_narration_args` 总长 = v2 权威；`apad` 受 pause budget 约束（超预算阻断）；pre/post 门禁接入 v2 plan/cues/padding |
| 改 | `src/video_studio/core/captions.py` | `build_cues(..., windows=...)`：cue 基于**实际音频窗口**，绝不越过实际旁白 |
| 改 | `src/video_studio/core/integrity.py` | 新门禁 `segment_alignment_v2`(G-SEG) / `timeline_audio_consistency_v2`(G-TL) / `planning_drift_metric` / G-PAD / G-SUB；`pre_render_gate` 接入 `narration_plan`（v2 语义：PI-1/PI-2 以**语音专属时基**计算）；`post_render_gate` 新增 **promote 静音阻断** 与 v2「**仅拦超出已声明预算的静音**」 |
| 改 | `src/video_studio/core/bgm.py` | `mix_filters` 记录 `narration_pad_s` / `padding_budget_s` / `narration_pad_within_budget`（不再让 `apad` 无声掩盖短缺） |
| 改 | `tests/narration_contract_test.py` | B7 断言按授权更新为 **v2 语义**（原「较短⇒标记需补齐」已被 v2 权威替换），业务语义未放松 |
| 改 | `tests/directorial_round2_test.py` | T0e 过期期望修正（登记链含此前治理层追加的 E2 v2 条目：5 条原始 + 1 条 v2） |
| 新 | `tests/duration_contract_v2_test.py` | **v2 单元/回归 27 项**（覆盖授权书 9 类场景） |
| 新 | `docs/regression_2x/phase6e_dc_v2_e2e.py` | **真实全新项目 E2E**（真实 TTS + 真实渲染 + 真实 PI） |
| 新（证据） | `docs/regression_2x/logs/phase6e_dc_v2_e2e.json`、`phase5m_code_fingerprint_dcv2b.json` | E2E 报告 + 指纹 |

**未被触碰**：`core/semantics.py`、`core/multimodal.py`、`core/mm_*.py`（冻结评测栈，指纹核对 = NONE）、`ops/integrity.py`、
v9 / C1–C4 / E1 / E2 候选 / `docs/regression_2x/baseline/*` / 任何 tag。

---

## 2. 设计（唯一可信时长权威链）

```
script(planning estimate, 仅参考)
   → TTS(逐段实测 dur_i)
   → audio_time_base = Σactual_i + pause_budget×(n−1) + trailing_pad     ← 唯一权威
   → timeline（由 audio_time_base 派生；场景窗口 = 实际时长 + 停顿预算）
   → cues（贴 actual 语音窗口；不越过旁白结束）
   → mix/render（apad 只覆盖已声明 pause budget）
   → PI（pre：G-SEG/G-TL/G-PAD/G-SUB；post：PI-3 静音 + promote 阻断）
```
- `declared` 只出现在 `PLANNING_DRIFT`（可审计，`blocking=false`）。
- **兼容开关**：仅当 voice 产物带 `audio_time_base_s`（v2 产物）时启用 v2 门禁；
  历史 v1 产物/合成 fixture 保持 v1 语义 ⇒ **不追溯破坏**已产出链路。
- 参数：`pause_budget_s = 0.75`（可被 `editing.narration_pause_budget_s` 覆盖）、`trailing_pad_s = 2.0`、
  `timeline_audio_tolerance_s = 0.5`、`concat_tolerance_s = 0.5`。

**核心不变式**（v2 下恒成立）：`audio_time_base == 实测旁白音轨时长 + 授权 pause budget`（±0.05 s）；
E2E 实测：`24.26 == 20.76 + 3.5` ✓。

---

## 3. 新增硬门禁定义

| ID | 名称 | 规则 | 位置 | 失败 |
| --- | --- | --- | --- | --- |
| **G-SEG** | 段级对齐（`segment_alignment_v2`） | `audio_time_base` 必须可算；逐段实际时长齐备；窗口单调不重叠；拼接一致（±0.5 s） | pre-render | **BLOCKED** |
| **G-TL** | 时基一致（`timeline_audio_consistency`） | `timeline_total == audio_time_base ±0.5 s` | pre-render | **BLOCKED** |
| **G-PAD** | 补齐预算（`check_narration_padding`） | `apad ≤ 授权 pause budget + trailing`（默认 1e-6 容差） | pre-render + bgm | **BLOCKED** |
| **G-SUB** | 字幕↔实际音频对齐（`subtitle_alignment`） | ① cue 展示时间 ≥98% 落在实际语音窗口；② 末条 cue 越过旁白结束 ≤1.0 s。**语音被字幕覆盖率仅作度量报告项**（与冻结 PI-5 政策一致，不阻断） | pre-render（+post 用同一 cue 表） | **BLOCKED** |
| **PROMOTE** | 静音 promote 阻断 | PI-3 未 PASS ⇒ `promote_blocked=true`（成片可留作人工审查，但**禁止 promote**） | post-render | **禁止 promote** |
| **PI-1/PI-2（v2 口径）** | 覆盖率/双侧时长 | 以**语音专属时基**（`timeline − 已声明预算`）计算，避免把已声明停顿误判为短缺 | pre-render | **BLOCKED** |
| **PLANNING_DRIFT** | 规划偏差诊断 | `declared vs actual` 偏差，**永不阻断** | pre-render（记录） | — |

---

## 4. 单测与回归结果

| 套件 | 结果 |
| --- | --- |
| **`tests/duration_contract_v2_test.py`（新）** | **27/27 rc=0** — V1 actual<declared、V2 actual>declared、V3 多段累计 drift、V4 zero/invalid TTS、V5 字幕越过实际音频、V6 padding 超预算、V7 尾部静音 + promote 阻断、V8 timeline/audio 不一致、V9 **真实 v9 数据回放**（declared 1532.0 / actual 961.656 / 需补 570.3 s ⇒ v2 下 fail-closed）+ G0/G1 门禁接线 |
| `narration_contract_test` | 45/45 rc=0（B7 按授权更新为 v2 断言） |
| `captions_test` | 21/21 rc=0 |
| `bgm_ducking_test` | 48/48 rc=0 |
| `integrity_test` / `integrity_gates_test` / `integrity_truth_test` | 28/28、45/45、**243/243** rc=0 |
| `maintenance_fixes_test` | 30/30 rc=0 |
| `execution_reliability_test` / `directorial_batch_test` / `directorial_round2_test` | 75/75、78/78、**67/67** rc=0 |
| 冻结评测栈 | 未触碰（指纹核对 = NONE） |

> 说明：v2 门禁首次接入时对 **v1 合成 fixture** 造成追溯性阻断（4 个套件变红）。已按"v2 是新契约、不追溯破坏历史产物"的原则加 **兼容开关**（以 `audio_time_base_s` 为界），4 个套件全部恢复绿；仅 `narration_contract_test` 的 **B7** 因授权变更语义而更新断言（已披露）。

---

## 5. 真实全新测试项目 E2E 结果（`mock_tts_used = false`）

- 项目：**`p_dcv2_20260929_094959`（全新，非生产）**；工作区 `output/phase6e_dc_v2_e2e/<ts>/`
- 真实 TTS：**edge-tts `zh-CN-XiaoxiaoNeural`**，3 段，用时 14.6 s
- 权威链实测：
  | 项 | 值 |
  | --- | --- |
  | declared（脚本声明） | **62.0 s** |
  | actual（逐段实测） | **[7.032, 7.032, 6.696] = 20.76 s** |
  | pause budget ×2 + trailing | 1.5 + 2.0 = 3.5 s |
  | **audio_time_base（权威）** | **24.26 s** |
  | 实测旁白音轨 | 20.76 s（== Σactual，拼接自洽） |
  | **PLANNING_DRIFT** | **39.24 s（blocking=false）** |
  | 契约 policy | **`audio_time_base_v2`**、`audio_padded_to_timeline=false` |
- 真实渲染：**SUCCEEDED**；成片 `output/t_render_draft.mp4`，**时长 24.267 s ≈ audio_time_base**（旧行为会被拉到声明 62 s）
- 门禁状态（落盘证据）：`PI-1/PI-2/PI-3/PI-4/PI-5/PI-6 = PASS`、`G-TL/G-PAD/G-SUB = PASS`、`PLANNING_DRIFT = PASS`、
  `pre_render.blocked=false`、`post_render.blocked=false`、无 `PROMOTE_BLOCKED`
- **字幕↔实际语音**：v2 末条 cue **21.364 s**（v1 同片会到 **45.8 s**，越过旁白）；渲染烧录的 ASS 3 条 cue **全部落在实际音频窗口内**；
  抽帧：语音时刻（t=2.0 s）字幕白字像素 **8,500**、尾部 pause 区（t=23.26 s）**0**
- 历史完整性：v9 / C1–C4 / E1 / E2 候选 sha256 **全未变**；baseline 目录未变；无 promote
- **21/21 通过**；报告：`docs/regression_2x/logs/phase6e_dc_v2_e2e.json`

---

## 6. 新旧时基行为对比

| 维度 | v1（旧：declared 权威 + apad 补齐） | v2（新：audio_time_base 权威） |
| --- | --- | --- |
| 时间轴总长 | 由声明时长决定（v9：1532 s） | `Σactual + pause budget + trailing`（v9 同数据 ≈ **978.7 s**） |
| 旁白短缺处理 | **`apad` 补齐到时间轴**（v9：570.3 s 静音掩盖） | 只允许 pause budget（17 s）；超出 ⇒ **G-PAD fail-closed** |
| 字幕时间基 | 声明时长分摊 ⇒ 漂移（v9 末端 **568.3 s**、960 s 后无旁白仍有字幕） | 实际音频窗口 ⇒ 零漂移；不越过旁白 |
| 覆盖率/时长门禁 | PI-1/PI-2 以声明的整段时间轴为基准 ⇒ 短旁白被误判/掩盖 | PI-1/PI-2 以**语音专属时基**计算；G-SEG/G-TL/G-PAD/G-SUB 独立把关 |
| declared≠actual | 记录但不阻断（且被 apad 掩盖） | **PLANNING_DRIFT**（可审计，不阻断） |
| 静音 | `apad` 造成长尾静音却"文件长度正确" | post-render 只拦**超出已声明预算**的静音；PI-3 未 PASS ⇒ **禁止 promote** |
| E2E 实测（新项目） | — | 声明 62.0 s → 权威 24.26 s、成片 24.267 s、全部 PI/G PASS、字幕 21.364 s 对齐 |

---

## 7. 对 v9 lineage 的影响

- **v9 及其全部后裔候选（C1–C4、E1、E2）仍带原缺陷**（音轨 570.3 s 静音、字幕漂移）：
  本阶段**未**重制、**未**修改、**未** promote；它们可继续作为**历史证据**与静帧比对素材，但**不能**作为"旁白/字幕正确"的基准。
- **v2 不追溯破坏**：兼容开关保证历史 v1 产物（无 `audio_time_base_s`）仍按 v1 语义处理 ⇒ 既有执行/审计链路不会被追认失败，
  但**也不会被追认为合规**（它们的问题已由 `6E-E2-SUBTITLE-DEFECT-v1` 记录在案）。
- **需要重制才能合规**：v9 母版成片、C1–C4、E1/E2 候选（以及任何按 v9 时基计算的 timeline/cues/ducking 窗口）。
  重制**不需要**重录旁白（TTS 音频是事实来源）、**不需要**重下素材；但**需要**重排镜头窗口与重烧字幕、重新渲染。
- **E2 的叠加层目标窗口失效**：E2 提案的 S05 `[245,300]` 定义在被修正前的时基上 ⇒ 重制后需重新定位并重新审批。
- **baseline/tag**：未改动；如需重切必须另行人工授权。

---

## 8. 遗留与未决（诚实标注）

1. **BGM 真实素材**：E2E 未引入外部 BGM 素材，只对 `mix_filters` 的 v2 证据（补齐预算/ducking 区间）做接线验证；
   带真实 BGM 的端到端（含响度母带）仍由既有 `bgm_ducking_test`（48/48）覆盖。
2. **PI-5 覆盖率语义未变更**：字幕显示覆盖率仍为度量报告项（沿用冻结政策），v2 只新增"字幕不得出现在无语音处/不得越过旁白"的阻断判据。
3. **`pause_budget_s` 取 0.75 s 为默认**：真实成片是否合适需人工在重制时确认（可按 `editing.narration_pause_budget_s` 调整）。
4. **未做**：v9 lineage 重制、baseline 重切、E1–E5 执行、promote。

**STOP —— 等待下一阶段授权（是否重制 v9 lineage / 重切 baseline / 继续 E3–E5）。**
