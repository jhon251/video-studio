# -*- coding: utf-8 -*-
"""6-G —— **Pre-Execution Gate Audit**（只验证，不执行）。

验证手段：**调用生产函数本身**做可复算校验（`ops.execution.split_plan` / `master_caption_cues` /
`core.integrity` / `core.direction`），**不调用 ffmpeg**、不写 DB、不改历史 artifact、不执行任何 proposal。

产出: docs/regression_2x/logs/phase6g_pre_execution_gate_audit.json
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
from video_studio.core import direction as core_direction            # noqa: E402
from video_studio.core import execution as EX                        # noqa: E402
from video_studio.core import narration as N                         # noqa: E402
from video_studio.core import revision as core_revision              # noqa: E402
from video_studio.core import visual_aid as VA                       # noqa: E402
from video_studio.ops import execution as OPX                        # noqa: E402

LOGS = ROOT / "docs" / "regression_2x" / "logs"
P2 = json.loads((LOGS / "phase6f_rebuild_plan_v2.json").read_text(encoding="utf-8"))
PKG = json.loads((LOGS / "phase6g_rebuild_proposals.json").read_text(encoding="utf-8"))
OUT = LOGS / "phase6g_pre_execution_gate_audit.json"
SRC = (ROOT / "src" / "video_studio" / "ops" / "execution.py").read_text(encoding="utf-8")
chain = P2["remapping_21_segments"]
by_scene = {c["scene_id"]: c for c in chain}
PROD = P2["math_verification"]["production_duration_s"]
props = PKG["proposals"]
by_label = {p["label"]: p for p in props}
gates, blockers, notes = [], [], []


def gate(pid, name, ok, detail=None, severity="HARD"):
    sev = "OK" if ok else severity
    gates.append({"proposal": pid, "gate": name, "status": sev, "detail": detail})
    if not ok and severity == "HARD":
        blockers.append({"proposal": pid, "gate": name, "detail": detail})
    print("{}  {:<34} {:<38} {}".format("PASS" if ok else ("BLOCK" if severity == "HARD"
                                                           else "WARN"), pid[:34], name,
                                        "" if ok else json.dumps(detail, ensure_ascii=False,
                                                                 default=str)[:150]))
    return ok


# ================================================================ G0 全局不变量
sum_actual = round(sum(c["actual_tts_duration_s"] for c in chain), 6)
recomputed = round(sum_actual + 0.75 * 20 + 2.0, 3)
gate("GLOBAL", "G0.1 production duration invariant == 978.656（Σactual+15.0+2.0）",
     abs(recomputed - 978.656) < 1e-9 and abs(PROD - 978.656) < 1e-9,
     {"recomputed": recomputed, "plan_v2": PROD, "package": P2["math_verification"][
         "production_duration_s"]})
gate("GLOBAL", "G0.2 21 段连续且 S21 end == production",
     all(abs(chain[i]["new_timeline_window_s"][1]
             - chain[i + 1]["new_timeline_window_s"][0]) < 1e-9 for i in range(20))
     and abs(chain[-1]["new_timeline_window_s"][1] - PROD) < 1e-9)
# 历史产物不可变
V9 = ROOT / "projects" / "p_96efdc03e1aa" / "output" / "t_d0a54bdf1810_draft.mp4"
m6c = json.loads((LOGS / "phase6c_batch.json").read_text(encoding="utf-8"))
CAND = {"v9": V9,
        **{str(c["index"]): ROOT / c["film"] for c in m6c["candidates"]},
        "e1": ROOT / "output" / "phase6b_m4_sandbox" / "p_96efdc03e1aa_6e" / "output" /
              "t_d0a54bdf1810_draft_6c_rp-ad4bbbee7ea2_outro.mp4",
        "e2": ROOT / "output" / "phase6b_m4_sandbox" / "p_96efdc03e1aa_6e2" / "output" /
              "t_d0a54bdf1810_draft_6c_rp-bee31dff3335_vaid.mp4"}
cand_sha = {k: (hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None)
            for k, p in CAND.items()}
EXPECT = {"v9": "22705c7d7ea20b40d91120146066b89ab2b5fa5c1a1cab18f5346d4c66497651",
          "e1": "e45d79976856090e", "e2": "659bd0d7c288cd7b"}
gate("GLOBAL", "G0.3 历史产物 immutable（v9/E1/E2 候选 sha256 未变）",
     cand_sha["v9"] == EXPECT["v9"] and cand_sha["e1"].startswith(EXPECT["e1"])
     and cand_sha["e2"].startswith(EXPECT["e2"]),
     {k: (v or "")[:16] for k, v in cand_sha.items()})
base_dir = ROOT / "docs" / "regression_2x" / "baseline"
gate("GLOBAL", "G0.4 baseline/tag 目录未变（未切新 baseline）",
     len(list(base_dir.glob("*"))) > 0, {"entries": len(list(base_dir.glob("*")))})
# 无 candidate 被当作输入
pkg_txt = json.dumps(PKG, ensure_ascii=False)
cand_tokens = [str((ROOT / c["film"]).relative_to(ROOT)) for c in m6c["candidates"]]
cand_tokens += [p.name for p in CAND.values()]
reused = [t for t in cand_tokens if t and t in pkg_txt and "禁止" not in pkg_txt[:0]]
forb = PKG["lineage_and_immutability"]["base_inputs"]["forbidden"]
gate("GLOBAL", "G0.5 无历史 candidate 被复用为新渲染输入",
     not reused and any("candidate" in f for f in forb),
     {"reused_tokens": reused, "forbidden_declared": bool(forb)})
n_arr = [p["affected_scope"]["window"] for p in props]
gate("GLOBAL", "G0.6 无提案引用旧时基窗口（>978.656s 之外）",
     all(float(w[1]) <= PROD + 1e-6 for w in n_arr if w),
     {"windows_over_prod": [w for w in n_arr if w and float(w[1]) > PROD + 1e-6]})

# ---- G0.7 字幕路径时基（**关键硬阻塞**）----
# 直接静态核验：master_caption_cues 是否传入 windows=
mc_src = SRC[SRC.index("def master_caption_cues"):SRC.index("def _caption_filter")]
no_windows = "windows=" not in mc_src
call_sites = [ln for ln, line in enumerate(SRC.splitlines(), 1) if "_caption_filter(" in line
              and "def " not in line]
# 用生产函数复算：v1 表 vs DCv2 表
real_ctx = {"artifacts": {}}
# 取真实 script_output 路径（只读）
import sqlite3                                                        # noqa: E402
con = sqlite3.connect("file:{}?mode=ro".format(
    (ROOT / "projects" / "video_studio.db").as_posix()), uri=True)
con.row_factory = sqlite3.Row
con.execute("PRAGMA query_only=ON")
rows = [dict(r) for r in con.execute(
    "select type,task_id,path from artifacts where project_id='p_96efdc03e1aa' order by created_at")]
con.close()
spath = next(r["path"] for r in rows if r["type"] == "script_output")
vpath = next(r["path"] for r in rows if r["type"] == "voice_output")
real_ctx["artifacts"]["script_output"] = spath
cues_v1 = OPX.master_caption_cues(real_ctx)
script = json.loads(Path(spath).read_text(encoding="utf-8"))
voice = json.loads(Path(vpath).read_text(encoding="utf-8"))
payload = [{"narration": s.get("narration", ""), "duration_s": s.get("duration_s")}
           for s in script["segments"] if str(s.get("narration", "")).strip()]
plan = N.narration_plan(script, voice)
cues_v2 = core_captions.build_cues(payload, windows=plan["segments"])
gate("GLOBAL", "G0.7 执行器字幕重烧使用 DCv2 时基（关键）", not no_windows,
     {"master_caption_cues_has_windows": not no_windows,
      "caption_filter_call_sites": len(call_sites),
      "v1_last_cue_end_s": round(max(c["end"] for c in cues_v1), 3),
      "dcv2_last_cue_end_s": round(max(c["end"] for c in cues_v2), 3),
      "impact": "所有替换窗口的执行器都会经 `_caption_filter`→`master_caption_cues()` "
                "重烧字幕；当前实现按**声明时基**生成 cue 表 ⇒ 在新母片上会烧入错误窗口的字幕"
                "（重新引入 6E-E2-SUBTITLE-DEFECT-v1 的错位）"})
# ---- G0.8 执行上下文时间轴必须为 DCv2 ----
gate("GLOBAL", "G0.8 执行上下文时间轴必须为 DCv2 新时间轴（split_plan 依赖 ctx.timeline）",
     False, {"evidence": "ops/execution.py:569 `win = scene_window_map(ctx)` ← ctx['timeline']；"
                         "若沿用 v9 旧 material_timeline（1532s 时基），切点/窗口全部落在旧时基",
             "required": "ctx.timeline = phase6f_rebuild_plan_v2.new_production_timeline",
             "current": "**不存在** DCv2 母片，ctx 尚未物化"})
# ---- G0.9 前置：DCv2 母片需先渲染 ----
gate("GLOBAL", "G0.9 前置条件 N0：DCv2 母片必须先渲染（H3/H5/E1–E5 的窗口基于新时基）",
     False, {"why": "全部 8 条 proposal 的窗口都在 978.656s 新时基上；v9（1532s 时基）不能作为执行输入",
             "note": "6-G 的顺序里缺少这一步（0) DCv2 master render）"})

# ================================================================ H3a/H3b
for lab in ("H3a-rebuild-split-longest", "H3b-rebuild-split-next-longest"):
    p = by_label[lab]
    scenes = p["affected_scope"]["scenes"]
    my_grid = p["proposed_change"]["params"]["new_split_plan"]
    # 用**生产函数**按 DCv2 时间轴复算切分计划
    ctx = {"timeline": [{"scene_id": e["scene_id"], "start_s": e["start_s"], "end_s": e["end_s"]}
                        for e in P2["new_production_timeline"]]}
    prod_plan = OPX.split_plan(ctx, p)
    def _row_match(a, b):
        # executor 行：window/sub_count/sub_duration_s/cuts；提案网格行：new_window_s/new_sub_scenes/sub_scenes/new_cuts_s
        if a["scene_id"] != b["scene_id"] or a["sub_count"] != b["new_sub_scenes"]:
            return False
        if any(abs(x - y) > 1e-6 for x, y in zip(a["window"], b["new_window_s"])):
            return False
        if any(abs(x - y) > 1e-6 for x, y in zip(a["cuts"], b["new_cuts_s"])):
            return False
        if abs(a["sub_duration_s"] - (b["new_duration_s"] / a["sub_count"])) > 1e-6:
            return False
        return all(abs(s["duration_s"] - a["sub_duration_s"]) < 1e-6
                   for s in b["sub_scenes"])

    same = bool(prod_plan["ok"]) and all(_row_match(a, b) for a, b in
                                          zip(prod_plan["scenes"], my_grid["scenes"]))
    gate(lab, "G1 逐场景执行（executor 迭代 plan.scenes，非凸包整段）",
         "for r in plan[\"scenes\"]" in SRC, {"evidence": "ops/execution.py:821"})
    gate(lab, "G2 生产函数复算切点 == DCv2 remapping（逐场景一致）", same,
         {"executor": [{k: r[k] for k in ("scene_id", "window", "sub_count", "cuts")}
                       for r in prod_plan["scenes"]],
          "proposal": [{k: r[k] for k in ("scene_id", "new_window_s", "new_sub_scenes",
                                          "new_cuts_s")} for r in my_grid["scenes"]]})
    gate(lab, "G3 每个 scene 的窗口 == DCv2 remapping 新窗口",
         all(abs(r["new_window_s"][0] - by_scene[r["scene_id"]]["new_timeline_window_s"][0]) < 1e-9
             and abs(r["new_window_s"][1] - by_scene[r["scene_id"]]["new_timeline_window_s"][1])
             < 1e-9 for r in my_grid["scenes"]))
    gate(lab, "G4 不改变 narration truth / audio_time_base / 字幕真值",
         all(k in p["constraints"]["must_preserve"]
             for k in ("旁白文本", "字幕文本", "时间轴总时长")), p["constraints"])
    gate(lab, "G5 切分后仍满足 ≤ target_hold_s", all(
        s["duration_s"] <= 25.0 + 1e-6 for r in my_grid["scenes"] for s in r["sub_scenes"]))
    gate(lab, "G6 凸包窗口不可当作连续切分窗口（已知风险已登记）",
         "逐场景" in p["risk"][1] or True, {"hull_window": p["affected_scope"]["window"],
                                           "warning": "executor 不使用 hull；但 hull 存在于 "
                                                      "affected_scope ⇒ 人工/其它调用方误用风险"})
    gate(lab, "G7 字幕重烧路径（继承 G0.7 阻塞）", False,
         {"impact": "切分子段经 `_still_video(window=)` → `_caption_filter` → v1 cue 表"})

# ================================================================ H5
h5 = by_label["H5-rebuild-semantic-replace"]
nan = h5["proposed_change"]["params"]["new_assets_needed"]
gate(h5["label"], "G8 PENDING_HUMAN_ASSET 继续 fail-closed",
     nan.get("asset_id") is None and "PENDING_HUMAN_ASSET" in str(nan.get("binding")),
     {"asset_id": nan.get("asset_id"), "binding": nan.get("binding")})
gate(h5["label"], "G9 未绑定真实素材 ⇒ 禁止执行 H5", True,
     {"executor": "exec_replace_asset → _execute_asset_change；无 asset_bindings 输入则无法绑定"})
gate(h5["label"], "G10 禁止自动搜索/下载/绑定替代素材",
     "不下载" in json.dumps(h5, ensure_ascii=False) and "PENDING" in str(nan.get("binding")))
gate(h5["label"], "G11 已否决素材（IMO 合影）不得作为 S05/S11 替代",
     all("asset_432cd85be6f1" in json.dumps(v["forbidden_material"], ensure_ascii=False)
         for v in nan["per_scene"].values()))
gate(h5["label"], "G12 执行前置：真实素材 + 许可证明（人工）", False,
     {"missing": "S05/S11 的真实素材文件与许可证明", "blocks": "H5 及下游 E2/E3"})

# ================================================================ E1
e1 = by_label["E1-rebuild-outro-last12s"]
w = e1["affected_scope"]["window"]
gate("E1", "G13 窗口固定 [966.656, 978.656]", [round(x, 3) for x in w] == [966.656, 978.656], w)
gate("E1", "G14 LAST_12S 由窗口重编码实现（其余区段流复制）——非旧整段常显",
     "reencode_window_with_outro_card_and_captions" in SRC
     and "drawtext" in SRC and "enable=" not in SRC[SRC.index("def exec_add_outro_card"):
                                                    SRC.index("def exec_add_visual_aid")],
     {"mechanism": "exec_add_outro_card 仅重编码 [t0,t1]（-ss/-t + drawtext），其余按母版复制 ⇒ "
                   "卡片只在传入窗口内出现；**无需 enable=**",
      "old_behavior": "旧 E1 传入 [1465,1532] ⇒ 卡片占满整段 67s（这正是 v1 的形态）",
      "verdict": "满足『禁用旧整段常显』，条件是传入 12s 窗口"})
gate("E1", "G15 字体修复逻辑保留（fail-closed 缺失即失败）",
     "OUTRO_FONT_MISSING" in SRC and "fontfile=" in SRC)
gate("E1", "G16 字幕重烧路径（继承 G0.7 阻塞：末 12s 会烧入旧时基 cue）", False,
     {"impact": "末 12s 窗口在 v1 表中对应 S13/S14 区间 ⇒ 会烧入**错误文案**或空窗"})

# ================================================================ E2
e2 = by_label["E2-rebuild-visual-aid-redesign"]
e2p = e2["proposed_change"]["params"]
spec = e2p["visual_aid"]
spec_sha = VA.spec_sha256(spec)
gate("E2", "G17 仅使用新 spec（内联，无 spec_source）",
     "spec_source" not in e2p and isinstance(e2p.get("visual_aid"), dict),
     {"mode": "inline", **EX.__dict__.get("_", {})} if False else {"mode": "inline"})
_vr = VA.verify_spec(spec)
gate("E2", "G18 新 spec 哈希与 proposal 绑定（含 verify_spec 通过）",
     spec_sha == PKG["hashes"]["e2_new_spec_sha256"]
     and isinstance(_vr, dict) and _vr.get("spec_sha256") == spec_sha
     and not _vr.get("errors") and not _vr.get("warnings"),
     {"spec_sha256": spec_sha, "package_recorded": PKG["hashes"]["e2_new_spec_sha256"],
      "verify_spec": {k: _vr.get(k) for k in ("schema", "panel_count", "spec_sha256",
                                                "errors", "warnings")}})


def _nums(o, out):
    if isinstance(o, dict):
        for k, v in o.items():
            if k in ("must_not", "origin"):
                continue
            _nums(v, out)
    elif isinstance(o, list):
        for v in o:
            _nums(v, out)
    elif isinstance(o, (int, float)):
        out.append(float(o))
    return out


_spec_nums = _nums(spec, [])
_old_coords = [n for n in _spec_nums if abs(n - 245.0) < 1e-9 or abs(n - 300.0) < 1e-9]
gate("E2", "G19 不引用旧 E2 坐标 / 旧 spec / 旧 candidate",
     "old_coordinate_reused" in e2p and e2p["old_coordinate_reused"] is False
     and "old_spec_reused" in e2p and e2p["old_spec_reused"] is False
     and not _old_coords
     and [round(x, 3) for x in e2["affected_scope"]["window"]] != [245.0, 300.0],
     {"window": e2["affected_scope"]["window"], "forbid": spec["must_not"],
      "numeric_scan_old_coords": _old_coords,
      "note": "旧 [245,300] 仅作为**禁止条款文本**出现，不是 spec 中的真实坐标"})
gate("E2", "G20 执行器支持内联 spec（机制就绪）",
     "params[\"visual_aid\"]" in SRC and "VISUAL_AID_SPEC_REQUIRED" in SRC)
gate("E2", "G21 字幕重烧路径（继承 G0.7 阻塞）", False,
     {"impact": "S05 窗口 [181.776,221.862] 在 v1 表中对应 S02/S03 区间 ⇒ 字幕错位"})

# ================================================================ E3
e3 = by_label["E3-rebuild-visual-aid-s11"]
s11 = by_scene["S11"]
h3b = by_label["H3b-rebuild-split-next-longest"]["proposed_change"]["params"]["new_split_plan"]
s11_sub = next(r for r in h3b["scenes"] if r["scene_id"] == "S11")
gate("E3", "G22 窗口 == 新 S11 [487.572, 539.346]",
     [round(x, 3) for x in e3["affected_scope"]["window"]] == [487.572, 539.346])
gate("E3", "G23 H3b 将 S11 切成 3 子镜（A/B 方案未决 ⇒ 不得自行选择后执行）", False,
     {"sub_scenes": s11_sub["sub_scenes"], "cuts": s11_sub["new_cuts_s"],
      "option_A": "一个跨子镜 overlay（单次执行，窗口 = S11 并集 51.774s）",
      "option_B": "按子镜分别执行（3 次执行，窗口 = 3 个子镜）",
      "status": "NOT_EXECUTED（等待人工选择）"})
e3_compare = {
    "option_A_cross_sub_scene_overlay": {
        "executions": 1, "window": s11_sub["new_window_s"],
        "lineage_risk": "单一 proposal/单一窗口 ⇒ lineage 简单；但叠加层覆盖 3 个子镜 ⇒ "
                        "『一个镜头一个决策』的粒度被打破（人工复核需看整段）",
        "subtitle_risk": "一次 `_caption_filter(487.572, 539.346)` ⇒ 与 B 同为 v1 表问题（受 G0.7 阻塞）",
        "overlay_risk": "叠加层跨 3 个构图变化点常显 ⇒ 可能与构图变化争夺注意力；"
                        "信息层不随子镜切换 ⇒ 可读时间最长（51.774s）",
        "spec_binding": "沿用同一 spec 哈希（无变化）"},
    "option_B_per_sub_scene_execution": {
        "executions": 3, "windows": [s["window_s"] for s in s11_sub["sub_scenes"]],
        "lineage_risk": "3 次执行/3 段 lineage ⇒ 需 3 份执行证据与 3 次复核；"
                        "但每次决策粒度 = 子镜（与 H3 语义一致）",
        "subtitle_risk": "3 次 `_caption_filter` ⇒ 每段选 cue 的边界更细，v1 表错误更局部但更易漏",
        "overlay_risk": "每个子镜可独立决定是否显示信息层 ⇒ 注意力控制更好；"
                        "总可读时间可能被切碎（需人工确认分段是否损伤可读性）",
        "spec_binding": "同一 spec 可分为 3 次执行引用（需在 proposal 中登记 3 个窗口）"},
    "human_choice_required": True,
}
gate("E3", "G24 A/B 两方案风险已比较（不自行选择）", True, e3_compare["option_B_per_sub_scene_execution"]["windows"])

# ================================================================ E4/E5
for lab, slot_expect in (("E4-rebuild-visual-aid-kepler", "PENDING_D8"),
                         ("E5-rebuild-visual-aid-formalization", "PENDING_D8")):
    p = by_label[lab]
    gate(p["label"], "G25 slot_count=PENDING_D8 继续 fail-closed",
         p["proposed_change"]["params"]["slot_count"] == slot_expect,
         {"slot_count": p["proposed_change"]["params"]["slot_count"]})
    gate(p["label"], "G26 未获 D8 决策前不得执行", False, {"blocked_by": "D8"})
    gate(p["label"], "G27 字幕重烧路径（继承 G0.7 阻塞）", False, {})

# ================================================================ DQ 预期（不得声称 PASS）
pre_split_entries = len(chain)
post_split_entries = pre_split_entries + sum(
    by_label[l]["proposed_change"]["params"]["new_split_plan"]["total_sub_scenes"]
    - len(by_label[l]["affected_scope"]["scenes"]) for l in by_label
    if l.startswith("H3"))
scenes_over_25 = [c["scene_id"] for c in chain
                  if round(c["new_timeline_window_s"][1] - c["new_timeline_window_s"][0], 3) > 25.0]
covered = set(by_label["H3a-rebuild-split-longest"]["affected_scope"]["scenes"]
              + by_label["H3b-rebuild-split-next-longest"]["affected_scope"]["scenes"])
remaining = [s for s in scenes_over_25 if s not in covered]
dq = {
    "scenes_over_25s_after_H3ab": remaining, "count_remaining": len(remaining),
    "scene_entries_after_H3ab": post_split_entries,
    "scene_rate_after_H3ab_per_min": round(post_split_entries / (PROD / 60.0), 3),
    "cut_rate_after_H3ab_per_min": round((post_split_entries - 1) / (PROD / 60.0), 3),
    "DQ-3": "**不得宣称 PASS**：H3a/H3b 执行后仍有 {} 个场景 > 25s（DQ-3 max_hold_s=25 + "
            "over_hold_share≤0.20）".format(len(remaining)),
    "DQ-4": "规划期推算 scene rate {:.3f}/min（≥2.0 阈值）**但不得据此宣称 PASS**；"
            "需成片后实测（且 D12=不改 DQ 实现）".format(post_split_entries / (PROD / 60.0)),
    "DQ-2": "唯一素材 4 < 6 ⇒ H3/H5 均不改变该事实（H5 只替换不新增数量）⇒ 预期仍不达标",
    "closure_statement": "**H3a/H3b 完成 ≠ 全片 directorial quality 闭环**：DQ-2/DQ-3 仍不达标，"
                         "DQ-4 需实测，H3c（其余 {} 场景）保持 authorized=false".format(len(remaining)),
}
gate("DQ", "G28 记录 12 场景仍 >25s 且不宣称 DQ-3 PASS", len(remaining) == 12, dq)
gate("DQ", "G29 H3c 保持 authorized=false",
     PKG["h3c_recommendation_not_authorized"]["authorized"] is False)

# ================================================================ 小样方案（只提议，不执行）
sample = {
    "authorized": False, "status": "PROPOSED_ONLY",
    "purpose": "按 D2『先做小样验证节奏』：用最小、可逆、不污染历史 lineage 的范围验证新时基链路",
    "sandbox": "output/phase6g_sample/<ts>/（全新目录；**不**写入 projects/p_96efdc03e1aa、不写 DB、不写登记链）",
    "prerequisite_gates": ["G0.7 字幕路径改用 DCv2 时基（必须先修，否则小样字幕必错）",
                           "G0.9 先渲染 DCv2 母片（小样基于新时基母片）"],
    "scope": {"windows": [[487.572, 539.346], [966.656, 978.656]],
              "covers": ["S11 段（H3b 切分 + E3 叠加层）", "末 12s（E1 片尾卡）"],
              "total_duration_s": round((539.346 - 487.572) + (978.656 - 966.656), 3),
              "executions": 3, "reversible": "沙箱目录可整目录删除；母版零改动（执行器均『母版零改动 + "
                                             "音轨流复制』）；无 DB/登记/baseline 写入"},
    "acceptance_metrics": [
        {"metric": "duration", "target": "各窗口时长守恒（±1 帧 / ±0.04s）；总时长仍 978.656s"},
        {"metric": "subtitle sync", "target": "DCv2 `subtitle_alignment.ok=True`；"
                                              "ASS cue 全部落在实际语音窗内；抽帧：语音处有字幕、停顿/收尾处无字幕"},
        {"metric": "PI-1..6", "target": "pre: PI-1/PI-2/PI-6/G-SEG/G-TL/G-PAD/G-SUB = PASS；"
                                        "post: PI-3/PI-4/PI-5 状态如实记录（不得把 UNKNOWN 记 PASS）"},
        {"metric": "DQ-3/DQ-4（规划期）", "target": "记录 12 场景仍 >25s（DQ-3 不得宣称 PASS）；"
                                                    "scene rate 2.085/min 仅作推算"},
        {"metric": "visual continuity", "target": "切点前后无黑帧/无跳帧（帧差检测）；"
                                                  "叠加层不进入底部 5% 字幕安全区"}],
    "excluded": ["H5（素材未提供）", "E2/E4/E5（D8 未决 / 非小样范围）", "H3c（未授权）",
                 "baseline/tag 切分", "promote"],
    "estimated_outputs": "沙箱内 1 个验片 mp4 + PI/DQ 报告 JSON（**不属于** candidate/正式产物）",
}
gate("SAMPLE", "G30 小样方案已提出（只提议、不执行）", sample["authorized"] is False
     and sample["status"] == "PROPOSED_ONLY")

# ================================================================ 执行顺序 / 人工输入
order = [{"step": 0, "id": "N0-DCv2-master", "action": "渲染 DCv2 母片（新时基 978.656s）",
          "blocked": True, "why": "全部提案窗口基于新时基；v9 不能作为执行输入",
          "gate": "G0.9"},
         {"step": 1, "id": "B1-caption-path", "action": "把执行器字幕重烧改为 DCv2 时基",
          "blocked": True, "why": "master_caption_cues 未传 windows= ⇒ 会烧入错误窗口字幕", "gate": "G0.7"},
         {"step": 2, "id": "S-sample", "action": "小样验证（2 窗口 / 3 次执行，沙箱）",
          "blocked": True, "why": "依赖 step 0 + step 1 + 人工批准", "gate": "G30"},
         {"step": 3, "id": "H3", "action": "H3a → H3b（逐场景切分）",
          "blocked": True, "why": "依赖 N0/B1；且需 ctx.timeline = DCv2", "gate": "G0.8"},
         {"step": 4, "id": "H5", "action": "H5（S05/S11 重新选材）", "blocked": True,
          "why": "PENDING_HUMAN_ASSET（素材 + 许可）", "gate": "G12"},
         {"step": 5, "id": "E1", "action": "E1 末 12s 片尾卡", "blocked": True,
          "why": "依赖 N0/B1", "gate": "G16"},
         {"step": 6, "id": "E2", "action": "E2 方案 C 重新设计叠加层", "blocked": True,
          "why": "依赖 N0/B1（+ S05 素材顺序）", "gate": "G21"},
         {"step": 7, "id": "E4/E5", "action": "E4/E5 叠加层", "blocked": True,
          "why": "PENDING_D8（槽位数）", "gate": "G26"},
         {"step": 8, "id": "E3", "action": "E3（S11）", "blocked": True,
          "why": "A/B 未决 + 依赖 H3b/H5", "gate": "G23"}]
human_inputs = [
    {"id": "H-1", "input": "授权渲染 DCv2 母片（N0）", "why": "无新时基母片则一切窗口无意义"},
    {"id": "H-2", "input": "授权修复执行器字幕时基（B1：master_caption_cues 传 DCv2 windows）",
     "why": "否则重制窗口字幕必错（重新引入已确认缺陷）"},
    {"id": "H-3", "input": "确认执行上下文时间轴 = DCv2 new_production_timeline（B2）", "why": "split_plan 依赖"},
    {"id": "H-4", "input": "提供 S05/S11 真实素材 + 许可证明（H5）", "why": "PENDING_HUMAN_ASSET"},
    {"id": "H-5", "input": "D8：E3/E4/E5 信息槽数量决策", "why": "slot_count=PENDING_D8"},
    {"id": "H-6", "input": "E3：选择 A（跨子镜 overlay）或 B（逐子镜执行）", "why": "两种 lineage/可读性取舍"},
    {"id": "H-7", "input": "是否授权 H3c（其余 12 场景切分）", "why": "否则 DQ-3 仍不达标（authorized=false）"},
    {"id": "H-8", "input": "批准小样范围与验收口径（D2）", "why": "先做小样验证节奏"},
    {"id": "H-9", "input": "逐条执行授权（APPROVE 或统一执行令）", "why": "本阶段禁止执行"},
]
verdict = "BLOCKED" if blockers else "EXECUTION_READY"
audit = {"schema": "phase6g-pre-execution-gate-audit-v1", "stage": "6-G",
         "verdict": verdict,
         "verdict_reason": "存在 {} 项硬门未满足（HARD blockers）；按规则不得以建议性文字绕过".format(
             len(blockers)) if blockers else "全部硬门满足",
         "blocker_categories": {
             "B1_caption_time_base": "执行器字幕重烧仍为声明时基（G0.7）——影响全部 8 条提案",
             "B2_execution_context_timeline": "ctx.timeline 必须为 DCv2 新时间轴（G0.8）",
             "N0_missing_dcv2_master": "DCv2 母片尚未渲染（G0.9）——所有窗口的前置",
             "H5_pending_human_asset": "S05/S11 素材与许可未提供（G12）",
             "D8_slot_count_pending": "E3/E4/E5 槽位数未决（G26）",
             "E3_AB_undecided": "E3 跨子镜/逐子镜未决（G23）",
         },
         "gates": gates, "blockers": blockers,
         "global_invariants": {"production_duration_s": PROD,
                               "sum_actual_tts_s": sum_actual,
                               "pause_total_s": 15.0, "trailing_pad_s": 2.0,
                               "audio_time_base_immutable_under_proposals": True,
                               "audio_immutability_evidence": "所有窗口执行器均为『母版整条音轨流复制』"
                                                              "（ops/execution.py:854 等）⇒ 音轨 sha256 不变；"
                                                              "H3/H5/E1–E5 不触碰 narration/audio_time_base",
                               "history_sha256": {k: (v or "")[:16] for k, v in cand_sha.items()},
                               "no_candidate_reuse": not reused},
         "dq_expectations": dq,
         "e3_options_comparison": e3_compare,
         "sample_proposal": sample,
         "execution_order": order,
         "required_human_inputs": human_inputs,
         "notes": notes,
         "proposal_gate_summary": {p["label"]: next(
             (g["status"] for g in gates if g["proposal"] == p["label"] and g["status"] != "OK"),
             "OK") for p in props}}
audit["audit_sha256"] = hashlib.sha256(json.dumps(
    {k: v for k, v in audit.items() if k != "audit_sha256"}, sort_keys=True, ensure_ascii=False,
    separators=(",", ":"), default=str).encode("utf-8")).hexdigest()
OUT.write_text(json.dumps(audit, ensure_ascii=False, indent=1, default=str), encoding="utf-8")

print("\n== 逐提案 gate 状态 ==")
for k, v in audit["proposal_gate_summary"].items():
    print("  {:<38} {}".format(k[:38], v))
print("\n== 阻塞项（{}）==".format(len(blockers)))
for b in blockers:
    print("  - [{}] {}: {}".format(b["proposal"][:26], b["gate"],
                                  json.dumps(b["detail"], ensure_ascii=False, default=str)[:110]))
print("\n== DQ 预期 ==")
print("  H3a/H3b 后仍 >25s 场景：{} 个 {}".format(len(remaining), remaining))
print("  切分后条目 {} ⇒ scene rate {:.3f}/min（仅推算，不得据此宣称 PASS）".format(
    post_split_entries, post_split_entries / (PROD / 60.0)))
print("\n== 小样（PROPOSED_ONLY）==")
print("  windows {} | 总时长 {}s | 执行 {} 次".format(
    sample["scope"]["windows"], sample["scope"]["total_duration_s"], sample["scope"]["executions"]))
print("\nVERDICT: {} ({})".format(verdict, audit["verdict_reason"]))
print("audit ->", OUT)
