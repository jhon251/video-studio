# 5-K 断点卡（Post-Final Maintenance）

- 日期: 2026-09-21
- 阶段状态: **十项授权动作已全部执行完毕并停止（⑩ STOP）**
- 授权基线: `5.x-final-baseline`（sha256 `be1717b9c7fe9ed9124be3876db64b5893915a4d0ffad56bd37eded5e6e2141e`）—— **未被改写**
- 新基线: `5.x-post-final-maintenance-baseline`（sha256 `b24023647f263f3f300f6de8af23b4ae532f4d4d769e7a117b68046f6eb48c14`，385 文件，**MATCH**）
- 详细报告: `docs/regression_2x/PHASE5K_REPORT.md`

## 1. 判定总览

| 项 | 内容 | 判定 |
|---|---|---|
| ① | 采纳 `-framerate 1` 图片输入（**并修正缺陷**） | **PASS** |
| ② | 采纳 ffmpeg 超时 1800→7200 s（两处） | **PASS** |
| ③ | 采用当前官方 DeepSeek 默认配置 | **PASS**（副作用见 ⑧） |
| ④ | 针对性回归 + 视频路径反证 | **PASS**（新增套件 28/28） |
| ⑤ | CHANGELOG 补齐 + 时序修复 | **PASS** |
| ⑥ | 杂物清理（`.bak` 隔离留痕） | **PASS** |
| ⑦ | 审计发现只登记不修复 | **PASS**（KNOWN_ISSUES #52–#64） |
| ⑧ | 针对性 + 全量回归 + 基线校验 | **FAILED（未全绿）**：批次 21/24、套件 44/47、e2e 结果退化；红项根因 = item ③ 配置副作用 / 环境网络 |
| ⑨ | 产出新基线（不覆盖旧 Final） | **PASS**（MATCH；旧 Final 哈希未变；状态文件标注 NOT_ALL_GREEN） |
| ⑩ | 停止并只报 PASS/PENDING/FAILED | **PASS** |

## 2. 断点（若下一会话继续）

1. **先决策 §7 的 5 件事**（尤其 #1：`llm.mock` 去留 → 决定 3 个套件 + 1 个批次项是否可恢复为绿）。
2. 若决定修：`config/config.json` 恢复**仅供离线**的 `llm.mock`（不动真实默认模型）**或** 让 `docs/regression_2x/run_ingest_test.py`
   等离线脚本自带 mock；并把 `tests/metrics_test.py` M5d 重钉到新基线 tag。
3. 修完后：重跑 `docs/regression_2x/phase3a_regression_batch.py` + `run_all_suites.py` +
   `docs/regression_2x/phase5k_battery_readonly.py`，再 `verify_baseline.py 5.x-post-final-maintenance-baseline`，
   **重新冻结**（覆盖本 tag 或另起 `…-baseline-r2`），并更新 `baseline_status_*.json`。
4. **不要**重跑 `docs/regression_2x/phase3a_real_chain.py`（会改写 5 份冻结证据日志；本阶段已用回拷机制处理过一次）。
5. 回归前请先冻结日志：`python docs/regression_2x/phase5k_freeze_logs.py`；回归后
   `python docs/regression_2x/phase5k_preserve_and_restore.py`（留档 + 恢复冻结证据，已实测 drift 0）。

## 3. 关键证据索引

- 证据汇总：`docs/regression_2x/logs/phase5k_evidence.json`
- 针对性套件输出：`docs/regression_2x/logs/phase5k_targeted_regression.txt`（28/28）
- 本轮批次留档：`docs/regression_2x/logs/phase5k_batch_logs/`（含 `phase3a_regression_batch.json`、`suites_summary.json`）
- 成片探针：`docs/regression_2x/logs/audit_p96efdc_film_check.json`（视频轨 1511.0 s vs 时间轴 1532.0 s）
- 停点诊断：`docs/regression_2x/logs/phase5k_ingest_diag{,2}.json`（4 条 UNSUPPORTED claim / 11 个未派发生产任务）
- 成本：`docs/regression_2x/logs/phase5k_cost_probe.json`（当日回归真实计费 $0.23852）
- 基线状态：`docs/regression_2x/baseline/baseline_status_5.x-post-final-maintenance-baseline.json`（NOT_ALL_GREEN）
