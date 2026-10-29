# -*- coding: utf-8 -*-
"""Phase 23 收尾登记：盲测达标 + q3 处置 + v4.1 定稿（更新 KNOWN_ISSUES #76 + STATUS/CHANGELOG）。"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")
disp = json.loads((L / "phase23_q3_disposition.json").read_text(encoding="utf-8"))
v41p = L / "phase23_v4_1_script.json"
v41_sha = hashlib.sha256(v41p.read_bytes()).hexdigest()

# ---------- KNOWN_ISSUES #76 更新：盲测已答 ⇒ 达标 ----------
p = R / "docs" / "KNOWN_ISSUES.md"
t = p.read_text(encoding="utf-8")
OLD = "## 76. 文案风格重写（Phase 23）：用户盲测**待回答** + AI 味信号**盲区登记** — `OPEN`"
NEW = "## 76. 文案风格重写（Phase 23）：盲测**已达标**、q3 清单已处置、v4.1 定稿 + AI 味信号**盲区登记** — `MITIGATED`"
if OLD in t:
    t = t.replace(OLD, NEW, 1)
UP = """
### 76.1-update 盲测结果与 q3 处置（**已达标，2026-10-01**）
**盲测结果**：**q1 = B（更像目标机制）、q2 = B（人味更重）** ⇒ 两问均判 v4，
机器信号同向（v4 `ai_flavor` 0.0000 < v3 4.5298）⇒ **判定达标**。
**q3 清单 4 条逐条处置**（见 `logs/phase23_q3_disposition.json`，**零额外 LLM 调用**）：
| # | 问题 | 处置 |
|---|---|---|
| ① | 路线图报幕段 | **删除** seg1 的时间线报幕句与"承诺说清"句，保留反方立场句 |
| ② | 「钉死/交代清楚/标清楚」元叙述过多 | **保留 2 处**（≤2 上限）、其余 4 处**折入正文** |
| ③ | 「不满足这个框架」书面腔 | 改口语「套不进这个二选一」 |
| ④ | 「问题有两层」枚举式 | 改口语句式并折入正文（"两件事都躲不开"） |
**处置后复跑**：六项机械校验**全过**；信号**无回退**（`ai_flavor` 0.0000 保持；推进词 0.2997→0.2995；
句长 CV 0.5608→0.5590；字数 3337→3339）。**v4.1 定稿**：`logs/phase23_v4_1_script.json`
（sha256 `{}`）。
**口径提示**：q3 的 4 条**全部落在信号可覆盖范围**（元叙述/报幕/书面腔/枚举），
故**本轮未新增信号盲区实例**；§76.2 列出的五类盲区（语义空转／伪具体化／立场虚化／
听觉节奏／视角跳变）仍为**待观察**状态。
""".format(v41_sha)
if "76.1-update" not in t:
    anchor = "### 76.2 AI 味信号覆盖不了的句子"
    i = t.find(anchor)
    t = (t[:i] + UP + "\n" + t[i:]) if i >= 0 else (t.rstrip() + "\n" + UP)
p.write_text(t, encoding="utf-8")
print("KNOWN_ISSUES #76 已更新为 MITIGATED")

STATUS = """> **Phase 23 盲测达标 ⇒ v4.1 定稿（2026-10-01）**
> - **盲测结果（真值 = 项目所有者）**：**q1 = B、q2 = B** ⇒ 两问均判 v4，机器信号同向
>   （v4 `ai_flavor` **0.0000** < v3 **4.5298**）⇒ **判定达标**。
> - **q3 清单 4 条已逐条处置（零额外 LLM 调用）**：① **删除**路线图报幕段（seg1 时间线报幕句 +
>   承诺说清句，保留反方立场句）；② 元叙述（钉死/交代清楚/标清楚）**保留 2 处**（≤2 上限）、
>   其余 4 处**折入正文**；③ 「不满足这个框架」→ 口语「**套不进这个二选一**」；
>   ④ 「问题有两层」枚举 → 口语句式并折入正文（"两件事都躲不开"）。
> - **处置后复跑**：六项机械校验**全过**（数字/实体零丢失零新增、fact_risks 13 条不减、
>   retention 1.0、字数比 1.0000、n-gram 守卫 0）；**信号无回退**（`ai_flavor` **0.0000** 保持，
>   推进词 0.2997→0.2995、句长 CV 0.5608→0.5590、字数 3337→3339）。
> - **v4.1 定稿**：`logs/phase23_v4_1_script.json`（sha256 `{}…`）—— 供 **Phase 24 渲染使用**。
> - q3 的 4 条**全部落在信号可覆盖范围**（元叙述/报幕/书面腔/枚举）⇒ **本轮未新增信号盲区实例**；
>   KNOWN_ISSUES #76 的"信号盲区"五类仍为**待观察**。**#76 状态 OPEN → MITIGATED**。
> - 成本：本阶段 LLM 合计 **$0.01852 / $0.50**（q3 处置 **$0**）。详见 `PHASE23_REPORT.md`

""".format(v41_sha[:16])

CHANGELOG = """## Phase 23 收尾 — 盲测达标（q1=B/q2=B）⇒ q3 四条处置 + v4.1 定稿（2026-10-01）

**盲测结果**：项目所有者判定 **q1 = B（更像目标机制）、q2 = B（人味更重）** ⇒ 两问均判 v4；
机器信号同向（v4 `ai_flavor` **0.0000** vs v3 **4.5298**）⇒ **达标**。

**q3 清单 4 条逐条处置（纯文本处置，零额外 LLM 调用）**
| # | 用户圈出的问题 | 处置 |
|---|---|---|
| ① | 路线图报幕段 | **删除** seg1 的时间线报幕句与"承诺说清"句；保留反方立场句 |
| ② | 「钉死/交代清楚/标清楚」类元叙述过多 | **保留 2 处**（≤2 上限：seg5「这里有两处得说清楚」、seg4「这句话得说清楚来源」）；seg1/seg2/seg4/seg6 共 **4 处折入正文** |
| ③ | 「不满足这个框架」书面腔 | 改口语「**套不进这个二选一**」 |
| ④ | 「问题有两层」枚举式 | 改口语句式并折入正文（"两件事都躲不开"） |

**处置后复跑（确认无回退）**：六项机械校验**全过** —— 数字保真 ✔、命名实体保真 ✔、
`fact_risks` **13 条不减** ✔、retention 机械分 **1.0** ✔、字数比 **1.0000** ✔、
**n-gram 守卫与参照文本最长公共 0** ✔。信号：**`ai_flavor` 0.0000 保持**（推进词 0.2997→0.2995、
句长 CV 0.5608→0.5590、冒号/破折号/限定语堆叠均维持 0）；字数 3337→3339。

**v4.1 定稿**：`logs/phase23_v4_1_script.json`（sha256 `{}`）—— **供 Phase 24 渲染使用**。
处置台账：`logs/phase23_q3_disposition.json`（含四条的 user_instruction → action 映射与信号对比）。

**盲区口径**：q3 的 4 条**全部落在信号可覆盖范围**（元叙述／报幕／书面腔／枚举）⇒
**本轮未新增信号盲区实例**；KNOWN_ISSUES **#76** 中"信号盲区"五类（语义空转／伪具体化／
立场虚化／听觉节奏／视角跳变）仍为**待观察**。**#76 状态 `OPEN` → `MITIGATED`**。

**成本**：Phase 23 全程 LLM **$0.01852 / $0.50**（q3 处置 **$0**，未调用 LLM）；VLM $0。

""".format(v41_sha)


def prepend(path: pathlib.Path, block: str, anchor: str):
    t = path.read_text(encoding="utf-8")
    if "v4.1 定稿" in t[:9000]:
        print("已含 v4.1 登记，跳过:", path.name)
        return
    i = t.find(anchor)
    path.write_text((t[:i] + block + t[i:]) if i >= 0 else (block + t), encoding="utf-8")
    print("已前插:", path.name)


prepend(R / "STATUS.md", STATUS, "> **Phase 23（文案风格重写：目标=说书机制）收尾")
prepend(R / "CHANGELOG.md", CHANGELOG, "## Phase 23 —")
print("v4.1 sha256:", v41_sha)
print("v4.1 字数:", disp["no_regression_check"]["chars_v4_1"])
