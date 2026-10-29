# 运行手册（RUNBOOK）— 3.x Final

> 适用范围：`C:\mp4agent\video-studio`（无 Git，版本以 `STATUS.md` + `CHANGELOG.md` + 基线 ZIP 为准）。
> 所有命令均在仓库根目录执行；Python 用 `C:\python3.13\python.exe`（装有 `edge_tts/numpy/PIL`）。

---

## 1. 正式入口

| 目的 | 命令 |
|---|---|
| 新建项目 | `python run.py init "目标描述" [--name 名字]` |
| 创建标准管线全部任务 | `python run.py plan <project_id>` |
| 推进调度（执行就绪任务） | `python run.py run <project_id> [--limit N]` |
| 自动推进（含自动批闸门，**演示用**） | `python run.py loop <project_id> [--auto-approve] [--max-rounds N]` |
| 查看任务表 | `python run.py status <project_id>` |
| **只读体检报告**（推荐） | `python run.py report <project_id> [--json]` |
| 人工审批任务闸门 | `python run.py approve <task_id> approve\|reject\|modify [--comment 备注]` |
| Claim 事实核查闸门 | `python run.py claims <project_id>` / `claim <claim_id>` / `approve-claim` / `reject-claim` / `revise-claim` |
| 素材登记（本地素材） | `python run.py ingest <project_id> <source_dir>` |
| 崩溃恢复 | `python run.py recover` |

配置：`--config config/config.json`（默认）。**默认配置 `provider=none`**（不访问任何外部素材服务）；
真实外部素材用 `--config config/config.real.provider.json`。

## 2. `resume` / `redo retrieval` / `redo render` / 验证命令的区别（最常踩的坑）

| 动作 | 命令 | 语义 | 会不会重新取数/渲染 |
|---|---|---|---|
| **接着跑** | `python run.py run <pid>` | 只执行 **PENDING/就绪** 的任务 | 不会（已 SUCCEEDED 的不动） |
| **核验** | `python docs/regression_2x/phase3a_real_chain.py --resume <pid>` | **只读复核**（推进未结算任务后核验产物） | **不会**——`--resume` 不重做已成功任务 |
| **重做 retrieval** | `python run.py redo <retrieval_task_id>` → `python run.py run <pid>` | 建 version+1 的新任务并重跑 | **会**：重新搜索/下载外部素材 |
| **重做 render** | `python run.py redo <render_task_id>` → `python run.py run <pid>` | 同上 | **会**：重新渲染成片（含响度母带与 QC） |
| **崩溃恢复** | `python run.py recover` | 把中断（RUNNING/DISPATCHED）任务回队 | 只重跑被中断的 |
| **验收复核** | `python docs/regression_2x/phase2_accept.py --verify <pid>` | 只读复核成片/时间轴/抽帧 | 不会 |

> **要点**：想"重新取数或重新出片"必须**显式 `redo`**；`--resume`/`--verify` 都只核验。
> 取 task_id：`python docs/regression_2x/list_tasks.py <pid>`。

## 3. 前置条件

| 能力 | 前提 | 不满足时的表现 |
|---|---|---|
| **真实 LLM** | `config/config.real*.json` + 项目根 `.env` 里的 `DEEPSEEK_API_KEY`；余额充足 | 401/402 → 任务失败；超预算 → **发请求前** `LLM_BUDGET_EXCEEDED`（`llm.max_total_usd`，默认 0.60） |
| **真实 TTS** | `edge_tts` 可用 + 网络可达 `speech.platform.bing.com` | 段级失败 → 逐段状态记录 + 重试；仍失败 → `voice` 产物不完整 → **渲染前闸门阻断**（`NARRATION_INCOMPLETE`） |
| **真实素材 Provider** | `config/config.real.provider.json`（provider=`wikimedia_commons`，免费、无需 key） | 未配置/被阻断 → `external_error` 记具体错误码；无可用素材 → `ASSEMBLY_BLOCKED` → **render BLOCKED** |
| **ffmpeg/ffprobe** | `bin/ffmpeg.exe` + `bin/ffprobe.exe`（真二进制，`python scripts/check_binaries.py` 可验） | ffprobe 非真 ffprobe → `FFPROBE_INVALID`（fail-closed）；ffmpeg 缺失 → render 置 BLOCKED（不空耗重试） |
| **离线回归/单测** | 无需网络（除 `phase2e_*`/`phase3a_real_chain` 等真实网络项） | — |

## 4. 外部 Provider（Wikimedia）异常处理

| 现象 | 错误码/证据 | 处理 |
|---|---|---|
| 429 限流（**最常见**；下载腿尤其严重） | `stats.rate_limited` / `PROVIDER_RATE_LIMITED` | 已内置 `min_interval_s`（默认 3.0s）请求/下载共用的最小间隔 + 429 专用退避（`rate_limit_backoff_s`，默认 10s，上限 30s）+ `rate_limit_retries`（默认 3）。**不要**把手动重试间隔调小 |
| 请求超时 | `PROVIDER_TIMEOUT` | 检查 `tools.material.timeout_s`（默认 25s）；网络抖动可直接重跑 `redo retrieval` |
| 搜索超时/失败 | `PROVIDER_TIMEOUT` / `PROVIDER_SEARCH_FAILED` | 搜索 API 一般不受限流影响；连续失败先跑 `python docs/regression_2x/phase3a_net_probe.py` 判断是否链路问题 |
| 下载失败/被拒 | `PROVIDER_DOWNLOAD_FAILED` / `ASSET_OVERSIZE` / `ASSET_TRUNCATED` / `ASSET_LICENSE_*` | 逐条记在 `external_rejected`（带 `error_code`）。被拒**绝不**入片；许可不明 → `needs_hitl` |
| 域名不可达（TLS 被链路阻断） | 所有请求超时；`phase3a_net_probe.py` 显示 TCP 通、TLS 超时 | 属环境问题（非代码）：等网络恢复后 `redo retrieval`；期间如实记 PENDING，**不得**用缓存/Mock 冒充真实下载 |
| 查询命中为 0 | `query_shaping.attempts[]` 全为 0 条 | 见 §6「检索 0 命中」 |

## 4b. 供给韧性开关（4-D，**默认关闭**）与失败判读

4-D 只在外部 provider 路径外层加了一层"缓存 + 分类 + 可解释 + 降级"，**默认全部不改变既有行为**：

| 开关（`config/config.json` → `tools.material`） | 默认 | 作用 |
|---|---|---|
| `supply_cache` | `false` | 打开后，**搜索层**结果按 `(provider, 查询, limit, kinds, 关键词, 策略指纹)` 缓存到 `<项目>/.supply_cache/search/`；命中只省一次搜索请求 |
| `supply_cache_ttl_s` | `900` | 缓存有效期（秒）；0 = 不过期 |
| `retry_after_max_s` | `30` | 采纳 HTTP `Retry-After` 的上限（防止无限等待） |

**打开缓存的建议**：仅在真实外部 provider（`wikimedia_commons`）下、且同一查询会被重复执行时打开
（例如反复 `redo retrieval`）。**不要**在需要"每次都打真实网络"的验收里打开。

**安全性质（已测）**：缓存**只存候选元数据**，不存"已验证"结论与本地路径；命中后仍会重新下载
（内容寻址缓存可省流量）、重新跑 `verify_material` 全量校验与许可门禁 —— 未验证素材**不可能**因缓存入片。
缓存过期/损坏/schema 不符一律按"未命中"处理。

**失败判读（错误码 → 类别 → 处置）**：`python -c "from video_studio.core.supply import classify_failure as c;
print(c('PROVIDER_RATE_LIMITED'))"`，或看检索产物 `external_provider.supply_report`：

| 类别 | 含义 | 要不要重试 |
|---|---|---|
| `TRANSIENT` | 超时/429/5xx/下载失败/空响应 | 由 `retry_decision` 有界重试（429 10/20/30s，其它 0.2s 线性 ≤2s） |
| `PERMANENT` | 404/鉴权/素材本身坏了（类型不符、截断、超限、尺寸不足） | 不重试；换素材或修目录 |
| `POLICY` | 请求预算用尽、缓存上限、未配置、复用策略冲突 | 不重试；下次运行或人工处理 |
| `LICENSE` | 许可缺失/不明/受限 | **绝不重试、绝不放行**；`run.py review` 走人工（HITL） |

**看降级路径**：`supply_report.degradation.rung` ∈ `EXTERNAL_VERIFIED → LOCAL_INGEST → THEME_FALLBACK →
SOLID_COLOR_CARD → BLOCKED_FOR_HUMAN`；`requires_human=true` 表示该镜头必须人工知悉（不会静默出片）。

## 4c. 检索质量开关（4-E，**默认关闭**）与 A/B 复算

4-E 只在**检索打分/查询形状**上提供可选的改进，**默认仍是既有实现**（`v1` = `kw_tokens` + `score`，一字未改）：

| 开关（`config/config.json` → `tools.retrieval`） | 默认 | 作用 |
|---|---|---|
| `scoring` | `"v1"` | `"v2"` = 多语言归一（复数/停用单字/保留 `vr`·`hmd` 等 2 字符缩写）+ 4-E 词典**概念扩展** + 拉丁**词边界**匹配 |
| `query_expansion` | `false` | `true` = 当查询**没有拉丁词**时，用 4-E 词典补拉丁查询串（中文 → `virtual reality headset` 之类），并同步重算 provider 侧关键词 |

**什么时候打开**：中文/多语言脚本要检索英文语料（Wikimedia Commons）时打开 `query_expansion`；
素材库以中文命名为主时，`scoring` 保持 `v1` 即可（中文名 v1 本就能命中）。
打开后检索产物会记录 `retrieval_config{scoring, query_expansion, expanded_terms, lexicon}`，便于追溯。

**开门禁不变**：无论开关如何，候选仍要过 `verify_material` 全量校验 + 许可门禁；语义正确性仍由 4-B 判定。
**分数不可跨版本比较**（v1 分数被字符级关键词抬高）——比较请用指标，不要比分数。

**A/B 复算（离线、确定性）**：

```powershell
C:\python3.13\python.exe docs\regression_2x\phase4e_ab_benchmark.py    # -> logs/phase4e_ab_results.json / .txt
C:\python3.13\python.exe tests\retrieval_quality_test.py               # 35/35，A/B 数值已冻结为断言
C:\python3.13\python.exe docs\regression_2x\phase4e_zh_query_probe.py  # 真实网络中文查询探针（环境相关）
```

指标口径：`TP`（域命中）/`FP`（域不符或"期望无结果却给候选"）/`UNKNOWN`（歧义查询命中，**不计 TP**）/
`FN`（期望域一条都没命中）；另有 `domain_hit_rate`、`top1_correct_rate`、`empty_correct_rate`。

## 4d. 可选 BGM + 旁白 ducking 开关（4-F，**默认关闭**）

4-F 的 BGM 是**可选扩展**：不配置就完全不启用，既有音频链、成片与 credits 与之前**逐字一致**。

```jsonc
// config/config.json -> tools.bgm（示例：启用一首已确认许可的本地 BGM）
"bgm": {
  "enabled": true,
  "source": "media/bgm.wav",          // 相对项目目录，或绝对路径
  "provider": "local_bgm",            // 来源标识（外部素材填 provider 名）
  "source_id": "my_track_v1",         // 来源条目 id / 文件名
  "license": "CC BY-SA 4.0",          // 机械判类：PUBLIC_DOMAIN / FREE_ATTRIBUTION 才放行
  "attribution": "作者 / 许可 / 来源链接",   // **必填**，缺失即拒绝
  "sha256": "<可选：期望值，给了一致才放行>",
  "bed_db": -20.0, "duck_db": -26.0, "ramp_ms": 250
}
```

| 行为 | 说明 |
|---|---|
| 校验 | 来源 / sha256 / 音频流 / 解码 / 时长 / 响度 / 静音 / 异常响度 / **许可** / **attribution** 全部通过才启用 |
| 拒绝 | 任一不通过 → 渲染 **BLOCKED**，错误形如 `[BGM_REJECTED] BGM_LICENSE_RESTRICTED: ...`；**不会**产出"悄悄没有 BGM"的成片 |
| ducking | 旁白时间段由 voice 逐段真实时长累加；期间 `duck_db`、之外 `bed_db`、边界 `ramp_ms` 线性过渡；**提前 ramp** 进入 duck（旁白优先）；重叠区间合并；`amix normalize=0` 不改旁白电平 |
| 过长/过短 | 长于片长 → 截断（`trimmed_to_film=true`）；短于片长 → **补静音**（`padded_after_bgm_end=true`，不循环） |
| 契约 | 成片仍须 `-16 LUFS ±1` / `TP ≤ -1.5 dBTP`；BGM 路径用**两遍线性** loudnorm（单遍动态在大动态混音上会低 ~3.5 LU），成片仍由既有 QC 实测把关 |
| 证据 | `render_output.bgm`（开关/校验/预混/母带/包络/区间）、`attribution.bgm`、credits 文件中的 BGM 段 |

**排查**：看 `run.py report <pid>` 的 `render_output.bgm`；被拒时 `tasks.error` 里有具体 `BGM_*` 码。
复算证据：`python docs/regression_2x/phase4f_evidence.py` → `logs/phase4f_bgm_evidence.json`；
单测：`python tests/bgm_ducking_test.py`（48/48）。

## 4e. 只读节奏分析与人工建议（4-G）

```powershell
python run.py rhythm <project_id>            # 人读版：建议 + 依据 + 动作 + 风险 + UNKNOWN
python run.py rhythm <project_id> --json     # 机器可读（确定性：多次运行逐字节一致）
python run.py rhythm <project_id> --artifact <render_output_artifact_id>   # 钉定某一版产物
```

| 项 | 说明 |
|---|---|
| 性质 | **只读**：`mode=ro` 打开数据库；不建任务/不写产物/不改时间轴·时长·旁白·素材·BGM/不触发 redo/不访问网络 |
| 规则 | 镜头过短/过长、旁白段落过短/过长、切换落在旁白句中、旁白超时轴被裁、切换密度高/低、静态画面持续、BGM duck 碎片化 |
| UNKNOWN | 时长缺失、旁白不可用、素材类型未知、成片时长缺失、旁白总时长缺失、BGM 未生效 → **只记 UNKNOWN，不给建议** |
| 建议字段 | `scene_id`、当前时长、规则、证据（实测/阈值/差值或时间窗）、建议动作、风险、置信度；`status=SUGGESTION`、`applied=false`、`executed=false` |
| 阈值 | `config/config.json → tools.rhythm`（默认 `min_scene_s=3`、`max_scene_s=20`、`static_warn_s=15`、`min/max_cuts_per_min=2/12`、`narration_boundary_tolerance_s=0.5`、`narration_seg_min/max_s=4/30`、`bgm_duck_transitions_warn=2`） |
| 边界 | 建议**不会自动生效**：任何改动都必须人工决定后另行走审批与 `redo`（建议器不触发、不写 decisions/changelog） |

证据与复算：`python docs/regression_2x/phase4g_evidence.py` → `logs/phase4g_rhythm_evidence.json`；
单测：`python tests/rhythm_advisor_test.py`（34/34，含只读与确定性证明）。

## 4f. 响度契约里的 LRA 到底是什么（4.x 收口审计结论）

**结论（有代码 + 行为 + 实测三重证据）**：

> `TARGET_LRA = 11` 是 ffmpeg `loudnorm` 的**目标参数**（写进滤镜串 `loudnorm=I=-16:TP=-1.5:LRA=11`），
> 同时作为**参考/复现值**记录在 `LOUDNESS_CONTRACT["target_lra"]` 与产物证据里。
> 它**不是硬门槛**：fail-closed 闸门 `core.audio.check_contract()` **只判两项** ——
> 集成响度 `-16 LUFS ±1`、真峰 `≤ -1.5 dBTP`。

**证据**：① 闸门源码中没有 LRA 字样；② 把实测 LRA 改成 99 LU 或 0.5 LU，闸门结论都不变；
③ 实测值：4-C v5 成片（纯旁白）**LRA 2.0 LU**；4-F 含 BGM 的预混输入 **18.30 LU**、
两遍母带后与交付成片均为 **13.8 LU**（详见 `docs/regression_2x/PHASE4X_FINAL_AUDIT.md` §4）。

**实践含义**：含 BGM 的成片 LRA 天然比纯旁白大，这不构成违约；若将来要把 LRA 变成硬门槛，
属于**契约变更**，需要新的授权（见 `docs/KNOWN_ISSUES.md` #15）。

## 4g. 多模态语义验证（5-A，真实视觉模型 CLIP，**只读**）

```powershell
python run.py multimodal-check <project_id>                      # 人读：逐镜头 MATCH/MISMATCH/UNKNOWN + 依据
python run.py multimodal-check <project_id> --json               # 机器可读（确定性：两次运行一致）
python run.py multimodal-check <project_id> --artifact <render_output_id>   # 钉定某一版成片（如 4-B 真值产物）
python run.py multimodal-check <project_id> --out report.json    # 可选：把 JSON 报告写到指定路径
```

| 项 | 说明 |
|---|---|
| 做什么 | 按镜头窗口从成片抽帧 → **本地 CLIP ViT-B/32**（离线 CPU）判"画面最像哪个语义域" → 与**旁白推导的期望域**比对 → 三态 |
| 期望域来源 | 4-B 词表为主；无命中时回退 4-E 检索词典；两级都无命中 → `UNKNOWN / MM_UNKNOWN_DOMAIN` |
| 判定 | `expected_sim ≥ 0.20` 且领先最强其它域 `≥ 0.02` → MATCH；被反超 `≥ 0.02` → MISMATCH；否则 UNKNOWN |
| 只读 | `mode=ro` 打开库、抽帧写系统临时目录、不写库/不写生产产物/不改选材·时间轴·旁白·BGM/不触发 redo |
| 与 4-B 的关系 | **新增证据层**：4-B 结论原样保留、不覆盖不删除；两层并列对照（真值产物 `a_2ed5f41d6b58` 上 S04/S06 两层都判 MISMATCH） |
| 依赖 | `.venv_tts\Scripts\python.exe`（torch 2.13.0+cpu / transformers 4.57.6）+ `models/clip/.../clip-vit-base-patch32`（权重 sha256 `a63082132ba4f97a…`） |
| 不可用时 | 一律 `UNKNOWN` + 明确错误码（`MM_MODEL_MISSING` / `MM_PYTHON_MISSING` / `MM_TIMEOUT` / `MM_NO_FRAMES` / …），**绝不伪造判定** |

证据与复算：`python docs/regression_2x/phase5a_evidence.py` → `logs/phase5a_multimodal_evidence.json`；
单测：`python tests/multimodal_test.py`（34/34，含真值回归与 fail-closed 用例）。

## 4h. 多模态候选复核（5-B，**只生成候选**）

```powershell
python run.py mm-review <project_id>                      # 为 MISMATCH/低置信镜头列出候选（人读）
python run.py mm-review <project_id> --json               # 机器可读（确定性）
python run.py mm-review <project_id> --artifact <render_output_id>   # 钉定某一版成片（如 4-B 真值产物）
python run.py mm-review <project_id> --out candidates.json # 可选：写到指定路径
```

| 项 | 说明 |
|---|---|
| 触发条件 | 只对 5-A 判为 `MISMATCH` 或低置信 `UNKNOWN`（`MM_AMBIGUOUS`/`MM_LOW_SIGNAL`）的镜头生成候选 |
| 候选来源 | 该项目**全部** `retrieval_candidates` 产物里 `verified=True` 且**本地文件存在**的素材（池外/被拒候选单列） |
| 证据 | asset / 来源 / 许可证（机械判类 + 门禁结论）/ **视觉相似度**（同一 CLIP 模型按 12 域打分）/ 旁白关联（期望域与命中词）/ 风险清单 |
| 状态 | `CANDIDATES_READY` / `BLOCKED:MMC_NO_CANDIDATES` / `BLOCKED:MMC_NO_LICENSED_CANDIDATE` / `UNKNOWN:MMC_MM_UNAVAILABLE` / `UNKNOWN:MMC_UNKNOWN_DOMAIN` / `UNKNOWN:MMC_LOW_VISUAL_SIM` |
| **不做** | 不自动选材、不自动替换、不自动 redo、不写库、不写产物；`select-candidate` 调用 0 次、`redo` 触发 0 次 |
| 人工确认（唯一写入口，仍是 4-C） | 复制报告里的 `human_command` 自行确认者身份与理由后执行；随后由人工执行 `redo` |

**排查**：候选为空 → 看 `rejected[].excluded_reasons`（`LOW_VISUAL_SIM` / `LICENSE_NOT_CLEAR` / `CURRENT_ASSET` /
`USED_BY_OTHER_SCENE`）与 `pool_summary`（verified_local vs unusable）；模型不可用 → 报告级 `UNKNOWN/MMC_MM_UNAVAILABLE`。
证据与复算：`python docs/regression_2x/phase5b_evidence.py` → `logs/phase5b_candidates_evidence.json`；
单测：`python tests/mm_candidates_test.py`（29/29）。

## 4i. 候选替换生效的完整闭环（5-C 实操口径，**写入口仍是 4-C**）

```powershell
# 1) 人工浏览候选（只读）
python run.py review p_f4b466a4a024            # 4-C 复核队列（含候选/许可/可用性）
python run.py mm-review p_f4b466a4a024 --json  # 5-B 多模态候选（含视觉证据/风险）
# 2) 人工明确选定（唯一写入口：写既有 decisions + changelog）
python run.py select-candidate p_f4b466a4a024 --scene S06 --asset asset_f3cf2b80432d `
       --by human:<你的标识> --reason "<选择理由>"          # 先加 --dry-run 只校验不写
# 3) 人工发起版本+1 重渲染，并推进到完成
python run.py redo <上一版 render_task_id>     # 打印 "已创建重做任务: t_xxxx"
python run.py run p_f4b466a4a024 --limit 4     # 重复执行直到新版本 SUCCEEDED
# 4) 替换后复验（全部只读）
python docs/regression_2x/phase5c_snapshot_after.py    # 版本链/时间轴/哈希对比
python docs/regression_2x/phase5c_append_only.py       # append-only/attribution/许可门禁/未授权镜头
python docs/regression_2x/phase5c_db_append_only.py    # 与冻结 DB 快照逐表逐行比对（最强口径）
python docs/regression_2x/phase5c_verify_film.py <render_output_artifact_id>  # 编码/时长/独立响度/逐镜头抽帧
python run.py semantic-check p_f4b466a4a024 --json     # 4-B（对最新成片）
python run.py multimodal-check p_f4b466a4a024 --artifact <id> --json   # 5-A（钉定版本）
python docs/regression_2x/phase5c_regression.py        # 全量回归 3-A～5-B（不改动冻结日志）
```

| 项 | 说明 |
|---|---|
| 前置 | 5-B 报告里该镜头必须是 `CANDIDATES_READY`（候选为空/全不可用时**不得**随便选一个） |
| 校验 | 选定素材必须在该镜头候选池内、可用、许可已清；否则 `HUMAN_SELECTION_*` → **拒绝且零写入** |
| 生效 | 渲染读"最新一条已批准决定"，写入 `selection_source="human_review"` + `human_selection{...}` |
| 失败 | 许可失败/候选失效/模型不可用 → **fail-closed**，绝不自动回退到别的素材（换材需新的 5-B 报告 + 新的人工决定） |
| 复验必看 | 5-A 判定可能**不变或退化**（资产级打分 ≠ 成片级判定，见 `KNOWN_ISSUES.md` #32/#33）——如实记录，不改阈值 |
| 证据 | `logs/phase5c_*.json`；回归结果另存 `logs/phase5c_rerun/`（冻结日志经 `logs_5b_frozen/` 备份后原样恢复） |

## 4j. 多帧/时序多模态验证（5-D，**只读平行证据层**）

```powershell
python run.py mm-temporal <project_id>                      # 7 帧/镜头 + 时序一致性（人读）
python run.py mm-temporal <project_id> --json               # 机器可读（确定性）
python run.py mm-temporal <project_id> --artifact <render_output_id>   # 钉定某一版成片（v5/v6 对照）
python run.py mm-temporal <project_id> --no-five-a           # 跳过 5-A 引用副本（省一次 3 帧验证）
python run.py mm-temporal <project_id> --out t.json --frames-dir <dir>
```

| 项 | 说明 |
|---|---|
| 解决什么 | 5-A 每镜头只抽 3 帧并做帧平均 → 单帧噪声/视角差异会让 `MATCH/UNKNOWN` 抖动；本层**加密到 7 帧**并做**帧间一致性**分析 |
| 每帧证据 | `id / time_s / sha256 / 期望相似度 / argmax 域 / 边际 / top-3 域`（逐帧可复核） |
| 聚合规则 | 期望相似度与边际的 **中位数/最小值/均值**、**逐帧 argmax 投票占比**、**相邻帧余弦**（mean/min）、**散布**、帧间平均域分数 |
| 判定（T0–T7） | `T1` 镜头内视觉切换（min 相邻余弦 < `split_cos`）→ UNKNOWN；`T2` 一致性 < `min_stability_cos` → UNKNOWN；`T3/T4` 多帧一致支持期望域/另一域 → MATCH/MISMATCH；`T5` 投票分散、`T6` 信号过低、`T7` 边际不足 → UNKNOWN |
| 置信度 | MATCH/MISMATCH：HIGH（一致性 ≥ `high_stability_cos` **且** \|中位边际\| ≥ 2×`margin`）/ MEDIUM；UNKNOWN：MEDIUM = **"稳定地判不出来"**（投票一致、无 split）/ LOW |
| 默认关闭 | `tools.multimodal_temporal` 缺省不存在；管线从不调用；只能人工执行只读命令（**不经过** `build_engine()`） |
| **不做** | 不换材、不选材、不 redo、不改时间轴/旁白/BGM、不写库、不写产物；**不改 5-A/4-B 结果**（报告里只放 `five_a_reference` 引用副本） |
| fail-closed | 模型/解释器缺失、无帧、worker 失败/超时/非法 JSON、帧数不足（< `min_frames`）、期望域推不出 → 一律 UNKNOWN + 明确错误码 |
| 复算 | `python tests/mm_temporal_test.py`（53/53）、`python docs/regression_2x/phase5d_evidence.py` → `logs/phase5d_evidence.json` |
| 已知限制 | 整帧嵌入受**烧录字幕**影响（#38）；时序层**不会**把 UNKNOWN 变 MATCH（#39）；阈值为工程默认且敏感性已披露（#40）；T1/T2 分支在本项目成片上不出现，由真实模型夹具覆盖（#42） |

## 4k. 多模态证据质量校准（5-E，**只读评估层**）

```powershell
python run.py mm-quality p_f4b466a4a024                     # 冻结真值集上并列评估 4-B/5-A/5-D（人读）
python run.py mm-quality p_f4b466a4a024 --json              # 机器可读（确定性）
python run.py mm-quality p_f4b466a4a024 --no-layers         # 只校验真值集结构与覆盖度（秒级自检）
python run.py mm-quality p_f4b466a4a024 --out q.json --frames-dir <dir>
python tests/mm_quality_test.py                             # 34/34（含真实校准与只读证明）
```

| 项 | 说明 |
|---|---|
| 真值集 | `tests/fixtures/mm_truth_set_v1.json`（**冻结**；sha256 由代码 `TRUTH_SET_PIN` 与证据双向钉定）；每例含**内容标签 + 出处 + 允许/禁止的输出 + 覆盖度标签** |
| 覆盖度 | 必须覆盖 S04/S05/S06、MATCH/MISMATCH/UNCERTAIN、viewpoint/temporal_split/边界/fail-closed 等维度；**不满足即 fail-closed**（`MMQ_INSUFFICIENT_COVERAGE`） |
| 三层并列 | 4-B（文本规则）/ 5-A（3 帧 CLIP）/ 5-D（7 帧 + 时序）：**只读取、不覆盖**；报告逐用例并列 verdict/code |
| 证据分级 | `MODEL_EVIDENCE`（相似度/投票/top-k）/ `RULE_INFERENCE`（verdict/rule）/ `ENGINEERING_THRESHOLD`（各阈值）/ `UNKNOWN`（无判定） |
| 边界距离 | `sim−min_sim`、`|边际|−margin`、投票−下限、一致性−下限、是否 top-1 → 直观看出"差多少会翻转" |
| 敏感性 | 阈值矩阵（含"更松"一侧）**只披露**；`flip_summary` 逐条列出翻转；**5-E 不采纳任何阈值改动** |
| 不做 | 不改判定逻辑/阈值、不换材/选材/redo、不改时间轴、不写库；4-B/5-A/5-D 结果原样保留 |
| 5-F 建议 | 报告内 `recommendations_5f`（R1–R6），全部 `implemented_in_5e=False` |
| 复算 | `python docs/regression_2x/phase5e_evidence.py` → `logs/phase5e_evidence.json`（ALL_GREEN） |

## 4l. 多模态证据 Judge（5-F，**只读最终判定**）

```powershell
python run.py mm-judge <project_id>                          # 最终三态 + 理由码 + DoD（人读）
python run.py mm-judge <project_id> --json                    # 机器可读（确定性）
python run.py mm-judge <project_id> --from-calibration docs/regression_2x/logs/phase5e_quality.json
python tests/mm_judge_test.py                                 # 43/43（含 J0–J6 规则与零写证明）
```

| 项 | 说明 |
|---|---|
| 规则 | **J0** 全层不可用 → UNKNOWN；**J1** 5-D 结构性 UNKNOWN（镜头内切换/帧数不足/一致性不足）→ UNKNOWN；**J2** 冲突（MATCH 与 MISMATCH 并存）→ UNKNOWN（不选边）；**J3** 有 MISMATCH 且无 MATCH → MISMATCH；**J4** 全层一致 MATCH（≥2 层）→ MATCH；**J5** 单层 MATCH → UNKNOWN；**J6** 其余 → UNKNOWN |
| 证据优先级 | ① 结构性（5-D 时序/样本）＞ ② 冲突 ＞ ③ 错配 ＞ ④ 一致 MATCH ＞ ⑤ 无法收敛 |
| UNKNOWN | **合法最终结果**；Judge 层**无任何阈值参数**，不存在"调阈值减少 UNKNOWN"的路径（DoD D7） |
| 输入 | 三层**独立**证据（4-B/5-A/5-D）；不改、不覆盖它们的报告与判定逻辑 |
| 不做 | 不换材/不选材/不 redo/不改时间轴/不写库；不自动发布；**不追求提高 MATCH 率** |
| 真值口径 | 冻结真值集 `mm_truth_set_v1.json`（14 例，`7eb952f2…`）+ Judge 覆盖层 `mm_judge_truth_v1.json`（`a6332858…`，case 集合必须完全一致） |
| 复算 | `python docs/regression_2x/phase5f_evidence.py` → `logs/phase5f_evidence.json`（ALL_GREEN）；DoD 见 `PHASE5F_MULTIMODAL_DOD.md` |



## 5. 常见失败与恢复

| 症状 | 含义 | 处理 |
|---|---|---|
| `CLAIM_GATE_BLOCKED` | 有 Claim 未人工审核，生产环节被闸门拦住 | `run.py claims <pid>` → `approve-claim/reject-claim/revise-claim` |
| `NARRATION_INCOMPLETE` | 旁白不完整或超时轴超容差 | `run.py status` 看逐段状态；重跑 `redo <voice_task>`；必要时 `redo <script_task>` |
| `ASSEMBLY_BLOCKED` / `ASSET_INSUFFICIENT` | 素材不足（无候选/全部不可用） | 检查 Provider 配置与网络；或 `run.py ingest` 提供本地素材 |
| `LOUDNESS_OUT_OF_CONTRACT` | 成片响度不满足 -16 LUFS ±1 / TP ≤ -1.5 dBTP | 看 `run.py report <pid>` 的响度小节；若 `mastering_applied=false` 说明配置关掉了母带链（故障注入用），改回默认即可 |
| 渲染后被抽帧核验判失败 | 分配素材未出现在其窗口 | 属真实缺陷信号（不回退）；`run.py report` 看 `material_verification.failed_scenes` |
| 任务反复失败 | 见 `tasks.error` | `run.py redo <task_id>`（版本+1，保留旧行，依赖自动重连） |
| 进程中断 | RUNNING/DISPATCHED 残留 | `python run.py recover` |

## 6. 检索 0 命中的排查顺序

1. `run.py report <pid>` → **外部素材用量**：看 `mode`、`query_shaping.mode` 与 `attempts[]`；
2. `mode=cjk_only`（查询里没有拉丁/数字词）→ Commons 命中率低属**已知限制**（见 `KNOWN_ISSUES.md` #4）；
3. `attempts[]` 有尝试但 `items=0` → 词太偏（多词 AND 过严）；可 `redo` 相关 **script/visual_plan** 让旁白含更可检索的词，
   或直接在 `config.real.provider.json` 调 `query_term_limit`；
4. 网络层：`python docs/regression_2x/phase3a_net_probe.py`（TCP/TLS/DNS 三段判读）。

## 7. 只读体检（日常首选）

```bat
python run.py report <project_id>            :: 人读
python run.py report <project_id> --json     :: 机器可读（同一数据源）
```
包含：任务状态分布 / 失败与阻断原因 / 产物清单与关键产物指纹 / 事件统计与最近失败 /
**成本（LLM，估算）** / **外部素材用量（非计费）** / 成片时长契约 / **响度实测与结论** / 抽帧核验 /
旁白状态 / 署名台账 / 质检结论。
**报告是只读的**：数据库以 `mode=ro` 打开（写操作被 SQLite 拒绝），不触发任务、不改任何状态
（由 `tests/report_command_test.py` 的 R5 组自动断言）。

## 8. 回归与验收（改代码后必跑）

```bat
python docs\regression_2x\run_all_suites.py                  :: 全部套件（期望全 rc=0）
python docs\regression_2x\phase3a_regression_batch.py        :: 批次（含 E2E/ingest/2-C/2-D/2-E/真实网络项）
python docs\regression_2x\phase3a_classify_batch.py          :: 期望"非预期结果 = 0"
python docs\regression_2x\phase3a_real_chain.py --resume p_f4b466a4a024   :: 3-A 真实链路只读复核（16/16）
python docs\regression_2x\phase3b_audit.py                   :: 响度实测审计（3-B）
python docs\regression_2x\verify_baseline.py 3.x-final-baseline           :: 基线零漂移（MATCH）
```

## 9. 环境事实（避免重复踩坑）

- 本机 `locale.getpreferredencoding()` = **cp936**：CLI 已强制 UTF-8 输出（Phase 3-C），
  但其它工具链仍建议显式 `PYTHONIOENCODING=utf-8`；
- PowerShell 5.1 不要用 `Get-Content | Set-Content` 处理中文文件；不要用内联 heredoc 写 Python
  （写成 `.py` 文件再跑）；控制台乱码属显示问题，以文件内容为准；
- Wikimedia 媒体主机**下载**限流严重（实测 144 次 429），搜索 API 不受影响；
- 内存/磁盘：`projects/` 会累积大量项目（当前 471 个），缓存字节见 `report` 的素材小节。
