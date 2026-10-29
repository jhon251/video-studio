# -*- coding: utf-8 -*-
"""Phase 13-E 收官 / P13E-3 **就绪度与配方**固化（本阶段未渲染；为下一阶段一次性执行备好全部依据）。"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sqlite3
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import lineage_guard as LG                                     # noqa: E402
from video_studio.core import motion as M                                             # noqa: E402

guard = LG.check_lineage(LG.authoritative_film(R), root=R)
plan = json.loads((L / "phase6f_rebuild_plan_v2.json").read_text(encoding="utf-8"))
rm = plan["remapping_21_segments"]
cfg = json.loads((R / "config" / "config.json").read_text(encoding="utf-8"))
motion_cfg, motion_src = M.resolve_config(cfg, root=R)
con = sqlite3.connect("file:" + (R / "projects" / "video_studio.db").as_posix() + "?mode=ro",
                      uri=True)
con.row_factory = sqlite3.Row
scripts = [dict(r) for r in con.execute(
    "select artifact_id,path from artifacts where type='script_output' and "
    "project_id='p_96efdc03e1aa' order by created_at")]
con.close()
script_info = []
for s in scripts:
    j = json.loads(pathlib.Path(s["path"]).read_text(encoding="utf-8"))
    segs = j.get("segments") or []
    script_info.append({"artifact_id": s["artifact_id"], "segments": len(segs),
                        "total_duration_s": round(sum(float(x.get("duration_s") or 0)
                                                      for x in segs), 1)})
new_windows = [{"scene_id": e["scene_id"], "new_timeline_window_s": e["new_timeline_window_s"],
                "actual_tts_duration_s": e.get("actual_tts_duration_s"),
                "pause_budget_s": e.get("pause_budget_s")} for e in rm]
total_new = round(sum(float(e["new_timeline_window_s"][1]) - float(e["new_timeline_window_s"][0])
                      for e in rm), 1)
out = {
    "schema": "phase13e-p13e3-readiness-v1",
    "status": "PENDING_NOT_RENDERED",
    "why_not_rendered": "管线级端到端渲染需要 **DCv2 谱系脚本产物**；项目内唯一 `script_output` 是 v9 谱系（1530.0 s），"
                        "而按 Phase 13-E 谱系纪律**禁止**在 v9 底片上渲染（会重现 #65/#67 度量伪影）。"
                        "故 P13E-3 必须先做『DCv2 脚本合成』这一前置步骤（配方见下），本阶段未执行完整渲染。",
    "readiness": {
        "lineage_guard": guard,
        "authoritative_film": LG.AUTHORITATIVE_LINEAGE["film"],
        "motion_switch": {"file": str((R / "config" / "render_motion.json").relative_to(R)),
                          "resolved": {k: v for k, v in motion_cfg.items() if k != "note"},
                          "source": motion_src,
                          "note": "渲染开关文件（授权明确允许）；config.json 未改动"},
        "dcv2_timeline": {"source": "logs/phase6f_rebuild_plan_v2.json#new_production_timeline",
                          "scenes": len(plan["new_production_timeline"]),
                          "total_s": total_new},
        "script_artifacts_present": script_info,
        "dcv2_script_artifact_exists": any(abs(s["total_duration_s"] - 978.7) <= 2.0
                                           for s in script_info),
    },
    "synthesis_recipe": {
        "goal": "合成 DCv2 谱系脚本（21 段；段时长 = DCv2 重建窗口；旁白文本沿用既有 v9 脚本；"
                "旁白音频为事实来源），用于管线级渲染",
        "inputs": [
            "logs/phase6f_rebuild_plan_v2.json#remapping_21_segments（逐景 old→new 窗口 + actual_tts_duration_s + pause_budget_s）",
            "artifacts(type='script_output', project=p_96efdc03e1aa) —— 现有 21 段旁白文本（v9 谱系，仅取**文本**）",
            "logs/phase6g_exec_h5.json#binding —— S05=asset_h5_S05_65377b888b778226、S11=asset_h5_S11_1e9d2ab4e64ef982（素材绑定）",
        ],
        "steps": [
            "1) 守卫：assert_lineage(H5 978.7s 底片) 必须通过（已通过：{}）".format(guard["verdict"]),
            "2) 逐景取 new_timeline_window_s 作为段时长（合计 {:.1f}s，目标 978.7s）".format(total_new),
            "3) 旁白文本按 scene_id 对齐旧脚本段；TTS/音频按 new_audio_window_s 放置（pause_budget 保留）",
            "4) 素材绑定沿用 H5 binding（S05=Russell 页已核验 sha256 一致）",
            "5) 走 Engine/editing 生产路径（`_render`）渲染；**运动开关已 enabled=true**（config/render_motion.json）",
            "6) 渲染后复验：PI 全门 / 响度契约 / 时长契约(978.7±1s) / 逐景抽帧 corr（S06=0.3245 小裕度如实记录、不调阈值）/ 字幕与旁白对齐",
            "7) DQ 双口径：原口径复算 + DQ-3 freezedetect 语义并列说明（**不宣称 PASS**）",
            "8) 逐景 MOTION_VERIFIED 证据（来自 `<project>/render/motion_evidence.json` + 场景 10%/90% 抽帧像素差）",
        ],
        "expected_outputs": ["全片合成候选（978.7s 谱系，新文件名，零 promotion）",
                             "logs/phase13e_p13e3_render.json（含 PI/DQ/corr/对齐/motion 证据）"],
        "render_budget": "单次 ≤3h；后台作业；超限先报告实际增速",
    },
    "policy_provenance": {"planned_by_stage33_derived": True,
                          "max_zoom_end": M.MAX_ZOOM_END, "pan_max_ratio": M.PAN_MAX_RATIO,
                          "min_scene_s": M.MIN_SCENE_S, "max_enabled_ratio": M.MAX_ENABLED_RATIO,
                          "motion_window_max_frames": M.MOTION_WINDOW_MAX_FRAMES,
                          "note": "策略常量出处见 core/motion.py POLICY[…][『basis』]；**未放宽任何阈值**"},
    "new_windows": new_windows,
    "lineage_completeness_gap": "**新发现**：DCv2/H5 权威谱系**没有 script_output 产物**（只有时基计划 + 成片），"
                                "而管线级重渲染需要脚本 ⇒ 记录为 KNOWN_ISSUES 候选 **#72**（谱系产物不完整："
                                "DCv2 重建未产出对应脚本 artifact）。本阶段**未**擅自新建脚本产物。",
    "zero_render_this_stage": True, "zero_llm": True, "zero_network": True, "no_promotion": True,
}
p = L / "phase13e_p13e3_readiness.json"
p.write_text(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
print("守卫:", guard["verdict"], "| 运动开关:", json.dumps({k: v for k, v in motion_cfg.items() if k != 'note'}, ensure_ascii=False), "| 来源:", motion_src.split('\\')[-1])
print("现有脚本产物:", [(s["artifact_id"], s["total_duration_s"]) for s in script_info],
      "| DCv2 脚本存在:", out["readiness"]["dcv2_script_artifact_exists"])
print("DCv2 窗口合计: %.1fs（目标 978.7）| 段数: %d" % (total_new, len(rm)))
print("状态:", out["status"], "| 产物:", p.name)
