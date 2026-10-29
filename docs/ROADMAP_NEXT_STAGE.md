# 视频制作 Agent 能力盘点与下一阶段设计（设计稿 · 只读 · 不修改任何封包）

> 状态：设计仅供裁决。未修改 2.x / 3.1.4 任何封包文件，未进入实现。

## 一、现状盘点

### 已封包（2.x + 3.1.4）
| 能力 | 载体 | 输出 |
|---|---|---|
| 选题研究→claim 结构化→证据核查（Truth/Evidence） | 2.x tools（8D–8F，SHA 冻结） | Research Brief / Evidence Pool |
| 内容规划→蓝图→初稿→Creator Style v2 口播稿 | 2.x tools（8H–8K，冻结） | 已裁决口播稿 |
| 视觉规划→Production Plan→分镜 | 2.x tools（8N/8P/8Q） | shotlist 44 镜 + RUNBOOK + 成本估算 + QA 清单 |
| 素材研究：视觉意图→五路由检索→版权硬门槛→语义排序→Top-3/NO_SAFE | stage31（3.1.4 SEALED） | Material Package（materials/metadata/rights/shot_mapping/search_log/preview.html） |

### 实验/离线资产（未封包，未接生产链）
- `scripts/build_video_v2.py`：ffmpeg 文字卡成片（TTS 配音 + drawtext）
- `scripts/clone_voice_f5.py` + `models/f5`：F5-TTS 声音克隆（CPU）
- `scripts/_build_jarvis_step*.py/.ps1`、`_concat_*.py`：离线逐镜装配脚本
- `bin/ffmpeg.exe` / `bin/ffprobe.exe`、`produce_2x.py`
- `models/mt`（opus-mt-zh-en）、`models/semantic`（MiniLM）

## 二、能力缺口清单（素材猎取 → 最终成片）

| # | 缺口 | 现状 | 缺什么 | 等级 |
|---|---|---|---|---|
| 1 | 素材落地与规格化 | 3.1.4 只下载预览图 + 给 URL | 批量下载所选资产（原图/转码视频）、统一分辨率/帧率/时长、去水印检查、license-attribution sidecar 生成 | **P0** |
| 2 | 时间轴草稿（剪辑清单） | 只有 shotlist + shot_mapping | 把「镜头→Primary/ALT→口播→时长→字幕」渲染成可导入剪辑软件的 EDL/XML/剪映草稿；人工只需替换/微调 | **P0** |
| 3 | 配音对齐 | 只有口播稿 + 实验 TTS/克隆 | VO 生成（真人录音或 TTS/克隆）→ 分句时间戳 → 与 shot 时长对齐 → 响度/降噪归一 | **P0** |
| 4 | 字幕 | 2.x 有口播稿，无时间轴字幕 | 口播稿 + VO 时间戳 → SRT/ASS 字幕（含数字/实体高亮） | **P1** |
| 5 | 素材缺口回填 | 3.1.4 给"自制建议"（纯文本） | NO_SAFE_MATCH 镜的可执行回填：自录清单/AI 生成图（无文字装饰图）/字卡模板 | **P1** |
| 6 | 证据截图落地 | 3.1.4 分离 evidence 但不抓取 | 证据来源页截图采集（无头浏览器或人工上传位）+ 来源标注卡 | **P1** |
| 7 | 成片渲染/导出 | 实验 ffmpeg 文字卡版 | 素材+字幕+VO+BGM 的 ffmpeg 装配、1080p/4K、码率/响度规范、片尾署名 roll | **P0** |
| 8 | 质量校验（QC） | 2.x 有静态 QA 清单 | 运行时 QC：字幕-音频同步、响度 LUFS、画面连续性、版权署名完整性、Truth 数字一致性抽查 | **P1** |
| 9 | 发布 | 无 | 平台导出规格 + 元数据 + 分发 | **P3（明确后续阶段）** |

## 三、下一阶段设计（建议：Stage 3.2「视频装配器」草案）

### 定位（严格界定）
3.2 = 把已封包的 2.x（脚本/分镜）+ 3.1.4（素材包）**装配成可交付的剪辑工程与成片**。它是"装配/编排器"，不是"导演 Agent"、不是"全自动创意生成"。

### 建议链路（分两个子阶段）
**3.2a 剪辑工程生成（半自动，人工兜底优先）**
```
Material Package(3.1.4) + shotlist(2.x) + 口播稿
  → 素材落地（P0#1：下载+规格化+attribution sidecar）
  → 时间轴草稿（P0#2：EDL/XML/剪映草稿，镜头→素材→时长→字幕占位）
  → 证据截图落地（P1#6）
  → 人工确认/替换（NEEDS_REVIEW 工作流复用 3.1.4 的三态）
```
产出：一个可被真人导入剪映/Premiere 的工程骨架 + 全部资产与署名清单。

**3.2b 成片渲染（自动化，但以 3.2a 产物为输入）**
```
  → VO 对齐（P0#3）→ 字幕（P1#4）→ 缺口回填（P1#5）
  → ffmpeg 装配（P0#7）→ QC（P1#8）→ 导出
```
产出：成片 MP4 + SRT + 片尾署名。

### 硬边界（沿用既有原则）
- Truth/Evidence、Creator Style v2、口播稿、2.x/3.1.4 封包**一律不改**；
- rights gate / semantic threshold 45 / NO_SAFE_MATCH 语义**完全复用**，装配层不得绕过；
- 不新增主题专用规则；不引入需 API key 的商业源；不放松版权；
- 发布（P3#9）不在 3.2 范围，留待后续；
- 全自动"导演级创意剪辑"明确不做——3.2 只做确定性装配 + 人工兜底。

### 关键依赖与风险
1. **素材下载量与版权**：批量下载须逐条核对 license/署名并生成 sidecar（复用 3.1.4 rights 层）；
2. **视频转码**：Commons 视频多为 webm，需 ffmpeg 转 mp4（bin 已有）；
3. **VO 时轴对齐**：TTS/克隆为实验资产，接生产前需定 VO 来源策略（真人优先 / TTS 兜底）——需人工裁决；
4. **字幕时间戳**：无语音识别时用 TTS 合成时长估算或真人朗读校准；
5. **QC 的 Truth 一致性**：数字/实体与 2.x 证据链比对，仅报告不自动改。

### 建议里程碑（供裁决）
- M1（3.2a）：素材落地 + attribution sidecar + EDL/XML 时间轴草稿 —— 可先于配音/渲染交付；
- M2（3.2b）：字幕 + VO 对齐 + 缺口回填；
- M3（3.2b）：ffmpeg 渲染 + QC + 署名 roll；
- M4（后续）：发布。

## 四、明确不做的（防止范围蔓延）
- 不重写 2.x 创作链、不改 Creator Style v2 / Truth / Evidence；
- 不改 3.1.4 retrieval/ranking/rights/阈值/词库；
- 不接需要 API key 的素材/TTS/发布服务；
- 不实现"导演 Agent"级自动创意剪辑与多模态视频理解；
- 不 SEAL 任何新版本、不进入发布环节。

**本稿仅为设计，等待人工裁决是否启动 Stage 3.2。**
