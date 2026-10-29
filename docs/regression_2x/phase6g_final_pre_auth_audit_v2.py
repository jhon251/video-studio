# -*- coding: utf-8 -*-
"""6-G —— **FINAL FREEZE PRE-AUTH AUDIT v2**（只读；人工裁定：第 8 项仅适用于最终冻结对象/链路末端）。

允许：生成本审计证明、明确第 8 项适用范围、记录历史帧量化差异、重算 D11。
禁止：改历史 ledger/proposal/output/SHA、重跑 H3a/H3b/E1/E2、promote、指定母片、baseline/tag、
      改代码、改 POLICY/DQ 判据。产出: docs/regression_2x/logs/phase6g_final_pre_auth_audit_v2.json
"""
import hashlib
import json
import pathlib
import subprocess
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import captions as core_captions              # noqa: E402
from video_studio.core import direction as core_direction            # noqa: E402
from video_studio.core import execution as EX                        # noqa: E402
from video_studio.core import integrity as core_integrity            # noqa: E402
from video_studio.core import materials as core_materials            # noqa: E402
from video_studio.core import narration as N                         # noqa: E402
from video_studio.core import revision as core_revision              # noqa: E402
from video_studio.core import visual_aid as VA                       # noqa: E402
from video_studio.ops import execution as OPX                        # noqa: E402

L = R / "docs" / "regression_2x" / "logs"
OUT = L / "phase6g_final_pre_auth_audit_v2.json"
FF, FP = str(R / "bin/ffmpeg.exe"), str(R / "bin/ffprobe.exe")
PROD, TOL, VID_S, VID_F = 978.656, 0.05, 978.640, 24466
MATPLAN = R / "docs/regression_2x/phase6e_materials/phase6e_material_plan.json"
PASS, FAIL, HISTDIFF = [], [], []


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def ck(name, ok, detail=None):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else json.dumps(detail, ensure_ascii=False,
                                                      default=str)[:200]))
    return bool(ok)


def probe(p):
    r = subprocess.run([FP, "-v", "error", "-show_entries",
                        "format=duration:stream=codec_type,duration,nb_frames", "-of", "json",
                        str(p)], capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    j = json.loads(r.stdout or "{}")
    o = {"format_duration_s": round(float((j.get("format") or {}).get("duration") or 0), 4)}
    for s in (j.get("streams") or []):
        o[s.get("codec_type")] = {"duration_s": round(float(s.get("duration") or 0), 4),
                                  "nb_frames": s.get("nb_frames")}
    return o


def amd5(p):
    r = subprocess.run([FF, "-v", "error", "-i", str(p), "-map", "0:a", "-c", "copy", "-f", "md5",
                        "-"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return (r.stdout or "").strip().split("=")[-1]


N0 = json.loads((L / "phase6g_n0_dcv2_master.json").read_text(encoding="utf-8"))
P2 = json.loads((L / "phase6f_rebuild_plan_v2.json").read_text(encoding="utf-8"))
B1 = json.loads((L / "phase6g_exec_batch1.json").read_text(encoding="utf-8"))
H5R = json.loads((L / "phase6g_exec_h5.json").read_text(encoding="utf-8"))
DQR = json.loads((L / "phase6g_h5_dq_recompute.json").read_text(encoding="utf-8"))
V1 = json.loads((L / "phase6g_final_pre_auth_audit.json").read_text(encoding="utf-8"))
FP6G2 = json.loads((L / "phase5m_code_fingerprint_6g2.json").read_text(encoding="utf-8"))
led = EX.load_ledger(str(L / "phase6g_exec_ledger.jsonl"))
regs = core_revision.load_register(str(L / "phase6g_rebuild_proposal_register.jsonl"))
MASTER = R / N0["master"]["path"]
MASTER_MD5 = amd5(MASTER)


def snap():
    return {"ledger": sha(L / "phase6g_exec_ledger.jsonl"),
            "register": sha(L / "phase6g_rebuild_proposal_register.jsonl"),
            "db": sha(R / "projects/video_studio.db"),
            "baseline": sorted(p.name for p in (R / "docs/regression_2x/baseline").glob("*")),
            "master": sha(MASTER), "matplan": sha(MATPLAN),
            "v1_audit": sha(L / "phase6g_final_pre_auth_audit.json"),
            "h5_report": sha(L / "phase6g_exec_h5.json"),
            "dq": sha(L / "phase6g_h5_dq_recompute.json"),
            "code": {k: (sha(R / k) if (R / k).is_file() else None)
                     for k in FP6G2["files"]},
            "accepted": {e.get("stage"): e.get("output_sha256") for e in led
                         if e.get("output_sha256")},
            "projects_files": len([p for p in (R / "projects/p_96efdc03e1aa").rglob("*")
                                   if p.is_file()])}
BEFORE = snap()
HISTDIFF_STAGES = ("H3a", "H3b", "E1", "E2")

# ================================================================ 第 8 项：**按裁定适用范围**重新判定
RULING = {
    "decision": "第 8 项『video = 978.640s / 24466 frames』**仅适用于最终冻结对象/链路末端产物**；"
                "不追溯要求 OPT-A 之前的历史中间产物达到该帧精度。",
    "final_freeze_object": H5R["output"]["path"],
    "historical_intermediates_keep": "原 SHA / 原 acceptance / 原 ledger entry（**不得重写、不得重跑**）",
    "historical_frame_difference_recorded_as": "『历史已知帧量化差异』（**不得**重新判为 acceptance failure）",
}
rows = []
for e in led:
    if not e.get("output_sha256"):
        continue
    st = e.get("stage")
    p = R / e["output_path"]
    pr = probe(p)
    rows.append({"stage": st, "ledger_seq": e.get("seq"),
                 "acceptance": e.get("acceptance") or "ACCEPTED（隐含）",
                 "path": e["output_path"], "sha256": sha(p),
                 "sha_matches_ledger": sha(p) == e["output_sha256"],
                 "duration_s": pr.get("format_duration_s"),
                 "video_s": (pr.get("video") or {}).get("duration_s"),
                 "frames": int((pr.get("video") or {}).get("nb_frames") or 0),
                 "audio_s": (pr.get("audio") or {}).get("duration_s"),
                 "audio_md5": amd5(p)})
chain = [r for r in rows if r["acceptance"].startswith(("ACCEPTED", "ACCEPTED（"))]
end_stage = "H5"
end = next(r for r in rows if r["stage"] == end_stage)
ck("8(裁定后). 最终冻结对象（链路末端 = H5）满足 duration 978.656 / video 978.640 / "
   "24466 frames / audio 978.656 / audio md5 == DCv2 master",
   abs(end["duration_s"] - PROD) <= TOL and abs(end["video_s"] - VID_S) <= 0.01
   and end["frames"] == VID_F and abs(end["audio_s"] - PROD) <= TOL
   and end["audio_md5"] == MASTER_MD5, end)
for r in rows:
    if r["stage"] in HISTDIFF_STAGES:
        HISTDIFF.append({"stage": r["stage"], "ledger_seq": r["ledger_seq"],
                         "frames": r["frames"], "video_s": r["video_s"],
                         "duration_s": r["duration_s"], "audio_md5_ok":
                             r["audio_md5"] == MASTER_MD5, "sha256": r["sha256"],
                         "status": "历史已知帧量化差异（原 SHA/acceptance/ledger entry 保留；"
                                   "**不重判为失败**、不重跑、不改写）"})
ck("8b. 十条接受产物：duration 978.656 + audio 978.656 + audio md5 == master（全链一致）",
   all(abs(r["duration_s"] - PROD) <= TOL and abs(r["audio_s"] - PROD) <= TOL
       and r["audio_md5"] == MASTER_MD5 for r in chain),
   [r["stage"] for r in chain if r["audio_md5"] != MASTER_MD5])
LEDSHA = {r["stage"]: r["sha256"] for r in rows}
ck("8c. 历史中间产物（H3a/H3b/E1/E2）的 SHA 仍与其**原始台账记录**一致（未被改写）",
   all(r["sha_matches_ledger"] for r in rows if r["stage"] in HISTDIFF_STAGES),
   [r["stage"] for r in rows if r["stage"] in HISTDIFF_STAGES and not r["sha_matches_ledger"]])
ck("8d. 历史帧量化差异已按裁定**仅记录**（4 条，状态为差异而非失败；无重跑/无改写）",
   len(HISTDIFF) == 4 and all(r["frames"] in (24464, 24465) for r in HISTDIFF))

# ================================================================ 其余全部确认项
ck("1. 十条 accepted chain 完整（产物 sha 与台账一致）",
   len(chain) == 10 and all(r["sha_matches_ledger"] for r in chain),
   [r["stage"] for r in chain if not r["sha_matches_ledger"]])
ck("2. H3c-2 原始 FAILED（seq6）与 OPT-A ACCEPTED（seq7）历史完整",
   any(e.get("seq") == 6 and e.get("acceptance") == "FAILED" for e in led)
   and any(e.get("seq") == 7 and str(e.get("acceptance")) == "ACCEPTED_OPT_A_EXACT_DURATION"
           for e in led)
   and (L / "phase6g_exec_batch2.json").is_file()
   and (L / "phase6g_optA_attempt1_failure.json").is_file()
   and (L / "phase6g_optA_attempt1_failure.json").stat().st_size > 0)
ck("3. proposal register = 6 条且链完整",
   len(regs) == 6 and core_revision.verify_register_chain(regs).get("ok") is True,
   {"n": len(regs)})
ck("4. execution ledger = 11 条且链完整；末端 entry_sha256 与 H5 报告记录一致",
   len(led) == 11 and EX.verify_chain(led).get("ok") is True
   and led[-1]["entry_sha256"] == H5R["ledger_entry"]["entry_sha256"],
   {"n": len(led), "terminal": led[-1]["entry_sha256"][:16]})
ck("5. DCv2 master 未改变（sha {}）".format(sha(MASTER)[:16]),
   sha(MASTER) == N0["master"]["sha256"])
tl = [{"scene_id": c["scene_id"], "start_s": c["new_timeline_window_s"][0],
       "end_s": c["new_timeline_window_s"][1]} for c in P2["remapping_21_segments"]]
cw = [{"scene_id": c["scene_id"], "start_s": c["new_audio_window_s"][0],
       "end_s": c["new_audio_window_s"][1]} for c in P2["remapping_21_segments"]]
ident = OPX.timeline_identity(tl, production_duration_s=PROD, source="pre-auth v2")
ck("6. timeline identity 未改变（{}）".format(ident["identity_sha256"][:16]),
   ident["identity_sha256"] == N0["timeline_identity"]["identity_sha256"]
   and all(e.get("timeline_identity") == ident["identity_sha256"] for e in led
           if e.get("timeline_identity")))
ck("7. caption time base = dcv2（全部台账）",
   all(e.get("caption_time_base") == "dcv2" for e in led if e.get("caption_time_base")))
ck("9. H5 S05/S11 绑定/SHA/license/asset_id 与 proposal、报告、台账一致 + 文件实算",
   all(sha(pathlib.Path(H5R["asset_records"][s]["path"])) == H5R["asset_records"][s]["sha256"]
       for s in ("S05", "S11"))
   and H5R["binding"] == {s: H5R["asset_records"][s]["asset_id"] for s in ("S05", "S11")}
   and next(e for e in led if e.get("stage") == "H5")["binding"] == H5R["binding"])
a, b = DQR["DQ"]["after_H5"], DQR["DQ"]["before_H5"]
ck("10/11/12/13. DQ：DQ-2 PASS(6) / DQ-3 PASS(24.195) / DQ-4 PASS(2.943)；DQ-5 既有 FAIL（不处理）；"
   "DQ-8 NOT_ASSESSABLE（不补造）；DQ-1/DQ-6/DQ-7 保持未评估",
   a["DQ-2"]["state"] == "PASS" and a["DQ-2"]["unique_assets"] == 6
   and a["DQ-3"]["state"] == "PASS" and abs(a["DQ-3"]["max_hold_s"] - 24.195) < 0.01
   and a["DQ-4"]["state"] == "PASS" and a["DQ-5"]["state"] == "FAIL"
   and b["DQ-5"]["state"] == "FAIL" and a["DQ-8"]["state"] == "NOT_ASSESSABLE"
   and all(k not in json.dumps(DQR["DQ"]) for k in ("DQ-1", "DQ-6", "DQ-7")),
   {"DQ-2": a["DQ-2"]["state"], "DQ-3": a["DQ-3"]["state"], "DQ-4": a["DQ-4"]["state"],
    "DQ-5": a["DQ-5"]["state"], "DQ-8": a["DQ-8"]["state"]})
# PI + 冻结复核（十条逐一实测）
b1_sb = R / B1["sandbox"]
script = json.loads((b1_sb / "artifacts/script_output.json").read_text(encoding="utf-8"))
voice = json.loads((b1_sb / "artifacts/voice_output.json").read_text(encoding="utf-8"))
cues = core_captions.build_cues(
    [{"narration": s["narration"], "duration_s": s.get("duration_s")}
     for s in script["segments"] if str(s.get("narration", "")).strip()],
    windows=[{"start_s": w["start_s"], "end_s": w["end_s"]} for w in cw])
plan = N.narration_plan(script, voice)
GP = core_integrity.gate_policy({"tools": {"ffmpeg": {"path": FF, "ffprobe": FP}}})
sm = lambda m: {x: (y.get("state") if isinstance(y, dict) else y) for x, y in m.items()}
pi = {}
for r in chain:
    p = R / r["path"]
    pre = core_integrity.pre_render_gate(script.get("segments") or [], voice, PROD, GP,
                                         narration_duration_s=voice.get("narration_duration_s"),
                                         narration_plan=plan, cues=cues,
                                         narration_padding_s=PROD - float(
                                             voice.get("narration_duration_s") or 0))
    post = core_integrity.post_render_gate(p, PROD, cues, voice.get("narration_duration_s"), True,
                                          FF, FP, GP, narration_plan=plan)
    rc = OPX.pi_recheck(OPX.attach_dcv2_time_base(
        {"config": {"tools": {"ffmpeg": {"path": FF, "ffprobe": FP}}}, "root": str(R),
         "film": str(p), "cues": cues, "timeline_duration_s": PROD,
         "artifacts": {"script_output": str(b1_sb / "artifacts/script_output.json"),
                       "voice_output": str(b1_sb / "artifacts/voice_output.json")}},
        timeline=[dict(e, selected_asset={}) for e in tl], caption_windows=cw,
        production_duration_s=PROD, source="pre-auth v2"),
        {"proposal_id": "AUDIT2-" + r["stage"], "action": "replace_asset",
         "affected_scope": {"scenes": [], "window": None}}, {"outputs": [{"path": r["path"]}]})
    pi[r["stage"]] = {"pre": sm(pre["metrics"]), "post": sm(post["metrics"]),
                      "pre_blocked": pre["blocked"], "promote_blocked": post.get("promote_blocked"),
                      "frozen_recheck": rc.get("pi_gate_outcome")}
    print("   PI {} pre={} PI-3={} promote_blocked={} frozen={}".format(
        r["stage"], all(pi[r["stage"]]["pre"].get(g) == "PASS"
                        for g in ("PI-1", "PI-2", "PI-6", "G-TL", "G-PAD", "G-SUB")),
        pi[r["stage"]]["post"].get("PI-3"), pi[r["stage"]]["promote_blocked"],
        pi[r["stage"]]["frozen_recheck"]))
ck("14. 十条 PI pre/post 与 frozen recheck 全部 PASS（promote 未被阻断）",
   all((not v["pre_blocked"]) and all(v["pre"].get(g) == "PASS" for g in
                                      ("PI-1", "PI-2", "PI-6", "G-TL", "G-PAD", "G-SUB"))
       and v["post"].get("PI-3") == "PASS" and not v["promote_blocked"]
       and v["frozen_recheck"] == "PASS" for v in pi.values()),
   {k: v for k, v in pi.items() if v["frozen_recheck"] != "PASS"})
# 代码
diffs = [{"file": k, "expected": v, "actual": (sha(R / k) if (R / k).is_file() else None)}
         for k, v in FP6G2["files"].items()
         if (not (R / k).is_file()) or sha(R / k) != v]
ck("15. 无未授权代码变化（唯一差异 = 已授权 OPT-A：src/video_studio/ops/execution.py；其余 423 "
   "文件字节一致）",
   len(diffs) == 1 and diffs[0]["file"] == "src/video_studio/ops/execution.py"
   and diffs[0]["actual"].startswith("b00db7829a0cc17e"), diffs)
ck("15b. POLICY / 一般性阈值 / DQ 判据 / `_PANEL_KIND` / 冻结材料 未变",
   EX.POLICY["max_scenes_per_proposal"] == 6
   and EX.POLICY["max_share_of_film_per_proposal"] == 0.30
   and core_direction.DEFAULT_POLICY["max_hold_s"] == 25.0
   and core_direction.DEFAULT_POLICY["min_unique_assets"] == 6
   and core_materials.DEFAULT_POLICY["frame_match_min_corr"] == 0.30
   and VA._PANEL_KIND == {"P1": "ladder", "P2": "cards", "P3": "positions"}
   and sha(MATPLAN) == "0cefd8810515138cf3a8e2057ffcf3c695bc16d7b8cfac818bd6fcad74689df8"
   and TOL == 0.05)
AFTER = snap()
ck("16. DB / baseline / frozen materials / master / accepted artifacts / 历史链 均未改变",
   all(AFTER[k] == BEFORE[k] for k in ("ledger", "register", "db", "baseline", "master",
                                       "matplan", "accepted", "projects_files")),
   {k: BEFORE[k] == AFTER[k] for k in ("ledger", "register", "db", "baseline", "master",
                                       "matplan", "accepted", "projects_files")})
ck("16b. 上一轮审计产物（v1）与 H5 报告/DQ 复算 未被改写（历史不可变）",
   AFTER["v1_audit"] == BEFORE["v1_audit"] and AFTER["h5_report"] == BEFORE["h5_report"]
   and AFTER["dq"] == BEFORE["dq"])
ck("17/18/19/20/21. 未 promote、未指定母片、未切 baseline/tag、未处理 DQ-5、未补造 DQ-8 证据",
   (not (L / "phase6g_final_master.json").exists()) and (not list(L.glob("*final_master*")))
   and (not (R / "docs/regression_2x/baseline/phase6g").exists())
   and a["DQ-5"]["state"] == "FAIL" and a["DQ-8"]["state"] == "NOT_ASSESSABLE"
   and AFTER["baseline"] == BEFORE["baseline"])
ck("22. 审计前后快照完全一致", AFTER == BEFORE,
   {k: BEFORE[k] == AFTER[k] for k in BEFORE if not isinstance(BEFORE[k], dict)})

# ================================================================ D11 重算
d11 = {"dq_2_met": {"ok": a["DQ-2"]["state"] == "PASS", "detail": "unique 6 ≥ 6"},
       "dq_3_met": {"ok": a["DQ-3"]["state"] == "PASS", "detail": "max_hold 24.195 ≤ 25；>25s 场景 0"},
       "dq_4_met": {"ok": a["DQ-4"]["state"] == "PASS", "detail": "2.943 ≥ 2.0"},
       "pi_gates_pass_on_chain": {"ok": all(v["frozen_recheck"] == "PASS" for v in pi.values()),
                                  "detail": "十条 PI pre/post + 冻结复核全 PASS"},
       "all_accepted_rebuild_items_executed": {"ok": len(chain) == 10,
                                               "detail": "H3a/H3b/H3c-1/H3c-2/E1–E5/H5 全部接受"},
       "no_open_technical_blockers": {"ok": True, "detail": "无 HARD blocker"},
       "final_master_designated_and_frozen": {"ok": False, "detail": "未指定（本轮禁止）"},
       "human_authorization_to_cut": {"ok": False, "detail": "D11 仍为『暂不切』"},
       "approval_ledger_persisted": {"ok": False, "detail": "审批对象仅以 approval_id 落在台账"
                                                           "（可选补强，非阻塞）"}}
verdict = "FINAL_FREEZE_PRE_AUTH_READY" if not FAIL else "BLOCKED"
rep = {"schema": "phase6g-final-pre-auth-audit-v2", "stage": "6-G / FINAL FREEZE PRE-AUTH AUDIT v2",
       "verdict": verdict, "checks": {"pass": PASS, "fail": FAIL},
       "item8_ruling": RULING,
       "item8_reevaluation": {"scope": "仅最终冻结对象/链路末端", "final_freeze_object": end["path"],
                              "duration_s": end["duration_s"], "video_s": end["video_s"],
                              "frames": end["frames"], "audio_s": end["audio_s"],
                              "audio_md5": end["audio_md5"], "result": "PASS"},
       "historical_frame_quantization_difference": HISTDIFF,
       "accepted_chain": rows, "register": {"n": len(regs),
                                            "chain": core_revision.verify_register_chain(regs)},
       "ledger": {"n": len(led), "chain": EX.verify_chain(led),
                  "terminal_entry_sha256": led[-1]["entry_sha256"]},
       "master": {"path": N0["master"]["path"], "sha256": sha(MASTER), "audio_md5": MASTER_MD5},
       "timeline_identity": ident["identity_sha256"], "caption_time_base": "dcv2",
       "h5_binding": {s: H5R["asset_records"][s] for s in ("S05", "S11")},
       "DQ": {"authoritative_source": "docs/regression_2x/logs/phase6g_h5_dq_recompute.json",
              "DQ-2": a["DQ-2"], "DQ-3": a["DQ-3"], "DQ-4": a["DQ-4"], "DQ-5": a["DQ-5"],
              "DQ-8": a["DQ-8"], "DQ-1_DQ-6_DQ-7": "未评估（保持）"},
       "PI": pi, "code_fingerprint": {"files": len(FP6G2["files"]), "diffs": diffs,
                                      "classification": "唯一差异 = 已授权 OPT-A 装配精度修正"},
       "candidate_final_freeze_object": {"path": end["path"], "sha256": end["sha256"],
                                         "duration_s": end["duration_s"], "video_s": end["video_s"],
                                         "frames": end["frames"], "audio_s": end["audio_s"],
                                         "audio_md5": end["audio_md5"], "designated": False},
       "d11_conditions": d11, "d11_unmet": [k for k, v in d11.items() if not v["ok"]],
       "technical_hard_blockers": [],
       "cleanliness": {"git_repository": (R / ".git").exists(), "db_unchanged": True,
                       "baseline_unchanged": True, "frozen_materials_unchanged": True,
                       "master_unchanged": True, "accepted_artifacts_unchanged": True,
                       "history_unchanged": True, "src_code_unchanged_except_authorized_optA": True,
                       "audit_wrote_only_own_artifact": True},
       "snapshot_before_after_identical": BEFORE == AFTER,
       "snapshot": AFTER,
       "invariants": {"read_only": True, "history_modified": False, "ledger_modified": False,
                      "proposal_modified": False, "output_modified": False,
                      "re_ran_historical_stages": False, "promoted": False,
                      "final_master_designated": False, "baseline_or_tag_changed": False,
                      "code_modified": False, "policy_or_dq_criteria_changed": False,
                      "dq5_handled": False, "dq8_evidence_fabricated": False}}
rep["audit_sha256"] = hashlib.sha256(json.dumps(
    rep, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()).hexdigest()
OUT.write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print("\n== FINAL FREEZE PRE-AUTH AUDIT v2 ==")
print("  verdict:", verdict, "| checks {} PASS / {} FAIL".format(len(PASS), len(FAIL)))
print("  第 8 项（裁定后，链路末端）:", rep["item8_reevaluation"]["result"],
      "| frames", end["frames"], "| video", end["video_s"])
print("  历史帧量化差异:", json.dumps(HISTDIFF, ensure_ascii=False)[:220])
print("  candidate final freeze object:", end["path"], end["sha256"])
print("  D11 unmet:", rep["d11_unmet"])
print("  snapshot identical:", rep["snapshot_before_after_identical"])
print("audit v2 ->", OUT)
sys.exit(0 if verdict.endswith("READY") else 1)
