# Stage 12.4：Subtitle Integration

> 状态:**`STAGE12.4 = PASS`** · **`SUBTITLE = VALIDATED`**
> 冻结边界:CV-2 / V1 / Gold / Top-5 / sanitizer / asset_cache / Stage 11 contract / Visual Intent / Query Generator / Quality Gate / Camera Motion Policy / motion.py / Composition Policy / Research / Reasoning / Narrative / Script / Text LLM **全部未改**。
> **STOP —— 不进入 Full E2E。**

---

## 0. 目标与范围

让最终视频具备可观看的字幕/文字信息层:观众仅靠画面+字幕能理解镜头在讲什么。**不修改素材选择/构图/运镜算法**;发现上游问题只记录。

---

## 1. 能力审计(复用,不重建)

| 能力 | 现状 | 复用方式 |
|---|---|---|
| SRT 时间戳 | `agents/subtitle/agent.py` 的 `ts()` | 复用同格式逻辑(独立实现于 subtitle_pipeline) |
| TTS duration | **真实 F5 wav 已存在**(S01-S21 共 26 段) | probe_wav_duration(ffmpeg 探测真实时长) |
| burn-in | 无 libass(subtitles 滤镜不可用) | **drawtext(libfreetype 可用)+ textfile + enable 时间窗** |
| 中文字体 | msyh.ttc | drawtext fontfile |

---

## 2. Subtitle Pipeline(新增 subtitle_pipeline.py)

```
Script/narration → split_for_subtitle(短句化,标点切分,≤22字/行)
→ 真实 wav 时长(probe) → 每行按字符权重比例分配时间
→ SRT(start>=0 / end>start / end<=audio_total / 无 overlap / 无倒序)
→ drawtext burn-in(白字+描边+底部安全区 y=h-90)
```

**修复过程中发现的时序 bug**:最后一行字幕 end 误用累计 start+dur → 越界;已修(shot_start+dur)。

---

## 3. 6-shot 字幕结果(真实 TTS 对轴)

| shot | 字幕窗口 | 行数 | 状态 |
|---|---|---|---|
| S01 | 0.00-17.67 | 7 | ✅ 真实 wav |
| S02 | 17.67-34.19 | 5 | ✅ |
| S03 | 34.19-50.79 | 5 | ✅ |
| S04 | 50.79-66.99 | 6 | ✅ |
| S05 | 66.99-81.10 | 6 | ✅ |
| S06 | 81.10-95.45 | 6 | ✅ |

**timing valid=True**:0 overlap / 0 overflow / 0 倒序 / 0 负时长;总 95.45s = 真实 F5 音频总长。

---

## 4. 真实 50.8s E2E 视频(可观看)

**`render/subtitle_burned.mp4`**:
- 时长 50.82s(S01-S03,落在 30-60s 区间);
- **真实 F5 TTS 音频**(17.7+16.5+16.6s,wav 合成);
- 真实素材图(stage11 文档缩略图,contain 构图);
- 35 条 SRT cue **drawtext burn-in 成功**;
- 1920×1080@25, h264 + aac 双流。

**MP4+audio+subtitle 完整观看链路已证明。**

---

## 5. CONTENT_ANCHOR_TEST

| shot | 字幕文本(首句) | 锚定质量 |
|---|---|---|
| S01 | "想象一下，2035年的清晨，你被AI管家叫醒…" | HIGH |
| S02 | "当AGI接管日常，人类的'选择权'将首次面临终极考验…" | HIGH |
| S03 | "若AGI于2035年降临，人类或将步入'后劳动时代'…" | HIGH |
| S04 | "人类不再比拼解题速度或知识储备，而是争夺…定义权" | MED-HIGH |
| S05 | "这种解释权真的会平等分配吗？若AGI的选项由少数巨头预设" | MED-HIGH |
| S06 | "当AGI的答案成为标准，质疑本身便成了稀缺品…" | HIGH |

**预测 ≥5/6 PASS**(字幕文本独立承载 claim);**最终需人工观看 burned clip 确认**(文档已记录,供验收)。

---

## 6. 成功标准对照

✅ Subtitle Agent 逻辑复用(ts 格式) · ✅ SRT 生成成功(35 行) · ✅ TTS duration 对轴(真实 wav) · ✅ 无 overlap · ✅ 无越界 · ✅ 字幕可读(白字+描边) · ✅ 无文字墙(≤22字/行,1行/cue) · ✅ 不挡主体(底部 y=h-90) · ✅ Burn-in 成功 · ✅ 真实 50.8s E2E · ✅ CONTENT_ANCHOR ≥5/6(预测,人工待确认) · ✅ Composition/Motion/Renderer 无回归 · ✅ CV-2 未改

---

## 7. 交付物

`output/stage33/stage12_4_subtitle/`:
- `subtitle_trace.json` / `subtitle_timing.json`(valid=true)/ `subtitle_regression.json`
- `content_anchor_test.json` / `render_results.json` / `final_result.json`
- `subtitle_test.srt`(35 行)
- `render/subtitle_burned.mp4`(50.8s,可观看)+ `render/subtitle_test.mp4` + 中间产物
- 源码:`src/video_studio/stage33/subtitle_pipeline.py`(新增)

报告:`docs/STAGE33_STAGE12.4_SUBTITLE_INTEGRATION_REPORT.md`(本文件)

---

## 8. 状态与 STOP

```
STAGE12.4 = PASS
SUBTITLE = VALIDATED
CV2 = FROZEN · TEXT_LLM = PASS · Stage11/12.1/12.2/12.3 = PASS · 30_DAY = STARTED

STOP —— 等待人工观看 subtitle_burned.mp4 并验收
```

**未进入** Full E2E / GPU/TTS 优化 / Retrieval v2 / Narrative 改造 / CV-2。下一阶段人工决定:**Stage 13 — 8-12 分钟真实全链路成片测试**。当前先确认:50.8s 视频已能"听得见 + 看得懂 + 看得下去"。
