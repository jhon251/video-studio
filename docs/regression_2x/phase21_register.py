# -*- coding: utf-8 -*-
"""Phase 21 登记：KNOWN_ISSUES #75 处置更新 + LIMITATION + STATUS/CHANGELOG + 三版本材料包。"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")

# ---------- 三版本 promotion 材料包 ----------
p19 = json.loads((L / "phase19_p19_4_verification.json").read_text(encoding="utf-8"))
p20 = json.loads((L / "phase20_p20_2_verification.json").read_text(encoding="utf-8"))
p21 = json.loads((L / "phase21_p21_3_verification.json").read_text(encoding="utf-8"))
old_pkg = json.loads((L / "phase20_p20_3_promotion_package.json").read_text(encoding="utf-8"))


def ver(j, name):
    return {
        "name": name, "candidate": j["candidate"],
        "sha256": j["candidate_sha256"], "bytes": j["candidate_bytes"],
        "segments": j.get("segments"),
        "duration_s": j["duration_contract"]["measured_s"],
        "duration_within": j["duration_contract"]["within"],
        "loudness": j["loudness"],
        "pi_pre_blocked": j["pi_pre"]["blocked"], "pi_post_blocked": j["pi_post"]["blocked"],
        "subtitles": j["subtitle"], "motion": j["motion"],
        "per_scene": j["per_scene_verify"],
        "dq2": j.get("dq2_corrected"), "dq3": {k: v for k, v in j["dq3"].items()
                                               if k != "holds"},
        "gate_state": j.get("gate_state", ""),
    }


pkg = {
    "schema": "phase21-promotion-package-v1",
    "stage": "Phase 21 P21-3 promotion 材料包（三版本对比 + 观看推荐序）",
    "recommended_promotion_baseline": p19["candidate"],
    "baseline_note": ("P21-3 因**派生段逐景核验 33 处误报**仍 fail-closed ⇒ 依授权书预案，"
                      "**21 景版自动转正为 promotion 基线**。"),
    "watch_order": [
        {"rank": 1, "version": "A (P19 21 景)", "candidate": p19["candidate"],
         "why": "唯一**全门通过 + DQ-2 PASS**，可直接交付；DQ-3 FAIL（max 67.374s）"},
        {"rank": 2, "version": "C (P21 40 段 v2.1)", "candidate": p21["candidate"],
         "why": ("**时长 977.88s ✔ + DQ-2 PASS ✔ + DQ-3 42.5%**（远优于 A 的 100%）；"
                 "仅剩**派生段核验口径**待修（建议复用 P18-1 bank），修完即可全门通过")},
        {"rank": 3, "version": "B (P20 40 段)", "candidate": p20["candidate"],
         "why": "已被 C 取代（时长/DQ-2/核验三处不通过），仅作过程留档"},
    ],
    "versions": {"A_p19_21seg": ver(p19, "A (P19 21 景)"),
                 "B_p20_40seg": ver(p20, "B (P20 40 段)"),
                 "C_p21_40seg": ver(p21, "C (P21 40 段 v2.1)")},
    "fixes_landed": {
        "#75.2（40 段 × 冻结 pause 幻影膨胀 +14.2s）": "**已修复**：time_base_policy=v2.1 pause 归因表；"
            "40 段 base 992.884 → 977.884 ∈ 978.7±1；常量零改动；21 段路径逐字节兼容。",
        "#75.3（派生段未绑定素材 ⇒ DQ-2 FAIL + 核验空转）": "**已修复**：绑定展开到 40 条；"
            "DQ-2 由 FAIL(share 0.9369/unique 3) 恢复 **PASS(0.1778/10)**；核验覆盖 2/40 → **40/40**。",
        "新发现（派生段核验误报 33 处）": "**未修复**：需把派生段核验口径改为 P18-1 的子窗口 bank；"
            "当前致门 fail-closed。",
        "#75.1（句中切点设计债）": "**未执行**（依 §0 裁定），维持登记。",
    },
    "known_limitations": old_pkg["known_limitations"] + [
        "**派生段核验误报（P21 新发现）**：派生段窗口只含父素材局部裁切，核验以 48×48 与素材全图比较 ⇒ "
        "33/40 景误判失败（#74 盲区重现）；门内仲裁需 33 次 VLM（21 段版仅 4 次）。",
        "**P19-2 盲区（LIMITATION）**：「素材-素材」互相似度**不能**捕获「素材 vs 任意成片帧」的误吸引 —— "
        "实证 `301ff850be9c` discriminative_score 仅 0.0574 却对 S02/S07 成片帧达 ~0.35。",
        "**授权书预期与实测差异**：40 段 base 预期 978.634（按 20 原始边界），实测 **19** 个原始边界 ⇒ "
        "977.884（Δ−0.75s，仍 ∈978.7±1）。",
    ],
    "one_page_summary": (
        "【Phase 21 一页摘要】#75.2 与 #75.3 **两项修复均已落地并验证**："
        "① v2.1 pause 归因表（原始边界 0.75s / 派生边界 0s，常量零改动、21 段路径逐字节兼容）"
        "⇒ 40 段时基 992.884 → **977.884s ∈ 978.7±1**；"
        "② 素材绑定展开到 40 条（40/40 覆盖）⇒ DQ-2 由 FAIL(0.9369/3) 恢复 **PASS(0.1778/10)**、最大复用 8 景。"
        "响度/PI/字幕/运动 全 PASS；DQ-3 **42.5%**（max 37.201s，A 版为 100%/67.374s）。"
        "**但派生段逐景核验误报 33 处**（子窗口 vs 素材全图，48×48 盲区）⇒ **门仍 fail-closed，未登记交付级候选**；"
        "依预案 **A（P19 21 景）转正为 promotion 基线**。观看序：A → C（修核验口径后）→ B。"),
    "zero_promotion": True,
}
pp = L / "phase21_promotion_package.json"
pp.write_text(json.dumps(pkg, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
print("材料包 ->", pp.relative_to(R).as_posix())

# ---------- KNOWN_ISSUES #75 处置更新 ----------
p = R / "docs" / "KNOWN_ISSUES.md"
t = p.read_text(encoding="utf-8")
BLOCK = """
### 75.4 处置更新（Phase 21 验证）
| 项 | 状态 | 证据 |
|---|---|---|
| **75.2** 40 段 × 冻结 pause 幻影膨胀 | **已修复（RESOLVED）** | `time_base_policy=v2.1`：`core/narration.py::pause_attribution`（归因表驱动，**常量零改动**）；40 段 base **992.884 → 977.884s ∈ 978.7±1**；21 段无表路径 **978.656s 逐字节兼容**。证据 `logs/phase21_p21_1_2_build.json`、`PHASE21_REPORT.md` §1。 |
| **75.3** 派生段未绑定素材 | **已修复（RESOLVED）** | `material_timeline` 展开 40 条（两侧素材继承，`parent_scene_id` + 子窗口）；DQ-2 由 FAIL(share 0.9369/unique 3) 恢复 **PASS(0.1778/10)**；逐景核验覆盖 **2/40 → 40/40**。证据 `logs/phase21_p21_3_verification.json`。 |
| **75.1** 句中切点设计债 | **维持 OPEN** | 依 Phase 20 §0 裁定 NOT_EXECUTED；DQ-3 仍 42.5%（>20%），若需 ≤20% 须解此债或上移 `max_hold_s`（需授权）。 |
| **新：派生段核验误报 33 处** | **OPEN（P21 发现）** | 派生段窗口只含父素材**局部裁切**，核验以 48×48 与**素材全图**比较 ⇒ 33/40 误判失败（即 #74 的"中心裁切/局部化"盲区在同一度量上重现）；门内仲裁需 33 次 VLM（21 段版仅 4 次）。**建议**：派生段改用 P18-1 `bank_score` 子窗口口径（零 VLM 成本、确定性）。 |

### 75.5 LIMITATION：P19-2「素材-素材」指标盲区（一并登记）
P19-2 的 `discriminative_score`（素材间 48×48 最大 corr）**不能**捕获
「**素材 vs 任意成片帧**」的误吸引机制。实证：Phase 18 反门仅有的 2 条误通过来源
`301ff850be9c` 在本指标下仅 **0.0574**（远低于 0.35 阈值），却对 S02/S07 的**成片帧**达 ~0.35。
⇒ 该标记**有用但不充分**；覆盖后一现象需另立「素材 vs 历史帧包」吸引度指标（**未做**）。
"""
if "### 75.4" not in t:
    t = t.rstrip() + "\n" + BLOCK
    p.write_text(t, encoding="utf-8")
    print("KNOWN_ISSUES #75 已更新处置与 LIMITATION")
else:
    print("KNOWN_ISSUES #75 已有处置更新")

STATUS = """> **Phase 21（派生段时基与绑定收口）收尾，2026-09-30**
> **P21-1 pause 归因策略（v2.1）DONE ✔｜P21-2 素材绑定展开 DONE ✔｜P21-3 渲染 131.9s：两项修复达成，但派生段核验误报 33 处 ⇒ 仍 fail-closed**
> - **#75.2 已修复**：新增 `time_base_policy=v2.1` pause **归因表**（`core/narration.py::pause_attribution`）——
>   原始边界保持 `PAUSE_BUDGET_S=0.75`（**常量零改动**）、经静音吸附的派生边界 `pause=0`
>   （依据：实测停顿已被切片吸收，双计即幻影膨胀）。**40 段 base 992.884 → 977.884s ∈ 978.7±1**；
>   **21 段无表路径 978.656s 逐字节兼容**；常量指纹断言未改。
>   **与授权书预期差异（如实）**：预期 978.634 按 **20** 原始边界；实测 **19** 个（40 段序列以派生段结尾）
>   ⇒ 977.884（Δ−0.75s，仍在容差内）。
> - **#75.3 已修复**：`material_timeline` 展开 **40 条**（两侧素材继承 + `parent_scene_id` + 子窗口；
>   fail-closed 解析 0 失败）⇒ **DQ-2 由 FAIL(share 0.9369/unique 3) 恢复 PASS(0.1778/10)、最大复用 8 景**；
>   **逐景核验覆盖 2/40 → 40/40**。
> - **P21-3 全门**：时长 **977.88s ✔**｜响度 **−16.1 LUFS/−2.5 dBTP** ✔｜PI 前/后全 PASS、`promote_blocked=False` ✔｜
>   字幕 `SUBTITLE_ALIGNED`（216 cue、语音内 1.0、越界 0s）✔｜运动 **24 景/0 fallback** ✔｜**DQ-2 PASS** ✔｜
>   **DQ-3 42.5%**（17/40、max 37.201s；A 版 100%/67.374s）⇒ **显著改善、未达 ≤20%**（按口径报改善）。
> - **⚠️ 新发现（OPEN）**：**派生段逐景核验误报 33 处** —— 派生段窗口只含父素材**局部裁切**，
>   核验以 48×48 与**素材全图**比较 ⇒ 子窗口天然低分（#74"中心裁切/局部化"盲区重现）；
>   门内仲裁将需 **33 次 VLM**（21 段版仅 4 次）⇒ **门仍 fail-closed，未登记交付级候选**。
>   **建议修复**：派生段改用 P18-1 `bank_score` 子窗口口径（零 VLM 成本、确定性、与既有修复同源）。
> - **预案执行**：依授权书，**21 景版 `p_50e10b27b44d` 自动转正为 promotion 基线**。
> - **三版本材料包** `logs/phase21_promotion_package.json`（观看序：**A → C（修核验后）→ B**）。
> - 边界：LLM **$0**、VLM **$0.0007**、网络 **0**、渲染 131.9s；`config.json`/DB schema/**PI 阈值与判定语义**/
>   `mm_*` 冻结栈/词表/baseline/母片与既有候选/冻结真值**均未改**；**未句中拆分、未改一字旁白（4927→4927）、
>   未重跑 claim 链、零 promotion**。
> - KNOWN_ISSUES **#75.4/#75.5** 已登记（两修复 RESOLVED + P19-2 盲区 LIMITATION）。详见 `PHASE21_REPORT.md`

"""

CHANGELOG = """## Phase 21 — 派生段时基与绑定收口：#75.2/#75.3 双修复达成，派生段核验误报 33 处致门仍 fail-closed（2026-09-30）

**P21-1 `time_base_policy=v2.1`（pause 归因策略）DONE。#75.2 修复。** 新增
`core/narration.py::pause_attribution()` / `_pauses()`：**原始段边界**保持 `PAUSE_BUDGET_S=0.75`
（**常量数值与语义零改动**，指纹断言通过），**经静音吸附的派生边界 `pause=0`**
（依据：`silencedetect` 实测停顿**已被切片吸收**，再计即"幻影膨胀"——#75.2 根因）；
`audio_time_base_s()` / `audio_segment_windows()` **消费该表**，逐边界登记 `original|derived` + 依据引用。
**双路径硬验收**：21 段**无表**路径 **978.656s 逐字节兼容**（表为 None 亦然）；
40 段**无表**复现旧膨胀 **992.884s**（证明修复真实生效）；40 段**有表** **977.884s ∈ 978.7±1**（−15.0s）。
**与授权书预期差异（如实登记）**：授权书预期 978.634 系按 **20** 个原始边界；实测 **19** 个
（21 景 → 20 次父景切换，但 40 段序列**以派生段结尾**，末边界不计 pause）⇒ 977.884，Δ−0.75s，仍 ∈ 容差。

**P21-2 素材绑定展开到派生段 DONE。#75.3 修复。** `material_timeline` 展开 **40 条**，
每条带 `parent_scene_id` + 子窗口 + `selected_asset`（**两侧素材继承**）。
**fail-closed**：全部派生段可解析父绑定（**0 失败**）。
**DQ-2 按 `direction.DEFAULT_POLICY`（share ≤0.35 / unique ≥6）复算**：
由 P20 的 **FAIL**（`max_asset_share=0.9369`、`unique_assets=3`）恢复为
**PASS**（`max_asset_share=0.1778`、`unique_assets=10`、最大复用 **8 景**）；
**逐景核验覆盖 2/40 → 40/40**。

**P21-3 渲染 + 全门 + DQ 复算。** 沙箱 `p_96ee06071dde`、任务 `t_1033b541c548`、**131.9 s**；
候选 `projects/p_96ee06071dde/output/t_1033b541c548_draft.mp4`（43,875,812 B），
**未登记 `render_output`**（fail-closed）。**时长 977.88s ✔**｜响度 **−16.1 LUFS / −2.5 dBTP** ✔｜
PI 渲染前全 PASS（PI-1/2/6 + G-TL/G-PAD/G-SUB）｜PI 渲染后全 PASS 且 `promote_blocked=False` ✔｜
字幕 `SUBTITLE_ALIGNED`（216 cue、语音内 1.0、越界 0s）✔｜MOTION_VERIFIED（40 景中 24 景启用、0 fallback）✔｜
**DQ-2 PASS** ✔｜**DQ-3 42.5%**（17/40、max 37.201s；A 版 100%/67.374s）⇒ **显著改善、未达 ≤20%**（按口径报改善）。
**⚠️ 新发现（OPEN）**：**派生段逐景核验误报 33 处** —— 派生段窗口只含父素材**局部裁切**，
核验以 **48×48 与素材全图**比较 ⇒ 子窗口天然低分（KNOWN_ISSUES #74 "中心裁切/局部化呈现"盲区重现）；
门内仲裁层将需 **33 次 VLM**（21 段版仅 4 次）⇒ **门仍 fail-closed，未登记交付级候选**。
**建议修复**：派生段改用 P18-1 `bank_score` 子窗口口径（**零 VLM 成本、确定性、与既有修复同源**）。
**预案执行**：依授权书，**21 景版 `p_50e10b27b44d` 自动转正为 promotion 基线**。
**三版本材料包** `logs/phase21_promotion_package.json`（观看推荐序 **A → C（修核验后）→ B**）。

**登记**：KNOWN_ISSUES **#75.4**（75.2/75.3 RESOLVED、75.1 维持 OPEN、派生段核验误报 OPEN）
与 **#75.5**（P19-2「素材-素材」指标盲区 **LIMITATION**：`301ff850be9c` 该指标仅 0.0574
却对成片帧达 ~0.35 ⇒ 标记有用但不充分）。

**边界**：LLM **$0**、VLM **$0.0007**、网络 **0**、渲染 131.9 s；`config.json`、DB schema、
**PI 阈值与判定语义**、`mm_*` 冻结栈、词表、baseline、母片与既有候选、冻结真值**均未改**；
**未执行句中拆分、未改一字旁白（4927→4927 字符）、未重跑 claim/事实核查链、零 promotion、未发布**。

"""

for name, block, anchor in (("STATUS.md", STATUS, "> **Phase 20（句界拆分"),
                            ("CHANGELOG.md", CHANGELOG, "## Phase 20 —")):
    path = R / name
    txt = path.read_text(encoding="utf-8")
    if "Phase 21" in txt[:8000]:
        print("已含 Phase 21，跳过:", name)
        continue
    i = txt.find(anchor)
    path.write_text((txt[:i] + block + txt[i:]) if i >= 0 else (block + txt), encoding="utf-8")
    print("已前插:", name)
