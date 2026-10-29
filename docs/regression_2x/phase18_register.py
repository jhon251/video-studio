# -*- coding: utf-8 -*-
"""Phase 18 登记：STATUS.md / CHANGELOG.md 前插（不改历史条目）。"""
from __future__ import annotations

import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")

STATUS = """> **Phase 18（度量收口）收尾，2026-09-30**：**P18-1 present_test 修复 DONE ✔（4/5，未达 5/5，如实登记）** ｜
> **P18-2 corr v3 未采纳（双门未全过）** ｜ **P18-3 VLM 在屏核验层达标 ⇒ 已落地为仲裁层** ｜ **P18-4 登记 DONE ✔**
> - **P18-1（真 bug）**：`present_test` 比较基准由「画面 vs 素材**全图**」改为**多尺度 16:9 子窗口 bank**
>   （`core/corr_diagnostics.py::bank_score`）；**S08 rank 4→1、S13 rank 5→1**（证实全图口径是 bug）。
>   **但未达"五景全在屏"（4/5）**：**S07 由 argmax 退化为 rank 4**（bank 最佳 0.2766，
>   低于误导素材 `301ff850be9c` 的 0.352）⇒ 因多面板素材的子窗口只覆盖局部。**未调参补救、未掩盖**。
> - **P18-2 corr v3：未采纳**。变体实测（阈值 0.30 不变，双门运行前写死）：
>   `bank192` 正门 3/5·反门 **0/55**；**`edge192` 正门 5/5 但反门 35/55 ⇒ 边缘口径无区分力，否决**；
>   最佳 `max(bank48,bank192)` **正门 4/5·反门 2/55**（唯一失分 S07；2 条误通过均来自 `301ff850be9c`）。
>   ⇒ 双门未全过 ⇒ **未落地 v3、未改门禁、阈值仍 0.30**。
>   **LIMITATION（登记）**：反门语料**仅构造错配** —— 旧 S05 鲨鱼照等真实错配素材在本仓**不存在**
>   （全盘检索无该文件，仅存文件名/哈希）；**未以此为由放宽反门**。
> - **P18-3 VLM 在屏核验层：达标 ⇒ 已落地为仲裁层**。任务 = **视觉存在性**（"帧里在不在该素材"，
>   允许裁切/缩放/局部），**不判**"配不配"（与 #73 无关）。评测：正例 15（P17 五景×3 帧）+
>   负例 10（同帧 vs 池内 bank48 最高分素材）⇒ **一致 25/25 = 100%**、**false-present 0**、uncertain 0，
>   成本 **$0.0180**（≤$0.5）。**关键**：S07（corr 0.2766 失败）VLM 判 present 并准确描述
>   「完整抛物线、三点连线、坐标标注，仅底部叠加字幕」；S08 更指出"仅缺失顶点 D 与底部 F 点"。
>   仲裁规则：`corr<0.30` ⇒ VLM 核验 ⇒ **present 放行**（附证据）、**absent/uncertain/失败 ⇒ 维持阻断**（fail-closed）。
> - **最终效果**：五景在「corr(最佳变体) + VLM 仲裁」下 **5/5 放行、0 阻断**
>   （4 景确定性 + S07 经 VLM）；**未放宽阈值、未改 PI 门禁逻辑**。
> - **tests**：`tests/corr_metric_diagnostics_test.py` 扩至 **29/29 通过**
>   （诊断函数 + bank 口径 + 双向验证运行器 + 仲裁层逻辑含 uncertain⇒阻断）。
> - 边界：LLM **$0**、VLM **$0.0180**、网络 **0**；`config.json`/DB schema/**PI 门禁逻辑与阈值**/
>   `mm_*` 冻结栈/词表/baseline/执行链/拆镜提案**均未改**；**未渲染、未执行拆镜、未跳过双门**。
> - 详见 `docs/regression_2x/PHASE18_REPORT.md`

"""

CHANGELOG = """## Phase 18 — 度量收口：present_test 修复（4/5）、corr v3 未采纳、VLM 在屏核验层达标并落地为仲裁层（2026-09-30）

**P18-1 `present_test` 口径修复（真 bug）DONE。** 缺陷（P17 实证）：旧版以「画面 vs 素材**全图**」比较，
对**局部化/裁切/放大**呈现结构失效。修复：比较基准改为**多尺度 16:9 子窗口 bank**
（`core/corr_diagnostics.py::bank_score`，尺度 {1.0,0.8,0.6,0.45,0.35}×5×5），池内其它素材同样按 bank 比较；
`bank=False` 保留旧口径以便对照复现。**实测**：S08 rank **4→1**（0.0581→0.7705）、S13 rank **5→1**（0.0062→0.3763）
⇒ 证实"全图口径"确为 bug；**但在屏数 3/5 → 4/5，未达授权书要求的 5/5**：
**S07 由 argmax 退化为 rank 4**（bank 最佳 0.2766 < 误导素材 `301ff850be9c` 0.352）——
多面板素材的子窗口只覆盖局部所致。**未调参补救、未掩盖**；缺口由 P18-2/P18-3 处理。

**P18-2 corr v3：未采纳（双门未全过）。** 阈值 **0.30 不变**；双门运行前写死（正门 5 景 100% PASS、
反门 55 条构造负例 0 误通过）。变体实测：`bank192` 正门 3/5·反门 **0/55**；
**`edge192`（Sobel/FIND_EDGES 边缘口径）正门 5/5 但反门 35/55 ⇒ 稀疏线稿"到处都是边"、口径无区分力，否决**；
最佳 `max(bank48,bank192)` **正门 4/5·反门 2/55**（唯一失分 S07=0.2766；2 条误通过均为 `301ff850be9c`）。
⇒ **未落地 v3、未版本化、未改任何门禁**。
**LIMITATION（如实登记）**：反门语料**仅含构造错配**；旧 S05 鲨鱼照等真实历史错配素材在本仓**不存在**
（全盘检索无该文件，仅存文件名/哈希）⇒ 反门强度受限，**但未以此为由放宽反门**。

**P18-3 VLM 在屏核验层：达标 ⇒ 落地为仲裁层。** 任务边界 = **视觉存在性**（"帧中是否出现该素材的任何部分"，
允许裁切/缩放/局部），**不判**"配不配/合不合适"——与 KNOWN_ISSUES #73（语义相关性判据不同源）**无关**。
新增 `vlm_judge.judge_presence`（prompt `vlm-presence-verify-v1`，两图输入，输出 present/absent/uncertain + 理由；
**沿用 P14-1 文件缓存**，键含模型+两图 sha+prompt_version）。评测集冻结：正例 15（P17 五景×10/50/90% 帧）
+ 负例 10（同帧 vs 池内 bank48 最高分素材，确定性抽样）。**实测：与人工目视一致 25/25 = 100%、
false-present 0、uncertain 0，成本 $0.0180（≤$0.5）**。
**关键能力**：S07（corr 0.2766，确定性失败）VLM 判 **present** 并准确描述「完整抛物线、三点连线、
坐标标注及虚线结构，仅底部叠加字幕」；S08 进一步指出「仅缺失顶点 D 与底部 F 点」。
**仲裁层**（`logs/phase18_p18_3_arbitration.json`）：`corr<0.30` ⇒ VLM 核验 ⇒
**present ⇒ 放行**（附 VLM 证据/prompt_version/模型名）；**absent / uncertain / 调用失败 ⇒ 维持阻断**（fail-closed）。
**五景最终 5/5 放行、0 阻断**（4 景确定性 + S07 经 VLM）。

**P18-4 落地与登记。** 报告均带 `corr_metric` 版本与出处（确定性部分为**候选** `v3`，未采纳；
采纳部分为 **VLM 仲裁层 `vlm-presence-verify-v1`**）。KNOWN_ISSUES 更新三类盲区（稀疏线稿塌陷 /
中心裁切·局部化呈现 / 运动缩放）的处置：**统一由 VLM 仲裁层兜底**，**非**放宽阈值。
`tests/corr_metric_diagnostics_test.py` 扩至 **29/29 通过**（诊断函数 + P18-1 bank 口径 +
双向验证运行器 + P18-3 仲裁逻辑含 uncertain⇒阻断）。

**边界**：LLM **$0**、VLM **$0.0180**、网络 **0**；`config.json`、DB schema、**PI 门禁逻辑与阈值**、
`mm_*` 冻结栈、词表、baseline、执行链、拆镜提案（P17-4 保持只备不改）**均未改**；
**未渲染成片、未执行拆镜、未放宽阈值、未跳过双门**。

"""


def prepend(path: pathlib.Path, block: str, anchor: str):
    t = path.read_text(encoding="utf-8")
    if "Phase 18" in t[:7000]:
        print("已含 Phase 18，跳过:", path.name)
        return
    i = t.find(anchor)
    path.write_text((t[:i] + block + t[i:]) if i >= 0 else (block + t), encoding="utf-8")
    print("已前插:", path.name)


prepend(R / "STATUS.md", STATUS, "> **Phase 17（渲染后核验度量专项）收尾")
prepend(R / "CHANGELOG.md", CHANGELOG, "## Phase 17 —")
