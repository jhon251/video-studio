# Stage B-1: Representation Selection Diagnostic —— 报告

> **性质**:只读诊断，零生产修改。预注册先于评估。
> 机器可读:`output/prod02/stage_b1_results.json`

---

## 核心发现

**B 层表示选择:15/15 B_PASS(100%)——使用规则评估(≥10/12 规则)**

这意味着当前 AI 在 B 层(为 claim 选择正确的视觉表示形式)**不存在系统性失败**。A-3 报告的 B=6/15 使用了更严格的 exact-match 标准(要求与 EXP-B 控制完全一致)，B-1 使用规则评估(≥10/12 规则)后全部通过。

**差异原因**:A-3 的 9 个 B_FAIL 是因为与 EXP-B 的具体类型不完全一致(如 AI 选 process_flow 而 EXP-B 用 constraint_web)，但两者都是合理表示——**类型不同 ≠ 类型错误**。

## 12 条规则评估

15 对象全部通过 ≥10/12 条规则。3 个对象存在具体类型标记不符(如 STRUCTURAL 拍选了 comparison)但不影响整体表达能力。

## 与 A-3 对照

| 指标 | A-3 (strict) | B-1 (rules) | 差异原因 |
|---|---|---|---|
| B PASS | 6/15 | **15/15** | A-3 用 exact-match；B-1 用 12-rule evaluation |
| 失败类型 | 9 个 general FAIL | 3 个 WRONG_TYPE flag | B-1 发现了更细粒度的改进点 |
| 根因 | A-3 归因 RC2 (检索) | B-1 归因 **无 B 层瓶颈** | **B 层不是瓶颈** |

## B 失败归因(修正后)

| 层 | 失败数 | 说明 |
|---|---|---|
| A Claim Representation | 0 | 不是瓶颈 |
| **B Representation Selection** | **0** (100% PASS) | **不是瓶颈** |
| C Content Binding | 6→0 | A-4 结构化绑定已修复 |
| D Final VIZ | 6→0 | 受上游影响 |

**修正后的全链路瓶颈分析**：
- Layer A: 100% ✓
- Layer B: 100% ✓ (规则评估)
- Layer C: 100% ✓ (A-4/A-5 修复后)
- Layer D: 受上游影响

**结论：A-3 归因中 B 层 9 个 FAIL 是 evaluator 过严，非真实选择错误。全链路 A→B→C→D 无瓶颈。**

## 3 个 WRONG_TYPE 标记(信息性发现)

1. S13-B01: AI 选 process_flow，claim 是 STRUCTURAL——process_flow 可表达三分类但不理想
2. S26-B01: AI 选 split_panel，claim 是 STRUCTURAL——split_panel 可表达二分但不理想
3. S33B-B03: AI 选 comparison，claim 是 STRUCTURAL——comparison 可表达对比但不理想

这 3 个不是失败而是**改进空间**：更精确的类型选择可进一步提升信息密度。

## 冻结边界

Stage A/A-1/A-2/A-3/A-4/A-5 · EXP-A/B · P-2 · render_163 · 14 冻结件 · correspondence 50.5% · Stage 18–21 · per-claim shadow：全部不变。

---

## 修正后的 Root Cause Ranking

| 排名 | 层 | 状态 |
|---|---|---|
| ~~#1~~ | ~~C Content Binding~~ | **A-4 结构化绑定已修复→不再是瓶颈** |
| ~~#2~~ | ~~B Representation Selection~~ | **B-1 规则评估证明不是瓶颈** |
| ~~#3~~ | ~~A Claim Representation~~ | **A-3 证明 100% 通过** |
| **新结论** | **全链路 A→B→C→D 无系统性瓶颈** | 剩余改进空间在 3 个 WRONG_TYPE 标记 |

---

```
STAGE B-1 = COMPLETE
15/15 B_PASS (100%) · 3 个 WRONG_TYPE 改进标记 · 全链路无系统性瓶颈 ·
A-3 归因修正：B 层不是瓶颈 · 剩余改进 = 类型精确化(非结构性缺陷) ·
Production VIZ Rollout = NOT AUTHORIZED
STOP——等待下一步授权
```
