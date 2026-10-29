# -*- coding: utf-8 -*-
"""Phase 19 登记：STATUS.md / CHANGELOG.md 前插（不改历史条目）。"""
from __future__ import annotations

import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")

STATUS = """> **Phase 19（拆镜批执行 + VLM 仲裁生产接线 + 交付级最终渲染）收尾，2026-09-30**
> **P19-1 仲裁层生产接线 DONE ✔（加法/门控/默认关闭/关闭时逐字节一致）｜P19-2 误导倾向标记 DONE ✔（12 张全量，2 张标记）｜
> P19-3 拆镜批执行 DONE ✔（批准链 + 两轮；DQ-3 未达 ≤20% 如实登记）｜P19-4 最终渲染已执行（115.1s）：全门通过 + DQ-2 PASS，
> 但 DQ-3 零改善 ⇒ 登记为「**全门通过的候选**」，**不宣称交付级 PASS**，promotion 交人工**
> - **P19-1**：新增 `src/video_studio/core/render_arbitration.py`，接线于 `agents/editing/agent.py` 渲染后核验门；
>   开关链同 `render_motion.json`（外部文件 `config/render_arbitration.json`，**默认 off**，`config.json` 零改动）。
>   `corr<0.30` ⇒ VLM 存在性核验 ⇒ `present` ⇒ **PASS_VLM_PRESENT**（附证据/prompt_version/模型/成本）；
>   `absent`/`uncertain`/失败 ⇒ **维持阻断**（fail-closed）。**硬验收**：关闭时 `apply_arbitration` **原样返回入参对象**
>   （实测 `out is verification == True`）⇒ 逐字节一致。
> - **P19-1 实测（生产路径）**：用生产纯函数复现核验后跑仲裁 ⇒ **4 个失败景全部核验为 present 并放行**
>   （S06 0.242 / S11 0.153 / S13 0.006 / S18 0.253），成本 **$0.0021**。
> - **P19-2**：`discriminative_score` = 素材间 48×48 最大 corr，≥0.35 标记（实测 2 张：`23e71bc8a864`↔`432cd85be6f1` = 0.4797）。
>   **口径局限如实登记**：该指标**不能**捕获"素材 vs 成片帧"的误吸引——P18 的误通过源 `301ff850be9c` 本表仅 **0.0574**；
>   需另立"素材 vs 历史帧包"指标（本阶段未做）。
> - **P19-3**：19 条提案按 13-C 双字段转录批准（`authorized_by=human:project-owner` + 授权书）并**逐条绑定 proposal sha256**；
>   第 1 轮（≤35s）→ **45.0%**；第 2 轮（≤25s）→ **38.1%**；第 3 轮**无变化（切点耗尽）**。**未达 ≤20%**，
>   按授权口径**不硬切**（避免破坏旁白-画面对齐），如实报改善幅度。**文本零改动硬校验通过**（4927→4927 字符、978.656→978.656 s）。
> - **⚠️ 关键兼容性发现**：**拆镜后 42 段时基与既有 `voice_output`（21 段）冲突** —— 渲染前闸门报
>   `voice 产物不完整：缺少合法音频的段落 [21..41]` + `G-SUB FAIL` ⇒ **拆镜必须与旁白重配/音频重切同阶段进行**。
>   这是 P19-4 沿用 21 段时基、以及 **DQ-3 本阶段零改善**的直接原因。
> - **P19-4**：沙箱 `p_50e10b27b44d`、任务 `t_a4d8c1aafd04`、**115.1 s**；运动 enabled（12/21 景、0 fallback）+ 仲裁 enabled；
>   标记素材重选 **4 处**（S02/S03/S05/S08，替换后立即计入复用计数以免 DQ-2 恶化）；
>   候选 `t_a4d8c1aafd04_draft.mp4`（41,263,003 B），**未登记 render_output**（首跑被阻断 ⇒ fail-closed，非交付物）。
>   **全门**：时长 **978.66 s**（978.7±1 ✔）｜响度 **−16.1 LUFS / −2.5 dBTP** ✔｜PI 前/后全 **PASS**、
>   `promote_blocked=False` ✔｜字幕 `SUBTITLE_ALIGNED`（216 cue、语音内 1.0、越界 0s）✔｜逐景核验+仲裁 **4→0 失败** ✔｜
>   MOTION_VERIFIED 12/12 ✔。**DQ-2 PASS**（10 唯一素材、单素材最大复用 **5 景**）；**DQ-3 FAIL 且零改善**（max 67.374s、21/21 超 25s）。
> - 边界：LLM **$0**、VLM **$0.0201**（≤$0.5）、网络 **0**；`config.json`/DB schema/**PI 阈值与判定语义**/`mm_*` 冻结栈/
>   词表/baseline/冻结真值/母片与既有候选**均未改**；**零 promotion**、未发布、未自动改旁白文本、未跳过人工批准。
> - 详见 `docs/regression_2x/PHASE19_REPORT.md`

"""

CHANGELOG = """## Phase 19 — 拆镜批执行 + VLM 仲裁生产接线 + 交付级最终渲染：全门通过 + DQ-2 PASS，DQ-3 零改善（2026-09-30）

**P19-1 VLM 仲裁层生产接线（加法、配置门控、默认关闭）。** 新增 `src/video_studio/core/render_arbitration.py`，
接线于 `agents/editing/agent.py` 渲染后逐景核验门处。开关链同 `config/render_motion.json` 模式
（外部文件 `config/render_arbitration.json`，**默认 off**；**`config.json` 零改动**）。
语义：仅当 `corr < 0.30` 时调 `vlm-presence-verify-v1`；`present` ⇒ **PASS_VLM_PRESENT**（放行，附 VLM 证据/
prompt_version/模型名/成本）；`absent`/`uncertain`/调用失败 ⇒ **维持阻断**（fail-closed 语义零改动）。
**硬验收**：门控关闭时 `apply_arbitration` **原样返回入参对象**（实测 `out is verification == True`，
`failed_scenes` 未被触碰）⇒ 核验行为与现状**逐字节一致**。测试覆盖 `uncertain ⇒ 阻断` 与默认关闭一致性。
**生产路径实测**：用生产纯函数 `EditingAgent._verify_scene_frames` 复现核验后跑仲裁 ⇒
**4 个失败景全部核验为 present 并放行**（S06 0.242、S11 0.153、S13 0.006、S18 0.253），成本 **$0.0021**。

**P19-2 素材误导倾向标记。** `discriminative_score` = 该素材在 48×48 灰度下与**池内其它素材**的最大 corr；
**≥0.35 ⇒ `low_discriminative`**（短名单降权、不硬拒）。12 张全量登记，
**标记 2 张**（`23e71bc8a864` ↔ `432cd85be6f1` 互达 **0.4797**），无一张同时命中 `low_crop_safety`。
**口径局限（如实登记）**：本指标是「素材 vs 素材」，**不能**捕获「素材 vs 任意成片帧」的误吸引机制——
Phase 18 的 2 条反门误通过来源 `301ff850be9c` 在本表仅 **0.0574**（却对 S02/S07 成片帧达 ~0.35）⇒
标记**有用但不充分**；覆盖后一现象需另立「素材 vs 历史帧包」吸引度指标（**本阶段未做，登记为后续项**）。

**P19-3 拆镜批执行（DQ-3 未达 ≤20%，如实登记）。** 19 条 P17-4 提案按 **13-C 双字段**转录批准
（`authorized_by=human:project-owner`、`approval_document=Phase 19 授权书`），并**逐条绑定 proposal sha256**
（append-only 台账）。两轮拆分：第 1 轮（≤35s，切点取旁白句边界）景数 21→**40**、超限占比 100%→**45.0%**；
第 2 轮（≤25s）→ 景数 **42**、占比 **38.1%**；第 3 轮**无变化 ⇒ 切点耗尽**。
**未达 ≤20%**，按授权口径**不按固定秒数硬切**（会破坏旁白-画面对齐），如实报改善幅度并登记 LIMITATION。
**文本零改动硬校验通过**：4927→4927 字符、978.656→978.656 s。派生脚本 v2：
`output/phase19_script_sandbox/script_dcv2_split_v2.json`（42 段）。
**⚠️ 关键兼容性发现**：**拆镜后 42 段时基与既有 `voice_output`（21 段）冲突** —— 渲染前闸门报
`voice 产物不完整：缺少合法音频的段落 [21..41]` + `G-SUB FAIL` ⇒ **拆镜执行必须与旁白重配/音频重切同阶段进行**。
这是 P19-4 沿用 21 段时基、以及 **DQ-3 本阶段零改善**的直接原因。

**P19-4 交付级最终渲染（已执行）。** 沙箱 `p_50e10b27b44d`、任务 `t_a4d8c1aafd04`、**115.1 s**；
运动 `enabled=true`（12/21 景、**0 fallback**）+ **仲裁层 `enabled=true`**；
标记素材重选 **4 处**（S02 `a3f0e27204cd`→`301ff850be9c`、S03 `432cd85be6f1`→`33b360a5363c`、
S05 `23e71bc8a864`→`3f0b94a3f2ac`、S08 `5144139591a0`→`65377b888b77`；**每次替换后立即计入复用计数以免 DQ-2 恶化**）。
候选 `projects/p_50e10b27b44d/output/t_a4d8c1aafd04_draft.mp4`（41,263,003 B），
**未登记 `render_output`/`attribution`**（首跑被核验门阻断 ⇒ fail-closed）⇒ **非交付物**。
**全门复验**：时长 **978.66 s**（978.7±1 ✔，Δ−0.04）｜响度 **−16.1 LUFS / −2.5 dBTP** ✔｜
PI 渲染前全 PASS（PI-1/2/6 + G-TL/G-PAD/G-SUB）｜PI 渲染后全 PASS 且 `promote_blocked=False` ✔｜
字幕 `SUBTITLE_ALIGNED`（216 cue、语音内占比 1.0、越界 0 s）✔｜逐景核验+仲裁 **仲裁前失败 4 → 仲裁后失败 0** ✔｜
MOTION_VERIFIED **12/12**、0 fallback ✔。
**DQ 复算**：**DQ-2 PASS**（10 唯一素材；单素材最大复用 **5 景** = `23e71bc8a864`）；
**DQ-3 FAIL 且零改善**（max_hold 67.374 s、21/21 超 25 s）—— 因 §P19-3 的 voice 时基冲突，渲染实际沿用 21 段时基。
**交付级判定**：全门通过 + DQ-2 PASS **均满足**，但 **DQ-3 零改善**（授权书要求"显著改善+如实报告"）
且候选**未登记 render_output** ⇒ **登记为「全门通过的候选」，不登记为"交付级候选 PASS"**；promotion 交人工。

**边界**：LLM **$0**、VLM **$0.0201**（P18-3 $0.0180 + P19-4 仲裁 $0.0021；≤$0.5）、网络 **0**、渲染 115.1 s；
`config.json`、DB schema、**PI 阈值与判定语义**、`mm_*` 冻结栈、词表、baseline、冻结真值、v9/H5 母片与既有候选**均未改**；
**零 promotion**、未发布、**未自动改旁白文本**（字符数与时长效验通过）、未跳过任何人工批准。

"""


def prepend(path: pathlib.Path, block: str, anchor: str):
    t = path.read_text(encoding="utf-8")
    if "Phase 19" in t[:8000]:
        print("已含 Phase 19，跳过:", path.name)
        return
    i = t.find(anchor)
    path.write_text((t[:i] + block + t[i:]) if i >= 0 else (block + t), encoding="utf-8")
    print("已前插:", path.name)


prepend(R / "STATUS.md", STATUS, "> **Phase 18（度量收口）收尾")
prepend(R / "CHANGELOG.md", CHANGELOG, "## Phase 18 —")
