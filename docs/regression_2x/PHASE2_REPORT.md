# 3.x Phase 2-A / 2-B 报告：镜头级素材装配 + 素材时间轴

- 日期：2026-09-13
- 授权范围（逐字）：**只授权 Phase 2-A + Phase 2-B。不要自行开始 Phase 2-C。**
- 本阶段交付：2-A = 真实选材落到**镜头级装配**；2-B = **素材时间轴**（每镜头 → 素材的确定性分配记录 + render 实际按该时间轴出片）。
- 未开发（越界即不做）：Phase 2-C（fallback 分类学）、2-D（追溯报告）、2-E/2-F（外部素材 provider）、BGM、自动发布、UI 重构、新 Agent。
- 未触碰：Claim/HITL 闸门、append-only、exec isolation、断点恢复、既有 task/artifact/事件契约（仅**新增** `MATERIAL_TIMELINE` 事件类型）。

---

## 0. 结论先行（判定行）

| # | 判定项 | 结论 |
|---|---|---|
| 1 | **Phase 2-A/2-B 核心**（真实选材 → 镜头级分配 → 时间轴记录 → 成片**在屏**证据） | **PASS** |
| 2 | 全片覆盖时间轴**全部** 12 镜头（S01–S12） | **PARTIAL / PENDING**：成片 238.5s < 时间轴 438s，S09–S12 未渲染。根因在**音频阶段**（旁白音轨仅 7/12 段），**不是素材装配缺陷** |
| 3 | 既有回归（28 套件 + 3 机械 E2E + 真实小测 + 本地装配） | **PASS**（28/28、3/3、PASS、PASS） |
| 4 | 音轨质量（A/V 对齐、段完整） | **FAIL（既有缺陷，非本阶段引入）** → 见 §5 PENDING-1/2/3 |

一句话：**素材链路已真实打通并有在屏证据；拖后腿的是旁白音轨不完整，导致成片被 `-shortest` 截短到时间轴的前 54%。**

---

## 1. 15 项硬验收逐条核对

真实项目 `p_ab2b352e06b8`（真实 LLM 链路，`config/config.real.json`），素材为 3 张**人工逐张看过内容**的本地真图。原始证据见 `logs/phase2_evidence.md`、`logs/phase2_accept.json`、`logs/P2_accept.log`。

| # | 验收项 | 结论 | 证据 |
|---|---|---|---|
| 1 | 真实选材（非伪造） | PASS | `retrieval_candidates.material_mode=local_ingest`，3 个候选，全部来自 `projects/.../media/`，含真实 sha256 |
| 2 | ≥3 个不同镜头 | PASS | 时间轴 12 个镜头（S01–S12） |
| 3 | ≥3 个不同 `local_ingest` 素材 | PASS | 实际使用 3 个不同素材（见 §2 表） |
| 4 | 每个素材都被检索命中 | PASS | 命中分 25 / 22 / 14，各自带 `matched_tokens` |
| 5 | 每个素材被分配到镜头 | PASS | 3 个素材全部出现在时间轴；12/12 镜头均有素材 |
| 6 | 时间轴被记录 | PASS | `MATERIAL_TIMELINE` 事件 + `render_output.material_timeline`（12 条，含窗口/查询/命中 token/素材/理由/fallback） |
| 7 | render **实际使用**时间轴 | PASS | 逐镜头窗口抽帧，8 个已渲染镜头**全部**命中各自分配的素材（§3） |
| 8 | 抽帧确认**不同镜头显示不同素材** | PASS | 3 个素材各自在对应窗口为相关性最高；**不同素材镜头对最大相关 0.099**（同素材镜头复用 ≈0.99 属预期） |
| 9 | ffprobe 校验 | PASS | 2 流：h264 1920×1080 30fps 7155 帧 / aac 24000Hz 单声道；`format.duration=238.500` |
| 10 | ffmpeg 解码 rc=0 | PASS | `ffmpeg -v error -i <mp4> -f null -` → rc=0 |
| 11 | 素材来源/sha256/镜头/时间轴可追溯 | PASS | §2 表；`asset_id` ↔ `sha256` ↔ `media/` 路径 ↔ 镜头窗口 ↔ 秒级时间轴 |
| 12 | 素材不足时显式 fallback | PASS | 确定性测试：无任何素材命中 → 12/12 `SOLID_COLOR_CARD`、`selected_asset=None`；有素材缺失时 `fallback_scenes` 记录 |
| 13 | 既有 27 项测试仍通过 | PASS | `run_all_suites.py`：**28 total / 28 rc=0 / 0 失败**（27 旧 + 1 新增 `scene_assembly_test`） |
| 14 | 3 个机械 E2E 仍出片 | PASS | A/B/C 全部 SETTLED，各自产出 mp4（17.000s、2 流、真 ffprobe 校验） |
| 15 | 真实 LLM 小测仍可用 | PASS | `real_small_test.py`：2 次调用 $0.002558，无失败/阻塞，台账与任务行一致 |

**不得伪造项**：#7/#8 之所以敢判 PASS，是因为成片**真的**在 S01/S02/S03…S08 各自窗口内显示对应素材（相关系数 0.672–0.744，且换素材处相关系数跌到 ≤0.099）。**未能证明的部分（S09–S12）已明确记为 PENDING，未计入 PASS。**

---

## 2. 素材时间轴（2-B 交付物）

`visual_source=material_timeline`、`material_assembly=SUCCEEDED`、`scene_count=12`、`scenes_with_asset=12`、`fallback_scenes=[]`。

| 镜头 | 窗口(s) | 素材 ID | 素材名 | sha256[:16] | fallback |
|---|---|---|---|---|---|
| S01 | 0–30 | asset_3bd63424e488 | VR头显_镜片特写.jpg | 3bd63424e48866db | LOCAL_INGEST |
| S02 | 30–68 | asset_f304650dbc24 | VR头显_手柄_笔记本.jpg | f304650dbc24803c | LOCAL_INGEST |
| S03 | 68–104 | asset_3af507571a33 | 脑电头环_假人头模_陈列柜.jpg | 3af507571a33f029 | LOCAL_INGEST |
| S04 | 104–142 | asset_3bd63424e488 | VR头显_镜片特写.jpg | 3bd63424e48866db | LOCAL_INGEST |
| S05 | 142–174 | asset_3bd63424e488 | VR头显_镜片特写.jpg | 3bd63424e48866db | LOCAL_INGEST |
| S06 | 174–198 | asset_3bd63424e488 | VR头显_镜片特写.jpg | 3bd63424e48866db | LOCAL_INGEST |
| S07 | 198–226 | asset_f304650dbc24 | VR头显_手柄_笔记本.jpg | f304650dbc24803c | LOCAL_INGEST |
| S08 | 226–278 | asset_3bd63424e488 | VR头显_镜片特写.jpg | 3bd63424e48866db | LOCAL_INGEST |
| S09 | 278–314 | asset_3bd63424e488 | VR头显_镜片特写.jpg | 3bd63424e48866db | LOCAL_INGEST |
| S10 | 314–346 | asset_3bd63424e488 | VR头显_镜片特写.jpg | 3bd63424e48866db | LOCAL_INGEST |
| S11 | 346–402 | asset_f304650dbc24 | VR头显_手柄_笔记本.jpg | f304650dbc24803c | LOCAL_INGEST |
| S12 | 402–438 | asset_f304650dbc24 | VR头显_手柄_笔记本.jpg | f304650dbc24803c | LOCAL_INGEST |

匹配为**确定性词典混合打分**（CJK 二元组×2 + 单字×1 + 拉丁词(≥3)×2），素材按**已核对内容**命名；优先选用未使用素材，故 S02/S03 拿到 22/14 分的第二、第三素材，S04–S06 才开始复用。`selection_reason` 逐镜头落库（含"为避免重复优先选用未使用素材"标注）。

---

## 3. 在屏证据（抽帧 × 相关性）

成片 `t_dc426762251a_draft.mp4`：14,825,389 bytes，238.500s，7155 帧，2 流，decode rc=0。
抽帧方法：48×48 灰度 Pearson 相关；判定 = 分配素材为 argmax 且 corr > 0.3。

| 镜头 | 窗口(s) | 采样点(s) | 期望素材 | argmax 素材 | corr | 判定 |
|---|---|---|---|---|---|---|
| S01 | 0–30 | 15.0 | 3bd63424e488 | 3bd63424e488 | 0.672 | OK |
| S02 | 30–68 | 49.0 | f304650dbc24 | f304650dbc24 | 0.744 | OK |
| S03 | 68–104 | 86.0 | 3af507571a33 | 3af507571a33 | 0.684 | OK |
| S04 | 104–142 | 123.0 | 3bd63424e488 | 3bd63424e488 | 0.678 | OK |
| S05 | 142–174 | 158.0 | 3bd63424e488 | 3bd63424e488 | 0.673 | OK |
| S06 | 174–198 | 186.0 | 3bd63424e488 | 3bd63424e488 | 0.673 | OK |
| S07 | 198–226 | 212.0 | f304650dbc24 | f304650dbc24 | 0.730 | OK |
| S08 | 226–278 | 232.2 | 3bd63424e488 | 3bd63424e488 | 0.676 | OK（被成片结尾截断） |
| S09–S12 | 278–438 | — | — | — | — | **未渲染（PENDING）** |

- 确认在屏的**不同素材数 = 3**。
- **不同素材**镜头对最大相关 **0.099**（最低 −0.164）→ 换素材是真换了画面，不是同一张图。
- 同素材镜头对相关 ≈0.991（S04/S05/S06 均为镜片特写）→ 预期内，判重不采用该口径。

---

## 4. 回归（本阶段强制项）

| 项 | 命令 | 结果 |
|---|---|---|
| 全部套件 | `python docs/regression_2x/run_all_suites.py` | **28 total / 28 rc=0 / FAILED: []** |
| 新增装配单测 | `tests/scene_assembly_test.py` | **15/15**（3 镜头→3 不同素材；无素材→全 SOLID_COLOR_CARD；ffmpeg 实装 16.9s vs 17.0s；逐镜头相关 0.688/0.687/0.743；跨镜头最大 0.11） |
| 3 机械 E2E | `python docs/regression_2x/run_all_tests.py --fresh` | A/B/C **SETTLED**，各自 mp4 17.000s / 2 流 |
| 本地素材链路 | `python docs/regression_2x/run_ingest_test.py` | **PASS**：`visual_source=material_timeline`、`assembly=SUCCEEDED`、抽帧 t=2.1s 命中分配素材 corr 0.747 |
| 真实 LLM 小测 | `python docs/regression_2x/real_small_test.py` | **PASS**：2 调用 $0.002558，无失败 |
| 二进制真实性 | `python scripts/check_binaries.py` | **PASS**：ffprobe 真实且与 ffmpeg 非同一二进制 |
| 成本一致性 | `docs/regression_2x/phase2_evidence.py` | 任务行累计 $0.107305 == `LLM_CALL` 事件 19 条合计 $0.107305 |

本项目真实花费 **$0.107305**（19 次真实调用，含 2 次网络失败后的 redo）。

---

## 5. PENDING（不伪造 PASS）

### PENDING-1：成片未覆盖时间轴全部镜头（音频阶段缺陷，**非素材装配缺陷**）
- 事实：成片 238.500s vs 时间轴 438.0s → S09–S12 未被渲染（S08 被截断）。
- 机制：`EditingAgent._narration_args` 以 `-t {total} -shortest` 收尾；`total` 由**脚本时基**（Σduration_s+2=438s）决定，而音轨只有 236.448s → ffmpeg 在音轨结束处停止输出。
- 上游根因：`voice` 任务 3 次真实运行分别只合成 **1/12、9/12、7/12** 段（见 `logs/phase2_voice_stage_attempts.md`），空文件即失败段。
- 结论：素材装配侧无缺陷；**"时间轴被完整实现"这一点无法在当前音轨条件下证明** → PENDING。

### PENDING-2：旁白音轨内容与脚本时基错位
- `narration.mp3` 是**成功段**的顺序拼接（缺 seg_00/01/02/10/11），因此 t=0 起播放的是 S04 的旁白，而画面在 S01 → **A/V 语义错位**（画面窗口本身没错，音轨内容错位）。

### PENDING-3：`VoiceAgent` 失败开放（fail-open）——既有设计，未擅自更改
- 事实：11/12 段 TTS 失败时任务仍 `SUCCEEDED`，`confidence=1.0`，summary 只写"1 段合成为 narration.mp3"；`errors` 数组记录了失败但无人消费。
- 代码注释显示这是**有意的**设计（"合成失败…降级为计划模式并记录原因，不阻塞管线"），故**属于设计决策，需授权后才能改**（建议：逐段重试 + 复用已成功段 + 失败比例超阈值时判 FAILED）。
- 触发条件：`speech.platform.bing.com` 间歇性 `ClientConnectorError/ClientOSError`（本机同时段 `api.deepseek.com` 正常）。

### PENDING-4：fallback 分类学仍是 Phase 2-C 范围
- 目前只有 `LOCAL_INGEST` / `SOLID_COLOR_CARD`；`REAL_ASSET` / `FALLBACK_GENERATED` 等**未实现、未声称**。

### PENDING-5（延续）：语义级"镜头↔旁白"对齐
- 当前匹配是**词法**混合打分（1.1 期已给设计，未实现）。

### PENDING-6（延续，Phase 1.1）：成本残余 ≈¥3.24 无法在客户端归因
### PENDING-7（延续，Preflight）：GBK 具体触发条件 `ROOT_CAUSE_NOT_REPRODUCED`
### PENDING-8（延续）：Git tag `BLOCKED`（`STATUS.md:5` 记录用户指令"无 Git 仓库"）→ 用 ZIP+SHA256+清单代替

---

## 6. 验证器自身的两处修正（避免把工具缺陷当成产品缺陷）

1. **status 表列位读错**：状态表为 9 列，错误文本在下标 9；初版驱动读下标 8，把已 redo 成功的任务误判为"重做 2 次仍失败"。已改为**按类型最高版本**判定现行状态（低于最高版本的 BLOCKED 行是历史记录）。
2. **抽帧越界 clamp**：初版把超出成片时长的镜头 clamp 到片尾取帧，导致 S09–S12 被误报为"不匹配/画面相同"。已改为：起点在成片内 → 在**可见区间**取中点（并标注"被成片结尾截断"）；起点已超出 → 记"未渲染"，单列 PENDING。
3. 判重口径：只比较**期望素材不同**的镜头对（同素材复用 ≈1 属预期）。

---

## 7. 本阶段代码改动（可追溯）

| 文件 | 改动 |
|---|---|
| `src/video_studio/agents/editing/agent.py` | 新增 `_kw_tokens` / `_match_score` / `_build_material_timeline`；`_narration_args(..., timeline=)` 走逐镜头多输入装配（`-loop 1 -t` + scale/crop/setsar/fps + `concat` + drawtext + fade）；`render_output` 新增 `material_timeline / assets_used / scene_count / scenes_with_asset / fallback_scenes / material_assembly / visual_source`；新增 `MATERIAL_TIMELINE` 事件；修复 `img` 使用未导入 `Path` 的缺陷 |
| `src/video_studio/agents/retrieval/agent.py` | 词法混合打分 + `matched_tokens`；索引解析优先"文件最多的 asset_index"；查询回退自依赖产物；`material_mode` 三态 |
| `tests/scene_assembly_test.py` | 新增 15 例确定性装配测试（免费、无 LLM） |
| `docs/regression_2x/phase2_accept.py` | 新增验收驱动（init→ingest→plan→script→批准→settled→产物/抽帧核验），支持 `--resume/--redo/--verify` |
| `docs/regression_2x/phase2_evidence.py` | 新增证据汇总器（任务/成本/素材/音轨/成片/时间轴） |
| `docs/regression_2x/run_ingest_test.py` | 期望值更新为 `material_timeline` 语义，并**新增强制抽帧核验**（免费机械证据） |

---

## 8. 停止点

按授权：本阶段到此为止。**Phase 2-C 未开始**，等下一子阶段授权（建议优先处理 PENDING-1/2/3 —— 音轨完整性与 `VoiceAgent` fail-open，因为它们决定"时间轴能否被完整实现"这一验收项）。
