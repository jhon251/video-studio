# -*- coding: utf-8 -*-
"""Phase 28 登记：KNOWN_ISSUES #79 处置更新 + #80（末段画面异常）+ STATUS/CHANGELOG。"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")
v = json.loads((L / "phase27_p27_3_verification.json").read_text(encoding="utf-8"))
mm = v["motion_metrics"]

# ---------- #79 处置更新 ----------
p = R / "docs" / "KNOWN_ISSUES.md"
t = p.read_text(encoding="utf-8")
OLD = ("## 79. Phase 27：**派生段素材绑定未落到渲染**（阻塞交付级候选）"
       "+ v2 运动滤镜 `//` 缺陷 — `OPEN`")
NEW = ("## 79. Phase 27 → **Phase 28 已修复**：派生段绑定回退已落到生产路径"
       "（失败 17→4）；`//` 滤镜缺陷已修 — `RESOLVED`")
if OLD in t:
    t = t.replace(OLD, NEW, 1)
UP = """
### 79.4 处置更新（**Phase 28 已修复**，2026-10-01）
**根因比原判断更深**：`_build_material_timeline` **丢弃了脚本自带的 `scene_id`**，
改用序号合成 `S{i+1}` ⇒ 40 段派生脚本的 `S02p1…` 变成 `S01…S40`
⇒ **决策按合成 id 落库、闸门按派生 id 查**，两边 id 空间不一致。
（Phase 27 的 `checked 2/40` 即来源：只有 id 形式恰好相同的 `S01`/`S20` 蒙对。）

**修复（最小改动，不动 DB 写入路径）**：① **保留真实 id**
（`script_scene_id`/`parent_scene_id`/`bind_scene_id`；**裁决仍用合成 id** ⇒ 既有选材/分类语义逐字不变）；
② **父景绑定回退**（内存表 `parent_asset`，不写 DB）：派生段解析不到素材时按 `parent_scene_id`
回退到父景绑定并标记 `binding_source="parent_fallback"`；**无父景绑定 ⇒ 保持原状（fail-closed）**。

**实测效果**：逐景 `checked` **2/40 → 40/40**｜失败 **17 → 4**｜
DQ-2 `max_asset_share` **0.9369 → 0.3638**（阈值 0.35，仅差 **+0.0138**）、`unique_assets` **3 → 11**；
三指标 **15.2%/6.0s/69 → 11.9%/6.0s/82**（保持全过且更好）。

**v2 运动滤镜 `//` 缺陷**：已改 `floor(a/b)`，40/40 滤镜通过；另修正一处**Python 侧误用 `floor()`**
（`//` 在 Python 合法、只在发给 ffmpeg 的字符串里不合法）。

### 79.5 §0 教训入制（流程守卫，Phase 28 新增）
**规则**：任何"修复类"交付**必须在生产路径上加探针测试**；仅"模块 + 离线脚本验证"**不算落地**。
本会话已两次踩坑（Phase 22 bank 修复未接入调用点；Phase 21 绑定展开只做在离线脚本）
⇒ 均表现为"产物在位但未接入"。
**落地**：修复类测试必须**穿过生产调用点**并覆盖 **fail-closed 分支**；
修复类报告必须写明"生产路径探针测试"的位置。
"""
if "79.4" not in t:
    t = t.rstrip() + "\n" + UP

KI80 = """
---

## 80. Phase 28：末段/近末段画面异常（**深色背景 / 纯深蓝画面**）— `OPEN`

**发现（Phase 28，仲裁层 VLM 逐景核验直接读出）**：
| 景 | corr | VLM | 理由（原文节选） |
|---|---|---|---|
| **S18p1** | 0.055 | absent | 「**成片帧仅为深色背景加一行字幕**，无任何代码、图表或界面元素」 |
| **S21p2** | 0.000 | absent | 「**成片帧为纯深蓝色画面**，无任何文字、图案或结构特征」 |
| **S21p1** | None | （未调用） | — |
| S14p1 | 0.209 | absent | 「成片帧为数学分支结构图，素材为邮票标签，二者无任何重合」 |

**性质**：这是**真实渲染内容缺陷**（画面不含素材、几近纯色），**不是绑定/度量口径问题**
（绑定回退已修，`checked` 达 40/40）。**S21p1/S21p2 为全片末段**，
**疑与 40 段时基下最后几段的素材窗口/时长边界有关**（末段 `end_s` 被延长到 `cursor+2.0`）。
**建议**：下一阶段专项定位（抽查末段抽帧 + 检查时间轴末段窗口与素材可用性）。

**同阶段澄清**：另有 4 景（S04p1/S10p2/S11p1/S11p2，corr 0.250–0.299 略低于 0.30）
被 VLM 判 **present** 并**放行** —— 属**度量阈值下的正常边缘**（bank 口径 + 仲裁兜底按设计工作），
**不是缺陷**。
"""
if "## 80." not in t:
    t = t.rstrip() + "\n" + KI80
p.write_text(t, encoding="utf-8")
print("KNOWN_ISSUES #79 → RESOLVED（含 §0 教训入制）；#80 已登记")

STATUS = """> **Phase 28（绑定回退 + cap=2 收尾 + 交付级候选）收尾，2026-10-01 —— #79 已修复；门仍 fail-closed（4 景）⇒ 未登记交付级候选**
> **P28-1 绑定回退 DONE ✔（根因比授权书判断更深）｜P28-2 NOT_EXECUTED｜P28-3 已渲染但门未过｜P28-4/P28-5 NOT_EXECUTED**
> - **§0 教训入制（流程守卫，本阶段新增）**：**任何"修复类"交付必须在生产路径上加探针测试**；
>   仅"模块 + 离线脚本验证"**不算落地**。本会话已两次踩坑（Phase 22 bank 修复未接入调用点；
>   Phase 21 绑定展开只做在离线脚本）⇒ 均表现为"**产物在位但未接入**"。
>   修复类测试必须**穿过生产调用点**并覆盖 **fail-closed 分支**；修复类报告须写明探针位置。
> - **P28-1 根因（比授权书判断更深）**：`_build_material_timeline` **丢弃脚本自带 `scene_id`**、
>   改用序号合成 `S{i+1}` ⇒ 40 段派生脚本的 `S02p1…` 变成 `S01…S40`
>   ⇒ **决策按合成 id 落库、闸门按派生 id 查**，两边 id 空间不一致
>   （Phase 27 的 `checked 2/40` 即来源：只有 `S01`/`S20` 蒙对）。
>   **修复**：① 保留真实 id（`script_scene_id`/`parent_scene_id`/`bind_scene_id`；
>   **裁决仍用合成 id** ⇒ 既有选材/分类语义逐字不变）；② **父景绑定回退**（内存表，不写 DB）：
>   派生段解析不到素材 ⇒ 按 `parent_scene_id` 回退父景绑定、标 `binding_source="parent_fallback"`；
>   **无父景绑定 ⇒ 保持原状（fail-closed）**。③ `_bank_derived` 门控语义不变。
> - **实测净收益（如实量化）**：逐景 `checked` **2/40 → 40/40**｜失败 **17 → 4 景**｜
>   DQ-2 `max_asset_share` **0.9369 → 0.3638**（阈值 0.35，**仅差 +0.0138**）、`unique_assets` **3 → 11**｜
>   三指标 **15.2%/6.0s/69 → 11.9%/6.0s/82**（保持全过且更好）。
> - **P28-3 终渲染**：沙箱 `p_ddb17cfbacf8`、`t_5f76c2d95573`、**177.0 s**；成片 **44,535,732 B**
>   （**未登记 `render_output`**）；**运动 40/40、0 fallback**。
>   **已过门**：时长 **977.88s** ✔｜响度 **−16.1 LUFS / −2.5 dBTP** ✔｜PI 前/后全 PASS、
>   `promote_blocked=False` ✔｜字幕 `SUBTITLE_ALIGNED`（171 cue、语音内 1.0、越界 0s）✔｜
>   MOTION_VERIFIED ✔｜**三指标 11.9%/6.0s/82 全过** ✔（阈值不变）。
> - **仍阻断（4 景，真实内容问题，非绑定问题）**：仲裁层 **4 放行 / 4 阻断** ——
>   放行（VLM 判 present）：S04p1 0.277、S10p2 0.299、S11p1 0.250、S11p2 0.286（**边缘属正常**）；
>   阻断（VLM 判 absent）：**S14p1** 0.209（分支图 vs 邮票）、
>   **S18p1** 0.055「**深色背景加一行字幕**」、**S21p1**（未调用）、
>   **S21p2** 0.000「**纯深蓝色画面**」⇒ **S21p1/S21p2 为全片末段，疑与 40 段时基末段窗口有关**，
>   **登记 KNOWN_ISSUES #80** 留待专项定位。
>   **DQ-2** `0.3638 > 0.35` ⇒ FAIL（**差 +0.0138**，正是 `cap=2` 要解决的复用集中度）；
>   **DQ-3** `share 0.45 / max 36.836s` ⇒ 显著改善但未达 ≤20%（报改善、不报 PASS）。
> - **P28-2 NOT_EXECUTED**：受治理获取（**网络用量 0/6**）与 `cap=2` 分配未做；错配排除保持。
>   **H7 片尾卡 NOT_EXECUTED**。
> - **P28-4/P28-5 NOT_EXECUTED**（依预算纪律：渲染证据与阻塞诊断优先）。
>   已知最近完整跑：**Phase 25 = 81/81 rc=0**。本阶段相关套件全绿：
>   `motion_metrics_test` 28/28、`motion_guard_test` 27/27、`corr_metric_diagnostics_test` 29/29、
>   `material_taxonomy_test` 40/40、`visual_binding_test` 38/38、40 景 crop 滤镜 0 失败；
>   `motion_test` 21/22（唯一失败 `5b` 为**环境项**：`render_motion.json` 在场时"默认解析⇒off"必然不成立）。
> - 边界：LLM **$0**、VLM **$0.0049**、网络 **$0**、渲染 177.0s；DB schema/**PI 阈值与判定语义**/
>   **corr 度量与仲裁语义**/**motion POLICY 常量**/`mm_*`/词表/baseline/母片/既有候选**均未改**；
>   `config.json` 仅保留 Phase 27 授权的 `bank_derived=true`；未做图内元素动画、视频素材、句中拆分、
>   改旁白、promotion、发布。
> - 详见 `PHASE28_REPORT.md`；**KNOWN_ISSUES #79 → RESOLVED**（含 §0 教训入制）；新增 **#80**。

"""

CHANGELOG = """## Phase 28 — 绑定回退（#79）修复：核验失败 17→4、DQ-2 0.9369→0.3638；门仍 fail-closed（4 景）致未登记交付级候选（2026-10-01）

**§0 教训入制（流程守卫，本阶段新增）。** **规则：任何"修复类"交付必须在生产路径上加探针测试**；
仅"模块 + 离线脚本验证"**不算落地**。**为什么**：本会话已两次踩坑——Phase 22 的 bank 口径修复
（模块与双门证据都在，但 `_verify_scene_frames` 从未引用 ⇒ Phase 20 在 40 段上 33 处误报）、
Phase 21 的"绑定展开"（只做在**离线复验脚本**里 ⇒ Phase 27 逐景 `checked 2/40`、17 景失败）
——均表现为"**产物在位但未接入生产链**"。**落地**：修复类测试必须**穿过生产调用点**并覆盖
**fail-closed 分支**；修复类报告必须写明"生产路径探针测试"的位置（本次示例：绑定回退测试走
`EditingAgent._build_material_timeline`）。

**P28-1 绑定回退 DONE（根因比授权书判断更深）。** 授权书假设「闸门按派生 id 查不到 ⇒ 按
`parent_scene_id` 回退查绑定」；**实测根因更深**：`_build_material_timeline` **在 L167 丢弃了脚本
自带的 `scene_id`**、改用**序号合成** `scene_id = "S{:02d}".format(i+1)` ⇒ 40 段派生脚本的
`S02p1…` 被替换成 `S01…S40` ⇒ **决策按合成 id 落库、闸门按派生 id 查**，两边 id 空间不一致
（Phase 27 的 `checked 2/40` 即来源：只有 id 形式相同的 `S01`/`S20` 蒙对）。
**修复（最小改动，不动 DB 写入路径）**：① **保留真实 id**
（新增 `script_scene_id`/`parent_scene_id`/`bind_scene_id`；**裁决仍用合成 `scene_id`**
⇒ 既有选材/分类语义**逐字不变**；timeline 行改用 `bind_scene_id` 并附
`scene_id_synthetic`/`parent_scene_id`/`binding_source` 供审计）；
② **父景绑定回退**（**内存表** `parent_asset`，**不写 DB**）：派生段解析不到素材时按
`parent_scene_id` 回退到父景绑定（同一素材、两侧继承），标记 `binding_source="parent_fallback"`
并写 `fallback_reason`；**无父景绑定可回退 ⇒ 保持原状（fail-closed）**；
③ `_bank_derived` 门控语义不变（Phase 26 §0 已双门验证）。

**实测净收益（如实量化）**：逐景 `checked` **2/40 → 40/40**；失败 **17 → 4 景**；
DQ-2 `max_asset_share` **0.9369 → 0.3638**（阈值 0.35，**仅差 +0.0138**）、
`unique_assets` **3 → 11**；三指标 **15.2%/6.0s/69 → 11.9%/6.0s/82**（保持全过且更好）。
附带修正：v2 运动滤镜的 `//`（ffmpeg 不支持）→ `floor(a/b)`；并修正一处**Python 侧误用 `floor()`**
（`//` 在 Python 合法、仅发给 ffmpeg 的字符串里不合法）。

**P28-3 终渲染：已执行，门仍 fail-closed。** 沙箱 `p_ddb17cfbacf8`、任务 `t_5f76c2d95573`、
**177.0 s**；成片 `projects/p_ddb17cfbacf8/output/t_5f76c2d95573_draft.mp4`（**44,535,732 B**），
**未登记 `render_output`**（fail-closed）。**运动 40/40 启用、0 fallback**。
**已过门**：时长 **977.88s**（978.7±1 ✔）｜响度 **−16.1 LUFS / −2.5 dBTP** ✔｜
PI 渲染前/后全 PASS 且 `promote_blocked=False` ✔｜字幕 `SUBTITLE_ALIGNED`
（171 cue、语音内 1.0、越界 0s）✔｜MOTION_VERIFIED ✔｜**三指标 11.9% / 6.0s / 82 次全过** ✔（阈值不变）。
**仍阻断 4 景（真实内容问题，非绑定问题）**：仲裁层 **4 放行 / 4 阻断** ——
放行（VLM 判 `present`）：S04p1 0.277、S10p2 0.299、S11p1 0.250、S11p2 0.286（**边缘属正常**，
bank 口径 + 仲裁兜底按设计工作）；阻断（VLM 判 `absent`）：**S14p1** 0.209（分支图 vs 邮票）、
**S18p1** 0.055「**深色背景加一行字幕**」、**S21p1**（未调用）、**S21p2** 0.000「**纯深蓝色画面**」
⇒ **S21p1/S21p2 为全片末段，疑与 40 段时基下末段窗口/时长边界有关**，**登记 KNOWN_ISSUES #80**。
**DQ-2** `0.3638 > 0.35` ⇒ FAIL（**差 +0.0138**，正是 `cap=2` 要解决的复用集中度）；
**DQ-3** `share 0.45 / max 36.836s` ⇒ 显著改善但未达 ≤20%（报改善、不报 PASS）。

**P28-2 / P28-4 / P28-5：NOT_EXECUTED。** 受治理获取（**网络用量 0/6**）与 `cap=2` 分配未做
（错配排除保持生效）；H7 片尾卡未执行；三版材料包与**完整回归**未执行
（依授权书**预算纪律**：渲染证据与阻塞诊断优先）。已知最近一次完整跑：**Phase 25 = 81/81 rc=0**。
**本阶段相关套件实测**：`motion_metrics_test` **28/28**、`motion_guard_test` **27/27**、
`corr_metric_diagnostics_test` **29/29**、`material_taxonomy_test` **40/40**、
`visual_binding_test` **38/38**、40 景 crop 滤镜 **0 失败**；
`motion_test` **21/22**（唯一失败 `5b` 为**环境项**：`render_motion.json` 在场时
"默认解析 ⇒ off"必然不成立，Phase 13 起即为已知环境依赖）。

**依授权书**：全门过才登记交付级候选；本轮 **fail-closed ⇒ 如实 STOP**，
**P19 21 景版自动转正**（`projects/p_50e10b27b44d/output/t_a4d8c1aafd04_draft.mp4`）。

**边界**：LLM **$0**、VLM **$0.0049**、网络 **$0**、渲染 177.0 s；DB schema、
**PI 阈值与判定语义**、**corr 度量与仲裁语义**、**motion POLICY 常量**、`mm_*` 冻结栈、词表、
baseline、母片、既有候选**均未改**；`config.json` 仅保留 Phase 27 授权的
`tools.frame_match.bank_derived=true`；未做图内元素动画、视频素材接入、句中拆分、改旁白文本、
promotion、发布。**KNOWN_ISSUES #79 → RESOLVED**（含 §0 教训入制）；新增 **#80**（末段画面异常）。

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


prepend(R / "STATUS.md", STATUS, "> **Phase 27（底片组装")
prepend(R / "CHANGELOG.md", CHANGELOG, "## Phase 27 —")
print("三指标: 冻结 {:.1%} | 最长静止 {}s | 开场变化 {} | 全过 {}".format(
    mm["freeze_ratio"], mm["longest_static_s"], mm["opening_changes"], mm["all_pass"]))
print("DQ-2: state={} share={} unique={}".format(
    v["dq2"]["state"], v["dq2"]["max_asset_share"], v["dq2"]["unique_assets"]))
