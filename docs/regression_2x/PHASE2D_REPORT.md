# 3.x Phase 2-D 报告：外部素材 Provider 接入前的边界设计与实现

- 日期：2026-09-13
- 授权范围（逐字）：**"授权进入下一阶段：Phase 2-D：外部素材 Provider 接入前的边界设计与实现"**；"本阶段只做…"六项；"本阶段暂不做：BGM / 自动发布 / UI 大改 / 语义级镜头↔旁白对齐 / 自动许可证判定 / 多 Provider 智能竞价或复杂排序 / 大规模缓存系统 / 新增无关 Agent"；"完成后立即停止，等待下一阶段授权"。
- 定位：**接入前的边界层**。本阶段**未接入任何真实外部服务**（默认 `provider=none`，现有 local_ingest 行为不变），
  但把下载/校验/许可证/安全/资源限制全部落地并**用真实故障验证**。
- 未触碰：Claim/HITL 核心机制、append-only、exec isolation、断点恢复、既有 task/artifact/event 契约
  （**未新增事件类型、未新增 artifact 类型**；仅新增字段）、narration completeness gate、timeline 权威时长、
  Phase 2-C fallback 分类学、现有 local_ingest 行为。

---

## 0. 结论先行（判定行）

| # | 判定项 | 结论 |
|---|---|---|
| A | local_ingest 回归（正常路径不变 / 31 套件 / 3 机械 E2E / 真实小测 MockLLM=0） | **PASS** |
| B | Provider contract（fake/local provider 正常候选 + 标准化字段完整 + 可追溯） | **PASS**（46/46 单测 + 12/12 端到端） |
| C | 故障注入 10 类（错误码 / 不进 ffmpeg / 不当作命中 / 按定义 fallback·HITL·BLOCKED） | **PASS**（40/40 断言） |
| D | 真实成片证据（provider 素材进 timeline 并抽帧证实上屏） | **PASS**（corr 0.696 @ t=2.0s） |
| E | 报告 + 故障注入报告 + 可追溯证据 + 新 baseline | **PASS**（见 §6/§7） |
| — | 既有契约（2-A/B 验收、2-C 追溯）在本次改动后仍成立 | **PASS**（2-A/B PASS；2-C 38/38） |

---

## 1. Provider 抽象接口（需求 1）

新增 `src/video_studio/tools/material_provider.py`：

```python
MaterialProvider.search(query: MaterialQuery, ctx) -> list[ProviderCandidate]
MaterialProvider.fetch(candidates, ctx) -> list[ProviderCandidate]      # 下载 + 校验（含并发上限）
MaterialProvider.capabilities() -> dict                                # 自述 provider 与限制
```

三个实现（同一接口、同一校验管线）：

| 实现 | 说明 |
|---|---|
| `LocalIngestProvider`（`local_ingest`） | **现有 local_ingest 的兼容实现**：读项目 `media/` 索引、就地校验、不下载不复制（`download_status=ALREADY_LOCAL`）。单测验证其打分与旧链路一致（A4：16 vs 16） |
| `LocalCatalogProvider`（`local_catalog`） | 本地目录 + `catalogue.json`（验收用 fake/local provider），走**同一条**下载+校验管线 |
| `HttpCatalogProvider`（`http_catalog`） | 真实外部形态：catalogue 走 HTTPS 端点、逐条下载；默认 `require_https=true`、禁跳转、限时限量；transport 可注入 |

配置（纯新增）：`tools.material.{provider,catalog,max_bytes,timeout_s,max_retries,
max_concurrent_downloads,max_cache_bytes,allowed_ext,min_width,min_height,license_required,require_https}`；
provider 选择顺序 `tools.material.provider` → 既有开关 `tools.image.provider` → `none`。

## 2. Provider 结果标准化（需求 2）

`ProviderCandidate` 字段：`provider / source_id / source_url / name / ext / license / attribution /
usage_restrictions / bytes / sha256 / downloaded_path / download_status / probe_result / decodable /
media_type / width / height / status / error_code / error_detail / needs_hitl / license_cleared / match_score /
matched_tokens`，其中 `to_candidate()` 输出**现有素材候选结构**（`path/name/ext/size/sha256/license/
match_score/matched_tokens`）+ 追溯字段，因此外部素材**必然经过** Phase 2-C 分类学
（`NO_CANDIDATE / LOW_MATCH / ASSET_UNUSABLE / ASSET_CONFLICT / ASSET_EXHAUSTED`），无法绕过。

`retrieval_candidates` 新增（纯新增字段）：`external_provider`（capabilities/stats/计数）、
`external_verified`、`external_rejected[]`、`external_error`、`material_provided`；
`material_mode` 扩展为 `local_ingest | external | mixed | none | external_configured_no_candidate`
（原三种取值语义不变）。

## 3. 下载与验证边界（需求 3）

下载 → 逐项校验，任一失败即 `REJECTED` 且带明确错误码（12 类），**文件不落盘、绝不进入 ffmpeg**：

| 阶段 | 错误码 |
|---|---|
| 传输 | `PROVIDER_TIMEOUT` / `PROVIDER_HTTP_404` / `PROVIDER_HTTP_5XX` / `PROVIDER_HTTP_ERROR` / `PROVIDER_EMPTY_RESPONSE` / `PROVIDER_DOWNLOAD_FAILED` |
| 文件名 | `ASSET_DANGEROUS_FILENAME`（路径分隔符/`..`/绝对路径/控制字符/保留设备名/可执行扩展名/超长/非法字符） |
| 扩展名 | `ASSET_EXTENSION_NOT_ALLOWED`（白名单 .jpg/.jpeg/.png/.webp） |
| 体量 | `ASSET_OVERSIZE`（流式累计即中断）、`ASSET_EMPTY_FILE` |
| 实际类型 | `ASSET_TYPE_MISMATCH`（magic bytes 判定，**不看扩展名**） |
| 探测/解码 | `ASSET_PROBE_FAILED`（ffprobe 无有效图像流或尺寸无效）、`ASSET_FFMPEG_DECODE_FAILED`（ffmpeg rc≠0）、`ASSET_DECODE_FAILED`（PIL 装载失败） |
| 尺寸 | `ASSET_TOO_SMALL`（< 320×180，可配） |
| 许可证 | `ASSET_LICENSE_MISSING` / `ASSET_LICENSE_UNCLEAR` |
| 缓存 | `PROVIDER_CACHE_LIMIT` |

## 4. 许可证与归属（需求 4）

- `license` 为空/`unknown`/`unchecked`/`n/a`/`none` → `license_cleared=false`、`needs_hitl=true`，
  且**在 provider 层直接 REJECTED**（即便文件本身完全合法）→ 不进入候选 → 不进入正常素材路径。
- **不猜测、不生成**许可证：`license`/`attribution`/`usage_restrictions` 原样透传与记录。
- 场景级：被拒候选若本可命中该镜头，会写入 `material_timeline[].excluded_candidates`，
  并置 `license_pending=true`、`needs_hitl=true`（Phase 2-C 的 `needs_hitl` 只是记录/建议字段，
  **不改动** HITL 闸门与任务审批顺序）。

## 5. 安全与资源限制（需求 5）

- 超时（默认 20s）、大小上限（默认 8 MiB，流式中断）、重试（默认 2 次，仅超时/5xx/连接类）、
  并发上限（默认 2，`ThreadPoolExecutor`）。
- 落盘路径**由我们按 sha256 生成**（`media/external/<sha256>.<ext>`），绝不使用远端路径；
  文件名先过危险名检查；`.part` + `os.replace` 原子落盘。
- 重复下载：`(provider, source_id)` → sha256 索引 `.index.json`，命中即**不再触发传输层**
  （单测 D2：传输层 0 次调用；D2b：`cache_hits=1`）。
- 缓存上限（默认 256 MiB）：超限即 `PROVIDER_CACHE_LIMIT` 拒绝新下载，**不做静默淘汰**。
- 不执行下载内容：仅以只读方式经 PIL/ffprobe/ffmpeg 解析（单测 D6 断言无 `shell=True`）。
- 失败可降级：外部失败但本地有素材 → 降级继续（实测许可证用例）；完全无可用素材 →
  Phase 2-C 的 `ASSEMBLY_BLOCKED` → render 阻断（实测 9 个故障用例无成片）。

## 6. 验收证据

### A. local_ingest 回归
| 项 | 结果 |
|---|---|
| 全部套件 | **31 total / 31 rc=0 / FAILED: []**（30 旧 + 新增 `material_provider_test` 46/46） |
| 3 机械 E2E | A/B/C **全 SETTLED**（17.000s、24000Hz 真实旁白） |
| 真实 LLM 小测 | **PASS**，**MockLLM=0**，模型 `deepseek-flash` |
| 本地 ingest 链路 | **PASS**（抽帧 t=8.5s 命中 0.747） |
| ffprobe 真实性 / ffmpeg decode | **PASS** / 各成片 **rc=0** |
| Phase 2-A/B 验收 | **PASS**（成片 438.0s、12/12 在屏、3 个不同素材） |
| Phase 2-C 追溯 | **38/38** |

### B. Provider contract（`tests/material_provider_test.py` 46/46 + 端到端 12/12）
候选字段完整性（B2）、内容寻址落盘（B3/B1b）、provider/source/license/sha256/bytes 可追溯（B4）、
`license_cleared` 与 HITL 联动（B5）、转换为现有候选结构（B6）、capabilities（B7）。

### C. 故障注入 10 类 → `docs/regression_2x/PHASE2D_FAULT_REPORT.md`（40/40 断言）

### D. 真实成片证据（`phase2d_provider_e2e.py` 12/12）
`p_0787d451fb83`：S01 = 外部素材 `provider=local_catalog / source_id=ext-ccby-001 /
source_url=<catalogue file> / license=CC BY 4.0 / attribution=Example Studio / sha256=3bd63424…`，
**抽帧证实出现在成片**（t=2.0s，corr **0.696**，`appears_in_film=true`）；S02 = 许可证未明候选被拒 →
占位 + `needs_hitl/ license_pending` + 抽帧证实占位"不是任何素材"；成片 10.0s、2 流、decode rc=0。
记录：`logs/phase2d_provider_e2e.json`。

---

## 7. 代码改动（可追溯）

| 文件 | 改动 |
|---|---|
| `src/video_studio/tools/material_provider.py`（新） | Provider 抽象 + 三种实现 + 下载/校验/许可证/安全/资源边界 + 错误码表 + 内容寻址缓存与索引 |
| `src/video_studio/agents/retrieval/agent.py` | 接入 provider 层（搜索→下载→校验）；输出 `external_provider/external_verified/external_rejected/external_error/material_provided`；`material_mode` 扩展（含 `tools.material.provider` 判定）；provider 未配置时**零行为变化** |
| `src/video_studio/agents/editing/agent.py` | 素材池携带 provider 来源与许可字段；把被拒候选传入时间轴构建（`excluded_candidates`/`license_pending`）；`material_provided` 语义扩展到外部提供过候选 |
| `src/video_studio/core/materials.py` | 决策记录新增 `excluded_candidates`/`license_pending`（并据此置 `needs_hitl`）；候选/选中素材记录追加 provider 来源字段；阻断文案改为不误导（"本地素材索引或外部 provider 返回过候选"） |
| `tests/material_provider_test.py`（新） | 46 项确定性单测（契约 + 10 类故障 + 安全资源限制 + 工厂/降级） |
| `docs/regression_2x/phase2d_provider_e2e.py`（新） | 端到端：provider 素材进 timeline 且抽帧上屏 + 许可证边界 |
| `docs/regression_2x/phase2d_boundary_matrix.py`（新） | 10 类故障的真实项目矩阵（错误码/不落盘/不命中/BLOCKED 或降级） |

**过程中修正的两处自身缺陷**（如实记录）：
1. URL 分支原先"先下载后算 sha"，导致每次都重新下载（去重名存实亡）→ 改为 `(provider, source_id)`
   索引**先查后下**，并把缓存上限校验补到本地目录分支。
2. `material_mode` 未把 `tools.material.provider` 计入"已配置"，且 `assembly_class()` 仍用旧的
   `material_mode == "local_ingest"` 判定 → 外部候选全被拒时**错误地出了纯色底成片**（应为 BLOCKED）；
   已统一为 `material_provided`（本地索引非空 **或** 外部返回过候选）。

---

## 8. 基线与文档

- 新基线：`docs/regression_2x/baseline/3.x-phase2d-baseline.zip`（**332 文件 / 7,253,154 源码字节**，
  sha256 `27b28f7df4f18749af550477886a5eedd1698e5cb40e6acbd36051043dca2b02`），
  `verify_baseline.py 3.x-phase2d-baseline` → **MATCH（零漂移：zip 哈希一致、清单==条目、0 缺失、0 漂移）**。
  关键指纹：`tools/material_provider.py 78c753f9ec32bb53…`（新）、`agents/retrieval/agent.py d63302b00a2c7a6d…`、
  `agents/editing/agent.py 5486c7ca98d191ec…`、`core/materials.py 52fd30073ee1f38f…`、
  `tests/material_provider_test.py 634bc913b055eba9…`（新）、`config/config.json b264644539b2adbb…`（未改）。
- 更新：`CHANGELOG.md`（V2.2.3-Phase2D）、`STATUS.md`、`README.md`（Provider 边界与许可证规则）、
  `BASELINE_README.md`（基准行、§2e、命令列表、已知问题）。
- 证据：`logs/phase2d_provider_e2e.json`、`logs/phase2d_boundary_matrix.json`、
  `logs/suite_material_provider_test.log`。

---

## 9. 停止点

按授权：本阶段到此为止。**未接入任何真实外部服务**；未做 BGM、自动发布、UI 大改、语义级对齐、
自动许可证判定、多 Provider 竞价、大规模缓存、新 Agent。等下一阶段授权。
