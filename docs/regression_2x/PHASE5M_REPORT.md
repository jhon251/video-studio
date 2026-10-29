# 5-M 阶段报告：成片字幕化（画面内整段文案 → 逐条字幕）

- 日期: 2026-09-21
- 阶段: 5-M（在 `5.x-post-final-maintenance-baseline-r2` 之上；**只改字幕呈现**，不新增视频能力 / Judge / truth set / 阈值 / 自动选材 / 自动发布）
- 触发: 用户指出成片「**在画面中直接显示了这段完整的文案**」→ 要求「改成字幕」
- 授权基线: `5.x-post-final-maintenance-baseline-r2`（sha256 `2adc09c4092352f3c13af7b000db04b11e5ae34c96eb8389549ad7e3bcfb64e7`）
- 旧终稿: `5.x-final-baseline` sha256 `be1717b9…` —— 全程复核**未被修改/覆盖**

---

## 0. 问题确认（先取证，再改）

从 render v8 成片抽帧 t=20s（`output/_5m_frames/v8_t20.png`）可见：**整段旁白（148 字）按自适应字号折成 7 行、
居中铺满画面中部**并持续显示整个镜头时长。

代码定位（`agents/editing/agent.py::_narration_args`）：旧实现为**每段一条 `drawtext`**——
按文本长度自适应字号（28/34/42）、按字符数硬折行（26/20/16 字/行）、
`x=(w-text_w)/2:y=(h-text_h)/2`（**画面正中**）、`enable='between(t, 段起, 段止-0.4)'`（整段时长）。
因此"字幕"实际等于**整段文案贴在中景**，不是字幕。

附带发现（如实登记）：`agents/subtitle/agent.py` 生成的 SRT 也是**每段一条 cue、文本为整段旁白**；
但它**并未被渲染侧使用**（渲染侧自行从脚本重新取文本），属"产物与烧录不一致"的历史遗留。

---

## 1. 改法（最小且可验证）

| 层 | 变更 |
|---|---|
| **新增** `src/video_studio/core/captions.py` | 字幕**切分 / 折行 / 时间排布 / SRT / ASS** 的**纯函数单一事实源**：按句末标点切句 → 按停顿标点细分（每条 ≤36 字）→ 按**视觉宽度**折 ≤2 行（优先在标点处断、行首不放标点）→ 单条显示时长 = `字数/5.0` clamp [1.0s, 8.0s]，并在**镜头窗口内均匀铺开**（剩余时间为静默间隔）、超出窗口则按比例压缩；输出 `to_srt`（每条单行，保持可检索）与 `to_ass`（PlayRes=分辨率、**底部居中** Alignment=2、描边 Outline=3、字号=高度×4.2%、MarginV=高度×5%） |
| `agents/subtitle/agent.py` | 改用 `core.captions` 生成 cue 化 SRT（产物新增 `cues` 字段；`segments` 仍为段数，向后兼容） |
| `agents/editing/agent.py` | 删除"每段一条 drawtext + 自适应字号 + 居中"的旧烧录；改为**一次 `ass=filename='…':fontsdir='C\:/Windows/Fonts'`** 烧录 `core.captions` 生成的 ASS（底部居中、逐条、带描边）。滤镜位置不变（concat 之后、fade 之前），时长契约与音频链**未改** |

选择性说明：本项目 ffmpeg 构建 `--enable-libass --enable-fontconfig`（已实测 `ass`/`subtitles` 滤镜可用），
故采用 libass 而非 drawtext；字体经 fontconfig 解析（`Microsoft YaHei`），并用 `fontsdir` 兜底。

---

## 2. 验证（三层：单元 → 视觉探针 → 真实成片）

### 2.1 单元（新套件 `tests/captions_test.py`，**21/21**）
切句/细分/合并、折行（≤2 行、行宽上限、行首不放标点、优先标点断）、排布（单调/不重叠/不越镜头窗口/单条 ≤8s/窗口内铺开）、
SRT 结构（每条单行）、ASS 头（PlayRes/底部居中/描边/字号随高度缩放）、确定性（两次输出逐字节一致）、
真实脚本 21 段全量不变量、边界（空文本/非法 duration 不崩）。

### 2.2 视觉探针（`docs/regression_2x/phase5m_caption_probe.py`）
用**真实素材照片** + **真实脚本文本** + **与渲染同款 `ass=` 滤镜**渲染 36s 小片并抽帧：
- `frame_009.0s.png`：单行字幕底部居中（"我们证明了它，还是我们相信它被证明了？"），画面主体完全可见；
- `frame_025.0s.png`：两行字幕（"它的内容很朴素：给一张平面地图上色，/ 相邻的区域颜色不同，四种颜色够不够。"），
  两行配平、带描边、无溢出、CJK 字形正常（无豆腐块）。

### 2.3 真实成片（render **v9** = `t_d0a54bdf1810`）
| 项 | 结果 |
|---|---|
| 任务/产物 | render v9 `SUCCEEDED`；产物 `a_82b543375e11`（render_output）+ `a_c0f078f6c710`（attribution） |
| 成片 | `projects/p_96efdc03e1aa/output/t_d0a54bdf1810_draft.mp4`（46,761,341 B，sha256 `1d48…`，见证据 JSON） |
| 时长契约 | 容器 **1532.0 s**、**视频轨 1531.96 s**（残差 1 帧）、38,300 帧、1920×1080 h264+aac；`video_duration_ok=True`、delta 0.0 |
| 响度 | 独立 `ebur128`：**−16.1 LUFS / TP −2.5 dBFS**（契约 −16±1 / ≤−1.5 ✓） |
| 字幕 | 字幕产物 v2：21 段 → **216 条 cue**（SRT 12,594 字符）；成片抽帧确认**底部居中逐条字幕** |
| 抽帧 | `logs/phase5m_frames/v9_t{0020,0120,0420,0900,1400}s.png`（t=20s 单行字幕、t=1400s 尾部字幕） |
| 内容未变 | `topic_output` / `script_output` / `claims_map` / `editing_plan_output` / `structure_output` / `research_output` / `voice_output` **文件 sha256 全同**；claims 状态计数与 decisions 计数**全同** |
| 旧版保留 | v8（`t_30070f93a77e_draft.mp4`）与 v1–v7 全部保留（append-only），未删除未覆盖 |

### 2.4 字幕节奏与覆盖率（实测，供人工判断）
| 指标 | 值 |
|---|---|
| cue 数 / 显示总时长 | 216 条 / 987.6 s |
| 全片覆盖率 | **64.5%**（1532 s 内） |
| 静默间隔 | 均值 2.5 s、**最大 4.6 s**（无 >5 s 的空档） |
| 单条显示时长 | 1.0–8.0 s（按阅读速度 5 字/秒，长句封顶 8 s） |
| 每镜覆盖 | 49%–84%（21 镜逐镜统计见证据 JSON） |

> 覆盖不连续的原因**不是**字幕实现，而是本片既有的**旁白/时间轴不匹配**：
> 旁白实际 961.656 s（21 段 TTS 真实时长合计）而时间轴 1532.0 s（`voice_output.duration_contract.within_tolerance=false`，
> 短差 570.3 s）。即约 37% 的画面期间**本来就没有旁白**。5-M **未**改动该口径（属内容/时间轴问题，不是呈现问题）。

---

## 3. 回归（如实）

- 受影响套件：`captions_test` **21/21**、`scene_assembly_test` **15/15**、`narration_contract_test` **40/40**、
  `maintenance_fixes_test`（5-K 守卫）**28/28**、`offline_mock_test`（5-L 守卫）**23/23**、
  `attribution_compliance_test` **24/24**。
- **过程中发现并修复的自身缺陷（如实披露）**：首版实现用 `task["task_id"]` 命名 ASS 文件，
  而 `scene_assembly_test` / `narration_contract_test` 以**最小 task 字典**（只有 `project_id`）直接调用
  `_narration_args` → `KeyError: 'task_id'`（两套件转红）。已改为 `task.get("task_id") or "adhoc"`，两套件恢复全绿（15/15、40/40）。
  **该缺陷只在"无 task_id"的调用形态下出现，不影响已渲染成片**（真实渲染恒有 task_id），故 v9 无需重渲。
- 全量电池：见 §4。

---

## 4. 全量电池（25 步，与 5-F/5-G/5-J/5-L 同一步骤序列）—— **25/25 全绿（2026-09-23 重跑）**

脚本 `docs/regression_2x/phase5m_battery.py`（AST 解析步骤表；独立备份 `logs_5m_frozen/`、留档 `logs/phase5m_rerun/`）。

**首轮（2026-09-21）第 25 步被中断**：第 1–24 步完成到 `5f_judge`（23:47），`unit_suites` 未跑完，
未生成电池 summary，电池自带的"另存 + 回拷冻结日志"收尾未执行 → 已于 2026-09-23 用
`phase5m_preserve_and_restore.py` 补做（162 个改写文件回拷 / 82 个本轮产物留档 / **drift 0 / missing 0**）。
**该轮中间结果**（如实留档）：批次 23/24（唯一非预期 = `phase2e_real_provider` 环境网络 TLS）、
`suite_all` 48/49（唯一红 = `strip_v2_test` 过期契约，当日已修正并单独复跑 rc=0）。

**重跑（2026-09-23，最终结论）**：

| 口径 | 结果 |
|---|---|
| 电池 | **25/25 步 rc=0**（`all_rc_zero_raw = True`，`rc_nonzero = []`，总耗时 **4,397.0 s**） |
| 批次（第 2 步） | **24 项 → 24/24 符合预期**（0 非预期）；`phase2e_real_provider` **13/13**、`metrics_readonly` **18/18**、`run_ingest_test` **PASS**、`real_small_test` PASS、`phase2ab_accept_verify`/`phase3a_run1_verify` PASS |
| 单元套件 | **49 个 → 49 rc=0**（含新增 `captions_test`；含按契约修正后的 `strip_v2_test`） |
| E2E（`e2e_mechanical`） | **3/3 SETTLED**（`p_2fed6bb20a5b` / `p_711e79f8c5da` / `p_8a301fdde95a`） |
| 冻结证据日志 | **drift 0 / missing 0**（163 个改写文件逐文件回拷、0 新增、0 删除；`frozen_logs_restored=True`） |
| 代码/测试指纹 | 电池后 == 冻结时 == `c495dd64913c…`（`phase5m_code_fingerprint_{after,now}.json`） |
| 基线 | `5.x-post-final-maintenance-baseline-r3` → `verify_baseline` **MATCH**（见 §6 与 `BASELINE_README.md`）；旧 `5.x-final-baseline` 与 r1/r2 **未被改动** |

**判定：5-M = PASS**（授权范围内全部动作完成、必要电池达 DoD；字幕化改动的三层验证见 §2）。
遗留（不阻塞）：#65（旁白/时间轴不匹配 570.3 s，OPEN）与陈旧分支清理等运维事项见 `PHASE5M_CHECKPOINT.md` §3。

---

## 5. 产物清单

- 产品代码：`src/video_studio/core/captions.py`（新）、`src/video_studio/agents/subtitle/agent.py`、`src/video_studio/agents/editing/agent.py`
- 测试：`tests/captions_test.py`（新，21/21）
- 文档：`STATUS.md`、`CHANGELOG.md`、`docs/KNOWN_ISSUES.md`（#65/#66）、
  `docs/regression_2x/{PHASE5M_REPORT.md, PHASE5M_CHECKPOINT.md}`
- 脚本（docs）：`phase5m_{caption_probe,verify_render,battery,evidence,code_fingerprint,freeze_r3}.py`
- 证据（`docs/regression_2x/logs/`）：`phase5m_render_verify.json`、`phase5m_caption_probe/report.json` + 抽帧、
  `phase5m_frames/*.png`、`phase5m_regression_summary.json`、`phase5m_rerun/**`、`phase5m_evidence.json`
- 成片：`projects/p_96efdc03e1aa/output/t_d0a54bdf1810_draft.mp4`（v9，含逐条字幕）
