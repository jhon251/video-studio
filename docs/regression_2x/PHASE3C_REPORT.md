# 3.x Phase 3-C 报告：最终运维与成本收口

- 日期：2026-09-15
- 授权范围（逐字）：**"继续执行 3.x Phase 3-C：最终运维与成本收口"**（不新增业务能力；完成后立即 STOP）
- 阶段判定：**PASS**（Final DoD 见 §0；所有真实失败/受限项均按原状保留，见 §4 与 `KNOWN_ISSUES.md`）

---

## 0. Final DoD 逐条判定

| # | 要求 | 判定 | 证据 |
|---|---|---|---|
| 1 | 只读命令 `run.py report <project_id>`（任务/产物/事件/失败/成本/素材/响度与验证） | **PASS** | §1；`src/video_studio/ops/report.py`；`tests/report_command_test.py` **18/18** |
| 1b | **不得**修改运行状态、不得触发任务 | **PASS** | §1.3：DB sha256/行数前后不变；只读连接写操作被 SQLite 拒绝；连续 3 次运行零改动 |
| 2 | 成本边界收口：LLM 成本 / 外部素材用量分离；¥3.24 正式结论；不得把估算写成账单 | **PASS** | §2；`docs/COST_BOUNDARY.md`；`logs/phase3c_cost_boundary.json` |
| 3 | 运行手册（入口/resume/redo/验证/429/前置条件/常见失败） | **PASS** | `docs/RUNBOOK.md`（§3） |
| 4 | 已知问题台账（S04/S06、2-E 不可复原、stage32b +0.4 dB 等，**不得改写为 PASS**） | **PASS** | `docs/KNOWN_ISSUES.md`（13 项，全部标 `LIMITATION`/`BY DESIGN`/`ENV`） |
| 5 | 完整最终回归（33/33、批次、3-A、3-B、2-C/2-D/2-E/ingest/E2E/恢复） | **PASS** | §5 |
| 6 | `report` 五类场景（正常/失败/部分/不存在/只读性） | **PASS** | §1.2（证据文件逐场景留档） |
| 7 | 最终报告 + checkpoint + `3.x-final-baseline.zip` + manifest + SHA256 + 零漂移 + snapshot | **PASS** | §6（`verify_baseline.py` → **MATCH**） |

## 1. `run.py report <project_id>`（只读）

### 1.1 实现

- 新模块 `src/video_studio/ops/report.py`：`build_report()`（纯读数据）+ `format_report()`（纯渲染）+ `readonly_connection()`；
- CLI 接入 `src/video_studio/cli.py`：`report` 子命令**不经过** `build_engine()`（避免建库/建目录等任何副作用），
  直接以 `file:<db>?mode=ro` 打开数据库；不存在项目 → **rc=2** + 明确信息（不崩溃）；
- 输出内容：项目信息 / 任务状态分布 + 待审批 + 未派发 / 失败与阻断原因（任务行 + 最近事件）/
  产物清单与关键产物指纹 / **成本（LLM，估算）** / **外部素材用量（非计费）** / 成片时长契约 /
  **响度实测（目标/误差/校正次数/不达标原因）** / 抽帧核验与上屏 / 旁白状态 / 署名台账 / 质检结论；
- `--json` 提供同一数据源的机器可读输出。

### 1.2 五类场景证据（命令 / 返回码 / 关键结果 / 产物路径）

采集脚本：`python docs/regression_2x/phase3c_report_evidence.py`

| 场景 | 命令 | rc | 关键结果 | 产物 |
|---|---|---|---|---|
| 正常项目（3-A/3-B 真实链路） | `python run.py report p_f4b466a4a024` | **0** | 29 任务全 SUCCEEDED；成本估算 $0.0938；外部素材 2 请求 / 11,543,130 B / 限流 15；响度 **ok=True I=-16.1 LUFS TP=-2.7 dBTP Δ=-0.1**；抽帧 6/6 无失败；台账 6 条 = 上屏 6 条 | `logs/phase3c_report_normal.txt` |
| 失败项目（FAILED） | `python run.py report p_3cbad*` | **0** | 列出 `FAILED` 任务与 `LOUDNESS_OUT_OF_RANGE：I=-19.7 LUFS`；最近 `TASK_FAILED` 事件同因；如实显示**无成片** | `logs/phase3c_report_failed.txt` |
| 部分完成项目（PENDING） | `python run.py report p_3cpart*` | **0** | `PENDING=1` 并列出未派发任务；**无 render_output**（如实标注） | `logs/phase3c_report_partial.txt` |
| 不存在的项目 | `python run.py report p_3c_no_such_project` | **2** | `项目不存在: p_3c_no_such_project`；`build_report` 返回 `found=False`；无异常栈 | `logs/phase3c_report_missing.txt` |
| `--json` | `python run.py report p_f4b466a4a024 --json` | **0** | JSON 可解析，keys 含 `cost/material/film/attribution/...`；`tasks.total` 与文本模式一致（29） | `logs/phase3c_report_json.json` |

自动化断言（`tests/report_command_test.py`，**18/18 PASS**，rc=0）覆盖同一批场景，并额外断言：
成本标注为估算（非账单）、外部素材标注为非计费且统计到真实下载字节、响度证据被读出、
台账 ⟷ 上屏逐条一致、失败项目无成片仍可报告。

### 1.3 只读性验证（三重）

| 检查 | 方法 | 结果 |
|---|---|---|
| SQLite 层面禁写 | 用报告同款 `readonly_connection()` 执行 `INSERT` | **被拒**：`sqlite3.OperationalError: attempt to write a readonly database` |
| 文件级 | 运行前后 `sha256` + 字节大小 | **完全不变**（`logs/phase3c_report_readonly.txt`） |
| 行级 | `projects/tasks/artifacts/events/decisions/claims` 六表行数 | **完全不变**；连续 3 次 `report` 后仍不变（无新增任务/事件 → 未触发调度） |

### 1.4 顺带修掉的真实缺陷（3-C 发现）

**CLI 输出编码**：Windows 管道/重定向下 Python 用 locale 编码（本机 **cp936**）输出中文，
外部按 UTF-8 读取即乱码/解码失败（`run.py report` 最明显）。已按 Phase 1.1“subprocess 编码收口”的同一口径，
在 `cli.main()` 起始处把 `stdout/stderr` 固定为 UTF-8（`_force_utf8_io()`，异常安全）。
—— 这属**真实缺陷修复**，不是测试适配（修的是代码，不是断言）。

## 2. 成本边界收口

证据：`python docs/regression_2x/phase3c_cost_boundary.py` → `logs/phase3c_cost_boundary.json`

### 2.1 三条口径分离（详见 `docs/COST_BOUNDARY.md`）

| 口径 | 本次实测 | 性质 |
|---|---|---|
| **A. LLM 成本** | 全库任务行 `cost_usd` 合计 **$71.57108**（含 V1/V2 历史阶段；`deepseek-chat` $36 + `deepseek-reasoner` $35）；**3.x 当前线**（flash+v4-pro）**$0.5711**；`LLM_CALL` 事件 **1,032 次 / 847,319 tokens**（in 302,598 / out 544,721），事件内成本合计 $0.544703 | **估算**（token×价目表）；**无账单接口** |
| **B. 外部素材用量** | 请求 **71**（失败 0）；真实下载 **65,079,590 B**；**429 限流 144 次**；本地缓存 **122 文件 / 78,921,883 B**；**金额 $0.00** | **用量**（Wikimedia 免费、无 key）——**不是金额** |
| **C. 账户余额** | `/user/balance`（免费只读）：窗口内 8.79 → 8.53 CNY，而**本地 LLM 调用 = 0**、**本地事件新增 = 0** | 服务端真值，但**异步结算且可能含其它调用方**，不可逐笔归因 |

> **两个 LLM 口径为何不等**（$71.57108 vs $0.544703）：任务行 `cost_usd` 由各 Agent 写入（历史阶段跨阶段累计/直接赋值），
> `LLM_CALL` 事件是**逐次调用**记账。差值**不是漏账证据**，而是口径不同；单次运行的完整性由
> `tests/cost_accounting_test.py` 的守卫断言（`client.calls == LLM_CALL 事件数`、judge 直连也必须记账）。

### 2.2 ¥3.24 残余的正式结论

- **分类**：`NOT_ATTRIBUTABLE_CLIENT_SIDE`（**估算差额**，既不是账单，也不是台账算错）。
- **数量口径**：≈¥3.24（Phase 1.1 实测：余额 -4.78 CNY，可归因 ≈¥1.54，残差 ≈¥3.24）；人民币依赖 7.1 的换算率（客户端不可验证）。
- **机制复验（本次重跑，可复现）**：在**零本地 LLM 调用**的 61.5s 窗口内，余额仍下降 **-0.26 CNY**
  （8.79 → 8.53），本地 `LLM_CALL` 与事件计数均**未变** → 直接复现“余额变化不能归因于本地调用”。
- **候选原因**（客户端无法进一步区分，故不强行归因）：① 同一 key 被其它调用方使用；② 更早窗口的费用仍在异步/批量结算；
  ③ 客户端不可观测的计价细节（USD/CNY 换算率、服务端舍入/阶梯）。
- **纪律**：**没有**修改任何数字去凑平；本阶段也未把它写成账单或 PASS。

## 3. 运行手册与已知问题台账

- **`docs/RUNBOOK.md`**：正式入口（`init/plan/run/loop/status/report/approve/claims/ingest/recover`）；
  **`resume` ↔ `redo retrieval` ↔ `redo render` ↔ 验证命令的区别**（含"想重跑必须显式 redo"的坑）；
  真实 LLM / 真实 TTS / 真实 Provider / ffmpeg 的**前置条件**；Wikimedia **429/超时/下载失败/域名不可达**的处理；
  常见失败（`CLAIM_GATE_BLOCKED`/`NARRATION_INCOMPLETE`/`ASSEMBLY_BLOCKED`/`LOUDNESS_OUT_OF_CONTRACT`）与恢复；
  检索 0 命中的排查顺序；只读体检与回归命令；环境事实（cp936、PS 中文陷阱、限流常态）。
- **`docs/KNOWN_ISSUES.md`**：13 项，全部保留原状、**无一项被改写为 PASS**：
  #1 S04/S06 语义误选（`LIMITATION`，4.x 语义对齐后以"重选材"解决）；
  #2 2-E 历史成片音轨不可完全复原（`LIMITATION`，已还原集成响度、真峰差异如实记录）；
  #3 `stage32b` 保留 +0.4 dB 补偿（`BY DESIGN`，成片 -16.8 LUFS 在契约内）；
  #4 中文-only 查询命中率低；#5 媒体主机 429 常态化；#6 本地素材不做许可门禁（`BY DESIGN`）；
  #7 响度契约可配置（默认不放松）；#8 成本仅估算（无账单）；#9 失败路径使用合成契约（测试用）；
  #10–#13 Claim 人工介入、镜头数依赖 LLM、无项目清理策略、无 Git。

## 4. 完整最终回归

见 §5 表格（全部在**最终代码**上执行；批次的分类判读为 **非预期结果 = 0**）。

## 5. 回归结果

**批次汇总**：`phase3a_regression_batch.py` → **21/21 项 rc=0**；`phase3a_classify_batch.py` →
**非预期结果 = 0**（`logs/phase3a_regression_batch_classified.json`）。
**套件**：`run_all_suites.py` → **34/34 rc=0 / FAILED: []**（含新增 `report_command_test` **18/18** 与 3-B 的
`audio_loudness_test` **32/32**）。

| 项 | 命令 | 结果 |
|---|---|---|
| 全部套件 | `run_all_suites.py` | **34 total / 34 rc=0 / FAILED: []** |
| 回归批次 | `phase3a_regression_batch.py` + `phase3a_classify_batch.py` | **21/21 rc=0 · 非预期结果 = 0** |
| 3-A 真实链路 | `phase3a_real_chain.py --resume p_f4b466a4a024` | **16/16 PASS**（PASS=16 FAIL=0 PENDING=0） |
| 3-B 响度 | `tests/audio_loudness_test.py` / `phase3b_failure_paths.py` / `phase3b_audit.py` | **32/32** / **12/12** / 实测 **-16.1 LUFS（正式链）· -16.8（stage32b）** |
| 3-C 报告 | `tests/report_command_test.py` | **18/18**（五场景 + 只读性） |
| 2-C / 2-D / 2-E | `phase2c_trace` / `phase2c_fault_matrix` / `phase2d_boundary_matrix` / `phase2d_provider_e2e` / `phase2e_real_provider` / `phase2e_failure_paths` | 38/38 · A/C 出片 B/D BLOCKED · 40/40 · 12/12 · **13/13** · **29/29** |
| ingest / E2E / 恢复 | `run_ingest_test` / `run_all_tests.py --fresh` / `tests/smoke_mock.py` | PASS（抽帧 0.747）· A/B/C **SETTLED**（17.000s/24 kHz）· 12/12（含断点恢复 1 次） |
| 2-A/B 验收 / 二进制 / 真实小测 / 旁白契约 / 素材装配 | `phase2_accept.py --verify` / `check_binaries.py` / `real_small_test.py` / `narration_contract_test.py` / `scene_assembly_test.py` | PASS · PASS · PASS（MockLLM=0）· 40/40 · 15/15 |
| 成本边界 | `phase3c_cost_boundary.py` | rc=0（§2 数值） |

> 自动化范围说明：`report_command_test` 额外覆盖"报告不改变 DB 字节/行数、且不触发任务"；
> 恢复能力由 `smoke_mock`（断点恢复 1 次）与批次中的 E2E 全 SETTLED 共同覆盖。

## 6. 最终基线与 snapshot

| 项 | 值 |
|---|---|
| 标签 | `3.x-final-baseline` |
| ZIP | `docs/regression_2x/baseline/3.x-final-baseline.zip`（5,846,753 字节） |
| zip sha256 | `b82ba77ea85cfd22ad7206b95f2a86b927b585254d375d941a3ee1a1dcc4646f` |
| 文件数 / 源码字节 | **340 文件 / 7,422,723 字节**（`src/ config/ tests/ scripts/` + `run.py pyproject.toml README.md CHANGELOG.md STATUS.md`；**排除 `docs/`**） |
| manifest | `baseline_manifest_3.x-final-baseline.json`（逐文件 sha256 由 ZIP 内字节重算） |
| 零漂移校验 | `verify_baseline.py 3.x-final-baseline` → **MATCH**：zip 哈希一致、清单 == ZIP 条目、**0 缺失、0 漂移** |
| 最终 snapshot | `snapshots/3.x-final-20260915.{zip,db,json}`（DB sha256 `61e05c01ea5bd412…`，9,859,072 B） |

关键指纹（相对 3-B 基线）：`ops/report.py`（**新**）、`ops/__init__.py`（**新**）、`cli.py`（新增 `report` 子命令 +
UTF-8 输出收口）、`tests/report_command_test.py`（**新**，18/18）；
**未改动**：`config/config.json b264644539b2adbb…`（仍 `provider=none`）、`core/materials.py 253b628c2d0b1348…`、
`tools/material_provider.py 2607f35049716528…`、`tools/provider_wikimedia.py f5ee1f6a4183ae45…`、
`agents/editing/agent.py aeaf7c2c9f0e2851…`、`agents/retrieval/agent.py 32de908c26a8ab90…`、
`agents/voice/agent.py 9f102d2b78b8ba91…`、`core/engine.py becfdd8e56dd0e8b…`、`tools/ffmpeg_tool.py 9313f3b46af526f9…`。

## 7. 停止点

按授权：**未**做 BGM、**未**接入第二个 Provider、**未**做语义自动改选材、**未**做自动发布、**未**改 UI、
**未**建 Git tag、**未**修改默认 `provider=none`、**未**改动 Claim/HITL、append-only、恢复、任务/产物/event 契约、
**未**做大规模重构、**未**把 4.x 功能混入 3.x。**在此 STOP，等待下一阶段授权。**
