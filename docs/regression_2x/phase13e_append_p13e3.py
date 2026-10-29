# -*- coding: utf-8 -*-
"""Phase 13-E 收官：把 §8（P13E-3 就绪度 + 前置缺口 + 配方）追加进 PHASE13E_REPORT.md。"""
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
rep = R / "docs" / "regression_2x" / "PHASE13E_REPORT.md"
sys.stdout.reconfigure(encoding="utf-8")
txt = rep.read_text(encoding="utf-8")
if "## 8. Phase 13-E 收官" in txt:
    print("§8 已存在，跳过")
    sys.exit(0)
f = json.loads((L / "phase13e_p13e3_readiness.json").read_text(encoding="utf-8"))
g = f["readiness"]["lineage_guard"]
section = """
---

## 8. Phase 13-E 收官（P13E-3 授权执行）：**就绪度 DONE；渲染 PENDING（前置缺口已定位）**

### 8.1 已完成就绪项（全部实测）
| 项 | 结果 |
|---|---|
| 底片守卫 | `{verdict}`（`assert_lineage(H5_rp-0ebebb71f99c.mp4)`，978.7 s，sha256 `3b61dafda11c1b9d…`） |
| 运动开关（授权允许的外部渲染开关文件） | 新建 `config/render_motion.json`（`enabled=true`）；`resolve_config` ⇒ `{{"enabled": true}}`，来源 `render_motion.json`；**`config.json` 未改动** |
| 运动策略出处 | `core/motion.py` `POLICY[…]`（zoom ≤1.08、平移 ≤画面 3%、<10s 静止、启用 ≤60%、窗口 ≤150 帧）——**未放宽任何阈值** |
| DCv2 权威窗口 | `remapping_21_segments`（21 条）合计 **978.7 s**，与权威底片**完全一致**（S05=[181.776, 221.862]） |
| S05/Russell 绑定 | 已在权威底片（H5 `binding` + `asset_records` + `replaced_all` 门禁），无需替换 |

### 8.2 **前置缺口（本阶段新发现）**：DCv2 谱系**没有脚本产物**
- 项目内唯一 `script_output` = `a_49b58fb3dc01`（21 段、**总时长 1530.0 s = v9 谱系**）；
  **不存在**总时长 ≈978.7 s 的 DCv2 脚本 ⇒ `readiness.dcv2_script_artifact_exists = False`。
- 后果：**管线级端到端渲染需要脚本**；若用现有 v9 脚本渲染，产出的是 **v9 1530 s 片**——按 Phase 13-E 谱系纪律
  **禁止**在 v9 底片上渲染（会重现 #65/#67 度量伪影）⇒ **本阶段不做该渲染**。
- 登记为 KNOWN_ISSUES 候选 **#72**：*权威（DCv2/H5）谱系产物不完整——重建只产出时基计划与成片，未产出对应 `script_output`*；
  **本阶段未擅自新建脚本产物**（无授权不写生产产物）。

### 8.3 P13E-3 执行配方（已固化，下一阶段可一次性执行）
产物：`logs/phase13e_p13e3_readiness.json`（含逐景 21 条 new 窗口 + TTS 时长 + pause 预算）。
1. 守卫通过后，按 `remapping_21_segments` **合成 DCv2 脚本**（段时长 = `new_timeline_window_s`，合计 978.7 s；
   旁白**文本**沿用既有脚本；旁白**音频为事实来源**，按 `new_audio_window_s` + `pause_budget_s` 放置）；
2. 素材绑定沿用 H5 `binding`（S05=Russell 页，sha256 已核验）；
3. 走 Engine/editing `_render` 渲染（**运动开关已 `enabled=true`**）；
4. 复验：PI 全门 / 响度契约 / 时长契约（978.7±1 s）/ **逐景抽帧 corr（S06 小裕度如实记录、不调阈值）** / 字幕与旁白对齐；
5. **DQ 双口径**：原口径复算 + DQ-3 `freezedetect` 语义并列说明（**不宣称 PASS**）；
6. 逐景 **MOTION_VERIFIED** 证据（`<project>/render/motion_evidence.json` + 场景 10%/90% 抽帧像素差）；
7. 零 promotion；后台作业；单次 ≤3 h，超限先报告实际增速。

### 8.4 本次收官阶段的边界与预算
LLM **$0**、网络 **0**、**未执行全片渲染**；**未放宽任何 PI/DQ 阈值**；权威底片/v9 底片/现有脚本产物/`config.json`/
P7-6 产物/13-D 台账与报告**均未改**；新增仅 `config/render_motion.json`（授权允许的渲染开关文件）、
`logs/phase13e_p13e3_readiness.json` 与本节。
""".format(verdict=g["verdict"])
rep.write_text(txt + section + "\n", encoding="utf-8")
print("已追加 §8 | 报告含 P13E-3 配方:", "## 8. Phase 13-E 收官" in rep.read_text(encoding="utf-8"))
