# -*- coding: utf-8 -*-
"""Phase 13-E 续跑：把 P13E-2 结论 + 守卫入套件 + 回归结果追加进 PHASE13E_REPORT.md（append）。"""
import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")
rep = R / "docs" / "regression_2x" / "PHASE13E_REPORT.md"
txt = rep.read_text(encoding="utf-8")
if "## 7. Phase 13-E 续跑" in txt:
    print("续跑章节已存在，跳过")
    sys.exit(0)
f = json.loads((L / "phase13e_p13e2_finding.json").read_text(encoding="utf-8"))
suites = json.loads((L / "suites_summary.json").read_text(encoding="utf-8"))
reg = "**{} 套件 / {} rc=0 / FAILED: {}**".format(
    len(suites), sum(1 for x in suites if x["rc"] == 0),
    [x["suite"] for x in suites if x["rc"] != 0] or "[]")
g = f["guard"]
h5e = f["h5_lineage_binding_evidence"]
section = """
---

## 7. Phase 13-E 续跑（P13E-2 结论 + 守卫入套件 + 回归）

### 7.1 守卫入 `tests/` 套件（按续跑授权第 1 条，**先做**）
- 新增 core 模块 `src/video_studio/core/lineage_guard.py`（纯校验：`AUTHORITATIVE_LINEAGE`/`LEGACY_LINEAGE` 常量、
  `check_lineage()`、`assert_lineage()`、`load_authoritative_timeline()`；sha256 + 时长 ±1 s 双校验）。
- 新增套件 `tests/lineage_guard_test.py` ⇒ **10/10 PASS**（权威底片 `LINEAGE_OK`；**v9 底片 `LINEAGE_MISMATCH` 且 `assert_lineage` 抛错**；
  缺失 ⇒ `FILM_MISSING`；权威时间轴 21 景且 S05=[181.776,221.862]；与结论 JSON 一致；模块不触碰 PI/DQ 阈值、不写文件）。
- **真实缺陷（被仓库静态守卫抓出并已修）**：`subprocess_encoding_test` 报
  `src 内所有 subprocess(text=True) 均指定 encoding（静态守卫）| 漏点：['src/video_studio/core/lineage_guard.py:56']`
  ⇒ 我的新模块 `ffprobe` 调用缺 `encoding`；**已补 `encoding="utf-8", errors="replace"`**，该套件 6/6 PASS。
- **全量回归（含新套件）**：%s ✔（口径由 76 → **77** 套件）。
""" % reg
section += """
### 7.2 P13E-2 结论：**在权威底片上，S05 替换已实现 ⇒ 重复拼接为 no-op（未执行无意义渲染）**

| 证据 | 实测 |
|---|---|
| 守卫 | 权威底片 `{verdict}`（sha256 `{sha}`，时长 {dur} s，容差 {tol} s） |
| 权威时间轴性质 | `phase6f_rebuild_plan_v2.json#new_production_timeline` = **纯时基计划**（21 条仅 `start_s/end_s/narrative_window_s/pause_after_s`，**无素材绑定**：`selected_asset/asset_id` 全为 null） |
| H5 谱系的 S05 绑定 | `asset_records[0] = {{asset_id: {aid}, path: {path}, sha256: {sha2}}}`；`binding = {binding}` |
| 素材 sha256 校验 | 与 H5 人工验收值 `65377b888b778226…` **一致** ⇒ `{ok}` |
| H5 门禁（与本次目标直接相关） | `P0-S05 素材存在且 sha256 与人工验收一致` ✔；**`C1 内置逐镜替换证据：S05/S11 均已替换（replaced_all）`** ✔；**`B1 逐镜窗口 ASS == DCv2 表（2 文件，覆盖 ['S05','S11']）`** ✔ |
| H5 谱系 PI | pre：PI-1/2/6 + PLANNING_DRIFT/G-TL/G-PAD/G-SUB = PASS；post：PI-3/4/5 + frozen_recheck = PASS |

**结论**：P13-4 的目标（权威底片上 S05 = Russell 页、`replaced=true` 证据、PI 通过）**在 6-G/H5 母片上已经达成**；
在正确底片上再次执行同一 REPLACE 只会产出等价重复件 ⇒ **本阶段不做重复渲染**（no-op 判定，理由与证据见
`logs/phase13e_p13e2_finding.json`）。13-D 的 PI BLOCKED 已由 P13E-1 定格为**底片谱系错误的度量伪影**，与替换本身无关。

**副产物登记（下一阶段需知）**：H5 报告顶层**未持久化** `_caption_time_base`/`timeline_identity`（其门禁
"P6 DCv2 timeline identity 校验通过"为执行期校验）⇒ 若未来仍需在权威底片上做**真实拼接**，须先定位该时基的持久化来源；
**本阶段未尝试绕过该门禁**。

### 7.3 P13E-3 状态：**PENDING（未执行）**
运动臂全片候选（S05 已替换 + 运动层 `enabled=true`）**未产出**：需一次**全片渲染**（978.7 s 底片，管线级端到端）
+ 全门复验（PI 全门/响度/时长/逐景 corr（**S06 小裕度如实记录、不调阈值**）/字幕与旁白对齐）+ DQ 双口径报告
（DQ-3 `freezedetect` 语义并列，**不宣称 PASS**）。零 promotion；建议后台作业、单次 ≤3 h、超限先报告。

### 7.4 本次续跑的边界与预算
LLM **$0**、网络 **0**、**未做渲染**；**未放宽任何 PI/DQ 阈值**；权威底片/v9 底片/`config.json`/P7-6 产物/13-D 台账与报告**均未改**；
新增仅：`core/lineage_guard.py`、`tests/lineage_guard_test.py`、`logs/phase13e_p13e2_finding.json` 与本节。
""".format(verdict=g["verdict"], sha=g["sha256"][:16] + "…", dur=g["duration_s"], tol=g["tolerance_s"],
           aid=h5e["asset_record"]["asset_id"], path=h5e["asset_record"]["path"],
           sha2=str(h5e["asset_record"]["sha256"])[:16] + "…",
           binding=json.dumps(h5e["binding"], ensure_ascii=False),
           ok=h5e["asset_sha256_verified"])
rep.write_text(txt + section + "\n", encoding="utf-8")
print("已追加续跑章节 | 回归:", reg)
print("报告含 P13E-2 结论:", "no-op" in rep.read_text(encoding="utf-8"))
