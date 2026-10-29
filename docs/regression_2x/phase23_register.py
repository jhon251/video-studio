# -*- coding: utf-8 -*-
"""Phase 23 登记：KNOWN_ISSUES（盲测待办 + 信号盲区占位）+ STATUS/CHANGELOG。"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")
STYLE = R / "config" / "style_target_wangxiao_v1.md"
sh = hashlib.sha256(STYLE.read_bytes()).hexdigest()
rnd = json.loads((L / "phase23_rewrite_rounds.json").read_text(encoding="utf-8"))
base = json.loads((L / "phase23_flavor_baseline.json").read_text(encoding="utf-8"))

KI = """
---

## 76. 文案风格重写（Phase 23）：用户盲测**待回答** + AI 味信号**盲区登记** — `OPEN`

### 76.1 盲测待办（**阻塞项**，真值 = 项目所有者）
Phase 23 P23-4 盲测包已就位：`logs/phase23_blind_pack.json`（A/B 已打乱；明文对照封存于
`logs/phase23_blind_answer_key.json`，**验收前请勿查看**）。
**待回答**：q1 哪版更像目标机制？／q2 哪版人味更重？／q3 圈出仍有 AI 味的句子。
**达标线（运行前写死）**：q1 与 q2 **都判 v4 或持平** + 机器信号同向（v4 < v3，**已满足**）
+ 圈出句子**逐条处置**。**未达标** ⇒ 迭代一轮；仍不达标 ⇒ STOP 并转「人工执笔兜底路线」提案。

### 76.2 AI 味信号覆盖不了的句子 ⇒ 登记为**信号盲区**
`core/ai_flavor.py` 的 8 项信号只能覆盖**可机械计数**的 AI 味（推进词／对称构式／设问自答／
句长节奏／冒号展开／破折号／限定语堆叠／段落对称）。以下类型**故意未做信号**（盲区）：
- **语义空转**（说了很多但不推进信息）；
- **伪具体化**（类比贴切度差、类比与概念错配）；
- **立场虚化**（表面上"有态度"，实则无可检验判断）；
- **节奏的"听觉"层面**（朗读顺口度、气口），文本信号无法覆盖；
- **视角跳变**（叙事人称/焦点突然切换）。
⇒ 盲测 q3 若圈出上述类型的句子，**属信号盲区**，按授权书口径**登记而非硬修**。

### 76.3 已知口径限制
- **风格目标文档冻结状态**：`config/style_target_wangxiao_v1.md` 已产出（sha256 见下），
  **待所有者确认后正式冻结**（授权书要求）。
- **v4 内容结论继承 v3 谱系**：**未重跑 claim/事实核查链**（授权明令）⇒ v4 事实层未获新的独立核查。
- **prompt 不含参照例句**：为控体积与防诱导抄袭，system prompt 只投**机制名 + 规则句**；
  防抄依赖**机械 n-gram 守卫**（v4 与参照文本最长公共 **0**）。
"""
p = R / "docs" / "KNOWN_ISSUES.md"
t = p.read_text(encoding="utf-8")
if "## 76." not in t:
    t = t.rstrip() + "\n" + KI + "\n\n> 风格目标 sha256：`{}`\n".format(sh)
    p.write_text(t, encoding="utf-8")
    print("KNOWN_ISSUES #76 已登记")
else:
    print("KNOWN_ISSUES 已有 #76")

STATUS = """> **Phase 23（文案风格重写：目标=说书机制）收尾，2026-09-30 —— 待用户盲测回答**
> **P23-1 机制拆解 DONE ✔｜P23-2 AI 味信号层 DONE ✔（29/29 测试）｜P23-3 全文重写 DONE ✔（LLM 2 轮，第 2 轮 ACCEPTED）｜
> P23-4 盲测包 DONE ✔（**待回答，未作达标声明**）｜P23-5 登记 DONE**
> - **关键数字**：v3 `ai_flavor` **4.5298 → v4 0.0000**（同向 ✔）；**冒号 6.56→0、破折号 2.50→0、推进词 1.25→0.30**；
>   **n-gram 守卫与参照文本最长公共 0**（未抄口头禅）；字数 3337/3339；retention 机械分 **0.6→1.0**；
>   **数字与命名实体零丢失零新增**；成本 **$0.01852 / $0.50**。
> - **P23-1**：`config/style_target_wangxiao_v1.md` —— 7 条机制（授权起点）各配**参照实证例句映射** +
>   固规则 8 条 + 机械校验 6 项。**从参照补强的 4 项发现**：① 参照**零冒号零破折号**（v3 有 21+8）；
>   ② 开场即冲突对话；③ 抽象概念同段给世俗类比；④ 数据后给**即时反应句**而非仅翻译。
>   **冻结状态**：已产出并记 sha256，**待所有者确认后正式冻结**。
> - **P23-2**：新增 `core/ai_flavor.py`（8 信号 + POLICY 逐项机理 + 中文数字归一 + 数字/实体保真 +
>   n-gram 守卫 + retention 机械层）。**一次自我修正（如实）**：初版综合分被 `para_symmetry` 的
>   参照基线（1.0，因参照是逐行字幕无空行）主导、且"优于参照"也被扣分 ⇒ 改为
>   **「相对参照均值的正向偏离加权和」**（优于参照不扣分）。基线：v2 **6.3552**、v3 **4.5298**。
> - **P23-3**：真实 LLM **2 轮**（`deepseek-flash`）。第 1 轮 **ROLLED_BACK**（数字新增 `20`、实体丢失
>   `这个猜想`）、第 2 轮 **ACCEPTED（ai_flavor 0.0000）**。**v4 开场**：「1977 年，Appel 和 Haken 宣布
>   四色定理被证出来了，数学界那会儿的第一反应不是鼓掌。」（事实切入 + 态度外露）
>   +「几十万行」后紧跟人话翻译（机制⑤）。
>   **三处故障与处置（如实）**：① `max_tokens=16384` 被 reasoning 吃满致 content 为空
>   （与 Phase 8 v3 同一现象）⇒ 提到 **32768**；② prompt 瘦身（参照例句**不入 prompt**，防诱导抄袭）；
>   ③ **实体检测器误判**：初版把引号内纯中文描述性引语当实体 ⇒ 加**专名性判定**并记录
>   `quoted_dropped_descriptive` 以便审计。
> - **P23-4 待回答（阻塞项）**：盲测包 `logs/phase23_blind_pack.json`（A/B 打乱，明文对照封存于
>   `phase23_blind_answer_key.json`）——请回答 q1 更像目标机制／q2 人味更重／q3 圈出仍有 AI 味的句子。
>   **达标线运行前写死**：q1 与 q2 都判 v4 或持平 + 机器信号同向（**已满足**）+ 圈出句子逐条处置。
> - **P23-5 交付**：style_target / `core/ai_flavor.py` + `tests/ai_flavor_test.py`（**29/29**）/
>   `phase23_flavor_baseline.json` / `phase23_rewrite_rounds.json` / `phase23_blind_pack.json` /
>   **v4 稿全文** `phase23_v4_script.json` / `PHASE23_REPORT.md`。
> - 边界：`config.json`/DB schema/门禁/`mm_*` 冻结栈/词表/baseline/渲染素材**均未改**；
>   **未重跑 claim 提取链**（LIMITATION）；**未抄任何创作者口头禅**（守卫机械保证 0）。
>   回归 **78/78 rc=0**、**IMMUTABLE_OK**。详见 `PHASE23_REPORT.md`；盲区与待办入 **KNOWN_ISSUES #76**。

"""

CHANGELOG = """## Phase 23 — 文案风格重写（目标=王骁式说书机制）：信号层 + 2 轮重写，v4 ai_flavor 4.53→0.00，待用户盲测（2026-09-30）

**P23-1 参照处理与机制拆解 DONE。** 通读人工提供的王骁真实口播字幕
（`config/human_style_refs/wangxiao_zhongdong_科威特.txt` 160 行、
`..._埃及.txt` 599 行），产出 **`config/style_target_wangxiao_v1.md`**：
授权书 7 条机制为底，每条配 **规则 / 参照实证例句（机制→例句映射）/ 机理 / 对 v3 的应用**，
外加固规则 8 条 + 机械校验 6 项。**从参照补强 4 项发现**：① 参照文本**零冒号、零破折号**
（v3 有 21 个冒号 + 8 个破折号）；② 开场即**冲突对话引用**；③ 抽象概念在**同段内**给世俗类比；
④ 数据后给**即时反应句**（如「很多人都看愣了」）而不只是翻译。**铁律**：只学机制不抄句子，
例句仅供内部参照、一律不入稿；**文档待所有者确认后正式冻结 sha256**。

**P23-2 AI 味信号层 DONE。** 新增 `src/video_studio/core/ai_flavor.py`（机械、确定性、零 LLM）：
8 项信号（推进词密度／「不是A而是B」频率／设问自答／句长 CV／冒号展开／破折号补充／限定语堆叠／
段落对称性）+ `POLICY` 逐项机理 + 中文数字归一 + 数字保真 + 命名实体保真 + **n-gram 守卫** +
retention 机械层。**一次自我修正（如实登记）**：初版综合分把 8 项简单加权求和，被 `para_symmetry`
的参照基线（**1.0**，因参照是逐行字幕、无空行分段）主导，且"优于参照"也被扣分 ⇒
改为 **「相对参照均值的正向偏离加权和」**（`SCORE_WEIGHTS` / `HIGHER_IS_BETTER`）⇒ **优于参照不扣分**。
**基线**（`logs/phase23_flavor_baseline.json`）：v2 **6.3552**、v3 **4.5298**、参照为基准。
新增 `tests/ai_flavor_test.py`（**29/29 通过**）。

**P23-3 全文重写管线 DONE（真实 LLM 2 轮）。** 输入 v3 稿（8 段/3201 字），
system = style target 机制 + 硬规则 10 条；每轮后 6 项机械校验，**违反即回滚该轮**。
第 1 轮 **ROLLED_BACK**（数字新增 `20`、实体丢失 `这个猜想`，ai_flavor 0.2985）；
**第 2 轮 ACCEPTED（ai_flavor 0.0000）**，六项校验全过：数字保真 ✔、实体保真 ✔、
fact_risks 13 条不减少 ✔、retention 机械分 **0.6→1.0** ✔、字数比 **1.0006** ✔、
**n-gram 守卫与参照文本最长公共 0** ✔。
**v4 开场**：「1977 年，Appel 和 Haken 宣布四色定理被证出来了，数学界那会儿的第一反应不是鼓掌。」
（事实切入 + 态度外露，替换 v3 的「先做一个假设」）；「几十万行」后紧跟**人话翻译**
（「你一行一秒往下读，好几天不睡觉也读不完，人脑扛不住」）。
**三处故障与处置（如实登记）**：① `max_tokens=16384` 被 reasoning 吃满致 content 为空
（`LLM_REASONING_BUDGET_EXHAUSTED`，与 Phase 8 v3 同一现象）⇒ 提高至 **32768**；
② **prompt 瘦身**：参照例句**不入 prompt**（① 体积；② 反而诱导抄参照），改由机械 n-gram 守卫负责防抄；
③ **实体检测器误判**：初版把引号内纯中文描述性引语（如「被读完并被理解」）当命名实体 ⇒
加**专名性判定**（引号内须含拉丁/数字或以机构/定理后缀结尾），并把被丢弃项记入
`quoted_dropped_descriptive` 以便审计。**成本 $0.01852 / $0.50**。

**P23-4 用户盲测验收（待回答，未作达标声明）。** 盲测包 `logs/phase23_blind_pack.json`
（A/B **已打乱**，明文对照封存于 `logs/phase23_blind_answer_key.json`，验收前请勿查看），
参照文本**并列**在包内；含三问（q1 更像目标机制／q2 人味更重／q3 圈出仍有 AI 味的句子）。
**达标线运行前写死**：q1 与 q2 **都判 v4 或持平** + 机器信号同向（v4 4.5298→0.0000，**已满足**）
+ 圈出句子逐条处置。未达标 ⇒ 带清单迭代一轮；仍不达标 ⇒ STOP 并转「人工执笔兜底路线」提案。

**边界**：LLM **$0.01852**、VLM **$0**；`config.json`、DB schema、门禁、`mm_*` 冻结栈、词表、
baseline、渲染素材**均未改**；**未重跑 claim/事实核查链**（v4 内容结论继承 v3 谱系，按继承方法登记
LIMITATION）；**未抄任何创作者口头禅**（n-gram 守卫机械保证 0）。回归 **78/78 rc=0**、**IMMUTABLE_OK**。
**KNOWN_ISSUES #76** 登记盲测待办、信号盲区（语义空转／伪具体化／立场虚化／听觉节奏／视角跳变）与口径限制。

"""


def prepend(path: pathlib.Path, block: str, anchor: str):
    t = path.read_text(encoding="utf-8")
    if "Phase 23" in t[:9000]:
        print("已含 Phase 23，跳过:", path.name)
        return
    i = t.find(anchor)
    path.write_text((t[:i] + block + t[i:]) if i >= 0 else (block + t), encoding="utf-8")
    print("已前插:", path.name)


prepend(R / "STATUS.md", STATUS, "> **Phase 21（派生段时基与绑定收口）收尾")
prepend(R / "CHANGELOG.md", CHANGELOG, "## Phase 21 —")
print("风格目标 sha256:", sh)
