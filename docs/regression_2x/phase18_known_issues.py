# -*- coding: utf-8 -*-
"""Phase 18 / P18-4：KNOWN_ISSUES 更新 —— 三类核验盲区的**处置**（引用 Phase 17 归因与本阶段验证）。

在 #73 之后追加一节「#74 渲染后核验三类盲区：已定位 + 已由 VLM 仲裁层兜底（非放宽阈值）」。
不修改 #73 与任何历史条目。
"""
from __future__ import annotations

import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
p = R / "docs" / "KNOWN_ISSUES.md"
t = p.read_text(encoding="utf-8")

BLOCK = """
---

## 74. 渲染后核验度量：**三类盲区已定位并已由 VLM 仲裁层兜底**（非放宽阈值）— `MITIGATED`

| 编号 | 内容 | 证据 |
|---|---|---|
| **#74** | 冻结的渲染后核验度量 `corr_48 = frame_corr(gray48(asset), gray48(frame))`（阈值 0.30）存在**三类结构性盲区**，会把**素材确实在屏**的场景误判为失败。**处置：不改阈值、不改门禁，改由「VLM 存在性核验」仲裁层兜底。** | `PHASE17_REPORT.md`、`PHASE18_REPORT.md`、`logs/phase17_attribution.json`、`logs/phase18_p18_3_vlm_presence.json` |

### 三类盲区（Phase 17 逐景归因定位）
| # | 盲区 | 机理 | 实证 |
|---|---|---|---|
| ① | **稀疏线稿在 48×48 下塌陷** | 白底 + 细黑线 + 细小标记的线稿，重采样到 48×48 后有效信息几乎只落在极少数像素上；轻微缩放/位移即让线条换格 | S07 0.0783 / S08 0.0581 / S13 0.0062（**人工目视均证实同图在屏**） |
| ② | **16:9 中心裁切 / 局部化呈现** | 模板 `scale=1920:1080:force_original_aspect_ratio=increase, crop=1920:1080` 只保留中段；画面是素材的**局部**，与"全图"比较必然低分 | S02（1200×1560 竖多面板，0.1219）、S08（885×1033，0.0581）；S08 人工看图仅缺 D/F 标记 |
| ③ | **运动缩放（画面=素材子窗口）** | 启用运动的场景，画面是运动裁切窗口 = 素材某个**子窗口**，与全图相关性天然低于静态 | S06/S07/S13（SLOW_ZOOM/PAN）；`render/motion_evidence.json` |

### 已执行的修复与裁定（Phase 18）
1. **`present_test` 真 bug 已修（P18-1）**：比较基准由「画面 vs 素材**全图**」改为
   **多尺度 16:9 子窗口 bank** ⇒ S08 rank **4→1**、S13 rank **5→1**（证实"全图口径"是 bug）。
   **但在屏数 3/5 → 4/5，未达 5/5**：**S07 退化为 rank 4**（bank 0.2766 < 误导素材 `301ff850be9c` 0.352）。
   **未调参补救**。
2. **确定性 corr v3 未采纳（P18-2）**：阈值 0.30 不变、双门运行前写死。
   `bank192` 正门 3/5·反门 0/55；**边缘图口径正门 5/5 但反门 35/55 ⇒ 无区分力，否决**；
   最佳 `max(bank48,bank192)` 正门 4/5·反门 2/55 ⇒ **双门未全过 ⇒ 未落地、未改门禁**。
3. **VLM 存在性核验层达标并落地为仲裁层（P18-3）**：任务 = **"帧里在不在该素材"**
   （允许裁切/缩放/局部），**不判**"配不配"（与 **#73 无关**，两者是不同任务）。
   实测 **一致 25/25 = 100%、false-present 0、uncertain 0**，成本 **$0.0180**。
   仲裁：`corr<0.30` ⇒ VLM 核验 ⇒ **present 放行**（附证据）；**absent/uncertain/失败 ⇒ 维持阻断**（fail-closed）。
   五景 **5/5 放行**（4 确定性 + S07 经 VLM）。

### LIMITATION（如实登记，未被当作门通过的理由）
- **反门语料不全**：仅含**构造错配**（帧 vs 池内无关素材）。旧 S05 鲨鱼照等**真实历史错配素材在本仓不存在**
  （全盘检索无该文件，仅存文件名/哈希）⇒ 反门强度受限。
- **VLM 端点非确定性**（P14-2 已实测：`temperature=0` 下独立运行仍有标签变化）⇒ 仲裁层结论
  **以缓存键为复现单位**（同键同字节），跨键/跨版本不保证复现；因此仲裁证据**逐景留痕**并附 `prompt_version` + 模型名。
- **`301ff850be9c` 为已知误导素材**：在 48×48 / bank 口径下对 S02 与 S07 均达 ~0.35（超过阈值），
  是 v3 反门仅有的 2 条误通过来源；**建议后续素材入库时按 P17-3 的 `crop_safety` 同法增加"误匹配倾向"标记**。

### 为何不改阈值
授权与先例（Phase 11 / Phase 17 / Phase 18）均要求**修误报、不松真门**：降低 0.30 会同时放过
真实错配（反门），故采用"**确定性度量 + VLM 存在性仲裁**"而非阈值宽松。
"""

if "## 74." in t:
    print("KNOWN_ISSUES 已含 #74，跳过")
else:
    anchor = "\n## 变更纪律"
    i = t.find(anchor)
    if i >= 0:
        t = t[:i] + BLOCK + t[i:]
    else:
        t = t.rstrip() + "\n" + BLOCK
    p.write_text(t, encoding="utf-8")
    print("KNOWN_ISSUES 已追加 #74")

# 在 #73 状态行标注与 #74 的关系（不删改原内容）
t2 = p.read_text(encoding="utf-8")
if "与 #74 的关系" not in t2:
    old = "## 73. VLM 视觉相关性判定：**判据与人工不同源**（DQ/P7-4 需求语义 vs 人工叙事切题性）— `OPEN`"
    new = (old + "\n\n> **与 #74 的关系**：#73 是**语义相关性**判定（配不配）的任务定义问题；"
           "#74 是**视觉存在性**核验（在不在）的度量盲区。二者**不同任务**，"
           "Phase 18 的 VLM 仲裁层**不解决 #73**（#73 仍 OPEN）。")
    t2 = t2.replace(old, new, 1)
    p.write_text(t2, encoding="utf-8")
    print("已在 #73 标注与 #74 的关系（#73 仍 OPEN）")
else:
    print("#73 关系标注已存在")
