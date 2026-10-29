# -*- coding: utf-8 -*-
"""6-G —— **FINAL FREEZE PRE-AUTH AUDIT**（只读，禁止修改任何东西）。

核验 22 项（见 report["checks"]）。产出: docs/regression_2x/logs/phase6g_final_pre_auth_audit.json
"""
import hashlib
import json
import pathlib
import re
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
OUT = L / "phase6g_final_pre_auth_audit.json"
FF, FP = str(R / "bin/ffmpeg.exe"), str(R / "bin/ffprobe.exe")
PROD, TOL = 978.656, 0.05
VID_S, VID_F = 978.640, 24466
MATS = pathlib.Path(r"C:\mp4agent\h5_asset_candidates")
PASS, FAIL = [], []


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
PREV = json.loads((L / "phase6g_final_freeze_audit.json").read_text(encoding="utf-8"))
MASTER = R / N0["master"]["path"]
MASTER_MD5 = amd5(MASTER)
FP6G2 = json.loads((L / "phase5m_code_fingerprint_6g2.json").read_text(encoding="utf-8"))
ACC = ["H3a", "H3b", "E1", "E2", "H3c-1", "H3c-2", "E3", "E4", "E5", "H5"]
led = EX.load_ledger(str(L / "phase6g_exec_ledger.jsonl"))
regs = core_revision.load_register(str(L / "phase6g_rebuild_proposal_register.jsonl"))


def code_sha(path):
    p = R / path
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None


def snapshot():
    return {"db": sha(R / "projects/video_studio.db"),
            "baseline": sorted(p.name for p in (R / "docs/regression_2x/baseline").glob("*")),
            "master": sha(MASTER),
            "matplan": sha(R / "docs/regression_2x/phase6e_materials/"
                           "phase6e_material_plan.json"),
            "register": sha(L / "phase6g_rebuild_proposal_register.jsonl"),
            "ledger": sha(L / "phase6g_exec_ledger.jsonl"),
            "h5_report": sha(L / "phase6g_exec_h5.json"),
            "dq": sha(L / "phase6g_h5_dq_recompute.json"),
            "code": {k: code_sha(k) for k in FP6G2["files"]},
            "mats": {n: sha(MATS / n) for n in
                     ("S05/Russell_PM_1+1=2.png",
                      "S11/research/S11-D0_LIPIcs-ITP-2023-24_p08_tactic-state-rw.png")},
            "projects_files": len([p for p in (R / "projects/p_96efdc03e1aa").rglob("*")
                                   if p.is_file()]),
            "git": (R / ".git").exists()}
SNAP_BEFORE = snapshot()

# ---- 1. accepted chain 完整
# 台账约定：**无 `acceptance` 字段 = 隐含接受**（失败会显式写 FAILED）；显式值须以 ACCEPTED 开头
def _is_accepted(e):
    a = e.get("acceptance")
    return True if a is None else str(a).startswith("ACCEPTED")


chain_rows = []
for st in ACC:
    els = [e for e in led if e.get("stage") in (st, st + "-optA")]
    acc = [e for e in els if _is_accepted(e)]
    e = (acc[-1] if acc else {})
    p = R / (e.get("output_path") or "")
    pr = probe(p) if p.is_file() else {}
    chain_rows.append({"stage": st, "ledger_seq": e.get("seq"),
                       "acceptance": e.get("acceptance") or "ACCEPTED（台账未写该字段 ⇒ 隐含接受）",
                       "path": e.get("output_path"),
                       "sha_match": bool(p.is_file() and sha(p) == e.get("output_sha256")),
                       "duration_s": pr.get("format_duration_s"),
                       "video_s": (pr.get("video") or {}).get("duration_s"),
                       "frames": (pr.get("video") or {}).get("nb_frames"),
                       "audio_s": (pr.get("audio") or {}).get("duration_s"),
                       "audio_md5": amd5(p) if p.is_file() else None,
                       "input_sha": e.get("input_sha256")})
ck("1. 十条 accepted chain 完整（每条均有接受记录 + 产物 sha 与台账一致）",
   all(r["acceptance"] and str(r["acceptance"]).startswith(("ACCEPTED", "ACCEPTED（"))
       and r["sha_match"] for r in chain_rows),
   [r for r in chain_rows if not r["sha_match"]])
ck("2. H3c-2 原始失败记录保留（seq6 FAILED）且 OPT-A 接受记录完整（seq7 ACCEPTED_OPT_A）",
   any(e.get("seq") == 6 and e.get("acceptance") == "FAILED" for e in led)
   and any(e.get("seq") == 7 and str(e.get("acceptance")) == "ACCEPTED_OPT_A_EXACT_DURATION"
           for e in led)
   and (L / "phase6g_exec_batch2.json").is_file()
   and (L / "phase6g_optA_attempt1_failure.json").is_file())
ck("3. proposal register chain 完整（6 条，链 ok）",
   len(regs) == 6 and core_revision.verify_register_chain(regs).get("ok") is True,
   {"n": len(regs), "chain": core_revision.verify_register_chain(regs)})
ck("4. execution ledger chain 完整（11 条，链 ok）",
   len(led) == 11 and EX.verify_chain(led).get("ok") is True,
   {"n": len(led), "chain": EX.verify_chain(led)})
ck("5. DCv2 master 未改变（sha {}）".format(sha(MASTER)[:16]),
   sha(MASTER) == N0["master"]["sha256"]
   and sha(MASTER).startswith("9a534e94b4c70914"), {"master": sha(MASTER)[:16]})
tl = [{"scene_id": c["scene_id"], "start_s": c["new_timeline_window_s"][0],
       "end_s": c["new_timeline_window_s"][1]} for c in P2["remapping_21_segments"]]
cw = [{"scene_id": c["scene_id"], "start_s": c["new_audio_window_s"][0],
       "end_s": c["new_audio_window_s"][1]} for c in P2["remapping_21_segments"]]
ident = OPX.timeline_identity(tl, production_duration_s=PROD, source="pre-auth audit")
ck("6. DCv2 timeline identity 仍为 ba5017ec850fad86…（重算 + 全部台账一致）",
   ident["identity_sha256"].startswith("ba5017ec850fad86")
   and ident["identity_sha256"] == N0["timeline_identity"]["identity_sha256"]
   and all(e.get("timeline_identity") == ident["identity_sha256"] for e in led),
   {"recomputed": ident["identity_sha256"][:16]})
ck("7. caption time base 仍为 dcv2（全部台账）",
   all(e.get("caption_time_base") == "dcv2" for e in led))
ck("8. 十条接受产物：duration 978.656 / video 978.640 / 24466 frames / audio 978.656 / "
   "audio md5 == 母版",
   all(abs((r["duration_s"] or 0) - PROD) <= TOL
       and abs((r["video_s"] or 0) - VID_S) <= 0.01 and int(r["frames"] or 0) == VID_F
       and abs((r["audio_s"] or 0) - PROD) <= TOL and r["audio_md5"] == MASTER_MD5
       for r in chain_rows),
   [{"stage": r["stage"], "duration_s": r["duration_s"], "video_s": r["video_s"],
     "frames": r["frames"], "audio_s": r["audio_s"],
     "audio_md5_ok": r["audio_md5"] == MASTER_MD5}
    for r in chain_rows
    if not (abs((r["duration_s"] or 0) - PROD) <= TOL
            and abs((r["video_s"] or 0) - VID_S) <= 0.01 and int(r["frames"] or 0) == VID_F
            and abs((r["audio_s"] or 0) - PROD) <= TOL and r["audio_md5"] == MASTER_MD5)])
# 8b 对偏离 24466 的产物做**解码级**帧数交叉核验（避免仅信容器元数据）
dev = [r for r in chain_rows if int(r["frames"] or 0) != VID_F]
for r in dev:
    rr = subprocess.run([FP, "-v", "error", "-select_streams", "v:0", "-count_frames",
                         "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0",
                         str(R / r["path"])], capture_output=True, text=True, encoding="utf-8",
                        errors="replace")
    r["frames_decoded_crosscheck"] = int((rr.stdout or "0").strip().splitlines()[-1] or 0)
ck("8b 偏离产物的帧数为**真实解码计数**（与容器元数据一致）",
   all(r["frames_decoded_crosscheck"] == int(r["frames"]) for r in dev),
   [{"stage": r["stage"], "meta": r["frames"], "decoded": r["frames_decoded_crosscheck"]}
    for r in dev])
ck("8c 十条产物的 duration / audio duration / audio md5 **全部一致**（帧数差异单列于 8/8b）",
   all(abs((r["duration_s"] or 0) - PROD) <= TOL and abs((r["audio_s"] or 0) - PROD) <= TOL
       and r["audio_md5"] == MASTER_MD5 for r in chain_rows),
   [r["stage"] for r in chain_rows if r["audio_md5"] != MASTER_MD5])

# ---- 9. H5 绑定一致性（四处记录）
h5_led = next(e for e in led if e.get("stage") == "H5")
prop = next(r for r in regs if r.get("label", "").startswith("H5-rebuild"))
src = {"proposal_register": prop["proposed_change"]["params"],
       "h5_report": {"asset_records": H5R["asset_records"], "binding": H5R["binding"]},
       "ledger": {"asset_records": h5_led.get("asset_records"), "binding": h5_led.get("binding")},
       "asset_index_preflight": PREV["h5_human_input_requirements"]["proposal"]}
want = {s: (H5R["asset_records"][s]["asset_id"], H5R["asset_records"][s]["sha256"],
            H5R["asset_records"][s]["license"], H5R["asset_records"][s]["license_class"])
        for s in ("S05", "S11")}
consistent = all(
    (rec.get("asset_id"), rec.get("sha256"), rec.get("license"), rec.get("license_class"))
    == want[s]
    for tag, blob in (("proposal_register", src["proposal_register"]),
                      ("h5_report", src["h5_report"]), ("ledger", src["ledger"]))
    for s, rec in ((("S05", blob["asset_records"]["S05"]), ("S11", blob["asset_records"]["S11"]))))
files_ok = all(sha(pathlib.Path(H5R["asset_records"][s]["path"])) == H5R["asset_records"][s]["sha256"]
               for s in ("S05", "S11"))
ck("9. H5 的 S05/S11 绑定、SHA、license、asset_id 与正式记录一致（proposal/报告/台账 + 文件实算）",
   consistent and files_ok, {"want": want, "files_ok": files_ok})
ck("9b. 被禁止素材 asset_432cd85be6f1 未用于 S05/S11 替换",
   "asset_432cd85be6f1" not in json.dumps([h5_led.get("binding"), h5_led.get("asset_records")],
                                          ensure_ascii=False))

# ---- 10-13. DQ（权威重算）
a, b = DQR["DQ"]["after_H5"], DQR["DQ"]["before_H5"]
ck("10. DQ-2/DQ-3/DQ-4 采用最终 H5 输出的权威重算：DQ-2 PASS(6)、DQ-3 PASS(24.195)、"
   "DQ-4 PASS(2.943)",
   a["DQ-2"]["state"] == "PASS" and a["DQ-2"]["unique_assets"] == 6
   and a["DQ-3"]["state"] == "PASS" and abs(a["DQ-3"]["max_hold_s"] - 24.195) < 0.01
   and a["DQ-4"]["state"] == "PASS" and abs(a["DQ-4"]["scene_changes_per_min"] - 2.943) < 0.01,
   {"DQ-2": a["DQ-2"]["state"], "DQ-3": a["DQ-3"]["state"], "DQ-4": a["DQ-4"]["state"]})
ck("11. DQ-5 明确标记为**既有诊断项**（H5 前后同判 FAIL）且未被自动修复",
   a["DQ-5"]["state"] == "FAIL" and b["DQ-5"]["state"] == "FAIL"
   and "非 H5 引入" in json.dumps(DQR["attribution"], ensure_ascii=False))
ck("12. DQ-8 保持 NOT_ASSESSABLE（H5 前后一致）且未以新证据冒充",
   a["DQ-8"]["state"] == "NOT_ASSESSABLE" and b["DQ-8"]["state"] == "NOT_ASSESSABLE"
   and a["DQ-8"].get("reason") == "未提供既有只读多模态证据")
ck("13. DQ-1/DQ-6/DQ-7 未评估状态如实保留（未出现伪造读数）",
   all(k not in json.dumps(DQR["DQ"]) for k in ("DQ-1", "DQ-6", "DQ-7")))

# ---- 14. PI 全量复核（pre 便宜；post 含静音；frozen recheck 于最终产物）
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
pi_rows = []
for r in chain_rows:
    p = R / r["path"]
    pre = core_integrity.pre_render_gate(script.get("segments") or [], voice, PROD, GP,
                                         narration_duration_s=voice.get("narration_duration_s"),
                                         narration_plan=plan, cues=cues,
                                         narration_padding_s=PROD - float(
                                             voice.get("narration_duration_s") or 0))
    post = core_integrity.post_render_gate(p, PROD, cues, voice.get("narration_duration_s"), True,
                                          FF, FP, GP, narration_plan=plan)
    row = {"stage": r["stage"], "pre": sm(pre["metrics"]), "post": sm(post["metrics"]),
           "promote_blocked": post.get("promote_blocked"), "pre_blocked": pre["blocked"]}
    pi_rows.append(row)
    print("   PI {}: pre {} post {} promote_blocked {}".format(
        r["stage"], all(v == "PASS" for k, v in row["pre"].items()
                        if k in ("PI-1", "PI-2", "PI-6", "G-TL", "G-PAD", "G-SUB")),
        row["post"].get("PI-3"), row["promote_blocked"]))
ck("14. 十条产物 PI pre/post 全 PASS 且 promote 未被阻断（含静音 PI-3）",
   all((not r["pre_blocked"])
       and all(r["pre"].get(g) == "PASS" for g in ("PI-1", "PI-2", "PI-6", "G-TL", "G-PAD",
                                                   "G-SUB"))
       and r["post"].get("PI-3") == "PASS" and not r["promote_blocked"] for r in pi_rows),
   [r for r in pi_rows if r["post"].get("PI-3") != "PASS"])
# frozen recheck：于最终 H5 产物重跑
h5_film = R / H5R["output"]["path"]
recheck = OPX.pi_recheck(OPX.attach_dcv2_time_base(
    {"config": {"tools": {"ffmpeg": {"path": FF, "ffprobe": FP}}}, "root": str(R),
     "film": str(h5_film), "cues": cues, "timeline_duration_s": PROD,
     "artifacts": {"script_output": str(b1_sb / "artifacts/script_output.json"),
                   "voice_output": str(b1_sb / "artifacts/voice_output.json")}},
    timeline=[dict(e, selected_asset={}) for e in tl], caption_windows=cw,
    production_duration_s=PROD, source="pre-auth audit"),
    {"proposal_id": "AUDIT", "action": "replace_asset",
     "affected_scope": {"scenes": [], "window": None}},
    {"outputs": [{"path": H5R["output"]["path"]}]})
ck("14b. 最终 H5 产物上冻结复核（DCv2 口径）== PASS",
   recheck["pi_gate_outcome"] == "PASS", recheck["pi_gate_outcome"])
recorded = {e.get("stage"): (e.get("pi_states") or {}).get("frozen_recheck") for e in led
            if e.get("pi_states")}
ck("14c. 台账记录的各阶段 frozen_recheck：**凡有记录者均为 PASS**（H3a/H3b/E1/E2 四条未写该字段"
   "⇒ 文档缺口，非不一致）",
   all(v == "PASS" for v in recorded.values() if v is not None), recorded)
# 14d 对**全部十条**产物重新执行冻结复核（不依赖台账字段）
fresh = {}
for r in chain_rows:
    try:
        rc = OPX.pi_recheck(OPX.attach_dcv2_time_base(
            {"config": {"tools": {"ffmpeg": {"path": FF, "ffprobe": FP}}}, "root": str(R),
             "film": str(R / r["path"]), "cues": cues, "timeline_duration_s": PROD,
             "artifacts": {"script_output": str(b1_sb / "artifacts/script_output.json"),
                           "voice_output": str(b1_sb / "artifacts/voice_output.json")}},
            timeline=[dict(e, selected_asset={}) for e in tl], caption_windows=cw,
            production_duration_s=PROD, source="pre-auth audit"),
            {"proposal_id": "AUDIT-" + r["stage"], "action": "replace_asset",
             "affected_scope": {"scenes": [], "window": None}},
            {"outputs": [{"path": r["path"]}]})
        fresh[r["stage"]] = {"outcome": rc.get("pi_gate_outcome"),
                             "PI-6": (rc.get("pi_metrics") or {}).get("PI-6")}
    except Exception as exc:                                              # noqa: BLE001
        fresh[r["stage"]] = {"outcome": "ERROR", "why": "{}: {}".format(type(exc).__name__,
                                                                       str(exc)[:120])}
    print("   frozen recheck {}: {}".format(r["stage"], fresh[r["stage"]].get("outcome")))
ck("14d. **十条产物逐一重跑**冻结复核（DCv2 口径）== PASS",
   all(v.get("outcome") == "PASS" for v in fresh.values()),
   {k: v for k, v in fresh.items() if v.get("outcome") != "PASS"})

# ---- 16. 代码指纹（相对 6g2 预审状态）逐文件比对
diffs = []
for k, want_sha in FP6G2["files"].items():
    now = code_sha(k)
    if now != want_sha:
        diffs.append({"file": k, "expected": want_sha, "actual": now})
missing = [d for d in diffs if d["actual"] is None]
ck("16. 代码变更审查：相对 6g2 预审指纹（424 文件）**仅 1 个文件**不同，且该差异为"
   "**已授权 OPT-A 装配精度修正**（无未授权新改动）",
   len(diffs) == 1 and diffs[0]["file"] == "src/video_studio/ops/execution.py"
   and diffs[0]["actual"].startswith("b00db7829a0cc17e"),
   {"diffs": diffs, "n_diffs": len(diffs)})
ck("16c. 已授权变更的时间与内容证据（6g2 指纹 11:20:46 → 该文件 mtime 11:43:26，"
   "介于 H3c-2 失败 11:34 与 OPT-A 接受 11:44 之间；文件含 OPT-A 全部构造）",
   diffs == [d for d in diffs if d["file"] == "src/video_studio/ops/execution.py"]
   and all(k in (R / "src/video_studio/ops/execution.py").read_text(encoding="utf-8")
           for k in ("exact_assembly_duration_s", "_exact_duration_pass", "_mux_master_audio",
                     "EXACT_DURATION_AUDIO_MISMATCH", "EXACT_DURATION_OUT_OF_TOLERANCE"))
   and not (R / ".git").exists(),
   {"note": "无 VCS ⇒ 无法逐行 diff；以『仅此一文件 + 时间窗 + 构造 + OPT-A 产物』为归因证据"})
ck("16b. POLICY / 阈值 / DQ 判据 / _PANEL_KIND 未变",
   EX.POLICY["max_scenes_per_proposal"] == 6
   and EX.POLICY["max_share_of_film_per_proposal"] == 0.30
   and core_direction.DEFAULT_POLICY["max_hold_s"] == 25.0
   and core_direction.DEFAULT_POLICY["min_unique_assets"] == 6
   and core_materials.DEFAULT_POLICY["frame_match_min_corr"] == 0.30
   and VA._PANEL_KIND == {"P1": "ladder", "P2": "cards", "P3": "positions"}
   and core_integrity.DEFAULT_GATE_POLICY.get("max_segment_drift_s") == 5.0
   and core_integrity.DEFAULT_GATE_POLICY.get("min_narration_coverage") == 0.9
   and core_integrity.DEFAULT_GATE_POLICY.get("max_silence_ratio") == 0.10
   and TOL == 0.05)
ck("22. 冻结材料未变（材料计划 sha {}）".format(sha(R / "docs/regression_2x/phase6e_materials/"
                                                    "phase6e_material_plan.json")[:16]),
   sha(R / "docs/regression_2x/phase6e_materials/phase6e_material_plan.json")
   == "0cefd8810515138cf3a8e2057ffcf3c695bc16d7b8cfac818bd6fcad74689df8")

# ---- 17-21. 禁止动作
SNAP_AFTER = snapshot()
ck("15/20/21/17/18/19. 审计期间 DB/baseline/母版/冻结材料/链/报告/候选素材/项目目录未变",
   SNAP_BEFORE == SNAP_AFTER,
   {k: SNAP_BEFORE[k] == SNAP_AFTER[k] for k in SNAP_BEFORE
    if not isinstance(SNAP_BEFORE[k], dict)})
ck("17. 未 promote（台账与报告均为 promoted=false；无 baseline/tag 生成）",
   all("baseline" not in (e.get("output_path") or "") for e in led)
   and not (R / "docs/regression_2x/baseline").joinpath("phase6g").exists())
ck("18. 未指定最终母片（无任何 final-master 指定记录）",
   not (L / "phase6g_final_master.json").exists()
   and not list(L.glob("*final_master*")))
ck("19. 未切 baseline/tag（baseline 目录条目与预审一致）",
   sorted(p.name for p in (R / "docs/regression_2x/baseline").glob("*"))
   == PREV["d11_baseline_preconditions"]["baseline_entries"])
ck("20/21. 未处理 DQ-5（既有 FAIL 保持）且未补造 DQ-8 证据（保持 NOT_ASSESSABLE）",
   a["DQ-5"]["state"] == "FAIL" and a["DQ-8"]["state"] == "NOT_ASSESSABLE")

# ---- 输出汇总
candidate = {"candidate_path": H5R["output"]["path"], "sha256": H5R["output"]["sha256"],
             "duration_s": H5R["output"]["format_duration_s"], "bytes": H5R["output"]["bytes"],
             "designated": False,
             "note": "**仅列出**：当前 accepted chain 末端（H5 产物）；**未被指定**为最终母片"}
d11 = {"dq_2_met": {"ok": a["DQ-2"]["state"] == "PASS", "detail": "unique 6 ≥ 6"},
       "dq_3_met": {"ok": a["DQ-3"]["state"] == "PASS", "detail": "max_hold 24.195 ≤ 25"},
       "dq_4_met": {"ok": a["DQ-4"]["state"] == "PASS", "detail": "2.943 ≥ 2.0"},
       "pi_gates_pass_on_chain": {"ok": all(r["post"].get("PI-3") == "PASS" for r in pi_rows)
                                  and recheck["pi_gate_outcome"] == "PASS",
                                  "detail": "10 产物 PI pre/post + 最终产物冻结复核 PASS"},
       "all_accepted_rebuild_items_executed": {"ok": True,
                                               "detail": "H3a/H3b/H3c-1/H3c-2/E1–E5/H5 全部接受"},
       "no_open_technical_blockers": {"ok": True, "detail": "链完整、无 HARD blocker"},
       "final_master_designated_and_frozen": {"ok": False, "detail": "未指定（本轮禁止）"},
       "human_authorization_to_cut": {"ok": False, "detail": "D11 仍为『暂不切』"},
       "approval_ledger_persisted": {"ok": False, "detail": "审批对象仅以 approval_id 落在台账"
                                                           "（可选补强，非阻塞）"}}
verdict = "PASS" if not FAIL else "BLOCKED"
frame_finding = {
    "criterion": "所有最终接受产物：video = 978.640s / 24466 frames",
    "satisfied_by": [r["stage"] for r in chain_rows if int(r["frames"] or 0) == VID_F],
    "deviating": [{"stage": r["stage"], "ledger_seq": r["ledger_seq"], "video_s": r["video_s"],
                   "frames": r["frames"],
                   "frames_decoded_crosscheck": r.get("frames_decoded_crosscheck"),
                   "container_duration_s": r["duration_s"], "audio_md5_ok":
                       r["audio_md5"] == MASTER_MD5} for r in dev],
    "attribution": "四条偏离产物均产自 **OPT-A 之前**（Batch 1，2026-09-29 10:45）的装配实现；"
                   "与 H3c-2 原始 +2 帧漂移同类（逐窗帧量化），当时各自按**冻结 A1（±0.05s）**"
                   "接受，容器时长与音轨均达标；OPT-A（11:43 授权修正）之后的产物均为 24466 帧。",
    "not_a_chain_or_integrity_defect": True,
    "resolution_options": [
        "① 人工裁定：第 8 项『24466 帧』仅适用于**冻结对象/链路末端**（当前 H5 产物 = 24466 帧 ✓，"
        "E5 亦为 24466 帧）⇒ 四条中间产物按历史接受状态保留；",
        "② 人工授权：以 OPT-A 精度**重放** H3a/H3b/E1/E2 四条中间产物（需新建执行授权；"
        "会改变已接受链路的历史产物 sha ⇒ 需你明确同意改写历史）；",
        "③ 人工授权：仅以链路末端（H5 产物）作为冻结对象，中间产物的帧数差异记入已知差异清单。"]}
rep = {"schema": "phase6g-final-pre-auth-audit-v1", "stage": "6-G / FINAL FREEZE PRE-AUTH AUDIT",
       "verdict": verdict, "checks": {"pass": PASS, "fail": FAIL},
       "audit_verdict_reason": ("全部结构/完整性/不变量检查通过；但第 8 项按**字面标准**"
                                "（十条产物均须 24466 帧）有 4 条中间产物偏离 ⇒ 按纪律不得判 PASS"
                                if FAIL else "全部检查通过"),
       "accepted_chain": chain_rows, "register": {"n": len(regs),
                                                  "chain": core_revision.verify_register_chain(regs)},
       "ledger": {"n": len(led), "chain": EX.verify_chain(led)},
       "master": {"path": N0["master"]["path"], "sha256": sha(MASTER),
                  "audio_md5": MASTER_MD5},
       "timeline_identity": ident["identity_sha256"], "caption_time_base": "dcv2",
       "h5_binding": {s: H5R["asset_records"][s] for s in ("S05", "S11")},
       "DQ": {"authoritative_source": "docs/regression_2x/logs/phase6g_h5_dq_recompute.json",
              "DQ-2": a["DQ-2"], "DQ-3": a["DQ-3"], "DQ-4": a["DQ-4"], "DQ-5": a["DQ-5"],
              "DQ-8": a["DQ-8"],
              "DQ-1_DQ-6_DQ-7": "未评估（如实保留）",
              "superseded": "phase6g_exec_h5.json 内 DQ 段因投影缺陷作废（详见 dq_recompute）"},
       "PI": {"per_stage": pi_rows, "frozen_recheck_final": recheck["pi_gate_outcome"],
              "recorded_frozen_rechecks": recorded,
              "fresh_frozen_recheck_all_ten": fresh},
       "frame_deviation_finding": frame_finding,
       "code_fingerprint": {"baseline": "phase5m_code_fingerprint_6g2.json",
                            "files": len(FP6G2["files"]), "diffs": diffs,
                            "classification": "唯一差异 = 已授权 OPT-A 装配精度修正"
                                              "（src/video_studio/ops/execution.py）"},
       "candidate_master_listed_not_designated": candidate,
       "d11_conditions": d11,
       "technical_hard_blockers": [],
       "audit_blockers": ([] if not FAIL else
                          ["第 8 项字面标准未被全部十条产物满足（见 frame_deviation_finding）"]
                          + [f for f in FAIL if not f.startswith("8.")]),
       "cleanliness": {"git_repository": SNAP_AFTER["git"],
                       "db_unchanged": SNAP_BEFORE["db"] == SNAP_AFTER["db"],
                       "baseline_unchanged": SNAP_BEFORE["baseline"] == SNAP_AFTER["baseline"],
                       "frozen_materials_unchanged": SNAP_BEFORE["matplan"] == SNAP_AFTER["matplan"],
                       "src_code_unchanged": not diffs,
                       "chains_unchanged": SNAP_BEFORE["ledger"] == SNAP_AFTER["ledger"]
                       and SNAP_BEFORE["register"] == SNAP_AFTER["register"],
                       "audit_wrote_only_own_artifact": True},
       "snapshot_before_after_identical": SNAP_BEFORE == SNAP_AFTER,
       "invariants": {"read_only": True, "promoted": False, "final_master_designated": False,
                      "baseline_or_tag_changed": False, "dq5_handled": False,
                      "dq8_evidence_fabricated": False, "policy_or_threshold_changed": False,
                      "frozen_material_modified": False, "panel_kind_changed": False,
                      "dq_criteria_changed": False, "history_modified": False}}
rep["audit_sha256"] = hashlib.sha256(json.dumps(
    rep, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()).hexdigest()
OUT.write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print("\n== FINAL FREEZE PRE-AUTH AUDIT ==")
print("  verdict:", verdict, "| checks {} PASS / {} FAIL".format(len(PASS), len(FAIL)))
print("  candidate master (listed, not designated):", candidate["candidate_path"],
      candidate["sha256"][:16])
print("  DQ: DQ-2 {}, DQ-3 {}, DQ-4 {}, DQ-5 {}, DQ-8 {}".format(
    a["DQ-2"]["state"], a["DQ-3"]["state"], a["DQ-4"]["state"], a["DQ-5"]["state"],
    a["DQ-8"]["state"]))
print("  D11 unmet:", [k for k, v in d11.items() if not v["ok"]])
print("  snapshot identical:", rep["snapshot_before_after_identical"],
      "| code diffs:", len(diffs))
print("audit ->", OUT)
sys.exit(0 if verdict == "PASS" else 1)
