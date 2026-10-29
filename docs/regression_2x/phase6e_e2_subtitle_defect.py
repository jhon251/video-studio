# -*- coding: utf-8 -*-
"""E2 字幕缺陷：**确认、根因、影响范围**，并更正先前报告中的过度表述（只读）。

人工报告："字幕没有一条能对的上旁白的" ⇒ 已用测量确认（见 phase6e_e2_subtitle_audio_sync*.json）：
  · 脚本声明旁白时长合计 **1530.0 s**（时间轴 1532 s 由脚本推导）；
  · 真实 TTS 音频（voice_output 21 段）合计 **961.656 s** ⇒ 少 **568.344 s**；
  · 音频语音活动：0–960 s 占比 0.92–0.94，**960 s 之后 0.00**（无旁白），而字幕 cue 仍排到 1530 s；
  · 每段真实音频都短于脚本声明（例：seg2 脚本 80 s / 实际 57.72 s；seg6 95 s / 65.74 s）；
  · 母版 vs E2 候选的**字幕带**在 7 个采样点像素一致（0.03–0.72/255）⇒ E2 **未改字幕**，缺陷继承自 v9；
  · 与冻结 PI 门禁互相印证：PI-2 shortfall 570.344 s、PI-3 最长静音 570.869 s、PI-6 漂移 552.16 s ⇒
    **PI 门禁早已量化同一缺陷**（此前被归类为"既有 BLOCKED 模式"，未识别其真实含义 —— 现更正）。

产出: logs/phase6e_e2_subtitle_defect.json（缺陷记录）
      + 更新 logs/phase6e_e2_execution.json（更正过度表述）
      + 登记链追加 1 条 `defect-record-v1`
"""
import hashlib
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
LOGS = ROOT / "docs" / "regression_2x" / "logs"
SYNC1 = LOGS / "phase6e_e2_subtitle_audio_sync.json"
SYNC2 = LOGS / "phase6e_e2_subtitle_audio_sync2.json"
E2REP = LOGS / "phase6e_e2_execution.json"
PREP = LOGS / "phase6e_e2_review_prep.json"
LEDGER = LOGS / "phase6e_approval_status_r2.jsonl"
OUT = LOGS / "phase6e_e2_subtitle_defect.json"
V9 = ROOT / "projects" / "p_96efdc03e1aa" / "output" / "t_d0a54bdf1810_draft.mp4"
V9_SHA = "22705c7d7ea20b40d91120146066b89ab2b5fa5c1a1cab18f5346d4c66497651"
CAND = ROOT / "output" / "phase6b_m4_sandbox" / "p_96efdc03e1aa_6e2" / "output" / \
    "t_d0a54bdf1810_draft_6c_rp-bee31dff3335_vaid.mp4"


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


s2 = json.loads(SYNC2.read_text(encoding="utf-8"))
s1 = json.loads(SYNC1.read_text(encoding="utf-8"))
blocks = s2["blocks_60s"]
narr_end = next((b["block_s"][0] for b in blocks if (b["speech_frac"] or 0) < 0.05), None)
per = [p for p in s2["per_segment_script_vs_voice"] if p["voice_dur_s"] is not None]
drift = [{"i": p["i"], "script_dur_s": p["script_dur_s"], "voice_dur_s": p["voice_dur_s"],
          "delta_s": p["delta_s"], "cum_script_s": p["cum_script_s"],
          "cum_voice_s": p["cum_voice_s"],
          "cum_drift_s": (round(p["cum_script_s"] - p["cum_voice_s"], 3)
                          if p["cum_voice_s"] is not None else None)} for p in per]

defect = {
    "schema": "phase6e-subtitle-defect-v1", "stage": "6-E",
    "reported_by": "human:director(E2 candidate review)",
    "human_report": "字幕没有一条能对的上旁白的",
    "status": "CONFIRMED（测量确认）",
    "severity": "HIGH（影响全片可读性与可信度；影响 E2 的验收结论）",
    "scope": {
        "inherited_from": "v9 母版（同一 pipeline 生成的字幕与音轨）",
        "introduced_by_e2": False,
        "evidence_e2_not_the_cause": s2["subtitle_band_master_vs_candidate"],
        "affects": "全片（21 段全部存在漂移；960 s 之后完全无旁白但字幕继续）",
    },
    "root_cause": {
        "mechanism": "时间轴与字幕 cue 使用**脚本声明的旁白时长**（合计 1530.0 s），"
                     "而实际 TTS 音频只有 **961.656 s** ⇒ 每段的字幕按声明时长铺开，比真实语音慢，"
                     "误差逐段累积；且音频总长 < 时间轴 ⇒ 末段无声但仍有字幕。",
        "numbers": {
            "timeline_s": s2["totals"]["timeline_s"],
            "script_narration_s": s2["totals"]["script_narration_s"],
            "voice_total_s": s2["totals"]["voice_total_s"],
            "voice_vs_script_delta_s": s2["totals"]["voice_vs_script_delta_s"],
            "narration_audio_ends_at_s": narr_end,
            "caption_cues_until_s": 1530,
        },
        "per_segment_drift": drift,
        "cross_validation_with_frozen_PI_gates": {
            "PI-2_shortfall_s": 570.344, "PI-3_max_silence_s": 570.869, "PI-6_max_drift_s": 552.16,
            "interpretation": "冻结 PI 门禁一直在量化同一缺陷；先前把它当作『既有 BLOCKED 模式』"
                              "而未识别其含义 —— 现更正为**真实缺陷的量化证据**"},
    },
    "impact_on_e2": {
        "e2_overlay": "E2 的叠加层本身与本缺陷无关（叠加层在 [245,300] 正常渲染）",
        "but": "E2 候选继承了全片字幕漂移 ⇒ 以『字幕正常』为前提的验收不成立；"
               "E2 不得据此被 ACCEPT/promote",
        "window_245_300_specific": "窗口内字幕与母版逐像素一致（未改），但该窗口同样存在漂移"
                                   "（脚本累计 vs 音频累计在中段已相差数十秒）",
    },
    "corrections_to_prior_claims": [
        {"claim": "E2 执行报告『字幕正常 / 字幕未受损』",
         "correction": "该结论只证明了『窗口内字幕像素与母版一致（未被 E2 改变）』，"
                       "**未**验证『字幕文本与实际旁白对齐』；经测量，后者**不成立**（全片漂移，"
                       "960 s 后无旁白）。表述过度，现更正。",
         "status": "OVERCLAIM_CORRECTED"},
        {"claim": "审查准备 Q6『字幕未受损：数值成对接近』",
         "correction": "同上：仅证明像素一致与存在性，不构成『字幕正确』的证据。",
         "status": "OVERCLAIM_CORRECTED"},
        {"claim": "历次报告把 PI-1/2/3/5/6 FAIL 归类为『既有冻结模式』",
         "correction": "PI-2/3/6 的数值正是本字幕/旁白失同步缺陷的量化；应作为**缺陷证据**对待。",
         "status": "RECLASSIFIED"},
    ],
    "recommended_next_steps_for_human": [
        "① 决定缺陷归属：pipeline 级（脚本声明时长 vs TTS 实际时长契约）——需另行授权修复，本轮不做",
        "② 若继续使用 E2 候选做导演评审：应只评叠加层设计，不将字幕作为合格项",
        "③ 可选修复方向（均需人工授权、另立任务）："
        "a) 用真实 TTS 时长重建时间轴/字幕时间基；b) 让 TTS 适配声明时长（语速/停顿）；"
        "c) 字幕按实际音频重排并重烧（需重渲染全片）",
    ],
    "artifacts": {"sync_round1": str(SYNC1.relative_to(ROOT)), "sync_round2": str(SYNC2.relative_to(ROOT)),
                  "e2_execution_report": str(E2REP.relative_to(ROOT)),
                  "e2_review_prep": str(PREP.relative_to(ROOT))},
    "read_only": True, "executed_anything": False,
}
defect["candidate_sha256"] = sha(CAND)
defect["v9_sha256"] = sha(V9)
defect["defect_sha256"] = hashlib.sha256(
    json.dumps({k: v for k, v in defect.items() if k != "defect_sha256"}, sort_keys=True,
               ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
OUT.write_text(json.dumps(defect, ensure_ascii=False, indent=1), encoding="utf-8")

# 更正 E2 执行报告（自身产物）
rep = json.loads(E2REP.read_text(encoding="utf-8"))
rep["verify"]["audio"]["subtitle_sync_note"] = (
    "音频与 v9 逐字节一致（该结论不变）；但**字幕与旁白的对齐不成立**：全片字幕漂移，"
    "960 s 后无旁白仍有字幕（见 logs/phase6e_e2_subtitle_defect.json）。"
    "原『字幕正常/未受损』只证明像素与母版一致，属过度表述，已更正。")
rep["corrections"] = rep.get("corrections", []) + [{
    "what": "字幕结论", "old": "字幕正常/未受损（仅像素存在与一致性）",
    "new": "字幕与旁白失同步（全片，继承自 v9；960 s 后无旁白）；E2 未改字幕但不改变该缺陷",
    "why": "人工报告 + 音频/字幕时间基测量确认", "at": "E2 candidate human review"}]
rep["report_sha256"] = hashlib.sha256(
    json.dumps({k: v for k, v in rep.items() if k != "report_sha256"}, sort_keys=True,
               ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
E2REP.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")

# 审查准备：把 Q6/Q8 相关结论标注为受该缺陷影响
prep = json.loads(PREP.read_text(encoding="utf-8"))
prep["subtitle_defect_ref"] = str(OUT.relative_to(ROOT))
for c in prep["checklist"]:
    if c["id"] in ("Q6", "Q8", "Q9"):
        c["affected_by_defect"] = "SUBTITLE_AUDIO_DESYNC（全片继承自 v9；见缺陷记录）"
        c["machine_evidence"]["subtitle_sync"] = "不成立：字幕与旁白失同步（960 s 后无旁白）"
prep["report_sha256"] = hashlib.sha256(
    json.dumps({k: v for k, v in prep.items() if k != "report_sha256"}, sort_keys=True,
               ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
PREP.write_text(json.dumps(prep, ensure_ascii=False, indent=1), encoding="utf-8")


def entry_sha(r):
    b = {k: v for k, v in r.items() if k != "entry_sha256"}
    return hashlib.sha256(json.dumps(b, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


rows = [json.loads(x) for x in LEDGER.read_text(encoding="utf-8").splitlines() if x.strip()]
DID = "6E-E2-SUBTITLE-DEFECT-v1"
if not any(e.get("defect_id") == DID for e in rows):
    r = {"schema": "defect-record-v1", "stage": "6-E", "defect_id": DID,
         "status": defect["status"], "severity": defect["severity"],
         "human_report": defect["human_report"],
         "root_cause_summary": "脚本声明旁白 1530.0 s vs 真实 TTS 961.656 s（少 568.3 s）⇒ "
                               "字幕按声明时长铺开、逐段累积漂移；960 s 后无旁白仍有字幕",
         "introduced_by_e2": False, "inherited_from": "v9",
         "candidate_sha256": defect["candidate_sha256"],
         "defect_sha256": defect["defect_sha256"],
         "e2_acceptance_blocked_by_this": True,
         "corrections": [c["claim"] for c in defect["corrections_to_prior_claims"]],
         "decided_by": "agent:read-only-defect-verification",
         "provenance": "人工报告触发；只读测量确认；未执行任何 proposal",
         "read_only": True, "enforced": False, "advisory": True, "executes_changes": False}
    r["seq"] = len(rows) + 1
    r["prev_sha256"] = rows[-1]["entry_sha256"] if rows else ""
    r["entry_sha256"] = entry_sha(r)
    with open(LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("登记 seq", r["seq"], "| defect_id", DID)
prev, ok = "", True
rows2 = [json.loads(x) for x in LEDGER.read_text(encoding="utf-8").splitlines() if x.strip()]
for i, e in enumerate(rows2, start=1):
    if e["seq"] != i or e["prev_sha256"] != prev or e["entry_sha256"] != entry_sha(e):
        ok = False
        break
    prev = e["entry_sha256"]
print("ledger", len(rows2), "chain_ok", ok)
print("缺陷:", defect["status"], "|", defect["severity"])
print("脚本 {:.1f}s vs 音频 {:.1f}s ⇒ 差 {:.1f}s | 旁白结束于 ~{}s | 字幕排到 1530s".format(
    defect["root_cause"]["numbers"]["script_narration_s"],
    defect["root_cause"]["numbers"]["voice_total_s"],
    defect["root_cause"]["numbers"]["voice_vs_script_delta_s"], narr_end))
print("E2 未改字幕（母版 vs 候选字幕带一致）:", all(x["identical"] for x in
                                              s2["subtitle_band_master_vs_candidate"]))
print("json ->", OUT)
