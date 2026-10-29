# video-studio · AI 视频生产多 Agent 系统

**Python 3.12+ · License: MIT · 平台：Windows（开发/实测环境），其余平台未验证**

> **English TL;DR** — `video-studio` is a multi-agent video production system: 25 specialized
> agents (topic → research → script → fact-check → voice → material retrieval → render →
> subtitles → QA) turn a one-line goal into a finished narrated video, with claim-level human
> review gates, word-level subtitle sync, per-scene material licensing gates, loudness
> contracts and render gates that fail closed. LLM-optional: a Mock mode runs the full
> pipeline with zero API keys. Docs are mostly Chinese.

人类负责创意与判断，Agent 负责生产流程——本系统把「一句话选题」变成一条可播放、
可溯源、经过技术门禁检验的解说视频，全程任务落盘、断点可恢复、人工闸门可审计。

---

## 它能做什么

| 能力 | 说明 | 所在位置 |
|---|---|---|
| 端到端流水线 | 26 个标准任务（选题→研究→结构→脚本→配音→素材→剪辑→渲染→字幕→质检→发布包），4 道任务级人工闸门 + Claim 级审核闸门 | `src/video_studio/agents/`、`pipeline/` |
| 事实核查系统 | Claim 抽取→证据检索→来源核查→冲突检测；存在 `NEEDS_HUMAN` 的 Claim 时渲染类任务一律不派发 | `agents/claim_extractor` 等 V2 链 |
| 词级字幕同步 | 字幕时序锚定 TTS 词级时间戳（WordBoundary），实测句起点同步中位差 0.000s、零重叠 | `core/captions.py` |
| 解释级可视化生成器 | 从旁白语义节拍计划生成确定性模板动画（地图四色着色/冲突闪现修正/清单/坍缩/时间轴），逐拍校验「旁白引用↔cue」，不合格拒绝渲染 | `core/explain_viz.py` |
| 素材许可门禁 | 外部素材（Wikimedia Commons 已接入）逐个经 magic bytes/容器完整性/ffprobe/PIL 解码/许可证分类校验；许可不明→拒收+人工介入；渲染产出署名台账 `credits_*.txt` | `core/materials.py` |
| 音频响度契约 | 成片统一 -16 LUFS ±1 / 真峰 ≤ -1.5 dBTP，渲染后以 `ebur128` 实测回写，偏差过大直接 BLOCKED | `core/audio.py` |
| 防回归技术门禁 | 签名门 / 分配指纹 / 渲染前后 PI 门 / 烧录四门（覆盖·时长·重叠·同步）全部 fail-closed | `core/integrity.py`、各 driver |
| 一切落盘 | 任务/事件/产物/审批/决策存 SQLite(WAL)，append-only；`recover` 断点续跑、`redo` 任务重做（版本+1） | `core/engine.py`、`db/` |
| 只读运维 | `report` / `metrics`（确定性输出）/ `semantic-check`（离线三态语义核验）/ `review`（人审替换队列） | `cli.py` |

**诚实的边界**：Mock 模式只替换 LLM 文本；TTS 默认 `edge-tts`（免费、无需密钥、但需要网络），
完全离线时 voice 任务会如实失败而非伪造音轨。素材不足时该镜头记为 `SOLID_COLOR_CARD` 占位
并显式标注，绝不伪造素材。回归脚本中的绝对路径为开发机遗留，属已知限制。

## 架构总览

```
一句话选题
   │
   ▼
[orchestrator/pm] → topic → research → source_verify → structure → script ─┐
                          │            (Claim 级事实核查链：                │
                          │             claim_extractor → evidence →       │ 人工审稿
                          │             fact_check → conflict_detector)    ▼
                          ▼                                            script-review
                    4 道人工闸门 + Claim 闸门（NEEDS_REVIEW / NEEDS_HUMAN）
   │
   ▼
voice(edge-tts 词级时间戳) → visual → retrieval(素材检索+许可门禁) → editing ──► render
   │                                                                              │
   │                    explain_viz（语义节拍 → 解释性模板动画，可选接入）          │
   ▼                                                                              ▼
audio(响度契约) → subtitle(词级同步) → thumbnail/metadata/platform → qa → 发布包
```

25 个 Agent 按算力分档：**R**（reasoner：source_verify / fact_check / critic / compliance）、
**M**（chat：orchestrator / pm / topic / research / structure / script / visual / editing /
thumbnail / platform / metadata / qa / analyst 等）、**免 LLM**（asset / retrieval / voice /
audio / subtitle 等确定性角色）。

## 快速开始

### 0. 环境要求

- Python ≥ 3.12，安装依赖：
  ```bash
  pip install -e .
  ```
  （依赖很少：`requests` / `pillow` / `numpy`，见 `pyproject.toml`）
- **ffmpeg + ffprobe**：放入仓库 `bin/` 目录（`bin/ffmpeg.exe`、`bin/ffprobe.exe`）或加入 PATH；
  `python scripts/check_binaries.py` 可自检（会验证二进制真实可用、不得互相冒充）。

### 1. 零 API 密钥试跑（Mock LLM）

```bash
# a) 30 秒冒烟（纯离线，12 项检查）
python tests/smoke_mock.py

# b) 走一遍真实 CLI 生命周期（Mock 只替 LLM 文本；TTS 需网络，无密钥）
python run.py --config config/config.mock.json init "做一期鲸鱼娘皮肤幕后视频" --name demo
python run.py --config config/config.mock.json plan <项目ID>      # 创建 26 个任务
python run.py --config config/config.mock.json run <项目ID>       # 推进调度（需重复执行）
python run.py --config config/config.mock.json status <项目ID>    # NEEDS_REVIEW = 待人工闸门
python run.py --config config/config.mock.json approve <任务ID> approve   # 逐个批准 4 道任务闸门
python run.py --config config/config.mock.json claims <项目ID>    # Claim 级闸门（V2 必过）
python run.py --config config/config.mock.json approve-claim <claim_id> approve
python run.py --config config/config.mock.json run <项目ID>       # 直到无新任务
```

- **必须人工过闸**：`topic / structure / script / editing_plan` 四道任务闸门 + 全部 Claim。
  省略 Claim 审批会导致生产环节永远不派发——这是 V2 的设计而非缺陷。
- Mock 模式下 LLM 返回预置文案（内容与输入无关）；成片为纯色底 + 烧录字幕
  （无素材时），工程闭环完整，**内容保真需真实 API**。
- 集成测试（离线全管线出片，TTS 用本地正弦替代）：`python tests/pipeline_mock.py`
  （需要 `bin/ffmpeg.exe`，见上方环境要求）。

### 2. 接入真实 LLM

```bash
cp .env.example .env        # 填入 DEEPSEEK_API_KEY（密钥只从环境变量读取，禁止硬编码）
```

默认 `config/config.json` 即真实 DeepSeek 配置（按任务档位 R/M/F 路由模型，含预算上限）；
其余云端服务（search / image / video / TTS / ASR）按需在 `tools.*` 配置 provider。
已内置的真实外部素材 Provider：**Wikimedia Commons**（免费、无需密钥，启用方式见
[docs/README_V2_ENGINEERING.md](docs/README_V2_ENGINEERING.md)）。

### 3. 测试与回归

```bash
python tests/smoke_mock.py                    # 核心闭环冒烟（12 项）
python tests/pipeline_mock.py                 # 25 Agent 全管线集成（12 项，真实 ffmpeg 出片）
python docs/regression_2x/run_all_suites.py   # 全部回归套件（开发机口径）
```

注意：`src/video_studio/orchestration/tests/fixtures/` 的实拍图夹具因含真实人物肖像
**未随本仓库发布**（见该目录 README），该组用例需自行放置夹具后才能运行。

## 仓库结构

```
src/video_studio/     agents(25) | core(引擎/门禁/字幕/音频/素材/explain_viz) | tools | llm | db | hitl
config/               运行配置：config.json(真实) / config.mock.json(零密钥) / 规则与风格文件
tests/                冒烟 + 全管线集成
docs/                 设计与全部阶段报告；regression_2x/ 为回归驱动脚本
STATUS.md             开发进度总账（断点续做依据，全部阶段记录）
CHANGELOG.md          按阶段的工程变更史
```

## 文档地图

| 文档 | 内容 |
|---|---|
| [docs/DESIGN.md](docs/DESIGN.md) | V1 总体设计 |
| [docs/V2_SPEC.md](docs/V2_SPEC.md) | V2 规格（事实核查 / Claim 闸门） |
| [docs/RUNBOOK.md](docs/RUNBOOK.md) | 运行手册（闸门/失败恢复/真实服务前置条件） |
| [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md) | 已知问题台账（如实记录，不做遮掩） |
| [docs/README_V2_ENGINEERING.md](docs/README_V2_ENGINEERING.md) | V2.0 详细工程说明（素材校验链/响度契约/降级分类学等） |
| [STATUS.md](STATUS.md) / [CHANGELOG.md](CHANGELOG.md) | 完整开发日志（Phase 1–60，含每轮的门禁数据与失败留痕） |

## 设计原则

这个仓库的工程纪律比功能列表更值得看：

1. **Fail-closed**：任何校验不过（字幕跨度、旁白完整、素材许可、响度偏差、动画节拍计划）
   一律阻断并留痕，绝不静默降级或伪造产物。
2. **不伪造**：素材不足 → 显式占位并标注；Mock 与真实路径严格分离；测试修了必须接进生产
   （历史上为此专门立项五次）。
3. **可审计**：append-only 产物与事件；每个渲染都有分配指纹；每条外部素材有许可台账与
   出现于成片的抽帧证据。
4. **人在环上**：创意与判断（选题/结构/脚本/剪辑方案/Claim 结论）必须人工批准，Agent 只
   管生产与自证。

## License

[MIT](LICENSE)
