# -*- coding: utf-8 -*-
"""6-E —— **Evidence-Grounded Directorial Revision Round 2**：只生成/登记 Proposal，**禁止执行**。

输入（全部只读）：
  · 人工审片结论（本轮，逐条写入 `logs/phase6e_review_ledger_r2.jsonl`）；
  · 6-C 候选成片与执行证据（`logs/phase6c_batch.json`）——结论必须绑定具体 candidate 与 scene/window；
  · v9 母版时间轴与脚本旁白（`render_output` / `script_output`，只读）；
  · 6-B/M4-5 执行证据（`logs/phase6b_m5_v9_execution.json`）用于**跨批次重叠**声明。

硬约束（本脚本自身遵守，并由测试静态 + 运行期验证）：
  1. **不执行**：脚本内无 ffmpeg/subprocess 调用、不写任何成片；只写台账/登记/证据 JSON；
  2. 每条 proposal 绑定 [人工审片结论 → candidate → scene/window → 原始 evidence]；
  3. aS05/aS11 **禁止**继续使用已否决的 IMO 合影（asset_432cd85be6f1）作为替代素材；
  4. 「提高 CLIP 相似度」**不作为**充分依据（每条显式记录 `clip_similarity_sufficient=false`）；
  5. 新素材只声明 `semantic_spec` + `sourcing`，**不写 asset_id**；
  6. 保持 M3 局部化限制（≤6 镜 / 占比 ≤0.30）与 M5 冲突检测（含跨批次重叠**显式声明**）；
  7. DEFER/UNKNOWN 不得转成确定性修改（驱动决策必须是**可证**的 REJECT）。

用法: python docs/regression_2x/phase6e_round2_proposals.py
产出: logs/phase6e_review_ledger_r2.jsonl / logs/phase6e_proposal_register_r2.jsonl /
      logs/phase6e_round2.json
"""
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
LOGS = ROOT / "docs" / "regression_2x" / "logs"
DB = ROOT / "projects" / "video_studio.db"
PID, FILM_TASK = "p_96efdc03e1aa", "t_d0a54bdf1810"
FILM = ROOT / "projects" / PID / "output" / "{}_draft.mp4".format(FILM_TASK)
V9_SHA = "22705c7d7ea20b40d91120146066b89ab2b5fa5c1a1cab18f5346d4c66497651"
M6C = LOGS / "phase6c_batch.json"
M5_EXEC = LOGS / "phase6b_m5_v9_execution.json"
REVIEW = LOGS / "phase6e_review_ledger_r2.jsonl"
REGISTER = LOGS / "phase6e_proposal_register_r2.jsonl"
OUT = LOGS / "phase6e_round2.json"
FRAME_TOFU = "docs/regression_2x/logs/_outro_card_probe.png"
SANDBOX_OUT = ROOT / "output" / "phase6b_m4_sandbox" / "p_96efdc03e1aa_6c" / "output"

from video_studio.core import execution as EX                      # noqa: E402
from video_studio.core import human_review as HR                   # noqa: E402
from video_studio.core import revision as core_revision            # noqa: E402

IMO_ASSET = "asset_432cd85be6f1"          # 已被人审否决作为 aS05/aS11 替代素材（IMO 合影）
KEPLER_ASSET = "asset_3f0b94a3f2ac"       # Close-packed spheres（开普勒炮弹堆）
CHESS_ASSET = "asset_cfae038f6106"        # aS18 已验证正向替换（国际象棋奥赛合影）


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


# ---- 0) 只读取证基线 ----
db_b, film_b = sha(DB), sha(FILM)
sb_before = sorted((p.name, p.stat().st_size, round(p.stat().st_mtime, 3))
                   for p in SANDBOX_OUT.rglob("*") if p.is_file())

# ---- 1) 只读上下文 ----
con = sqlite3.connect("file:{}?mode=ro".format(DB.as_posix()), uri=True)
con.row_factory = sqlite3.Row
con.execute("PRAGMA query_only=ON")
rows = [dict(r) for r in con.execute(
    "select artifact_id, task_id, type, path from artifacts where project_id=? order by created_at",
    (PID,))]
con.close()
by_type = {}
for r in rows:
    by_type.setdefault(r["type"], []).append(r)


def payload(t, task=None):
    lst = by_type.get(t) or []
    rec = next((x for x in lst if task and x["task_id"] == task), lst[-1] if lst else None)
    if not rec:
        return {}
    p = Path(rec["path"])
    return json.loads((p if p.is_absolute() else ROOT / p).read_text(encoding="utf-8"))


script = payload("script_output")
render = payload("render_output", FILM_TASK)
timeline = render.get("material_timeline") or []
segs = script.get("segments") or []
narr = {e["scene_id"]: str((segs[i].get("narration") if i < len(segs) else "") or "")
        for i, e in enumerate(timeline)}
win = {e["scene_id"]: [float(e["start_s"]), float(e["end_s"])] for e in timeline}
asset_of = {e["scene_id"]: (e.get("selected_asset") or {}).get("asset_id") for e in timeline}
tl_total = float((render.get("duration_contract") or {}).get("timeline_duration_s") or 1532.0)
m6c = json.loads(M6C.read_text(encoding="utf-8"))
cand = {c["index"]: c for c in m6c["candidates"]}
cand["C1"] = cand[1]
cand["C4"] = cand[4]
h5_binding = m6c["asset_bindings"]["bindings"]
m5 = json.loads(M5_EXEC.read_text(encoding="utf-8"))
executed_c = [p for p in json.loads((LOGS / "phase6b_m3_proposals_v9.json")
                                    .read_text(encoding="utf-8"))["proposals"]
              if p["label"] in ("H3-batch1-split-longest", "H3-batch2-next-longest",
                                 "H5-semantic-mismatch-replace", "H7-outro-card")]

# ---- 2) 人工审片结论（round 2）→ 审片台账（append-only 哈希链）----
specs = [
    {"key": "E1", "kind": "outro_card_missing_cjk_glyphs", "scene": "S21",
     "window": [1465.0, 1532.0], "cand": "C1",
     "reason": "C1/C4 片尾卡的 CJK 文字渲染为豆腐块（缺字形），与同一帧 ASS 字幕中文正常形成对照",
     "evidence": {"frame": FRAME_TOFU,
                  "observation": "片尾卡显示『□□□□ □□□□□』；同帧底部 ASS 字幕中文正常 ⇒ drawtext 未显式指定 CJK 字体",
                  "root_cause": "exec_add_outro_card 的 drawtext 依赖 fontconfig 默认字体（无 CJK 覆盖）；"
                                "字幕链由 core.captions.to_ass + fontsdir 指定 Microsoft YaHei ⇒ 正常",
                  "candidate": {"film": cand[1]["film"], "sha256": cand[1]["film_sha256"]}}},
    {"key": "E2", "kind": "asset_semantically_unrelated_imo_group_photo", "scene": "S05",
     "window": [245.0, 300.0], "cand": "C4",
     "reason": "aS05 换用的 IMO 合影与『Tymoczko 引文/可检视性争论』无直接语义关系，人审否决继续使用",
     "evidence": {"current_asset": h5_binding.get("S05"), "current_asset_name": "Matematička gimnazija … IMO 2010 pic3.jpg",
                  "narr": narr.get("S05"),
                  "selection_evidence": next((x for x in m6c["asset_bindings"]["selection_evidence"]
                                              if x["scene_id"] == "S05"), {}),
                  "rejected_material": {"asset_id": IMO_ASSET, "why": "人工明确否决作为 aS05/aS11 替代素材"}}},
    {"key": "E3", "kind": "asset_semantically_unrelated_imo_group_photo", "scene": "S11",
     "window": [690.0, 770.0], "cand": "C4",
     "reason": "aS11 换用的 IMO 合影与『Lean/mathlib/形式化证明』无直接语义关系，人审否决继续使用",
     "evidence": {"current_asset": h5_binding.get("S11"), "current_asset_name": "Matematička gimnazija … IMO 2010 pic3.jpg",
                  "narr": narr.get("S11"),
                  "selection_evidence": next((x for x in m6c["asset_bindings"]["selection_evidence"]
                                              if x["scene_id"] == "S11"), {}),
                  "rejected_material": {"asset_id": IMO_ASSET, "why": "人工明确否决作为 aS05/aS11 替代素材"}}},
    {"key": "E4", "kind": "long_hold_insufficient_information", "scene": "S08,S09,S10",
     "window": [480.0, 690.0], "cand": "C4",
     "reason": "480–690s（210s）开普勒炮弹堆镜头信息量不足，人审要求**真正增加信息量**的局部方案",
     "evidence": {"narr_S08": narr.get("S08"), "narr_S09": narr.get("S09"), "narr_S10": narr.get("S10"),
                  "current_asset": KEPLER_ASSET,
                  "dq3": {"mean_hold_s": 72.952, "max_hold_s": 95.0, "source": "v9 DQ-3 实测"},
                  "note": "仅做 punch-in/构图变化（6-C 的切分方式）**不满足**本条；必须补充可核对的信息内容"}},
    {"key": "E5", "kind": "long_hold_insufficient_information", "scene": "S13,S14",
     "window": [850.0, 1000.0], "cand": "C4",
     "reason": "850–1000s（150s）IMO 合影长镜头信息量不足，人审要求真正增加信息量的局部方案",
     "evidence": {"narr_S13": narr.get("S13"), "narr_S14": narr.get("S14"),
                  "current_asset": asset_of.get("S13"),
                  "note": "该窗口仍使用 IMO 合影 **仅作为 S13/S14 的在用素材**；本条要求的是补充信息层，"
                          "不涉及 aS05/aS11 的否决规则"}},
    {"key": "K1", "kind": "verified_positive_change_keep", "scene": "S18",
     "window": [1245.0, 1330.0], "cand": "C4",
     "reason": "aS18 的素材替换经成片抽帧验证为正向（相关度 0.76，优于原素材 ≥0.59 的边距）⇒ 保留，不重复生成方案",
     "evidence": {"current_asset": h5_binding.get("S18"), "asset_name": "Slovenia Men's Team, 2024 Chess Olympiad",
                  "corr_new_mean": 0.7642, "corr_prev_mean": -0.0894,
                  "source": "logs/phase6c_batch.json → candidates[3].exec_evidence.asset_evidence.per_scene[2]"}},
]

if REVIEW.exists():
    REVIEW.unlink()
items, decisions = [], []
for s in specs:
    it = HR.human_audit_item(PID, s["kind"], s["reason"], "human:director(6-E) 审片结论（round 2）",
                            film_task=FILM_TASK, scene_id=s["scene"].split(",")[0], window=s["window"],
                            evidence=s["evidence"], unprovable=False)
    it["scene_ids"] = s["scene"].split(",")
    it["round"] = "6-E"
    items.append(it)
    dec = HR.make_decision(it, "REJECT" if s["key"] != "K1" else "ACCEPT",
                           s["reason"], "human:director(6-E)",
                           "人工审片 round 2：候选 {} 的 {} 窗口".format(s["cand"], s["window"]),
                           at="2026-10-01T00:00:00Z")
    dec = HR.append_decision(REVIEW, dec)
    decisions.append(dec)
    s["item"], s["decision"] = it, dec
rev_entries = HR.load_ledger(REVIEW)
print("审片台账:", len(rev_entries), "条 | chain_ok", HR.verify_chain(rev_entries)["ok"],
      "| 决策", [(d["finding_id"][:10], d["decision"]) for d in decisions])

by_key = {s["key"]: s for s in specs}

# ---- 3) 生成 5 条 Proposal（只登记，不执行）----
def mk(key, action, target, what, how, params, expected, risks, extra_scope=None, constraints=None):
    s = by_key[key]
    scenes = s["scene"].split(",")
    dur = s["window"][1] - s["window"][0]
    scope = {"scenes": scenes, "window": s["window"], "assets": [],       # 不写 asset_id（禁虚构）
             "share_of_film": round(dur / tl_total, 4),
             "not_touching": ["旁白文本", "字幕文本", "时间轴总时长", "其它镜头",
                              "C1–C4 现有候选成片", "素材许可/署名台账"]}
    scope.update(extra_scope or {})
    p = core_revision.make_proposal(
        s["item"], s["decision"], action, target,
        {"what": what, "how": how, "params": params}, scope, expected,
        constraints=constraints or {"must_preserve": ["旁白文本", "字幕文本", "时间轴总时长",
                                                      "既有许可/署名台账"]},
        risk=risks, known_scene_ids=list(win), known_asset_ids=[IMO_ASSET, KEPLER_ASSET,
                                                               CHESS_ASSET, "asset_30dd89a16713",
                                                               "asset_23e71bc8a864"],
        discriminator="6e-" + key.lower(), label="{}-{}".format(key, s["kind"]),
        evidence_refs=["docs/regression_2x/logs/phase6c_batch.json",
                       "docs/regression_2x/logs/phase6c_subtitle_check.json", FRAME_TOFU])
    return p


props = []
# E1 片尾卡字体修复
props.append(mk("E1", "add_outro_card", {"scene_id": "S21", "window": [1465.0, 1532.0]},
                "把 C1/C4 片尾卡的 CJK 文字改为**显式指定字体文件**渲染，消除豆腐块",
                "重渲染末镜窗口内的片尾卡：drawtext 增加 `fontfile=msyh.ttc`（与字幕链同一字体目录），"
                "文本与位置保持不变；其余视频段与母版音轨复制方式不变",
                {"font_file": "msyh.ttc", "fontsdir": "C:/Windows/Fonts",
                 "text": "感谢观看　我们下期再见", "keep_total_duration": True,
                 "keep_position_and_size": True, "reuse_subtitle_font": True},
                {"metric": "DQ-6（片尾关键词）+ 人工可读性",
                 "direction": "豆腐块 → 可读中文（不影响时长/音轨/字幕）",
                 "basis": "只读抽帧实证：{} 显示『□□□□ □□□□□』而同帧 ASS 字幕中文正常".format(FRAME_TOFU),
                 "assumption": "字体文件 msyh.ttc 在本机存在且覆盖所需字形（需执行阶段先校验）",
                 "not_guaranteed": True},
                ["若字体文件缺失 ⇒ 必须保持原状并回报人工（不得改用其它未审定字体）",
                 "重复执行可能造成窗口再编码（有损）⇒ 仅允许一次（幂等门禁）"]))
# E2 aS05 可检视性争论
props.append(mk("E2", "replace_asset", {"scene_id": "S05", "window": [245.0, 300.0]},
                "把 aS05 的 IMO 合影替换为与『可检视性争论』**直接相关**的差异化视觉",
                "在 S05 窗口内改用**新素材**（人工检索+许可核验后提供）；画面必须直接呈现"
                "『引文/表述是否可被逐字检视』这一争论对象（如原文页、逐字核对痕迹、可检视性示意），"
                "而不是再去拍一张无关的人像合影",
                {"semantic_spec": "与『Tymoczko 1979 文章的具体表述/引文可检视性』直接相关的素材："
                                  "①哲学家论文/期刊页的可读版面；②逐字核对/标注重合度示意；"
                                  "③『可检视性（surveyability）』概念图。**不得**使用 IMO/竞赛合影",
                 "sourcing": "人工检索（Wikimedia/期刊开放版面/PD 或 CC BY 素材）+ 许可核验；"
                             "本阶段只登记需求，不检索、不下载、不写 asset_id",
                 "count": 1, "must_be_readable_at_1080p": True,
                 "forbidden_material": [{"asset_id": IMO_ASSET, "why": "人工明确否决"}]},
                {"metric": "DQ-8（逐镜语义支撑）+ 人工叙事相关性",
                 "direction": "aS05 语义无关 → 与『可检视性争论』直接对应（DQ-8 状态需复核）",
                 "basis": "S05 旁白：{}".format(str(narr.get("S05"))[:80]),
                 "assumption": "语义达成仍由人工/语义层复核判定；本层不承诺 MATCH",
                 "not_guaranteed": True},
                ["新素材许可不清 ⇒ 必须退回待人工处理（不得先用后补）",
                 "素材可能在低分辨率下不可读 ⇒ 需人工确认可读性",
                 "与已执行的 H5 在 S05 上**跨批次重叠** ⇒ 需人工重新批准（见 cross_batch）"]))
# E3 aS11 Lean/mathlib
props.append(mk("E3", "replace_asset", {"scene_id": "S11", "window": [690.0, 770.0]},
                "把 aS11 的 IMO 合影替换为与『Lean / mathlib / 形式化证明』**直接相关**的视觉",
                "在 S11 窗口内改用**新素材**：必须呈现形式化证明的实际工作对象（源码/证明状态/依赖图），"
                "而不是竞赛合影",
                {"semantic_spec": "与『Lean 4 / mathlib / 形式化证明』直接相关的素材："
                                  "①Lean 源码或 mathlib 页面截图（含可辨识的定理/策略关键字）；"
                                  "②proof state / goal 面板示意；③形式化依赖图或验证流程示意。"
                                  "**不得**使用 IMO/竞赛合影",
                 "sourcing": "人工检索（开源项目页面/文档截图，遵循其许可）+ 许可核验；"
                             "本阶段只登记需求，不检索、不下载、不写 asset_id",
                 "count": 1, "must_be_readable_at_1080p": True,
                 "forbidden_material": [{"asset_id": IMO_ASSET, "why": "人工明确否决"}]},
                {"metric": "DQ-8（逐镜语义支撑）+ 人工叙事相关性",
                 "direction": "aS11 语义无关 → 与『Lean/mathlib』直接对应（DQ-8 状态需复核）",
                 "basis": "S11 旁白：{}".format(str(narr.get("S11"))[:80]),
                 "assumption": "截图类素材需确认许可与可读性；语义达成由人工/语义层复核",
                 "not_guaranteed": True},
                ["源码截图可能含第三方版权/商标 ⇒ 需许可核验（不清则待人工处理）",
                 "与已执行的 H3b（S11 切分）和 H5（S11 换用）**跨批次重叠** ⇒ 需人工重新批准"]))
# E4 480-690 信息增量
props.append(mk("E4", "add_visual_aid", {"scenes": ["S08", "S09", "S10"], "window": [480.0, 690.0]},
                "为 480–690s 开普勒炮弹堆长镜头补充**可核对的信息层**（非 punch-in）",
                "在 S08–S10 窗口内叠加**信息面板**（自制图形/排版，SELF_CREATED）："
                "①问题定义（等球最密堆积）；②候选结构对比（FCC/HCP）与占用率概念；"
                "③『审稿人无法 100% 确认』这一事实的原文出处；④Flyspeck 形式化的目标与状态。"
                "每一个数字/断言都必须**逐项附来源**；**禁止**仅做缩放/推近（punch-in）或重复构图变化",
                {"diagram": "kepler_information_panel", "self_created": True,
                 "content_slots": ["球堆积问题定义", "FCC/HCP 候选结构对比", "审稿人无法完全确认（含出处）",
                                   "Flyspeck：机器可检查的形式化目标"],
                 "each_number_must_cite_source": True,
                 "no_unverified_numbers": True, "punch_in_only_forbidden": True,
                 "keep_total_duration": True},
                {"metric": "信息增量（人工可核对项数）+ DQ-3/DQ-4",
                 "direction": "210s 单镜由『无新增信息』→ 至少 4 个可核对信息槽（不改变时长）",
                 "basis": "S08–S10 旁白：{} …".format(str(narr.get("S08"))[:60]),
                 "assumption": "信息层为图形/文字叠加，不改变画面语义主体；可读性需人工确认",
                 "not_guaranteed": True},
                ["叠加层遮挡主体或与字幕冲突 ⇒ 需遵守既有字幕安全区（底部 5% 边距）",
                 "任何未核实的数字不得进入画面（宁缺勿造）"]))
# E5 850-1000 信息增量
props.append(mk("E5", "add_visual_aid", {"scenes": ["S13", "S14"], "window": [850.0, 1000.0]},
                "为 850–1000s 长镜头补充**可核对的信息层**（非 punch-in）",
                "在 S13–S14 窗口内叠加信息面板（自制）：①『形式化验证不只是审查工具』的论证结构；"
                "②2024 年两件事的时间线（AlphaGeometry 发表于 Nature；系统参加 IMO 题目）与其**精确表述**；"
                "③『银牌=分数换算，不是实际参赛成绩』的可核对说明。每项断言附来源；禁止仅 punch-in",
                {"diagram": "formalization_claim_status_panel", "self_created": True,
                 "content_slots": ["形式化验证作为协作工具（论证结构）", "AlphaGeometry/Nature 2024（时间线）",
                                   "系统参加 IMO 题目（精确表述）", "银牌=分数换算（可核对说明）"],
                 "each_number_must_cite_source": True,
                 "no_unverified_numbers": True, "punch_in_only_forbidden": True,
                 "keep_total_duration": True},
                {"metric": "信息增量（人工可核对项数）+ DQ-3/DQ-4",
                 "direction": "150s 单镜由『无新增信息』→ 至少 4 个可核对信息槽（不改变时长）",
                 "basis": "S13/S14 旁白：{} …".format(str(narr.get("S13"))[:60]),
                 "assumption": "同上；不改变镜头时长与音轨",
                 "not_guaranteed": True},
                ["与既有字幕抢位 ⇒ 需在安全区内排版",
                 "关于 IMO 的表述必须与 S16 的口径一致（避免自相矛盾）"]))

for p in props:
    p["round"] = "6-E"
    key = p["label"].split("-")[0]
    s = by_key[key]
    p["evidence_chain"] = {
        "schema": "revision-evidence-chain-v2",
        "human_review": {"ledger_seq": s["decision"]["seq"], "decision": s["decision"]["decision"],
                         "decided_by": s["decision"]["decided_by"],
                         "decided_at": s["decision"]["decided_at"],
                         "reason": s["decision"]["reason"],
                         "provenance": s["decision"]["provenance"],
                         "entry_sha256": s["decision"]["entry_sha256"]},
        "candidate": {"label": s["cand"], "film": cand[s["cand"]]["film"],
                      "sha256": cand[s["cand"]]["film_sha256"],
                      "pi_gate_outcome": cand[s["cand"]]["pi_gate_outcome"]},
        "scene_window": {"scenes": s["scene"].split(","), "window": s["window"],
                         "narration": {k: narr.get(k) for k in s["scene"].split(",")}},
        "original_evidence": s["evidence"],
        "clip_similarity_sufficient": False,
        "why_not_clip": "『提高 CLIP 相似度』**不构成**修改依据：本条依据是**人审结论 + 候选成片实证**"
                        "（豆腐块字形 / 语义无关素材 / 长镜信息量不足），CLIP 分数既不必要也不充分",
        "not_provable_defer_guard": "驱动决策为**可证** REJECT（unprovable=False）；DEFER/UNKNOWN 不参与生成方案",
    }
    p["information_gain"] = {
        "adds": (["可读的 CJK 片尾文案（替代豆腐块）"] if key == "E1" else
                 ["与旁白论点直接对应的差异化视觉（替换语义无关素材）"] if key in ("E2", "E3") else
                 ["可核对的信息面板（问题定义/候选对比/出处/状态）"]),
        "punch_in_only": False if key in ("E1", "E2", "E3") else False,
        "punch_in_only_forbidden_and_avoided": key in ("E4", "E5"),
        "verifiable_props": (["片尾文字可读且与既有字幕字体一致"] if key == "E1" else
                             ["素材与旁白论点的直接对应关系（人工判定）"] if key in ("E2", "E3") else
                             ["每个数字/断言附来源", "不改变镜头时长与音轨"]),
    }
    p["material_requirement"] = {
        "needs_new_material": key in ("E2", "E3"),          # 需**外部**新素材（人检+许可核验）
        "needs_new_content_self_created": key in ("E4", "E5"),   # 需新内容，但为自制图形（无外部素材）
        "asset_id": None,
        "semantic_spec": (p["proposed_change"]["params"].get("semantic_spec")
                          or p["proposed_change"]["params"].get("diagram")),
        "sourcing": (p["proposed_change"]["params"].get("sourcing")
                     or "自制图形/排版（SELF_CREATED）；数字与断言须附公开来源"),
        "forbidden_material": (p["proposed_change"]["params"].get("forbidden_material") or []),
        "no_fabricated_asset_id": True,
    }

# ---- 4) 登记（append-only 哈希链）----
if REGISTER.exists():
    REGISTER.unlink()
for p in props:
    core_revision.append_proposal(REGISTER, p)
reg = core_revision.load_register(REGISTER)
print("登记:", len(reg), "条 | chain", core_revision.verify_register_chain(reg))

# ---- 5) 保留记录（aS18：已验证正向，不生成方案）----
k1 = by_key["K1"]
retention = {
    "schema": "retention-record-v1", "stage": "6-E", "round": "6-E",
    "kind": "verified_positive_keep", "scene_id": "S18", "window": k1["window"],
    "candidate": {"label": "C4", "film": cand["C4"]["film"], "sha256": cand["C4"]["film_sha256"]},
    "human_review": {"ledger_seq": k1["decision"]["seq"], "decision": k1["decision"]["decision"],
                     "decided_by": k1["decision"]["decided_by"],
                     "reason": k1["decision"]["reason"],
                     "entry_sha256": k1["decision"]["entry_sha256"]},
    "evidence": k1["evidence"],
    "no_proposal_generated": True,
    "why": "该替换已在 6-C 经成片抽帧验证为正向（0.7642 vs 原素材 −0.0894）⇒ 依人工审片第 6 条**保留**，"
           "不重复生成无必要方案（避免无谓改动与范围膨胀）",
    "clip_similarity_sufficient": False,
}

# ---- 6) 冲突检测（M5 口径）+ 跨批次重叠**显式声明** ----
new_matrix = EX.detect_conflicts(props)
cross = []
for p in props:
    for q in executed_c:
        c = EX.pair_conflict(p, q)
        if c:
            cross.append({"new": p["label"], "executed": q["label"], "kinds": c["kinds"],
                          "shared_scenes": c.get("shared_scenes"),
                          "note": "跨批次重叠（M5 门禁按批次判定）⇒ 需人工在批准时显式确认；"
                                  "本阶段不执行，故当前无阻断"})

# ---- 7) 局部化自检 ----
loc = [{"label": p["label"], "scenes": len(p["affected_scope"]["scenes"]),
        "share_of_film": p["affected_scope"]["share_of_film"],
        "within_max_scenes": len(p["affected_scope"]["scenes"])
        <= core_revision.DEFAULT_POLICY["max_scenes_per_proposal"],
        "within_max_share": p["affected_scope"]["share_of_film"]
        <= core_revision.DEFAULT_POLICY["max_share_of_film_per_proposal"]} for p in props]

# ---- 8) 只读/不执行完整性证明 ----
db_a, film_b_after = sha(DB), sha(FILM)
sb_after = sorted((p.name, p.stat().st_size, round(p.stat().st_mtime, 3))
                  for p in SANDBOX_OUT.rglob("*") if p.is_file())
cand_after = {c["index"]: sha(ROOT / c["film"]) for c in m6c["candidates"]}
out = {
    "schema": "directorial-round2-register-v1", "stage": "6-E",
    "note": "只生成/登记 Proposal，**未执行**：无 ffmpeg 调用、无新成片、未修改 C1–C4/v9/DB/timeline/字幕/素材。",
    "inputs": {"project_id": PID, "v9_film": str(FILM.relative_to(ROOT)), "v9_sha256": film_b,
               "phase6c_batch": str(M6C.relative_to(ROOT)),
               "review_ledger": str(REVIEW.relative_to(ROOT)),
               "register": str(REGISTER.relative_to(ROOT))},
    "human_review_round2": [
        {"seq": d["seq"], "finding_id": d["finding_id"], "kind": d["kind"],
         "decision": d["decision"], "scene_id": d["scene_id"], "window": d["window"],
         "reason": d["reason"], "decided_by": d["decided_by"], "decided_at": d["decided_at"],
         "provenance": d["provenance"], "unprovable": d["unprovable"],
         "entry_sha256": d["entry_sha256"], "original_evidence": d["original_evidence"]}
        for d in rev_entries],
    "review_chain": HR.verify_chain(rev_entries),
    "proposals": props,
    "proposal_count": len(props),
    "register_chain": core_revision.verify_register_chain(reg),
    "retention_records": [retention],
    "conflict_matrix_6e": new_matrix,
    "cross_batch_overlaps": cross,
    "locality": loc,
    "forbidden_material_check": {
        "rule": "aS05/aS11 不得继续使用已否决的 IMO 合影（{}）".format(IMO_ASSET),
        "e2_scope_assets": props[1]["affected_scope"]["assets"],
        "e3_scope_assets": props[2]["affected_scope"]["assets"],
        "no_asset_id_written": all(p["material_requirement"]["asset_id"] is None for p in props),
        "forbidden_declared": [p["material_requirement"]["forbidden_material"] for p in props
                               if p["material_requirement"]["forbidden_material"]]},
    "integrity": {
        "executed_anything": False, "ffmpeg_invocations": 0,
        "db_sha256_before": db_b, "db_sha256_after": db_a, "db_unchanged": db_b == db_a,
        "v9_sha256_before": film_b, "v9_sha256_after": film_b_after,
        "v9_unchanged": film_b == film_b_after and film_b == V9_SHA,
        "sandbox_output_unchanged": sb_before == sb_after,
        "sandbox_output_files": [x[0] for x in sb_after],
        "c1_c4_sha_unchanged": all(cand_after[c["index"]] == c["film_sha256"]
                                   for c in m6c["candidates"]),
        "candidates_verified": {str(k): v[:16] for k, v in cand_after.items()},
        "timeline_readonly": True, "subtitles_untouched": True, "materials_untouched": True,
        "baseline_dir_readonly": True, "no_new_baseline_or_tag": True,
    },
}
OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

print("\n提案清单:")
for p in props:
    print("  {} | {} | scenes {} | window {} | share {} | 素材需求 {} | asset_id {}".format(
        p["label"], p["action"], p["affected_scope"]["scenes"], p["affected_scope"]["window"],
        p["affected_scope"]["share_of_film"], p["material_requirement"]["needs_new_material"],
        p["material_requirement"]["asset_id"]))
print("6-E 内部冲突:", new_matrix["conflict_pair_count"], "| 跨批次重叠:", len(cross))
print("局部化:", all(x["within_max_scenes"] and x["within_max_share"] for x in loc))
print("完整性: DB {} | v9 {} | 沙箱产物未变 {} | C1–C4 未变 {}".format(
    out["integrity"]["db_unchanged"], out["integrity"]["v9_unchanged"],
    out["integrity"]["sandbox_output_unchanged"], out["integrity"]["c1_c4_sha_unchanged"]))
print("保留记录:", retention["kind"], retention["scene_id"], "| 未生成方案", retention["no_proposal_generated"])
print("json ->", OUT)
