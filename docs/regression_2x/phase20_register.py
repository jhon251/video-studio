# -*- coding: utf-8 -*-
"""Phase 20 登记：KNOWN_ISSUES 设计债 + STATUS/CHANGELOG 前插。"""
from __future__ import annotations

import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")

# ---------------- KNOWN_ISSUES：句中拆分设计债 ----------------
KI = """
---

## 75. 拆镜「句中切点」设计债 + 40 段时基与 pause 预算的**结构性冲突** — `OPEN`（设计债）

### 75.1 句中拆分（P19-3 第 2/3 轮）登记为 **NOT_EXECUTED**
Phase 20 §0（监理裁定）：**只执行句界拆分**（P19-3 第 1 轮 19 条提案，21→40 景，切点全在旁白句边界）。
第 2/3 轮的**句中切点**提案登记为 `NOT_EXECUTED`，理由：
句中切点的段文本**无法整句切分** ⇒ 字幕对齐风险 > DQ-3 边际收益（38.1% vs 45.0%）。
台账：`logs/phase19_split_execution_ledger.json`（第 2/3 轮记录保留，标注未执行）。

### 75.2 ⚠️ 40 段时基与冻结 pause 预算**结构性冲突**（Phase 20 实测，**阻塞 DQ-3 收口**）
- `core/narration.py::PAUSE_BUDGET_S = 0.75` 为**冻结常量**，`audio_time_base_s` 语义为
  `Σ段实测时长 + pause×(段数−1) + trailing(2.0)`。
- 21 段：`961.656 + 0.75×20 + 2.0 = 978.656s` ✔（与目标 978.7±1s 相符）
- **40 段**：`961.634 + 0.75×39 + 2.0 = 992.884s` ⇒ **超目标 +14.2s**（实测成片 **992.88s**）✘
- 要回到 978.7±1s，需 `pause ≈ 0.3852s/边界`（即把父级 15.0s 的 pause 总量摊到 39 个边界）。
- **但 pause 是冻结常量**（改它 = 动 PI 时基语义，超出授权）⇒ **授权书预期的
  "句界切片后总时长仍 978.7±1s" 在 40 段结构下不可能同时成立**。
- 数学不变量：`内容时长 = 976.656 − 0.75×(段数−1)`；40 段要求旁白内容仅 **946.4s**，
  而实际语音内容为 **961.634s**（4927 字，不可压缩、不可改写）⇒ 差额 15.2s 无解。
- **候选解法（需授权，本阶段未做）**：① 让 `pause_budget_s` 可从 voice 产物/policy 传入
  （改 PI 时基语义，最小改动）；② 或接受 992.88s 时长并同步放宽时长契约；③ 或回到 21 段。

### 75.3 逐景核验的段 ID 绑定缺口（Phase 20 实测）
40 段派生后，`MATERIAL_TIMELINE` decisions **仅覆盖 21 个父景 ID**（P20-2 的
`_phase20_binding` 提供了映射，但 decisions 仍按父景落库）⇒ 派生段
（`S01p1`/`S01p2`…）在核验时 `expected_asset_id` 为空，落入"占位镜头"分支 ⇒
**`checked_scenes` 仅 2/40**，核验近乎空转。
**处置**：拆镜要到 40 段时基**必须同步把素材绑定展开到每个派生段 ID**（否则闸门形同虚设）。
本阶段未做（授权范围未含），登记为设计债。
"""

p = R / "docs" / "KNOWN_ISSUES.md"
t = p.read_text(encoding="utf-8")
if "## 75." not in t:
    anchor = "\n## 变更纪律"
    i = t.find(anchor)
    t = (t[:i] + KI + t[i:]) if i >= 0 else (t.rstrip() + "\n" + KI)
    p.write_text(t, encoding="utf-8")
    print("KNOWN_ISSUES 已追加 #75")
else:
    print("KNOWN_ISSUES 已含 #75")

STATUS = """> **Phase 20（句界拆分 × 旁白切片同阶段收口）收尾，2026-09-30**
> **P20-1 40 段 voice 派生 DONE ✔（零重合成）｜P20-2 交付级渲染已执行但 **fail-closed**：
> 时长契约不通过 + 逐景核验近乎空转 ⇒ **未产生交付级候选**｜P20-3 材料包 DONE ✔（含阻塞说明）**
> - **P20-1 「40 段 voice 产物派生」（沙箱、确定性、零重合成）DONE**：从既有 21 段 `voice_output` +
>   `narration.mp3` **纯音频切片**出 40 段，每段文本**逐字继承**（字符数 **4927→4927 相等**，逐段 sha256 记录）。
>   含**实测静音吸附**（`silencedetect`）：**19/19 切点落在真实停顿上**。
>   v2 时基：**978.634s**（Δ−0.022）。**fail-closed 已实际触发两次并修正**：
>   ① 首版每边界给 0.75s pause ⇒ 时基 +14.2s（BLOCKED）；改**pause 总量守恒**后消除；
>   ② 末段切片越过音频 EOF（961.656s）⇒ 实测时长不符（BLOCKED）；加 **EOF 夹取**后消除。
> - **⚠️ P20-2 fail-closed（关键发现，如实报告）**：**40 段结构下时长契约不可能同时成立**。
>   `core/narration.py::PAUSE_BUDGET_S=0.75` 是**冻结常量**，`audio_time_base_s = Σ实测 + pause×(段数−1) + 2.0`：
>   21 段 = **978.656s** ✔；**40 段 = 992.884s** ⇒ 实测成片 **992.88s**，**超 978.7±1s 达 +14.2s** ✘。
>   要回 978.7s 需 `pause≈0.3852s/边界`（把父级 15.0s 摊到 39 边界），但那等于**改 PI 时基语义**（超授权）；
>   数学不变量 `内容 = 976.656 − 0.75×(段数−1)` ⇒ 40 段要求旁白仅 **946.4s**，实际 **961.634s**，**15.2s 无解**。
>   ⇒ 授权书预期的"句界切片后总时长仍 978.7±1s"与 40 段 + 冻结 pause **不可兼得**。
> - **⚠️ 第二处缺口**：40 段派生后 `MATERIAL_TIMELINE` decisions **仅覆盖 21 个父景 ID** ⇒ 派生段
>   `expected_asset_id` 为空、落入"占位镜头"分支 ⇒ **逐景核验 `checked_scenes` 仅 2/40（近乎空转）**。
>   拆镜到 40 段**必须同步把素材绑定展开到每个派生段 ID**。
> - **P20-2 已通过的门**（如实并列）：响度 **−16.1 LUFS / −2.5 dBTP** ✔｜PI 前全 PASS（PI-1/2/6 + G-TL/G-PAD/G-SUB）｜
>   PI 后全 PASS 且 `promote_blocked=False` ✔｜字幕 `SUBTITLE_ALIGNED`（216 cue、语音内 1.0、越界 0s）✔｜
>   MOTION_VERIFIED（40 景中 24 景启用运动、0 fallback）✔｜**DQ-2 PASS**（11 唯一素材）。
>   **DQ-3：45.0%（18/40）、max_hold 36.836s**（原 100%、67.374s）⇒ **显著改善但未达 ≤20%**，按口径报"改善"不报 PASS。
>   候选 `projects/p_2b99e67181ce/output/t_63e1aa25069d_draft.mp4`（44,465,324 B），**未登记 render_output**。
> - **结论**：**未登记交付级候选**；**21 景版 `p_50e10b27b44d` 仍是目前唯一全门通过的候选**。
> - 边界：LLM **$0**、VLM **$0.0007**（≤$0.5）、网络 **0**、渲染 122.6 s；`config.json`/DB schema/**
>   PI 阈值与判定语义**/`mm_*` 冻结栈/词表/baseline/母片与既有候选/冻结真值**均未改**；
>   **未执行句中拆分、未改一字旁白、未重跑 claim 链、零 promotion**。
> - 设计债入 KNOWN_ISSUES **#75**（句中切点 / 40 段时基×pause 冲突 / 段 ID 绑定缺口）。
> - 详见 `docs/regression_2x/PHASE20_REPORT.md`

"""

CHANGELOG = """## Phase 20 — 句界拆分 × 旁白切片同阶段收口：P20-1 完成、P20-2 fail-closed（40 段时基×pause 结构冲突）（2026-09-30）

**§0 裁定范围。** 只执行**句界拆分**（P19-3 第 1 轮 19 条提案，21→40 景，切点全在旁白句边界）；
第 2/3 轮**句中切点**提案登记 **NOT_EXECUTED**（理由：句中切点的段文本无法整句切分 ⇒
字幕对齐风险 > DQ-3 边际收益 38.1% vs 45.0%），入 KNOWN_ISSUES #75 作设计债。目标：DQ-3 **显著改善**，不追 ≤20%。

**P20-1 40 段 voice 产物派生（沙箱、确定性、零重合成）DONE。** 输入既有 21 段 `voice_output`
（`segments_manifest` + `narration.mp3` 实测 961.656s）与第 1 轮句界拆分时间轴；
**纯音频切片**出 40 段，每段文本按句界**逐字继承**（**4927→4927 字符相等**，逐段 `text_sha256` 记录）；
切点在父景窗内用 `silencedetect` 的**实测静音中点吸附**（19/19 切点落在真实停顿上）；
`audio_time_base_s = 978.634s`（Δ−0.022）。**provenance**：`derived_from`（voice 产物 sha256 +
拆镜台账 sha256 + source audio sha256）、切片规则版本 `p20-voice-slice-v1:sentence-boundary+silence-snap`、逐段 sha256。
**fail-closed 实际触发两次并修正（如实登记）**：① 首版每边界给 0.75s pause ⇒ 时基 +14.2s（`TIME_BASE_DRIFT`）⇒
改**pause 总量守恒**（父级 15.0s 摊到 39 边界）后消除；② 末段切片越过音频 EOF（961.656s）⇒ 实测时长不符
（`DURATION_MISMATCH`）⇒ 加 **EOF 夹取**后消除。

**P20-2 交付级渲染已执行（122.6s）但 fail-closed，未产生交付级候选。**
沙箱 `p_2b99e67181ce`、任务 `t_63e1aa25069d`；40 段派生脚本（`script_dcv2_p20_40seg.json`，
总时长 978.634s == voice 时基）+ 40 段 voice 派生产物 + 池素材 10 张（P19-4 的 4 处标记素材降权重选沿用）；
运动 enabled + 仲裁层 enabled。候选 `projects/p_2b99e67181ce/output/t_63e1aa25069d_draft.mp4`（44,465,324 B）。
**⚠️ 关键发现（阻塞 DQ-3 收口，如实报告）**：**40 段结构下时长契约不可能同时成立** ——
`core/narration.py::PAUSE_BUDGET_S = 0.75` 为**冻结常量**，`audio_time_base_s = Σ段实测 + pause×(段数−1) + trailing(2.0)`；
**21 段 = 961.656 + 0.75×20 + 2.0 = 978.656s** ✔，**40 段 = 961.634 + 0.75×39 + 2.0 = 992.884s** ⇒
实测成片 **992.88s**，**超 978.7±1s 达 +14.2s** ✘。要回 978.7s 需 `pause ≈ 0.3852s/边界`，
而那等于**改 PI 时基语义**（超授权）；数学不变量 `内容 = 976.656 − 0.75×(段数−1)` ⇒ 40 段要求旁白内容仅
**946.4s**，实际 **961.634s**（4927 字，不可压缩/不可改写）⇒ **15.2s 无解**。
**⚠️ 第二处缺口**：40 段派生后 `MATERIAL_TIMELINE` decisions **仅覆盖 21 个父景 ID** ⇒ 派生段
`expected_asset_id` 为空、落入"占位镜头"分支 ⇒ **逐景核验 `checked_scenes` 仅 2/40（近乎空转）**；
拆镜到 40 段**必须同步把素材绑定展开到每个派生段 ID**。
**已通过的门（如实并列）**：响度 **−16.1 LUFS / −2.5 dBTP** ✔｜PI 渲染前全 PASS（PI-1/2/6 + G-TL/G-PAD/G-SUB）｜
PI 渲染后全 PASS 且 `promote_blocked=False` ✔｜字幕 `SUBTITLE_ALIGNED`（216 cue、语音内占比 1.0、越界 0s）✔｜
MOTION_VERIFIED（40 景中 **24 景**启用运动、**0 fallback**）✔｜**DQ-2 PASS**（11 唯一素材）✔。
**DQ 复算**：**DQ-3 = 45.0%（18/40）、max_hold 36.836s**（原 100%、67.374s）⇒ **显著改善，但未达 ≤20%**，
按授权口径报"改善幅度"、**不报 PASS**。
**交付级判定**：**未登记交付级候选**（时长契约不通过 + 核验空转）；**21 景版 `p_50e10b27b44d` 仍是目前唯一全门通过的候选**。

**边界**：LLM **$0**、VLM **$0.0007**、网络 **0**、渲染 122.6 s；`config.json`、DB schema、
**PI 阈值与判定语义**、`mm_*` 冻结栈、词表、baseline、母片与既有候选、冻结真值**均未改**；
**未执行句中拆分、未改一字旁白文本、未重跑 claim/事实核查链、零 promotion、未发布**。
设计债入 **KNOWN_ISSUES #75**。

"""


def prepend(path: pathlib.Path, block: str, anchor: str):
    t = path.read_text(encoding="utf-8")
    if "Phase 20" in t[:8000]:
        print("已含 Phase 20，跳过:", path.name)
        return
    i = t.find(anchor)
    path.write_text((t[:i] + block + t[i:]) if i >= 0 else (block + t), encoding="utf-8")
    print("已前插:", path.name)


prepend(R / "STATUS.md", STATUS, "> **Phase 19（拆镜批执行")
prepend(R / "CHANGELOG.md", CHANGELOG, "## Phase 19 —")
