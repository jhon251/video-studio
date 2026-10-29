# Stage 3.2b P0-7 Remediation Design / Root-Cause Review（仅设计，待授权后实施）

## 1. VO 1005 字/分 —— 根因证据

**实测数据（P0-1 产物）：**
- 20 段全部 **16.7–16.9 字/s**（标准差≈0.05），均匀度极高 → 说明是**全局时长先验**被错误标定，而非个别文本/合成异常；
- 参考音频 `build_v2/wav/S01.wav`：**47.36s / 204 字 = 4.3 字/s**（Huihui 自然语速，正常）；
- 参考文本 `build_v2/tts/S01.txt`：**204 字（全文）**；
- F5-TTS 预处理日志：`Audio is over 12s, clipping short.` → **音频被截到 12s，但 ref_text 仍为全文 204 字**。

**根因**：F5-TTS 的时长先验 ≈ ref_audio_duration / len(ref_text) = **12s / 204 字 ≈ 17 字/s**。参考音频被截断而参考文本未同步截断 → 每个生成段继承 ~16.7 字/s（1000+ 字/分）。证据链闭合：16.7 ≈ 17，且 20 段均匀。

**结论**：不是 F5 模型缺陷、不是中文分词问题、不是采样率/测量问题（sf 24000Hz 读数与 ffprobe 一致）；是**参考音文错位**。

## 2. VO 修复方案与目标速度（不擅自定速，供裁决）
- 方案 A（根因修复，推荐）：重建"对齐参考"——参考音频截取 12s 窗口，**ref_text 同步截取该窗口的实际字数**（约 52 字），或新录一段"目标语速参考 + 逐字一致文本"（如 Huihui Rate=-2 重读 12s 短文本）；F5 时长先验即恢复正常（≈4–4.5 字/s）。
- 方案 B（辅助微调）：F5 `infer(speed=…)` 参数（不动模型/不动 F5 资产本体，仅 adapter 传参）。
- 方案 C（排除）：对成品做 time-stretch（伤音质）。
- **目标速度范围建议**：**240–300 字/分（4–5 字/s）**；以参考语速 4.3 字/s（≈258 字/分）为自然锚点。最终取值由人工裁决。
- 预期：442 字 @4.3 字/s ≈ **103s ≈ 1:43** 成片。
- 硬约束：冻结 narration 逐字不变；不改稿；不删字。

## 3. Loudness pipeline 修复方案
- 现状：P0-1 对整段 voiceover 做过 loudnorm，但 P0-5 逐镜挂载**原始 segment**，loudnorm 未进入链路 → 成片 I=-20.8 LUFS。
- 修复（确定性，两选一，推荐 B）：
  - A：P0-5 逐镜装配时对每镜音频应用 `loudnorm=I=-16:TP=-1.5:LRA=11`（镜级统一）；
  - B：**P0-6 成片级 loudnorm**（concat 后、烧字幕前对整体音轨统一 loudnorm，最符合"final program loudness"语义）。
- 目标：成片 I ≈ −16 LUFS、TP ≤ −1.5dB、无 clipping。
- 不修改冻结稿/3.1.4；QC 保留该项检查。

## 4. Subtitle tail overflow 修复方案（只修时间边界，不动文字）
- 现状：末条字幕 end=26.432s > 成片 26.38s（约 0.05s，源于逐镜音频 `-t` 微裁）。
- 方案（确定性）：在 P0-3 输出前增加**成片时长钳制**——subtitle 生成时以 alignment 段时为准（保持 26.432 内部一致），在 P0-6 烧录后（或 P0-3 已知最终媒体时长时）对**所有字幕条目的 end 执行 `min(end, media_duration)`**；若末条因钳制导致 start≥end，则该条 end=media_duration 且 start 不变（差值≥0.01s 才保留）。
- 约束：不改变文字、不改变顺序、不产生 overlap（钳制只发生在最后一条，且用 `<=` 边界校验）。

## 5. Timeline contract 修订方案
四者关系重新定义：
- **production duration（真值）**：最终成片媒体实测时长（QC 探针值）；
- **measured VO duration**：segment 实测音频时长之和（P0-1 真值）；
- **nominal duration**：shotlist 名义时长，**仅作 planning/fallback metadata**，永不进入成片时长计算；
- **transition/gap duration**：可选（默认 0；仅在人工裁决需要时加入，并物化进镜头文件，而不是只存在于 alignment 汇总）。
- 契约规则：`production_duration = Σ(adopted_i) + Σ(gap_i)`，其中 `adopted_i = vo_measured`（无 VO 段才 fallback nominal）；alignment 的 `total_duration` 必须等于 P0-5 各镜 adopted 之和 + 实际物化的 gap 之和（消除当前 32.132 vs 26.38 的不一致来源）。

## 6. Gap / transition 处理策略
- 暂不加入固定 0.3s gap（裁决确认）。
- 当前镜边界 0.3–0.54s 静音 = VO 尾部自然呼吸，非缺陷；QC 的 silencedetect 阈值改为 d≥0.8s 才告警（**阈值调整属于 QC 判定标准修订，需你确认后实施**）。
- VO 语速修复后，重新评估是否需 0.3–0.5s 镜间缝（届时再裁决）。

## 7. 修改文件清单（仅 3.2b 内）
- `stage32b/vo.py`：参考音文对齐（截断文本或新参考）+ 可选 speed 传参；VO 重新生成仅此文件；
- `stage32b/assemble.py`（若选 loudnorm 方案 A）或 `stage32b/render.py`（若选方案 B）；
- `stage32b/subtitle.py`：末条 end 钳制；
- `stage32b/alignment.py`：total_duration 口径修正（=Σadopted+Σgap 物化值）；
- `stage32b/qc.py`：silencedetect 阈值、LUFS 检查项；
- `scripts/run_stage32b.py`：参数透传。

## 8. 不修改文件清单
2.x 全部；Truth/Evidence；Creator Style v2；冻结 narration；3.1.4 全模块与 SHA；Material Package；rights gate；semantic threshold 45；NO_SAFE_MATCH；F5-TTS/ffmpeg 实验资产本体；P0-1~P0-7 已有产物（修复后重新生成属于新产物）。

## 9. Regression plan
- 重跑：P0-1（新参考 VO）→ P0-2 → P0-3（含钳制）→ P0-4（复用）→ P0-5 → P0-6 → P0-7；
- 每阶段 Gate 全绿；2.x 13 套件 + SHA；3.1.4 SHA（B33B7310…）不变；
- 幂等与 fingerprint 校验沿用。

## 10. Final real-video acceptance plan
- 成片目标：442 字 @4–5 字/s ≈ 88–110s；I≈−16 LUFS；字幕无越界；镜间停顿自然；
- 重新输出 human_review 清单（时间点随新时长更新）；
- 人工裁决项：最终语速（240–300 字/分）、是否需要镜间缝、loudnorm 方案 A/B、silencedetect 阈值修订。

**本轮仅诊断与设计。等待授权后实施（先 VO 根因修复，其余随之重跑）。**
