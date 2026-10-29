# 4.x Phase 4-E 完成与交接（2026-09-16）

> **状态：4-E 检索质量量化已完成并冻结基线**。结论看 `PHASE4E_REPORT.md`，进度看 `STATUS.md`。
> **只做量化，不做自动改选材；未进入 4-F。**

## 0. 一句话结论

在**不改默认行为**的前提下，建立了**固定测试集 + 中文/多语言 A/B 基准**，用 TP/FP/UNKNOWN/FN 指标
量化出既有检索的真实缺陷（字符级假匹配 + 中文无桥），并给出可选的 v2 改进：
域命中 0.6875 → **1.0**、FP 39 → 18、无结果假匹配 4 → **0**，同时证明改进**不绕过**许可门禁、素材校验与 4-B。

## 1. 冻结产物（可直接引用）

| 项 | 值 |
|---|---|
| 前置基线 | `4.x-phase4d-baseline.zip` sha256 `f2c783d493a9cb9fe0e2b1601e22a9eaa117d07a2ef885103e0fd2b2d0a51641` |
| **新基线** | `4.x-phase4e-baseline`：355 文件 / 7,684,598 字节 / zip sha256 `275f9a1aa5f4f2f493df10dabcbfd544438146d40679ff47951433d90eb0f55b`（`verify_baseline.py` **MATCH**） |
| manifest | `baseline/baseline_manifest_4.x-phase4e-baseline.json` |
| 快照（非基线） | `snapshots/4.x-phase4e-20260916.{zip,db,json}`（DB sha256 `d0539635690bb4b9…`） |
| 固定测试集 | `tests/retrieval_bench_v1.json`（sha256 `73fc61d47b044d68…`；**入基线**，改它必须新建 v2） |
| A/B 结果 | `logs/phase4e_ab_results.json`（含指标定义 + 逐查询逐候选明细）、`logs/phase4e_ab_summary.txt` |
| 真实网络探针 | `logs/phase4e_network_probe.json`（中文查询 0 → 8 候选；`status=OK`，仅记录） |
| 变更清单 | `logs/phase4e_change_list.json`（代码 修改 1 / 新增 4 / 删除 0） |

## 2. 交接要点（明天继续时先看这里）

1. **A/B 数值已冻结为断言**（`tests/retrieval_quality_test.py` C2/C3/C4/C5/D1–D6）：想改测试集/词典必须新建
   `retrieval_bench_v2` + 新词典版本，并**同时给出两侧结果**，不许就地改数凑绿。
2. **不要**把 `tools.retrieval.scoring` 默认改成 `v2`（授权要求默认不变；4-D 的 `supply_cache` 同理默认关闭）。
3. **词典 ≠ 语义判定**：检索层只给"候选质量"；`core/semantics.py`（4-B）与许可门禁是唯一判定入口，
   4-B 真值仍钉 `a_2ed5f41d6b58`，词表 `semantics_v1.json` sha256 前缀 `083e8d55c9899706`（本阶段未动）。
4. 已知残余（**不要**当成 bug 顺手"修绿"）：域级同域泛化（量子计算机 → 通用 PC 图）、
   真实网络伪友（`prionace glauca` → `Picea glauca`）、`鲸鱼娘` 角色名 vs 鲸鱼语义。
5. 两项 Wikimedia 真实网络用例仍记 `PENDING（环境）`：本轮 29/29 与 13/13 通过（网络可用），
   **状态与期望值不得改写**。
6. 进入 4-F 或自动改选材：**需要新的授权**。

## 3. 复现命令（离线，约 2–4 分钟）

```powershell
cd C:\mp4agent\video-studio
C:\python3.13\python.exe tests\retrieval_quality_test.py                 # 35/35（含 A/B 冻结断言）
C:\python3.13\python.exe docs\regression_2x\phase4e_ab_benchmark.py      # A/B 完整结果 + 指标定义
C:\python3.13\python.exe docs\regression_2x\run_all_suites.py            # 39/39
C:\python3.13\python.exe docs\regression_2x\verify_baseline.py 4.x-phase4e-baseline
```
