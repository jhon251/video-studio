# F12/F13 终审交接笔记（Phase 57 + 57 续 · 2026-10-11）

## 交付物（第六次终审对象，两版并排）
- **F12（基线画面版）**：
  `projects/p_3e9292101f10/output/t_3553b076b02d_draft_with_outro_v2.mp4`（697.534s）
- **F13（黑板主线画面版，与 F12 唯一差异 = 10 抽象景换黑板主线图）**：
  `projects/p_3e9292101f10/output/t_483813d58447_draft_with_outro_v2.mp4`（697.534s，
  四门 9/9 同口径复测通过，`logs/p57_5_delivery_candidate.jsonl`）
- **对照基线**：同目录 `t_158db818a8b3_draft_with_outro_v2.mp4`（F10.1）——
  F12 与 F10.1 **逐景素材 36/36 一致、音轨逐字节一致**，唯一变量 = 字幕层。
- **F14（全片视频版，与 F13 唯一差异 = 15 景换专属 Pexels 视频）**：
  `projects/p_3e9292101f10/output/t_7968f9ac5fe7_draft_with_outro_v2.mp4`（697.534s，
  四门 9/9，`logs/p58_4_delivery_candidate.jsonl`）——**36 景 = 36 独立素材（零复用）**。
- 终审三个画面方向二选一：**F10.1 旧栈 / F13 黑板主线 / F14 视频版**；
  字幕跟嘴已在 F12/F13/F14 同源通过（独立口径四门）。

## 本次修了什么（与 F10.1 的差异 = 仅 cue 层）
1. cue 单一分发链：`build_cues_from_words_exact`（P55 验证版）的产物不再被
   旧词级路径覆盖（F10.1 的 105-cue-178s 直接死因，"测试修了、生产没接"第五例）；
2. 生产断言（构建后烧录前 fail-closed）：跨度 ≈ 音频 ±2s / median ≥3s / 重叠 0 /
   条数 101–111；
3. 连带修复三个静默缺陷：P56-2 pins 块 silent-kill（自登记起未生效）、
   句中切景钳制（句尾语音无字幕 31 处 / 61.45s）、尾句重分（10 句无自己的 cue）。
   详见 `docs/regression_2x/logs/p57_erratum.json`（D1–D5）。

## 烧录实测门（独立口径：烧录 ASS + 成片混音，禁止循环）
- 覆盖 **100.0%**（≥95%）｜时长 median **5.400s**（≥3s）｜=1.0s±0.1 cue **0**｜
  同时活跃 max **1**、重叠 **0**｜句起点同步 median **0.0030s**、>1s **0**（句 111）
- 3 景帧检字幕带 3/3（`output/p57_frames/`）
- 证据：`logs/p57_3_four_gates.json`、`logs/p57_4_delivery_candidate.jsonl`、
  渲染日志 `output/p40_probe/render_f12.log`

## 终审裁决点
1. **字幕跟嘴**（本次主裁决）：字幕出现/消失是否与语音同步、句尾不再提前消失、
   长句跨镜头不再断字幕。
2. 字幕文本与旁白逐句一致（111 句 = 全句数，含此前被吞的段尾句）。

## 备注
- erratum：F6–F10.1 的字幕门为构建器自测（循环论证第四例）；F12 起以烧录 ASS
  为唯一口径。**F10.1 的登记数值未改写**（append-only）。
- 材料包 v6（`p57_merged_payload.json`，65 张含黑板主线）校验 65/65 完好；
  F13 即用它渲染。**F10.1 原始 pins 备份**：`logs/p56_2_f9_pins.f10_1_backup.json`
  （当前 `p56_2_f9_pins.json` 已换成 F13 pins——重渲 F12 前需先还原）。
- 中间无效渲染隔离于 `output/_quarantine_p57_*`（审计留痕，非交付物）。
- 全量回归串行一次：`docs/regression_2x/logs/suites_summary.json`（81 套件全过）。

## 视频素材接入状态（P58 垂直切片已完成，2026-10-11）
- **已通**：Pexels Videos 采集（8 景 / 30.2 MB 入池）、建池 ffprobe 可用性、
  渲染装配**视频条**（裁剪/定格/时长契约/旁白优先不变）、帧检视频参照；
  `tests/p58_video_material_test.py` 10/10；1080p 真视频探针 rc=0。
- **F14（全片视频版）待终审裁定画面方向后放行**：需扩充全片查询表、
  定视频锚定策略、实测全片渲染时长。证据：`logs/p58_vertical_slice.json`。


## 发布阶段（2026-10-11 续：人工裁定 F14 方向后）
- **发布候选 = F14.1（F14 + BGM）**：
  `projects/p_3e9292101f10/output/t_a2afaba91eeb_draft_with_outro_v2.mp4`（697.534s，
  113.4 MB，四门 9/9，`logs/p58_5_delivery_candidate.jsonl`）。
- **BGM**：Erik Satie《Gymnopédie No.1》CC0 钢琴录音（Wikimedia Commons），
  710s crossfade 底床（`media/bgm/satie_gymnopedie_no1_cc0_bed710s.mp3`，
  sha256=7250daa…）；经 Phase 4-F BGM 模块混入，**旁白优先**：床 -20 dB /
  旁白段 duck -26 dB / 250ms 线性过渡；实测片尾无旁白区 -35.9 LUFS（轻床），
  成片响度契约通过。
- **声音**：当前旁白 = edge-tts zh-CN-XiaoxiaoNeural；**克隆声从未进过本片**
  （全库 1084 个语音产物均为 edge-tts/fixture）。口播稿 =
  `output/publish/narration_script_f14.txt`（3520 字，与成片逐字一致）。
  用户克隆声若要替换：本地 GPT-SoVITS（`C:\mp4agent\gpt-sovits`）+ 参照样片
  （`C:\mp4agentoice_ref`）合成新旁白 ⇒ **换音频 = 换时间基**，需重切景、
  重算窗与 cue（词级时间戳缺失时回落 P52-1 音频锚定）后整体重渲。


## 发布阶段二（2026-10-14：音色裁定 + F15）
- **人工裁定**：画面方向 = F14（视频版）；音色 = **Yunxi 云希青年男声**（放弃克隆，
  第三方声音合规风险已说明）；BGM 保留。
- **发布候选 = F15（Yunxi 版）**：
  `projects/p_2eac65565600/output/t_ee63a79fe9f4_draft_with_outro_v2.mp4`
  （655.134s，108.8 MB，四门 9/9，`logs/p58_9_delivery_candidate.jsonl`）。
- **语音链重建（P58-7）**：9 段 Yunxi 重合成（WordBoundary 1964 词，与晓晓版同数）
  ⇒ 同句子分组静音吸附重切 36 景（**逐景文本 sha 守恒** ⇒ pins/字幕句流不变）
  ⇒ 新时间基 **655.088s**（云希较快，全片缩短 42.4s）。
- **F15 = 新沙箱 p_2eac65565600**（F10.1/F12/F13/F14 证据工程原样保留）。
- F14.1（晓晓版 697.5s）保留为备选；两版仅音色不同。
