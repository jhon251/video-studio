# -*- coding: utf-8 -*-
"""校正 Phase 17 登记文本：区分「机器归因」与「人工目视」两种口径（不改历史）。"""
from __future__ import annotations

import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")

OLD_1 = ("> - **P17-1 归因（S02/S06/S07/S08/S13）**：**人工看图 5/5 证实素材确实在屏**（帧包\n"
         ">   `output/phase17_attr_pack/`）。低 corr **非错配**，是三种**度量伪影**叠加：\n")
NEW_1 = ("> - **P17-1 归因（S02/S06/S07/S08/S13）**：**机器归因**（同分辨率 argmax）确认 **S02/S06/S07 在屏**\n"
         ">   （`sampling_artifact`×2 / `crop_artifact`×1），对 **S08/S13 报 `possible_real_mismatch`**\n"
         ">   （依授权书**不得**裁定为在屏）；**人工帧包目视**（`output/phase17_attr_pack/`）显示 S08/S13 画面\n"
         ">   即被分配素材的**裁切/放大局部**（差异已定位：`present_test` 以「画面 vs 素材**全图**」比较，对局部化画面失效）。\n"
         ">   低 corr 的三种**度量伪影**：\n")

OLD_2 = ("> - **归因过程中的一处自我更正（如实登记）**：首版 `present_test` 只比\"画面 vs 各素材**全图**\"，\n"
         ">   把 S08/S13 误判为 `possible_real_mismatch`（rank 4/5）。改为\"同分辨率 + **子窗口库**\"后两景证实为在屏。\n")
NEW_2 = ("> - **两种口径的差异已并列登记，不互相覆盖**：机器口径（argmax）只确认 3 景在屏；\n"
         ">   人工目视确认 S08/S13 为同图局部。本阶段**不把 S08/S13 记为「已证实在屏」**（`possible_real_mismatch` 的裁定禁区）。\n")

OLD_3 = ("**P17-1 五景归因 DONE。** 新增纯函数模块 `src/video_studio/core/corr_diagnostics.py`（裁切/密度/运动/字幕/\n"
         "区域最优匹配五假设 + `present_test` 同分辨率 argmax 判定）。对象：Phase 16 渲染后核验门失败的\n"
         "S02/S06/S07/S08/S13。**人工看图 5/5 证实素材确实在屏**（帧包 `output/phase17_attr_pack/<景>/{frame_10,50,90,asset}.png`）。\n"
         "结论：低 corr **非错配**，为三种**度量伪影**：① **稀疏线稿在 48×48 下塌陷**（S07/S08/S13）；\n"
         "② **16:9 中心裁切**（S02 1200×1560 竖多面板、S08 885×1033）；③ **运动缩放**（画面=素材子窗口）。\n"
         "归因报告 `logs/phase17_attribution.json`。**未动阈值、未改门禁**。\n"
         "**一处自我更正（如实登记）**：首版 `present_test` 仅比较\"画面 vs 各素材**全图**\"，把 S08/S13 误判为\n"
         "`possible_real_mismatch`（rank 4/5）；改为\"同分辨率 + **子窗口库**\"后两景证实为在屏。\n")
NEW_3 = ("**P17-1 五景归因 DONE。** 新增纯函数模块 `src/video_studio/core/corr_diagnostics.py`（裁切/密度/运动/字幕/\n"
         "区域最优匹配五假设 + `present_test` 同分辨率 argmax 判定）。对象：Phase 16 渲染后核验门失败的\n"
         "S02/S06/S07/S08/S13。**机器归因**：S02/S06/S07 = `sampling_artifact`/`crop_artifact`（同分辨率 argmax，确认在屏）；\n"
         "**S08/S13 = `possible_real_mismatch`**（rank 4/12、5/12；依授权书不得裁定为在屏）。\n"
         "**人工帧包目视**（`output/phase17_attr_pack/<景>/{frame_10,50,90,asset}.png`）显示 S08/S13 画面\n"
         "即被分配素材的**裁切/放大局部**（S08=欧拉四边形图 Fig.7 裁掉 D/F；S13=Lean UI 右侧被放大）。\n"
         "**两种口径差异已定位**：`present_test` 以「画面 vs 素材**全图**」比较 ⇒ 对**局部化画面失效**（argmax 偏向其它稀疏线稿）。\n"
         "低 corr 的三种**度量伪影**：① **稀疏线稿在 48×48 下塌陷**（S07/S08/S13）；\n"
         "② **16:9 中心裁切**（S02 1200×1560 竖多面板、S08 885×1033）；③ **运动缩放**（画面=素材子窗口）。\n"
         "归因报告 `logs/phase17_attribution.json`；分布 `{crop_artifact:1, sampling_artifact:2, possible_real_mismatch:2}`。\n"
         "**未动阈值、未改门禁**。\n")

for name in ("STATUS.md", "CHANGELOG.md"):
    p = R / name
    t = p.read_text(encoding="utf-8")
    n = 0
    for a, b in ((OLD_1, NEW_1), (OLD_2, NEW_2), (OLD_3, NEW_3)):
        if a in t:
            t = t.replace(a, b)
            n += 1
    p.write_text(t, encoding="utf-8")
    print("{}: 替换 {} 处".format(name, n))
