# Stage 3.2b Implementation Design Review（设计审查稿 · 待授权后实施）

> 状态：仅设计。未修改 2.x / 3.1.4 / 实验资产；未进入编码。
> 上游问题只报告：**当前仓库中不存在 3.2a 的剪辑工程/时间轴草稿产物**（3.2a 仅有设计稿 `docs/ROADMAP_NEXT_STAGE.md`）——见 §0。

## §0 输入缺口报告（上游问题，只报告不擅改）
用户契约假设 3.2a 已产出"剪辑工程/时间轴草稿"。本仓库实际状态：
- 存在：2.x 冻结口播稿、3.1.4 Material Package（含《珊瑚礁正在消失》20 镜 `material_pkg_real`）、shotlist、3.2a 设计稿；
- 不存在：任何 3.2a 时间轴草稿/EDL/剪辑工程文件。
**设计决策（供裁决）**：3.2b 定义一套最小 Timeline 输入契约（timeline.json），并内置一个"3.2a-lite 适配器"：当 3.2a 产物缺失时，由 shotlist + 3.1.4 shot_mapping 直接构造 timeline 草稿（镜头顺序/素材引用/状态继承），该适配器**只读上游、只生成 3.2b 自己的中间产物**，不写回任何封包。

---

## 1. 输入契约（只读）
| 输入 | 来源 | 用途 |
|---|---|---|
| narration（冻结口播稿） | 2.x 产物（珊瑚稿为 `output/stage31_realworld/coral/V2_FINAL_SCRIPT_JARVIS.md`） | VO 文本、字幕文本、narration hash |
| shotlist（S01–S20 + duration_hint） | 2.x/测试包 | 镜头顺序与名义时长 |
| Material Package（shot_mapping + metadata + rights + materials/ 预览） | 3.1.4 SEALED 产物 | Primary/ALT/状态/license/attribution/预览图 |
| timeline.json（可选） | 3.2a 产物（当前缺失→由 3.2a-lite 适配器生成草稿） | 镜头→素材→时长装配表 |
| VO 参考音色（可选） | 人工提供；缺省用现有 F5-TTS 冒烟参考 | 声音克隆参考 |
以上全部只读；3.2b 不写回任何输入。

## 2. 输出契约（production/ 交付包）
见 §十一目录结构（final.mp4、subtitles.srt/ass、voiceover.wav、audio/segments、timeline/final_timeline.json、materials/、provenance/、manifests/、qc/、README.md）。

## 3. 目录结构（新增，全部在 output 下，不触碰封包）
```
output/stage32b/coral/
  build/            # 中间产物（segments、临时视频/图片副本、ffmpeg 中间）
  production/       # 最终交付包（§十一结构）
  manifests/        # input_manifest / render_manifest / alignment_manifest
  qc/               # qc_report.json / qc_report.md
```
命名：`production/` 为交付；`build/` 可重放可删除；`manifests/` 记录输入指纹与命令。

## 4. VO 数据结构
```json
{"segments": [{"id": "VO_S01_001", "shot_id": "S01", "text": "…冻结原文…",
  "audio_file": "audio/segments/VO_S01_001.wav", "sample_rate": 24000,
  "engine": "f5-tts|huihui-tts", "model_ref": "…", "start": 0.0, "end": 4.2,
  "duration": 4.2, "status": "OK|ERROR"}], "total": {"file": "voiceover.wav", "duration": …}}
```
segment = 一句话（按口播稿标点切分）；文本必须与冻结稿逐字一致（hash 校验）。

## 5. word/segment timestamp 结构
segment 级时间戳（本阶段不做词级强对齐）：
```json
{"segment_id": "VO_S01_001", "text_hash": "…", "start": 0.0, "end": 4.2,
 "duration": 4.2, "source": "tts_measured|tts_estimated"}
```
F5-TTS/Huihui 生成的音频以 ffprobe 实测时长为准；估计值仅用于预排，最终以实测对齐。

## 6. 字幕结构
- SRT：`序号 / 00:00:00,000 --> 00:00:04,200 / 文本`；长句按 ≤20 字拆行、时间按比例分配；不重叠；总覆盖 = VO 总时长。
- ASS：Dialogue 事件 + 最简样式（黑边白字、底部居中、字号 54、无动画）。文本一律取冻结稿，禁止改写；字幕不得出现稿外事实。

## 7. timeline 与 VO 对齐策略
- 原则：**口播顺序优先**。镜头顺序 = shotlist 顺序不变；每个镜头的实际时长 = 该镜头全部 segment 的实测时长之和（+ 镜尾 gap 0.3s）；shotlist 的 duration_hint 仅作 fallback。
- 无 segment 的镜头（BLOCKED 类）使用其名义时长或最短 4s 文字卡时长。
- 输出 `alignment_manifest.json`：shot_id ↔ segment_ids ↔ start/end（成片时间轴）↔ 素材引用 ↔ 状态。

## 8. 图片 duration 策略
- 图片 clip 时长 = 该镜头实际 VO 时长（与 segment 对齐）；VO 缺失时 = min(名义时长, 6s)。
- 添加简单 Ken Burns（zoompan 慢速 1.00→1.06，禁用复杂动效）；无 VO 的图片镜头以 4–6s 定格。

## 9. 视频 In/Out 策略
- 视频素材：In=0，Out=min(clip 需求时长, 源时长)；不得超出 source duration（QC 拦截）；无源时长时默认取 8s。
- 视频一律 `scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2` 统一画布，禁止变形拉伸。

## 10. BLOCKED / NEEDS_REVIEW 行为（安全边界）
- 状态来源：3.1.4 mapping 中 NO_SAFE_MATCH / note；3.2a 时间轴中 BLOCKED 标记。
- 处理顺序：A 自制文字卡（GENERATED）→ B 自制简单图形（色块+标题）→ C 自录占位（人工）→ D 人工占位卡。
- 一律记录 `BLOCKED_REASON / FALLBACK_TYPE / HUMAN_ACTION_REQUIRED`；生成物标记 `SELF_CREATED`，绝不伪装成外部素材；**绝不**降阈值/用 UNKNOWN/UNSAFE/网上抓图。

## 11. attribution 进入交付包
- `provenance/attribution.txt`：每条成片使用的外部素材（SAFE/CONDITIONAL）按 3.1.4 rights_summary 生成署名行（作者 + license + 来源 URL）；CONDITIONAL 必署；片尾可加一页署名汇总（由 timeline 末尾字幕卡承载，不另做创意设计）。
- `provenance/materials.json`：clip→material_id→source/license/attribution 全链。

## 12. QC 数据结构
```json
{"video": {"exists":…, "decode":…, "duration":…, "resolution":…, "fps":…, "codec":…, "black_frame_rate":…},
 "audio": {"stream":…, "duration":…, "clipping":…, "silence_ratio":…, "loudness_lufs":…, "sample_rate":…},
 "timeline": {"order_ok":…, "overlap":…, "clip_duration_legal":…, "inout_legal":…, "vo_align_ok":…},
 "subtitle": {"srt_parse":…, "ass_parse":…, "time_legal":…, "no_overlap":…, "coverage_ok":…},
 "provenance": {"clip_to_material_ok":…, "attribution_complete":…},
 "truth": {"narration_hash_match":…}}
```
QC 只报告，不自动修片。

## 13. FFmpeg pipeline（确定性优先）
```
阶段1 素材规范化：copy → scale/pad → 时长裁剪（复用 bin/ffmpeg.exe）
阶段2 VO：segments → concat（filter_complex concat n=…:a=1）→ loudnorm(I=-16,TP=-1.5) → voiceover.wav
阶段3 镜头装配：每镜头 [视频/图片 + 对应 VO 段] → 单镜 mp4（libx264 crf 20, 1080p25, aac 48k）
阶段4 合成：filter_complex concat n=镜头数:v=1:a=1 → 烧录字幕(ass) → +faststart → final.mp4
```
所有命令写入 render_manifest.json（含版本、输入 SHA、命令与参数）；同输入重跑输出内容 deterministic（固定 fps/crf/顺序，不用随机）。

## 14. 错误分类
`VO_SYNTH_FAILED` / `SOURCE_MISSING` / `LICENSE_UNSAFE`（理论上被上游拦截）/ `FFMPEG_FAILED` / `QC_FAILED_VIDEO|AUDIO|SUBTITLE|TIMELINE` / `INPUT_HASH_MISMATCH` / `RATE_LIMIT`。错误即停该阶段，写 ERROR 报告；不静默跳过（VO 失败尤其必须显式 ERROR）。

## 15. retry 策略
- VO 合成：单 segment 失败重试 2 次（同参数）；仍失败→该 segment 标 ERROR，**不静默跳过**，流程进入可报告错误态（人工可单独重跑该 segment）。
- FFmpeg：命令失败重试 1 次；失败保留日志与中间文件。
- 网络：本阶段不依赖网络（素材已在本地/URL 缓存），如需补下载走 3.1.4 退避约定。

## 16. 允许修改的文件
- 新增：`src/video_studio/stage32b/`（renderer 新模块）、`scripts/run_stage32b.py`、`tests/stage32b_*.py`、`docs/STAGE32B_*.md`、`output/stage32b/**`（本阶段自有产物）。
- 适配器 wrapper 包装 F5-TTS/ffmpeg（不改实验资产本体）。

## 17. 绝对禁止修改
2.x 冻结链与口播稿、Truth/Evidence、Creator Style v2、3.1.4 SEALED 全部模块与 SHA、3.1.4 Material Package、rights gate、阈值 45、NO_SAFE_MATCH、ranking/retrieval/provenance、3.2a 设计稿、F5-TTS/ffmpeg 实验资产本体。

## 18. 幂等/可重跑策略
- 每阶段产物带输入指纹（narration hash + shotlist hash + material_package hash）；指纹不变则跳过已完成阶段（除非 --force）。
- 中间产物写 build/，可整体删除重放；交付包 production/ 每次全量重建（旧产物先归档为 .prev 或由 --force 覆盖）。
- 随机源禁用（固定 seed/crf/fps）；时间戳由实测时长确定。

## 19. Gate 映射（§十四 16 项）
G1–G16 全部纳入 `scripts/run_stage32b.py --gate`：输入完整→VO→timestamp→字幕→对齐→BLOCKED 安全→FFmpeg→decode→音频 QC→字幕 QC→provenance→narration hash→2.x 回归→3.1.4 SHA→交付包完整→人工观看（REAL_VIDEO_REVIEW 清单输出）。任一 P0 失败即 STOP 报告，不 SEAL。

## 20. 真实验收对象
《珊瑚礁正在消失》20 镜（3.1.4 material_pkg_real）为第一条生产视频；VO 引擎默认 F5-TTS（参考音色用现有冒烟参考），失败单句显式 ERROR；如无人工提供参考音色，回退 Huihui TTS 并如实记录 provenance。

---

**结论：设计审查完成，等待授权。授权后按 P0（VO→对齐→字幕→BLOCKED 处理→装配→QC）顺序实施；每阶段完成 STOP 报告。**
