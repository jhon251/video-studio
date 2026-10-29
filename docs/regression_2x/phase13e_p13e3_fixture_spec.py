# -*- coding: utf-8 -*-
"""P13E-3 ② 夹具规格固化（精确到字段/依赖图）+ 最终状态更新（诚实登记：未启动渲染作业）。"""
import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")
fs = L / "phase13e_p13e3_final_state.json"
st = json.loads(fs.read_text(encoding="utf-8"))
prov = json.loads((L / "phase13e_script_derivation_provenance.json").read_text(encoding="utf-8"))
fixture = {
    "goal": "以 Engine/editing 生产路径（`_render`）渲染 DCv2 谱系全片运动候选（21 景 / 978.7 s / 运动 enabled）",
    "observed_requirements": {
        "source": "src/video_studio/agents/editing/agent.py::_render（L321–L417 实测读取点）",
        "dependency_tasks": [
            {"role": "script", "artifact_type": "script_output",
             "field_used": "script（segments[].{narration,duration_s,…}）",
             "supply": "本次合成的 DCv2 派生脚本（沙箱）",
             "line": "L321–L324（按依赖任务倒序取最后一个 script_output）"},
            {"role": "voice", "artifact_type": "voice_output",
             "field_used": "payload.audio（音频路径）+ 可选 audio_time_base_s（v2 权威开关）",
             "supply": "沿用既有项目 voice 产物（**旁白音频=事实来源**；若带 audio_time_base_s 则启用 Duration Contract v2）",
             "line": "L349–L369"},
            {"role": "retrieval", "artifact_type": "retrieval_candidates",
             "field_used": "material_mode + candidates/external_*（供 asset_pool 与时间轴装配）",
             "supply": "沿用既有项目检索产物（素材池）+ S05 绑定 Russell 页（H5 binding 继承）",
             "line": "L384–L392"},
        ],
        "filesystem": {"media_dir": "<project>/media（素材池文件须真实存在）", "line": "L399–L417"},
        "motion": {"switch": "config/render_motion.json（enabled=true，已就位）",
                   "insertion_point": "concat 之前（Phase 13 P13-2）",
                   "evidence_out": "<project>/render/motion_evidence.json"},
    },
    "execution_plan": [
        "1) 守卫 assert_lineage(H5 底片) ⇒ LINEAGE_OK（已通过）",
        "2) 建沙箱工作区：复制/链接既有项目 media/ 与 voice 产物；写入 DCv2 派生脚本为新 script_output",
        "3) 建依赖任务与 editing 任务（engine.create_task(pid,'script'/'voice'/'retrieval'/'editing', dependencies=[…])）",
        "4) engine.run_cycle(pid) ⇒ 触发 `_render`（运动 enabled）",
        "5) 全门复验：PI 全门 / 响度契约 / 时长 978.7±1 s / 逐景抽帧 corr（S06 小裕度如实记录、不调阈值）/ 字幕与旁白对齐",
        "6) DQ 双口径报告（原口径复算 + DQ-3 freezedetect 语义并列；**不宣称 PASS**）",
        "7) 逐景 MOTION_VERIFIED（render/motion_evidence.json + 10%/90% 抽帧像素差）",
        "8) 零 promotion；后台作业；单次 ≤3 h，超限先报告实际增速",
    ],
    "estimated_render_scale": {"scenes": 21, "duration_s": 978.656, "fps": 25,
                               "note": "≈24,466 帧 1080p；实测同类窗口重编码 55 s 用时 80.5 s（Phase 13-D）⇒ 全片渲染预计需数十分钟至数小时，须后台作业"},
}
st["fixture_spec"] = fixture
st["pending"]["full_film_motion_render"]["status"] = "PENDING_NOT_STARTED_HONEST"
st["pending"]["full_film_motion_render"]["blocker"] = (
    "**未启动（诚实登记）**：夹具装配点已精确定位（见 fixture_spec），但构建夹具 + 运行 "
    "`editing._render` 全片（≈24,466 帧 1080p）需要连续的后台执行窗口与逐阶段验证；本会话剩余执行预算不足以"
    "在**不牺牲验证**的前提下完成（宁可 PENDING，也不启动无法验证的作业/不伪造渲染完成）。"
    "所需输入已全部就位（派生脚本 / 运动开关 / 素材绑定 / 权威底片 / 既有 media 与 voice 产物）。")
st["honest_statement"] = ("授权 ② 的渲染作业**未启动**。原因是执行预算，而非输入缺失或规则阻塞；"
                         "所有输入与装配规格均已固化，下一阶段可直接执行 `fixture_spec.execution_plan`。")
fs.write_text(json.dumps(st, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
print("夹具规格已固化（依赖任务/字段/行号/计划）")
print("② 状态:", st["pending"]["full_film_motion_render"]["status"])
print("输入就绪:", json.dumps(st["pending"]["full_film_motion_render"]["ready_inputs"], ensure_ascii=False)[:200])
