# -*- coding: utf-8 -*-
"""Phase 14 登记：STATUS.md / CHANGELOG.md 前插条目 + KNOWN_ISSUES.md 追加候选。
只做**前插/追加**，不改任何历史条目（append/prepend-only）。"""
from __future__ import annotations

import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")

STATUS_BLOCK = """# 建设进度清单（断点续做的唯一依据）

> **状态更新（Phase 14 收尾，2026-09-30）**：Phase 13-E ② 的渲染作业**已执行**（见下），本节已按现实更新；
> 历史「未启动」陈述**保留**于其后（不删改历史）。
>
> **Phase 14（VLM 视觉相关性判定）：P14-1 DONE ✔ ｜ P14-2 DONE（**门禁 FAIL**）｜ P14-3 未执行（按授权书不集成）｜ P14-4 DONE**
> - **P14-1**：新增 `tools/vlm_judge.py`（OpenAI 兼容 + 最长边≤768px/JPEG q80 确定性降采样 + `temperature=0` +
>   JSON/Schema 校验 + `PROVIDER_*` fail-closed + 文件缓存 + 三级 `resolve_config`，**默认关闭**）、
>   `tools/vlm_eval.py`、`run.py vlm-eval`（只读）、`config/vlm_judge.example.json`。
> - **P14-2**：冻结真值集 `tests/fixtures/vlm_relevance_truth_v1.json`（**27 对**：RELEVANT 24 / IRRELEVANT 3，
>   sha256 `6104cfc202113510…`，逐对 provenance）。**⚠️ 未达 ≥30 对**（全仓仅 27 对带显式人工证据；缺口运行前登记，
>   **未用机器判定充数**）。达标线运行前写死：`agreement ≥ 90%` 且 `人工 IRRELEVANT→机器 RELEVANT = 0`。
> - **实测结果**：`agreement = 3/27 = 11.11%`（**FAIL**）；`人工 IRRELEVANT→机器 RELEVANT = 0`（通过）；
>   正例误判 16；非二值 8。**成本 $0.0201**（上限 $2）。⇒ **按授权书「未达标只报告不集成」，未接线任何生产链。**
> - **失配根因（有证据）**：`visual_goal` 派生自脚本/分镜的**生成式画面描述**，而人工 operator 判的是
>   **叙事/主题切题性** —— 两者**判据不同源**；模型逐条精确地指出「缺某元素」，属**按字面正确执行**。
>   诊断变体（口径改为「话题同一性」，**不参与门禁**）仅把一致率提到 25.93% ⇒ **不是提示词措辞问题**。
>   **关键不对称**：两个变体下「人工 IRRELEVANT→机器 RELEVANT」**均为 0** ⇒ 该 VLM 在此设定下是
>   **可靠的拒绝器、不可靠的确认器**。
> - 成本台账：门禁 $0.0201 + 诊断变体 $0.0167 + 连通性探针 $0.0006 = **$0.0368**（上限 $2）；
>   单价表标注 `verified=False`（**未按真实账单核对**，成本为估算，不参与任何判定）。
> - 边界：**未改** `config.json`、**未写 DB**、**未接线** agent、**未放宽**任何阈值、**零 promotion**；
>   仅**新增** `tools/vlm_judge.py`、`tools/vlm_eval.py` 与 `cli.py` 的**新增只读子命令**。
> - 产物：`logs/phase14_eval_report.json`（门禁）、`logs/phase14_eval_diag_anchor.json`（诊断）、
>   `logs/phase14_label_inventory.json`、`tests/fixtures/vlm_relevance_truth_v1.json`；
>   **未产出** P14-3 集成与 `logs/phase14_na_resolution.json`（门禁未过）。
>
> **Phase 13-E ② 全片运动候选渲染（已执行，2026-09-30）**：沙箱项目 `p_e4c65c1c58ed`，
> 后台作业 **207.4 s**，产出候选 `projects/p_e4c65c1c58ed/output/t_249079cc5431_draft.mp4`（59,832,977 B，
> sha256 `af1e22ed0abc7f89…`）；运动 `enabled=true` 命中 **12/21 景**、**0 fallback**。
> 实测：**时长 978.66 s**（978.7±1 内）、**响度 I=−16.1 LUFS / TP=−2.5 dBTP**（达标）、
> **PI 渲染前/后全 PASS**、**字幕对齐全 PASS**（216 cue、orphan 0）；**逐景 corr 20/21**（冻结口径 0.30）。
> **渲染后核验硬门因 S03（corr 0.1536）阻断** ⇒ fail-closed **未登记 `render_output`/`attribution`**（非交付物）。
> 独立复核证明 S03 **素材确在屏**（成片帧与静态模板同图；运动反而把相关度从 0.153 提到 0.172），
> 属**冻结度量对稀疏线稿的结构性盲区**；**未放宽任何阈值、未改度量、未改生产代码**。
> 回归 **77/77 rc=0**、**IMMUTABLE_OK**、**零 promotion**。DQ 双口径：DQ-2/DQ-3 FAIL（素材池贫瘠 5 张真图 +
> 单景过长）、`freezedetect` 218 块并列说明，**不宣称 PASS**。详见 `PHASE13E_REPORT.md` §10。

"""

CHANGELOG_BLOCK = """## Phase 14 — VLM 视觉相关性判定：P14-1 **DONE**；P14-2 真实评测门禁 **FAIL（11.11%）⇒ 不集成**（2026-09-30）

**P14-1 provider（DONE）**：新增 `src/video_studio/tools/vlm_judge.py`，按 `PHASE14_REPORT.md` §4 冻结设计落地：
OpenAI 兼容 `chat/completions` + 图像输入；**确定性降采样**（最长边 ≤768px、JPEG q80、`LANCZOS`，参数入 `POLICY` 并注明依据=成本控制）；
`temperature=0`；JSON 输出 + Schema 校验（label 枚举/reason/confidence）；超时 90 s + 重试 2 次 + 指数退避；
`PROVIDER_*` fail-closed（10 个错误码，失败不抛异常、label 置 `NOT_ASSESSABLE`）；**文件缓存**
`output/vlm_judge_cache/<sha256[:32]>.json`（键 = `prompt_version|model|image_sha256|need_text_sha256`，命中即 $0）；
`resolve_config` 三级链（内存 `config.tools.vlm_judge` → `config/vlm_judge.json` → 默认 `{"enabled": false}`），
key **只从环境变量**读；**判定独立性**（单次只看一个 (需求, 候选图) 对，prompt 刻意不含同景其它候选/分数/任何既有结论）。
另新增 `tools/vlm_eval.py`、只读 CLI `run.py vlm-eval`、`config/vlm_judge.example.json`。
**未改 `config.json`、未接线任何生产 agent。**

**P14-2 冻结真值集**：`tests/fixtures/vlm_relevance_truth_v1.json`，**27 对**（RELEVANT 24 / IRRELEVANT 3），
sha256 `6104cfc202113510…`，逐对带 provenance（来源文件 + 定位字段 + **人工原文理由**）与 requirement 快照。
**⚠️ 未达授权要求的 ≥30 对**：全仓仅存在 27 对带显式人工正/负证据的 (镜头, 素材) 对；缺口**运行前登记并保留**，
**未**用机器判定充数。`selection_override` 541 条中约 516 条为鉴权测试，其 `before_asset_id` 混杂后期**许可/镜次身份**
替换且与同对正例标签**自相矛盾**，故**排除**。达标线**运行前写死**：`agreement ≥ 90%` 且
`人工 IRRELEVANT→机器 RELEVANT = 0`；归一规则写死：`PARTIAL`/`NOT_ASSESSABLE`（含失败）**一律计为不一致**。

**P14-2 实测（真实 API）**：`agreement = 3/27 = 11.11%` ⇒ **FAIL**；`人工 IRRELEVANT→机器 RELEVANT = 0` ⇒ 通过；
正例误判 RELEVANT→IRRELEVANT 16；非二值 8。成本 **$0.0201**（上限 $2）。二次运行走缓存 ⇒ **$0 且报告 sha256 逐字节一致**（已实测）。

**P14-3（集成 + 143 对 NA 实测）：未执行** —— 按授权书「严禁在门禁未通过前接线」，**未改任何生产链**、
**未产出** `logs/phase14_na_resolution.json`。

**失配根因（有证据，未调参掩饰）**：`visual_goal` 派生自脚本/分镜的**生成式画面描述**
（如 S01「暗背景，长串无法辨识的证明步骤缓慢滚动」），而人工 operator 的理由是**叙事/主题切题性**
（如 S01「真实 IMO 数学国家队合影，契合『数学与人类』主题」）⇒ **判据不同源**。模型理由逐条精确
（S08 球堆↔开普勒判 RELEVANT；S03「与四色定理相关，但未体现『空椅子与屏幕光』」判 PARTIAL），
属**按字面正确执行**。诊断提示词变体（口径改为「话题同一性」，**明确不参与门禁**）仅把一致率提到 **25.93%**
（`logs/phase14_eval_diag_anchor.json`）⇒ **失配不是提示词措辞造成的**。
**关键不对称（可用于生产设计）**：两个变体下「人工 IRRELEVANT→机器 RELEVANT」**均为 0**、机器仅 1–5 次判 RELEVANT
⇒ 该 VLM 在此设定下是**可靠的拒绝器、不可靠的确认器**。

**成本/边界**：总 API 花费 **$0.0368**（门禁 27 对 $0.0201 + 诊断 27 对 $0.0167 + 连通性探针 $0.0006），上限 $2 ✔；
单价表 `verified=False`（**未按真实账单核对**，成本为估算，不参与任何判定）。**未改** `config.json`、**未写 DB**、
**未接线** agent、**未放宽**任何阈值、**零 promotion**；冻结产物（母片/DCv2/baseline/真值）**零改动**。

"""

ISSUE_BLOCK = """
---

## 73. VLM 视觉相关性判定：**判据与人工不同源**（DQ/P7-4 需求语义 vs 人工叙事切题性）— `OPEN`

| 编号 | 内容 | 证据 |
|---|---|---|
| **#73** | P14-2 冻结真值集（27 对，RELEVANT 24 / IRRELEVANT 3）上，`qwen3-vl-plus` 的
`overall agreement = 3/27 = 11.11%`（阈值 90%）⇒ **门禁 FAIL、P14-3 未集成**。 | `logs/phase14_eval_report.json`；
`tests/fixtures/vlm_relevance_truth_v1.json`（sha256 `6104cfc202113510…`） |

- **性质**：**判据定义层面的失配**，不是模型故障、也不是提示词措辞问题。
  `visual_goal` 派生自脚本/分镜的**生成式画面描述**（`visual_requirements.json#builder_rules R-GOAL`：
  `visual_goal ← shot_description`），而人工 operator 的选材理由是**叙事/主题切题性**。
  模型据字面逐元素比对，故大量判 `IRRELEVANT`/`PARTIAL`，属**按给定任务正确执行**。
- **不是措辞问题（已证）**：把口径改为「话题同一性、可作视觉锚点」的诊断变体（**不参与门禁**）
  仅把一致率从 11.11% 提到 **25.93%**（`logs/phase14_eval_diag_anchor.json`）。
- **关键不对称（正面发现）**：两个变体下「人工 IRRELEVANT → 机器 RELEVANT」**均为 0**，且机器仅 1–5 次判 RELEVANT
  ⇒ 该 VLM 在此设定下是**可靠的「拒绝器」**、但**不是可靠的「确认器」**。
- **为何本阶段不修**：授权书明令「评测门禁前置、未达标只报告不集成」；修它需要改 **P7-4 需求语义**
  或另立「主题切题性」判定规范，属**跨阶段口径决策**，须人工授权。
- **影响**：143 对 `NOT_ASSESSABLE` **仍未被解析**（P14-3 未执行）；HITL 面未缩小。
  附带遗留：`visual_relevance.json` 中 RELEVANT 依 `human_*` 证据、其余落 NA，
  **机器判定不得充当人工真值**（本阶段未越界）。
- **建议处置（择一，需新授权）**：① 把 `visual_goal` 与人工判据的统一写成**显式判定规范**（改 P7-4 语义）后重跑门禁；
  ② 把该 VLM 改为**负例过滤/降 HITL 面**用途（仅拒收 IRRELEVANT），并**另立只含负例的评测集**验证；
  ③ 人工补足 **≥30 对**真值（含更多负例）后重跑（当前 27 对、负例仅 3，置信度不足）。

### 真值集规模不足（连带登记）
- P14-2 授权要求 **≥30 对**人工真值；全仓实测仅 **27 对**带显式人工正/负证据 ⇒ **未达标**，
  已在运行前登记并保留缺口，**未用机器判定充数**（经用户确认按 27 对执行）。
- 缺口原因：`visual_relevance.json` 的 RELEVANT 依 `human_*` 证据、其余 143 对为 NA（无人工标签）；
  `selection_override` 的 541 条中约 516 条为鉴权测试，其余 `before_asset_id` 混杂**许可/镜次身份**替换，
  与同对正例标签自相矛盾，**不可**作相关性负例。
"""


def prepend_after(path: pathlib.Path, block: str, anchor_prefix: str | None):
    txt = path.read_text(encoding="utf-8")
    if "Phase 14" in txt[:4000] and "P14-2" in txt[:4000]:
        print("已存在 Phase 14 登记，跳过:", path.name)
        return
    if anchor_prefix:
        i = txt.find(anchor_prefix)
        if i >= 0:
            # 插到该 anchor 之前
            new = txt[:i] + block + txt[i:]
            path.write_text(new, encoding="utf-8")
            print("已前插于 anchor 之前:", path.name, "| anchor:", anchor_prefix[:40])
            return
    path.write_text(block + txt, encoding="utf-8")
    print("已前插于文件头:", path.name)


def append(path: pathlib.Path, block: str):
    txt = path.read_text(encoding="utf-8")
    if "## 73." in txt:
        print("KNOWN_ISSUES 已含 #73，跳过")
        return
    i = txt.find("## 变更纪律")
    if i >= 0:
        new = txt[:i] + block.strip() + "\n\n" + txt[i:]
    else:
        new = txt.rstrip() + "\n" + block
    path.write_text(new, encoding="utf-8")
    print("已追加:", path.name)


def fix_status(path: pathlib.Path):
    """清理前插产生的重复 H1 与空行：保留 1 个标题 + 1 个空行 + 正文。"""
    txt = path.read_text(encoding="utf-8")
    h1 = "# 建设进度清单（断点续做的唯一依据）"
    if txt.count(h1) > 1:
        first = txt.find(h1)
        second = txt.find(h1, first + 1)
        body = txt[second + len(h1):].lstrip("\n")
        txt = h1 + "\n\n" + body
        path.write_text(txt, encoding="utf-8")
        print("已修正 STATUS.md 重复标题；剩余标题数:", path.read_text(
            encoding="utf-8").count(h1))
    else:
        print("STATUS.md 标题数正常:", txt.count(h1))


prepend_after(R / "STATUS.md", STATUS_BLOCK + "> ", "> **Phase 13-E ② 全片运动候选渲染")
prepend_after(R / "CHANGELOG.md", CHANGELOG_BLOCK, "## Phase 13-E 最终执行")
append(R / "docs" / "KNOWN_ISSUES.md", ISSUE_BLOCK)
fix_status(R / "STATUS.md")
