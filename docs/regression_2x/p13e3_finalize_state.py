# -*- coding: utf-8 -*-
"""P13E-3 ② 最终状态更新（诚实登记实测结果；零覆盖既有记录）。"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(R / "src"))

fs = L / "phase13e_p13e3_final_state.json"
st = json.loads(fs.read_text(encoding="utf-8"))
rep = json.loads((L / "phase13e_p13e3_render.json").read_text(encoding="utf-8"))
fix = json.loads((R / "output" / "phase13e_p13e3_sandbox" / "fixture.json")
                 .read_text(encoding="utf-8"))


def sha(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


film = R / rep["film"]["path"]
mv = rep["motion_verification"]

st["executed"] = {
    "schema": "phase13e-p13e3-executed-v1",
    "status": "EXECUTED_GATE_BLOCKED",
    "verdict": ("渲染作业**已执行**并产出全片候选；**渲染后核验硬门阻断**（S03 抽帧 corr 0.153 < 0.30）"
                "⇒ 未登记 render_output/attribution ⇒ **非交付物**，候选交人工观看。"
                "**未宣称 PASS**、未放宽任何阈值。"),
    "basis_decision": {
        "literal_recipe_v1_outcome": "BLOCKED（PI-6 最大漂移 15.0s > 5.0s）且成片 980.656s 超契约 1.956s",
        "adopted": "情形② v2 时基（沙箱派生 voice 补 audio_time_base_s），经用户授权",
        "authoritative_voice_artifact_untouched": True,
        "voice_derivation": {
            "derived_from": "a_e99273b936c0",
            "derived_from_sha256": sha(R / "projects" / "p_96efdc03e1aa" / "artifacts"
                                       / "a_e99273b936c0.json"),
            "audio_time_base_s": 978.656,
            "formula": "Σ actual_tts_duration_s(961.656) + pause 0.75×20(15.0) + trailing 2.0",
        },
    },
    "sandbox": {
        "project_id": fix["sandbox_project_id"],
        "render_task_id": fix["tasks"]["editing"],
        "task_status": "BLOCKED",
        "candidate": rep["film"]["path"],
        "candidate_bytes": rep["film"]["bytes"],
        "candidate_sha256": sha(film) if film.is_file() else "MISSING",
        "render_wall_clock_s": 207.4,
        "render_output_artifact": None,
        "attribution_artifact": None,
        "note": "fail-closed：阻断即不写交付物；mp4 保留为证据（不作交付物登记）",
    },
    "motion": {
        "enabled": True,
        "plan_counts": mv["plan_counts"],
        "applied_scenes": mv["enabled_scenes"],
        "fallback": mv["fallback"],
        "evidence_file": "{}/render/motion_evidence.json".format(fix["sandbox_project_id"]),
    },
    "gates": {
        "duration_contract": rep["duration_contract"],
        "loudness": {"contract": rep["loudness"]["contract"],
                     "independent_measure": {
                         k: rep["loudness"]["independent_measure"].get(k)
                         for k in ("lufs", "true_peak_dbtp", "ok", "method")}},
        "pi_pre_render": {"blocked": rep["pi_gates"]["pre_render"]["blocked"],
                          "states": rep["pi_gates"]["pre_render"]["states"]},
        "pi_post_render": {"blocked": rep["pi_gates"]["post_render"]["blocked"],
                           "promote_blocked": rep["pi_gates"]["post_render"]["promote_blocked"],
                           "states": rep["pi_gates"]["post_render"]["states"]},
        "subtitle_alignment": {"code": rep["subtitle_alignment"]["v2_alignment"]["code"],
                               "cues": rep["subtitle_alignment"]["cue_count"],
                               "cue_display_in_speech_ratio":
                                   rep["subtitle_alignment"]["v2_alignment"]
                                   ["cue_display_in_speech_ratio"],
                               "orphan_cues": rep["subtitle_alignment"]["orphans"]["orphan_cues"],
                               "orphan_share": rep["subtitle_alignment"]["orphans"]["orphan_share"]},
        "per_scene_corr": {
            "metric": "frame_pearson_48x48（冻结口径）",
            "threshold": 0.30,
            "passed": mv["summary"]["corr_ge_0_30_count"],
            "total": len(mv["scenes"]),
            "failed": mv["summary"]["corr_failed_scenes"],
            "failed_detail": {"S03": 0.1536},
            "narrow_margin": mv["summary"]["corr_narrow_margin_scenes"],
            "thresholds_relaxed": False,
        },
        "motion_verified": {"enabled_scenes": mv["summary"]["motion_enabled_count"],
                            "verified": mv["summary"]["motion_verified_count"],
                            "method": "10%/90% 抽帧像素差（480×270 灰度平均绝对差）",
                            "limitation": ("该差值与字幕变化/H.264 量化噪声不可区分 ⇒ "
                                           "静止场景差 0.85–1.86 与运动场景 1.02–1.69 重叠；"
                                           "运动确定性另由 motion_evidence.json 与 S03 corr "
                                           "提升（0.153→0.172）佐证；**该局限如实登记**")},
    },
    "blocking_finding": {
        "gate": "agents/editing/agent.py L823–835 成片抽帧核验（在 PI 渲染后硬门之前）",
        "scene": "S03",
        "code": "[ASSET_INSUFFICIENT]",
        "corr_expected": 0.153,
        "corr_best": 0.153,
        "min_corr": 0.3,
        "sample_t_s": 101.49,
        "independent_recheck": {
            "corr_frame_vs_raw_asset": 0.1529,
            "corr_frame_vs_static_fullframe_template": 0.1529,
            "corr_frame_vs_motion_zoom_template": 0.172,
            "visual_inspection": "成片帧与静态模板为**同一张四色定理示意图**（同一构图/节点布局）",
            "conclusion": ("**素材确实在屏**（非错配/非占位伪装）。低分属冻结度量自身的结构性盲区："
                           "稀疏高对比线稿（白底+细黑线+稀疏彩点）重采样到 48×48 后，轻微缩放/位移"
                           "即令线条落到不同像素格，相关系数塌陷。S03 为全片唯一此类线稿；"
                           "其余 20 景（实拍/密纹图片）corr 0.54–0.99。"
                           "**运动层不是致因**：运动模板相关度反而更高（0.172 > 0.153）。"),
        },
        "actions_not_taken": ["放宽 PI/DQ 或 corr 阈值", "修改 frame_corr 度量口径",
                              "调整运动参数/选材以规避核验", "修改任何被测生产代码"],
    },
    "dq_dual_caliber": {
        "original_caliber_readonly": {
            "DQ-2_asset_reuse": rep["dq_readonly"].get("DQ-2_asset_reuse", {}).get("state"),
            "DQ-3_static_hold": rep["dq_readonly"].get("DQ-3_static_hold", {}).get("state"),
            "DQ-3_fail_findings": [
                {k: f.get(k) for k in ("scene_id", "hold_s", "asset_id")}
                for f in (rep["dq_readonly"].get("DQ-3_static_hold", {}).get("findings") or [])
                if f.get("kind") == "hold_exceeds_max"],
        },
        "dq3_freezedetect_semantics": {
            "blocks": rep["dq3_freezedetect"]["blocks"],
            "params": rep["dq3_freezedetect"]["params"],
            "note": ("与 DQ-3 同源：9 个静止场景按设计无像素变化，如实计为冻结块。"
                     "两口径**不可互相替代**，本报告**不把任何一项读作 PASS**。"),
        },
        "root_cause_of_dq_fails": ("素材池贫瘠（本夹具素材池取自项目内检索产物，仅 5 张真实图像；"
                                   "**不含** H5 权威绑定的 Russell 页，该文件不在 media/）"
                                   "+ 场景本身很长（21 景/978.7s，单景 30–67s）；**不是**运动层缺陷。"),
        "pass_claimed": False,
    },
    "artifacts": {
        "verification_report": "docs/regression_2x/logs/phase13e_p13e3_render.json",
        "fixture": "output/phase13e_p13e3_sandbox/fixture.json",
        "build_log": "output/phase13e_p13e3_sandbox/fixture_build.log",
        "suites_summary": "docs/regression_2x/logs/suites_summary.json",
    },
    "registration": {"llm_usd": 0, "network_calls": 0, "promotion": False,
                     "thresholds_relaxed": False, "production_code_modified": False},
    "regression": {
        "suites_total": 77, "rc0": 77, "failed": [],
        "note": ("初跑 76/77：唯一失败 motion_test::5b（断言『无外部文件时运动层 off』）"
                 "系本阶段**已授权**的 config/render_motion.json(enabled=true) 与该测试前提冲突，"
                 "非代码缺陷。处置：把开关文件按字节暂存沙箱后复跑 ⇒ 77/77 rc=0（motion_test 22/22），"
                 "再逐字节还原（sha256 27f4a438b02dc773… 前后一致），解析仍为 enabled=true。"
                 "**未改任何测试、未改任何阈值**。"),
        "summary_file": "docs/regression_2x/logs/suites_summary.json",
    },
    "immutability": {"verdict": "IMMUTABLE_OK",
                     "checker": "docs/regression_2x/phase13_immutable_check.py",
                     "authoritative_film_sha256_prefix": "3b61dafda11c1b9d",
                     "config_json_untouched": True,
                     "authoritative_voice_artifact_untouched": True},
}

st["pending"]["full_film_motion_render"] = {
    "status": "EXECUTED_GATE_BLOCKED",
    "detail": st["executed"]["verdict"],
    "next_actions": [
        "人工观看候选：projects/{}/output/{}".format(fix["sandbox_project_id"],
                                              pathlib.Path(rep["film"]["path"]).name),
        "裁定 S03：若认定『素材确在屏』，则需**显式授权**处置路径（如对稀疏线稿另立口径 / "
        "补足素材池后重选材），本次**未擅自**改动任何阈值或度量",
        "素材池贫瘠（5 张真实图像）驱动的 DQ-2/DQ-3 FAIL 属夹具输入限制，非运动层缺陷；"
        "若需达成交付级 DQ，应先补足权威 H5 绑定素材到 media/ 后重跑",
    ],
}
st["honest_statement"] = (
    "P13E-3 ② **已执行**：全片运动候选已渲染（978.66s / 12 景运动 / 0 fallback），"
    "时长与响度契约达标、PI 全门与字幕对齐全 PASS、逐景 corr 20/21；"
    "**但渲染后核验硬门因 S03（corr 0.153 < 0.30）阻断**，故未登记交付物、**不宣称 PASS**。"
    "独立复核证明 S03 素材确在屏、非运动层所致，属冻结度量对稀疏线稿的结构性盲区；"
    "**未放宽任何阈值、未改度量、未改生产代码**。")

fs.write_text(json.dumps(st, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
print("最终状态已更新")
print("status:", st["executed"]["status"])
print("candidate:", rep["film"]["path"], rep["film"]["bytes"], "B")
print("candidate sha256:", st["executed"]["sandbox"]["candidate_sha256"][:16], "…")
print("gates: duration", rep["duration_contract"]["measured_s"], "| PI pre/post",
      rep["pi_gates"]["pre_render"]["blocked"], rep["pi_gates"]["post_render"]["blocked"])
print("corr:", st["executed"]["gates"]["per_scene_corr"]["passed"], "/",
      st["executed"]["gates"]["per_scene_corr"]["total"],
      "| failed:", st["executed"]["gates"]["per_scene_corr"]["failed"])
print("artifacts ->", fs.name)
