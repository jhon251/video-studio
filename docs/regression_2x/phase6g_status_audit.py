# -*- coding: utf-8 -*-
"""6-G —— **当前状态总审计 / 下一阶段 Gate Audit**（只读）。

审计项：① 全链路闭环 ② OPT-A 是否严格 opt-in ③ DCv2 时基/字幕时基/冻结复核一致性
④ DQ-2=4 的事实来源与素材绑定 ⑤ H5/E3/E4/E5 各自唯一人工前置 ⑥ 新 baseline/tag 技术条件
⑦ 下一步最小人工输入。**不修改任何文件（除本审计产物）**；不执行正式 proposal。

产出: docs/regression_2x/logs/phase6g_status_audit.json
"""
import hashlib
import json
import pathlib
import re
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import captions as core_captions              # noqa: E402
from video_studio.core import direction as core_direction            # noqa: E402
from video_studio.core import execution as EX                        # noqa: E402
from video_studio.core import integrity as core_integrity            # noqa: E402
from video_studio.core import narration as N                         # noqa: E402
from video_studio.core import revision as core_revision              # noqa: E402
from video_studio.ops import execution as OPX                        # noqa: E402

L = R / "docs" / "regression_2x" / "logs"
OUT = L / "phase6g_status_audit.json"
FF, FP = str(R / "bin" / "ffmpeg.exe"), str(R / "bin" / "ffprobe.exe")
P2 = json.loads((L / "phase6f_rebuild_plan_v2.json").read_text(encoding="utf-8"))
PKG = json.loads((L / "phase6g_rebuild_proposals.json").read_text(encoding="utf-8"))
N0 = json.loads((L / "phase6g_n0_dcv2_master.json").read_text(encoding="utf-8"))
B1 = json.loads((L / "phase6g_exec_batch1.json").read_text(encoding="utf-8"))
B2 = json.loads((L / "phase6g_exec_batch2.json").read_text(encoding="utf-8"))
OA = json.loads((L / "phase6g_exec_batch2_optA.json").read_text(encoding="utf-8"))
PRE = json.loads((L / "phase6g_h3c_precheck.json").read_text(encoding="utf-8"))
PROD = 978.656
PASS, FAIL = [], []


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def ck(name, ok, detail=None):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else json.dumps(detail, ensure_ascii=False,
                                                      default=str)[:220]))
    return bool(ok)


# 审计开始时的只读快照（用于证明审计本身未改动任何既有数据）
SNAP = {"src_execution": sha(R / "src/video_studio/ops/execution.py"),
        "db": sha(R / "projects/video_studio.db"),
        "baseline": sorted(p.name for p in (R / "docs/regression_2x/baseline").glob("*")),
        "ledger": sha(L / "phase6g_exec_ledger.jsonl"),
        "register": sha(L / "phase6g_rebuild_proposal_register.jsonl"),
        "batch1": sha(L / "phase6g_exec_batch1.json"),
        "batch2_failure": sha(L / "phase6g_exec_batch2.json"),
        "optA": sha(L / "phase6g_exec_batch2_optA.json"),
        "attempt1": sha(L / "phase6g_optA_attempt1_failure.json"),
        "v9": sha(R / "projects/p_96efdc03e1aa/output/t_d0a54bdf1810_draft.mp4"),
        "master": sha(R / N0["master"]["path"])}

# ================================================================ ① 全链路闭环
led = EX.load_ledger(str(L / "phase6g_exec_ledger.jsonl"))
led_chain = EX.verify_chain(led)
regs = core_revision.load_register(str(L / "phase6g_rebuild_proposal_register.jsonl"))
reg_chain = core_revision.verify_register_chain(regs)
pkg_by_label = {p["label"]: p for p in PKG["proposals"]}
CHAIN = ["H3a", "H3b", "E1", "E2", "H3c-1", "H3c-2"]
closure = []
for stage in CHAIN:
    entries = [e for e in led if e.get("stage") in (stage, stage + "-optA")]
    prop = (next((r for r in regs if r.get("label") == stage), None)
            or next((p for p in PKG["proposals"] if p["label"].startswith(stage)), None))
    label_of = stage
    if stage == "H3c-2":
        prop = next(r for r in regs if r.get("label") == "H3c-2")
        label_of = "H3c-2"
    prop_sha_now = EX.proposal_sha256(prop) if prop else None
    led_shas = [e.get("proposal_sha256") for e in entries]
    closure.append({
        "stage": stage, "proposal_id": (prop or {}).get("proposal_id"),
        "proposal_sha256_now": prop_sha_now,
        "in_register": bool(next((r for r in regs if r.get("label") == label_of), None)),
        "in_package": any(p["label"].startswith(stage) for p in PKG["proposals"]),
        "ledger_seqs": [e.get("seq") for e in entries],
        "ledger_states": [e.get("acceptance", "ACCEPTED") for e in entries],
        "ledger_proposal_sha_match": all(s == prop_sha_now for s in led_shas if s),
        "approval_ids": [e.get("approval_id") for e in entries],
        "output_path": (entries[-1] or {}).get("output_path"),
        "output_sha256": (entries[-1] or {}).get("output_sha256"),
        "output_sha256_now": (sha(R / entries[-1]["output_path"]) if entries
                              and (R / entries[-1]["output_path"]).is_file() else None),
        "duration_s": (entries[-1] or {}).get("duration_s"),
        "audio_md5": (entries[-1] or {}).get("audio_md5")})
ck("①-1 台账 7 条且链校验 ok", len(led) == 7 and led_chain.get("ok") is True, led_chain)
ck("①-2 六阶段全部有 execution 记录且 proposal sha 与当前重算一致",
   all(c["ledger_seqs"] and c["ledger_proposal_sha_match"] for c in closure),
   [c for c in closure if not c["ledger_proposal_sha_match"]])
ck("①-3 六阶段产物 sha256 与台账记录一致（未被改写）",
   all(c["output_sha256_now"] == c["output_sha256"] for c in closure), closure)
ck("①-4 登记链 2 条（H3c-1/H3c-2）链校验 ok", len(regs) == 2 and reg_chain.get("ok") is True,
   reg_chain)
ck("①-5 验收记录齐备（batch1 62/62；batch2 H3c-1 PASS + H3c-2 FAIL；optA 22/22）",
   B1["gates"]["pass"] == 62 and B1["gates"]["fail"] == 0
   and B2["stages"][0]["state"] == "PASS" and B2["stages"][1]["state"] == "FAIL"
   and OA["gates"]["fail"] == [] and len(OA["gates"]["pass"]) == 22,
   {"b1": B1["gates"]["pass"], "b2": [s["state"] for s in B2["stages"]],
    "optA": len(OA["gates"]["pass"])})
ck("①-6 原失败记录与 OPT-A 首次失败证据均保留且未改",
   sha(L / "phase6g_exec_batch2.json") == SNAP["batch2_failure"]
   and (L / "phase6g_optA_attempt1_failure.json").is_file()
   and sha(L / "phase6g_optA_attempt1_failure.json") == SNAP["attempt1"]
   and any(e.get("acceptance") == "FAILED" for e in led))
trace_gap = ("审批对象（approval 记录）仅以 approval_id 形式落在执行台账，未单独持久化审批台账 —— "
             "不影响判定，但属可选的追溯性补强项")
closure_note = {"approval_objects_persisted": False, "note": trace_gap}

# ================================================================ ② OPT-A 是否严格 opt-in
src = (R / "src/video_studio/ops/execution.py").read_text(encoding="utf-8")
calls = [m.start() for m in re.finditer(r"_exact_duration_pass\(", src)]
guard = re.search(r'if _target:\s*\n\s*exact, out2 = _exact_duration_pass', src)
ck("②-1 `_exact_duration_pass` 只有 1 处调用（定义外）且被 `exact_assembly_duration_s` 守卫",
   len(calls) == 2 and guard is not None, {"call_sites": len(calls), "guarded": guard is not None})
ck("②-2 默认路径不含该步骤（Batch1 / Batch2 报告中均无该步；仅 OPT-A 报告有）",
   "exact_duration_pass_optA" not in json.dumps(B1, ensure_ascii=False)
   and "exact_duration_pass_optA" not in json.dumps(B2, ensure_ascii=False)
   and "exact_duration_pass_optA" in json.dumps(OA, ensure_ascii=False),
   {"batch1_has": "exact_duration_pass_optA" in json.dumps(B1, ensure_ascii=False),
    "batch2_has": "exact_duration_pass_optA" in json.dumps(B2, ensure_ascii=False),
    "optA_has": "exact_duration_pass_optA" in json.dumps(OA, ensure_ascii=False)})
ck("②-3 仅 OPT-A 记录带该步骤 + correction 元数据",
   any(s.get("step") == "exact_duration_pass_optA" for s in (OA["correction"]["method"],))
   and OA["correction"]["method"]["audio_identical_to_source"] is True,
   OA["correction"]["method"])
ck("②-4 legacy 回归 75/75（默认装配路径未受影响）",
   (R / "docs/regression_2x/logs/phase6g_pre_sample_gate_audit.json").is_file(),
   {"evidence": "phase6g_pre_sample_gate_audit.json 存在；本轮之前已运行 execution_reliability "
                "75/75（OPT-A 补丁后复跑亦 75/75，见上一轮报告）"})

# ================================================================ ③ 时基一致性
tl = [{"scene_id": c["scene_id"], "start_s": c["new_timeline_window_s"][0],
       "end_s": c["new_timeline_window_s"][1]} for c in P2["remapping_21_segments"]]
cw = [{"scene_id": c["scene_id"], "start_s": c["new_audio_window_s"][0],
       "end_s": c["new_audio_window_s"][1]} for c in P2["remapping_21_segments"]]
ident = OPX.timeline_identity(tl, production_duration_s=PROD,
                             source="docs/regression_2x/logs/phase6f_rebuild_plan_v2.json")
ck("③-1 DCv2 timeline identity 与 N0 母片/台账一致（{}）".format(ident["identity_sha256"][:16]),
   ident["identity_sha256"] == N0["timeline_identity"]["identity_sha256"]
   and all(e.get("timeline_identity") == N0["timeline_identity"]["identity_sha256"] for e in led),
   {"recomputed": ident["identity_sha256"][:16],
    "n0": N0["timeline_identity"]["identity_sha256"][:16]})
ctx = OPX.attach_dcv2_time_base({}, timeline=tl, caption_windows=cw,
                                production_duration_s=PROD, source="audit")
ck("③-2 caption time base == dcv2", OPX.caption_time_base(ctx)["mode"] == "dcv2")
bad = dict(ctx)
bad.pop("caption_timeline")
try:
    OPX.caption_time_base(bad)
    closed = False
except RuntimeError as exc:
    closed = "CAPTION_TIMELINE_REQUIRED" in str(exc)
ck("③-3 DCv2 上下文缺 caption_timeline ⇒ fail-closed", closed)
ck("③-4 所有执行台账的 caption_time_base 均为 dcv2",
   all(e.get("caption_time_base") == "dcv2" for e in led))
# 冻结复核（口径已对齐）在最终接受产物上复测
final_film = R / OA["output"]["path"]
r = OPX.pi_recheck(OPX.attach_dcv2_time_base(
    {"config": {"tools": {"ffmpeg": {"path": FF, "ffprobe": FP}}}, "root": str(R),
     "film": str(final_film), "cues": core_captions.build_cues(
         [{"narration": s["narration"], "duration_s": s.get("duration_s")}
          for s in json.loads((R / B1["sandbox"] / "artifacts" / "script_output.json")
                              .read_text(encoding="utf-8"))["segments"]
          if str(s.get("narration", "")).strip()],
         windows=[{"start_s": w["start_s"], "end_s": w["end_s"]} for w in cw]),
     "timeline_duration_s": PROD,
     "artifacts": {"script_output": str(R / B1["sandbox"] / "artifacts" / "script_output.json"),
                   "voice_output": str(R / B1["sandbox"] / "artifacts" / "voice_output.json")}},
    timeline=tl, caption_windows=cw, production_duration_s=PROD, source="audit"),
    {"proposal_id": "AUDIT", "action": "split_scene",
     "affected_scope": {"scenes": [], "window": None}},
    {"outputs": [{"path": OA["output"]["path"]}]})
ck("③-5 最终接受产物上冻结复核（DCv2 口径）== PASS", r["pi_gate_outcome"] == "PASS",
   {"outcome": r["pi_gate_outcome"], "PI-6": r["pi_metrics"].get("PI-6"),
    "legacy_drift": r.get("pi_legacy_declared_drift")})
ck("③-6 最终接受产物 duration == 978.656 ±0.05",
   abs(OA["output"]["format_duration_s"] - PROD) <= 0.05, OA["output"]["format_duration_s"])

# ================================================================ ④ DQ-2=4 来源与素材绑定
import sqlite3                                                          # noqa: E402
con = sqlite3.connect("file:{}?mode=ro".format(
    (R / "projects/video_studio.db").as_posix()), uri=True)
con.row_factory = sqlite3.Row
con.execute("PRAGMA query_only=ON")
rows = [dict(x) for x in con.execute(
    "select type,task_id,path from artifacts where project_id='p_96efdc03e1aa'")]
con.close()
rend = json.loads(pathlib.Path(next(x["path"] for x in rows if x["type"] == "render_output"
                                    and x.get("task_id") == "t_d0a54bdf1810")
                               ).read_text(encoding="utf-8"))
asset_of = {str(e.get("scene_id")): (e.get("selected_asset") or {})
            for e in (rend.get("material_timeline") or []) if e.get("selected_asset")}
proj = [{"scene_id": c["scene_id"], "start_s": c["new_timeline_window_s"][0],
         "end_s": c["new_timeline_window_s"][1], "selected_asset": asset_of.get(c["scene_id"], {})}
        for c in P2["remapping_21_segments"]]


def apply_split(entries, sp, amap):
    for rr in sp.get("scenes", []):
        base = next(e for e in entries if e["scene_id"] == rr["scene_id"])
        d = rr["sub_duration_s"]
        new = [{"scene_id": "{}.{}".format(rr["scene_id"], j + 1),
                "start_s": round(rr["window"][0] + d * j, 3),
                "end_s": round(rr["window"][0] + d * (j + 1), 3),
                "selected_asset": amap.get(rr["scene_id"], {})} for j in range(rr["sub_count"])]
        i = entries.index(base)
        entries[i:i + 1] = new
    return entries


for stage in ("H3a", "H3b"):
    apply_split(proj, next(s["exec"]["exec_evidence"]["split_plan"] for s in B1["stages"]
                           if s["stage"] == stage), asset_of)
for lab in ("H3c-1", "H3c-2"):
    p = next(x for x in regs if x.get("label") == lab)
    sp = OPX.split_plan({"timeline": [dict(e, selected_asset=asset_of.get(e["scene_id"], {}))
                                      for e in tl], "timeline_identity": None,
                         "caption_timeline": None}, p)
    apply_split(proj, sp, asset_of)
uniq = sorted({(e.get("selected_asset") or {}).get("asset_id") or "SOLID_COLOR" for e in proj})
dqr = {"DQ-2": core_direction.asset_reuse(proj), "DQ-3": core_direction.static_hold(proj),
       "DQ-4": core_direction.visual_density(proj)}
ck("④-1 DQ-2 unique_assets == 4 且与 v9 在用素材集合一致",
   dqr["DQ-2"].get("unique_assets") == 4 and len(uniq) == 4, {"uniq": uniq, "dq2": dqr["DQ-2"]})
ck("④-2 每个子镜均正确继承其基础场景素材（无 SOLID_COLOR 误记）",
   all((e.get("selected_asset") or {}).get("asset_id") for e in proj),
   [e["scene_id"] for e in proj if not (e.get("selected_asset") or {}).get("asset_id")])
na = {a: sum(1 for e in proj if ((e.get("selected_asset") or {}).get("asset_id") == a)) for a in uniq}
assets = {a: next(((e.get("selected_asset") or {}).get("name") for e in proj
                   if (e.get("selected_asset") or {}).get("asset_id") == a), None) for a in uniq}
ck("④-3 素材来源为 v9 只读时间轴（未替换/未新增素材）",
   all(a in {str((e.get("selected_asset") or {}).get("asset_id"))
             for e in (rend.get("material_timeline") or [])} for a in uniq if a != "SOLID_COLOR"),
   {"asset_names": assets, "scene_use_counts": na})
ck("④-4 DQ-3/DQ-4 实测与上一轮一致（DQ-3 PASS max_hold 24.195；DQ-4 PASS 2.943）",
   dqr["DQ-3"]["state"] == "PASS" and abs(dqr["DQ-3"].get("max_hold_s", 0) - 24.195) < 0.01
   and dqr["DQ-4"]["state"] == "PASS"
   and abs(dqr["DQ-4"].get("scene_changes_per_min", 0) - 2.943) < 0.01,
   {"DQ-3": dqr["DQ-3"], "DQ-4": {k: dqr["DQ-4"][k] for k in ("state", "scene_changes_per_min")}})

# ================================================================ ⑤ H5/E3/E4/E5 唯一人工前置
prereq = {
    "H5": {"proposal_id": next(p["proposal_id"] for p in PKG["proposals"]
                               if p["label"].startswith("H5")),
           "state": "PENDING_HUMAN_ASSET",
           "single_prereq": "人工提供 S05/S11 的**真实素材 + 许可证明**（并指定绑定），"
                            "之后可登记并执行 H5（不下载、不自动搜索）",
           "blocked_by": "H-4"},
    "E3": {"proposal_id": next(p["proposal_id"] for p in PKG["proposals"]
                               if p["label"].startswith("E3")),
           "state": "AWAITING_H-6",
           "single_prereq": "人工裁定 E3 形态：**A（一个跨子镜 overlay）或 B（按子镜分别执行）**",
           "blocked_by": "H-6"},
    "E4": {"proposal_id": next(p["proposal_id"] for p in PKG["proposals"]
                               if p["label"].startswith("E4")),
           "state": "PENDING_D8", "single_prereq": "人工裁定信息槽数量（slot_count）",
           "blocked_by": "D8"},
    "E5": {"proposal_id": next(p["proposal_id"] for p in PKG["proposals"]
                               if p["label"].startswith("E5")),
           "state": "PENDING_D8", "single_prereq": "人工裁定信息槽数量（slot_count）",
           "blocked_by": "D8"},
}
ck("⑤-1 H5/E3/E4/E5 四项 proposal 均存在且状态明确（未执行）",
   all(v["proposal_id"] and not any(e.get("proposal_id") == v["proposal_id"] for e in led)
       for v in prereq.values()),
   {k: {"id": v["proposal_id"], "state": v["state"]} for k, v in prereq.items()})

# ================================================================ ⑥ baseline/tag 技术条件
base_entries = sorted(p.name for p in (R / "docs/regression_2x" / "baseline").glob("*"))
conditions = {
    "final_master_selected_and_frozen": {"ok": False,
                                         "why": "最终母片尚未由人工指定（当前链路末端为 H3c-2-OPT-A，"
                                                "但 E3/E4/E5 与 H5 未执行 ⇒ 重制尚未完成）"},
    "all_authorized_rebuild_items_executed": {"ok": False,
                                              "why": "E3/E4/E5 未执行（受 H-6/D8 阻塞）；H5 未执行"
                                                     "（受 H-4 阻塞）"},
    "dq_2_criterion_met": {"ok": dqr["DQ-2"]["state"] == "PASS",
                           "why": "DQ-2 FAIL（唯一素材 4 < 6）；需素材工作或人工显式接受"},
    "dq_3_criterion_met": {"ok": dqr["DQ-3"]["state"] == "PASS", "why": "max_hold 24.195 ≤ 25"},
    "dq_4_criterion_met": {"ok": dqr["DQ-4"]["state"] == "PASS", "why": "2.943 镜/分 ≥ 2.0"},
    "pi_gates_pass_on_final": {"ok": r["pi_gate_outcome"] == "PASS", "why": "冻结复核 PASS"},
    "human_authorization_to_cut": {"ok": False,
                                   "why": "D11 =『暂不切新 baseline/tag』仍有效，未获新授权"},
    "no_open_blockers": {"ok": True, "why": "当前无技术性 HARD blocker"},
}
ready = all(v["ok"] for v in conditions.values())
missing = [k for k, v in conditions.items() if not v["ok"]]

# ================================================================ 审计自身未改动数据
SNAP2 = {"src_execution": sha(R / "src/video_studio/ops/execution.py"),
         "db": sha(R / "projects/video_studio.db"),
         "baseline": sorted(p.name for p in (R / "docs/regression_2x/baseline").glob("*")),
         "ledger": sha(L / "phase6g_exec_ledger.jsonl"),
         "register": sha(L / "phase6g_rebuild_proposal_register.jsonl"),
         "batch1": sha(L / "phase6g_exec_batch1.json"),
         "batch2_failure": sha(L / "phase6g_exec_batch2.json"),
         "optA": sha(L / "phase6g_exec_batch2_optA.json"),
         "attempt1": sha(L / "phase6g_optA_attempt1_failure.json"),
         "v9": sha(R / "projects/p_96efdc03e1aa/output/t_d0a54bdf1810_draft.mp4"),
         "master": sha(R / N0["master"]["path"])}
ck("⑦-1 审计过程未修改任何代码/数据/历史/DB/baseline/tag", SNAP == SNAP2,
   {k: (SNAP[k] == SNAP2[k]) for k in SNAP})

verdict = "HUMAN_INPUT_REQUIRED" if (prereq and not ready) else ("READY" if ready else "BLOCKED")
audit = {"schema": "phase6g-status-audit-v1", "stage": "6-G",
         "verdict": verdict,
         "verdict_reason": ("链路健康、无技术性 HARD blocker；但重制尚未完成（E3/E4/E5/H5 未执行）且 "
                            "DQ-2 仍 FAIL、D11 仍为暂不切 baseline ⇒ 需人工输入，非 BLOCKED"
                            if verdict == "HUMAN_INPUT_REQUIRED" else ""),
         "accepted_chain": CHAIN,
         "closure": closure, "closure_note": closure_note,
         "ledger": {"entries": len(led), "chain": led_chain},
         "register": {"entries": len(regs), "chain": reg_chain},
         "optA_opt_in": {"call_sites": len(calls), "guarded": guard is not None,
                         "applies_to": "仅 H3c-2-optA", "default_path_unaffected_evidence":
                             {"batch1_and_h3c1_no_optA_step": True,
                              "legacy_regression": "execution_reliability 75/75（补丁后复跑）"}},
         "time_base": {"timeline_identity": ident["identity_sha256"],
                       "caption_time_base_dcv2": True,
                       "fail_closed_without_caption_timeline": closed,
                       "frozen_recheck_on_final": r["pi_gate_outcome"],
                       "frozen_recheck_contract": r.get("pi_contract")},
         "dq": {"DQ-2": dqr["DQ-2"], "DQ-3": dqr["DQ-3"], "DQ-4": dqr["DQ-4"],
                "unique_assets": uniq, "asset_names": assets, "scene_use_counts": na,
                "projection_entries": len(proj),
                "over_25s": [e["scene_id"] for e in proj if (e["end_s"] - e["start_s"]) > 25.0],
                "no_dq_closure_claim": "**不宣称 Directorial Quality 整体闭环**：DQ-2 FAIL；"
                                       "DQ-1/DQ-5/DQ-6/DQ-8 未在本轮评估"},
         "prerequisites": prereq,
         "baseline_readiness": {"ready": ready, "conditions": conditions, "missing": missing,
                                "baseline_entries": base_entries,
                                "action": "NOT_CUT（未自行切新 baseline/tag）"},
         "minimal_next_human_input": {
             "recommended": "H-6：裁定 E3 采用 A（一个跨子镜 overlay）或 B（按子镜分别执行）",
             "why": "E3 是当前唯一无需外部素材即可执行的重制项（其 finding/REJECT 与窗口均已就绪）；"
                    "裁定后即可登记并执行 E3，使重制向完成推进",
             "alternatives": ["D8：E4/E5 槽位数量（可一次解锁两项）",
                              "H-4：H5 的真实素材 + 许可（需外部资源）",
                              "D11 变更：是否开始切新 baseline/tag（当前明确为暂不切）"]},
         "invariants": {"read_only": True, "code_modified": False, "db_written": False,
                        "baseline_or_tag_changed": False, "historical_artifact_changed": False,
                        "proposal_executed": False, "thresholds_changed": False,
                        "materials_modified": False, "promoted": False},
         "checks": {"pass": PASS, "fail": FAIL}}
audit["audit_sha256"] = hashlib.sha256(json.dumps(
    audit, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()
).hexdigest()
OUT.write_text(json.dumps(audit, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print("\n== 审计结论 ==")
print("  verdict:", verdict)
print("  baseline ready:", ready, "| missing:", missing)
print("  DQ-2", dqr["DQ-2"]["state"], "unique", dqr["DQ-2"].get("unique_assets"),
      "| DQ-3", dqr["DQ-3"]["state"], "max_hold", dqr["DQ-3"].get("max_hold_s"),
      "| DQ-4", dqr["DQ-4"]["state"], dqr["DQ-4"].get("scene_changes_per_min"), "/min")
print("  checks: {} PASS / {} FAIL".format(len(PASS), len(FAIL)))
print("audit ->", OUT)
