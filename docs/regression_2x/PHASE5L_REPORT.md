# 5-L 阶段报告：5-K 已确认失败项修复（离线 mock 独立化 + M5d 钉定换代 + 重渲染收口）

- 日期: 2026-09-21
- 阶段: 5-L（在 `5.x-post-final-maintenance-baseline` 之上继续；**不新增**视频能力 / Judge 能力 / truth set / 阈值 / 自动选材 / 自动发布）
- 授权基线: `5.x-post-final-maintenance-baseline`（r1，sha256 `b24023647f263f3f300f6de8af23b4ae532f4d4d769e7a117b68046f6eb48c14`）
- 旧终稿: `5.x-final-baseline` sha256 `be1717b9c7fe9ed9124be3876db64b5893915a4d0ffad56bd37eded5e6e2141e` —— **未被修改/覆盖**（每步复核）
- 判定纪律: 只报 `PASS / PENDING / FAILED`；无证据不得 PASS；**只有全部必要电池达到 DoD 才可标 PASS**

---

## 0. 结论

**5-L = PASS**（全部必要电池达到 DoD：电池 **25/25 步 rc=0**、批次 **24/24**、单元套件 **48/48 rc=0**、
E2E **3/3 SETTLED**、冻结证据日志恢复 **drift 0**、针对性 **28/28 + 23/23**、旧 Final sha 未变）。
新基线 `5.x-post-final-maintenance-baseline-r2` 已按门禁冻结（`verify_baseline` → **MATCH**），**不覆盖** r1 与 5.x Final。
**PENDING（环境）**：`phase2e_real_provider` 属环境网络项——本轮 **13/13 通过**，但历史 `PENDING（环境）` 记录**未被改写**（不代表网络问题已消除）。

---

## 1. 逐项判定（授权 11 项）

| # | 授权项 | 判定 | 证据 |
|---|---|---|---|
| 1 | 保留当前真实 DeepSeek 作为生产默认 | **PASS** | `config/config.json` 无 `llm.mock`；tiers `M/F=deepseek-flash`、`R=deepseek-v4-pro`；`cli.load_config(None)` 仍解析它（`offline_mock_test.py` L1a–L1c/L3a/L3b） |
| 2 | 恢复/重构**独立离线 mock 测试能力**，离线测试显式使用 mock | **PASS** | 新增 `config/config.mock.json`（生产配置逐字副本 + 仅追加 `llm.mock`，含 `_offline` 溯源块）；4 个调用点显式指定（L4）；`run_ingest_test` **PASS**、`e2e_mechanical` **3/3 SETTLED**、`cost_accounting_test` **20/20**、`pipeline_mock` **rc=0** |
| 3 | **禁止**把 mock 恢复成生产默认 | **PASS** | 生产配置无 mock（L1a）；`cli` 默认路径未改（L3b）；`src/**`+`run.py` **零**引用 `config.mock.json`（L5）；新增守卫套件 23/23 |
| 4 | `metrics_test`/`metrics_readonly` M5d 重钉当前有效 baseline/tag，记录为测试契约更新 | **PASS** | 改钉 `5.x-post-final-maintenance-baseline`（旧钉 `3.x-final-baseline` 已移除）；钉定 sha 可满足（`7b03424846f1` 双侧一致）；断言强度不变（仍逐字节 sha256）；`metrics_readonly` 批次 **18/18**；`phase4ab_evidence.py` 同步改钉 |
| 5 | `p_96efdc03e1aa` 用 5-K 修正参数重渲染（仅消除视频轨少 21 s） | **PASS** | render **v8** `t_30070f93a77e`：视频轨 **1511.0 → 1531.96 s**（时间轴 1532.0 s，残差 1 帧）；−16.1 LUFS / TP −2.5 dBFS；attribution 21 镜 1:1；**topic/script/claims/人工决策全未变**；旧 v7 sha 未变 |
| 6 | 不处理 provenance 四件套，仅保留 #52–#64 登记 | **PASS** | `KNOWN_ISSUES.md` §18 仍为 #52–#64（64 条），**未新增、未改写** |
| 7 | 历史报告与 STATUS.md 只做事实口径修正 | **PASS** | `STATUS.md` 顶部新增 5-K（**首轮 FAILED** + 根因 + 未改写声明）与 5-L 两块；`PHASE5K_REPORT.md` 追加 §9（**不改动 §0–§8 任何数字**）；`BASELINE_README.md` r1 行加事实补注 + 新增 r2 行 |
| 8 | 重跑针对性 / 全量 / E2E / baseline verify | **PASS** | §2（电池 25 步全 rc=0 含批次与 E2E；两个 baseline verify MATCH） |
| 9 | 只有必要电池达 DoD 才标 PASS，否则保持 FAILED/PENDING；不得强行冻结为全绿 | **PASS** | 冻结脚本**带 6 项门禁**（G1–G6，全 PASS 才写基线）；本轮实测全绿后才冻结 r2 |
| 10 | 旧 `5.x-final-baseline` SHA 不变 | **PASS** | 每一步复核：`be1717b9…` 未变、384 条目未变（门禁 G6 + 证据包 `baselines.final`） |
| 11 | 完成后 STOP | **PASS** | 本报告 + `PHASE5L_CHECKPOINT.md`；无后续动作 |

---

## 2. 全量回归（5-L 电池：与 5-F/5-G/5-J **同一步骤序列**）

脚本 `docs/regression_2x/phase5l_battery.py` 用 **AST 解析** `phase5f_regression.py` 的 `STEPS` 字面量作为步骤表
（防"悄悄少跑/换跑步骤"），仅把冻结日志备份/输出路径改为 5-L 专用（`logs_5l_frozen/`、`logs/phase5l_rerun/`），
**不改动 5-E 期的历史备份 `logs_5e_frozen/`**。

| 口径 | 结果 |
|---|---|
| 电池步数 | **25/25 步 rc=0**（`all_rc_zero_raw = True`；总耗时 **4,260.9 s ≈ 71 min**） |
| 批次（阶段 2） | **24 项 → 24/24 符合预期**（0 非预期） |
| 单元套件 | **48 个 → 48 rc=0**（0 失败） |
| E2E（`e2e_mechanical`） | **`A/B/C = SETTLED / SETTLED / SETTLED`**（5-K 首轮为 MAXROUNDS/MAXROUNDS/BLOCKED） |
| 离线 ingest（`run_ingest_test`） | **VERDICT: PASS**（S01 抽帧 期望=最高=`asset_f304650dbc24`、corr **0.747**，与 mock 时代冻结值**一致**） |
| 针对性套件 | **28/28**（5-K 套件，仍全绿）+ **23/23**（5-L 新套件） |
| 真实链路 | `3a_real_chain` **PASS 16/16**；`phase2e_real_provider` **13/13**（网络窗口健康） |
| 冻结证据日志 | **drift 0 / missing 0**（162 个被回归改写者逐文件回拷、1 个新增保留；`frozen_logs_restored=True`） |
| 基线校验 | r1（历史）→ 因 5-L 改动而 `DIFF`（预期）；**r2 → MATCH（missing 0 / drifted 0）**；旧 Final → 本体哈希**未变** |

### 2.1 一次性披露：批次内 `suite_all` 与电池末尾 `unit_suites` 的差异

批次（阶段 2，21:38–21:59）内的 `suite_all` 曾记录 1 个红项 `cost_accounting_test`（**过期断言**，见 §4 §⑤）；
该断言在 5-L 内按测试契约更新修正后，电池末尾 `unit_suites`（阶段 25，22:19–22:36）复跑为 **48/48 rc=0**。
两处结果**均已留档**（`logs/phase5l_rerun/phase3a_suite_all.log` 与 `logs/phase5l_rerun/suites_summary.json`），
不做遮蔽；`run_all_suites.py` 的退出码不反映套件级失败（"rc 通过 ≠ 结果达标"），故此处以**套件级 summary**为准。

---

## 3. 离线 mock 独立化（item 1/2/3）

| 项 | 事实 |
|---|---|
| 生产默认 | `config/config.json` sha256 `7b03424846f15efcf4a68b30983effc0`，**无** `llm.mock`，tiers M/F=`deepseek-flash`、R=`deepseek-v4-pro` |
| 离线 mock 配置（新） | `config/config.mock.json`，sha256 `222503ee4c70374ab1b9d22d795110da`，= 生产配置**逐字副本 + 仅追加** `llm.mock`（15 个角色）+ `_offline` 溯源块（mock 来源 = 冻结 `5.x-final-baseline` 内 config，含 zip sha256 与段 sha256） |
| 显式消费者 | `tests/cost_accounting_test.py`、`tests/pipeline_mock.py`（加载 mock 配置）；`docs/regression_2x/run_ingest_test.py`、`docs/regression_2x/run_all_tests.py`（`run.py --config config/config.mock.json`） |
| 隔离证明 | `src/**` 与 `run.py` **零**引用 mock 配置；`cli.load_config(None)` 仍解析生产配置；`_offline.purpose` 明示"offline only, NOT the production default" |
| 语义不变式 | mock 配置的 `tiers` / `pricing` / `provider` 与生产**逐字一致**（mock 不改变模型与计价语义） |
| 守卫套件（新） | `tests/offline_mock_test.py` **23/23**（L1a–L9） |

---

## 4. 测试/证据契约更新（item 4，公开说明）

| 位置 | 变更 | 理由 | 强度 |
|---|---|---|---|
| `tests/metrics_test.py` M5d | 钉定 tag `3.x-final-baseline` → `5.x-post-final-maintenance-baseline` | 旧钉定目标**早已过期**（3.x 期），本次配置换代使其首次转红；属**契约换代** | **不变**（仍要求 `config/config.json` 与 manifest 逐字节 sha256 相等） |
| `docs/regression_2x/phase4ab_evidence.py` | 同步改钉当前有效基线 | 同上（证据脚本口径） | 不变（仍打印"现在/基线"两个 sha 与一致性判定） |
| `tests/cost_accounting_test.py`（1 处） | 「mock 运行费用为 0」→「mock 调用按价目表**如实计价**并写回任务（>0、模型在价目表内）」+「逐任务非负、与 `compute_cost` 同源可复算」 | 旧断言成立的前提是"mock 模型恰好不在价目表内"（历史 `deepseek-chat` 无价目），配置换代后前提消失 | 「价目未知不猜价（0 + `unknown_pricing` 标记）」仍由**同文件独立检查**保证；新增两条检查均在，套件由 19 → **20/20** 全通过 |

> **未修改任何业务语义**：本轮**零**产品代码改动（`src/**`、`run.py` 未动）；仅 `config/`（新增 mock 配置）、`tests/`、`docs/`、根文档。

---

## 5. 重渲染验收（item 5）

| 项 | 旧（render v7 `t_898378f6b0f8`） | 新（render **v8** `t_30070f93a77e`） |
|---|---|---|
| 视频轨时长 | **1511.0 s（短 21.0 s）** | **1531.96 s（残差 0.04 s = 1 帧 @25 fps）** |
| 容器 / 音轨 | 1532.0 s / 1532.0 s | 1532.0 s / 1532.0 s |
| 帧数 / 编码 / 分辨率 | 37,775 / h264+aac / 1920×1080 | 38,300 / h264+aac / 1920×1080 |
| 独立响度（ebur128） | −16.1 LUFS / TP −2.5 dBFS | **−16.1 LUFS / TP −2.5 dBFS**（契约 −16±1 / ≤ −1.5 ✓） |
| attribution | 21 镜 1:1 | **21 镜 1:1（sha 0 处不符）** |
| 旧成片文件 | — | **sha256 未变**（`3f3f0c01…`，append-only 保留） |

**未改动项（逐字节/逐条复核）**：`topic_output`、`script_output`、`claims_map`、`editing_plan_output`、`structure_output`、
`research_output`、`voice_output`、`subtitle` 产物的文件 sha256 全同（before/after 快照）；
claims **136 VERIFIED 且 claim_id 全同**；decisions **125 条**（`human` 104 + `human:operator` 21）与 `node` 分布全同，
其中 **21 条 `selection_override` 人工选材决策逐一未变**。

**如实披露（操作副作用）**：`redo` + `run` 时调度器先拾取了**陈旧 PENDING 分支 v5**（`t_a881aee95cf3`，历史错误
`ASSET_INSUFFICIENT`），使其转为 SUCCEEDED 并**覆盖了该路径上先前的孤儿文件**（82,655,278 B → 48,856,295 B；该文件此前
不对应任何成功产物）；随后才执行目标 v8。此项已记入证据包 `snapshots.films_changed`。另：v3 仍为 BLOCKED（历史分支，未动）。

---

## 6. 新基线（item 9：门禁通过才冻结）

| 项 | 值 |
|---|---|
| tag | `5.x-post-final-maintenance-baseline-r2` |
| ZIP | `docs/regression_2x/baseline/5.x-post-final-maintenance-baseline-r2.zip`，sha256 `2adc09c4092352f3c13af7b000db04b11e5ae34c96eb8389549ad7e3bcfb64e7` |
| 文件数 / 源码字节 | **387** / 8,369,624（= r1 的 385 + `config/config.mock.json` + `tests/offline_mock_test.py`） |
| manifest / 校验 | `baseline_manifest_5.x-post-final-maintenance-baseline-r2.json`；`verify_baseline` → **MATCH（missing 0 / drifted 0）** |
| 快照 | `snapshots/5.x-post-final-maintenance-20260921-r2.{zip,db,json}`（DB 38,014,976 B / sha256 `a9583f27…`） |
| 门禁（`phase5l_freeze_r2.py`） | G1 电池 25/25 ✓、G2 日志恢复 ✓、G3 批次 24/24 ✓、G4 套件 48/48 ✓、G5 针对性 28/28+23/23 ✓、G6 旧 Final sha 未变 ✓ |
| **一次性重冻说明** | 首次冻结 sha `eea8d4110eaabd476b43db2bf38be9fe5a9ca3421e9c72946bf1d3c544ed65c9`（387 文件）；随后补写 `CHANGELOG.md` 的 5-L 条目 → **按同一门禁重冻**为 `2adc09c4…`（当前有效值）。两个 sha 均已记录，最终以 `2adc09c4…` 为准 |
| 不覆盖 | r1（`b24023647f26…`，385 文件）与 `5.x-final-baseline`（`be1717b9…`，384 文件）**均未被改写** |

---

## 7. 遗留与未处理（如实登记）

1. **provenance 四件套**（悬空候选引用 13、陈旧 `external/.index.json` 11、素材编辑一等溯源、邮票 sha 不明变化）**按授权未处理**；
   登记保持 `docs/KNOWN_ISSUES.md` §18 **#52–#64**（未新增、未改写）。
2. **`phase2e_real_provider`** 本轮通过，但 Wikimedia 直连 TLS 的历史 `PENDING（环境）` 记录**未改写**（环境属性不变）。
3. **#57 的既有产物**：v7（短 21 s）作为历史版本**保留**；v8 为修正版。是否把 v8 提升为"发布候选/替换 v7"属**产品决策**，5-L 未做。
4. **v5 分支副作用**（§5 披露）：调度器拾取陈旧 PENDING 分支并覆盖孤儿文件；如需彻底清理陈旧分支，需新的运维授权。
5. **r1 基线** 相对当前工作树已 `DIFF`（4 处：`STATUS.md` + 3 个测试文件；另有 2 个新增文件），属**预期**：r1 是 5-K 检查点，
   5-L 成果由 **r2** 承载。

---

## 8. 本阶段产物清单

- 产品/配置：`config/config.mock.json`（新；**生产默认 `config/config.json` 未改**）
- 测试：`tests/offline_mock_test.py`（新，23/23）、`tests/cost_accounting_test.py`、`tests/pipeline_mock.py`、`tests/metrics_test.py`
- 文档：`STATUS.md`、`CHANGELOG.md`（5-L 条目）、`docs/KNOWN_ISSUES.md`（未改）、`docs/regression_2x/{PHASE5K_REPORT.md §9, BASELINE_README.md, PHASE5L_REPORT.md, PHASE5L_CHECKPOINT.md}`
- 脚本（docs）：`phase5l_{recon,snapshot,verify_render,battery,make_mock_config,evidence,freeze_r2}.py`
- 证据（`docs/regression_2x/logs/`）：`phase5l_evidence.json`（汇总）、`phase5l_targeted_suites.txt`、
  `phase5l_render_verify.json`、`phase5l_snapshot_{before,after}.json`、`phase5l_regression_summary.json`、
  `phase5l_rerun/**`（本轮 25 步结果留档）、`phase5l_freeze_gate.json`、`phase5l_battery_stdout.txt`
- 基线/快照：`baseline/5.x-post-final-maintenance-baseline-r2.zip` + manifest + `baseline_status_…-r2.json`；
  `snapshots/5.x-post-final-maintenance-20260921-r2.{zip,db,json}`
- 项目数据（`p_96efdc03e1aa`）：render v8 产物（`a_7242524b2f86` + `a_d15217b4a474`）、新成片
  `t_30070f93a77e_draft.mp4`、`credits_t_30070f93a77e.txt`；v1–v7 全部保留
