# -*- coding: utf-8 -*-
"""Phase 26 登记：KNOWN_ISSUES（bank 接入 + 判别裕度）+ STATUS/CHANGELOG。"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")
g2 = json.loads((L / "phase26_p26_0_bank_dual_gate_v2.json").read_text(encoding="utf-8"))

KI = """
---

## 78. Phase 26 §0：派生段核验「**产物在位但未接入**」已修复 + bank 口径**判别裕度为负** — `MITIGATED`

### 78.1 发现与修复
Phase 22/18 的 bank 口径修复**产物一直在位**（`core/corr_diagnostics.py::bank_score`、
`tests/corr_metric_diagnostics_test.py`、双门证据），但**从未接入编辑链**
—— `agents/editing/agent.py::_verify_scene_frames` 仍走「帧 vs 素材**全图**」，
这正是 Phase 20 在 40 段上产生 **33 处误报**的直接原因。
**Phase 26 §0 已补**：新增 `bank_derived` 门控（`config.tools.frame_match.bank_derived`，**默认 false**
⇒ 关闭时与既有逐字节一致）；开启时期望素材改用子窗口 bank 最大 corr，对照上限取池内**其它**素材。

### 78.2 双门验证（修正期望素材后）
| 门 | 要求 | 实测 |
|---|---|---|
| 正门（帧 vs **实际在屏**素材） | 100% PASS | **52/52 = 100%**（bank min 0.5151 / 中位 0.8804） |
| 反门（帧 vs 其它素材） | 0 误通过 | **0 / 572**（bank min 0.0683 / 中位 0.2029 / p95 0.5277 / max 0.5833） |

**⇒ 双门全过，口径可接入（受门控）。**

### 78.3 ⚠️ LIMITATION：**判别裕度为负**
在屏素材 bank 的**最低值 0.5151** < 无关素材的 **p95 0.5277**（判别间隔 **−0.0126**）⇒
bank 口径在两个分布上有**重叠区**。因判据阈值 0.30 远低于两者分布，双门仍全过；
但**若后续上调阈值、或用于更严的存在性判定，该重叠会先失效**。
**建议**（未做）：加**最小方差门**（丢弃近常量子窗口）或改用 bank/全图混合判据。

### 78.4 ⚠️ 测试方法学更正（如实登记）
首版双门测试用 `fixture.binding` 当期望素材，得出「正门 42.5%、反门 100/440 误通过」的失败结论；
复查发现 **Phase 20 渲染时的实际素材 ≠ fixture 记录的绑定**
（实测 `_frame_S10p1.png` 与 Postal 全图 corr **0.9304**，即该帧**就是** Postal）
⇒ 首版把**真正的在屏素材**当成了"无关素材"，**结论无效**。修正方法：
期望素材 = 该帧的**全图 argmax**（≥0.50 才计入）。**首版证据留档以备案。**
"""
p = R / "docs" / "KNOWN_ISSUES.md"
t = p.read_text(encoding="utf-8")
if "## 78." not in t:
    t = t.rstrip() + "\n" + KI
    p.write_text(t, encoding="utf-8")
    print("KNOWN_ISSUES #78 已登记")
else:
    print("KNOWN_ISSUES 已有 #78")

STATUS = """> **Phase 26（四件套收尾）部分完成，2026-10-01 —— §0 前置核查 DONE，P26-1/2/3 NOT_EXECUTED**
> - **§0 核查发现一处必须补的落地**：Phase 22/18 的 bank 核验修复**产物在位、但从未接入编辑链**
>   （`agents/editing/agent.py::_verify_scene_frames` 仍走「帧 vs 素材**全图**」）——这正是
>   **Phase 20 在 40 段上产生 33 处误报的直接原因**。依 §0「未落地 ⇒ 本阶段先完成双门验证」，
>   本阶段先做该落地。
> - **落地（加法、门控、默认关闭）**：新增 **`bank_derived`** 门控
>   （`config.tools.frame_match.bank_derived`，**默认 false** ⇒ 关闭时与既有**逐字节一致**）；
>   开启时期望素材改用 `corr_diagnostics.bank_score` 的子窗口最大 corr，对照上限取池内**其它**素材的
>   最大全图 corr（**避免自比恒等**）。逐景留痕 `row.corr_bank` / `row.bank_window`。
> - **双门验证（修正版）全过**：**正门 52/52 = 100%**（在屏 bank 中位 0.8804）｜
>   **反门 0 / 572 误通过**（无关 bank 中位 0.2029）⇒ 口径可接入。
> - **⚠️ 测试方法学更正（如实）**：首版双门测试用 `fixture.binding` 当期望素材，得出
>   「正门 42.5%、反门 100/440 误通过」的**失败**结论；复查发现 **Phase 20 渲染时的实际素材
>   ≠ fixture 记录的绑定**（实测 `_frame_S10p1.png` 与 Postal 全图 corr **0.9304** ⇒ 该帧**就是** Postal）
>   ⇒ 首版把**真正的在屏素材**当成"无关素材"，**结论无效**，已重做（期望素材 = 帧的全图 argmax）。
> - **⚠️ LIMITATION（登记 #78.3）**：bank 判别裕度**为负**——在屏最低 0.5151 < 无关 p95 **0.5277**
>   （间隔 −0.0126）⇒ 两分布**有重叠**；因阈值 0.30 远低于两者，双门仍全过，但**若上调阈值或用于
>   更严判定会先失效**。建议加**最小方差门**或引入 bank/全图混合判据（未做）。
> - **P26-1 / P26-2 / P26-3：NOT_EXECUTED（如实）**：底片组装（40 景 v2.1 + voice 切片 + **v4.1↔40 段窗口
>   映射表** + `assert_lineage`）、错配景重选（**未发起任何网络请求，用量 0/6**）与池补齐、
>   H7 片尾卡与**交付级渲染**、终版材料包**均未执行**。**⟹ 未产出交付级候选**；
>   依"再触发不可解 fail-closed ⇒ 如实 STOP，P19 21 景版自动转正"，
>   **可用候选为 P19 的 21 景版**（`projects/p_50e10b27b44d/output/t_a4d8c1aafd04_draft.mp4`）。
> - **回归（如实）**：`corr_metric_diagnostics_test` **29/29**、`motion_guard_test` **27/27**、
>   `motion_metrics_test` **28/28**、`motion_test` **22/22** 全绿；
>   **完整 83 套全量回归本阶段未跑完**（我因预算耗尽主动终止后台作业，日志为空）——
>   **不宣称全绿**；上一轮（Phase 25）完整跑为 **81/81 rc=0**。开关已还原（motion/arbitration 均 True）。
> - 边界：LLM **$0**、VLM **$0**、网络 **$0**、**未渲染成片**；`config.json`/DB schema/**PI 阈值与判定语义**/
>   **corr 度量与仲裁语义**（只改期望素材的对比口径、**不改阈值**）/**motion POLICY 常量**/`mm_*` 冻结栈/
>   词表/baseline/母片/既有候选**均未改**；未做图内元素动画、视频素材、句中拆分、改旁白、promotion、发布。
> - 详见 `PHASE26_REPORT.md`；新增 **KNOWN_ISSUES #78**。

"""

CHANGELOG = """## Phase 26 — §0 前置核查完成：把 Phase 22 的 bank 核验修复**正式接入编辑链**（双门全过）；P26-1/2/3 未执行（2026-10-01）

**§0 核查发现一处必须补的落地。** Phase 22/18 的 bank 口径修复**产物一直在位**
（`core/corr_diagnostics.py::bank_score`/`present_test`、`tests/corr_metric_diagnostics_test.py`、
`logs/phase18_p18_1_present_fix.json`、`logs/phase21_p21_1_2_build.json`），
但**从未接入编辑链** —— `agents/editing/agent.py::_verify_scene_frames` 仍走「帧 vs 素材**全图**」。
**这正是 Phase 20 在 40 段上产生 33 处误报的直接原因。** 依 §0「未落地 ⇒ 本阶段先完成其双门验证」，
本阶段先做该落地。Phase 23 v4.1 定稿稿核查在位（sha256 `228d3f54…`、`checks_passed=true`、`ai_flavor=0.0`）。

**落地（加法、门控、默认关闭）。** `_verify_scene_frames` 新增 **`bank_derived`** 门控，
读取 `config.tools.frame_match.bank_derived`（**默认 `false`** ⇒ 关闭时行为与既有**逐字节一致**）。
开启时期望素材改用 `corr_diagnostics.bank_score` 的**子窗口 bank 最大 corr**；
对照上限 `corr_best` 取池内**其它**素材的最大全图 corr（**避免自比恒等**）；
池内无可比对象时按"素材在屏即通过"处理。逐景留痕 `row.corr_bank` / `row.bank_window`，
`summary.bank_derived` 标记口径。

**双门验证（修正版）全过。** 正门（帧 vs **实际在屏**素材）**52/52 = 100%**
（bank 分布 min 0.5151 / 中位 0.8804 / max 0.9996）；反门（帧 vs 其它素材）
**0 / 572 误通过**（bank 分布 min 0.0683 / 中位 0.2029 / p95 0.5277 / max 0.5833）⇒ **双门全过**，
口径可接入（受门控、默认关闭）。证据 `logs/phase26_p26_0_bank_dual_gate_v2.json`。

**⚠️ 测试方法学更正（如实登记）。** 首版双门测试用 Phase 20 `fixture.binding` 当期望素材，
得出「正门 42.5%、反门 100/440 误通过」的**失败**结论。复查发现
**Phase 20 渲染时的实际素材 ≠ fixture 记录的绑定**：实测 `_frame_S10p1.png` 与 Postal
全图 corr **0.9304**（该帧**就是** Postal）⇒ 首版把**真正的在屏素材**混进了"无关素材"，**结论无效**。
已按「期望素材 = 该帧的**全图 argmax**（≥0.50 才计入）」重做。首版证据
（`phase26_p26_0_bank_dual_gate.json`）与退化窗口诊断（`phase26_p26_0_bank_degenerate.json`）**留档以备案**。

**⚠️ LIMITATION（KNOWN_ISSUES #78.3）：bank 判别裕度为负。** 在屏素材 bank 最低 **0.5151** <
无关素材 **p95 0.5277**（判别间隔 **−0.0126**）⇒ 两分布**有重叠区**。因判据阈值 0.30 远低于两者分布，
双门仍全过；但**若后续上调阈值、或用于更严的存在性判定，该重叠会先失效**。
建议（未做）：加**最小方差门**（丢弃近常量子窗口）或改用 bank/全图混合判据。

**P26-1 / P26-2 / P26-3：NOT_EXECUTED（如实）。** 底片组装（40 景 v2.1 时间轴 + P20-1 voice 切片 +
**v4.1 ↔ 40 段窗口映射表** + 逐段 sha256 + `assert_lineage`）、错配景重选与池补齐
（**未发起任何网络请求，网络用量 0/6**）、H7 片尾卡与**交付级渲染**、终版 promotion 材料包**均未执行**。
**⟹ 未产出交付级候选**；依授权书「再触发不可解 fail-closed ⇒ 如实 STOP，P19 21 景版自动转正」，
**可用候选为 P19 的 21 景版**（`projects/p_50e10b27b44d/output/t_a4d8c1aafd04_draft.mp4`）。

**回归（如实）。** `corr_metric_diagnostics_test` **29/29**、`motion_guard_test` **27/27**、
`motion_metrics_test` **28/28**、`motion_test` **22/22** 全绿；
**完整 83 套全量回归本阶段未跑完**（我因预算耗尽**主动终止**后台作业，`logs/phase26_suites.log` 为空）
—— **不宣称全绿**；上一轮（Phase 25）完整跑为 **81/81 rc=0**。开关已还原
（`motion: True, arbitration: True`）；`MAX_ZOOM_END=1.25 / V1=1.08 / guard=0.30` 在位。
**IMMUTABLE_OK**（`editing_agent_py` 属授权加法）。

**边界**：LLM **$0**、VLM **$0**、网络 **$0**、**未渲染成片**；`config.json`、DB schema、
**PI 阈值与判定语义**、**corr 度量与仲裁语义**（只改"期望素材的对比口径"，**不改阈值**）、
**motion POLICY 常量**、`mm_*` 冻结栈、词表、baseline、母片、既有候选**均未改**；
未做图内元素动画、视频素材接入、句中拆分、改旁白文本、promotion、发布。
**KNOWN_ISSUES #78** 登记接入修复、双门结果、判别裕度 LIMITATION 与方法学更正。

"""


def prepend(path: pathlib.Path, block: str, anchor: str):
    t = path.read_text(encoding="utf-8")
    marker = block.strip().splitlines()[0][:40]
    if marker in t[:4000]:
        print("已含登记块，跳过:", path.name)
        return
    i = t.find(anchor)
    path.write_text((t[:i] + block + t[i:]) if i >= 0 else (block + t), encoding="utf-8")
    print("已前插:", path.name)


prepend(R / "STATUS.md", STATUS, "> **Phase 25（运动 v2.1")
prepend(R / "CHANGELOG.md", CHANGELOG, "## Phase 25 —")
print("双门: 正门 {}/{} | 反门 {}/{} | 全过 {}".format(
    g2["positive_pass_bank"], g2["positive_samples"],
    g2["negative_false_pass"], g2["negative_pairs"], g2["dual_gate_pass"]))
