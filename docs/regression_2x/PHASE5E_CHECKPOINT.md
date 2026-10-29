# 5.x Phase 5-E 断点卡（CHECKPOINT）— 2026-09-17 **已结项**

> 授权（逐字遵守）：只做 5-E，**完成后 STOP，不进入 5-F/Final**；不得把未完成项写成 PASS；
> 不得放宽任何冻结规则；**禁止为提高通过率调阈值**；每一项 PASS 必须有证据路径。

## 0. 状态

| 项 | 结果 |
|---|---|
| 阶段判定 | **PASS**（含 §1 如实登记的限制 #43–#48） |
| 报告 | `docs/regression_2x/PHASE5E_REPORT.md` |
| 授权基线（起点） | `5.x-phase5d-baseline.zip` sha256 `cab3324bad69bb56…`（与授权书逐字节一致、ZIP 自洽） |
| **新基线（当前基准）** | `baseline/5.x-phase5e-baseline.zip` sha256 **`3934369a7f62e14ca93a08b58c24b898345e5f03ee0fe2d46a875fef5f4f2b57`**（374 文件 / 8,140,706 B / 6,095,381 B zip）；`verify_baseline.py` → **MATCH** |
| 相对 5-D 的 delta | **修改 3 / 新增 4 / 删除 0**（修改：`CHANGELOG.md`、`STATUS.md`、`cli.py`；新增：`core/mm_quality.py`、`ops/mm_quality.py`、`tests/fixtures/mm_truth_set_v1.json`、`tests/mm_quality_test.py`） |
| 冻结真值集 | `tests/fixtures/mm_truth_set_v1.json`（14 例；sha256 **`7eb952f2797e180c…`**，已随基线固化） |
| 校准结果 | **14/14 用例满足真值集**（0 违例 / 0 UNRESOLVED / 0 层间冲突）；**三层 MATCH 精确率 = 1.0** |
| 证据汇编 | `logs/phase5e_evidence.json`（**ALL_GREEN=true**） |
| 阶段快照 | `snapshots/5.x-phase5e-20260917.{zip,db,json}`（DB sha256 `dcae4810967ee567…`） |
| 测试/回归归档 | `snapshots/phase5e-tests-archive-20260917.zip`（+ 同名 manifest） |
| 5-F/Final | **未进入**（等待人工授权） |

## 1. 十项授权要求 → 落地位置

| 授权项 | 落地 |
|---|---|
| ① 冻结小型真值集（覆盖 S04/S05/S06 + MATCH/MISMATCH/UNKNOWN + 视角 + 时序切换） | `tests/fixtures/mm_truth_set_v1.json`（14 例；含出处 `content_label_provenance`、允许/禁止输出、覆盖度标签；指纹双向钉定） |
| ② 5-A/5-D/4-B **并列**、不覆盖原结果 | `run.py mm-quality` 逐用例并列 verdict/code；模块哈希与冻结证据比对（§7） |
| ③ margin/top-k/投票/一致性/视角/阈值敏感性；**禁止调阈值** | 报告 §3/§4；`boundary`、`sensitivity`（含"更松"一侧，仅披露）；`changes_thresholds=false` |
| ④ 区分模型证据/规则推断/工程阈值/UNKNOWN | `evidence_classes`（16/8/8/2 字段）+ 每例**四段式可解释链** |
| ⑤ 不换材/选材/redo、不改时间轴、不写生产 DB | 只读层：DB 字节+五张表+项目 78 文件零变更；静态扫描无写调用 |
| ⑥ 真值缺失/模型不可用/冲突/样本不足 → fail-closed | 8 类情形（§6）：`MMQ_TRUTH_*`/`MMQ_INSUFFICIENT_COVERAGE`/`*_MODEL_MISSING`/`MMT_INSUFFICIENT_FRAMES`/`MMQ_EVIDENCE_CONFLICT`/`UNRESOLVED` |
| ⑦ 评估是否需要 5-F，只建议不实施 | `recommendations_5f`：**R1–R6**，全部 `implemented_in_5e=False` |
| ⑧ 全量回归 3-A～5-D，网络 PENDING 原状 | 23 步全 rc=0；套件 **45/45**；批次 **24/24**；冻结证据 drift 0；PENDING 记录未改写 |
| ⑨ 报告/真值集/校准证据/限制/evidence.json/新基线+SHA256 | 本卡 + `PHASE5E_REPORT.md` + `logs/phase5e_quality.json` + `phase5e_evidence.json` + `5.x-phase5e-baseline`（`3934369a…`） + manifest |
| ⑩ 完成后 STOP | 已停（未进入 5-F/Final） |

## 2. 关键结论（可复算）

| 结论 | 证据 |
|---|---|
| 三层**零误报**：没有把内容 MISMATCH 判成 MATCH | `metrics.*.match_precision_on_truth = 1.0`、`false_match_on_mismatch_cases=[]` |
| 5-A/5-D 的 UNKNOWN 只在"内容正确但证据弱"（T06 S05 / T08 S06 side） | `unknown_on_match_cases` |
| **放宽 margin −0.01 会把 T05(S05) 变 MATCH**；收紧 +0.02/+0.04 会把 4 例变 UNKNOWN | `sensitivity.flip_summary` |
| `min_stability_cos ±0.05` 无影响；**S06(side) 永不翻转** | `sensitivity.cases_never_flipping` |
| 内容-MATCH 用例期望域**全部 top-1**；MISMATCH 用例 top-1 是 `wildlife` | `case_rows[*].*_boundary.expected_in_top1` |
| 5-C 的 S06 `MATCH→UNKNOWN` 是**视角导致的稳定域区分度不足**（非采样噪声） | 5-D §5 + 本阶段 T07/T08 对照 |
| 5-F 六条建议（R1 字幕掩码/R2 成片口径预测量/R3 扩真值集/R4 UNKNOWN 两种语义/R5 S06 取舍/R6 top-1 解释列） | `recommendations_5f`（**均未实施**） |

**复算命令**：`python tests/mm_quality_test.py`（34/34）、
`python run.py mm-quality p_f4b466a4a024 --json`、`python docs/regression_2x/phase5e_evidence.py`、
`python docs/regression_2x/verify_baseline.py 5.x-phase5e-baseline`。

## 3. 如实登记的限制（`KNOWN_ISSUES.md` #43–#48）

- **#43** 真值集小（14 例）且全部来自同一**静态素材**项目 → 结论不可外推；
- **#44** "MATCH 精确率 = 1.0"仅是在这 14 例上的结论（UNKNOWN 计为保守而非误报）；
- **#45** 5-A/5-D 对"内容正确但区分度不足"的镜头给 UNKNOWN（保守设计，降低可判定覆盖率）；
- **#46** 阈值敏感性显示"放宽即变 MATCH"——**本阶段不采纳任何阈值改动**；
- **#47** top-1 一致性只是解释性指标（样本小），**未**作为规则；
- **#48** 真值集开发期修正三处夹具缺陷并重新定稿（初稿/定稿哈希均留痕），定稿后未再修改。

## 4. 还剩什么（明确不可做）

- **不可**进入 5-F/Final（授权到 5-E 为止）；
- **不可**为让 S06 变 MATCH 而调 `margin`（敏感性已证明：放宽 0.01 就会把 S05 变 MATCH，属放宽规则）；
- **不可**把 `mm-quality` 接入生产判定链（它是评估层；任何规则化改动需新授权 + 扩充真值集 + 全量回归）。

## 5. 绝不可忘的纪律

- 冻结项：4-B 词表与真值钉定、5-A 阈值、5-D 规则、响度契约、素材验证阈值、许可门禁、
  append-only/version+1、HITL —— **一个字都不许改**；
- 不得自动改选材：任何素材变更只能由**人工** `select-candidate` + 人工 `redo`；
- 不得新增写入口；不得删除/覆盖 4-B/5-A/5-B/5-C/5-D 的冻结证据（本轮用 `logs_5d_frozen/` + drift 校验证明未动）；
- 2 项 Wikimedia 真实网络项仍记 `PENDING（环境）`，即使某轮跑过也不得改写其状态；
- **未进入 5-F/Final**。
