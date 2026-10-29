# 5-L 断点卡（5-K 已确认失败项修复）

- 日期: 2026-09-21
- 阶段状态: **PASS —— 全部必要电池达到 DoD，已停止（item 11 STOP）**
- 授权基线: `5.x-post-final-maintenance-baseline`（r1，sha256 `b24023647f26…`）
- 新基线: `5.x-post-final-maintenance-baseline-r2`（sha256 `2adc09c4092352f3c13af7b000db04b11e5ae34c96eb8389549ad7e3bcfb64e7`，387 文件，**MATCH**）
- 旧终稿: `5.x-final-baseline` sha256 `be1717b9c7fe9ed9124be3876db64b5893915a4d0ffad56bd37eded5e6e2141e` —— **未变**
- 详细报告: `docs/regression_2x/PHASE5L_REPORT.md`

## 1. 判定总览（授权 11 项，全部 PASS）

| # | 项 | 判定 |
|---|---|---|
| 1 | 生产默认保留真实 DeepSeek | PASS |
| 2 | 独立离线 mock 能力 + 离线测试显式使用 | PASS |
| 3 | 禁止把 mock 作为生产默认 | PASS（新增 23/23 守卫） |
| 4 | M5d 重钉当前有效基线（测试契约更新） | PASS（18/18） |
| 5 | `p_96efdc03e1aa` 重渲染消除视频轨少 21 s | PASS（1511.0 → 1531.96 s） |
| 6 | 不处理 provenance，仅保留 #52–#64 | PASS（未新增/未改写） |
| 7 | 历史报告与 STATUS.md 事实口径修正 | PASS（未改写历史数字） |
| 8 | 重跑针对性/全量/E2E/baseline verify | PASS |
| 9 | 达 DoD 才 PASS；不强行冻结为全绿 | PASS（门禁 G1–G6 全通过才冻结） |
| 10 | 旧 `5.x-final-baseline` SHA 不变 | PASS |
| 11 | 完成即 STOP | PASS |

**DoD 实测**：电池 **25/25 步 rc=0**、批次 **24/24**、套件 **48/48 rc=0**、E2E **3/3 SETTLED**、
`run_ingest_test` **PASS**、`phase2e_real_provider` **13/13**、针对性 **28/28 + 23/23**、冻结证据日志 **drift 0**。

## 2. 断点（若下一会话继续）

1. **无需修正动作**；如需推进，先读 `PHASE5L_REPORT.md` §7（遗留：provenance 四件套按授权未做；
   `PENDING（环境）` 未改写；v7/v8 哪个作为发布候选属产品决策；陈旧 PENDING 分支 v5 的清理需运维授权）。
2. **回归纪律**（本阶段已验证的流程）：
   - 冻结日志：`python docs/regression_2x/phase5k_freeze_logs.py`（如需另建 5-L 命名可仿 `phase5l_battery.py`）
   - 全量电池（25 步、路径适配、AST 比对步骤表）：`python docs/regression_2x/phase5l_battery.py`
   - 证据包：`python docs/regression_2x/phase5l_evidence.py`
   - 冻结（带门禁，未全绿会 exit 3 且不写基线）：`python docs/regression_2x/phase5l_freeze_r2.py`
3. **不要**重跑 `docs/regression_2x/phase3a_real_chain.py` 单独作为回归（电池已含；单独跑会改写 5 份冻结证据日志）。
4. 若再改任何基线内文件（`src/ config/ tests/ scripts/` 或根 `CHANGELOG.md`/`STATUS.md`），
   **必须重新冻结**（r2 会转 DIFF），且**不得**覆盖 r1 与 `5.x-final-baseline`。

## 3. 关键证据索引

- 证据汇总：`docs/regression_2x/logs/phase5l_evidence.json`
- 电池 summary：`docs/regression_2x/logs/phase5l_regression_summary.json`（25 步 rc、日志恢复）
- 本轮批次/套件/验证：`docs/regression_2x/logs/phase5l_rerun/`（含 `phase3a_regression_batch.json`、`suites_summary.json`、
  `phase3a_e2e_mechanical.log`（3/3 SETTLED）、`phase3a_run_ingest_test.log`（PASS）、`suite_cost_accounting_test.log`（20/20））
- 重渲染验收：`docs/regression_2x/logs/phase5l_render_verify.json`（1511.0 → 1531.96 s、−16.1 LUFS / TP −2.5 dBFS、
  内容/claim/决策未变、attribution 21/21）
- 前后快照：`docs/regression_2x/logs/phase5l_snapshot_{before,after}.json`
- 门禁与基线状态：`docs/regression_2x/logs/phase5l_freeze_gate.json`、
  `docs/regression_2x/baseline/baseline_status_5.x-post-final-maintenance-baseline-r2.json`
- 离线 mock 配置：`config/config.mock.json`（`_offline` 块含来源与不变式）；守卫套件 `tests/offline_mock_test.py`
