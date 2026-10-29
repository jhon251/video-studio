# AI 视频生产多 Agent 系统（video-studio）

> **开源说明（2026-10-17 发布）**：本仓库为去敏后的开源快照。
> · **不含**：API 密钥（复制 `.env.example` 为 `.env` 自行填写）、ffmpeg/ffprobe 与本地模型等
>   二进制（请自行安装 ffmpeg 并置于 PATH 或 `bin/`）、成片与素材等重型产物（`output/`、`projects/`）；
> · `config/config*.json` 只含环境变量名引用，不含任何密钥值；
> · `orchestration/tests/fixtures/` 的实拍图夹具因含真实人物肖像未发布（见该目录 README），
>   除该组用例外其余测试均可运行；
> · 内部工程记录（STATUS.md / CHANGELOG.md / docs/）按原样保留，供追溯开发过程。

> **V2.0.0 Release（2026-08-15 封版）**：25 Agent + 事实核查系统 + Claim 级人工审核。
> 验收记录见 [docs/RELEASE_V2.0.md](docs/RELEASE_V2.0.md)，变更历史见 [CHANGELOG.md](CHANGELOG.md)。

> 人类主导创意，AI Agent 负责视频生产流程管理 —— 由 25 个专职 Agent 组成的"AI 视频生产团队"。
> 完整设计见 [docs/DESIGN.md](docs/DESIGN.md)（V1）与 [docs/V2_SPEC.md](docs/V2_SPEC.md)（V2）。

## 快速开始（零 API 密钥，Mock 模式）

当前 `config/config.json` 预置了 Mock LLM 与本地 ffmpeg，开箱即跑。
**注意：V2 起还有一道 Claim 审核闸门（第 6 步），省略它将导致生产环节全部不派发、永远产不出视频。**

```powershell
cd C:\mp4agent\video-studio

# 0. 二进制自检（ffmpeg / ffprobe 必须真实可用且不得互相冒充）
python scripts/check_binaries.py

# 1. 创建项目
python run.py init "做一期鲸鱼娘皮肤幕后视频" --name demo

# 2.（可选）登记本地素材：把媒体文件复制进 projects/<ID>/media/ 并重建索引
python run.py ingest <项目ID> D:\素材目录

# 3. 按标准管线创建全部任务（返回项目 ID，如 p_xxxx；共 26 个任务）
python run.py plan <项目ID>

# 4. 推进调度（需重复执行；每次只跑"就绪"的任务）
python run.py run <项目ID>

# 5. 查看状态（NEEDS_REVIEW = 任务级闸门待人工裁决）
python run.py status <项目ID>

# 6. 人工审批：任务闸门（共 4 道，必须逐个批准）
#    topic        → 选题方向
#    structure    → 内容结构
#    script       → 脚本/文案
#    editing_plan → 剪辑方案（第 4 号闸门，批准后才可能进入 render）
python run.py status <项目ID>              # 表中"待审批=是"且状态 NEEDS_REVIEW 的即是闸门
python run.py approve <任务ID> approve --comment "方向OK"

# 7. 人工审批：Claim 闸门（V2 必需！）
python run.py claims <项目ID>              # 列出 Claim 及状态/待人工
python run.py approve-claim <claim_id> --comment "结论可接受"
#    仅当项目内全部 Claim 为 VERIFIED 或 REJECTED 时才放行生产环节；
#    存在 NEEDS_HUMAN 时 visual_plan/retrieval/voice/render 等 15 类任务一律不派发。

# 8. 继续推进，直到没有新任务（成片出现在 projects/<ID>/output/*_draft.mp4）
python run.py run <项目ID>
python run.py status <项目ID>

# 9. 崩溃/断电后恢复；任务失败重做（版本 +1）
python run.py recover
python run.py redo <任务ID>
```

**按顺序**：`init → [ingest] → plan → run → status → approve → approve-claim → run → status`；
`recover` 随时可用；`redo` 用于 BLOCKED/需回退重做的任务。也可用 `loop <ID>` 自动推进，
但 `--auto-approve` 仅限演示（生产要求人工审批闸门）。

产物在 `projects/<项目ID>/`：`artifacts/`（全部中间产物，append-only）、
`media/`（ingest 的本地素材）、`output/`（成片 draft.mp4 与发布包）、`manifest.json`（断点恢复清单）。

### 素材能力的三种状态（必须区分，不得伪造）

| 状态 | 触发条件 | 表现 |
|---|---|---|
| a. 有真实素材（外部 provider） | `tools.material.provider`（或既有 `tools.image.provider`）配置为已注册 provider | 经**统一 Provider 层**搜索→下载→强校验；`material_mode=external/mixed`；未通过校验的候选单列 `external_rejected`，**绝不入片** |
| b. 使用本地 ingest 素材 | `run.py ingest <ID> <目录>` 登记过文件 | `asset_index` / `retrieval_candidates` 标记 `material_mode=local_ingest`，候选按关键词命中；**命中后按素材时间轴逐镜头入片** |
| c. 无素材（仅字幕底片） | 未 ingest 且 provider 均为 `none` | `material_mode=none`；成片为纯色底 + 烧录字幕 |

**外部素材 Provider 边界（3.x Phase 2-D）**：本阶段**只做边界层，未接入任何真实外部服务**（默认 `provider=none`）。
三个实现共用一条管线：`local_ingest`（现有行为的兼容实现，就地校验不复制）、`local_catalog`（本地目录 +
catalogue.json，用于验收/离线联调）、`http_catalog`（真实形态，仅 HTTPS）。候选统一字段：
`provider / source_id / source_url / license / attribution / usage_restrictions / bytes / sha256 /
downloaded_path / download_status / probe_result / decodable / media_type / status / error_code /
needs_hitl / license_cleared`，并转换为现有候选结构 → **必须经过 Phase 2-C 分类学**（不可绕过）。

**校验顺序（任一失败即拒收，不落盘、不进 ffmpeg）**：传输（超时/404/5xx/空响应/429，含重试）→ 危险文件名与
路径穿越（含可执行扩展名、保留设备名）→ 扩展名白名单 → 大小上限（流式中断）/空文件 → **magic bytes 实际
类型**（不看扩展名）→ **容器完整性**（JPEG `FFD9` / PNG `IEND` / WEBP RIFF 长度，防截断）→ ffprobe 有效图像流
与尺寸 → ffmpeg 解码 rc=0 → PIL **完整解码**（`load()`，非仅 `verify()`）→ 尺寸下限 → 许可证。
**许可证缺失或不明确 → 直接拒收 + `needs_hitl=true`**（不猜测、不生成许可证）；被拒候选若本可命中某镜头，
会写入该镜头 `excluded_candidates` 并置 `license_pending=true`。

**已接入的唯一真实外部 Provider（3.x Phase 2-E）：Wikimedia Commons**（MediaWiki API + `upload.wikimedia.org`
直链；免费、无需 API key）。启用示例（默认配置仍是 `provider=none`）：

```jsonc
"tools": { "material": {
    "provider": "wikimedia_commons", "search_limit": 8, "max_bytes": 8388608, "timeout_s": 25,
    "min_interval_s": 3.0, "rate_limit_retries": 3, "rate_limit_backoff_s": 10.0,
    "license_required": true,
    "auth": { "mode": "none", "api_key_env": "WIKIMEDIA_API_TOKEN", "require_key": false }
}}
```

- **凭据**：只从环境变量或项目根 `.env` 读取（`WIKIMEDIA_API_TOKEN` 可选）；**不硬编码**；`require_key=true`
  且无凭据 → `PROVIDER_NOT_CONFIGURED`（不伪造候选）；日志/产物只记 `token_present`。
- **查询整形（机械规则，非语义）——3.x Phase 3-A 修正为"按语料取词 + 分簇检索"**：
  ① 只看查询里的**拉丁/数字词**（中文旁白无空格，旧规则把整句当成一个词 → Commons 实测 **0 命中**）；
  ② 再按**源码位置**切成**词簇**——连续出现的拉丁词才属于同一簇（如 `Meta Quest 3`），
  因为**不同镜头的品牌不能 AND 到一起**（实测 `Quest PSVR2 PICO Valve` 四词 AND → **0 命中**；
  同簇短语 `Meta Quest 3` / `Quest 3` → 8 条高相关命中，见 `logs/phase3a_query_ladder.txt`）；
  ③ 多词簇优先、逐条查询，拿到足够候选即停（请求次数记入 `stats.requests`），
  每次尝试与命中数记入 `stats.query_shaping.attempts[]`；无拉丁词时退回 CJK 词块（`mode=cjk_only`）。
  **不做翻译、不做语义判断**；中文-only 查询命中率低属**已知限制**，如实记录。
- **许可证机械分类**：`CC0/PD`→`PUBLIC_DOMAIN`；`CC BY*`→`FREE_ATTRIBUTION`（可用但须署名）；
  `fair use/non-free/all rights reserved`→**`RESTRICTED`（拒收）**；空/`unknown`→`UNKNOWN`（拒收 + HITL）。
  `attribution/usage_restrictions` 原样保留并在 timeline 证据中可追溯。
- **真实网络失败面**：`PROVIDER_AUTH_FAILED`(401/403)、`PROVIDER_RATE_LIMITED`(429，含专用退避/重试预算)、
  `PROVIDER_TIMEOUT`、`PROVIDER_SEARCH_FAILED`、`PROVIDER_REQUEST_BUDGET`、`ASSET_TRUNCATED` 等；
  未通过校验者不落盘、不进 ffmpeg；完全无可用素材 → `ASSEMBLY_BLOCKED` → render 阻断。

**安全与资源**：落盘名由 sha256 生成（绝不使用远端路径）、`.part` + 原子替换、`(provider, source_id)` 索引
**先查后下**（防重复下载）、缓存上限（超限拒绝而非静默淘汰）、下载超时/大小/重试/并发上限、
**从不执行下载内容**；外部失败可降级到 local_ingest，完全无可用素材 → `ASSEMBLY_BLOCKED` → render 阻断。

**署名/许可台账 + 许可合规（3.x Phase 3-A）**：渲染时新增**只读交付物** `attribution`（渲染任务第二个 artifact，
`render_output` 仍是 `artifacts[0]`），由 `render_output.material_timeline` **逐条派生**（不重新推断）：
`provider / source_id / source_url / license / license_class / usage_restrictions / attribution /
selected_asset{asset_id,name,sha256,path,bytes,width,height} / 镜头与时间窗 / appears_in_film / film_evidence`；
同时输出人可读 `output/credits_<task_id>.txt` 随片交付。

- **许可门禁的适用范围 = 外部 provider 素材**（`core.materials.license_gate_applies`）：`RESTRICTED`/`UNKNOWN`
  一律不得入片（provider 层拒收 + `classify_scene` 分类阶段再查一次，纵深防御）。
  **3-A 新增的两道门禁（分类阶段 / 渲染池）只作用于外部候选**：默认路径（`provider=none`）下本地自带素材
  （local_ingest，`license` 通常为 `unchecked`）**不在门禁范围**——管线拿不到提供方声明，只原样记录声明值，
  **不做法律判断**（台账中 `scope=local_user_material`）。
  注意：若显式配置 `image.provider=local_ingest`，provider 层**既有**门禁（Phase 2-D/2-E 行为，本次未改）
  仍按其 `license_required` 策略判定；空/未声明许可证在 2-E 与 3-A 下**同样**被拒（3-A 只是新增了
  `fair use/non-free/…` 的 `ASSET_LICENSE_RESTRICTED` 类别判定）。
- **自动断言**：`restricted_or_unknown_in_film == []`（scope=`external_provider_assets`）、台账 ⟷ 时间轴 1:1、
  外部素材 `appears_in_film=true` 且抽帧相关度 ≥ 阈值（证据字段 `corr_expected/corr_best`）。

**音频响度契约（3.x Phase 3-B）**：成片音频统一到 **-16 LUFS（±1 LU）/ 真峰 ≤ -1.5 dBTP**，
契约与实现单一事实源在 `core/audio.py`；正式渲染链与 `stage32b` 路径**共用同一条母带链**
（`loudnorm=I=-16:TP=-1.5:LRA=11` → `alimiter=limit=0.7079`）。

- **处理**：`agents/editing` 的每个脚本渲染分支都套母带链，并**显式 `aresample=<输入采样率>`**——
  `loudnorm` 内部按 192 kHz 处理并输出 192 kHz，不还原会把 24 kHz 旁白变成 192 kHz（实测踩过）。
- **实测 QC**：渲染后用真实 `ffmpeg -af ebur128=peak=true` 测成片，结果写入
  `render_output.audio_loudness{ok, measured_lufs, measured_true_peak_dbtp, delta_lu, contract, method,
  audio_chain, corrections, passes[]}`。
- **fail-closed**：偏差 ≤3 LU 允许 1–2 次**只重编音频**（`-c:v copy`）的收尾校正；
  **偏差 >3 LU 拒绝校正、直接 BLOCKED**（大幅偏差意味着母带链没生效，静默修好会掩盖故障）；
  测不到（无音轨/无 ffmpeg）同样判不合格。不达标时不写 `render_output`。
- **配置**（可选，默认即上述契约值）：`tools.ffmpeg.loudness.{target_lufs, max_true_peak_dbtp,
  tolerance_lu, target_lra, apply_mastering}`；`apply_mastering=false` 只跳过处理、**不放松 QC**
  （因此会让渲染 fail-closed，仅用于故障注入验证）。
- **stage32b 同契约**：`vo.py`/`render.py` 复用同一母带链（保留其历史 +0.4 dB 限幅补偿），
  `qc.py` 的响度断言由旧的 ±2 LU 收紧为统一 ±1 LU。

**素材时间轴（3.x Phase 2-A/2-B）**：检索命中本地素材时，`editing` 会把脚本逐段切成镜头，为**每个镜头**
确定性地分配素材（词法混合打分：CJK 二元组×2 + 单字×1 + 拉丁词≥3×2；优先使用未被占用的素材），
并把结果写入 `render_output.material_timeline`（镜头窗口 + 检索查询 + 命中 token + 素材
`asset_id/name/source/sha256/path/bytes/score` + 选择理由 + `fallback_state`）+ `MATERIAL_TIMELINE` 事件；
`render` 按该时间轴逐镜头装配（每镜头 `-loop 1 -t 窗口长 -i 素材` → 统一 scale/crop → concat → 字幕/淡入淡出 → 混旁白）。
此时 `visual_source=material_timeline`、`material_assembly=SUCCEEDED`、`assets_used/scene_count/scenes_with_asset/fallback_scenes` 均落盘。

**重要边界**：素材**不足**时（某镜头关键词交集为空）该镜头记 `fallback_state=SOLID_COLOR_CARD` 且
`selected_asset=None`——**不伪造**素材；整片无任何素材命中时退回纯色底 + 烧录字幕路径。

**运维入口（3.x Final / Phase 3-C + 4.x Phase 4-A/4-B）**：

- **只读体检报告**：`python run.py report <project_id> [--json]` —— 一屏看清任务状态、失败/阻断原因、产物与指纹、
  事件统计、**成本（LLM，估算）**、**外部素材用量（非计费）**、成片时长契约、**响度实测结论**、抽帧核验、
  旁白状态、署名台账与质检结论。**只读**：数据库以 `mode=ro` 打开（写操作被 SQLite 拒绝），不触发任何任务。
- **只读质量/成本指标（4-A）**：`python run.py metrics <project_id> [--json]` 或 `python run.py metrics --all [--limit N]`
  —— 候选/上屏率、corr、时长与响度契约、旁白完整性、外部素材用量、LLM 成本（估算）、人工介入，以及**语义核验三态计数**。
  输出**确定性**（无时间戳、排序固定）：同一数据两次运行**逐字节一致**。
- **离线三态语义核验（4-B）**：`python run.py semantic-check <project_id> [--json]`
  —— 逐镜头给出 `MATCH` / `MISMATCH` / `UNKNOWN` + **规则 ID + 命中关键词/标记 + 共享词分类**（词级桥 vs 字面碎片）。
  **离线、只读、可复算**：不访问网络、不调用 LLM、**无任何数值阈值**（判据为类别式规则）；
  无法判断一律 `UNKNOWN`，绝不当作 `MATCH`。知识库 `core/lexicons/semantics_v1.json`（带版本与 sha256）。
- **人审候选替换（4-C）**：
  `python run.py review <project_id> [--all] [--json]` —— **只读复核队列**：列出语义非 `MATCH` 的镜头 +
  该镜头**可选候选池**（含可用性/许可类别/已被哪些镜头使用）+ 已拒候选（附错误码）+ 当前素材；
  候选池为空或全部不可用时明确标出 `blocked_scenes`（**必须 BLOCKED，不得随便选一个**）。
  `python run.py select-candidate <pid> --scene S04 --asset asset_xxx --by <人> --reason "..." [--dry-run]`
  —— 记录**人工明确选定**（写既有 `decisions`（`node=selection_override`）+ 既有 `changelog`（`human_confirmed=1`）；
  不存在的素材 / 不可用素材 / 无 `--by` / 无 `--reason` 一律**拒绝写入**）。
  替换生效：`python run.py redo <render_task>` → `python run.py run <pid> --limit 4`
  （复用既有 append-only / version+1；渲染侧只读消费人工选定，并在时间轴写 `selection_source="human_review"`
  与 `human_selection{decision_id,decided_by,reason,decided_at}`；**校验不过即 fail-closed**，绝不静默回退到自动选材）。
- **运行手册**：`docs/RUNBOOK.md`（正式入口 / `resume`↔`redo`↔验证的区别 / 429 与超时处理 / 真实 LLM·TTS·Provider
  的前置条件 / 常见失败与恢复）。
- **成本边界**：`docs/COST_BOUNDARY.md`（LLM 估算 vs 外部素材用量 vs 账户余额三条口径；
  ¥3.24 残余的正式结论 `NOT_ATTRIBUTABLE_CLIENT_SIDE`）。
- **已知问题台账**：`docs/KNOWN_ISSUES.md`（语义误选 S04/S06、2-E 历史成片不可完全复原、`stage32b` +0.4 dB 补偿等）。

**人工审稿（2026-10-20 新增，"梗/人味"的唯一入口）**：

```powershell
python run.py script-review <项目ID>                     # 只读：导出 <项目>/media/script_review.md
#   每段一行（@@Sxx 开头）+ 字数/预估时长/预算(±30%)/节拍 + 审稿 5 问
#   弹药库：config/humor_pack.md（句式模板/世俗类比/数字人话/口语连接/红线）
python run.py script-apply <项目ID> --file <该md> ^
       --checklist 11111 --notes "S02 加了一句人话"      # 校验后写 <项目>/media/script_review.json
python run.py redo <script任务> && python run.py run <项目ID> --limit 4
```

- **人工稿优先于 LLM**：`ScriptAgent.run` 检测到 `media/script_review.json` 后**不再调模型**，
  直接以人工稿落产物（`source=human_review`，事件 `SCRIPT_HUMAN_REVIEW`）；因此 `redo` 稳定复现人改过的稿。
- **校验（不通过即不落盘）**：段数不可增删、空段、节拍名/字段名泄漏（`curiosity`…）、
  AI 味词（`综上所述/值得注意的是/…`）、单段字数漂移 >30%（告警）、全片漂移 >5%（默认拒绝，需 `--allow-drift`）。
  改字数会改 TTS 时长 → 时间轴/素材窗口/字幕全变，这是"必须重排"的显式确认。
- **审稿 5 问**：具体的人 / 可截图的句子 / 反常识 / 世俗类比 / 结尾回扣。答"否"写进 `--notes`。

**质量阈值已改按外部标杆标定（2026-10-20）**：`core/rhythm.py` 与 `core/direction.py` 的出厂阈值
从"内部历史自洽"改为"外部标杆"——`max_scene_s` 20→**10s**、`static_warn_s` 15→**4s**、
`min_cuts_per_min` 2→**15 次/分**（王骁 ≈20–40、燕三 ≈60+）、`max_hold_s` 25→**10s**、
`max_over_hold_share` 0.20→**0.05**。旧口径会让"18.4s/镜、3.4 次/分"的成片全部 PASS。

**素材不足降级分类学（3.x Phase 2-C）**：每个镜头都会得到一个**可审计的决策记录**：
- 诊断 `insufficiency_class`：`NO_CANDIDATE`（无候选）/ `LOW_MATCH`（最高分 < `editing.min_match_score`，默认 3）/
  `ASSET_UNUSABLE`（解码失败/尺寸不合格，带 `ASSET_DECODE_FAILED` 等错误码）/ `ASSET_CONFLICT`（命中镜头负向约束）/
  `ASSET_EXHAUSTED`（素材被占用且 `asset_reuse_policy=forbid`）/ `NONE`（正常命中）。
- 动作 `fallback_state`：`LOCAL_INGEST`（正常命中）/ `THEME_FALLBACK`（同主题降级，**明确标注 + needs_hitl**）/
  `SOLID_COLOR_CARD`（安全占位，`selected_asset=null`）/ `BLOCKED_FOR_HUMAN`（阻断等人工补素材）。
- 装配级 `assembly_class=ASSEMBLY_BLOCKED`：**已提供本地素材却没有任何镜头能把真实素材放上屏** → render 在调用
  ffmpeg 之前抛 `[ASSET_INSUFFICIENT]` 并 BLOCKED（不产出"看起来成功"的成片）。
- **禁止静默降级**：降级必写分类与原因（含实际分数/阈值）；占位场景 `selected_asset` 必为 `null`，且成片抽帧核验
  会确认该窗口**不是**任何素材；不可用素材绝不进入 ffmpeg；渲染后会**逐镜头抽帧核验**，把 `appears_in_film`
  与 `film_evidence`（采样点/argmax/相关系数）写回时间轴——"分配了素材却在该窗口看不到它" 判渲染失败。

相关字段：`render_output.{material_policy, insufficiency_summary, insufficiency_classes, fallback_states,
scenes_needing_hitl, assets_rejected, scene_evidence, material_verification, traceability_version}` 与
`material_timeline[].{original_requirement, candidates[], selected_asset, insufficiency_class, fallback_state,
fallback_reason, selection_reason, needs_hitl, allowed_in_final_render, entered_timeline, appears_in_film}`。

**旁白与时长契约（3.x Phase 2-B.1）**：脚本时基 = `Σ max(segment.duration_s, 3.0) + 2` 是**成片时长的权威来源**
（等于素材时间轴末镜头 `end_s`）。`voice` 阶段逐段合成并复用：只有**全部段落**都有合法音频时才
`complete=true`/`confidence=1.0` 并重建 `narration.mp3`；任一段失败 → 任务 FAILED→重试→BLOCKED
（错误码 `TTS_NETWORK` 可重试、`TTS_SYNTHESIS_FAILED` 等不可重试），**不会**用残缺音轨覆盖已有完整音轨。
`render` 在**调用 ffmpeg 之前**校验旁白完整性，产出后再校验 `|成片时长 - 时间轴| ≤ 1.0s`：
旁白较短用静音补齐（视频**不缩短**），偏长在容差（默认 10%）内按时间轴裁尾、超容差直接阻断——
**不会再出现"任务成功但成片被截短"**。相关字段：`voice_output.complete/segment_details/duration_contract`、
`render_output.narration_state/narration_completeness/duration_contract/video_duration_ok`。

## 接入真实 DeepSeek API

1. 复制 `config/config.example.json` 为 `config/config.json`
2. 删除其中的 `"mock"` 段
3. 设置环境变量：`$env:DEEPSEEK_API_KEY = "sk-..."`（或写入 config）
4. 其余云端服务按需配置：`tools.search / image / video / tts / asr` 的 provider 与密钥

> Mock 模式下 LLM 返回预置文案，**内容与输入选材无关**（不同选材会产出字节相同的成片）。
> 工程闭环可用，但"内容保真"必须用真实 API 才成立。

## 25 个 Agent

| 档位 | Agent |
|---|---|
| R（reasoner） | source_verify, fact_check, critic, compliance |
| M（chat） | orchestrator, pm, topic, research, structure, script, visual, editing, thumbnail, platform, metadata, qa*, analyst |
| 免 LLM | asset, retrieval, voice, audio, subtitle（+qa 技术项） |

*：qa 技术项为确定性检查，内容核对 V2 引入 M。

## 测试

```powershell
python tests/smoke_mock.py      # 核心闭环冒烟（12 项）
python tests/pipeline_mock.py   # 25 Agent 全管线集成（12 项，真实 ffmpeg 成片）
python docs/regression_2x/run_all_suites.py   # 全部套件（25 个）
python docs/regression_2x/run_all_tests.py --fresh   # 三组选材端到端出片
python docs/regression_2x/run_ingest_test.py         # 本地 ingest 全链
python scripts/check_binaries.py <某个.mp4>          # 二进制真实性 + 真实探测
```

## 目录

```
config/  配置与权限规则        src/video_studio/  agents|core|tools|memory|hitl|llm|pipeline|db
docs/    DESIGN.md 总体设计    docs/regression_2x/  2.x 基线（ZIP+manifest+报告）
tests/   冒烟+集成测试         projects/  运行时数据
```

## 断线恢复

一切落盘：任务/事件/产物/决策/审批在 SQLite(WAL)，进度清单见 `STATUS.md`。
中断后：`python run.py recover` 把未完成任务回队，`status` 查看，`run` 继续。

