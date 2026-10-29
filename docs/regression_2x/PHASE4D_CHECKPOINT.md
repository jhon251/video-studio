# 4.x Phase 4-D 完成与交接（2026-09-16）

> **状态：4-D 供给韧性底座已完成并冻结基线**。结论看 `PHASE4D_REPORT.md`，进度看 `STATUS.md`。
> **未进入 4-E/4-F。**

## 0. 一句话结论

在**不改默认行为、不改数据库结构、不接第二 Provider**的前提下，给外部素材供给加了
"失败分类 + 有界重试 + 搜索层缓存（默认关闭）+ 可控降级 + 可解释报告"，
并用 8 条路径 + 引擎级故障注入证明**失败一律 fail-closed 且不污染既有产物/台账/版本链**。

## 1. 冻结产物（可直接引用）

| 项 | 值 |
|---|---|
| 唯一前置基线 | `4.x-phase4c-fix-baseline.zip` sha256 `3b0e998e1c2e0de180b711b71242423ead90ecfca3f5e73e1bfe18078b6ad96e` |
| **新基线** | `4.x-phase4d-baseline`：351 文件 / 7,622,277 字节 / zip sha256 `f2c783d493a9cb9fe0e2b1601e22a9eaa117d07a2ef885103e0fd2b2d0a51641`（`verify_baseline.py` **MATCH**） |
| manifest | `baseline/baseline_manifest_4.x-phase4d-baseline.json` |
| 快照（非基线） | `snapshots/4.x-phase4d-20260916.{zip,db,json}`（DB sha256 `f903b106ad6212b2…`，13,021,184 字节） |
| 变更清单 | `logs/phase4d_change_list.json`（代码 修改 2 / 新增 3 / 删除 0） |
| 证据 | `logs/phase4d_taxonomy.json`、`phase4d_retry_plan.json`、`phase4d_cache.json`、`phase4d_paths.json`、`phase4d_failclosed.json`、`phase4d_evidence_summary.txt` |

## 2. 新增/修改（5 个代码文件）

- **新** `src/video_studio/core/supply.py`：失败分类表（32 码）、`retry_decision()`、`SupplyCache`、
  `degradation_plan()`、`SupplyDiagnostics`、`summarize()`。
- **新** `src/video_studio/tools/supply.py`：`ResilientSupply`（`search`/`fetch`/`report`/`verified_only`/
  `degradation_facts`）、`candidate_metadata`/`candidate_from_metadata`。
- **新** `tests/supply_resilience_test.py`：55 项（A 分类 / B 重试 / C 缓存 / D 八路径 / E 阶梯 / F 引擎级 fail-closed / G 默认不变）。
- 改 `src/video_studio/tools/material_provider.py`：`TransportError.retry_after_s`、429 `Retry-After`（≤30s）、
  下载重试统一走 `core.supply`、3 个加法策略键。
- 改 `src/video_studio/agents/retrieval/agent.py`：外部候选层包 façade；产物加 `supply` / `supply_report`。

## 3. 交接要点（明天继续时先看这里）

1. **不要**把 `supply_cache` 默认改成 `true`（会改变外部 provider 的请求模式；授权要求最小增量且默认不变）。
2. **不要**因为"缓存命中"就跳过下载/校验/许可门禁——`candidate_from_metadata()` 会把候选重置为未验证，
   这是安全不变量，`tests/supply_resilience_test.py::D3` 已固定。
3. 429 的 `retries` 计数沿用 2-D/2-E 语义（含最后一次未执行的计划重试）；**不要在 4-D 里顺手改它**。
4. 4-B 真值表仍钉在 `a_2ed5f41d6b58`；4-C 的版本链当前是 **v5 `t_b8f866ddc062`**；这两处都**不许**为了别的阶段改动。
5. 两项 Wikimedia 真实网络用例仍记 `PENDING（环境）`：本轮实测 29/29 与 13/13 通过（网络可用），
   但**状态与期望值不得改写**。
6. 若要进入 4-E 或接入第二 Provider：**需要新的授权**；第二 Provider 必须独立抽象、默认关闭，
   并过素材验证 + 许可验证 + attribution 验证三重门。

## 4. 复现命令（离线，约 3–5 分钟）

```powershell
cd C:\mp4agent\video-studio
C:\python3.13\python.exe tests\supply_resilience_test.py            # 4-D 单测 55/55
C:\python3.13\python.exe docs\regression_2x\phase4d_evidence.py      # 证据（八路径 + 不污染）
C:\python3.13\python.exe docs\regression_2x\run_all_suites.py        # 38/38
C:\python3.13\python.exe docs\regression_2x\verify_baseline.py 4.x-phase4d-baseline
```
