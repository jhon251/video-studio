# -*- coding: utf-8 -*-
"""P13E-3 最终状态固化 + 报告 §9 追加。"""
import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")
prov = json.loads((L / "phase13e_script_derivation_provenance.json").read_text(encoding="utf-8"))
suites = json.loads((L / "suites_summary.json").read_text(encoding="utf-8"))
reg = "**{} 套件 / {} rc=0 / FAILED: {}**".format(
    len(suites), sum(1 for x in suites if x["rc"] == 0),
    [x["suite"] for x in suites if x["rc"] != 0] or "[]")
state = {
    "schema": "phase13e-p13e3-final-state-v1",
    "stage": "Phase 13-E 最终执行（授权：DCv2 脚本合成 + 全片运动候选渲染）",
    "done": {
        "1_dcv2_script_artifact": {"status": "DONE",
                                   "path": prov["derived_script"],
                                   "sha256": prov["derived_script_sha256"],
                                   "segments": prov["segments"],
                                   "total_duration_s": prov["total_duration_s"],
                                   "text_verbatim_ok": prov["text_verbatim_ok"],
                                   "derived_from": prov["source_script"],
                                   "synthesis_rule_version": prov["synthesis_rule_version"],
                                   "zero_overwrite": True,
                                   "content_chain_not_rerun": True},
        "2_motion_switch": {"status": "DONE", "file": "config/render_motion.json",
                            "resolved": {"enabled": True}, "config_json_untouched": True},
        "3_lineage_guard": {"status": "DONE", "verdict": "LINEAGE_OK"},
        "4_derivation_check": {"status": "DONE",
                               "timing_matched": prov["timing_matched"],
                               "timing_mismatch": prov["timing_mismatch"],
                               "note": "S21 65.0→67.0 s 系已知 E1 片尾卡插入的时长差；**无需改写文本**，故未触发 STOP"},
    },
    "pending": {
        "full_film_motion_render": {
            "status": "PENDING_NOT_STARTED",
            "blocker": "管线级渲染需要 Engine 夹具（项目 + script_output(=派生脚本) + retrieval 载荷/素材池 + 旁白音频），"
                       "并在其上跑 editing._render（运动 enabled）；预计单次全片渲染耗时较长（≤3h 上限）。"
                       "本阶段（预算内）未启动该渲染。",
            "ready_inputs": {"script": prov["derived_script"],
                             "motion_switch": "config/render_motion.json",
                             "asset_binding": prov["asset_binding_inherited"],
                             "base_film_for_reference": "output/phase6g_exec_h5/20260929_151026/out/H5_rp-0ebebb71f99c.mp4"},
            "recipe_ref": "docs/regression_2x/PHASE13E_REPORT.md §8.3",
        }
    },
    "registration": {"regression": reg, "llm_usd": 0, "network_calls": 0,
                     "render_executed": False, "promotion": False,
                     "thresholds_relaxed": False},
    "immutability": {"authoritative_film_untouched": True, "v9_film_untouched": True,
                     "config_json_untouched": True, "p7_6_products_untouched": True,
                     "phase13d_records_untouched": True, "sandbox_zero_overwrite": True},
}
p = L / "phase13e_p13e3_final_state.json"
p.write_text(json.dumps(state, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")

rep = R / "docs" / "regression_2x" / "PHASE13E_REPORT.md"
txt = rep.read_text(encoding="utf-8")
if "## 9. Phase 13-E 最终执行" not in txt:
    txt += """
---

## 9. Phase 13-E 最终执行（授权：① DCv2 脚本合成 + ② 全片运动候选渲染）

### 9.1 ① DCv2 脚本产物合成：**DONE**（纯派生，文本逐字未改）
- **沙箱新文件（零覆盖）**：`output/phase13e_script_sandbox/script_dcv2_derived_v1.json`
  ｜sha256 `{sha}`｜21 段｜**总时长 978.656 s**（= 权威底片 978.7 s）
- **文本逐字校验：True** —— `text_hash_original == text_hash_derived`（4947 字符，**未改一字**，含标点/空白）
- **派生依据**：`derived_from = a_49b58fb3dc01`（sha256 `{src}`）；段时长 = `remapping_21_segments.new_timeline_window_s`；
  音频为事实来源（`new_audio_window_s` + `pause_budget_s`）；`synthesis_rule_version = {rule}`
- **内容链未重跑**：本产物**继承**原脚本既有 claim/事实核查/结构审结论（报告与 provenance 均写明"内容结论继承自 a_49b58fb3dc01 谱系"）
- **映射证据（关键）**：v9 脚本 21 段**无 `scene_id` 字段** ⇒ 采用**段序↔景序**映射，并以**时长证据**证实：
  **20/21 逐段吻合**（段时长 == `old_timeline_window_s` == v9 渲染时间轴窗口）；
  唯一偏差为 **S21：脚本 65.0 s vs 旧窗口 67.0 s（Δ=2.0 s）**——系已知 **E1 片尾卡插入**的时长差，
  **属时长差异而非文本对齐问题** ⇒ **无需改写任何文本**，故**未触发**授权 (a) 的 STOP 条件。
- provenance：`logs/phase13e_script_derivation_provenance.json`（含源/规则/时间证据/绑定继承/零覆盖标记）

### 9.2 ② 全片运动候选渲染：**PENDING（未启动）**
- 已就绪输入：派生脚本（上）、运动开关 `config/render_motion.json`（`enabled=true`）、
  H5 素材绑定（S05=Russell 页，sha256 已核验）、权威底片（权威谱系真相源，已过守卫）。
- **未启动原因（如实）**：管线级渲染需先构建 **Engine 夹具**
  （项目 + `script_output`(=派生脚本) + `retrieval` 载荷/素材池 + 旁白音频），再跑 `editing._render`（运动 enabled），
  随后执行全门复验（PI 全门 / 响度契约 / 时长 978.7±1 s / 逐景 corr（S06 小裕度如实记录、不调阈值）/ 字幕与旁白对齐）、
  DQ 双口径（**不宣称 PASS**）与逐景 **MOTION_VERIFIED**；单次渲染 ≤3 h。**本阶段预算内未启动**。
- 配方见 §8.3；就绪输入见 `logs/phase13e_p13e3_final_state.json`。

### 9.3 本次执行的口径与边界
回归 {reg}（本阶段未改被测代码）｜LLM **$0**、网络 **0**、**未执行渲染**、**零 promotion**、**未放宽任何 PI/DQ 阈值**；
权威底片/v9 底片/既有脚本产物/`config.json`/P7-6 产物/13-D 台账与报告**均未改**；新增仅派生脚本（沙箱）、
provenance、最终状态与本节。
""".format(sha=prov["derived_script_sha256"][:16] + "…", src=prov["source_script"]["sha256"][:16] + "…",
           rule=prov["synthesis_rule_version"], reg=reg)
    rep.write_text(txt, encoding="utf-8")
print("最终状态:", p.name, "| 派生脚本 sha:", prov["derived_script_sha256"][:16])
print("回归:", reg, "| 报告 §9 在位:", "## 9. Phase 13-E 最终执行" in rep.read_text(encoding="utf-8"))
