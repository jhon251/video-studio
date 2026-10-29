# 5-K 收尾后维护阶段报告（Post-Final Maintenance）

- 日期: 2026-09-21
- 阶段: 5-K（5.x 冻结后的**维护**阶段，非新能力阶段）
- 授权基线: `5.x-final-baseline`，ZIP sha256 `be1717b9c7fe9ed9124be3876db64b5893915a4d0ffad56bd37eded5e6e2141e`（**禁止修改/覆盖/重写**）
- 禁止项（授权原文）: **禁止新增视频能力**；**禁止修改 Judge、truth set、threshold、multimodal evaluator、human decision chain**
- 纪律: 只报 `PASS / PENDING / FAILED`；无证据不得 PASS；PENDING/FAILED 不得改写成 PASS

---

## 0. 一句话结论

十项授权动作**全部执行完毕**；①–⑦、⑨ **PASS**，⑧（全量回归）**FAILED —— 未全绿**，
⑩ 已 STOP。全量回归的 3 个红项**根因已实测闭合**：**全部来自授权 item ③（采纳当前真实默认配置）的副作用或环境网络**，
**与 ①②④ 的代码改动无关**（守卫与反证见 §5）。红项未修复（超出十项授权），已登记 `#62/#63/#64` 交人工决策。

---

## 1. 逐项判定（授权十项）

| # | 授权动作 | 判定 | 关键证据 |
|---|---|---|---|
| ① | 正式采纳 `editing/agent.py` 图片输入 `-framerate 1` 改动 | **PASS**（**并修正其缺陷**） | `tests/maintenance_fixes_test.py` M1a–M1f / M2a–M2d / M3a–M3d；§2 三形态对比表 |
| ② | 正式采纳 `ffmpeg_tool.py` 两处超时 1800→7200 s | **PASS** | M5a（`timeout=7200` ×2、无 `1800`）、M5b（`probe=120`/`concat=600`/ffprobe 校验 `60` 未动） |
| ③ | 采用当前真实 DeepSeek 默认配置（官方 `deepseek-flash`，不再以旧 V4 Flash 为目标） | **PASS**（采纳完成）**＋代价已实测登记** | M6a–M6c：tiers `M/F=deepseek-flash`、`R=deepseek-v4-pro`；router 回退不再指向 `deepseek-chat`，历史别名登记 `LEGACY_MODEL_IDS`；`logs/phase5k_model_audit.json`。**代价**：见 §5 红项（`#62/#63/#64`） |
| ④ | 为①②加针对性回归 + 「视频输入路径不受影响」反证 | **PASS** | 新增 `tests/maintenance_fixes_test.py` **28/28**；M4a（视频路径 2.0 s / 30 fps / h264）、M4b（命令中无 `-framerate`/`-loop`） |
| ⑤ | 补全 CHANGELOG（5-H/5-I/5-J/5.x Final/本阶段产品改动）并修时序 | **PASS** | 条目齐全、倒序正确（`5-K`@9 → `Final`@71 → `5-J`@95 → `5-I`@113 → `5-H`@127 → `V2.5.7`@146）；`logs/phase5k_evidence.json` → `docs_registration` |
| ⑥ | 清理 `config.config.mock.json.bak` 等杂物 | **PASS** | 2 个 `.bak`（6,423 B/`b2646445…`、45,798 B/`09204d62…`）移入 `output/_quarantine_20260921/` + `MANIFEST.json`；`config/` 内 `*.bak/*.tmp/*.orig` = 0（M7a/M7b） |
| ⑦ | 审计发现**只登记不修复** | **PASS** | `docs/KNOWN_ISSUES.md` §18 新增 **#52–#64**（悬空候选引用 13、陈旧 `external/.index.json` 11、素材编辑缺一等溯源、邮票 sha 不明变化、运维旁路、覆盖缺口、跨文档口径不一致、本次配置副作用三项） |
| ⑧ | 针对性 + 全量回归 + 基线校验 | **FAILED（未全绿）** | 针对性 **28/28 PASS**；批次 **21/24 符合预期**；单元套件 **44/47 rc=0**；只读电池子集 **8/8**；基线校验 **MATCH**；红项见 §5 |
| ⑨ | 产出新基线 `5.x-post-final-maintenance-baseline`（不得覆盖旧 Final） | **PASS** | 新基线 385 文件 / `b24023647f26…` / `verify_baseline` → **MATCH（missing 0 / drift 0）**；`5.x-final-baseline.zip` 哈希**未变**（384 条目）；快照 `snapshots/5.x-post-final-maintenance-20260921`；状态文件明示 **NOT_ALL_GREEN** |
| ⑩ | 停止并只报 PASS/PENDING/FAILED | **PASS** | 本报告 + `PHASE5K_CHECKPOINT.md`；无后续动作 |

---

## 2. item ① 的证据：缺陷是真实存在的，修正后与冻结基线语义一致

`post-final` 漂移形态（`-loop 1 -framerate 1 -t d -i 图`，无 `trim`）在 1 fps 图片源 + `-t d` 下**只产出约 d−1 帧**，
导致**每个图片镜头静默短约 1 s**。三种形态**同条件**实测（真实 ffmpeg，`tests/maintenance_fixes_test.py` M2，
S0=冻结基线形态 / S1=漂移形态 / S4=5-K 修正形态）：

| 镜头时长 d | S0 冻结形态 | S1 漂移形态 | S4 修正形态 | S4 帧数 | S4 标称率 |
|---|---|---|---|---|---|
| 2.0 s | 1.967 s | **1.000 s（−0.967）** | 1.967 s（Δ=0.000） | 60 | 30/1 |
| 2.5 s | 2.467 s | **2.000 s（−0.467）** | 2.467 s（Δ=0.000） | 75 | 30/1 |
| 20.0 s | 19.967 s | **19.000 s（−0.967）** | 19.967 s（Δ=0.000） | 600 | 30/1 |
| 73.4 s | 73.367 s | **72.000 s（−1.367）** | 73.367 s（Δ=0.000） | 2202 | 30/1 |

- **片级**（3 镜 7.0+5.5+9.25=21.75 s，同条件）：S4 视频轨 **21.733 s**、S1 **19.000 s**（**短 2.733 s**）→ M3a–M3d。
- **既有产物**（`p_96efdc03e1aa` v7）：容器 **1532.0 s**（音轨占满）但**视频轨仅 1511.0 s（短 21 s = 21 镜 × 1 s）**（`logs/audit_p96efdc_film_check.json`）。
  **不回溯重制**（登记 #57）。
- 结论：**该改动方向正确（1 fps 取帧把解码量从 25·d 帧降到约 d 帧）、但原实现有缺陷**；
  5-K 采纳**修正后**形态：输入 `-t ceil(d)+2` + 每段 `fps,trim=duration=d,setpts=PTS-STARTPTS`。
- 其它图片合成分支（背景图 `-loop 1 -t total`、`stage32b/assemble.py`、冻结的 `ops/mm_quality.py` 合成夹具）
  仍是**旧（默认 25 fps）形态**，不受该缺陷影响，也**未改动**（M1f + 全库 grep 证据）。

---

## 3. item ③ 的证据：默认配置已切到当前官方模型

| 项 | 值（实测） |
|---|---|
| tiers | `R=deepseek-v4-pro`（8192）、`M=deepseek-flash`（16384）、`F=deepseek-flash`（2048） |
| 价格表 | 覆盖 `deepseek-flash` / `deepseek-v4-pro`；历史别名一律 `unknown_pricing`（不猜价） |
| router | 回退 = `CURRENT_OFFICIAL_MODELS["routine"]`（不再回退 `deepseek-chat`）；`LEGACY_MODEL_IDS = (deepseek-chat, deepseek-reasoner, deepseek-v4-flash-vision-exp)` |
| 历史 id 清册 | 冻结判定工具 3 个文件（`sufficiency_judge`/`llm_semantic_judge`/`evidence_signal` 的 `MODEL_DEFAULT="deepseek-chat"`）、`stage33/**` 10 个文件（`deepseek-v4-flash-vision-exp`）、`output/**` 历史脚本 29 个 → **一律未改**（登记 #59） |

---

## 4. item ⑥/⑦ 的证据

- 隔离：`output/_quarantine_20260921/MANIFEST.json`（原路径/大小/sha256/时间可回溯）；隔离文件 sha 复核一致；`config/` 无残留。
- 登记：`docs/KNOWN_ISSUES.md` §18 **#52–#64**（13 条），**全部为登记，未修复**；`#56` 是本阶段**实测发现并修正**的缺陷（RESOLVED (5-K)）。

---

## 5. item ⑧ 全量回归：如实结果（**未全绿**）

### 5.1 组成与结果

| 回归组成 | 规模 | 结果 |
|---|---|---|
| 针对性套件 `tests/maintenance_fixes_test.py` | 28 项 | **28/28 PASS（rc=0）** |
| 全量批次 `phase3a_regression_batch.py` | 24 项 | **21 项符合预期 / 3 项红**（exit=1） |
| 单元套件 `run_all_suites.py` | 47 个套件 | **44 rc=0 / 3 红** |
| 电池只读子集 `phase5k_battery_readonly.py` | 8 项 | **8/8 rc=0** |
| 冻结证据恢复 | 2,148 文件 | **drift 0 / missing 0（MATCH）**；148 个被回归改写者逐文件回拷，79 个新增者保留 |
| 基线校验 | 新旧各一 | 新 `5.x-post-final-maintenance-baseline` → **MATCH**；旧 `5.x-final-baseline` → 本体哈希**未变** |

### 5.2 红项明细（全部根因已闭合）

| 红项 | 现象 | 根因（实测证据） | 归属 |
|---|---|---|---|
| `run_ingest_test`（批次项） | 40 轮后 `retrieval 未匹配到本地素材候选` / 无成片 | 真实模型产出 30 VERIFIED + **4 UNSUPPORTED** claim → **冻结生产闸门**（全部 claim 须 VERIFIED/REJECTED）按其 fail-closed 设计**阻塞 11 个生产任务（`retry_count=0`）**；测试脚本的批准过滤器不覆盖 UNSUPPORTED（其设计年代只有 1 条 mock claim） | **item ③ 副作用**（#62） |
| `metrics_readonly`（批次项） | 17/18，M5d 红 | `config/config.json` sha `7b03424846f1…` vs 钉定目标 `baseline_manifest_3.x-final-baseline.json` 的 `b264644539b2…`（**钉定目标本身早已过期**，本次配置变更使其首次转红） | **item ③ 副作用**（#64） |
| `phase2e_real_provider`（批次项，网络） | `TransportError: [PROVIDER_TIMEOUT] _ssl.c:1011: The handshake operation timed out` | Wikimedia 直连 TLS 握手超时（与历史 `PENDING（环境）` 同类；同批 `phase2e_failure_paths` 本轮 29/29 通过 → 网络抖动） | **环境** |
| `cost_accounting_test`（套件） | `KeyError: 'mock'`（L140） | 同 `#62/#64`：`config.json` 不再含 `llm.mock` | **item ③ 副作用**（#64） |
| `pipeline_mock`（套件） | `KeyError: 'mock'`（L53） | 同上 | **item ③ 副作用**（#64） |
| `metrics_test`（套件） | 17/18（M5d） | 同 `metrics_readonly` | **item ③ 副作用**（#64） |
| `e2e_mechanical`（批次项） | rc=0 **但结果退化**：`A/B=MAXROUNDS`、`C=BLOCKED`（冻结时代 3/3 **SETTLED**） | 原 mock 驱动的离线链改走真实 API（`model_used=deepseek-flash/deepseek-v4-pro`） | **item ③ 副作用**（#63，"rc 通过 ≠ 结果达标"） |

### 5.3 这些红项**不是** 5-K 代码改动造成的（反证）

- ①（图片输入参数）：M2/M3 三形态同条件对比证明修正形态与**冻结基线 S0 形态**逐例时长一致、帧数精确；
  视频路径 M4a/M4b 反证**未受影响**。
- ②（超时）：只放宽等待上限；M5b 证明其它 op 超时未动；M5c 证明图片/视频两条真实渲染路径均成功。
- ④：M8a 证明 Judge / truth set / multimodal evaluator / human decision chain / thresholds 与 `5.x-final-baseline`
  **逐字节一致**；M8b 证明**旧 Final 基线 ZIP 哈希未变**；M8d 证明未新增 `ops/` 工具（无新视频能力）。
- 红项 3 个套件/1 个批次项的报错文本与调用栈均指向 `llm.mock` 缺失或配置 sha 钉定，**与 video/render/ffmpeg 路径无关**。

### 5.4 未执行项（如实登记，见 #60）

- `phase3a_real_chain.py`：真实网络链**重跑**型脚本，会改写 5 份冻结证据日志（2026-09-21 曾误跑并已回拷）；
  本阶段通过项目自带电池机制与批次内只读复核（`phase2_accept.py --verify` → **PASS**）覆盖。
- `4ab…5f_evidence.py`（证据重生成）、`5e_calibration` / `5f_judge`（重算 CLIP/Judge）：其被守卫的模块已由 M8
  **逐字节证明未改**，重跑只产出等价证据且会改写冻结日志，故未执行。
- 因此本阶段**没有**"电池 25/25"式表述；可比口径仅 §5.1 的组成与结果。

---

## 6. item ⑨ 新基线

| 项 | 值 |
|---|---|
| tag | `5.x-post-final-maintenance-baseline` |
| ZIP | `docs/regression_2x/baseline/5.x-post-final-maintenance-baseline.zip`，sha256 `b24023647f263f3f300f6de8af23b4ae532f4d4d769e7a117b68046f6eb48c14` |
| 文件数 / 源码字节 | **385** / 8,346,816 |
| manifest | `baseline_manifest_5.x-post-final-maintenance-baseline.json`（411 由 ZIP 内条目字节重建，权威口径） |
| 校验 | `verify_baseline.py` → **MATCH**（zip 哈希一致、manifest == ZIP 条目、**missing 0 / drifted 0**） |
| 相对 `5.x-final-baseline` | 新增 1（`tests/maintenance_fixes_test.py`）；修改 6（`CHANGELOG.md`、`STATUS.md`、`config/config.json`、`agents/editing/agent.py`、`llm/router.py`、`tools/ffmpeg_tool.py`）；删除 0 |
| 旧 Final | ZIP sha256 `be1717b9…` **未变**、384 条目**未变**（M8b + `verify_baseline` 复算） |
| 快照 | `docs/regression_2x/snapshots/5.x-post-final-maintenance-20260921.{zip,db,json}`（DB 37,171,200 B / sha256 `318d5be2…`） |
| 状态文件 | `baseline/baseline_status_5.x-post-final-maintenance-baseline.json` → `regression_status.verdict = "NOT_ALL_GREEN"` |

> ⚠ **冻结条件差异（明示）**：项目既有 DoD 要求"电池全绿才冻结基线"（5-G 曾因电池红而**拒绝冻结**）。
> 本次按授权 item ⑨ **显式要求**产出新基线，但 §5 的红项尚未处置，故基线随附状态文件明确标注
> `NOT_ALL_GREEN`，**不得当作"全绿验收基线"引用**；人工若决定修 #62/#63/#64，应在其后**重新冻结**（覆盖本 tag 或另起 tag）。

---

## 7. 需要人工决策的事项（5-K **未**实施）

| # | 事项 | 备选处置 |
|---|---|---|
| 1 | `config.json` 不含 `llm.mock` 导致 3 个套件 + 1 个批次项红、e2e 退化、离线回归转真实计费（#62/#63/#64） | ① 恢复**仅供离线**的 `llm.mock`（不动真实默认模型）；② 让离线回归脚本自带 mock 配置（`docs/` 不在基线内）；③ 接受现状并把相关项标注为"需真实 API" |
| 2 | `metrics_test` M5d 的钉定目标仍是 `3.x-final-baseline`（早已过期） | 重钉到新基线 tag（1 行改动） |
| 3 | `p_96efdc03e1aa` v7 成片视频轨短 21 s（#57） | 是否用修正后的渲染参数**重渲染**（新授权） |
| 4 | 审计完整性四件套（#52–#55）与运维旁路（#58） | 按 `AUDIT_P96EFDC03E1AA.md` §3 优先级排期 |
| 5 | 跨文档口径不一致（#61）；`STATUS.md` 顶部叙述仍只描述 GLM 会话的**首版占位卡 DRAFT**、未反映其最终 21 镜真实素材成片（`AUDIT_WORKSPACE_20260921.md` §3 已登记） | 是否回改历史阶段报告与 `STATUS.md`（5-K 未回改；`STATUS.md` 在基线内，改动需随新基线一起重冻） |

---

## 8. 本阶段产物清单

- 产品/基线内：`src/video_studio/agents/editing/agent.py`、`src/video_studio/tools/ffmpeg_tool.py`、
  `src/video_studio/llm/router.py`、`config/config.json`（采纳）、`tests/maintenance_fixes_test.py`（新）、
  `CHANGELOG.md`、`STATUS.md`
- 基线外（docs/）：`PHASE5K_REPORT.md`（本文）、`PHASE5K_CHECKPOINT.md`、`BASELINE_README.md`（新增 5-G/Final/5-K 三行）、
  `docs/KNOWN_ISSUES.md` §18、脚本 `phase5k_{cleanup,framerate_probe,duration_probe,fix_probe,fix_probe2,freeze_logs,restore_logs,
  preserve_and_restore,evidence,baseline_status,battery_readonly,cost_probe,ingest_diag,ingest_diag2,5b_drift,ki_order,ki_order2,ki_repair}.py`
- 证据（`docs/regression_2x/logs/`）：`phase5k_evidence.json`（汇总）、`phase5k_targeted_regression.txt`、
  `phase5k_model_audit.json`、`phase5k_logs_restore.json`、`phase5k_battery_readonly.json`、`phase5k_cost_probe.json`、
  `phase5k_ingest_diag{,2}.json`、`phase5k_5b_drift_preexisting.json`、`phase5k_batch_logs/`（本轮 88 个产物留档）
- 隔离区：`output/_quarantine_20260921/`（+ `MANIFEST.json`）；冻结备份保险：`output/_5k_frozen_backups_20260921/`

---

## 9. 事后补记（5-L 修正记录，2026-09-21；**不改动本文档上文任何已记录的事实与数字**）

> 本文档 §0–§8 记录的是 5-K **首轮**执行与判定结果：**首轮全量回归 = FAILED（未全绿）**，
> 批次 **21/24**、单元套件 **44/47**、`e2e_mechanical` 结果退化（MAXROUNDS/MAXROUNDS/BLOCKED）—— 这些数字
> **保持原样、未被改写**。下列是后续阶段 5-L 的**修正记录**（事实口径补记）：

| 5-K 首轮红项 | 5-K 根因（本文档 §5.2） | 5-L 修正动作 | 5-L 实测结果 |
|---|---|---|---|
| `run_ingest_test` | 真实模型 + 冻结 claim 闸门 fail-closed（#62） | 新增独立离线 mock 配置 `config/config.mock.json`，该用例**显式** `--config` 指定 | **VERDICT: PASS**（S01 抽帧 期望=最高=asset_f304650dbc24、corr 0.747，与 mock 时代冻结值一致） |
| `cost_accounting_test` | `KeyError: 'mock'`（#64） | 同上 + **测试契约更新**（旧断言"mock 运行费用为 0"的前提随配置换代消失 → 改为"按价目表如实计价并写回任务"，并保留"逐任务非负、与 compute_cost 同源可复算"） | **20/20 通过** |
| `pipeline_mock` | `KeyError: 'mock'`（#64） | 同上（显式加载 mock 配置） | **rc=0**（48/48 套件之一） |
| `metrics_readonly` / `metrics_test` M5d | 钉定目标 `3.x-final-baseline` 早已过期（#64） | M5d **改钉当前有效基线** `5.x-post-final-maintenance-baseline`（测试契约更新，**断言强度不变**）；4-A 证据脚本同步改钉 | **18/18 通过** |
| `e2e_mechanical` 结果退化 | 离线机械 E2E 改走真实 API（#63） | `run_all_tests.py` **显式** `--config` 指定 mock 配置 | **3/3 SETTLED** |
| `phase2e_real_provider` | 环境网络（Wikimedia TLS 握手超时） | **未做任何代码改动** | 本轮 **13/13 通过**（网络窗口恢复；环境属性不变，历史 `PENDING（环境）` 记录未改写） |
| #56 既有产物视频轨短 21 s | 5-K 只修渲染参数、不回溯重制（#57） | 用 5-K 修正参数**重渲染** `p_96efdc03e1aa`（render v8 `t_30070f93a77e`） | **视频轨 1511.0 s → 1531.96 s**（时间轴 1532.0 s，残差 1 帧）；旧 v7 成片 sha256 未变；topic/script/claims/人工决策全未变 |

**5-L 电池（与本文档 §5.1 同一步骤序列，25 步）**：**25/25 步 rc=0**（`all_rc_zero_raw=True`）、
批次 **24/24 符合预期**、单元套件 **48/48 rc=0**、冻结证据日志恢复 **drift 0 / missing 0**、
旧 `5.x-final-baseline` sha256 **未变**；新基线 `5.x-post-final-maintenance-baseline-r2`
（`verify_baseline` → **MATCH**）**不覆盖** r1 与 5.x Final。详见 `docs/regression_2x/PHASE5L_REPORT.md`。
