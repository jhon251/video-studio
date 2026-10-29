# -*- coding: utf-8 -*-
"""Phase 25 登记：KNOWN_ISSUES #77 处置更新 + STATUS/CHANGELOG。"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")
c = json.loads((L / "phase25_p25_1_motion_v21.json").read_text(encoding="utf-8"))
m = c["probe_resolution_finding"]["measurements"].get("320x180", {})
g = c["guard"]

# ---------- KNOWN_ISSUES #77 处置更新 ----------
p = R / "docs" / "KNOWN_ISSUES.md"
t = p.read_text(encoding="utf-8")
OLD = "## 77. Phase 24 P24-1：**运动幅度上限与「冻结占比 <50%」约束冲突**（阻塞四件套） — `OPEN`"
NEW = ("## 77. Phase 24 P24-1 → **Phase 25 已解除**：幅度上修 1.25 后三指标实测全过 "
       "（原「幅度 × 冻结占比」约束冲突）— `RESOLVED`")
if OLD in t:
    t = t.replace(OLD, NEW, 1)
UP = """
### 77.6 处置更新（**Phase 25 已解除，2026-10-01**）
| 项 | 结果 |
|---|---|
| **幅度上修** | `MAX_ZOOM_END: 1.08 → **1.25**`（授权 P25-1）；保留 `MAX_ZOOM_END_V1=1.08` 作**守卫降级目标** |
| **总推进** | **142px → 384px**（1920 基准，2.7×）；探针尺度每秒可见变化跨过可测阈值 |
| **三指标实测** | 冻结占比 **73.7% → 0.0%** ✔｜最长静止 **9.0s → 0.0s** ✔｜开场 90s 变化 **5 → 23 次** ✔ |
| **MAD 中位数** | **0.0 → 10.23**（内容运动从"逐像素完全相同"变为显著可测） |
| **每景 corr 守卫** | 新增 `core/motion_guard.py`：`corr<0.30 ⇒ 该景幅度降回 1.08 重渲 + 登记 MOTION_DOWNGRADED`；**只调运动参数**，不改 corr 判定与仲裁语义 |
| **测试** | `motion_guard_test` **27/27**、`motion_metrics_test` **28/28**、`motion_test` **22/22**（共 **77** 项） |

**⚠️ 对 §77.3 的归因更正（如实登记）**：P24 曾把失败归因于"**探针分辨率** + 幅度上限的双重约束"，
并写下"分辨率决定成败"。**P25 实测更正**：1.25 幅度下 **160×90 / 320×180 / 480×270 三种探针全部通过**
（冻结均 0.0%）⇒ **主因是幅度**（1.08 的 142px 太小），分辨率只是**敏感度系数**。
P24 的"分辨率决定成败"表述**过强，特此更正**。（`freezedetect` 不可用作内容运动度量的更正**仍然成立**。）

**⚠️ 与授权书推导的差异（如实登记）**：授权书写"1.25 幅度 ⇒ 480px 推进"；
本实现 `w_end = out_w/zoom_end = 1536` ⇒ 总推进 **384px**（480 对应 `w_end=1440`/1.333 倍）。
倍数关系一致（×1.25），仅"幅度"基准不同；**384px 已足够**（三指标全过），故**未改语义**。
"""
if "77.6" not in t:
    t = t.rstrip() + "\n" + UP
p.write_text(t, encoding="utf-8")
print("KNOWN_ISSUES #77 → RESOLVED（含两处更正）")

STATUS = """> **Phase 25（运动 v2.1：幅度 1.25 + 每景 corr 守卫）收尾，2026-10-01**
> **P25-1 DONE ✔（幅度 1.25 生效 + 守卫落地 + 三指标**实测全过** + tests 77 项全绿）｜
> P25-2 / P25-3 / P25-4 NOT_EXECUTED（见下，未产出交付级候选）**
> - **Phase 24 的阻塞已解除**：`MAX_ZOOM_END 1.08 → **1.25**` ⇒ 总推进 **142px → 384px**（2.7×）。
>   **三指标实测**（20s/24s 探针短片，320×180 MAD 法、阈值运行前写死）：
>   **冻结占比 73.7% → 0.0%** ✔｜**最长静止 9.0s → 0.0s** ✔｜**开场 90s 变化 5 → 23 次** ✔｜
>   MAD 中位数 **0.0 → 10.23**。
> - **每景 corr 守卫（硬性，新增 `core/motion_guard.py`）**：渲染后逐景复核，`corr < 0.30`
>   ⇒ **该景幅度降回 `MAX_ZOOM_END_V1(1.08)` 重渲**并登记 `MOTION_DOWNGRADED`（附 from/to 幅度与实测 corr）；
>   仲裁层照旧兜底。**只调运动参数**，不改 corr 判定阈值与仲裁语义。边界：恰 0.30 ⇒ 不降级；
>   corr 缺失 ⇒ `KEEP_UNKNOWN`（登记不降级）。40 景演习：启用 40/40、降级 13、降级景幅度均 ≤1.08 ✔。
> - **顺带修掉一个 P25 才暴露的 bug**：`build_plan` 的 `int(str(id).lstrip("S"))` 对**派生段 id**
>   （`S02p1`）抛 `ValueError` ⇒ 新增 `_scene_ordinal()`（正则取前导数字）。40 景含派生段 id，
>   **P24 的单段测试覆盖不到**。
> - **tests（三套全绿，共 77 项）**：`motion_guard_test` **27/27**（新）、`motion_metrics_test` **28/28**、
>   `motion_test` **22/22**。
> - **⚠️ 两处如实更正**：① **P24 的归因过强**——实测 1.25 幅度下 **160/320/480 三种探针全部通过**
>   （冻结均 0.0%）⇒ **主因是幅度**，分辨率只是敏感度系数；P24 写的"分辨率决定成败"**已更正**
>   （`freezedetect` 不可用作内容运动度量的更正**仍成立**）。② **与授权书推导的差异**：授权写
>   "1.25 ⇒ 480px 推进"，本实现为 **384px**（480 对应 1.333 倍）；倍数关系一致、384px 已足够 ⇒ **未改语义**。
> - **P25-2/P25-3/P25-4 NOT_EXECUTED（诚实说明）**：本阶段预算集中在 **P25-1**（授权的前置阻塞解除项，
>   且其"三指标可达"结论**必须实测**而非推断——P24 的教训）。因此：Phase 22 bank 核验修复**未核查**、
>   40 景 v2.1 底片与 **v4.1↔40 段窗口映射未完成**、**未发起受治理获取**、P24-2 错配景重选**未生成提案**、
>   H7 片尾卡与**交付级渲染未执行**。**⟹ 本阶段未产出交付级候选**；可用候选仍是 **P19 的 21 景版**
>   （`projects/p_50e10b27b44d/output/t_a4d8c1aafd04_draft.mp4`）。
> - 边界：LLM **$0**、VLM **$0**、网络 **$0**、**未渲染成片**（仅探针短片）；
>   `config.json`/DB schema/**PI 阈值与判定语义**/**corr 度量与仲裁语义**/`mm_*` 冻结栈/词表/baseline/
>   母片/既有候选**均未改**；未做图内元素动画、视频素材接入、句中拆分、改旁白、promotion、发布。
> - **完整回归 80 套一次跑完未中途停止**（`logs/phase25_suites.log` + `logs/suites_summary.json`）；
>   **IMMUTABLE_OK**。详见 `PHASE25_REPORT.md`；#77 已在 KNOWN_ISSUES 标记 **RESOLVED**。

"""

CHANGELOG = """## Phase 25 — 运动 v2.1（幅度 1.25 + 每景 corr 守卫）：Phase 24 的约束冲突解除，三指标实测全过（2026-10-01）

**Phase 24 阻塞解除。** `core/motion.py` 的 `MAX_ZOOM_END` 由 **1.08 上修到 1.25**（授权 P25-1），
并使 `plan_scene` 的 `zoom_end` 不再硬编码 1.08（新增 `zoom_max` 参数，缺省 1.25）；
保留 **`MAX_ZOOM_END_V1 = 1.08`** 作为**每景 corr 守卫的降级目标**。
总推进由 **142px → 384px**（1920 基准，2.7×），探针尺度每秒可见变化跨过可测阈值。
**实测**（探针短片，320×180 MAD 法、阈值运行前写死）：**冻结占比 73.7% → 0.0%**、
**最长静止 9.0s → 0.0s**、**开场 90s 变化 5 → 23 次**、MAD 中位数 **0.0 → 10.23** ⇒ **三指标全过**。

**P25-1 每景 corr 守卫（硬性，新增 `core/motion_guard.py`）。** 渲染后逐景复核 corr：
`corr < CORR_GUARD_MIN(0.30)` ⇒ **该景幅度自动降回 `MAX_ZOOM_END_V1(1.08)` 重渲**，
并登记 **`MOTION_DOWNGRADED`**（附 from/to 幅度与实测 corr）；仲裁层（`core/render_arbitration.py`）
照旧兜底。`guarded_scenes()` 给出确定性降级集合，`rebuild_plan_with_guard()` 按降级集重算计划
（未降级景**不受影响**，`plan.counts.downgraded` 一致，内嵌 `plan.guard` 摘要）。
**边界**：恰等于 0.30 ⇒ **不降级**；corr **缺失** ⇒ `KEEP_UNKNOWN`（登记但不降级，待复核）。
**守卫只调运动参数**，不改 corr 判定阈值、不改仲裁语义（授权边界）。
40 景演习：启用 **40/40**、降级 **13**、降级景幅度均 ≤1.08 ✔。

**顺带修掉一个 P25 才暴露的 bug。** `build_plan` 原用 `int(str(scene_id).lstrip("S"))` 解析父景序号，
对**派生段 id**（`S02p1`，40 景底片必然出现）抛 `ValueError` ⇒ 新增 `_scene_ordinal()`
（正则取前导数字、异常返回 0）。P24 的单段测试**覆盖不到**该路径。

**tests（三套全绿，共 77 项）**：新增 `tests/motion_guard_test.py` **27/27**
（降级/保持/未知/边界、计划重建、派生段 id 解析、三指标口径写死、确定性）；
`tests/motion_metrics_test.py` 更新为 **28/28**（幅度 384px vs 142px、探针 320×180）；
`tests/motion_test.py` 常量断言更新 **22/22**。

**⚠️ 两处如实更正。** ① **P24 的归因过强**：P24 曾把失败归因于「探针分辨率 + 幅度上限的双重约束」
并写下「分辨率决定成败」；P25 实测 **1.25 幅度下 160×90 / 320×180 / 480×270 三种探针全部通过**
（冻结均 0.0%）⇒ **主因是幅度**（1.08 的 142px 太小），分辨率只是**敏感度系数**，
P24 的该表述**已更正**（`freezedetect` 不可用作内容运动度量这一更正**仍然成立**）。
② **与授权书推导的差异**：授权书写「1.25 幅度 ⇒ 480px 推进」；本实现 `w_end = out_w/zoom_end = 1536`
⇒ 总推进 **384px**（480 对应 `w_end=1440`，即 1.333 倍）。倍数关系一致（×1.25），仅"幅度"基准不同；
**384px 已足够**（三指标全过）⇒ **未改语义**。

**P25-2 / P25-3 / P25-4：NOT_EXECUTED（诚实说明）。** 本阶段预算集中在 **P25-1**——它是授权的前置阻塞
解除项，且其"三指标可达"结论**必须实测**而非推断（P24 的教训：纸面推导与实测不符）。
因此本阶段**未**完成：Phase 22「派生段 bank 核验修复」的落地核查、40 景 v2.1 底片与
**v4.1 ↔ 40 段窗口映射**、**受治理获取**（≤6 张 Wikimedia）、P24-2 错配景重选提案、
H7 片尾卡与**交付级渲染**。**⟹ 未产出交付级候选**；可用候选仍是 **P19 的 21 景版**
（`projects/p_50e10b27b44d/output/t_a4d8c1aafd04_draft.mp4`）。

**边界**：LLM **$0**、VLM **$0**、网络 **$0**、**未渲染成片**（仅探针短片）；
`config.json`、DB schema、**PI 阈值与判定语义**、**corr 度量与仲裁语义**、`mm_*` 冻结栈、词表、
baseline、母片、既有候选**均未改**；未做图内元素动画、视频素材接入、句中拆分、改旁白文本、
promotion、发布。**完整回归 80 套一次跑完、未中途停止**（`logs/phase25_suites.log`）；
**IMMUTABLE_OK**。**KNOWN_ISSUES #77 → RESOLVED**（含上述两处更正）。

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


prepend(R / "STATUS.md", STATUS, "> **Phase 24（视觉观感四件套）收尾")
prepend(R / "CHANGELOG.md", CHANGELOG, "## Phase 24 —")
print("三指标实测（320x180）: 冻结 {:.1%} | 最长静止 {}s | 开场变化 {} | MAD中位 {}".format(
    m.get("freeze_ratio", -1), m.get("longest_static_s"), m.get("opening_changes"),
    m.get("mad_median")))
print("守卫: 降级 {} 景".format(len(g["downgrade"])))
