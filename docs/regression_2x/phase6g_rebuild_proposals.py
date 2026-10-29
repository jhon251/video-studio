# -*- coding: utf-8 -*-
"""6-G —— **Rebuild Proposal Preparation**（只生成 proposal package，**禁止执行**）。

人工决策（本轮，逐条落实）：D1=0.75s｜D2=接受 978.656s（先做小样）｜D3=不扩写脚本｜
D4=S01/S13–S16 暂留 IMO 合影（重复度风险单列）｜D5=重新 proposal H3a/H3b｜D6=重新 proposal H5
（S05/S11 禁用已否决的 IMO 合影）｜D7=E2 采用方案 C（重新设计信息图）｜D8=E4/E5 重新 proposal 后再定槽位｜
D9=E1 placement=新 S21 最后 12s｜D10=完整重制｜D11=暂不切 baseline/tag｜D12=不改 DQ 实现。

生成：只**新写** `docs/regression_2x/logs/phase6g_rebuild_proposals.json`
（不写登记链、不改 DB、不调用 ffmpeg、不生成 MP4/candidate、不下载素材、不重录 TTS、不执行任何提案）。

治理路径：凡存在**人工 REJECT finding** 的对象，一律通过冻结的 `core.revision.make_proposal` 重新生成
`revision-proposal-v1`（绑定原 finding_id + 原 REJECT 决策 entry_sha256），窗口/切点全部按 DCv2 新时基重算。
"""
import hashlib
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
from video_studio.core import execution as EX                        # noqa: E402
from video_studio.core import human_review as HR                     # noqa: E402
from video_studio.core import revision as core_revision              # noqa: E402
from video_studio.core import visual_aid as VA                       # noqa: E402

LOGS = ROOT / "docs" / "regression_2x" / "logs"
MAT = ROOT / "docs" / "regression_2x" / "phase6e_materials"
P2 = LOGS / "phase6f_rebuild_plan_v2.json"
M2 = LOGS / "phase6b_m2_review_ledger_v9.jsonl"
M3 = LOGS / "phase6b_m3_proposals_v9.json"
R6 = LOGS / "phase6e_review_ledger_r2.jsonl"
OUT = LOGS / "phase6g_rebuild_proposals.json"
PAUSE = 0.75
TARGET_HOLD_S = 25.0
D = {"D1": "pause_budget=0.75s", "D2": "accept 978.656s + 先做小样验证节奏", "D3": "不扩写脚本",
     "D4": "S01/S13–S16 暂留 IMO 合影（重复度风险单列）", "D5": "重新 proposal H3a/H3b",
     "D6": "重新 proposal H5（S05/S11 禁用已否决的 IMO 合影）", "D7": "E2 采用方案 C（重新设计）",
     "D8": "E4/E5 重新 proposal 后再定槽位", "D9": "E1 placement=新 S21 最后 12s",
     "D10": "完整重制", "D11": "暂不切新 baseline/tag", "D12": "保持当前 DQ-4 实现"}

p2 = json.loads(P2.read_text(encoding="utf-8"))
chain = p2["remapping_21_segments"]
P2_SHA = p2["plan_sha256"]
by_scene = {c["scene_id"]: c for c in chain}
m3 = json.loads(M3.read_text(encoding="utf-8"))["proposals"]
m3_by_label = {p["label"]: p for p in m3}
m2 = [json.loads(x) for x in M2.read_text(encoding="utf-8").splitlines() if x.strip()]
m2_by_fid = {}
for e in m2:
    m2_by_fid.setdefault(e["finding_id"], e)
r6 = [json.loads(x) for x in R6.read_text(encoding="utf-8").splitlines() if x.strip()]
r6_by_fid = {e["finding_id"]: e for e in r6}


def win(scene_ids):
    idx = [c["index"] for c in chain if c["scene_id"] in scene_ids]
    return [chain[min(idx)]["new_timeline_window_s"][0], chain[max(idx)]["new_timeline_window_s"][1]]


PROD = p2["math_verification"]["production_duration_s"]


def span_share(scene_ids):
    """受影响**内容时长**占比 = Σ(受影响场景新窗口) / 生产时长（避免用首尾凸包夸大范围）。"""
    tot = sum(by_scene[s]["new_timeline_window_s"][1] - by_scene[s]["new_timeline_window_s"][0]
              for s in scene_ids)
    return round(tot / PROD, 4)


def scene_windows(scene_ids):
    return [{"scene_id": s, "window_s": by_scene[s]["new_timeline_window_s"]}
            for s in scene_ids]


def trace(scene_ids):
    return {"dcv2_plan": str(P2.relative_to(ROOT)), "dcv2_plan_sha256": P2_SHA,
            "dcv2_math_checks": p2["math_verification"]["all_pass"],
            "remapping_rows": [{"scene_id": c["scene_id"], "old_window_s": c["old_timeline_window_s"],
                                "new_window_s": c["new_timeline_window_s"],
                                "actual_tts_s": c["actual_tts_duration_s"]}
                               for c in chain if c["scene_id"] in scene_ids],
            "production_duration_s": p2["math_verification"]["production_duration_s"]}


# ---------------------------------------------------------------- H3 新切分计划（INVALID 旧切点）
def split_grid(scene_ids, target=TARGET_HOLD_S):
    rows = []
    for sid in scene_ids:
        c = by_scene[sid]
        w0, w1 = c["new_timeline_window_s"]
        dur = round(w1 - w0, 3)
        k = int(dur // target) + (1 if dur % target > 1e-6 else 0)
        k = max(k, 1)
        d = dur / k
        subs = []
        for i in range(k):
            s0 = round(w0 + d * i, 3)
            s1 = round(w0 + d * (i + 1), 3) if i < k - 1 else round(w1, 3)
            subs.append({"sub_id": "{}-{}".format(sid, chr(ord('a') + i)),
                         "window_s": [s0, s1], "duration_s": round(s1 - s0, 3)})
        old_w = c["old_timeline_window_s"]
        old_dur = round(float(old_w[1]) - float(old_w[0]), 3)
        old_k = int(old_dur // target) + (1 if old_dur % target > 1e-6 else 0)
        rows.append({"scene_id": sid,
                     "old_window_s": old_w, "old_duration_s": old_dur,
                     "old_cuts_s": [round(float(old_w[0]) + old_dur / old_k * i, 3)
                                    for i in range(1, old_k)],
                     "old_sub_scenes": old_k,
                     "new_window_s": [w0, w1], "new_duration_s": dur,
                     "new_cuts_s": [round(w0 + d * i, 3) for i in range(1, k)],
                     "new_sub_scenes": k, "sub_scenes": subs,
                     "reason": "旧切点基于旧时基（窗口 {:.1f}s 推导）⇒ **INVALID**；新窗口 {:.1f}s 需 {} 个子镜"
                               "（target_hold_s={}）".format(old_dur, dur, k, target)})
    return {"target_hold_s": target, "scenes": rows,
            "total_sub_scenes": sum(r["new_sub_scenes"] for r in rows),
            "old_cuts_invalidated": True}


h3a_scenes = m3_by_label["H3-batch1-split-longest"]["affected_scope"]["scenes"]
h3b_scenes = m3_by_label["H3-batch2-next-longest"]["affected_scope"]["scenes"]
grid_a, grid_b = split_grid(h3a_scenes), split_grid(h3b_scenes)

# 未授权但必须披露：21/21 场景 > 25s ⇒ 若严格执行 25s 规则，全片都需切分
filmwide = [c["scene_id"] for c in chain
            if c["scene_id"] not in (h3a_scenes + h3b_scenes)
            and round(c["new_timeline_window_s"][1] - c["new_timeline_window_s"][0], 3) > TARGET_HOLD_S]


# ---------------------------------------------------------------- proposals（走 make_proposal）
proposals, blocks = [], []


def build(label, finding_id, entries, action, action_target, what, how, params, scope,
          expected, constraints, risk, discriminator, decision_note, rebuild_note):
    finding = entries["finding"]
    dec = entries["decision"]
    rec = core_revision.make_proposal(
        finding, dec, action, action_target,
        {"what": what, "how": how, "params": params}, scope, expected,
        constraints=constraints, risk=risk,
        known_scene_ids=[c["scene_id"] for c in chain],
        known_asset_ids=["asset_432cd85be6f1", "asset_3f0b94a3f2ac", "asset_cfae038f6106",
                         "asset_30dd89a16713", "asset_23e71bc8a864"],
        discriminator=discriminator, label=label,
        evidence_refs=[str(P2.relative_to(ROOT)), "docs/regression_2x/logs/phase6f_rebuild_plan.json"])
    rec["rebuild"] = {"stage": "6-G", "decision_refs": decision_note, "note": rebuild_note,
                      "replaces_old_window": True,
                      "old_proposal": {"label": rebuild_note.get("old_label"),
                                       "window": rebuild_note.get("old_window")},
                      "lineage": trace(scope["scenes"])}
    rec["governance"] = {"finding_id": finding_id,
                         "decision_entry_sha256": dec.get("entry_sha256"),
                         "registered": False,
                         "registration_note": "本阶段只生成 package；正式登记（新登记链）在执行授权阶段进行"}
    return rec


def entries_for(finding_id):
    if finding_id not in r6_by_fid:
        raise KeyError("finding {} 不在 6-E 审片台账".format(finding_id))
    e = r6_by_fid[finding_id]
    if e.get("decision") != "REJECT":
        raise ValueError("finding {} 不是 REJECT".format(finding_id))
    return {"finding": e, "decision": e}


def entries_m2(finding_id):
    e = m2_by_fid.get(finding_id)
    if not e or e.get("decision") != "REJECT":
        raise ValueError("M2 finding {} 缺失或非 REJECT".format(finding_id))
    return {"finding": e, "decision": e}


# ---- H3a / H3b（split_scene，重算切点）----
h3_fid = m3_by_label["H3-batch1-split-longest"]["finding_id"]
for label, grid, scenes, disc in (("H3a-rebuild-split-longest", grid_a, h3a_scenes, "6g-h3a"),
                                  ("H3b-rebuild-split-next-longest", grid_b, h3b_scenes, "6g-h3b")):
    proposals.append(build(
        label, h3_fid, entries_m2(h3_fid), "split_scene",
        {"scenes": scenes, "window": win(scenes)},
        "在 DCv2 新时基上重新切分该批长镜（旧切点全部作废）",
        "按 target_hold_s={} 在新窗口内**均分**子镜；保留旁白/字幕/总时长/音轨；逐场景给出子镜窗口".format(
            TARGET_HOLD_S),
        {"scene_ids": scenes, "target_hold_s": TARGET_HOLD_S, "keep_audio": True,
         "keep_total_duration": True, "new_split_plan": grid, "old_cuts_invalidated": True,
         "dcv2_plan_sha256": P2_SHA},
        {"scenes": scenes, "window": win(scenes), "assets": [],
         "share_of_film": span_share(scenes), "windows": scene_windows(scenes),
         "not_touching": ["旁白文本", "字幕文本", "时间轴总时长", "其它镜头", "历史 artifact（v9/C1–C4/E1/E2）"]},
        {"metric": "DQ-3 静态保持 / DQ-4 视觉密度", "direction": "新窗口内子镜 ≤ {}s".format(TARGET_HOLD_S),
         "basis": "DCv2 remapping：{}".format("; ".join(
             "{}({:.1f}s→{}子镜)".format(r["scene_id"], r["new_duration_s"], r["new_sub_scenes"])
             for r in grid["scenes"])),
         "assumption": "切分不改变旁白/字幕/时长；DQ 判定需成片后实测", "not_guaranteed": True},
        {"must_preserve": ["旁白文本", "字幕文本", "时间轴总时长", "历史 artifact 不变"],
         "target_hold_s": TARGET_HOLD_S},
        ["子镜过短可能造成节奏碎片化（需人工看片）",
         "与 E3（S11）等叠加层窗口存在结构耦合"],
        disc, [k for k in ("D5", "D10", "D12")],
        {"old_label": m3_by_label["H3-batch1-split-longest" if disc == "6g-h3a"
                                  else "H3-batch2-next-longest"]["label"],
         "old_window": [by_scene[s]["old_timeline_window_s"] for s in scenes]}))

# ---- H5（replace_asset，S05/S11；新素材方案，不绑定、不下载）----
h5_fid = m3_by_label["H5-semantic-mismatch-replace"]["finding_id"]
h5_scenes = ["S05", "S11"]
h5_spec = {
    "S05": {"semantic_spec": "与『引文/表述可否被逐字检视（surveyability）』**直接相关**的真实素材："
                             "①论文/期刊版面（可读）；②逐字核对/标注重合示意；③概念图。"
                             "**不得**使用 IMO/竞赛合影。",
            "sourcing": "人工检索（Wikimedia/开放期刊版面/PD 或 CC BY）+ 许可核验；本阶段**不下载、不绑定**",
            "forbidden_material": [{"asset_id": "asset_432cd85be6f1", "why": "人工明确否决作为 aS05 替代素材"}]},
    "S11": {"semantic_spec": "与『Lean / mathlib / 形式化证明』**直接相关**的真实素材："
                             "①Lean/mathlib 源码或页面截图（含可辨识定理/策略关键字）；②proof state/goal 面板示意；"
                             "③形式化依赖图或验证流程示意。**不得**使用 IMO/竞赛合影。",
            "sourcing": "人工检索（开源项目页面/文档，遵循其许可）+ 许可核验；本阶段**不下载、不绑定**",
            "forbidden_material": [{"asset_id": "asset_432cd85be6f1", "why": "人工明确否决作为 aS11 替代素材"}]},
}
proposals.append(build(
    "H5-rebuild-semantic-replace", h5_fid, entries_m2(h5_fid), "replace_asset",
    {"scenes": h5_scenes, "window": win(h5_scenes)},
    "在 DCv2 新时基上为 S05/S11 重新提出**候选素材方案**（不含 IMO 合影）",
    "先由人工检索并提供真实素材 + 许可核验，再绑定；本阶段只给出 semantic_spec/sourcing 与禁止项",
    {"scene_ids": h5_scenes,
     "new_assets_needed": {"count": 2, "per_scene": h5_spec, "asset_id": None,
                           "binding": "PENDING_HUMAN_ASSET（本阶段不绑定、不下载）"},
     "dcv2_windows": {s: by_scene[s]["new_timeline_window_s"] for s in h5_scenes},
     "retain": {"S18": {"asset_id": "asset_cfae038f6106",
                        "why": "6-E 人审 ACCEPT（verified_positive_keep）⇒ 保留，不在本次替换范围"}}},
    {"scenes": h5_scenes, "window": win(h5_scenes), "assets": [],
     "share_of_film": span_share(h5_scenes), "windows": scene_windows(h5_scenes),
     "not_touching": ["旁白文本", "字幕文本", "时间轴总时长", "S18 的既有选材", "历史 artifact"]},
    {"metric": "DQ-8 逐镜语义支撑", "direction": "S05/S11 由语义不匹配 → 与旁白论点直接对应",
     "basis": "6-E 人审 REJECT（引文可检视性 / Lean-mathlib 语义不匹配）",
     "assumption": "语义达成需人工与语义层复核；本阶段不承诺 MATCH", "not_guaranteed": True},
    {"must_preserve": ["旁白文本", "字幕文本", "时间轴总时长", "许可/署名台账"],
     "forbid": ["asset_432cd85be6f1 作为 S05/S11 替代素材"]},
    ["素材许可不清 ⇒ 退回人工（不得先用后补）", "与 H3b（S11 切分）窗口耦合",
     "素材可读性/分辨率需人工确认"],
    "6g-h5", [k for k in ("D6", "D10")],
    {"old_label": "H5-semantic-mismatch-replace", "old_window": [[245.0, 300.0], [690.0, 770.0]]}))

# ---- E1（add_outro_card；placement = 新 S21 最后 12s）----
e1_fid = r6[0]["finding_id"]
s21 = by_scene["S21"]
e1_window = [round(s21["new_timeline_window_s"][1] - 12.0, 3), s21["new_timeline_window_s"][1]]
assert e1_window == [966.656, 978.656], e1_window
proposals.append(build(
    "E1-rebuild-outro-last12s", e1_fid, entries_for(e1_fid), "add_outro_card",
    {"scene_id": "S21", "window": e1_window},
    "片尾卡重新绑定到新 S21，placement 固定为**最后 12 s**",
    "在新 S21 的 [966.656, 978.656] 内重渲染片尾卡（保留显式字体修复），窗口外按母版复制、音轨流复制",
    {"scene_ids": ["S21"], "window": e1_window, "placement": "LAST_12S",
     "font_file": "msyh.ttc", "fontsdir": "C:/Windows/Fonts", "reuse_subtitle_font": True,
     "text": "感谢观看　我们下期再见", "keep_total_duration": True, "keep_position_and_size": True,
     "requires": "drawtext 需限定时间窗（enable=between(...)）或独立末段重编码",
     "dcv2_plan_sha256": P2_SHA},
    {"scenes": ["S21"], "window": e1_window, "assets": [],
     "share_of_film": span_share(["S21"]), "windows": scene_windows(["S21"]),
     "not_touching": ["旁白文本", "字幕文本", "时间轴总时长", "S21 前 38.8s 的画面", "历史 artifact"]},
    {"metric": "DQ-6 片尾完整性（结构项）", "direction": "片尾卡仅出现在最后 12 s",
     "basis": "6-E 人审 REJECT（豆腐块）+ D9 决策（P-B）",
     "assumption": "字体文件存在且覆盖字形；12 s 足以读完两行文案", "not_guaranteed": True},
    {"must_preserve": ["旁白文本", "字幕文本", "时间轴总时长", "音轨为母版流复制"],
     "placement": "LAST_12S", "fail_closed": "字体缺失 ⇒ 原样保留并回报"},
    ["与 DQ-6 的『末镜更换』口径需复核（片尾卡只覆盖末 12s）",
     "若执行器不支持 enable= 时间窗，需要最小实现改动"],
    "6g-e1", [k for k in ("D9", "D10")],
    {"old_label": "E1-outro_card_missing_cjk_glyphs", "old_window": [1465.0, 1532.0]}))

# ---- E2（方案 C：重新设计信息图；新 spec，不复用旧 spec/坐标）----
e2_fid = r6[1]["finding_id"]
e2_window = by_scene["S05"]["new_timeline_window_s"]
e2_spec = {
    "schema": VA.SCHEMA, "layout": "panel_columns",
    "no_external_assets": True, "forbid_verbatim_quotes": True,
    "panels": [{
        "id": "P1", "title": "本片的可检视程度（示意）", "kind": "ladder",
        "items": ["未核对原文", "转述（本片当前状态）", "逐字核对", "机器可逐步复核"],
        "source": "本片 S05 旁白（转述声明）",
        "source_label": "来源：本片 S05 旁白"}],
    "origin": {"compiled_from": "6-G option C redesign", "kept_from_old":
               ["可检视程度阶梯（4 级）", "转述状态（本片当前状态）高亮"],
               "dropped_from_old": ["两篇文献元数据面板（P2）", "两种立场面板（P3）"],
               "drop_reason": "D7=方案 C：40.086s 窗口内按阅读速度（5 字/秒）最多约 200 字；"
                              "文献元数据与两立场改由旁白/字幕承担，避免信息过载"},
    "sources": ["本片 S05 旁白"],
    "must_not": ["不使用 IMO/竞赛合影", "不复用旧 [245,300] 坐标", "不复用旧 spec/哈希",
                 "不出现西文双引号引语"]}
VA.verify_spec(e2_spec)
proposals.append(build(
    "E2-rebuild-visual-aid-redesign", e2_fid, entries_for(e2_fid), "add_visual_aid",
    {"scene_id": "S05", "window": e2_window},
    "按方案 C **重新设计** S05 信息图（不沿用旧坐标与旧 spec）",
    "以**内联 spec**（`params.visual_aid`）渲染单面板信息层：阶梯 + 当前状态高亮；"
    "文献元数据与两立场交给旁白/字幕",
    {"scene_ids": ["S05"], "window": e2_window, "visual_aid": e2_spec,
     "design_option": "C（重新设计）", "old_spec_reused": False, "old_coordinate_reused": False,
     "inline_spec": True, "dcv2_plan_sha256": P2_SHA},
    {"scenes": ["S05"], "window": e2_window, "assets": [],
     "share_of_film": span_share(["S05"]), "windows": scene_windows(["S05"]),
     "not_touching": ["旁白文本", "字幕文本", "时间轴总时长", "历史 artifact"]},
    {"metric": "DQ-8 逐镜语义支撑 + 人工可检视性", "direction": "单面板在 40.086s 内可读完（≤ ~200 字）",
     "basis": "D7=方案 C；旧设计 385 字需 77.0s > 窗口 40.086s",
     "assumption": "面板为常显信息层；可读性需人工确认", "not_guaranteed": True},
    {"must_preserve": ["旁白文本", "字幕文本", "时间轴总时长"],
     "overlay_safe_area": "不得进入底部 5% 字幕安全区", "no_external_assets": True},
    ["信息量下降（文献 DOI/两立场不再上屏）⇒ 需人工确认可接受",
     "spec 为内联 ⇒ 其哈希即 proposal 哈希的一部分"],
    "6g-e2", [k for k in ("D7", "D10")],
    {"old_label": "E2-v2-asset_semantically_unrelated_imo_group_photo", "old_window": [245.0, 300.0]}))
e2_spec_sha = VA.spec_sha256(e2_spec)

# ---- E3/E4/E5（重新登记；窗口按新时基；E3 与 H3b 结构耦合）----
for label, fid, scenes, disc, slot_note in (
        ("E3-rebuild-visual-aid-s11", r6[2]["finding_id"], ["S11"], "6g-e3",
         "信息槽数量按新窗口复核（D8：重新 proposal 后再定）"),
        ("E4-rebuild-visual-aid-kepler", r6[3]["finding_id"], ["S08", "S09", "S10"], "6g-e4",
         "D8：E4/E5 重新 proposal 后再决定槽位数量；本 package 只登记窗口与约束，不固定槽位数"),
        ("E5-rebuild-visual-aid-formalization", r6[4]["finding_id"], ["S13", "S14"], "6g-e5",
         "D8：同上；且 D4 决定 S13–S16 暂留 IMO 合影 ⇒ 底层画面不变，仅叠加上层")):
    w = win(scenes)
    dep = (["H3b-rebuild-split-next-longest（S11 被切分为子镜，叠加层需覆盖并入窗口）"]
           if "S11" in scenes else [])
    proposals.append(build(
        label, fid, entries_for(fid), "add_visual_aid",
        {"scenes": scenes, "window": w},
        "按 DCv2 新时基重新登记视觉辅助层（窗口重算，语义保留）",
        "沿用原设计的**语义**，窗口改为新时基；信息槽数量待 D8 决定后定稿",
        {"scene_ids": scenes, "window": w, "slot_count": "PENDING_D8", "slot_note": slot_note,
         "dcv2_plan_sha256": P2_SHA,
         "dependencies": dep},
        {"scenes": scenes, "window": w, "assets": [],
         "share_of_film": span_share(scenes), "windows": scene_windows(scenes),
         "not_touching": ["旁白文本", "字幕文本", "时间轴总时长", "历史 artifact"]},
        {"metric": "信息增量（人工可核对项数）+ DQ-3", "direction": "窗口内 ≥2–4 个可核对信息槽（待 D8）",
         "basis": "DCv2 remapping 新窗口 {:.1f}s（旧 {:.1f}s）".format(w[1] - w[0],
                                                                     {"E3": 80.0, "E4": 210.0,
                                                                      "E5": 150.0}[label[:2]]),
         "assumption": "槽位数量与可读性需人工确认", "not_guaranteed": True},
        {"must_preserve": ["旁白文本", "字幕文本", "时间轴总时长"],
         "overlay_safe_area": "不得进入底部 5% 字幕安全区", "no_external_assets": True},
        ["窗口缩短 ⇒ 可读时间下降" if label[:2] in ("E4", "E5") else "与 H3b 子镜结构耦合",
         "S13–S16 底层为 IMO 合影（D4 暂留）⇒ 素材重复度风险单列"],
        disc, [k for k in (("D8", "D4", "D10") if label[:2] in ("E4", "E5") else ("D8", "D10"))],
        {"old_label": r6[{"E3": 2, "E4": 3, "E5": 4}[label[:2]]]["kind"],
         "old_window": r6[{"E3": 2, "E4": 3, "E5": 4}[label[:2]]]["window"]}))

# ---- S18 保留记录（非 proposal）----
retention = {"schema": "retention-record-v1", "stage": "6-G", "kind": "verified_positive_keep",
             "scene_id": "S18", "asset_id": "asset_cfae038f6106",
             "human_decision": "6-E 人审 ACCEPT（hr-9e98ab2b36d2）+ D6 范围（仅 S05/S11）",
             "action": "保留既有选材；仅按新窗口 {}-{} 重算显示时长".format(
                 by_scene["S18"]["new_timeline_window_s"][0],
                 by_scene["S18"]["new_timeline_window_s"][1]),
             "no_proposal_generated": True}

# ---- H3c 建议（未授权，不作为 proposal）----
h3c_recommendation = {
    "id": "H3c-filmwide-split-remainder", "authorized": False,
    "reason": "DCv2 下 **21/21** 场景时长 > target_hold_s=25s；仅 H3a/H3b 的 9 个场景被授权重切",
    "scenes_not_covered": filmwide, "count": len(filmwide),
    "note": "若严格执行 25s 规则，其余场景也需切分；**未获授权 ⇒ 不生成 proposal**，仅登记为建议",
}

# ---- 全片素材 in/out / motion 计划（新时间轴；不生成视频）----
split_index = {}
for g in (grid_a, grid_b):
    for r in g["scenes"]:
        split_index[r["scene_id"]] = r
material_plan = []
for c in chain:
    w0, w1 = c["new_timeline_window_s"]
    sp = split_index.get(c["scene_id"])
    material_plan.append({
        "scene_id": c["scene_id"], "asset_id": c["asset"], "asset_name": c["asset_name"],
        "new_window_s": [w0, w1], "required_display_s": round(w1 - w0, 3),
        "narrative_window_s": c["new_audio_window_s"],
        "motion": {"mode": "ken_burns_or_still", "duration_s": round(w1 - w0, 3),
                   "note": "运动/静止时长 = 新窗口；视频素材需核对可用长度（不下载、不执行）"},
        "split": (None if not sp else {"sub_scenes": sp["sub_scenes"], "new_cuts_s":
                                      sp["new_cuts_s"], "old_cuts_invalidated": True}),
        "asset_policy": ("D4：暂留（IMO 合影，S01/S13–S16 在用；素材重复度风险单列）"
                         if c["asset"] == "asset_432cd85be6f1" else "沿用 v9 在用素材"),
    })

# ---- 依赖图 ----
dependencies = {
    "topological_order": ["H3a-rebuild-split-longest", "H3b-rebuild-split-next-longest",
                          "H5-rebuild-semantic-replace", "E1-rebuild-outro-last12s",
                          "E2-rebuild-visual-aid-redesign", "E3-rebuild-visual-aid-s11",
                          "E4-rebuild-visual-aid-kepler", "E5-rebuild-visual-aid-formalization"],
    "edges": [
        {"from": "H3a-rebuild-split-longest", "to": "*", "kind": "timeline_structure",
         "note": "切分改变子镜网格 ⇒ 任何窗口/叠加层都应在切分**之后**落位（或明确覆盖并入窗口）"},
        {"from": "H3b-rebuild-split-next-longest", "to": "E3-rebuild-visual-aid-s11",
         "kind": "window_structure", "note": "S11 被切为 3 子镜 ⇒ E3 叠加层需覆盖并入窗口"},
        {"from": "H5-rebuild-semantic-replace", "to": "E3-rebuild-visual-aid-s11",
         "kind": "material", "note": "S11 素材更换与叠加层同窗口 ⇒ 需先定素材再定叠加"},
        {"from": "H5-rebuild-semantic-replace", "to": "E2-rebuild-visual-aid-redesign",
         "kind": "material", "note": "S05 素材更换（PENDING_HUMAN_ASSET）⇒ 叠加层在其之上"},
        {"from": "PENDING_HUMAN_ASSET", "to": "H3/H5/E1–E5 执行", "kind": "hard_gate",
         "note": "素材未提供并核验前，H5 及其下游不得执行（fail-closed）"}],
    "independent": ["E4-rebuild-visual-aid-kepler", "E5-rebuild-visual-aid-formalization",
                    "E1-rebuild-outro-last12s"],
}

# ---- lineage / immutability ----
lineage = {
    "base_inputs": {
        "allowed": ["v9 素材集合（只读）", "script_output（只读）", "真实 TTS narration（961.656s，不重录）",
                    "DCv2 21 段 remapping（本 package 的唯一时基来源）"],
        "forbidden": ["C1–C4 / E1 / E2 候选成片作为新母片输入", "任何历史 candidate 作为渲染输入",
                      "修改历史 artifact / DB / baseline / tag"],
        "explicit": "旧 candidate **不得**作为新母片输入；新母片由 v9 素材 + 新时基 + 本 package 重新渲染产生",
    },
    "traceability": {"dcv2_plan": str(P2.relative_to(ROOT)), "dcv2_plan_sha256": P2_SHA,
                     "dcv2_math_checks_all_pass": p2["math_verification"]["all_pass"],
                     "remapping_rows": len(chain)},
    "immutability": {"v9": "unchanged", "c1_c4": "unchanged", "e1_e2_candidates": "unchanged",
                     "db": "unchanged", "baseline": "unchanged", "tags": "unchanged",
                     "existing_register": "unchanged（本 package 不写入既有登记链）"},
}

package = {
    "schema": "phase6g-rebuild-proposals-v1", "stage": "6-G",
    "state": "PROPOSALS_READY / AWAITING_EXECUTION_AUTHORIZATION",
    "human_decisions_applied": D,
    "note": "只生成 proposal package：未执行任何提案、未调用 ffmpeg、未生成 MP4/candidate、未改 DB/历史 artifact/"
            "baseline/tag、未下载素材、未重录 TTS、未改 DQ 实现、未 promote。",
    "proposals": proposals,
    "proposal_count": len(proposals),
    "split_plans": {"H3a": grid_a, "H3b": grid_b},
    "h3c_recommendation_not_authorized": h3c_recommendation,
    "retention_records": [retention],
    "material_inout_motion_plan": material_plan,
    "dependencies": dependencies,
    "lineage_and_immutability": lineage,
    "hashes": {
        "dcv2_plan_sha256": P2_SHA,
        "e2_new_spec_sha256": e2_spec_sha,
        "e1_window": e1_window,
        "proposals": [{"label": p["label"], "proposal_id": p["proposal_id"],
                       "proposal_sha256": EX.proposal_sha256(p),
                       "verify_proposal_errors": core_revision.verify_proposal(p)}
                      for p in proposals],
    },
    "human_review_points": [
        {"proposal": "H3a/H3b（重切分）", "check": ["每个场景的新子镜数与时长是否可接受",
                                                    "碎片化风险（最短子镜 {:.1f}s）".format(
                                                        min(s["duration_s"] for g in (grid_a, grid_b)
                                                            for r in g["scenes"]
                                                            for s in r["sub_scenes"])),
                                                    "H3c（未授权）是否要一并授权以覆盖其余 12 个场景"]},
        {"proposal": "H5（重新选材）", "check": ["S05/S11 的 semantic_spec 是否认可",
                                                 "素材由谁提供、许可如何核验",
                                                 "确认 S18 保留、不在替换范围"]},
        {"proposal": "E1（末 12s 片尾卡）", "check": ["[966.656, 978.656] 是否合适",
                                                      "是否需要 enable= 时间窗实现（最小改动）",
                                                      "DQ-6『末镜更换』口径是否仍满足"]},
        {"proposal": "E2（方案 C 重新设计）", "check": ["保留：可检视性阶梯 4 级 + 当前状态高亮",
                                                        "删除：文献元数据面板、两立场面板（改由旁白/字幕承担）",
                                                        "新 spec 哈希 {}（内联，随 proposal 哈希绑定）".format(
                                                            e2_spec_sha[:16]),
                                                        "可读性（≤~200 字 / 40.086s）是否接受"]},
        {"proposal": "E3/E4/E5（重新登记）", "check": ["D8：槽位数量待定 ⇒ 是否先定槽位再执行",
                                                       "E3 与 H3b 子镜结构的覆盖方式（并入窗口 vs 逐子镜）",
                                                       "E4 131.9s / E5 86.1s 的可读性",
                                                       "D4：S13–S16 沿用 IMO 合影的重复度风险是否接受"]},
        {"proposal": "全局", "check": ["是否授权执行顺序（H3 → H5 → E1/E2/E4/E5 → E3）",
                                       "小样验证（D2）范围与验收口径",
                                       "D11：暂不切 baseline/tag ⇒ 验收以人工看片为准"]},
    ],
    "next_stage_inputs_needed": ["H5 的真实素材 + 许可（人工提供）", "D8 槽位数量决策",
                                 "执行授权（逐条 APPROVE 或统一执行令）"],
}


def esha(rec):
    body = {k: v for k, v in rec.items() if k != "package_sha256"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


package["package_sha256"] = esha(package)
OUT.write_text(json.dumps(package, ensure_ascii=False, indent=1, default=str), encoding="utf-8")

print("== 6-G Rebuild Proposals ==")
for p in proposals:
    print("  {:36s} {:14s} id {:18s} sha {} verify={}".format(
        p["label"][:36], p["action"], p["proposal_id"], EX.proposal_sha256(p)[:16],
        core_revision.verify_proposal(p) or "OK"))
print("\nH3a: {} 场景 → {} 子镜 | H3b: {} 场景 → {} 子镜".format(
    len(grid_a["scenes"]), grid_a["total_sub_scenes"], len(grid_b["scenes"]),
    grid_b["total_sub_scenes"]))
print("H3c 未授权建议：其余 {} 个场景 >25s 未覆盖".format(len(filmwide)))
print("E2 新 spec sha256 {}（保留 2 要素 / 删除 2 要素）".format(e2_spec_sha[:16]))
print("E1 window {}（placement=LAST_12S）".format(e1_window))
print("依赖顺序：{}".format(" → ".join(dependencies["topological_order"][:4]) + " …"))
print("package_sha256 {}", "{}".format(package["package_sha256"][:16]))
print("state:", package["state"])
print("package ->", OUT)
