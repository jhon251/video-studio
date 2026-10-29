# -*- coding: utf-8 -*-
"""Phase 27 登记：KNOWN_ISSUES（派生段绑定未落渲染 + // bug）+ STATUS/CHANGELOG。"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")
v = json.loads((L / "phase27_p27_3_verification.json").read_text(encoding="utf-8"))
mm = v["motion_metrics"]

KI = """
---

## 79. Phase 27：**派生段素材绑定未落到渲染**（阻塞交付级候选）+ v2 运动滤镜 `//` 缺陷 — `OPEN`

### 79.1 派生段绑定未落到渲染（**唯一剩余阻塞**）
**现象**：40 段成片渲染成功，但逐景核验 `checked = 2/40` —— 只有 `S01`/`S20`（父景 id）
有 `expected_asset_id`；其余 **38 个派生段**（`S02p1`…）为 `None` ⇒ 落入"占位镜头"分支
⇒ **17 景失败**；连带 **DQ-2 FAIL**（`max_asset_share 0.9369`、`unique_assets 3`，政策 ≤0.35 / ≥6）。

**根因**：`MATERIAL_TIMELINE` 的 decisions **按父景 ID 落库**；40 段派生脚本的 scene_id 是
**派生 ID**，闸门按派生 ID 查绑定 ⇒ 查不到。
**这是与 Phase 26 §0「产物在位但未接入」同一模式的第二次出现**：
Phase 21 的"绑定展开"只做在**离线复验脚本**里，**未进入渲染链**。

**修复路径（推荐第 1 项）**：
1. **闸门按 `parent_scene_id` 回退查绑定**（改动最小、不动 DB 写入路径）；
2. 或把父景绑定**展开**成 40 条 decisions 写进 `MATERIAL_TIMELINE`；
3. `bank_derived` 已在位并按派生段取子窗口 corr（Phase 26 §0 双门：正门 100% / 反门 0），
   绑定修好后 40/40 可核验；
4. 一并做 **DQ-2 的 `cap=2` 新口径**与**受治理获取 ≤6 张**（本轮未执行，网络用量 0/6）。

### 79.2 v2 运动滤镜使用 `//`，**ffmpeg 表达式解析器不支持**（已修复）
`crop_filter` 的 v2 平移/缩放闭式原用 `//` 做整数除。**ffmpeg 不支持 `//`**
（报 `Undefined constant or missing '(' in '/519)'`）⇒ 首轮渲染 **19/40 景 crop 配置失败**、
**-22 Invalid argument**、成片 **0 B**。已改为 `floor(a/b)`，重测 **40/40 滤镜全部通过**。
**为何 Phase 24/25 未发现**：那两阶段只渲染**单段探针**（S01 走 zoom 分支，
且 24s 场景未触发平移分支的 `//` 路径）⇒ **只有 40 景全片渲染才暴露**。

### 79.3 ✅ 已达成：三指标在**真实 40 景成片**上首次全过
| 指标 | 阈值 | 实测 |
|---|---|---|
| 冻结占比 | <50% | **15.2%** ✔ |
| 最长连续静止 | <25s | **6.0s** ✔ |
| 开场 90s 变化 | ≥3 次 | **69 次** ✔ |

（Phase 24 提出的观感目标至此达成；对比 P24 的 73.7% / 9.0s / 5 次。）
其余门禁全过：时长 **977.88s** ✔｜响度 **−16.1 LUFS / −2.5 dBTP** ✔｜
PI 前/后全 PASS、`promote_blocked=False` ✔｜字幕 `SUBTITLE_ALIGNED`（171 cue、语音内 1.0、越界 0s）✔｜
MOTION_VERIFIED **40/40、0 fallback** ✔。**仅剩 §79.1 一项。**
"""
p = R / "docs" / "KNOWN_ISSUES.md"
t = p.read_text(encoding="utf-8")
if "## 79." not in t:
    t = t.rstrip() + "\n" + KI
    p.write_text(t, encoding="utf-8")
    print("KNOWN_ISSUES #79 已登记")
else:
    print("KNOWN_ISSUES 已有 #79")

STATUS = """> **Phase 27（底片组装 + 错配清除 + 交付级渲染）收尾，2026-10-01 —— 成片已产出、三指标首次全过；
> 但逐景核验门 fail-closed（17 景）⇒ 未登记交付级候选**
> **P27-1 DONE ✔｜P27-2 部分 DONE｜P27-3 渲染已产出但门未过｜P27-4/P27-5 NOT_EXECUTED**
> - **P27-1 底片组装 DONE**：40 景 v2.1 时间轴 + P20-1 voice 切片 + **v4.1 定稿稿文本**。
>   **v4.1（8 段）↔ 40 段窗口映射表**已落盘（`logs/phase27_p27_1_mapping.json`）：
>   按**句界/窗口对齐规则**（父景/子段两级、按累计时长比例选切点、吸附句/子句边界）
>   ⇒ **文本零改动硬校验 3468 → 3468 字符（相等 ✔）**，逐段 sha256 + 父景/子段**双重守恒**；
>   **`assert_lineage` 通过 ✔**（时基差 0.75s < 1.0）；`frame_match.bank_derived=true` 已开启
>   （默认仍 false，关闭路径逐字节兼容已于 Phase 26 §0 证明）。
> - **P27-2 部分 DONE**：错配素材（旗帜照，P24-2 点名）**已排除**；标记素材降权重选 **4 处**
>   （S02/S03/S05/S08）。**未执行**：受治理获取（**网络用量 0/6**）、`cap=2` 新口径分配。
> - **P27-3 渲染 DONE（成片已产出）**：沙箱 `p_c7d6b1f4dab2`、`t_649df0e2f014`、**172.9 s**；
>   成片 **43,185,500 B**（**未登记 `render_output`** ⇒ 非交付物）；
>   **运动 40/40 启用、0 fallback**。
> - **✅ 三指标在真实 40 景成片上首次全过**：冻结占比 **15.2%**（<50%）｜
>   最长连续静止 **6.0s**（<25s）｜开场 90s 变化 **69 次**（≥3）。
>   其余门禁全过：时长 **977.88s** ✔｜响度 **−16.1 LUFS / −2.5 dBTP** ✔｜PI 前/后全 PASS、
>   `promote_blocked=False` ✔｜字幕 `SUBTITLE_ALIGNED`（171 cue、语音内 1.0、越界 0s）✔。
> - **⚠️ 阻塞（唯一）**：**派生段素材绑定未落到渲染** —— `bank_derived` 已生效但
>   **仅 2/40 景有 `expected_asset_id`**（`S01`/`S20`），38 个派生段为 `None` ⇒ 落入占位分支
>   ⇒ **逐景失败 17 景**；连带 **DQ-2 FAIL**（`max_asset_share 0.9369`、`unique 3`）。
>   **根因**：`MATERIAL_TIMELINE` 的 decisions **只按父景 ID 落库**，闸门按**派生 ID** 查不到
>   —— 与 Phase 26 §0「产物在位但未接入」**同一模式的第二次出现**（Phase 21 的绑定展开只做在
>   离线复验脚本里）。**修复**：闸门按 `parent_scene_id` **回退查绑定**（改动最小），或把绑定展开进
>   `MATERIAL_TIMELINE`。**DQ-3** `share 0.45 / max 36.836s` ⇒ 显著改善但未达 ≤20%（报改善、不报 PASS）。
>   **仲裁层**：仅 1 景进入 VLM 核验（判 absent）⇒ 未放行；成本 **$0.0007**。
> - **🔧 顺带修掉一个真 bug**：v2 运动闭式用了 `//` 做整数除，而 **ffmpeg 表达式不支持 `//`**
>   ⇒ 首轮渲染 **19/40 景 crop 配置失败**、**-22 Invalid argument**、成片 **0 B**；改 `floor(a/b)` 后
>   **40/40 滤镜全通过**。**Phase 24/25 未发现**，因为那两阶段只渲染单段探针（S01 走 zoom 分支、
>   24s 未触发平移 `//` 路径）⇒ **只有 40 景全片渲染才暴露**。
> - **P27-4/P27-5 NOT_EXECUTED**（依预算纪律：渲染证据未完整落盘前不把预算花在回归上；
>   本轮虽已落盘但门未过，仍如实优先报告）。已知最近完整跑：**Phase 25 = 81/81 rc=0**。
> - **依授权书**：全门过才登记交付级候选；本轮 **fail-closed ⇒ 如实 STOP**，
>   **P19 21 景版自动转正**（`projects/p_50e10b27b44d/output/t_a4d8c1aafd04_draft.mp4`）。
> - 边界：LLM **$0**、VLM **$0.0007**、网络 **$0**、渲染 172.9s；DB schema/**PI 阈值与判定语义**/
>   **corr 度量与仲裁语义**/**motion POLICY 常量**/`mm_*`/词表/baseline/母片/既有候选**均未改**；
>   `config.json` 仅**追加** `tools.frame_match.bank_derived=true`（授权项，默认仍 false）；
>   未做图内元素动画、视频素材、句中拆分、改旁白、promotion、发布。
> - 详见 `PHASE27_REPORT.md`；新增 **KNOWN_ISSUES #79**。

"""

CHANGELOG = """## Phase 27 — 底片组装（v4.1 文本 × 40 景）+ 错配清除 + 交付级渲染：**三指标首次全过**，但派生段绑定未落渲染致门 fail-closed（2026-10-01）

**P27-1 底片组装 DONE。** 40 景 v2.1 时间轴 + P20-1 voice 切片 + **Phase 23 v4.1 定稿稿文本**。
**v4.1（8 段）↔ 40 段窗口映射表**落盘 `logs/phase27_p27_1_mapping.json`：因**分段数不符**（8 vs 21 父景 /
40 子段），按授权要求**按句界/窗口对齐规则映射并登记规则** ——「先把 v4.1 全文按**父景累计时长比例**
切到 21 个父景，再按**子段时长比例**切到 40 子段；切点**吸附在最接近的句/子句边界**；字符区间偏移
⇒ **逐字保留**」。**文本零改动硬校验：3468 → 3468 字符（相等）**；逐段 `text_sha256` 记录；
父景级与子段级**双重守恒**断言通过。产物 `output/phase27_script_sandbox/script_p27_v41_40seg.json`
（40 段 · 978.634s）。**`assert_lineage` 通过**（时基差 0.75s < 1.0）。
**`frame_match.bank_derived = true` 已开启**（`config.json` 的 `tools.frame_match` **追加**该键，
**默认仍为 false**；关闭路径逐字节兼容性已于 Phase 26 §0 证明）。

**P27-2 错配清除 + 池补齐（部分 DONE）。** 错配素材（P24-2 点名的旗帜照）**已在池内排除**
（`EXCLUDE_NAME_HINTS`）；标记素材（`low_crop_safety`/`low_discriminative`）**降权重选 4 处**
（S02/S03/S05/S08，替换后立即计入复用计数以免 DQ-2 恶化）。**未执行**：
**受治理获取 ≤6 张（网络用量 0/6）**、**`cap=2` 新口径分配**。

**P27-3 交付级渲染（成片已产出）。** 沙箱 `p_c7d6b1f4dab2`、任务 `t_649df0e2f014`、**172.9 s**；
成片 `projects/p_c7d6b1f4dab2/output/t_649df0e2f014_draft.mp4`（**43,185,500 B**），
**未登记 `render_output`**（fail-closed，非交付物）；**运动 `{enabled: 40, fallback: 0, scenes: 40}`**。
**✅ 三指标在真实 40 景成片（非探针）上首次全过**：冻结占比 **15.2%**（<50%）、
最长连续静止 **6.0s**（<25s）、开场 90s 变化 **69 次**（≥3）⇒ **Phase 24 提出的观感目标达成**
（对比 P24：73.7% / 9.0s / 5 次）。其余门禁全过：时长 **977.88s**（978.7±1 ✔）、
响度 **−16.1 LUFS / −2.5 dBTP** ✔、PI 渲染前/后全 PASS 且 `promote_blocked=False` ✔、
字幕 `SUBTITLE_ALIGNED`（**171 cue**、语音内 **1.0**、越界 **0 s**）✔。

**⚠️ 阻塞（唯一）：派生段素材绑定未落到渲染。** `bank_derived` 确实生效
（`summary.bank_derived=true`），但**仅 2/40 景有 `expected_asset_id`**（`S01`/`S20`，父景 id）；
其余 **38 个派生段**（`S02p1`…）为 `None` ⇒ 落入"占位镜头"分支 ⇒ **逐景失败 17 景**
（`corr_expected=None`）；**连带 DQ-2 FAIL**（`max_asset_share 0.9369`、`unique_assets 3`，
政策 ≤0.35 / ≥6）。**根因**：`MATERIAL_TIMELINE` 的 decisions **按父景 ID 落库**，
而闸门按**派生 ID** 查绑定 ⇒ 查不到。**这是与 Phase 26 §0「产物在位但未接入」同一模式的第二次出现**
（Phase 21 的"绑定展开"只做在**离线复验脚本**里，未进入渲染链）。
**修复（推荐）**：闸门按 `parent_scene_id` **回退查绑定**（改动最小、不动 DB 写入路径），
或把父景绑定**展开**进 `MATERIAL_TIMELINE`。**DQ-3**：`share 0.45`、`max_hold 36.836s`
⇒ **显著改善但未达 ≤20%**（按口径报改善、不报 PASS）。**仲裁层**：仅 1 景进入 VLM 核验（判 `absent`）
⇒ 未放行；成本 **$0.0007**。

**🔧 顺带修掉一个真 bug（如实登记）。** v2 运动闭式（平移与缩放）原用 `//` 做整数除，
而 **ffmpeg 表达式解析器不支持 `//`**（报 `Undefined constant or missing '(' in '/519)'`）
⇒ 首轮渲染 **19/40 景 crop 配置失败**、**-22 Invalid argument**、成片 **0 B**。
已改为 `floor(a/b)`，重测 **40/40 滤镜全部通过**（`logs/phase27_crop_diag.json`）。
**为何 Phase 24/25 未发现**：那两阶段只渲染**单段探针**（S01 走 zoom 分支，且 24s 场景恰好
未触发平移分支的 `//` 路径）⇒ **只有 40 景全片渲染才暴露**。

**P27-4 / P27-5：NOT_EXECUTED。** 终版 promotion 材料包未生成（候选未成立）；
**完整回归未跑**（依授权书**预算纪律**：渲染证据未完整落盘前不把预算花在回归上；
本轮虽已落盘但门未过，仍如实优先报告）。已知最近一次完整跑：**Phase 25 = 81/81 rc=0**。

**依授权书**：全门过才登记交付级候选；本轮 **fail-closed ⇒ 如实 STOP**，
**P19 21 景版自动转正**（`projects/p_50e10b27b44d/output/t_a4d8c1aafd04_draft.mp4`）。

**边界**：LLM **$0**、VLM **$0.0007**、网络 **$0**、渲染 172.9 s；DB schema、
**PI 阈值与判定语义**、**corr 度量与仲裁语义**、**motion POLICY 常量**、`mm_*` 冻结栈、词表、
baseline、母片、既有候选**均未改**；`config.json` 仅**追加** `tools.frame_match.bank_derived=true`
（P27-1 授权项，**默认仍 false**）；未做图内元素动画、视频素材接入、句中拆分、改旁白文本、
promotion、发布。**KNOWN_ISSUES #79** 登记派生段绑定阻塞、`//` 缺陷与三指标达成。

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


prepend(R / "STATUS.md", STATUS, "> **Phase 26（四件套收尾）部分完成")
prepend(R / "CHANGELOG.md", CHANGELOG, "## Phase 26 —")
print("三指标: 冻结 {:.1%} | 最长静止 {}s | 开场变化 {} | 全过 {}".format(
    mm["freeze_ratio"], mm["longest_static_s"], mm["opening_changes"], mm["all_pass"]))
