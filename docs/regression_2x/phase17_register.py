# -*- coding: utf-8 -*-
"""Phase 17 登记：STATUS.md / CHANGELOG.md 前插（不改历史条目）。"""
from __future__ import annotations

import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")

STATUS = """> **Phase 17（渲染后核验度量专项）收尾，2026-09-30**：**五景归因 DONE ✔** ｜ **度量 v2 未采纳** ｜
> **P17-3 裁切安全预登记 DONE ✔** ｜ **P17-4 拆长镜提案 DONE ✔（19 条，只备不改）**
> - **P17-1 归因（S02/S06/S07/S08/S13）**：**人工看图 5/5 证实素材确实在屏**（帧包
>   `output/phase17_attr_pack/`）。低 corr **非错配**，是三种**度量伪影**叠加：
>   ① **稀疏线稿在 48×48 下塌陷**（S07/S08/S13）；② **16:9 中心裁切**（S02 竖多面板 1200×1560、
>   S08 885×1033）；③ **运动缩放**（画面=素材子窗口）。**未动阈值、未改门禁**。
>   归因模块 `src/video_studio/ops/corr_diagnostics.py`（纯函数、确定性）；
>   报告 `logs/phase17_attribution.json`。
> - **归因过程中的一处自我更正（如实登记）**：首版 `present_test` 只比"画面 vs 各素材**全图**"，
>   把 S08/S13 误判为 `possible_real_mismatch`（rank 4/5）。改为"同分辨率 + **子窗口库**"后两景证实为在屏。
> - **P17-2 度量 v2（corr_effective = max(全图, 多尺度×网格子窗口)，阈值 0.30 不变）：未采纳**。
>   分离度实测：正集（在屏 5 景）通过 **0/5 → 4/5**；负集（画面 vs 池内其它素材，55 对）
>   误通过 **0/55 → 2/55**（最大 0.3542，来自同一稀疏线稿素材）。
>   **双向门**：正门 **4/5 未达 100%**（S07 0.2766<0.30）⇒ 不过；反门语料**不全**
>   （旧 S05 鲨鱼照等错配素材在本仓**不存在**，仅存文件名/哈希）⇒ 亦不过。
>   依授权书「任一门不过 ⇒ 不采纳」，**未落地 corr_metric=v2、未改任何门禁**。
>   证据 `logs/phase17_metric_v2_experiment.json`、`logs/phase17_metric_prototype.json`。
> - **P17-3**：`crop_safety` 对全部 12 张池素材计算；**2 张标记 `low_crop_safety`**
>   （`5144139591a0` 0.0906、`a3f0e27204cd` 0.1397，均为 P16-3 获取）⇒ 短名单**降权**、
>   **不硬拒**；登记 `logs/phase17_crop_safety_registry.json`（Phase 16 两张失真素材已留档）。
> - **P17-4**：按 DQ-3 口径生成 **19 条** 6-B `split_scene` 提案（目标 ≤35s，拆分点取**旁白句边界**，
>   两侧**素材继承** ⇒ DQ-2 不变），登记 `logs/phase17_split_proposals.json`；**不执行、不渲染**。
> - 测试：新增 `tests/corr_diagnostics_test.py`（诊断函数 + **双向验证运行器**）**19/19 通过**。
> - 边界：LLM **$0**、VLM **$0**、网络 **0**；`config.json`/DB schema/`mm_*` 冻结栈/词表/baseline/
>   **PI 门禁逻辑**/执行链**均未改**；**未渲染、未执行拆镜、未放宽任何阈值**。
> - 详见 `docs/regression_2x/PHASE17_REPORT.md`

"""

CHANGELOG = """## Phase 17 — 渲染后核验度量专项：五景归因（5/5 在屏）、v2 未采纳、裁切安全预筛、19 条拆镜提案（2026-09-30）

**P17-1 五景归因 DONE。** 新增纯函数模块 `src/video_studio/ops/corr_diagnostics.py`（裁切/密度/运动/字幕/
区域最优匹配五假设 + `present_test` 同分辨率 argmax 判定）。对象：Phase 16 渲染后核验门失败的
S02/S06/S07/S08/S13。**人工看图 5/5 证实素材确实在屏**（帧包 `output/phase17_attr_pack/<景>/{frame_10,50,90,asset}.png`）。
结论：低 corr **非错配**，为三种**度量伪影**：① **稀疏线稿在 48×48 下塌陷**（S07/S08/S13）；
② **16:9 中心裁切**（S02 1200×1560 竖多面板、S08 885×1033）；③ **运动缩放**（画面=素材子窗口）。
归因报告 `logs/phase17_attribution.json`。**未动阈值、未改门禁**。
**一处自我更正（如实登记）**：首版 `present_test` 仅比较"画面 vs 各素材**全图**"，把 S08/S13 误判为
`possible_real_mismatch`（rank 4/5）；改为"同分辨率 + **子窗口库**"后两景证实为在屏。

**P17-2 度量 v2：未采纳。** 候选 `corr_effective = max(corr_res48(全图,画面), max over 尺度{1.0,0.8,0.6,0.45,0.35}×5×5 网格
的 corr_res48(画面, 素材 16:9 子窗口))`，**阈值 0.30 不变**。分离度实测：正集（在屏 5 景）通过 **0/5 → 4/5**；
负集（画面 vs 池内其它素材，55 对）误通过 **0/55 → 2/55**（最大 0.3542，同一稀疏线稿素材）。
**双向门（运行前写死）**：正门需 100% PASS ⇒ 实测 4/5（S07 0.2766<0.30）**不过**；
反门需已知错配 100% FAIL ⇒ 冻结语料**不全**（旧 S05 鲨鱼照等素材在本仓不存在，仅存文件名/哈希）**不过**。
依授权书「任一门不过 ⇒ 不采纳，如实报告」，**未落地 corr_metric=v2、未改任何门禁、阈值仍 0.30**。
证据 `logs/phase17_metric_v2_experiment.json`、`logs/phase17_metric_prototype.json`。
建议下阶段：提高分辨率（如 192）重验同一 bank 形式 / 引入边缘图或结构相似口径 / **补齐反门语料**后再裁定。

**P17-3 裁切安全预筛 DONE。** `crop_safety = corr_48(全图, scale=1920:1080:force_original_aspect_ratio=increase,
crop=1920:1080)` 对全部 12 张池素材计算；**2 张 <0.30 标记 `low_crop_safety`**
（`5144139591a0` 0.0906、`a3f0e27204cd` 0.1397，均 P16-3 获取）⇒ 短名单**降权、不硬拒**（人工仍可选）。
登记 `logs/phase17_crop_safety_registry.json`；Phase 16 两张失真素材已随表留档。

**P17-4 拆长镜提案 DONE（只备不改）。** 按 DQ-3 口径（`max_hold_s=25s`）对 >35s 场景生成
**19 条** 6-B `split_scene` 格式提案（覆盖 S02–S19、S21），拆分点取**旁白句边界**（无边界则均分），
每条附拆分窗口、**两侧素材继承**（DQ-2 复用关系不变）与 DQ-2/DQ-3 预期影响。
登记 `logs/phase17_split_proposals.json`；`execution.executed=false` ⇒ **不执行、不渲染**。

**测试**：新增 `tests/corr_diagnostics_test.py`（覆盖诊断函数性质 + **P17-2 双向验证运行器**）**19/19 通过**。

**边界**：LLM **$0**、VLM **$0**、网络 **0**；`config.json`、DB schema、`mm_*` 冻结栈、词表、baseline、
**PI 门禁逻辑**、执行链**均未改**；**未渲染成片、未执行拆镜、未放宽任何阈值**。

"""


def prepend(path: pathlib.Path, block: str, anchor: str):
    t = path.read_text(encoding="utf-8")
    if "Phase 17" in t[:7000]:
        print("已含 Phase 17，跳过:", path.name)
        return
    i = t.find(anchor)
    path.write_text((t[:i] + block + t[i:]) if i >= 0 else (block + t), encoding="utf-8")
    print("已前插:", path.name)


prepend(R / "STATUS.md", STATUS, "> **Phase 16（素材池扩充）收尾")
prepend(R / "CHANGELOG.md", CHANGELOG, "## Phase 16 —")
