# 4.x Phase 4-G 完成与交接（2026-09-16）

> **状态：4-G 只读节奏分析与人工建议已完成并冻结基线**。结论看 `PHASE4G_REPORT.md`，进度看 `STATUS.md`。
> **只读、不改任何生产数据；未进入 5.x。**

## 0. 一句话结论

新增一条**只读**命令 `run.py rhythm <pid>`：读既有 `render_output`/`voice_output`，按 10 条机械规则
给出**建议 + 依据 + 置信度**（无法判断时只记 UNKNOWN），**不写库、不写产物、不改时间轴/时长/旁白/素材/BGM、
不触发 redo、不绕过 HITL**；同输入同配置输出逐字节一致。

## 1. 冻结产物（可直接引用）

| 项 | 值 |
|---|---|
| 前置基线 | `4.x-phase4f-baseline.zip` sha256 `214374a1d14a6daf2729c7a8df63056bb8562dcaa4fa5e27e4e5d7cd59f45a23` |
| **新基线** | `4.x-phase4g-baseline`：360 文件 / 7,819,574 字节 / zip sha256 `1daf93a1a3971ae5b0c22b57b1fe81a23a878d763c543ea801aabd02adf013c3`（`verify_baseline.py` **MATCH**） |
| manifest | `baseline/baseline_manifest_4.x-phase4g-baseline.json` |
| 快照（非基线） | `snapshots/4.x-phase4g-20260916.{zip,db,json}`（DB sha256 `c030950486ef66d9…`） |
| 证据 | `logs/phase4g_rhythm_evidence.json`、`logs/phase4g_evidence_summary.txt` |
| 变更清单 | `logs/phase4g_change_list.json`（代码 修改 1 / 新增 3 / 删除 0） |
| 报告 | `PHASE4G_REPORT.md` |

## 2. 交接要点（继续时先看这里）

1. **建议器必须保持只读**：`ops/rhythm.py` 只能走 `readonly_connection`；**不要**给它加写库/写产物/派发任务的能力
   （`tests/rhythm_advisor_test.py` K5 会做静态检查：无写库 SQL、无 `write_artifact`/`set_task_status`/`run_cycle`/
   `build_engine`/`subprocess`/redo 调用）。
2. **建议 ≠ 变更**：所有建议必须 `status="SUGGESTION"`、`applied=false`、`executed=false`，报告级 `applied_changes=0`；
   文本输出必须标注『建议·未执行』且不得出现"已执行/已应用/已修改/已生效"字样（K4 断言）。
3. **UNKNOWN 不许强行变建议**：时长/旁白/素材类型/成片时长缺失时进入 `unknowns[]`（G1–G3、H1 断言）。
4. **阈值改动会改变建议集合**：`tools.rhythm` 覆盖默认（3/20/15s、2/12 cuts/min、0.5s、4/30s、2）；
   改阈值须同步更新 `PHASE4G_REPORT.md` 与证据 JSON。
5. **旁白窗口口径**与 4-F ducking 一致（逐段真实时长累加）；末段被时间轴契约裁剪时，
   `R_CUT_MID_NARRATION` 与 `R_NARRATION_TRIMMED` 可能同时出现（本片即如此，已如实记录）。
6. 4-B 真值仍钉 `a_2ed5f41d6b58`；4-C 版本链当前 **v5 `t_b8f866ddc062`**；4-D/4-E/4-F 的开关默认值均未变。
7. 两项 Wikimedia 真实网络用例仍记 `PENDING（环境）`（本轮实测通过，**状态不得改写**）。
8. 进入 5.x 或任何自动改片能力：**需要新的授权**。

## 3. 复现命令（离线，约 1–3 分钟）

```powershell
cd C:\mp4agent\video-studio
C:\python3.13\python.exe run.py rhythm p_f4b466a4a024            # 只读建议（人读）
C:\python3.13\python.exe tests\rhythm_advisor_test.py            # 34/34（含只读与确定性证明）
C:\python3.13\python.exe docs\regression_2x\phase4g_evidence.py   # 证据（场景矩阵 + 只读证明）
C:\python3.13\python.exe docs\regression_2x\run_all_suites.py     # 41/41
C:\python3.13\python.exe docs\regression_2x\verify_baseline.py 4.x-phase4g-baseline
```
