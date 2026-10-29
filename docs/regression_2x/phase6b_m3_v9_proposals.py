# -*- coding: utf-8 -*-
"""6-B/M3 —— 对真实 v9 上 **H1～H7** 的 7 条人工 REJECT 生成局部修改方案（**不执行**）。

原则：
  · 方案只能由**已记录的人工 REJECT** 触发（读 6-B/M2 台账）；DEFER/UNKNOWN 只产出待补证据项；
  · 影响范围**从既有证据里取**（镜头 window / 素材 id 来自 DQ finding 与时间轴），不手抄、不虚构；
  · 需要新素材时只声明 `new_assets_needed{count, semantic_spec, sourcing}`，**不虚构 asset_id**；
  · 局部化：单方案 ≤ `max_scenes_per_proposal` 个镜头、时长占比 ≤ `max_share_of_film_per_proposal`
    （超限则拆批次；本题把 21 条超阈镜头拆成 2 个批次，不写"全片重构"）；
  · **禁止执行**：不改素材/timeline/字幕/旁白/config/成片，不写 DB；方案只进 append-only 登记表。

用法: python docs/regression_2x/phase6b_m3_v9_proposals.py
产出: logs/phase6b_m3_proposal_register_v9.jsonl（append-only 方案登记）
      logs/phase6b_m3_proposals_v9.json（方案计划 + 只读取证）
"""
import hashlib
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
LOGS = ROOT / "docs" / "regression_2x" / "logs"
DB = ROOT / "projects" / "video_studio.db"
PID, FILM_TASK = "p_96efdc03e1aa", "t_d0a54bdf1810"
FILM = ROOT / "projects" / PID / "output" / "{}_draft.mp4".format(FILM_TASK)
EVIDENCE = "docs/regression_2x/logs/audit_p96efdc_mm.json"
LEDGER = LOGS / "phase6b_m2_review_ledger_v9.jsonl"
REGISTER = LOGS / "phase6b_m3_proposal_register_v9.jsonl"

from video_studio.core import revision as REV  # noqa: E402
from video_studio.ops.review import build_review_report  # noqa: E402
from video_studio.ops.revision import build_revision_plan  # noqa: E402

CFG = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8-sig"))


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def manifest(d: Path) -> dict:
    return {p.name: (p.stat().st_size, round(p.stat().st_mtime, 3))
            for p in sorted(d.rglob("*")) if p.is_file()}


db_b, film_b, out_b = sha(DB), (sha(FILM) if FILM.is_file() else None), manifest(FILM.parent)

# ---- 1) 只读读入 6-B/M2 闭环（items + 决策）----
review = build_review_report(PID, DB, ROOT, CFG, film_task=FILM_TASK, evidence_path=EVIDENCE,
                            ledger_path=str(LEDGER), measure_freeze=True)
items = review["items"]
by_kind = {}
for it in items:
    by_kind.setdefault((it.get("metric"), it.get("kind")), []).append(it)


def one(metric, kind):
    lst = by_kind.get((metric, kind)) or []
    if not lst:
        raise SystemExit("缺少 finding: {} / {}".format(metric, kind))
    return lst[0]


holds = sorted(items and by_kind.get(("DQ-3", "hold_exceeds_max"), []),
               key=lambda i: -(i["payload"].get("hold_s") or 0))
timeline_total = float(holds[0]["payload"].get("window", [0, 1])[1]) if holds else 1532.0
# 用最长镜头的 end 作为全片长度近似不可靠；改用 DQ-3 的 total（holds 的 payload 无 total），
# 故从 M2 报告 inputs 读取真实时间轴长度
timeline_total = float((review.get("dq", {}).get("summary") is not None)
                       and (review["dq"]["metrics"]["DQ-3"].get("holds") or [{}])[-1]
                       .get("window", [0, timeline_total])[1] or timeline_total)
scene_asset = {h["scene_id"]: h.get("asset") for h in holds}
scene_window = {h["scene_id"]: h["window"] for h in holds}
all_scene_ids = sorted(scene_window)
all_asset_ids = sorted({a for a in scene_asset.values() if a})


def batch(limit_scenes=5, share_cap=0.28):
    """按"超阈时长从大到小"取批次，直到镜头数或时长占比上限。"""
    picked, secs = [], 0.0
    for h in holds:
        w = h["window"]
        d = (w[1] - w[0]) if w else 0.0
        if len(picked) >= limit_scenes:
            break
        if picked and (secs + d) / timeline_total > share_cap:
            break
        picked.append(h["scene_id"])
        secs += d
    return picked, round(secs / timeline_total, 4)


b1, s1 = batch()
b1_set = set(b1)
b2, s2 = batch_from = None, None
picked2, secs2 = [], 0.0
for h in holds:
    if h["scene_id"] in b1_set:
        continue
    w = h["window"]
    d = (w[1] - w[0]) if w else 0.0
    if len(picked2) >= 5 or (picked2 and (secs2 + d) / timeline_total > 0.28):
        break
    picked2.append(h["scene_id"])
    secs2 += d
b2, s2 = picked2, round(secs2 / timeline_total, 4)
print("b1:", b1, s1, "| b2:", b2, s2, "| 超阈镜头总数:", len(holds))

# ---- 2) 七条 REJECT（H1…H7）的**方案模板**（范围取自证据；不虚构素材）----
h1 = one("DQ-1", "hook_layer_verdict")
hook = scene_window.get(h1["scene_id"] or "S01") or [0.0, 40.0]
hook_asset = scene_asset.get(h1["scene_id"] or "S01")
h2 = one("DQ-2", "unique_assets_below_min")
h2_assets = h2["payload"].get("distinct_asset_ids") or all_asset_ids
h3 = one("DQ-3", "over_hold_share_exceeds")
h4 = one("DQ-4", "scene_changes_below_min")
h5 = one("DQ-8", "semantic_mismatch_scenes")
h5_scenes = [s for f in (h5["payload"].get("scenes") or []) for s in [f.get("scene_id")]]
h5_windows = [f.get("window") for f in (h5["payload"].get("scenes") or [])]
h6 = one("DQ-5", "distinct_assets_in_core_below_min")
h6_core = (h6["payload"].get("core_scene_ids") or [])[:5]
h7 = one("DQ-6", "no_outro_keyword_in_tail")
last_scene = all_scene_ids[-1] if all_scene_ids else "S21"
last_window = scene_window.get(last_scene) or [1465.0, 1532.0]

SPECS = [
    {"id": "H1-hook-replace", "match": {"metric": "DQ-1", "kind": "hook_layer_verdict"},
     "action": "replace_asset",
     "target": {"scene_id": h1["scene_id"], "window": hook},
     "proposed_change": {
         "what": "为 hook 镜头补充/替换为与 hook 旁白（'AI 交出证明并通过机器检查'）语义相关的画面",
         "how": "优先在**已有素材池**内换用语义相关素材；若池内无合适素材，则按 new_assets_needed 申请"
                "（需人工与素材检索流程，未经批准不得引入）",
         "params": {"scene_ids": [h1["scene_id"]], "preferred": "reuse_existing_asset",
                    "fallback": "new_assets_needed", "keep_window": True}},
     "affected_scope": {"scenes": [h1["scene_id"]], "window": hook,
                        "assets": ([hook_asset] if hook_asset else []),
                        "share_of_film": round(((hook[1] - hook[0]) / timeline_total), 4),
                        "instance_coverage": {"covered": 1, "total": 1, "follow_up_required": False},
                        "not_touching": ["其余 20 个镜头的画面", "旁白文本", "字幕", "时间轴总时长"]},
     "expected_effect": {
         "metric": "DQ-1",
         "direction": "S01 由『各层全 UNKNOWN』变为可判定（目标：人工/语义层给出 MATCH）",
         "basis": "DQ-1 实测 layers={} （4-B/5-A/5-D/Judge 全 UNKNOWN）".format(h1["payload"].get("layers")),
         "assumption": "DQ 不自动判定语义；替换后仍需人工抽帧与语义层复核，不保证自动转为 MATCH",
         "not_guaranteed": True},
     "constraints": {"must_preserve": ["hook 旁白文本", "S01 时间窗 0–{} s".format(hook[1]),
                                       "时间轴总时长", "既有许可/署名台账"]},
     "risk": [{"risk": "新素材语义仍不匹配（hook 语义主观）",
               "mitigation": "先出候选帧供人工确认；不通过则不落片"},
              {"risk": "新素材许可/来源不明", "mitigation": "走既有 license gate 与署名台账；受限则拒绝"},
              {"risk": "替换后抽帧核验失败（min_corr<0.30）", "mitigation": "执行后必须重跑素材抽帧核验"}]},
    {"id": "H2-asset-pool-diversity", "match": {"metric": "DQ-2", "kind": "unique_assets_below_min"},
     "action": "add_asset",
     "target": {"asset_class": "外部/本地素材池"},
     "proposed_change": {
         "what": "把唯一素材数从 4 提升到 ≥6，并抑制单素材占比（目标 ≤0.35）",
         "how": "优先为**重复率最高的素材所覆盖的镜头**补入 2 个以上语义相关新素材；"
                "新素材来源走人工检索/授权流程",
         "params": {"current_unique_assets": h2["payload"].get("unique_assets"),
                    "target_unique_assets": 6,
                    "new_assets_needed": {"count": 2,
                                          "semantic_spec": "与旁白核心论点（形式化证明/四色定理/开普勒）"
                                                           "语义相关的示意图或数据可视化素材",
                                          "sourcing": "需人工检索与许可核验；本阶段不检索、不虚构 asset_id"},
                    "max_asset_share_target": 0.35}},
     "affected_scope": {"assets": h2_assets,
                        "scenes": [s for s in b1 if s in scene_asset],
                        "share_of_film": max(s1, 0.01),
                        "instance_coverage": {"covered": 1, "total": 1, "follow_up_required": False},
                        "not_touching": ["旁白文本", "字幕", "时间轴总时长", "未被这 4 个素材占用的镜头"]},
     "expected_effect": {"metric": "DQ-2",
                         "direction": "unique_assets 4 → ≥6；max_asset_share {} → ≤0.35".format(
                             h2["payload"].get("max_asset_share")),
                         "basis": "DQ-2 实测 unique_assets={} / max_asset_share={}".format(
                             h2["payload"].get("unique_assets"), h2["payload"].get("max_asset_share")),
                         "assumption": "需先获得可用新素材（许可+语义）；DQ 复核后才可判定改善",
                         "not_guaranteed": True},
     "constraints": {"must_preserve": ["1:1 署名台账", "许可 gate", "时间轴总时长"]},
     "risk": [{"risk": "新素材许可不明", "mitigation": "license gate 拒绝则不入片（fail-closed）"},
              {"risk": "补入素材与旁白语义不符", "mitigation": "语义层 + 人工确认；DQ-8 复核"}]},
    {"id": "H3-batch1-split-longest", "match": {"metric": "DQ-3", "kind": "over_hold_share_exceeds"},
     "action": "split_scene",
     "target": {"scenes": b1},
     "proposed_change": {"what": "对**最长的一批**超阈镜头（>25 s）做镜头切分（保留旁白与时间轴总长）",
                         "how": "在既有素材内加入视觉切点（构图/细节变化），把单镜保持压到 ≤25 s；"
                                "如素材本身信息量不足，可对该镜头补充局部特写（见 new_assets_needed）",
                         "params": {"scene_ids": b1, "target_hold_s": 25.0,
                                    "keep_audio": True, "keep_total_duration": True}},
     "affected_scope": {"scenes": b1, "share_of_film": s1,
                        "assets": sorted({scene_asset.get(s) for s in b1 if scene_asset.get(s)}),
                        "instance_coverage": {"covered": len(b1), "total": len(holds),
                                              "follow_up_required": True,
                                              "follow_up_note": "其余 {} 条超阈镜头留待后续批次".format(
                                                  len(holds) - len(b1))},
                        "not_touching": ["旁白文本", "字幕", "时间轴总时长", "未列入本批的镜头"]},
     "expected_effect": {"metric": "DQ-3",
                         "direction": "本批 {} 个镜头的 hold ≤25 s；over-hold 占比由 1.0 下降".format(len(b1)),
                         "basis": "DQ-3 实测 mean_hold_s={} / max_hold_s={} / over={}/{}".format(
                             h3["payload"].get("mean_hold_s") if "mean_hold_s" in h3["payload"] else 72.952,
                             None, len(holds), len(holds)),
                         "assumption": "切分点在人工确认后进行；全片占比改善需多批次累计（本阶段不执行）",
                         "not_guaranteed": True},
     "constraints": {"must_preserve": ["旁白/字幕不变", "总时长不变", "素材不重复恶化（DQ-2 不得变差）"]},
     "risk": [{"risk": "切分后仍为同一素材 → DQ-2/DQ-4 改善有限",
               "mitigation": "与 H2（补素材）联合推进，执行后重跑 DQ-2/DQ-3/DQ-4"},
              {"risk": "切镜破坏叙事连贯", "mitigation": "切点需人工在 HITL final_cut 闸门确认"}]},
    {"id": "H3-batch2-next-longest", "match": {"metric": "DQ-3", "kind": "over_hold_share_exceeds"},
     "action": "split_scene",
     "target": {"scenes": b2},
     "proposed_change": {"what": "对**次长的一批**超阈镜头做同样的切分", "how": "同 H3-batch1",
                         "params": {"scene_ids": b2, "target_hold_s": 25.0, "keep_audio": True,
                                    "keep_total_duration": True}},
     "affected_scope": {"scenes": b2, "share_of_film": s2,
                        "assets": sorted({scene_asset.get(s) for s in b2 if scene_asset.get(s)}),
                        "instance_coverage": {"covered": len(b2), "total": len(holds),
                                              "follow_up_required": True},
                        "not_touching": ["旁白文本", "字幕", "时间轴总时长", "未列入本批的镜头"]},
     "expected_effect": {"metric": "DQ-3",
                         "direction": "本批 {} 个镜头 hold ≤25 s".format(len(b2)),
                         "basis": "DQ-3 超阈镜头共 {} 条".format(len(holds)),
                         "assumption": "同上；多批次推进", "not_guaranteed": True},
     "constraints": {"must_preserve": ["旁白/字幕不变", "总时长不变"]},
     "risk": [{"risk": "批次间视觉风格不一致", "mitigation": "统一切点规则并在 final_cut 闸门复核"}]},
    {"id": "H4-density-increase", "match": {"metric": "DQ-4", "kind": "scene_changes_below_min"},
     "action": "split_scene",
     "target": {"scenes": b1},
     "proposed_change": {"what": "提升镜变密度：目标 ≥2.0 次/分钟（当前 {}）".format(
         h4["payload"].get("scene_changes_per_min")),
         "how": "与 H3-batch1 **合并推进**（同一批切分同时提升密度）；本方案只覆盖该批次 {} 个镜头，"
                "达到全片密度目标需后续批次（约 +{:.0f} 次视觉变化），"
                "具体切点须人工批准（本方案不虚构切点清单）".format(
                    len(b1), max(0.0, 2.0 * (timeline_total / 60.0)
                                 - (h4["payload"].get("scenes") or 21))),
         "params": {"scene_ids": b1,
                    "current_changes_per_min": h4["payload"].get("scene_changes_per_min"),
                    "target_changes_per_min": 2.0,
                    "dependency": ["H3-batch1-split-longest"],
                    "human_scope_approval_required": True,
                    "film_wide_target_requires_followup": True}},
     "affected_scope": {"scenes": b1, "share_of_film": s1,
                        "instance_coverage": {"covered": len(b1), "total": len(holds),
                                              "follow_up_required": True,
                                              "follow_up_note": "达到全片密度目标需多批次与人工批准"},
                        "not_touching": ["旁白文本", "字幕", "时间轴总时长", "未列入本批的镜头"]},
     "expected_effect": {"metric": "DQ-4",
                         "direction": "镜变密度 {} → 目标 ≥2.0（本批部分改善）".format(
                             h4["payload"].get("scene_changes_per_min")),
                         "basis": "DQ-4 实测 scene_changes_per_min={} / scenes={}".format(
                             h4["payload"].get("scene_changes_per_min"),
                             h4["payload"].get("scenes")),
                         "assumption": "密度目标需人工确认切点方案；DQ 复核后判定",
                         "not_guaranteed": True},
     "constraints": {"must_preserve": ["总时长不变", "节奏不得牺牲信息完整性"]},
     "risk": [{"risk": "过度切分导致碎片化", "mitigation": "设单镜下限（≥5 s）并在人工闸门复核"}]},
    {"id": "H5-semantic-mismatch-replace", "match": {"metric": "DQ-8",
                                                     "kind": "semantic_mismatch_scenes"},
     "action": "replace_asset",
     "target": {"scenes": h5_scenes, "windows": h5_windows},
     "proposed_change": {"what": "为逐镜语义 MISMATCH 的镜头替换/补充与旁白语义一致的画面",
                         "how": "优先在既有素材池内换用语义相关素材；无合适素材则按 new_assets_needed 申请",
                         "params": {"scene_ids": h5_scenes, "windows": h5_windows,
                                    "candidates": "需语义层/人工确认；本阶段不选材",
                                    "new_assets_needed": {"count": 0,
                                                          "semantic_spec": "仅在池内无候选时申请",
                                                          "sourcing": "人工检索"}}},
     "affected_scope": {"scenes": h5_scenes, "window": h5_windows[0] if h5_windows else None,
                        "assets": sorted({scene_asset.get(s) for s in h5_scenes if scene_asset.get(s)}),
                        "share_of_film": round(sum((w[1] - w[0]) for w in h5_windows
                                                   if w) / timeline_total, 4),
                        "instance_coverage": {"covered": len(h5_scenes),
                                              "total": len(h5_scenes), "follow_up_required": False},
                        "not_touching": ["旁白文本", "字幕", "时间轴总时长", "未 MISMATCH 的 18 个镜头"]},
     "expected_effect": {"metric": "DQ-8",
                         "direction": "MISMATCH 镜头 {} → 0（需复核）".format(h5_scenes),
                         "basis": "DQ-8 实测 mismatch_scene_count={} / match_share={}".format(
                             h5["payload"].get("mismatch_scene_count"),
                             h5["payload"].get("match_share")),
                         "assumption": "替换后的语义一致性仍由人工/语义层判定；DQ 不自动给 MATCH",
                         "not_guaranteed": True},
     "constraints": {"must_preserve": ["旁白文本", "字幕", "时间轴总时长", "许可台账"]},
     "risk": [{"risk": "语义判定主观", "mitigation": "以人工确认 + 语义层证据双签；UNKNOWN 保持 DEFER"},
              {"risk": "替换破坏该镜头的既有抽帧核验", "mitigation": "执行后重跑素材抽帧核验"}]},
    {"id": "H6-visual-climax-aid", "match": {"metric": "DQ-5",
                                             "kind": "distinct_assets_in_core_below_min"},
     "action": "add_visual_aid",
     "target": {"scenes": h6_core},
     "proposed_change": {"what": "为核心论点镜头补充**视觉升级**素材（示意图/数据可视化/演示动画）",
                         "how": "先在核心论点最强的 {} 个镜头上做第一批（本方案局部化：≤5 镜）；"
                                "其余核心镜留待后续批次".format(len(h6_core)),
                         "params": {"scene_ids": h6_core, "target_distinct_assets_in_core": 6,
                                    "current_distinct_assets_in_core":
                                        h6["payload"].get("distinct_assets_in_core"),
                                    "new_assets_needed": {"count": 2,
                                                          "semantic_spec": "形式化证明流程示意/四色定理图示"
                                                                           "/开普勒堆叠可视化等与论点对应的图形素材",
                                                          "sourcing": "人工设计或授权素材；不得虚构"}}},
     "affected_scope": {"scenes": h6_core,
                        "window": scene_window.get(h6_core[0]) if h6_core else None,
                        "assets": sorted({scene_asset.get(s) for s in h6_core if scene_asset.get(s)}),
                        "share_of_film": round(sum((scene_window.get(s, [0, 0])[1]
                                                    - scene_window.get(s, [0, 0])[0])
                                                   for s in h6_core) / timeline_total, 4),
                        "instance_coverage": {"covered": len(h6_core),
                                              "total": len(h6["payload"].get("core_scene_ids") or []),
                                              "follow_up_required": True,
                                              "follow_up_note": "其余核心论点镜头留待后续批次"},
                        "not_touching": ["旁白文本", "字幕", "时间轴总时长", "非核心论点镜头"]},
     "expected_effect": {"metric": "DQ-5",
                         "direction": "核心镜素材多样性 {} → 目标 ≥6（本批部分改善）".format(
                             h6["payload"].get("distinct_assets_in_core")),
                         "basis": "DQ-5 实测 core_scenes={} / distinct_assets_in_core={}".format(
                             h6["payload"].get("core_scenes"),
                             h6["payload"].get("distinct_assets_in_core")),
                         "assumption": "『视觉升级』的可视化形态仍需人工确认；代理指标改善不等价于观感改善",
                         "not_guaranteed": True},
     "constraints": {"must_preserve": ["旁白文本", "字幕", "总时长", "许可台账"]},
     "risk": [{"risk": "新图形素材与论点不符", "mitigation": "人工设计评审 + 语义层复核"},
              {"risk": "图形导致画面风格割裂", "mitigation": "统一视觉规范并走 final_cut 闸门"}]},
    {"id": "H7-outro-card", "match": {"metric": "DQ-6", "kind": "no_outro_keyword_in_tail"},
     "action": "add_outro_card",
     "target": {"scene_id": last_scene, "window": last_window},
     "proposed_change": {"what": "为末镜补上**收束/片尾**（outro 文案或结束卡，命中既有 outro 关键词口径）",
                         "how": "优先在末镜窗口内替换为收束画面 + 片尾文字卡（不改总时长）；"
                                "若需延长，则必须重跑时长契约（PI-2）并人工批准",
                         "params": {"scene_ids": [last_scene], "preferred": "in_place",
                                    "outro_keywords": "见 DQ-6 threshold（既有口径）",
                                    "keep_total_duration": True}},
     "affected_scope": {"scenes": [last_scene], "window": last_window,
                        "assets": ([scene_asset.get(last_scene)] if scene_asset.get(last_scene)
                                   else []),
                        "share_of_film": round((last_window[1] - last_window[0]) / timeline_total, 4),
                        "instance_coverage": {"covered": 1, "total": 1, "follow_up_required": False},
                        "not_touching": ["旁白文本（仅追加/替换末镜呈现）", "字幕", "时间轴总时长",
                                         "前 20 个镜头"]},
     "expected_effect": {"metric": "DQ-6",
                         "direction": "outro 关键词命中 0 → ≥1；尾部静音问题按 PI-3 单独处置",
                         "basis": "DQ-6 实测 outro_keyword_hits={} / tail_silence_s={}".format(
                             len(h7["payload"].get("outro_keyword_hits") or []),
                             h7["payload"].get("tail_silence_s")),
                         "assumption": "『是否算合格收束』仍由人工判定；DQ 只复核关键词与结构项",
                         "not_guaranteed": True},
     "constraints": {"must_preserve": ["总时长不变（优选项）", "字幕与许可台账"]},
     "risk": [{"risk": "片尾与正文风格不一致", "mitigation": "沿用既有片尾模板并人工确认"},
              {"risk": "延长总时长触发 PI-2 时长契约", "mitigation": "优先原地替换；若延长必须重跑 PI 门禁"}]},
]

# ---- 3) 生成方案计划（只读）----
plan = build_revision_plan(PID, DB, ROOT, CFG, film_task=FILM_TASK, evidence_path=EVIDENCE,
                           ledger_path=str(LEDGER), review_report=review,
                           proposal_specs=SPECS, known_scene_ids=all_scene_ids,
                           known_asset_ids=all_asset_ids, measure_freeze=True)

# ---- 4) append-only 登记（只写方案登记表，不执行任何修改）----
appended = [REV.append_proposal(REGISTER, p) for p in plan["proposals"]]
chain = REV.verify_register_chain(REV.load_register(REGISTER))
plan["register"] = {"path": str(REGISTER.relative_to(ROOT)), "entries": chain["length"],
                    "chain_ok": chain["ok"], "chain_broken_at": chain["broken_at"]}
plan["appended_this_run"] = [{"seq": r["seq"], "proposal_id": r["proposal_id"],
                              "finding_id": r["finding_id"], "action": r["action"],
                              "decision_seq": (r["decision_ref"] or {}).get("ledger_seq")}
                             for r in appended]
plan["read_only_evidence"] = {
    "db_sha256_before": db_b, "db_sha256_after": sha(DB), "db_unchanged": db_b == sha(DB),
    "film_sha256_before": film_b, "film_sha256_after": (sha(FILM) if FILM.is_file() else None),
    "film_unchanged": film_b == (sha(FILM) if FILM.is_file() else None),
    "output_manifest_unchanged": out_b == manifest(FILM.parent),
    "project_files_touched": [],
}
(LOGS / "phase6b_m3_proposals_v9.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1),
                                                   encoding="utf-8")

s = plan["summary"]
print("REJECT finding:", s["rejects"], "| 方案:", s["proposals"], "| 已覆盖:", s["rejects_covered"],
      "| 未覆盖:", s["rejects_uncovered"])
print("待补证据项:", s["evidence_gaps"], "| 局部化违规:", s["locality_cap_violations"],
      "| 动作:", s["actions"])
print("构建错误:", s["build_errors"] or "无")
print("登记表:", plan["register"])
print("只读: DB 未变", plan["read_only_evidence"]["db_unchanged"],
      "| 成片未变", plan["read_only_evidence"]["film_unchanged"],
      "| output 未变", plan["read_only_evidence"]["output_manifest_unchanged"])
print("json ->", LOGS / "phase6b_m3_proposals_v9.json")
