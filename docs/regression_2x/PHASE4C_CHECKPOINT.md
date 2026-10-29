# 4.x Phase 4-C 完成与交接（2026-09-15 收工归档 → 已完成）

> **状态：4-C 已全部收尾完成**（替换真实完成 + 全部验收项通过 + 回归在最终代码上重跑 + 基线已冻结并零漂移校验）。
> 本文件保留为**交接与历史追溯**；结论看 `PHASE4C_REPORT.md`，进度看 `STATUS.md`。
> **未进入 4-D/4-E/4-F。**

## 00. 收尾修复补记（2026-09-16）：S05 连带 MISMATCH 已消除

4-C 首轮留下的**唯一未决项**（S05 因 `prefer_unused` 复用被释放的鲨鱼照而 `MISMATCH`）已在一次**收尾修复**中闭环：

- 路径：`run.py review` → 人工 `run.py select-candidate --scene S05 --asset asset_f3cf2b80432d --by human:project-owner --reason …`
  → `decisions d_a683da3c5d3b` + `changelog #820` → `run.py redo t_1dbf3c1bc6f7` → **render v5 `t_b8f866ddc062`**（v1–v4 append-only 保留）。
- 结果：语义 **`MATCH=6 / MISMATCH=0 / UNKNOWN=0`**；复用检查**仅 S05 变化**，鲨鱼素材 `asset_28160d959ed5` 已释放且无人接管，
  三个 VR 素材各用 2 镜；attribution ⟷ 时间轴 1:1；成片 104.000s / **-16.1 LUFS、TP -2.7 dBTP** /
  抽帧 6/6（S05 **0.355**，替换前在 v4 上为 0.729——**以本补记为准**）；3-A 16/16；3-B 32/32 + 12/12；37/37 套件 rc=0。
- **代码增量 0**（仅 `CHANGELOG.md`、`STATUS.md` 文档登记）；新基线 **`4.x-phase4c-fix-baseline`**
  zip sha256 `3b0e998e1c2e0de180b711b71242423ead90ecfca3f5e73e1bfe18078b6ad96e`（348 文件 / 7,543,538 字节，`verify_baseline.py` **MATCH**）；
  快照 `snapshots/4.x-phase4c-fix-20260916.{zip,db,json}`。
- 完整 7 项报告：`PHASE4C_FIX_REPORT.md`。**未进入 4-D/4-E/4-F。**

## 0. 收尾结果（原 §3 四步的完成情况）

| 步 | 结果 |
|---|---|
| ① 重跑完整回归批次（24 项）+ 判读 | ✅ **22/24 rc=0**；2 项真实网络用例 rc=1 → **`PENDING（环境）`（状态未改）**；证据 `logs/phase4c_batch_resume.txt`、`logs/phase3a_regression_batch_classified.json` |
| ② 重跑被中断的网络项 | ✅ 已运行：`phase2e_real_provider` rc=1（`PROVIDER_TIMEOUT`）、`phase2e_failure_paths` rc=1（超时）→ 均保持环境 PENDING；**跨时点观察**：本阶段两次收尾各出现过一次 29/29 通过（网络间歇恢复） |
| ③ 冻结 `4.x-phase4c-baseline` + 零漂移校验 | ✅ 348 文件 / 7,538,751 字节 / zip sha256 `08018d4e81d8c3df0a85953158bda1d86c02494237413f4b91b2b6d56f09171d`；`verify_baseline.py` → **MATCH**；snapshot `4.x-phase4c-20260916` |
| ④ 回填报告 §7/§9 与基线表 | ✅ 报告与 `BASELINE_README.md` 均已回填 |

**套件**：`run_all_suites.py` → **37 total / 37 rc=0 / FAILED: []**（含新增 `human_selection_test` 18/18）。

---

## 1. 已完成（可直接引用，无需重做）

| 项 | 结果 | 证据 |
|---|---|---|
| **真实人工替换（≥1 次，实际 2 次）** | S04 鲨鱼照 → `Visitor using a Meta Quest 3 VR headset…`；S06 鲨鱼照 → `Meta Quest 3 front View.jpg` | `logs/phase4c_evidence_summary.txt`、`logs/phase4c_replacement_relations.json` |
| 人工选择证据 | `decisions` `d_a74b1d9f5ab6`(S04) / `d_9a7600dfeebf`(S06)，`made_by=human:project-owner`，`state=approved` + 理由 | `logs/phase4c_human_decision_evidence.json` |
| redo / version+1 / append-only | `redo t_b7a62ec8e29a` → render **v4 `t_1dbf3c1bc6f7`**；v1–v3 任务与产物全部保留 | 同上（版本链表） |
| changelog | `#798` / `#799`，`human_confirmed=1`，`target_type=selection_override` | 同上 |
| attribution ⟷ 新时间轴 1:1 | **PASS**（台账 6 条 / 有素材镜头 6 个，scene_id+asset_id+sha256 逐条一致） | `logs/phase4c_new_film_evidence.json` |
| 新成片验证 | `t_1dbf3c1bc6f7_draft.mp4`：h264+aac、**104.000s**、响度 **-16.1 LUFS / TP -2.7 dBTP**、抽帧 **6/6 在屏 0 失败**（S04 corr 0.472、S06 0.919） | 同上 |
| 3-A 关键断言 | `phase3a_real_chain.py --resume p_f4b466a4a024` → **16/16 PASS**（对照系数 S01 0.459 / S02 0.921 / S03 0.348 / S04 0.472 / S05 0.729 / S06 0.919） | `logs/phase3a_real_chain.json` |
| 4-C 测试 | `tests/human_selection_test.py` → **18/18** | `logs/phase3a_human_selection.log` |
| 4-A/4-B 测试（已按新状态修好口径） | `tests/semantic_check_test.py` → **29/29**（真值钉在冻结产物 `a_2ed5f41d6b58`）；`tests/metrics_test.py` → **18/18**（M6b 改为跨模块一致性） | 同上目录 |
| 断点快照 | `snapshots/4.x-phase4c-wip-20260915.{zip,db,json}`：348 文件 / 7,538,536 字节 / zip sha256 `00f1e15a88a8bbc60bbaf6ecde324de1b84f7f2a158900f2f05fb6461474d02e`；DB sha256 `d0e1addc3d9447e4…`（11,292,672 B） | — |

## 2. 收工时的批次状态（如实记录）

被中断的批次（`logs/phase4c_batch_console.txt`，24 项）：**21 项 rc=0**，2 项 rc=1，1 项被中断。

| 项 | 当时结果 | 性质与后续处置 |
|---|---|---|
| `semantic_check` | rc=1（25/28，C1 真值表失败） | **测试期望过期**（真值表原本读"最新成片"，而 4-C 已把 S04/S06 修好）→ **已修**：真值**钉在 3-A 冻结产物 `a_2ed5f41d6b58`**（append-only 保证仍在），并新增 C0 断言"载体是冻结产物"；单独复测 **29/29** |
| `metrics_readonly` | rc=1（17/18，M6b 失败） | **测试硬编码**了替换前的 `MISMATCH=S04,S06` → **已修**：M6b 改为**跨模块一致性**（metrics ⟷ `semantic_report` 逐项相等）；单独复测 **18/18**，如实显示替换后 `MATCH=5 / MISMATCH=1 / S05` |
| `suite_all` | rc=0，**FAILED: []** | 该项在测试修复**之后**运行 → 全部套件通过（含修好的 4-A/4-B/4-C 套件） |
| `phase2e_failure_paths` | rc=0，**29/29** | **本轮网络恢复**（17 分钟后仍为环境波动）——**按授权仍记 `PENDING（环境）`，未改状态**，仅记录此观察 |
| `phase2e_real_provider` | **被中断**（未运行完） | 待次日重跑 |
| 其余 20 项 | 全 rc=0（provider 46/46、taxonomy 40/40、attribution 24/24、audio 32/32、3-B 失败路径 12/12、report 18/18、human_selection 18/18、cost_boundary、narration 40/40、2-C 38/38、2-C 故障矩阵、2-D 40/40、2-D provider 12/12、ingest PASS、E2E A/B/C SETTLED、real_small PASS、check_binaries PASS、2-A/B 验收 PASS、3-A run1 复核 PASS） | — |

## 3. 次日续做步骤（按顺序，约 15–20 分钟）

```bat
cd C:\mp4agent\video-studio

:: 1) 在最终代码上重跑完整回归批次（24 项），并做分类判读
python docs\regression_2x\phase3a_regression_batch.py
python docs\regression_2x\phase3a_classify_batch.py

:: 2) 单独确认被中断的网络项（网络可用时应 13/13；不可用则如实记 PENDING（环境））
python docs\regression_2x\phase2e_real_provider.py

:: 3) 冻结 4-C 基线并做零漂移校验
python docs\regression_2x\make_baseline.py 4.x-phase4c-baseline --no-docs
python docs\regression_2x\rebuild_manifests.py
python docs\regression_2x\verify_baseline.py 4.x-phase4c-baseline      :: 必须 MATCH
python docs\regression_2x\make_snapshot.py 4.x-phase4c-20260916

:: 4) 回填文档（这三个是 docs/ 内、不入包，可在冻结后写）
::    PHASE4C_REPORT.md §7 回归、§9 新基线；BASELINE_README.md 增加 4.x-phase4c-baseline 行
```

## 4. 纪律提醒（次日不要越界）

- **2 项 Wikimedia 网络回归保持 `PENDING（环境）`**：不得改写状态、不得修改其期望值；
  `phase2e_failure_paths` 本轮虽 29/29，仍按授权保留 PENDING 登记，等待用户确认后再改。
- **S05 的连带效应不得自动修复**：`prefer_unused` 把被释放的鲨鱼照路由给了 S05（`MISMATCH` 转移到 S05）。
  修法只能是**人工再下一次决定**（`run.py review` → `run.py select-candidate … --scene S05 …` → `run.py redo <render_task>`）；
  **不得**自动改选材、不得改 4-A/4-B 判定逻辑、不得改复用策略来"凑绿"。
- 不接第二 Provider、不做 BGM/UI/节奏自动改时长/Git tag、不改数据库结构、不改任何冻结契约。
- 真值表**钉在冻结产物**（`a_2ed5f41d6b58`）；任何时候都**不得**把真值改成与新状态一致来"凑通过"。

## 5. 归档清单

| 归档 | 路径 | 指纹 |
|---|---|---|
| 断点快照（工作树） | `docs/regression_2x/snapshots/4.x-phase4c-wip-20260915.zip` | sha256 `00f1e15a88a8bbc60bbaf6ecde324de1b84f7f2a158900f2f05fb6461474d02e`（348 文件 / 7,538,536 B） |
| 断点快照（项目 DB） | `docs/regression_2x/snapshots/4.x-phase4c-wip-20260915.db` | sha256 `d0e1addc3d9447e4be8b662f4449ec4d39dd406b7f5f1f0fca3ebdb1c36b2602`（11,292,672 B） |
| 上一冻结基线（未动） | `docs/regression_2x/baseline/4.x-phase4ab-baseline.zip` | sha256 `3a7eb41a04d9043bbdb68bc4a7ad817874df152353e16d53d214415ecc90191f` |
| 4-C 证据 | `docs/regression_2x/logs/phase4c_*` | 关系/人工决定/新成片/语义复核/汇总 |
| 4-C 报告 | `docs/regression_2x/PHASE4C_REPORT.md` | §7/§9 待回填 |
| 批次日志（被中断那次） | `docs/regression_2x/logs/phase4c_batch_console.txt` | 21 项 rc=0 + 2 项过期期望（已修） + 1 项中断 |

## 6. 已知问题（状态不变，不得改写）

1. **S05 新增 `MISMATCH`**（复用策略连带效应，未自动处理）。
2. 候选池规模受限（本项目 6 个候选因 `ASSET_OVERSIZE`/`PROVIDER_RATE_LIMITED` 被拒不可选）；池空/全不合规时
   机制 fail-closed（测试 H3/H5 覆盖）。
3. `--by` 为自填标识（无强身份认证）；同镜头多条决定以最新一条生效（旧的 append-only 保留）。
4. 4-A/4-B 既有已知限制不变（真值样本 n=6、知识库覆盖有限、`keyboard` 等同形词未收录、未实现 LLM 判定、
   判定结果不落库）。
5. 3.x 已知问题 13 项状态不变（`docs/KNOWN_ISSUES.md`）。
6. 2 项 Wikimedia 网络回归 `PENDING（环境）`（本轮 `phase2e_failure_paths` 已通过 29/29，状态按授权不改）。
