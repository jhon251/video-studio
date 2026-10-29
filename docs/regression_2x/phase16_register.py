# -*- coding: utf-8 -*-
"""Phase 16 登记：STATUS.md / CHANGELOG.md 前插（未改历史条目）。"""
from __future__ import annotations

import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")

STATUS = """> **Phase 16（素材池扩充）收尾，2026-09-30**：§1 DONE ✔ ｜ **P16-1 负例过滤器验证 FAIL**（误杀 13/24=54.17%、
> 捕获 11/20=55%）⇒ 按授权书**回退人工短名单、过滤器不接线** ｜ **P16-2 登记 DONE**（只登记有许可记录的 2 张 H5 素材，零推断）
> ｜ **P16-3 受治理获取 DONE**（仅 Wikimedia，8 请求，**4 张 VERIFIED**，许可门逐张不放宽）｜ **P16-4 S03 重选 DONE**
> （扩池后选材重解，S03 换为 `432cd85be6f1`，成片 corr 0.569 ⇒ **13-E 线稿盲区消除**）｜
> **P16-5 重渲染已执行但渲染后核验门阻断**（沙箱 `p_32aded38172b`，173s，失败 5 景）⇒ **未登记交付级候选**。
> - **池扩充 6 → 12 张唯一图像**；引擎选材 **5 种 → 12 种**；**DQ-2 由 FAIL 转 PASS**（最大复用 10 景 → **5 景**）
> - **新发现（有证据）**：新增素材中 2 张"多面板/竖构图"在 1920×1080 模板**中心裁切**下失真
>   （corr(全图, 裁切画面) = 0.140 / 0.091 < 0.30）⇒ 渲染后核验门按设计判失败；**人工看图证实素材确实在屏**
>   （S02 成片帧正是被分配素材，仅被裁掉中间两个面板）。**未调阈值、未改模板**。证据 `logs/phase16_crop_safety.json`
> - S06/S07/S13 另有来源（其素材裁切安全度 0.72/0.92/0.76 却仍失败）⇒ **未归因，如实登记，留待下阶段专项定位**
> - **DQ-3 仍 FAIL 且不可由换素材修复**：21/21 景时长 30.3–67.4s 全部超 25s 上限 ⇒ 需**拆分长镜**（6-B `split_scene`），
>   **不在本次授权范围**
> - 边界：LLM **$0**、VLM **$0.0131**（≤$1）、网络**仅 Wikimedia 8 次**且逐请求留痕；**未放宽许可门**、
>   **未用机器 RELEVANT 放行任何绑定**、**未跳过人工短名单**、**未自动 promotion**；`config.json`/阈值/判定逻辑/冻结栈**均未改**
> - 详见 `docs/regression_2x/PHASE16_REPORT.md`

"""

CHANGELOG = """## Phase 16 — 素材池扩充：池 6→12、DQ-2 转 PASS；P16-1 过滤器 FAIL（回退人工短名单）；P16-5 渲染后核验门阻断（2026-09-30）

**P16-1 负例过滤器验证（硬门）：FAIL。** 冻结评测集 `tests/fixtures/p16_negative_filter_eval_v1.json`
（sha256 `fceeae24b6ee9e44…`）= **负例 20**（人工 3 + 已知陷阱 10 + **构造跨景 7**）+ **误杀测试集 24**（真值集全部正例）。
达标线**运行前写死**（捕获率 ≥60%、误杀率 ≤5%、每条 DENY 附理由）。真实 VLM 实测：
**负例捕获 11/20 = 55.00%（FAIL）**、**正例误杀 13/24 = 54.17%（FAIL）**、DENY 全部附理由 ✔、成本 $0.0131。
**关键发现**：误杀 13 条与 P14-2 门禁失配（24 正例中机器判 IRRELEVANT 亦 13 条）**是同一统计量**
⇒ "作负例过滤器"与"≥90% 一致"**互斥**（同一根因 KNOWN_ISSUES #73）。**未调参救援**（误杀 13>允许 1，
后验阈值调整属运行后调参）。**回退路径**：P16-3 预筛 = **人工短名单（provider 元数据）**，过滤器**不接线**。

**P16-2 本地素材登记（零网络/零推断）：DONE。** 只登记 Phase 12 覆盖层**已有许可记录**的素材 ⇒
登记 **2 张**（`Russell_PM_1+1=2.png` PD-US；`S11-D0_…p08_tactic-state-rw.png` CC BY 4.0），
文件入 `projects/p_96efdc03e1aa/media/registered/` 并复核 sha256 一致；**未登记 15 张**（无许可记录，
逐条留原因）。台账 `logs/phase16_local_registry.json`。

**P16-3 受治理获取（P7-5 路径，仅 Wikimedia）：DONE。** 目标 = DQ-2/DQ-3 点名场景 S03/S06/S07；
**8 次网络请求 / 失败 0**；**4 张 VERIFIED**（`ScienceOfMathematicsComte.jpg` PD；`Jensen's Inequality…` CC BY-SA 4.0；
`Euler proof…` CC0；`Comparison of simple power law curves…` CC BY-SA 4.0）；许可门**逐张不放宽**
（候选许可分布 PD 25 / FREE 31，被拒均为 `ASSET_OVERSIZE`(>8MiB) 与 `ASSET_DANGEROUS_FILENAME`）。
**池 6 → 12 张唯一图像**。逐请求留痕 `logs/phase16_acquisition_ledger.json`。

**P16-4 S03 重选：DONE（扩池后选材重解）。** 不硬编码指定，把全部 12 张作为候选池让引擎**确定性重解**：
S03 由 13-E 的稀疏线稿（corr 0.153，13-E 阻断根因）换为 `432cd85be6f1`，**成片 corr 0.569 ⇒ 达标**，
**13-E 线稿盲区消除**。选材多样性 **5 → 12 种**，单素材最大复用 **10 → 5 景**。

**P16-5 交付级重渲染：已执行，渲染后核验门阻断。** 沙箱 `p_32aded38172b` / 任务 `t_8364252d64f1`，
**173 s**；运动 `enabled=true`；派生脚本文本零改动。候选 `t_8364252d64f1_draft.mp4`（39,946,220 B），
**未登记 `render_output`/`attribution`**（fail-closed）⇒ 非交付物。**失败 5 景**：
S02(0.122)/S06(0.242)/S07(0.078)/S08(0.058)/S13(0.006)（`frame_pearson_48x48, min_corr=0.30`）。
**根因（独立复核 + 人工看图）**：1920×1080 模板**中心裁切** vs 全图 —— 2 张**多面板/竖构图**素材
`a3f0e27204cd`(1200×1560)、`5144139591a0`(885×1033) 的 `corr(全图, 裁切画面)` = **0.140 / 0.091**（<0.30）；
**人工看图证实素材确实在屏**（S02 成片帧即被分配素材，仅裁掉中段）。**未调阈值、未改模板**。
S06/S07/S13 另源（其素材裁切安全度 0.72/0.92/0.76）⇒ **未归因，如实登记**。

**DQ 复算（生产度量，同口径对比 13-E）**：唯一素材 **5→12**；**DQ-2 FAIL → PASS**（最大复用 10→5 景）；
**DQ-3 仍 FAIL**（max_hold 67.374s，21/21 景超 25s 上限）且**不可由换素材修复** ⇒ 需拆分长镜（6-B），
**不在本次授权范围**。**未达成"交付级候选" ⇒ 未登记、零 promotion。**

**边界**：LLM **$0**、VLM **$0.0131**（≤$1）、网络**仅 Wikimedia 8 次**且逐请求记账；`config.json`、DB schema、
PI/DQ 阈值与判定逻辑、`mm_*` 冻结栈、词表、baseline、6-B 执行链语义、frozen 真值（只读引用）**均未改**；
**未放宽许可门**、**未用机器 RELEVANT 放行任何绑定**、**未跳过人工短名单**、**未自动 promotion**。

"""


def prepend(path: pathlib.Path, block: str, anchor: str):
    t = path.read_text(encoding="utf-8")
    if "Phase 16" in t[:6000]:
        print("已含 Phase 16，跳过:", path.name)
        return
    i = t.find(anchor)
    if i < 0:
        path.write_text(block + t, encoding="utf-8")
        print("前插文件头:", path.name)
    else:
        path.write_text(t[:i] + block + t[i:], encoding="utf-8")
        print("前插于 anchor 前:", path.name)


prepend(R / "STATUS.md", STATUS, "> **Phase 14（VLM 视觉相关性判定）")
prepend(R / "CHANGELOG.md", CHANGELOG, "## Phase 14 —")
