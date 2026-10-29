# -*- coding: utf-8 -*-
"""6-F —— **Historical Lineage Rebuild Planning**（只读规划：不重制、不生成 MP4、不调用 ffmpeg）。

规则：
  · v9 / C1–C4 / E1 / E2 视为**历史 artifact**，只读引用，不修改、不覆盖、不 promote；
  · narration truth = 现有真实 TTS 逐段时长（**不重录**）；
  · 用 DCv2 `audio_time_base` 重新推导：21 段实际窗口 / timeline / 字幕窗口 / BGM ducking / 素材 in-out；
  · 产出 `logs/phase6f_rebuild_plan.json`（**不生成任何 MP4**）。

产出: docs/regression_2x/logs/phase6f_rebuild_plan.json
"""
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
from video_studio.core import bgm as core_bgm                        # noqa: E402
from video_studio.core import captions as core_captions              # noqa: E402
from video_studio.core import narration as N                         # noqa: E402
from video_studio.core import revision as core_revision              # noqa: E402

LOGS = ROOT / "docs" / "regression_2x" / "logs"
DB = ROOT / "projects" / "video_studio.db"
OUT = LOGS / "phase6f_rebuild_plan.json"
PAUSE = N.PAUSE_BUDGET_S                    # 0.75（DCv2 默认；可被 editing.narration_pause_budget_s 覆盖）
TRAILING = N.TRAILING_PAD_S                 # 2.0
PID, FILM_TASK = "p_96efdc03e1aa", "t_d0a54bdf1810"
V9 = ROOT / "projects" / PID / "output" / "{}_draft.mp4".format(FILM_TASK)
TARGET_HOLD_S = 25.0                        # 6-C H3 的切分目标（沿用其注册参数，若可读）

# ---------------------------------------------------------------- 只读取数
con = sqlite3.connect("file:{}?mode=ro".format(DB.as_posix()), uri=True)
con.row_factory = sqlite3.Row
con.execute("PRAGMA query_only=ON")
rows = [dict(r) for r in con.execute(
    "select artifact_id, task_id, type, path from artifacts where project_id=? order by created_at",
    (PID,))]
con.close()


def load(rec):
    p = Path(rec["path"])
    return json.loads((p if p.is_absolute() else ROOT / p).read_text(encoding="utf-8"))


def latest(t, task=None):
    lst = [r for r in rows if r["type"] == t]
    x = next((y for y in lst if task and y["task_id"] == task), lst[-1] if lst else None)
    return (load(x), x) if x else ({}, None)


script, s_rec = latest("script_output")
voice, v_rec = latest("voice_output")
render, r_rec = latest("render_output", FILM_TASK)
segs = script.get("segments") or []
vsegs = voice.get("segments") or []
timeline = render.get("material_timeline") or []
m6c = json.loads((LOGS / "phase6c_batch.json").read_text(encoding="utf-8"))
m3 = json.loads((LOGS / "phase6b_m3_proposals_v9.json").read_text(encoding="utf-8"))
r2 = json.loads((LOGS / "phase6e_round2.json").read_text(encoding="utf-8"))

actual = [float(s.get("duration_s") or 0.0) for s in vsegs]
n = len(actual)
sum_actual = round(sum(actual), 6)
audio_time_base = round(sum_actual + PAUSE * max(n - 1, 0) + TRAILING, 3)
declared = [max(float(s.get("duration_s") or 0.0), 3.0) for s in segs]
declared_base = round(sum(declared) + TRAILING, 3)

# ---------------------------------------------------------------- 1) 21 段 remapping
table, cd, ca = [], 0.0, 0.0
for i in range(n):
    d, a = declared[i], actual[i]
    w0 = round(ca, 3)
    pause_i = PAUSE if i < n - 1 else TRAILING
    w1 = round(w0 + a + pause_i, 3)
    tw = timeline[i] if i < len(timeline) else {}
    sa = (tw.get("selected_asset") or {})
    table.append({
        "index": i, "scene_id": tw.get("scene_id") or "S{:02d}".format(i + 1),
        "old_declared_window_s": [round(cd, 3), round(cd + d, 3)],
        "old_timeline_window_s": [tw.get("start_s"), tw.get("end_s")],
        "actual_tts_duration_s": round(a, 3),
        "pause_budget_s": round(pause_i, 3),
        "new_audio_window_s": [w0, round(w0 + a, 3)],
        "new_timeline_window_s": [w0, w1],
        "cumulative_position_s": w0,
        "old_to_new_offset_s": round(w0 - cd, 3),
        "timeline_delta_s": round((w1 - w0) - (float(tw.get("end_s") or 0)
                                              - float(tw.get("start_s") or 0)), 3),
        "asset": {"asset_id": sa.get("asset_id"), "name": (sa.get("name") or sa.get("title")),
                  "license_class": sa.get("license_class"), "fallback_state": tw.get("fallback_state"),
                  "appearance_mode": tw.get("appearance_mode") or tw.get("material_mode")},
        "text_head": str(segs[i].get("narration") or "")[:24],
    })
    cd += d
    ca = w1

# ---------------------------------------------------------------- 2) 字幕窗口（v1 vs v2）
payload = [{"narration": s.get("narration", ""), "duration_s": s.get("duration_s")} for s in segs]
cues_v1 = core_captions.build_cues(payload)
plan = N.narration_plan(script, voice, config={"editing": {"narration_pause_budget_s": PAUSE}})
cues_v2 = core_captions.build_cues(payload, windows=plan["segments"])
sub = {
    "chars_per_sec": core_captions.CHARS_PER_SEC,
    "v1": {"cues": len(cues_v1), "first_start_s": cues_v1[0]["start"] if cues_v1 else None,
           "last_end_s": cues_v1[-1]["end"] if cues_v1 else None},
    "v2": {"cues": len(cues_v2), "first_start_s": cues_v2[0]["start"] if cues_v2 else None,
           "last_end_s": cues_v2[-1]["end"] if cues_v2 else None},
    "v2_alignment": N.subtitle_alignment(cues_v2, plan),
    "v1_alignment": N.subtitle_alignment(cues_v1, plan),
    "per_scene_cues_v2": [{"scene_id": t["scene_id"],
                           "cues": len([c for c in cues_v2 if c["segment_index"] == i]),
                           "window_s": round(t["new_timeline_window_s"][1]
                                             - t["new_timeline_window_s"][0], 3)}
                          for i, t in enumerate(table)],
}

# ---------------------------------------------------------------- 3) 每场时长 / 素材占比 / 指标
per_scene = []
for t in table:
    w = t["new_timeline_window_s"]
    per_scene.append({"scene_id": t["scene_id"], "duration_s": round(w[1] - w[0], 3),
                      "asset_id": t["asset"]["asset_id"], "asset_name": t["asset"]["name"]})
asset_share = {}
for s in per_scene:
    key = s["asset_name"] or "(solid/placeholder)"
    asset_share[key] = round(asset_share.get(key, 0.0) + s["duration_s"], 3)
for k in asset_share:
    asset_share[k] = {"duration_s": asset_share[k],
                      "share": round(asset_share[k] / audio_time_base, 4)}
durs = [s["duration_s"] for s in per_scene]
metrics = {
    "new_production_duration_s": audio_time_base,
    "sum_actual_tts_s": sum_actual,
    "pause_total_s": round(PAUSE * max(n - 1, 0), 3),
    "trailing_pad_s": TRAILING,
    "old_declared_time_base_s": declared_base,
    "duration_reduction_s": round(declared_base - audio_time_base, 3),
    "duration_reduction_ratio": round((declared_base - audio_time_base) / declared_base, 4),
    "scene_count": n,
    "scene_duration_min_s": round(min(durs), 3), "scene_duration_mean_s": round(sum(durs) / n, 3),
    "scene_duration_max_s": round(max(durs), 3),
    "scene_change_density_per_min": round(n / (audio_time_base / 60.0), 3),
    "static_hold": {"mean_hold_s": round(sum(durs) / n, 3), "max_hold_s": round(max(durs), 3),
                    "scenes_over_25s": [s["scene_id"] for s in per_scene if s["duration_s"] > 25.0]},
    "asset_share": asset_share,
    "max_asset_share": round(max(v["share"] for v in asset_share.values()), 4),
    "unique_assets": len([k for k in asset_share if k != "(solid/placeholder)"]),
    "note": "以上为**规划期推算**（基于既有 TTS 时长 + DCv2 pause budget）；"
            "**不**代表 DQ-1..DQ-8 判定（DQ 需成片后实测，且本阶段不重制）。",
    "sensitivity_pause_budget": {str(p): round(sum_actual + p * (n - 1) + TRAILING, 3)
                                 for p in (0.0, 0.25, 0.5, 0.75, 1.0, 1.5)},
}

# ---------------------------------------------------------------- 4) 旧 proposal 迁移状态
_reg = core_revision.load_register(LOGS / "phase6e_proposal_register_r2.jsonl")


def win_of(pid_label):
    """取**生效版本**：若该 label 存在 v2（append-only 取代版本），以 v2 为准。"""
    v2 = next((x for x in _reg if str(x.get("label", "")).startswith(pid_label)
               and x.get("version") == 2), None)
    if v2 is not None:
        return v2
    return next((x for x in r2["proposals"] if x["label"].startswith(pid_label)), None)


def new_window_for_scenes(scene_ids):
    idx = [t["index"] for t in table if t["scene_id"] in scene_ids]
    if not idx:
        return None
    return [table[min(idx)]["new_timeline_window_s"][0], table[max(idx)]["new_timeline_window_s"][1]]


def old_window_for_scenes(scene_ids):
    idx = [t["index"] for t in table if t["scene_id"] in scene_ids]
    if not idx:
        return None
    return [table[min(idx)]["old_timeline_window_s"][0], table[max(idx)]["old_timeline_window_s"][1]]


directorial = []
for label, scenes, note in (("E1", ["S21"], "片尾卡（add_outro_card）"),
                            ("E2", ["S05"], "可检视性信息图（add_visual_aid）"),
                            ("E3", ["S11"], "Lean/mathlib 视觉（add_visual_aid）"),
                            ("E4", ["S08", "S09", "S10"], "开普勒信息面板（add_visual_aid）"),
                            ("E5", ["S13", "S14"], "形式化验证面板（add_visual_aid）")):
    p = win_of(label)
    ow = old_window_for_scenes(scenes)
    nw = new_window_for_scenes(scenes)
    directorial.append({
        "label": p["label"] if p else label, "proposal_id": p["proposal_id"] if p else None,
        "proposal_sha256": core_revision and __import__("video_studio.core.execution",
                                                         fromlist=["x"]).proposal_sha256(p)
        if p else None,
        "semantic": note, "scenes": scenes,
        "old_proposal_window_s": (p["affected_scope"]["window"] if p else None),
        "old_scene_window_s": ow, "new_scene_window_s": nw,
        "new_duration_s": (round(nw[1] - nw[0], 3) if nw else None),
        "old_duration_s": (round(ow[1] - ow[0], 3) if ow else None),
        "window_offset_s": (round(nw[0] - ow[0], 3) if (nw and ow) else None),
        "reuse_old_window": False,
        "status": "MIGRATABLE_WITH_RETARGET（设计与语义可迁移，坐标必须按新时基重算）",
    })

split_map = {}
for p in m3["proposals"]:
    if p["label"].startswith("H3"):
        split_map[p["label"]] = p
split_analysis = []
for label, p in split_map.items():
    scenes = (p.get("affected_scope") or {}).get("scenes") or []
    for sid in scenes:
        t = next((x for x in table if x["scene_id"] == sid), None)
        if not t:
            continue
        old_len = (float(t["old_timeline_window_s"][1]) - float(t["old_timeline_window_s"][0]))
        new_len = t["new_timeline_window_s"][1] - t["new_timeline_window_s"][0]
        old_k = int(old_len // TARGET_HOLD_S) + (1 if old_len % TARGET_HOLD_S > 1e-6 else 0)
        new_k = int(new_len // TARGET_HOLD_S) + (1 if new_len % TARGET_HOLD_S > 1e-6 else 0)
        split_analysis.append({
            "proposal": label, "scene_id": sid, "old_scene_len_s": round(old_len, 3),
            "new_scene_len_s": round(new_len, 3),
            "old_sub_scenes": old_k, "new_sub_scenes": new_k,
            "old_cuts_s": [round(float(t["old_timeline_window_s"][0]) + old_len / old_k * i, 3)
                           for i in range(1, old_k)],
            "new_cuts_s": [round(t["new_timeline_window_s"][0] + new_len / new_k * i, 3)
                           for i in range(1, new_k)],
            "still_needed": bool(new_k > 1),
            "verdict": ("CUTS_INVALIDATED（旧切点坐标失效，需按新窗口重算）" if old_k != new_k
                        else "CUTS_RECALCULATED（子镜数不变，坐标全变）"),
        })

proposal_status = [
    {"proposal": "H7-outro-card / E1", "scenes": ["S21"], "class": "可迁移（需重定位）",
     "why": "语义（末镜补片尾卡 + 显式字体）与窗口无关；但 [1465,1532] 失效，须用新 S21 窗口；"
            "字体修复本身可移植（`ops.execution.exec_add_outro_card` v2 已支持 font_file）"},
    {"proposal": "H3a/H3b（长镜切分）", "scenes": "6-C 指定场景", "class": "必须重新 proposal",
     "why": "切点由旧窗口长度推导；新窗口长度全变（如 S07 95→65.7s）⇒ 子镜数与切点坐标均需重算，"
            "且部分场景可能不再需要切分"},
    {"proposal": "H5（池内换材）", "scenes": ["S05", "S11", "S18"], "class": "部分失效（需重新选材）",
     "why": "选材依赖 narration 语义（可复用）与窗口长度（已变）；S05/S11 的旧选材（IMO 合影）"
            "已被人工否决，重制时不得沿用 ⇒ 必须重新 proposal/重新选材"},
    {"proposal": "H2（素材池多样性）", "scenes": "全片", "class": "可迁移（与窗口无关）",
     "why": "依赖素材池数量与许可，不依赖时间基；仍需人工提供合格素材（否则保持 PENDING）"},
    {"proposal": "H4（依赖 H3a）", "scenes": "-", "class": "失效（依赖链需重建）",
     "why": "H4 依赖 H3a 的执行结果；H3a 必须重新 proposal ⇒ H4 需重新评估依赖"},
    {"proposal": "E2（S05 信息图）", "scenes": ["S05"], "class": "设计可迁移（坐标必须重算）",
     "why": "设计语义（可检视性阶梯/转述状态/文献元数据/两种立场）与时长无关；"
            "但旧 [245,300] 失效，须改绑新 S05 实际窗口；spec_source 哈希绑定需重新登记"},
    {"proposal": "E3（S11 视觉）", "scenes": ["S11"], "class": "设计可迁移（坐标必须重算）",
     "why": "同上；且 E3 尚未知是否有真实素材需求（当前 HOLD）"},
    {"proposal": "E4（S08–S10 面板）", "scenes": ["S08", "S09", "S10"], "class": "设计可迁移（跨镜窗口缩短）",
     "why": "旧 480–690s（210s）→ 新窗口显著缩短；信息槽数量与可读时间需重新核算"},
    {"proposal": "E5（S13–S14 面板）", "scenes": ["S13", "S14"], "class": "设计可迁移（跨镜窗口缩短）",
     "why": "同上；并需重新核对 S16 口径一致性（内容不变，窗口变）"},
    {"proposal": "C1–C4（6-C 候选成片）", "scenes": "-", "class": "全部失效（必须重制）",
     "why": "候选本身建立在旧时基（含 570.3s 静音与字幕漂移）⇒ 不能作为重制后的基线或参照交付物"},
]

# ---------------------------------------------------------------- 5) E2 设计可迁移性（阅读时间）
e2 = win_of("E2")
spec_text_chars = 0
plan_json = json.loads((ROOT / "docs" / "regression_2x" / "phase6e_materials" /
                        "phase6e_material_plan.json").read_text(encoding="utf-8"))
for pnl in plan_json["items"]["E2"]["C_self_made_spec"]["panels"]:
    spec_text_chars += len(pnl["title"]) + sum(len(x) for x in pnl["content"])
s05 = next(t for t in table if t["scene_id"] == "S05")
s05_win = s05["new_timeline_window_s"]
e2_migration = {
    "design_semantics_kept": ["可检视程度阶梯", "转述状态（本片当前状态）", "两篇文献元数据（含 DOI）",
                              "两种立场（转述，不引原文）"],
    "coordinate_migration": "FORBIDDEN（不得沿用 [245,300]）",
    "new_target_window_s": s05_win, "new_display_duration_s": round(s05_win[1] - s05_win[0], 3),
    "old_display_duration_s": 55.0,
    "readable_chars_estimate": spec_text_chars,
    "min_reading_time_s_at_chars_per_sec": round(spec_text_chars
                                                 / float(core_captions.CHARS_PER_SEC), 2),
    "feasible": bool(spec_text_chars / float(core_captions.CHARS_PER_SEC)
                     <= (s05_win[1] - s05_win[0])),
    "note": "面板为**常显信息层**（非逐字阅读），但若人工按字幕阅读速度估算，"
            "所需时间须 ≤ 新窗口；不足时应减少槽位或延展到相邻镜头（需人工裁定）",
}

# ---------------------------------------------------------------- 6) rebuild scope
minimal = {
    "name": "最小重制范围（保结构）",
    "keep": ["21 镜结构与素材选择（除被否决素材）", "旁白 TTS 音频（事实来源）",
             "E1 片尾卡字体修复（可移植）", "E2/E3/E4/E5 的**设计语义**"],
    "change": ["timeline 由 audio_time_base 派生", "time-line/字幕/BGM ducking 重算",
               "E1 outro 重定位到新 S21", "E2 信息图重定位到新 S05（spec_source 重新登记）",
               "渲染全片（视频/字幕/音轨）"],
    "not_included": ["H3a/H3b 重新切分", "H5 重新选材", "E3/E4/E5 执行", "baseline/tag 重切"],
    "expected_total_s": audio_time_base,
    "risk": "旧切分坐标与新窗口不匹配（若沿用在旧坐标上做的切分，会导致切点落在错误位置）",
}
full = {
    "name": "完整重制范围（重规划）",
    "keep": ["旁白 TTS 音频", "事实核查证据链", "历史产物作为参考"],
    "change": ["最小范围全部 + H3a/H3b 按新窗口重新切分（重新 proposal + 重新审批）",
               "H5 重新选材（含被否决素材替换）", "E2/E3/E4/E5 按新窗口重新登记/审批/执行",
               "镜头窗口与素材 in/out、运动时长重新布局", "重切新 baseline/tag（需人工授权）"],
    "not_included": ["重录 TTS", "重下素材", "修改历史 artifact"],
    "expected_total_s": audio_time_base,
    "risk": "内容覆盖率随时长下降 36% ⇒ 需人工确认叙事密度/是否扩写脚本",
}

# ---------------------------------------------------------------- 7) 风险与待人工确认
imo_scenes = [t["scene_id"] for t in table
              if (t["asset"] or {}).get("asset_id") == "asset_432cd85be6f1"]
risks = [
    {"id": "R0", "risk": "资产政策：IMO 合影（asset_432cd85be6f1）在 v9 中并非只在 S05/S11",
     "detail": {"v9_in_use_scenes": imo_scenes,
                  "share": (metrics["asset_share"].get("Matematička gimnazija - Mathematical "
                                                        "Gymnasium Belgrade - MGB - IMO 2010 - pic3.jpg")
                             or {}).get("share"),
                  "human_ban_scope": "人工否决的是把它作为 aS05/aS11 的**替代素材**；S13–S16 在 v9 中本就是它在用"},
     "need_human": "重制时 S13–S16 是否继续使用该素材（涉及 E5 窗口底层画面与署名/许可台账）"},
    {"id": "R1", "risk": "新 production duration 取决于 pause budget 选择",
     "detail": metrics["sensitivity_pause_budget"], "need_human": "确认 pause_budget_s（默认 0.75）"},
    {"id": "R2", "risk": "全片时长下降 {}%（{}s → {}s）".format(
        round(metrics["duration_reduction_ratio"] * 100, 1), declared_base, audio_time_base),
     "detail": "镜头变短、信息密度上升、节奏变快；叙事完整性需人工确认", "need_human": "是否扩写脚本或接受缩短"},
    {"id": "R3", "risk": "旧切分/换材/叠加窗口坐标全部失效",
     "detail": "H3a/H3b 切点、H5 选材、E1–E5 窗口均需按新时基重算", "need_human": "是否授权重新 proposal"},
    {"id": "R4", "risk": "DQ-3/DQ-4 等指标将显著变化（镜头更短、切点更多）",
     "detail": "本阶段只给推算值，**不**宣称 DQ PASS", "need_human": "重制后需实测复核"},
    {"id": "R5", "risk": "E4/E5 跨镜信息面板的可用展示时间缩短",
     "detail": "E4 旧 210s → 新窗口 {}s；E5 旧 150s → 新 {}s".format(
         round(new_window_for_scenes(["S08", "S09", "S10"])[1]
               - new_window_for_scenes(["S08", "S09", "S10"])[0], 1),
         round(new_window_for_scenes(["S13", "S14"])[1]
               - new_window_for_scenes(["S13", "S14"])[0], 1)),
     "need_human": "信息槽数量/可读性是否仍成立"},
    {"id": "R6", "risk": "素材是否仍可用（部分素材时长/比例假设基于旧窗口）",
     "detail": "仍为静帧/卡片为主，但运动（Ken Burns）时长需按新窗口重算", "need_human": "确认素材可复用"},
    {"id": "R7", "risk": "重制会产生与历史候选不同的成片 ⇒ 历史证据链如何归档",
     "detail": "v9/C1–C4/E1/E2 保留为历史 artifact（不改动）；新片为新产物", "need_human": "归档与命名策略"},
]

plan_out = {
    "schema": "phase6f-rebuild-plan-v1", "stage": "6-F",
    "note": "**只读规划**：未重制、未生成 MP4、未调用 ffmpeg、未修改 v9/C1–C4/E1/E2/DB/baseline、未执行 E3–E5、未 promote。",
    "inputs": {"project_id": PID, "film_task": FILM_TASK,
               "voice_artifact": v_rec["artifact_id"] if v_rec else None,
               "render_artifact": r_rec["artifact_id"] if r_rec else None,
               "narration_truth": "现有真实 TTS（不重录）",
               "pause_budget_s": PAUSE, "trailing_pad_s": TRAILING},
    "production_duration": {
        "formula": "audio_time_base = Σ actual_tts_duration + pause_budget×(n−1) + trailing_pad",
        "sum_actual_tts_s": sum_actual, "n_segments": n,
        "pause_budget_s": PAUSE, "pause_total_s": round(PAUSE * (n - 1), 3),
        "trailing_pad_s": TRAILING,
        "NEW_PRODUCTION_DURATION_S": audio_time_base,
        "NOT_just_narration_truth": "narration truth 是 {}s；生产时长还必须加上段间停顿预算与收尾 ⇒ {}s".format(
            sum_actual, audio_time_base),
    },
    "remapping_21_segments": table,
    "new_production_timeline": [
        {"scene_id": t["scene_id"], "start_s": t["new_timeline_window_s"][0],
         "end_s": t["new_timeline_window_s"][1],
         "narrative_window_s": t["new_audio_window_s"],
         "pause_after_s": t["pause_budget_s"]} for t in table],
    "subtitles": sub,
    "ducking_windows_v2": [{"scene_id": t["scene_id"], "start_s": t["new_audio_window_s"][0],
                            "end_s": t["new_audio_window_s"][1],
                            "duck_target_db": -26.0, "bed_db": -20.0,
                            "ramp_ms": 300} for t in table],
    "scene_material_inout": [
        {"scene_id": t["scene_id"], "asset": t["asset"], "old_window_s": t["old_timeline_window_s"],
         "new_window_s": t["new_timeline_window_s"],
         "required_display_s": round(t["new_timeline_window_s"][1]
                                     - t["new_timeline_window_s"][0], 3),
         "action": "复用素材（按新窗口重算运动/静止时长；视频素材需核对可用长度）"}
        for t in table],
    "metrics_estimate": metrics,
    "directorial_retargeting": directorial,
    "six_c_split_reanalysis": split_analysis,
    "proposal_migration_status": proposal_status,
    "e2_design_migration": e2_migration,
    "rebuild_scopes": {"minimal": minimal, "full": full,
                       "selection": "NOT_CHOSEN（由人工决定，本阶段不自行选择）"},
    "risks_and_human_decisions": risks,
    "invariants": {"v9_unchanged": True, "c1_c4_unchanged": True, "e1_e2_unchanged": True,
                   "db_unchanged": True, "baseline_tag_unchanged": True,
                   "e3_e4_e5_not_executed": True, "ffmpeg_invocations": 0,
                   "mp4_generated": 0, "promoted": False},
}
plan_out["plan_sha256"] = hashlib.sha256(
    json.dumps({k: v for k, v in plan_out.items() if k != "plan_sha256"}, sort_keys=True,
               ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()
OUT.write_text(json.dumps(plan_out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")

print("== 新 production duration ==")
print("  Σ actual TTS            : {} s".format(sum_actual))
print("  + pause {}×{} 段间     : {} s".format(PAUSE, n - 1, round(PAUSE * (n - 1), 3)))
print("  + trailing              : {} s".format(TRAILING))
print("  = **audio_time_base**   : **{} s**（旧声明时基 {} s，缩短 {} s / {}%）".format(
    audio_time_base, declared_base, metrics["duration_reduction_s"],
    round(metrics["duration_reduction_ratio"] * 100, 1)))
print("  灵敏度(pause=0/0.5/1.0): {}".format(
    {k: v for k, v in metrics["sensitivity_pause_budget"].items() if k in ("0.0", "0.5", "1.0")}))
print("\n== 21 段 remapping（前 6 + 末 3）==")
for t in table[:6] + table[-3:]:
    print("  {} old {} → new {} (actual {:.3f}s + pause {:.2f}) 偏移 {:+.1f}s".format(
        t["scene_id"], t["old_timeline_window_s"], t["new_timeline_window_s"],
        t["actual_tts_duration_s"], t["pause_budget_s"], t["old_to_new_offset_s"]))
print("\n== 导演决策重定位 ==")
for d in directorial:
    print("  {} {} → {}（新时长 {}s，偏移 {:+.1f}s）".format(
        d["label"][:28], d["old_scene_window_s"], d["new_scene_window_s"], d["new_duration_s"],
        d["window_offset_s"] or 0.0))
print("\n== 6-C 切分重算（前 5）==")
for s in split_analysis[:5]:
    print("  {} {} 旧 {:.1f}s/{}子镜 → 新 {:.1f}s/{}子镜  {}".format(
        s["proposal"][:16], s["scene_id"], s["old_scene_len_s"], s["old_sub_scenes"],
        s["new_scene_len_s"], s["new_sub_scenes"], s["verdict"][:22]))
print("\n== 指标推算（不宣称 DQ PASS）==")
print("  镜数 {} | 时长 min/mean/max {}/{}/{} s | 换镜密度 {}/min | >25s 场景 {}".format(
    metrics["scene_count"], metrics["scene_duration_min_s"], metrics["scene_duration_mean_s"],
    metrics["scene_duration_max_s"], metrics["scene_change_density_per_min"],
    metrics["static_hold"]["scenes_over_25s"]))
print("  最大素材占比 {} | 唯一素材 {}".format(metrics["max_asset_share"],
                                            metrics["unique_assets"]))
print("  字幕 v1 末条 {}s → v2 末条 {}s | v2 对齐 ok={}".format(
    sub["v1"]["last_end_s"], sub["v2"]["last_end_s"], sub["v2_alignment"]["ok"]))
print("  E2 可迁移: 语义保留 / 新窗口 {} / 需阅读 {:.2f}s ≤ 窗口 {}s ⇒ {}".format(
    e2_migration["new_target_window_s"], e2_migration["min_reading_time_s_at_chars_per_sec"],
    e2_migration["new_display_duration_s"], e2_migration["feasible"]))
print("\nplan ->", OUT)
