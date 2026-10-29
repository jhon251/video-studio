# 4.x Phase 4-D 报告：供给韧性底座（2026-09-16）

**授权**：进入 4-D 供给韧性；以 `4.x-phase4c-fix-baseline.zip` 为**唯一基线**；不使用 Git；保持
4-A/4-B/4-C 逻辑、冻结契约、Claim/HITL、redo、append-only、许可门禁不变；**先做最小增量**
（供给缓存、限流/超时分类、失败可解释、可控降级）；如接入第二 Provider 必须独立抽象/默认关闭/三重验证；
禁止因供给失败静默使用未验证素材；禁止自动语义改选材；不做 BGM/UI/节奏自动改时长/自动发布；
不修改数据库结构（若不可避免先 STOP 报告）；覆盖八条路径；证明失败 fail-closed 且不污染既有产物/台账/版本链；
先实现并验证供给韧性底座，**不顺便进入 4-E**。

**前置校验（唯一基线）**：`docs/regression_2x/baseline/4.x-phase4c-fix-baseline.zip`
sha256 `3b0e998e1c2e0de180b711b71242423ead90ecfca3f5e73e1bfe18078b6ad96e`（实测一致，5,891,489 字节）。

**结论：PASS**（八条路径全部 fail-closed；默认行为与 `provider=none` 不变；未改数据库结构；未接第二 Provider）。

---

## 1. 变更文件与影响面

| # | 文件 | 类型 | 影响面 |
|---|---|---|---|
| 1 | `src/video_studio/core/supply.py` | **新增**（纯函数/离线/只读） | 失败分类表（32 码）、重试计划、供给缓存实现、降级阶梯、诊断汇总。**不读写 DB、不访问网络** |
| 2 | `src/video_studio/tools/supply.py` | **新增** | `ResilientSupply` façade（搜索缓存/失败归类/报告）+ `verified_only()`（唯一入池出口）+ `degradation_facts()`（由**既有** 2-C 策略键推导） |
| 3 | `tests/supply_resilience_test.py` | **新增** | 4-D 单测 55 项（A–G 七组） |
| 4 | `src/video_studio/tools/material_provider.py` | 修改（加法） | `TransportError.retry_after_s`；`UrllibTransport` 429 解析 `Retry-After`；下载重试判定改由 `core.supply.retry_decision` 统一；`DEFAULT_POLICY` 增加 3 个开关 |
| 5 | `src/video_studio/agents/retrieval/agent.py` | 修改（加法） | `_external_candidates` 外层包 `ResilientSupply`；检索产物新增 `supply` / `supply_report`；**入池判定未改** |
| — | `CHANGELOG.md` / `STATUS.md` | 修改（**仅文档登记**） | 版本条目与断点状态 |

**未改动**：`config/config.json`（sha256 `b264644539b2adbb…` 与基线 manifest **一致**）、`db/schema.py`（**无表/列变更**）、
`core/materials.py`（2-C 分类学与许可门禁）、`core/semantics.py` + lexicon（4-B）、`core/selection_review.py` +
`ops/selection_review.py`（4-C）、`core/audio.py`（3-B）、`ops/metrics.py` / `ops/report.py`（4-A/3-C）、
任何 2-D/2-E 冻结接口签名。**变更清单**：`logs/phase4d_change_list.json`
（代码 **修改 2 / 新增 3 / 删除 0**；`baseline_delta.py` 实测相对上一基线：修改 4 / 新增 3 / 删除 0，其中 2 项为文档）。

**影响面判定**：默认配置（`provider=none`）下**零行为变化**（检索层 façade 仅在外层做 no-op 分支判定）；
外部 provider 路径下新增"缓存查找（默认关闭）+ 失败归类 + 报告字段"，判定权仍 100% 属于
`verify_material`（下载后强校验）与许可门禁。

## 2. Provider / 缓存 / 限流 / 超时行为

**失败分类（`classify_failure`，单一来源）**：32 个既有错误码 → `TRANSIENT` 7 / `PERMANENT` 16 / `POLICY` 6 / `LICENSE` 3；
未登记码 → `UNKNOWN`（不重试、不放行、如实记录）。表见 `logs/phase4d_taxonomy.json`。

| 类别 | 代表码 | 处置 |
|---|---|---|
| TRANSIENT | `PROVIDER_TIMEOUT`、`PROVIDER_RATE_LIMITED`、`PROVIDER_HTTP_5XX`、`PROVIDER_DOWNLOAD_FAILED`、`PROVIDER_EMPTY_RESPONSE`、`PROVIDER_SEARCH_FAILED`、`ASSET_TRUNCATED` | 有界重试；耗尽即放弃该候选（**不降级为未验证素材**） |
| PERMANENT | `PROVIDER_HTTP_404`、`PROVIDER_AUTH_FAILED`、`ASSET_TYPE_MISMATCH`、`ASSET_PROBE_FAILED`、`ASSET_OVERSIZE` … | 不重试，记录并跳过 |
| POLICY | `PROVIDER_REQUEST_BUDGET`、`PROVIDER_CACHE_LIMIT`、`PROVIDER_NOT_CONFIGURED`、`PROVIDER_UNKNOWN`、`ASSET_CONFLICT`、`ASSET_EXHAUSTED` | 不重试；需人工或下次运行处理 |
| LICENSE | `ASSET_LICENSE_MISSING` / `_UNCLEAR` / `_RESTRICTED` | **绝不重试、绝不放行**，转人工（`needs_hitl`） |

**限流/超时（`retry_decision`，有界、确定性、无抖动）**：
- 429：线性退避 `10s / 20s / 30s`（基数 `rate_limit_backoff_s`，上限 `max_backoff_s`），预算 `rate_limit_retries`；
- 超时/5xx/下载失败：`0.2s / 0.4s`（上限 2.0s），预算 `max_retries`（总尝试 = 1 + max_retries）；
- **`Retry-After` 仅在 30s 上限内被采纳**（实测 45s→30s；5s 不覆盖本地 10s）；
- 404/鉴权/许可/策略类：**一律不重试**。
- **与 2-D/2-E 逐值一致**：`tests/supply_resilience_test.py` B1/B2/B4 断言退避与预算数值；D4b 断言 429 的
  `attempts=3 / retries=3 / rate_limited=3`（沿用既有计数语义：预算取自 `rate_limit_retries`，实际尝试受
  `1+max_retries` 循环约束，故计数含最后一次未执行的计划重试——**既有行为，本次未改，如实登记**）。

**供给缓存（`SupplyCache`，搜索层，默认关闭）**：
- 键 = `sha256(provider, 查询文本, limit, kinds, 关键词集合, 策略指纹)`；策略指纹覆盖
  `max_bytes/allowed_ext/min_width/min_height/license_required/require_https/search_limit/provider`（换策略即换键）；
- 目录 `<project_dir>/.supply_cache/search/`（**不放在 `media/external`**，避免污染下载缓存字节上限口径）；
  原子写（tmp + `os.replace`）；TTL 默认 900s；过期/损坏/schema 不符 → **视为未命中**（`EXPIRED`/`CORRUPT`/`SCHEMA_MISMATCH`），
  绝不因缓存异常影响正确性；
- **只缓存候选元数据**（provider/source_id/name/source_url/ext/license/attribution/usage_restrictions/bytes/sha256/
  match_score/matched_tokens）；**不缓存** `downloaded_path`、`status`、`verified`、`license_cleared`；
  命中恢复出的候选一律 `status=CANDIDATE`、`download_status=NOT_DOWNLOADED`、`license_cleared=False`；
- 命中后**仍要重新下载（内容寻址缓存可省流量）+ `verify_material` 全量校验 + 许可门禁**才可能入池
  → **缓存无法让未验证素材进入成片**（D3 用例：命中后源文件消失 → `PROVIDER_DOWNLOAD_FAILED`，入池 0）；
- 实测：D2 搜索只调用 1 次、第二次 `from_cache=True`、两次都重新校验后入池 1 个候选；
  引擎级 F2 两次 retrieval 的 `cache_key` 相同、第二次 `from_cache=True`（命中 1 次）。
- **下载缓存**（2-D 既有内容寻址 `media/external/<sha256>`）与并发上限（`max_concurrent_downloads=2`）**未改**。

## 3. 失败路径与 fail-closed 证据

**八条路径（离线注入，`logs/phase4d_paths.json`）—— fail-closed 8/8**：

| # | 路径 | 实测结果 | fail-closed |
|---|---|---|---|
| 1 | 正常 | 1 个候选 VERIFIED 入池；降级阶梯 `EXTERNAL_VERIFIED`；无失败记录 | ✅（正常放行） |
| 2 | 缓存命中 | `from_cache=True`、命中 1 次、重新校验后仍 1 个入池 | ✅ |
| 3 | 429 限流 | 3 次尝试后 `PROVIDER_RATE_LIMITED`、入池 0、归类 TRANSIENT | ✅ |
| 4 | 超时 | 2 次尝试后 `PROVIDER_TIMEOUT`、入池 0 | ✅ |
| 5 | 空候选 | 0 候选、无伪造、阶梯给出兜底档且 `requires_human=True` | ✅ |
| 6 | 下载失败 | `PROVIDER_DOWNLOAD_FAILED`、`download_status=FAILED`、入池 0 | ✅ |
| 7 | 校验失败 | `ASSET_TRUNCATED` + `ASSET_TYPE_MISMATCH`、入池 0 | ✅ |
| 8 | 许可不明 | `ASSET_LICENSE_MISSING`/`_UNCLEAR`/`_RESTRICTED` + `needs_hitl=True`、入池 0 | ✅ |

**引擎级 fail-closed（`logs/phase4d_failclosed.json`）**：429 与超时项目 → 检索 `external_verified=0`、
`external_error` 保留具体码、render **`BLOCKED`**（`[ASSET_INSUFFICIENT]`）、**无成片**、
**无 `render_output` / `attribution` 产物**；降级阶梯显式给出兜底档并要求人工（不静默出片）。

**不污染（同一证据文件）**：对照项目（有已校验外部候选）在失败运行前后
**全部文件逐字节一致**（含 `manifest.json` 与缓存目录）、任务数 2→2、产物数 2→2、事件数 9→9；
失败项目 `decisions`/`changelog` 零新增；真实 `projects/video_studio.db` 在证据脚本运行前后**sha256 未变**
（`fd8801aba7b590dd…`）；4-C 版本链未受影响（见 §5）。

## 4. 许可门禁与 attribution 不退化

- 许可门禁代码路径**未改动**（`core/materials.classify_license` / `license_block_reason` /
  `license_gate_applies` 原样复用，`material_provider._license_flags` 未改）；
- 4-D 新用例断言：三种许可问题（缺字段 / `unknown` / `fair use`）→ 分别
  `ASSET_LICENSE_MISSING` / `_UNCLEAR` / `_RESTRICTED`，`needs_hitl=True`，**入池 0**；
  且归类为 `LICENSE` 且 `retryable=False`（不会被重试"洗白"）；
- 缓存不携带 `license_cleared`/`license_class`，恢复后必须重新判定（防止"缓存把受限素材洗成已清权"）；
- **attribution 不退化**：`phase3a_real_chain.py --resume p_f4b466a4a024` → C1 台账与时间轴逐条一致、
  C2 台账镜头集合 == 有素材镜头集合（6,6）、C3 credits 文本随片落盘（`output/credits_t_b8f866ddc062.txt`，6 条）、
  B1/B3 成片内无 RESTRICTED/UNKNOWN（`restricted_or_unknown_in_film=[]`）、许可类别统计 `FREE_ATTRIBUTION: 6`。

## 5. 4-A / 4-B / 4-C 回归

| 项 | 命令 | 结果 |
|---|---|---|
| 4-A 指标 | `tests/metrics_test.py` | **18/18**（两次运行逐字节一致、只读、`provider=none` 证据） |
| 4-B 验证器 | `tests/semantic_check_test.py` | **29/29**（真值仍钉在 3-A 冻结产物 `a_2ed5f41d6b58` + C0 载体断言） |
| 4-C 机制 | `tests/human_selection_test.py` | **18/18** |
| 4-C 现状复核 | `phase4c_evidence.py` | 语义 **`MATCH=6 / MISMATCH=0 / UNKNOWN=0`**；版本链仍 v1–v5（当前 **v5 `t_b8f866ddc062`**）；attribution ⟷ 时间轴 1:1（6/6）；复核队列待办 0 / 必须 BLOCKED 0；复用检查与 4-C 收尾时**完全一致**（鲨鱼素材仍释放未用） |
| 套件总量 | `run_all_suites.py` | **38 total / 38 rc=0 / FAILED: []**（37 旧 + 新增 `supply_resilience_test` **55/55**） |

## 6. 3-A / 3-B 回归

| 项 | 命令 | 结果 |
|---|---|---|
| **3-A 真实链路（离线复核）** | `phase3a_real_chain.py --resume p_f4b466a4a024` | **16/16 PASS / FAIL 0 / PENDING 0**（真实 LLM 产物、真实 Provider 11,543,130 字节、TTS 6/6、时长契约 104.0s、成片可解码、抽帧 S01 0.459 / S02 0.921 / S03 0.348 / S04 0.472 / **S05 0.355** / S06 0.919 全部 ≥0.30） |
| **3-B 响度契约** | `tests/audio_loudness_test.py` | **32/32** |
| **3-B 失败路径** | `phase3b_failure_paths.py` | **12/12**（含 fare closed：不合规成片不交付） |
| 成片实测（4-C v5） | `phase4c_evidence.py` | h264+aac / **104.000s** / **-16.1 LUFS、TP -2.7 dBTP** / 抽帧 6/6 无失败 |
| 回归批次 | `phase3a_regression_batch.py` | **24 项全部 rc=0，非预期结果 = 0** |

## 7. `provider=none` 回归

- `config/config.json` sha256 `b264644539b2adbbf0f6897b5a118b2a` 与**基线 manifest 逐字节一致**（本次未改默认配置）；
- `DEFAULT_POLICY["provider"] == "none"`、`DEFAULT_POLICY["supply_cache"] is False`（新增开关默认关闭）；
- `provider_from_config({"tools": {"material": {"provider": "none"}}})` → `(None, None)`（纯 no-op，不构造 provider、不伪造候选）；
- `tests/metrics_test.py` M5 组（`provider=none` 证据、外部请求/下载 = 0 且照常出片）**通过**；
- 全量套件 38/38 通过（其中多项以默认 `provider=none` 配置运行）。

## 8. 网络 PENDING 原样保留

- 两项依赖真实网络的用例**状态与期望值均未改写**：`phase2e_failure_paths`、`phase2e_real_provider`
  （另 `phase3a_run1_verify` 标注为依赖真实网络）**仍记 `PENDING（环境）`**；
- **本轮实测（仅记录，不改状态）**：`phase2e_failure_paths` **29/29 通过**、`phase2e_real_provider` **13/13 通过**
  （本日 Wikimedia 链路可用）→ 与既有"间歇可用/超时振荡"的观察一致；回归批次 `非预期结果 = 0`；
- 4-D 的**全部新增断言均离线**（注入式假传输层 + 本地目录 provider），不依赖网络即可复现。

## 9. 新 baseline（ZIP + manifest + SHA256）与未做/已知限制

| 项 | 值 |
|---|---|
| 标签 | `4.x-phase4d-baseline` |
| ZIP | `docs/regression_2x/baseline/4.x-phase4d-baseline.zip`（5,918,783 字节） |
| **zip sha256** | **`f2c783d493a9cb9fe0e2b1601e22a9eaa117d07a2ef885103e0fd2b2d0a51641`** |
| 文件数 / 源码字节 | **351 文件 / 7,622,277 字节**（`src/ config/ tests/ scripts/` + 根文件，**排除 `docs/`**，与前序基线同口径） |
| manifest | `baseline/baseline_manifest_4.x-phase4d-baseline.json`（逐文件 sha256 由 ZIP 内字节重算） |
| 零漂移校验 | `verify_baseline.py 4.x-phase4d-baseline` → **MATCH**（zip 哈希一致、清单 == ZIP 条目、0 缺失、0 漂移） |
| 断点快照（非基线） | `snapshots/4.x-phase4d-20260916.{zip,db,json}`（DB sha256 `f903b106ad6212b2…`，13,021,184 字节） |
| 上一冻结基线（未动） | `4.x-phase4c-fix-baseline.zip` sha256 `3b0e998e…d96e`；`4.x-phase4c-baseline.zip` sha256 `08018d4e…171d` |
| 相对上一基线 | **代码 修改 2 / 新增 3 / 删除 0**；文档登记 2（`CHANGELOG.md`、`STATUS.md`）；`config`/DB schema **未变** |

**未做（如实登记，未进入 4-E/4-F）**：
1. **未接入第二 Provider**：授权为"如接入…"，按**最小增量**本轮不接入。既有抽象
   （`MaterialProvider` + `provider_from_config` 注册点）**未改**；将来接入必须：独立抽象、**默认关闭**、
   经**素材验证 + 许可验证 + attribution 验证**三重门（且需另行授权）。
2. **未做 BGM、UI、节奏自动改时长、自动发布**；**未做自动语义改选材**；未改数据库结构（**无表/列变更**）。
3. 已知限制（沿用 + 新增）：
   - 供给缓存是**搜索层元数据缓存**，TTL 内可能返回"过期候选清单"（例如来源已下线）；安全性不受影响
     （仍要重新下载 + 校验 + 许可门禁），但**新鲜度**依赖 TTL（默认 900s）；
   - 缓存键含策略指纹与查询，但**不含 provider 目录内容**：目录变更在 TTL 内不生效（同上，仅影响新鲜度）；
   - 429 的重试计数语义沿用 2-D/2-E（含最后一次未执行的计划重试），本次**未修改**（避免行为漂移）；
   - `ASSET_TRUNCATED` 归类为 TRANSIENT（原理上可重下修复），但当前实现**不自动重下**（如实登记）；
   - 4-B 知识库覆盖、人工决定无身份认证、候选池规模等既有限制**不变**（见 `PHASE4C_REPORT.md` §8）；
   - 3.x 已知问题 13 项状态**不变**（`docs/KNOWN_ISSUES.md`）。

**停止点**：按授权**已完成 4-D 底座即 STOP**，不进入 4-E/4-F。
