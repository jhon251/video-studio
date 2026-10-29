# -*- coding: utf-8 -*-
"""6-F —— **Historical Lineage Rebuild Planning v2（修订）**：只读、可进入人工授权阶段的最终计划。

本版修正（相对 v1）：
  1. 统一 E1 窗口：以**计划自身的原始累计链**为唯一权威（S21 = 927.840–978.656）；
     并明确 E1 片尾卡的**实际 placement**（v1 把它默认成整个 S21），给出三种 placement 方案（不替用户选择）。
  2. 修正统计口径：明确区分 **scene rate（21/total）** 与 **cut rate（20/total）**；
     并指出 **DQ-4 冻结实现使用镜头数/分钟**（`core/direction.py:212` 的 `len(timeline)/(total/60)`），
     "换镜次数/min" 若被采用需另行授权改 DQ 实现（本阶段不改）。
  3. E2 不再"直接迁移"：给出三种处理方案（精简槽位 / 延展至相邻镜头 / 重新设计）及其代价。
  4. 完整重制范围继续为**候选**，不自行授权。
  5. 21 段数学一致性完整验算（Σactual / pause / trailing / 总长 / 连续无重叠无空洞 / S21 末端 / 逐段偏移）。
  6. 生成最终风险与人工决策清单。

禁止：ffmpeg / 生成 MP4 / candidate / 改 DB / 改 v9·C1–C4·E1·E2 / 改 baseline·tag / 执行 E3–E5 / promote /
      重录 TTS / 下载新素材 / 替用户选择 pause_budget·是否扩写·最小或完整范围。

产出: docs/regression_2x/logs/phase6f_rebuild_plan_v2.json
"""
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
from video_studio.core import captions as core_captions              # noqa: E402
from video_studio.core import narration as N                         # noqa: E402
from video_studio.core import revision as core_revision              # noqa: E402
from video_studio.core import execution as EX                        # noqa: E402

LOGS = ROOT / "docs" / "regression_2x" / "logs"
DB = ROOT / "projects" / "video_studio.db"
OUT = LOGS / "phase6f_rebuild_plan_v2.json"
P1 = LOGS / "phase6f_rebuild_plan.json"
PAUSE = N.PAUSE_BUDGET_S
TRAILING = N.TRAILING_PAD_S
TARGET_HOLD_S = 25.0

# ---------------------------------------------------------------- 取数（只读）
con = sqlite3.connect("file:{}?mode=ro".format(DB.as_posix()), uri=True)
con.row_factory = sqlite3.Row
con.execute("PRAGMA query_only=ON")
rows = [dict(r) for r in con.execute(
    "select artifact_id, task_id, type, path from artifacts where project_id=? order by created_at",
    ("p_96efdc03e1aa",))]
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
render, r_rec = latest("render_output", "t_d0a54bdf1810")
segs = script.get("segments") or []
vsegs = voice.get("segments") or []
timeline = render.get("material_timeline") or []
m6c = json.loads((LOGS / "phase6c_batch.json").read_text(encoding="utf-8"))
m3 = json.loads((LOGS / "phase6b_m3_proposals_v9.json").read_text(encoding="utf-8"))
r2 = json.loads((LOGS / "phase6e_round2.json").read_text(encoding="utf-8"))
e1rep = json.loads((LOGS / "phase6e_e1_execution.json").read_text(encoding="utf-8"))
p1 = json.loads(P1.read_text(encoding="utf-8"))
reg = core_revision.load_register(LOGS / "phase6e_proposal_register_r2.jsonl")

actual = [float(s["duration_s"]) for s in vsegs]          # 原始精度（权威）
n = len(actual)
sum_actual = sum(actual)

# ---------------------------------------------------------------- (5) 数学验算
chain, cursor, checks = [], 0.0, []


def ck(name, ok, detail=None):
    checks.append({"check": name, "ok": bool(ok), "detail": detail})
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else "| " + json.dumps(detail, ensure_ascii=False)[:200]))
    return bool(ok)


for i in range(n):
    pause_i = PAUSE if i < n - 1 else TRAILING
    w0 = round(cursor, 3)
    audit_end = round(cursor + actual[i], 3)
    w1 = round(cursor + actual[i] + pause_i, 3)
    tw = timeline[i] if i < len(timeline) else {}
    chain.append({
        "index": i, "scene_id": tw.get("scene_id") or "S{:02d}".format(i + 1),
        "old_timeline_window_s": [tw.get("start_s"), tw.get("end_s")],
        "actual_tts_duration_s": round(actual[i], 3),
        "pause_budget_s": round(pause_i, 3),
        "new_audio_window_s": [w0, audit_end],
        "new_timeline_window_s": [w0, w1],
        "cumulative_position_s": w0,
        "old_to_new_offset_s": round(w0 - float(tw.get("start_s") or 0.0), 3),
        "duration_delta_vs_old_s": round((w1 - w0) - (float(tw.get("end_s") or 0.0)
                                                     - float(tw.get("start_s") or 0.0)), 3),
        "asset": (tw.get("selected_asset") or {}).get("asset_id"),
        "asset_name": ((tw.get("selected_asset") or {}).get("name")
                       or (tw.get("selected_asset") or {}).get("title")),
    })
    cursor = w1

production = round(sum_actual + PAUSE * (n - 1) + TRAILING, 3)
ck("M1 Σ actual TTS == 961.656", abs(sum_actual - 961.656) < 1e-9, sum_actual)
ck("M2 pause 合计 == 0.75×20 == 15.0", abs(PAUSE * (n - 1) - 15.0) < 1e-9, PAUSE * (n - 1))
ck("M3 trailing == 2.0", abs(TRAILING - 2.0) < 1e-9, TRAILING)
ck("M4 production duration == 978.656",
   abs(production - 978.656) < 1e-9, production)
continuity = all(abs(chain[i]["new_timeline_window_s"][1]
                     - chain[i + 1]["new_timeline_window_s"][0]) < 1e-9 for i in range(n - 1))
ck("M5 21 段连续：后段起点 == 前段终点（无重叠、无空洞）", continuity)
ck("M6 S21 end == production duration",
   abs(chain[-1]["new_timeline_window_s"][1] - production) < 1e-9,
   {"s21_end": chain[-1]["new_timeline_window_s"][1], "production": production})
offsets_ok = all(
    abs(chain[i]["old_to_new_offset_s"]
        - (chain[i]["new_timeline_window_s"][0] - float(chain[i]["old_timeline_window_s"][0]))) < 1e-3
    for i in range(n))
ck("M7 每段 old→new offset 与其窗口一致", offsets_ok)
audio_sum = round(sum(c["actual_tts_duration_s"] for c in chain), 3)
ck("M8 表内逐段 actual 之和 == 961.656（无舍入漂移）", abs(audio_sum - 961.656) < 1e-9, audio_sum)

# ---------------------------------------------------------------- (2) 速率口径
total = production
scene_rate = round(n / (total / 60.0), 3)          # 镜头数/分钟（DQ-4 现用口径）
cut_rate = round((n - 1) / (total / 60.0), 3)      # 换镜/切点次数/分钟（物理切点）
rates = {
    "scene_rate_per_min": scene_rate,
    "cut_rate_per_min": cut_rate,
    "definitions": {
        "scene_rate": "镜头数 / 总分钟 = {} / ({}/60) = **{}**/min".format(n, total, scene_rate),
        "cut_rate": "切点（镜头切换）次数 / 总分钟 = ({n}−1) / ({t}/60) = **{c}**/min".format(
            n=n, t=total, c=cut_rate),
    },
    "dq4_current_implementation": {
        "code": "core/direction.py:212 `changes_per_min = len(timeline) / (total / 60.0)`",
        "meaning": "**DQ-4 现用口径 = 镜头数/分钟（scene rate）**，不是切点次数/分钟",
        "threshold": "min_scene_changes_per_min = 2.0（DQ-4 下限）",
        "planning_estimate": {"value": scene_rate, "would_pass_threshold": scene_rate >= 2.0},
        "note": "若人工要求 DQ-4 采用『换镜次数/min』语义，需要**另行授权修改 DQ 实现**；"
                "本阶段不修改任何 DQ 代码，也不宣称 DQ PASS/FAIL。",
    },
    "naming_correction": "v1 计划里仅给出 1.287/min 并称『换镜密度』；v2 明确它是 **scene rate**，"
                         "并单列 cut rate，避免口径混用。",
}

# ---------------------------------------------------------------- (3) corrected E1 window
s21 = chain[-1]
e1_prop = next((x for x in r2["proposals"] if x["label"].startswith("E1")), None)
e1_steps = [s for s in (e1rep["execution"].get("steps") or [])
            if s.get("step") == "reencode_window_with_outro_card_and_captions"]
e1 = {
    "proposal_id": e1_prop["proposal_id"] if e1_prop else None,
    "proposal_sha256": EX.proposal_sha256(e1_prop) if e1_prop else None,
    "old_window_s": e1_prop["affected_scope"]["window"] if e1_prop else None,
    "CORRECTED_NEW_WINDOW_S": s21["new_timeline_window_s"],
    "new_s21_window_s": s21["new_timeline_window_s"],
    "discrepancy": {
        "v1_chat_table_claimed": [927.888, 978.656],
        "plan_v1_json_and_v2_authoritative": [927.84, 978.656],
        "root_cause": "v1 聊天表格中 S13–S21 的行由**手算舍入值**写出（误用了 44.016/40.584/47.712/"
                      "44.760/39.240/46.608 等值），而 voice_output 的真实逐段时长为 "
                      "43.92/40.68/47.64/44.856/39.192/46.584；计划 JSON 与 v2 均由**原始精度累计链**生成 ⇒ 权威值为 927.840。",
        "resolution": "以原始累计链为唯一权威；v2 计划内**不再出现** 927.888。",
    },
    "executed_placement_evidence": {
        "step": (e1_steps[0] if e1_steps else {}),
        "finding": "已执行的 E1 使用 `affected_scope.window=[1465,1532]`（=旧 S21 整段 67.0s），"
                   "drawtext 未带 `enable=` ⇒ 片尾卡在**整个窗口内常显**，并非仅结尾若干秒。",
        "implication": "v1 计划把『E1 窗口』等同于『末镜窗口』是**沿用了旧执行形态**；"
                       "v2 明确区分『卡片可用窗口（新 S21）』与『卡片实际 placement（人工决定）』。",
    },
    "placement_options": [
        {"id": "P-A", "name": "整段常显（沿用旧执行形态）",
         "window_s": s21["new_timeline_window_s"], "duration_s": 50.816,
         "impact": "与旧行为一致；末镜全程覆盖片尾文案",
         "cost": "末镜信息层被片尾文案长期占据（50.8s）"},
        {"id": "P-B", "name": "仅片尾若干秒（建议值供人工选择，不自动采用）",
         "window_s": [round(s21["new_timeline_window_s"][1] - 12.0, 3),
                      s21["new_timeline_window_s"][1]], "duration_s": 12.0,
         "impact": "片尾卡只出现在真正结尾；需要 `enable='between(t,…)'` 或独立末段重编码",
         "cost": "与旧 E1 执行形态不同 ⇒ 需要新的 E1 绑定与（若改实现）最小代码改动"},
        {"id": "P-C", "name": "最后一段旁白结束后的收尾区（trailing 2.0s）",
         "window_s": [round(s21["new_timeline_window_s"][1] - TRAILING, 3),
                      s21["new_timeline_window_s"][1]], "duration_s": 2.0,
         "impact": "只在收尾静音区显示，最不干扰内容",
         "cost": "2.0s 对中文两行文案偏短，可能不可读"},
    ],
    "choice": "NOT_CHOSEN（由人工决定）",
}

# ---------------------------------------------------------------- (6) E2 三种方案
plan_json = json.loads((ROOT / "docs" / "regression_2x" / "phase6e_materials" /
                        "phase6e_material_plan.json").read_text(encoding="utf-8"))
e2_plan = plan_json["items"]["E2"]["C_self_made_spec"]
chars = sum(len(p["title"]) + sum(len(x) for x in p["content"]) for p in e2_plan["panels"])
cps = float(core_captions.CHARS_PER_SEC)
s05 = chain[4]
s05_dur = round(s05["new_timeline_window_s"][1] - s05["new_timeline_window_s"][0], 3)
read_need = round(chars / cps, 1)
e2v2_reg = next((x for x in reg if x.get("version") == 2 and x["label"].startswith("E2")), None)
e2_options = {
    "current_design": {"panels": [p["id"] for p in e2_plan["panels"]], "chars": chars,
                       "reading_need_s": read_need, "new_window_s": s05["new_timeline_window_s"],
                       "new_window_duration_s": s05_dur,
                       "deficit_s": round(read_need - s05_dur, 1)},
    "options": [
        {"id": "A", "name": "精简信息槽",
         "how": "保留语义四要素但压缩文字（例如阶梯 4 级改为 4 个短标签、文献元数据只留作者+年份+DOI 后缀、"
                "两立场各一行），把字数压到可按阅读速度在窗口内读完",
         "target_chars": int(s05_dur * cps), "target_reading_s": s05_dur,
         "cost": ["信息量下降（DOI/卷期页需取舍）", "需人工重新审定文本（不得新增/删改事实）",
                  "需重新登记 spec（spec_source 或内联 spec 的哈希）"],
         "needs_new_proposal": True},
        {"id": "B", "name": "延展至相邻镜头",
         "how": "把信息层覆盖 S04–S06（或 S05+相邻）以取得更长展示时间",
         "window_example_s": [chain[3]["new_timeline_window_s"][0],
                              chain[5]["new_timeline_window_s"][1]],
         "window_duration_s": round(chain[5]["new_timeline_window_s"][1]
                                    - chain[3]["new_timeline_window_s"][0], 1),
         "cost": ["**扩大 affected_scope**（跨 3 镜，需重新做局部化/冲突校验）",
                  "与相邻镜头既有内容叠加，可能遮挡", "与 H3 切分/其它方案的重叠风险上升"],
         "needs_new_proposal": True},
        {"id": "C", "name": "重新设计信息图",
         "how": "改用更少、更大的视觉元素（例如只保留『阶梯 + 当前状态高亮』一个面板，文献元数据以字幕/旁白承担）",
         "cost": ["设计语义**部分保留**（四要素中可能只留 1–2 项）", "需人工确认哪些要素不可丢",
                  "需要全新 spec 与重新登记"],
         "needs_new_proposal": True},
    ],
    "old_design": {"proposal_id": e2v2_reg["proposal_id"] if e2v2_reg else None,
                   "proposal_sha256": EX.proposal_sha256(e2v2_reg) if e2v2_reg else None,
                   "old_window_s": [245.0, 300.0],
                   "migration": "**禁止直接迁移**：坐标与设计体量均须重新决定（三种方案见上）"},
    "choice": "NOT_CHOSEN（由人工决定）",
}

# ---------------------------------------------------------------- (5) 迁移状态
def effective(label):
    v = next((x for x in reg if str(x.get("label", "")).startswith(label)
              and x.get("version") == 2), None)
    return v or next((x for x in r2["proposals"] if x["label"].startswith(label)), None)


def win(scenes):
    idx = [c["index"] for c in chain if c["scene_id"] in scenes]
    return [chain[min(idx)]["new_timeline_window_s"][0],
            chain[max(idx)]["new_timeline_window_s"][1]]


migration = []
for label, scenes, kind in (("E1", ["S21"], "片尾卡"),
                            ("E2", ["S05"], "可检视性信息图"),
                            ("E3", ["S11"], "Lean/mathlib 视觉"),
                            ("E4", ["S08", "S09", "S10"], "开普勒信息面板"),
                            ("E5", ["S13", "S14"], "形式化验证面板")):
    p = effective(label)
    ow = [chain[c["index"]]["old_timeline_window_s"][0] for c in chain if c["scene_id"] in scenes]
    nw = win(scenes)
    migration.append({
        "label": p["label"] if p else label, "proposal_id": p.get("proposal_id") if p else None,
        "proposal_sha256": (EX.proposal_sha256(p) if p else None),
        "kind": kind, "scenes": scenes,
        "old_proposal_window_s": (p.get("affected_scope", {}) or {}).get("window") if p else None,
        "new_scene_window_s": nw,
        "new_duration_s": round(nw[1] - nw[0], 1),
        "status": ("必须重新 proposal（窗口变化 + 设计体量需重定）" if label == "E2"
                   else "重新绑定的新窗口；语义可迁移，坐标必须重算"),
        "reuse_old_window": False,
    })
for lab, cls, why in (
        ("H3a/H3b（长镜切分）", "必须重新 proposal",
         "切点由旧窗口推导；9 个场景子镜数 4→2/3，旧坐标全部作废"),
        ("H5（池内换材）", "必须重新 proposal（重新选材）",
         "S05/S11 旧选材为已被人工否决的 IMO 合影；窗口亦变"),
        ("H2（素材池多样性）", "可迁移（与时间基无关）",
         "仍需人工提供合格素材，否则保持 PENDING"),
        ("H4（依赖 H3a）", "失效（依赖链需重建）", "H3a 重做 ⇒ H4 需重新评估"),
        ("C1–C4（6-C 候选）", "不得作为重制基线",
         "建立在旧时基（570.3s 静音 + 字幕漂移）")):
    migration.append({"label": lab, "kind": "（非本次 E 系列）", "status": cls, "why": why})

# ---------------------------------------------------------------- H3 重算（引用 v1 结果并复核）
split_recalc = p1["six_c_split_reanalysis"]

# ---------------------------------------------------------------- (6) 最终人工决策清单
imo_scenes = [c["scene_id"] for c in chain if c["asset"] == "asset_432cd85be6f1"]
asset_share = {}
for c in chain:
    k = c["asset_name"] or "(solid/placeholder)"
    asset_share[k] = round(asset_share.get(k, 0.0)
                           + (c["new_timeline_window_s"][1] - c["new_timeline_window_s"][0]), 3)
share_pct = {k: round(v / total, 4) for k, v in asset_share.items()}

decisions = [
    {"id": "D1", "question": "pause_budget 是否确认为 0.75 s？",
     "options": {"0.0": 963.656, "0.25": 968.656, "0.5": 973.656, "0.75": 978.656, "1.0": 983.656},
     "impact": "决定新片长与段间呼吸感；不影响 narration truth（961.656s）",
     "current": "NOT_CHOSEN（DCv2 默认 0.75 仅作为推算基准）"},
    {"id": "D2", "question": "是否接受约 978.656 s（较旧 1532.0 s 缩短 36.1%）的新片长？",
     "options": ["接受", "不接受并先扩写脚本（另立任务）", "先做小样验证节奏"],
     "impact": "决定重制是否可进入执行", "current": "NOT_CHOSEN"},
    {"id": "D3", "question": "是否扩写脚本（增加旁白内容以恢复时长/覆盖）？",
     "options": ["不扩写（接受缩短）", "扩写（需重新事实核查 + 重新 TTS + 重新审批）"],
     "impact": "扩写会改变 narration truth 与全部窗口 ⇒ 需重跑规划", "current": "NOT_CHOSEN"},
    {"id": "D4", "question": "R0：S13–S16 是否继续使用 IMO 合影（asset_432cd85be6f1）？",
     "detail": {"v9_in_use_scenes": imo_scenes, "share": share_pct.get(
         "Matematička gimnazija - Mathematical Gymnasium Belgrade - MGB - IMO 2010 - pic3.jpg"),
         "human_ban_scope": "人工否决的是作为 aS05/aS11 的替代素材"},
     "options": ["继续使用（保留 v9 用法）", "替换为其它素材（需人工提供 + 许可核验）",
                 "仅在 E5 窗口替换"],
     "impact": "影响 E5 底层画面、署名/许可台账与素材占比", "current": "NOT_CHOSEN"},
    {"id": "D5", "question": "H3 是否重新切分（9 个场景子镜数 4→2/3）？",
     "options": ["重新 proposal 并按新窗口切分", "不切分（接受长镜）", "仅切分其中部分场景"],
     "impact": "影响 DQ-3/DQ-4 与镜头节奏；21/21 场景 > 25s 静态保持上限",
     "current": "NOT_CHOSEN"},
    {"id": "D6", "question": "H5 是否重新选材（S05/S11 不得沿用 IMO 合影）？",
     "options": ["重新选材（需人工/检索 + 许可核验）", "保持 v9 原素材（若与禁用法不冲突）"],
     "impact": "影响 S05/S11 语义与 DQ-8", "current": "NOT_CHOSEN"},
    {"id": "D7", "question": "E2 如何处理 40.086 s 阅读窗口？",
     "detail": e2_options["current_design"],
     "options": ["A 精简信息槽", "B 延展至相邻镜头", "C 重新设计信息图", "暂缓 E2"],
     "impact": "影响方案范围/局部化校验/是否需要新 spec 登记", "current": "NOT_CHOSEN"},
    {"id": "D8", "question": "E4/E5 信息槽是否需要压缩（E4 131.9s、E5 86.1s）？",
     "options": ["保持 4 槽", "压缩为 2–3 槽", "拆分到相邻镜头"],
     "impact": "影响可读性与信息密度", "current": "NOT_CHOSEN"},
    {"id": "D9", "question": "E1 片尾卡 placement 采用哪一种（P-A 整段 / P-B 末 12s / P-C 收尾 2s）？",
     "impact": "决定是否保持旧行为；P-B/P-C 可能需要最小实现改动",
     "current": "NOT_CHOSEN"},
    {"id": "D10", "question": "重制范围选最小还是完整？",
     "options": ["最小重制范围（保结构）", "完整重制范围（重规划）"],
     "impact": "决定是否重新 proposal 切分/选材与是否重切 baseline",
     "current": "NOT_CHOSEN（本阶段不自行选择）"},
    {"id": "D11", "question": "新 baseline/tag 策略？",
     "options": ["重制后新切 baseline + 新 tag", "仅新 tag（baseline 保持旧）", "暂不切（先人工验收成片）"],
     "impact": "影响回归基线与验收口径", "current": "NOT_CHOSEN（未授权前不动 baseline/tag）"},
    {"id": "D12", "question": "DQ-4 是否改用『切点次数/分钟』口径？",
     "detail": rates, "options": ["保持现有实现（镜头数/分钟）", "授权修改 DQ 实现（另立任务）"],
     "impact": "影响 DQ-4 判定口径与阈值含义", "current": "NOT_CHOSEN（未改 DQ 代码）"},
]

# ---------------------------------------------------------------- 输出
plan = {
    "schema": "phase6f-rebuild-plan-v2", "stage": "6-F",
    "state": "PLANNING_ONLY / AWAITING_HUMAN_AUTHORIZATION",
    "note": "只读修订计划：未重制、未生成 MP4、未调用 ffmpeg、未改 v9/C1–C4/E1/E2/DB/baseline/tag、"
            "未执行 E3–E5、未 promote、未重录 TTS、未下载素材。",
    "supersedes": {"plan_v1": str(P1.relative_to(ROOT)),
                   "plan_v1_sha256": hashlib.sha256(P1.read_bytes()).hexdigest()},
    "corrections_in_v2": [
        "统一 E1/S21 窗口为 927.840–978.656（v1 聊天表格的 927.888 系手算舍入误值，计划 JSON 本身正确）",
        "明确 E1 的『窗口』与『placement』是两件事（旧执行形态为整段常显；v2 给出三种 placement，不替人选）",
        "速率口径拆分 scene rate（1.287/min，DQ-4 现用）与 cut rate（1.226/min）",
        "E2 不再直接迁移：给出 A/B/C 三种处理方案及代价",
        "补齐 21 段数学一致性验算（M1–M8）",
        "新增 12 项人工决策清单（D1–D12）",
    ],
    "math_verification": {"checks": checks, "all_pass": all(c["ok"] for c in checks),
                          "sum_actual_tts_s": round(sum_actual, 6),
                          "pause_total_s": round(PAUSE * (n - 1), 3),
                          "trailing_pad_s": TRAILING,
                          "production_duration_s": production,
                          "formula": "Σactual + pause×(n−1) + trailing = {} + {} + {} = {}".format(
                              round(sum_actual, 3), round(PAUSE * (n - 1), 3), TRAILING, production),
                          "not_just_narration_truth": "narration truth = 961.656 s；"
                                                      "生产时长 = 978.656 s（含停顿预算与收尾）"},
    "remapping_21_segments": chain,
    "new_production_timeline": [
        {"scene_id": c["scene_id"], "start_s": c["new_timeline_window_s"][0],
         "end_s": c["new_timeline_window_s"][1], "narrative_window_s": c["new_audio_window_s"],
         "pause_after_s": c["pause_budget_s"]} for c in chain],
    "rates": rates,
    "e1_window_and_placement": e1,
    "e2_reproposal": e2_options,
    "migration_status": migration,
    "six_c_split_reanalysis": split_recalc,
    "metrics_estimate": {
        "new_production_duration_s": production,
        "old_declared_time_base_s": p1["metrics_estimate"]["old_declared_time_base_s"],
        "duration_reduction_s": round(p1["metrics_estimate"]["old_declared_time_base_s"] - production, 3),
        "duration_reduction_ratio": round((p1["metrics_estimate"]["old_declared_time_base_s"]
                                           - production)
                                          / p1["metrics_estimate"]["old_declared_time_base_s"], 4),
        "scene_count": n,
        "scene_duration_s": {"min": round(min(c["new_timeline_window_s"][1]
                                              - c["new_timeline_window_s"][0] for c in chain), 3),
                             "mean": round(total / n, 3),
                             "max": round(max(c["new_timeline_window_s"][1]
                                              - c["new_timeline_window_s"][0] for c in chain), 3)},
        "scenes_over_25s": [c["scene_id"] for c in chain
                            if (c["new_timeline_window_s"][1] - c["new_timeline_window_s"][0]) > TARGET_HOLD_S],
        "asset_share": {k: {"duration_s": v, "share": share_pct[k]} for k, v in asset_share.items()},
        "unique_assets": len([k for k in asset_share if k != "(solid/placeholder)"]),
        "max_asset_share": max(share_pct.values()),
        "note": "**规划期推算，不是 DQ 判定**；DQ 需重制成片后实测（本阶段不宣称 DQ PASS/FAIL）。",
    },
    "rebuild_scopes": {"minimal": p1["rebuild_scopes"]["minimal"],
                       "full": p1["rebuild_scopes"]["full"],
                       "selection": "NOT_CHOSEN（由人工在 D10 决定）"},
    "human_authorization_checklist": decisions,
    "invariants": {"ffmpeg_invocations": 0, "mp4_generated": 0, "candidate_generated": 0,
                   "db_modified": False, "v9_modified": False, "c1_c4_modified": False,
                   "e1_e2_modified": False, "baseline_tag_modified": False,
                   "e3_e4_e5_executed": False, "promoted": False, "tts_rerecorded": False,
                   "materials_downloaded": False},
}
plan["plan_sha256"] = hashlib.sha256(
    json.dumps({k: v for k, v in plan.items() if k != "plan_sha256"}, sort_keys=True,
               ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()
OUT.write_text(json.dumps(plan, ensure_ascii=False, indent=1, default=str), encoding="utf-8")

print("\n== 速率口径 ==")
print("  scene rate = {} /min（DQ-4 现用实现口径）".format(scene_rate))
print("  cut rate   = {} /min（切点次数）".format(cut_rate))
print("\n== corrected E1 ==")
print("  窗口（新 S21）= {} | 旧窗口 {}".format(e1["CORRECTED_NEW_WINDOW_S"], e1["old_window_s"]))
print("  placement: {}（由人工在 D9 选择）".format(e1["choice"]))
print("\n== E2 三方案 ==")
print("  现设计 {} 字 / 需 {:.1f}s / 新窗口 {:.1f}s / 缺口 {:.1f}s".format(
    chars, read_need, s05_dur, e2_options["current_design"]["deficit_s"]))
for o in e2_options["options"]:
    print("   {} {}".format(o["id"], o["name"]))
print("\n== 指标（规划期推算，非 DQ 判定）==")
print("  总长 {} s | 场景 min/mean/max {}/{}/{} s | >25s 场景 {} 个".format(
    production, plan["metrics_estimate"]["scene_duration_s"]["min"],
    plan["metrics_estimate"]["scene_duration_s"]["mean"],
    plan["metrics_estimate"]["scene_duration_s"]["max"],
    len(plan["metrics_estimate"]["scenes_over_25s"])))
print("  唯一素材 {} | 最大素材占比 {} | IMO 合影在用场景 {}".format(
    plan["metrics_estimate"]["unique_assets"], plan["metrics_estimate"]["max_asset_share"],
    imo_scenes))
print("\n== 状态 ==\n  {} | 数学验算 all_pass={} | 人工决策 {} 项".format(
    plan["state"], plan["math_verification"]["all_pass"], len(decisions)))
print("plan ->", OUT)
