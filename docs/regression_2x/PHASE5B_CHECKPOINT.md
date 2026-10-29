# 5.x Phase 5-B 完成与交接（2026-09-16）

> **状态：5-B 多模态证据增强 + 人审候选闭环已完成并冻结基线**。结论看 `PHASE5B_REPORT.md`，进度看 `STATUS.md`。
> **只生成候选；未自动替换；未进入 5-C。**

## 0. 一句话结论

在 5-A 的三态判定之上，为 **MISMATCH/低置信**镜头生成**可解释候选**（含同一 CLIP 模型给出的**视觉相似度**、
来源、许可、旁白关联与风险）；真实 S04/S06 产出合格候选且**包含 4-C 历史人工选定素材**；
**生产状态一字未改**（不写库/不写产物/不触发 redo），人工确认仍只走 4-C `select-candidate` + 人工 `redo`。

## 1. 冻结产物（可直接引用）

| 项 | 值 |
|---|---|
| 前置基线 | `5.x-phase5a-baseline.zip` sha256 `1f6bb1062dc7a49570cc298992fd6d99a5579cf387c53c9b0d2aa8c1d8232bac`（授权书写作 `svg5.x-…`，文件名笔误已登记） |
| **新基线** | `5.x-phase5b-baseline`：367 文件 / 7,946,132 字节 / zip sha256 `dee0e33cad31418bb04fd76ae9d6d62d394cdd1741e22b8ba7ef31e9a39ab67e`（`verify_baseline.py` **MATCH**） |
| manifest | `baseline/baseline_manifest_5.x-phase5b-baseline.json` |
| 快照（非基线） | `snapshots/5.x-phase5b-20260916.{zip,db,json}`（DB sha256 `9b6321d25ce6ec2a…`） |
| 证据 | `logs/phase5b_candidates_evidence.json`、`logs/phase5b_evidence_summary.txt` |
| 变更清单 | `logs/phase5b_change_list.json`（代码 修改 1 / 新增 3 / 删除 0） |

## 2. 交接要点（继续时先看这里）

1. **候选层永远只读**：`ops/mm_candidates.py` 只能走 `readonly_connection`；不得加入 `record_selection(...)`/
   `select_candidate(...)`/`redo(...)`/写库/调度器调用（`tests/mm_candidates_test.py` G3 按**调用形式**静态检查）。
2. **唯一写入口是 4-C**：`run.py select-candidate`（人工确认，写既有 decisions/changelog）+ 人工 `run.py redo`
   （append-only + version+1）。5-B **没有**新增写入路径，也没有调用它们。
3. **排序≠决定**：候选按视觉相似度降序；真实案例排序第一为 `side`（0.2886），而 4-C 时人选择的是 `Visitor`/`front`
   —— 三者都在候选内，选择权在人工（`KNOWN_ISSUES.md` #27）。
4. **阈值**：`min_visual_sim=0.22`、`max_candidates=3`、`require_license_clear=true`（可配、非法值回退，不放松）；
   改动会改变候选集合，须同步报告/证据/测试。
5. **fail-closed 优先**：模型不可用 → `UNKNOWN/MMC_MM_UNAVAILABLE`（先于"期望域推不出"判断）；空池 →
   `BLOCKED/MMC_NO_CANDIDATES`；许可不合格 → `BLOCKED/MMC_NO_LICENSED_CANDIDATE`。
6. 既有阶段默认值均未变（BGM 关闭、检索 v2 关闭、供给缓存关闭、多模态/候选默认关闭）；`provider=none` 仍为默认。
7. 两项 Wikimedia 真实网络用例仍记 `PENDING（环境）`（本轮通过仅作记录，**状态不得改写**）。
8. 进入 5-C（自动换材/自动执行）或任何自动改片能力：**需要新的授权**。

## 3. 复现命令（离线，约 1–3 分钟）

```powershell
cd C:\mp4agent\video-studio
C:\python3.13\python.exe run.py mm-review p_f4b466a4a024 --artifact a_2ed5f41d6b58   # 真实 S04/S06 候选
C:\python3.13\python.exe tests\mm_candidates_test.py                                 # 29/29
C:\python3.13\python.exe docs\regression_2x\phase5b_evidence.py                       # 证据（三路径 + 交叉核对）
C:\python3.13\python.exe docs\regression_2x\run_all_suites.py                         # 43/43
C:\python3.13\python.exe docs\regression_2x\verify_baseline.py 5.x-phase5b-baseline
```
