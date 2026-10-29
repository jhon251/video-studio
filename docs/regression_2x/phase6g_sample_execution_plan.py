# -*- coding: utf-8 -*-
"""6-G —— 小样（S11 + LAST_12S）**确定性执行计划 + 验收计划**（PROPOSED_ONLY，**不执行**）。

范围（人工指令第 6 条）：`[487.572, 539.346]`（S11，51.774s）+ `[966.656, 978.656]`（末 12s）
共 63.774s / **3 executions**（split → overlay 链式 2 次；E1 片尾卡 1 次）。

本脚本只做**确定性推演**（调用生产函数 `split_plan` / `caption_time_base` / `build_cues` /
`verify_spec` 计算将要执行的参数与预期输出），**不调用 ffmpeg、不写 DB、不执行任何 proposal**。

产出: docs/regression_2x/logs/phase6g_sample_execution_plan.json
"""
import hashlib
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
from video_studio.core import captions as core_captions              # noqa: E402
from video_studio.core import visual_aid as VA                       # noqa: E402
from video_studio.ops import execution as OPX                        # noqa: E402

LOGS = ROOT / "docs" / "regression_2x" / "logs"
P2 = json.loads((LOGS / "phase6f_rebuild_plan_v2.json").read_text(encoding="utf-8"))
PKG = json.loads((LOGS / "phase6g_rebuild_proposals.json").read_text(encoding="utf-8"))
N0 = json.loads((LOGS / "phase6g_n0_dcv2_master.json").read_text(encoding="utf-8"))
AUD = json.loads((LOGS / "phase6g_pre_sample_gate_audit.json").read_text(encoding="utf-8"))
OUT = LOGS / "phase6g_sample_execution_plan.json"
SRC = (ROOT / "src" / "video_studio" / "ops" / "execution.py").read_text(encoding="utf-8")
PROD = P2["math_verification"]["production_duration_s"]
chain = P2["remapping_21_segments"]
by_scene = {c["scene_id"]: c for c in chain}
W_A = [487.572, 539.346]
W_B = [966.656, 978.656]
master = ROOT / N0["master"]["path"]

tl = [{"scene_id": c["scene_id"], "start_s": c["new_timeline_window_s"][0],
       "end_s": c["new_timeline_window_s"][1]} for c in chain]
cw = [{"scene_id": c["scene_id"], "start_s": c["new_audio_window_s"][0],
       "end_s": c["new_audio_window_s"][1]} for c in chain]
ctx = OPX.attach_dcv2_time_base(
    {"film": str(master), "box": str(master.parent / "sample_box"),
     "root": str(ROOT), "ffmpeg": str(ROOT / "bin" / "ffmpeg.exe"),
     "artifacts": {}}, timeline=tl, caption_windows=cw, production_duration_s=PROD,
    source="docs/regression_2x/logs/phase6f_rebuild_plan_v2.json")
ident = ctx["timeline_identity"]
cap_base = OPX.caption_time_base(ctx)

# ---------------------------------------------------------------- 1) split S11（机制验证；非正式 H3b 执行）
h3b = next(p for p in PKG["proposals"] if p["label"].startswith("H3b"))
sample_split_prop = {"proposal_id": "SAMPLE-h3b-s11-subset", "action": "split_scene",
                     "affected_scope": {"scenes": ["S11"]},
                     "proposed_change": {"params": {"target_hold_s": 25.0}}}
split_plan = OPX.split_plan(ctx, sample_split_prop)
s11_asset = by_scene["S11"]["asset_name"]

# ---------------------------------------------------------------- 2) overlay spec（**小样专用**，非 E2/E3 设计）
sample_spec = {"schema": VA.SCHEMA, "layout": "panel_columns", "no_external_assets": True,
               "forbid_verbatim_quotes": True,
               "panels": [{"id": "P1", "title": "小样叠加层（机制验证）",
                           "kind": "ladder",
                           "items": ["机制验证 A", "机制验证 B", "机制验证 C"],
                           "source": "6-G sample mechanism test",
                           "source_label": "来源：6-G 小样机制验证"}],
               "origin": {"compiled_from": "6-G sample（PROPOSED_ONLY）",
                          "note": "**不是** E2 方案 C 的最终设计，也**不是** E3 的最终设计；"
                                  "仅用于验证『叠加层 + DCv2 字幕重烧 + 跨子镜窗口』机制"},
               "sources": ["6-G sample mechanism test"],
               "must_not": ["不使用 IMO/竞赛合影", "不复用旧 [245,300] 坐标",
                            "不产生西文双引号引语"]}
vr = VA.verify_spec(sample_spec)
sample_spec_sha = VA.spec_sha256(sample_spec)

# ---------------------------------------------------------------- 3) E1 片尾卡（P-B：末 12s）
e1 = next(p for p in PKG["proposals"] if p["label"].startswith("E1"))
e1_params = e1["proposed_change"]["params"]

# ---------------------------------------------------------------- 执行计划（确定性）
sandbox_rel = "output/phase6g_sample/<ts>"
execs = [
    {"exec": 1, "id": "SAMPLE-1-split-S11", "executor": "ops.execution.exec_split_scene",
     "input": {"film": N0["master"]["path"], "sha256": N0["master"]["sha256"]},
     "ctx_bindings": {"timeline": "DCv2 new_production_timeline",
                      "timeline_identity": ident["identity_sha256"],
                      "caption_timeline.identity_sha256": cap_base.get("identity_sha256")},
     "proposal_subset": {"proposal_id": "SAMPLE-h3b-s11-subset（**非正式 H3b 执行**，正式 H3b 仍 NOT_EXECUTED）",
                         "scene": "S11", "asset": s11_asset},
     "deterministic_params": {"window": split_plan["scenes"][0]["window"],
                              "sub_count": split_plan["scenes"][0]["sub_count"],
                              "sub_duration_s": round(split_plan["scenes"][0]["sub_duration_s"], 3),
                              "cuts": [round(x, 3) for x in split_plan["scenes"][0]["cuts"]],
                              "zoom_pattern": [1.0, 1.18, 1.0]},
     "ffmpeg_arg_template": [
         "ffmpeg -y -v error -loop 1 -i <S11 asset> -t <sub_duration> -vf "
         "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720:(iw-ow)/2:(ih-oh)/2,"
         "fps=25,format=yuv420p[+ass=DCv2字幕] -an -c:v libx264 -preset ultrafast -pix_fmt yuv420p "
         "work/sv_SAMPLE_s11_<j>.mp4（j=0..2）",
         "ffmpeg -y -v error -i <master> -i <sv_0> -i <sv_1> -i <sv_2> -filter_complex "
         "[0:v]trim/select 拼接 + [1:v][2:v][3:v] 覆盖窗口 -map ... -c:a copy  ⇒ out/sample_1_split.mp4"],
     "expected_output": {"path": sandbox_rel + "/out/sample_1_split.mp4",
                         "duration_s": PROD, "audio": "母版音频流复制（sha256 不变）",
                         "sha256": "运行后计算（不预置）"},
     "rollback": "删除 output/phase6g_sample/<ts>/ 即可（母版零改动）"},
    {"exec": 2, "id": "SAMPLE-2-overlay-on-split-S11",
     "executor": "ops.execution.exec_add_visual_aid",
     "input": {"film": sandbox_rel + "/out/sample_1_split.mp4", "sha256": "运行后计算"},
     "ctx_bindings": {"timeline_identity": ident["identity_sha256"],
                      "caption_timeline.identity_sha256": cap_base.get("identity_sha256"),
                      "caption_time_base.mode": cap_base["mode"]},
     "proposal_subset": {"proposal_id": "SAMPLE-e3-mechanism（**非正式 E3 执行**）",
                         "scene": "S11", "window": W_A,
                         "note": "A（跨子镜常显）仅作为**机制**验证形态；E3 的 A/B 取舍仍属 H-6，未决"},
     "deterministic_params": {"window": W_A, "spec": sample_spec,
                              "spec_sha256": sample_spec_sha,
                              "spec_mode": "inline（params.visual_aid）",
                              "verify_spec": {k: vr.get(k) for k in ("schema", "panel_count",
                                                                     "errors", "warnings")},
                              "safe_area": "SAFE_BOTTOM_FRACTION={}".format(
                                  VA.SAFE_BOTTOM_FRACTION)},
     "ffmpeg_arg_template": [
         "ffmpeg -y -v error -ss 487.572 -t 51.774 -i <sample_1_split> -vf "
         "<overlay drawbox/drawtext 由 core.visual_aid 编译>,ass=<DCv2 S11窗口字幕> -an "
         "-c:v libx264 -preset ultrafast ⇒ work/overlay_s11.mp4",
         "ffmpeg -y -v error -i <sample_1_split> -i <overlay_s11> -filter_complex "
         "窗口覆盖 + 其余复制 -map 0:a -c:a copy ⇒ out/sample_2_overlay.mp4"],
     "expected_output": {"path": sandbox_rel + "/out/sample_2_overlay.mp4",
                         "duration_s": PROD, "audio": "母版音频流复制（sha256 不变）",
                         "sha256": "运行后计算（不预置）"},
     "rollback": "删除 output/phase6g_sample/<ts>/ 即可"},
    {"exec": 3, "id": "SAMPLE-3-outro-last12s", "executor": "ops.execution.exec_add_outro_card",
     "input": {"film": N0["master"]["path"], "sha256": N0["master"]["sha256"]},
     "ctx_bindings": {"timeline_identity": ident["identity_sha256"],
                      "caption_timeline.identity_sha256": cap_base.get("identity_sha256")},
     "proposal_subset": {"proposal_id": e1["proposal_id"], "scene": "S21", "window": W_B,
                         "note": "E1 的**窗口内重编码**形态：片尾卡只在 [966.656, 978.656] 出现"},
     "deterministic_params": {"window": W_B, "seconds": 12.0,
                              "font_file": e1_params["font_file"],
                              "fontsdir": e1_params["fontsdir"],
                              "text": e1_params["text"], "placement": "LAST_12S",
                              "disable_enable_filter": True,
                              "why_no_enable": "executor 只重编码该 12s 窗口并对其余区段流复制 ⇒ "
                                               "卡片天然只占 12s（无需 enable=）"},
     "ffmpeg_arg_template": [
         "ffmpeg -y -v error -ss 966.656 -t 12.000 -i <master> -vf "
         "drawtext=text='感谢观看　我们下期再见':fontfile='C\\:/Windows/Fonts/msyh.ttc':"
         "fontcolor=white:fontsize=64:box=1:boxcolor=black@0.55:boxborderw=24:"
         "x=(w-text_w)/2:y=h-260,ass=<DCv2 末窗字幕> -an -c:v libx264 -preset ultrafast "
         "⇒ work/card_SAMPLE_outro.mp4",
         "ffmpeg -y -v error -i <master> -i <card> -filter_complex 前段复制+末12s覆盖 -map 0:a "
         "-c:a copy ⇒ out/sample_3_outro.mp4"],
     "expected_output": {"path": sandbox_rel + "/out/sample_3_outro.mp4",
                         "duration_s": PROD, "audio": "母版音频流复制（sha256 不变）",
                         "sha256": "运行后计算（不预置）"},
     "rollback": "删除 output/phase6g_sample/<ts>/ 即可"},
]
total_exec_s = round((W_A[1] - W_A[0]) + (W_B[1] - W_B[0]), 3)

# ---------------------------------------------------------------- 验收计划
acceptance = {
    "scope_windows": {"S11": W_A, "LAST_12S": W_B}, "total_duration_s": total_exec_s,
    "executions": 3,
    "metrics": [
        {"metric": "duration", "how": "ffprobe 每个输出",
         "target": "== 978.656 ± 0.05（split/overlay/outro 均不得改变总时长）",
         "fail_action": "标记 FAIL，不进入下一步"},
        {"metric": "subtitle sync（窗口内）",
         "how": "① DCv2 `core.narration.subtitle_alignment(cues, plan)`；"
                "② 抽帧：S11 语音时刻有字幕、S11 段内停顿（0.75s）无字幕；"
                "③ 末 12s：语音区（≤976.656）有字幕、收尾 2.0s 无字幕",
         "target": "alignment.ok=True 且抽帧判定一致；**不得**出现 v1 表末条 1528.636s 类错位",
         "fail_action": "FAIL（说明 B1 修复未生效）"},
        {"metric": "PI-1..6（每个输出）",
         "how": "`core.integrity.pre_render_gate`（v2 口径，narration_plan 传入）+ `post_render_gate`",
         "target": "pre: PI-1/PI-2/PI-6/G-SEG/G-TL/G-PAD/G-SUB = PASS；post: PI-3/PI-4/PI-5 如实记录"
                   "（UNKNOWN ≠ PASS）",
         "fail_action": "如实记录并阻断"},
        {"metric": "DQ-3 / DQ-4（规划期，非 PASS 判定）",
         "how": "`core.direction.static_hold` / `visual_density`（对投影时间轴）",
         "target": "**记录**：H3a/H3b 未执行 ⇒ 场景仍 >25s；不得宣称 DQ-3/DQ-4 PASS",
         "fail_action": "—（只读诊断）"},
        {"metric": "visual continuity",
         "how": "窗口边界 ±0.5s 抽帧帧差；split 的 `_cut_evidence.all_distinct`；黑帧检测",
         "target": "无黑帧、无跳帧；切点内容可区分",
         "fail_action": "FAIL"},
        {"metric": "audio identity",
         "how": "抽取输出音轨 sha256 与母版音轨 sha256 比对（执行器均为母版音轨流复制）",
         "target": "**完全一致**",
         "fail_action": "FAIL（音轨被改动）"},
        {"metric": "reversibility / isolation",
         "how": "检查写入路径全部位于 output/phase6g_sample/<ts>/；DB/baseline/tag/历史 artifact "
                "sha256 不变",
         "target": "全部满足",
         "fail_action": "FAIL 并立即停止"}],
    "verdict_policy": "小样通过 ≠ 6-G PASS；H3/H5/E1–E5 仍 NOT_EXECUTED；DQ 不得宣称 PASS",
}

plan = {"schema": "phase6g-sample-execution-plan-v1", "stage": "6-G",
        "state": "PROPOSED_ONLY / AWAITING_HUMAN_AUTHORIZATION（H-8）",
        "not_executed": True,
        "prerequisite_audit": {"path": "docs/regression_2x/logs/phase6g_pre_sample_gate_audit.json",
                               "verdict": AUD["verdict"],
                               "gates_pass": sum(1 for g in AUD["gates"] if g["status"] == "PASS"),
                               "gates_total": len(AUD["gates"])},
        "inputs": {"master": N0["master"], "timeline_identity": ident,
                   "caption_time_base": {"mode": cap_base["mode"],
                                         "identity_sha256": cap_base.get("identity_sha256")},
                   "master_manifest": "docs/regression_2x/logs/phase6g_n0_dcv2_master.json",
                   "sandbox_root": sandbox_rel, "never_touch": ["projects/", "baseline", "tags",
                                                                "v9", "C1–C4", "E1/E2 candidate"]},
        "executions": execs,
        "deterministic_split_plan_S11": split_plan["scenes"][0],
        "sample_spec": sample_spec, "sample_spec_sha256": sample_spec_sha,
        "acceptance_plan": acceptance,
        "not_in_scope": ["H5（PENDING_HUMAN_ASSET）", "E2/E4/E5（D8 未决）", "H3a/H3b 正式执行",
                         "H3c（authorized=false）", "baseline/tag 切分", "promote", "正式登记链"],
        "required_human_authorization": [
            {"id": "H-8", "need": "批准本小样范围 + 验收口径（是否允许为小样临时修复字幕路径）",
             "state": "PENDING_HUMAN_INPUT"},
            {"id": "H-9", "need": "小样执行授权（3 次沙箱执行）", "state": "PENDING_HUMAN_INPUT"},
            {"id": "H-6", "need": "E3 A/B（本小样以 A 形态**验证机制**，不构成 E3 决策）",
             "state": "PENDING_HUMAN_INPUT"}],
        "invariants": {"ffmpeg_calls": 0, "mp4_written": 0, "db_written": 0,
                       "historical_artifacts_modified": 0, "baseline_tag_modified": 0,
                       "proposals_executed": 0, "promoted": False}}
plan["plan_sha256"] = hashlib.sha256(json.dumps(
    {k: v for k, v in plan.items() if k != "plan_sha256"}, sort_keys=True, ensure_ascii=False,
    separators=(",", ":"), default=str).encode("utf-8")).hexdigest()
OUT.write_text(json.dumps(plan, ensure_ascii=False, indent=1, default=str), encoding="utf-8")

print("== 小样执行计划（PROPOSED_ONLY）==")
print("  窗口 A(S11) {} | 窗口 B(LAST_12S) {} | 合计 {}s | 执行 {} 次".format(
    W_A, W_B, total_exec_s, len(execs)))
for e in execs:
    print("   exec{} {} → {}".format(e["exec"], e["id"][:34], e["expected_output"]["path"]))
print("  S11 素材（v9 在用）: {}".format(s11_asset))
print("  split S11: {} 子镜 × {}s, cuts {}".format(
    split_plan["scenes"][0]["sub_count"],
    round(split_plan["scenes"][0]["sub_duration_s"], 3),
    [round(x, 3) for x in split_plan["scenes"][0]["cuts"]]))
print("  sample spec sha256: {}（verify_spec errors={}）".format(
    sample_spec_sha[:16], vr.get("errors")))
print("  验收指标 {} 项 | 前置审计 {} {}/{}".format(
    len(acceptance["metrics"]), AUD["verdict"],
    sum(1 for g in AUD["gates"] if g["status"] == "PASS"), len(AUD["gates"])))
print("  待人工授权: H-8 / H-9（+ H-6 供 E3 决策）")
print("plan ->", OUT)
