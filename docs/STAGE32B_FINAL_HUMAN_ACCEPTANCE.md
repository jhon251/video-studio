# Stage 3.2b 最终人工验收（FINAL HUMAN ACCEPTANCE）

- 验收对象：`output/stage32b/coral/production/final_preview.mp4`（102.04s / 1920×1080 / 25fps）+ 全套交付物（subtitles.srt/.ass、voiceover.wav、manifests、qc）
- 验收日期：2026-08-29（P0-7 Remediation Finalization 之后）
- 边界遵守：**未修改** 2.x / Truth/Evidence / Creator Style v2 / 冻结口播稿 / 3.1.4 全模块与 SHA / Material Package / rights gate / threshold 45 / NO_SAFE_MATCH；**未重新检索、未重新生成 VO、未改变 260 字/分裁决**；未进入 3.3。

---

## A. 机器 Gate（全部可复现数据）

### A1. P0-7 QC 13 项 Gate（`qc/qc_report.json`，remediation finalization 记录，本次复核一致）

| # | 检查项 | 结果 | 实测 |
|---|---|---|---|
| 1 | video decode/container 完整 | PASS | 102.1s / 1920×1080 / 25fps / 有音频 48kHz |
| 2 | 20/20 镜无丢失 | PASS | shots_missing=[] |
| 3 | VO 20/20 segment | PASS | 20/20 OK |
| 4 | VO↔shot 映射完整 | PASS | true |
| 5 | VO↔字幕同步（±0.1s，尾条 ±0.2s） | PASS | sync_bad=[] |
| 6 | 字幕逐字 Truth 一致 | PASS | true |
| 7 | 字幕无 overlap / 无越界 | PASS | false / true |
| 8 | 无黑帧/冻结帧 | PASS | blk=[] frz=[] |
| 9 | 音频 48kHz + TP≤-1.5dB + 无异常长静音(≥1s) | PASS | max=-2.2dB；abnormal=[]；natural 停顿 [0.875, 0.865]（裁决保留） |
| 10 | 成片响度 -18≤I≤-14 LUFS | PASS | I=-17.7 LUFS |
| 11 | 无弱匹配 USE_MATERIAL（全部 sem≥50 决策） | PASS | weak=[]（11 镜原状态全 PRIMARY） |
| 12 | provenance 链一致 | PASS | narration_sha 链一致 |
| 13 | output SHA 与 manifest 一致 | PASS | 3C629B6238B6…（本次独立复核一致） |

### A2. 本次验收独立复核（新执行，非复用旧数据）

- **最终产物 SHA256**（固化于 Seal 文件）：
  - `final_preview.mp4` = `3C629B6238B6A167A95BE33A2D208461D7322459451FCD6E1740DE109C8606B8`
  - `subtitles.srt` = `B6D82D4B900230BEE2BEC46D555F897548982E9DCE4A3047376F7D8E7CD09C32`
  - `subtitles.ass` = `275EFED0F59F98CC80887D13A7BD22919019516BD9F3B13D23CACDCDF070A42E`（= render_manifest.subtitle_sha，即烧录版）
  - `voiceover.wav` = `24A1AC2A84F5AF041D41772299606CEDDFA675F229A26C1DB0A30B2D25EA3D49`
  - 7 个 manifests + qc_report.json 共 11 项 SHA 见 `docs/STAGE32B_SEAL.md` 附录。
- **逐镜像素级画面分析**（`qc/_frame_analysis.py`，ffmpeg+NumPy，20 镜中帧）：**20/20 OK**
  - 9 张 TEXT_CARD：深青底占比 97.7–98.1%（0x0b2e33）+ 白色文字像素 0.99–1.16% → drawtext 全部渲染，无黑屏；
  - 11 张 USE_MATERIAL：内容方差 std 40.7–60.7 → 素材内容真实呈现，非空白/非黑帧；
  - 20 处镜头切换：相邻帧平均像素差 4.0–196.5，全部真实切换（文字卡↔文字卡差异小属预期：仅文字变化，已核 Sxx.txt 内容互异）；
  - 前 10 秒 5 帧：均为主题文字卡（开场"在海水下面…"→"珊瑚不是石头…"），主题建立正常；
  - 片尾 4 帧（98.5–101.5s）：S20 城市夜景内容连续存在，无黑屏。
- **字幕阅读压力**（subtitle_manifest 29 条独立计算）：全程 **4.32–4.48 字/s**（max 4.48），逐段语速 min/max/avg = **259.3 / 260.1 / 259.5 字/分**，20 段一致性极高；最长条目 22 字/5.09s；最短条目 1.62s/7 字——无压力高条目。
- **冻结资产 SHA 回归**（本次执行）：
  - 2.x：19 文件中 **15/19 与 `PRODUCTION_MANIFEST_2X.json` 逐字节一致**；4/19 为 2026-08-19 人工裁决 Creator Style v2 升级基线差异（production2x/__init__.py、content_planning.py、narrative_generation.py、creator_style.py），本次首次固化其 SHA（见 Seal 附录；此前仅以"裁决差异"声明，未留 SHA）；
  - 3.1.4：**12/12 一致**（9 模块 + run_stage31.py + 2 个 fetch 脚本），含 `__init__.py` = `B33B7310991A5E30AD108EEEC4949DB4F51C26DB0F6F6D464E5A32E4204754AA`（与 STAGE31_4_SEAL 记录一致）；
  - 冻结口播稿（coral）：内容 SHA（Python `read_text` 归一化口径）= `fd60866d…` **与全链 manifest 一致**（文件为 CRLF 行尾，字节级 SHA=254ACD59…，两者等价；已用 Python 复算验证）；
  - 参考文本：`ref_voice.txt` 归一化 SHA = `4b6ffe0a…` = vo_manifest.ref_text_sha；
  - 11 个 USE_MATERIAL 本地素材文件 SHA 与 shot_assembly_manifest **11/11 一致**。
- **冻结测试套件全量重跑**（本次执行，脚本式套件 `python tests/*_test.py`）：**18/18 全绿，0 失败**
  - 2.x 13 套件 229 项检查全过（agents_v2 28、claim_structuring 6、evidence_pool 7、evidence_regression 23、factcheck_v2 23、hitl_v2 19、llm_semantic_judge 16、numeric_parser 9、schema_v2 10、search_quality_v2 51、strip_v2 14、sufficiency_judge 15、text_quality 8）；
  - stage31 5 套件 147 项全过（intent 37、package 22、queryplan 13、rights 69、semantic 6）。
- **时间轴契约**：Σadopted = 102.199s（alignment_manifest.total_duration），gap=0；成片媒体实测 102.04–102.1s（逐镜 `-t` 微裁 0–19ms 编码取整，属已知公差）；末条字幕 end 已按媒体实测钳制到 102.04s。

### A 小结：机器 Gate **全部 PASS**（13/13 + 独立复核 + 18/18 套件 + SHA 回归）

---

## B. 人工观看 Gate（请按 `qc/human_review.md` 最终版执行）

人工观看清单已重建（最终 102.04s 时间轴，替代旧 26.38s 版），并附 3 张机器抽帧图（`qc/frames/`）。重点项与机器辅助证据：

| 用户要求检查项 | 机器已证 | 待人工确认 |
|---|---|---|
| 前 10 秒主题建立 | 0–10.4s 两张主题文字卡，渲染正常，文字=开场两句 | 文字卡开场是否"够味" |
| 260 字/分听感 | 语速 259.3–260.1 字/分，20 段均匀；停顿 0.875/0.865s 保留 | **听感自然度（核心）**：TTS 机械感/吞字/呼吸 |
| VO 与画面匹配 | 20 镜映射完整、逐字字幕同步 ±0.1s | 语义级匹配（9 张文字卡尤其） |
| 9 个 TEXT_CARD | 全部诚实标记 SELF_CREATED，渲染确认；4 个 marginal 拒绝项（46.8/45.2/48.6/45.6）+ 5 个 NO_SAFE | 观感是否可接受；S02/S07/S13/S16 是否人工放行原素材 |
| 11 个 USE_MATERIAL | 全部 PRIMARY、sem 50.0–67.2、rights SAFE/CONDITIONAL、素材文件 SHA 11/11 | 语义错配肉眼复核（S09 白化珊瑚 vs "雪森林"、S19 沙滩孩子 vs "潜水面镜"为相对弱项，供重点看） |
| 字幕阅读压力 | 4.32–4.48 字/s，无高压力条目 | 实际跟读感受 |
| 镜头切换自然度 | 20 处真实切换、无黑帧/冻结帧、镜间无缝、素材镜有 Ken Burns 缩放 | 硬切（无转场特效）是否可接受 |
| 音量/压缩痕迹 | I=-17.7 LUFS、峰值 -2.2 dBFS、无削波、无异常静音 | 听感上 limiter 链（-3dB+0.4dB 补偿）是否有可闻痕迹 |
| 片尾完整性 | S20 内容完整到 102.04s，无黑屏 | 无 fade-out/无片尾署名 roll 是否可接受 |

**B 小结：人工观看证据已齐备（逐镜时间窗 + 抽帧图 + 机器像素证据），等待人工观看裁决。**

---

## C. 已知限制（如实保留，不隐藏）

1. **素材覆盖不足**：9/20 镜（45%）无 SAFE 素材降级为静态文字卡（5 个 NO_SAFE + 4 个 marginal<50 拒绝）——这是 3.1.4 语义阈值/版权门槛的诚实结果，不是错误，但直接限制成片观感。
2. **静态表现力**：全部为静态图 + Ken Burns（1→1.06 缩放）；无视频 B-roll、无转场特效（20 处硬切）、无片头/片尾模板、无 fade-out（102.04s 直接结束）。
3. **音频**：无 BGM/音效；VO 为单克隆音色 F5-TTS（CPU），无情绪/重音/停顿润色；响度链为 loudnorm(-16)+alimiter(-3dB)+0.4dB 补偿，动态受限。
4. **字幕样式**：极简白字黑边（msyh 54px），无数字/实体高亮、无排版风格化。
5. **亮图未调色**：S06（海温图）Y=231、S08（古书插图）Y=208，白底偏亮，与深青文字卡反差大。
6. **QC 代码残留**：`qc.py` 的 `timeline_gap_note` 为 remediation 前旧口径硬编码文本（26.38s/32.132s），不影响任何 Gate 数据；按"验收期不改代码"纪律未修，仅记录。
7. **产能**：VO 生成 102s 音频耗时 3133s（≈52min，CPU F5-TTS 约 30× 实时）；无 GPU、无并行队列，规模化需产能改造。
8. **自动化边界**：2.x 为确定性模板生成器（Style v2 已去模板化，但非 LLM 自由写作）；"导演级创意剪辑/多模态视频理解"明确不做；发布链路（平台导出/分发）不在 3.2 范围。
9. **人工接口**：9 个 TEXT_CARD 的替换/放行目前只有 manifest 标记（human_action_required），无 GUI workbench、无 EDL/XML 剪辑工程导出（3.2a 设计未实现）。

---

## D. 是否建议 SEALED

**建议：SEALED（条件式封包）**——条件为"人工观看确认"。

- 机器 Gate 全 PASS（A 节 13/13 + 独立复核 + 18/18 套件 + SHA 回归全绿），无任何 Gate 级失败；
- 成片质量已到"可交付人工剪辑/发布前审片"水平：完整时间轴、逐字字幕、合规素材、诚实降级、全链可审计；
- 封包前唯一未完成的是**人工观看/听感确认**（B 节）——机器无法代听。Seal 文件将明确注明该条件；若人工观看发现问题，**按既有纪律重开 remediation（不修改阈值、不放松标准）**，Seal 可回滚。
- 按指令：封包后**不进入 3.3**，STOP 等待下一步授权。

---

## 最终结论：系统当前"从主题到视频"的实际能力与规模化缺口

### 已具备（端到端真实可用，全部确定性、可复现、可审计）

1. **主题 → 口播稿**（2.x 冻结链）：选题研究→claim 结构化→Truth/Evidence 核查→内容规划→蓝图→初稿→Creator Style v2 口播稿，无 LLM、无漂移、SHA 冻结；
2. **口播稿+分镜 → 素材包**（3.1.4 SEALED）：视觉意图→五路由检索（Wikidata/分类/全文+离线 MT/legacy/情绪）→**版权硬门槛**→hybrid 语义排序（≥45）→Top-3/NO_SAFE → Material Package（含 rights/provenance/search_log）；
3. **素材包+口播稿 → 成片**（3.2b 本次封包）：F5-TTS 克隆 VO（对齐参考，260 字/分）→ vo_measured 真值时间轴 → 逐字字幕（SRT/ASS）→ BLOCKED 决策（sem≥50 用素材 / <50 或 NO_SAFE → TEXT_CARD 诚实降级）→ 逐镜装配（Ken Burns / 文字卡）→ 渲染（1080p25、ASS 烧录、loudnorm+limiter）→ QC 13 项机器 Gate + provenance/SHA 链；
4. **交付物**：1920×1080 MP4 + SRT + ASS + VO WAV + 全套 manifest + 人工观看清单 + 抽帧图，license/attribution 全链保留；
5. **真实世界验证**：《珊瑚礁正在消失》20 镜全链 PASS（11 素材 + 9 文字卡），无任何错误素材/版权违规/越界字幕/削波。

### 距离"可规模化生产视频"的剩余缺口（按严重度）

| 缺口 | 现状 | 影响 | 候选解决（待裁决） |
|---|---|---|---|
| **素材供给侧** | Commons 静态图覆盖有限：45% 镜无 SAFE 素材；无视频源（Pexels/Pixabay 需 key 被禁）；中文语境覆盖差（tea recall 0.25） | 成片"图片流+文字卡"质感、单主题成功率受限 | 素材库扩容/自建库/人工素材接入位（3.x registry #3）；视频源转码管线 |
| **人工工作流** | 9/20 镜需人工替换/放行但无 workbench；无 EDL/XML 剪辑工程（3.2a 设计未实现） | 人工介入成本高、无法进剪辑软件二剪 | 3.2a 剪辑工程（素材落地 sidecar + EDL/XML/剪映草稿） |
| **动态表现力** | 无 B-roll/转场/片头片尾/BGM/音效/混音母带 | 未达"成片感"，属"初剪+配音+字幕"级 | 转场模板、片尾署名 roll、BGM 库（版权合规） |
| **产能** | CPU TTS 52min/102s 音频；无并行/队列/多项目 | 单条短视频小时级，不可批量 | GPU/队列调度/多项目编排 |
| **TTS 音质** | 单克隆音色、无情绪控制 | 听感上限受限于 F5-TTS CPU 推理与单一参考音 | 音色库/多参考/真人配音位 |
| **内容侧自动化边界** | 2.x 确定性生成非 LLM 自由写作；无多模态视频理解 | 创意多样性受限（架构决策，非缺陷） | LLM 文案器（Style v2 规范已为其预留） |
| **发布链路** | 无平台导出/元数据/分发 | 未到发布 | 明确后续阶段（P3） |

**一句话结论**：系统已具备"**主题 → 合规素材 → 配音 → 字幕 → 成片**"的端到端**确定性装配流水线**（单条 1–3 分钟科普视频可完整产出并交付人工审片）；但距离"可规模化生产"还差**素材供给扩容、人工剪辑工作台、动态/音频表现层、GPU 产能与发布链路**五大块——其中素材供给与人工工作流是最硬的现实瓶颈。

---

## 附录：本验收执行了什么 / 没执行什么

- 执行：产物清单核对、11 项最终 SHA 固化、逐镜像素分析、字幕压力计算、2.x/3.1.4 SHA 回归（含 CRLF 归一化口径核对）、18/18 冻结套件重跑、human_review.md 重建（最终时间轴）。
- 未执行（按指令）：未重新检索、未重新生成 VO、未改语速裁决、未修改任何冻结物、未进入 3.3、未改动 qc.py 的旧口径注释残留。
