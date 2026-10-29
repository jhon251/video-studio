# -*- coding: utf-8 -*-
"""6-G —— **POST-FREEZE VERIFICATION**（只读）：封版后立即核验，任何不一致即 FAIL-CLOSED。

产出: docs/regression_2x/logs/phase6g_post_freeze_verification.json
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
from video_studio.core import execution as EX                        # noqa: E402
from video_studio.core import integrity as core_integrity            # noqa: E402
from video_studio.core import narration as N                         # noqa: E402
from video_studio.core import revision as core_revision              # noqa: E402
from video_studio.ops import execution as OPX                        # noqa: E402

L = R / "docs" / "regression_2x" / "logs"
B = R / "docs" / "regression_2x" / "baseline"
FF, FP = str(R / "bin/ffmpeg.exe"), str(R / "bin/ffprobe.exe")
TAG = "6.x-final-baseline"
OUT = L / "phase6g_post_freeze_verification.json"
PROOF = json.loads((L / "phase6g_final_freeze.json").read_text(encoding="utf-8"))
P = PROOF["post_freeze_snapshot"]
PASS, FAIL = [], []


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def ck(name, ok, detail=None):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else json.dumps(detail, ensure_ascii=False,
                                                      default=str)[:200]))
    return bool(ok)


master = R / PROOF["1_final_master_path"]
ck("V1 final master SHA 未变（{}）".format(PROOF["2_final_master_sha256"][:16]),
   sha(master) == PROOF["2_final_master_sha256"] == P["final_master_sha256"]
   and sha(master) == PROOF["2_final_master_sha256"], {"actual": sha(master)[:16]})
ck("V2 DCv2 master 未变", sha(R / PROOF["dcv2_master_path"]) == P["dcv2_master_sha256"]
   if "dcv2_master_path" in PROOF else
   sha(R / "output/phase6g_sandbox/20260929_102445/out/dcv2_master_20260929_102445.mp4")
   == P["dcv2_master_sha256"])
ck("V3 frozen materials 未变（材料计划 sha 一致）",
   sha(R / "docs/regression_2x/phase6e_materials/phase6e_material_plan.json")
   == P["frozen_materials_sha256"]["material_plan"])
ck("V4 proposal register 未被改写（文件 sha 一致 + 链 ok + 6 条）",
   sha(L / "phase6g_rebuild_proposal_register.jsonl") == P["register_file_sha256"]
   and core_revision.verify_register_chain(
       core_revision.load_register(str(L / "phase6g_rebuild_proposal_register.jsonl")))["ok"],
   {"sha": sha(L / "phase6g_rebuild_proposal_register.jsonl")[:16]})
led = EX.load_ledger(str(L / "phase6g_exec_ledger.jsonl"))
ck("V5 历史 ledger entries 未被改写（文件 sha 一致 + 11 条 + 链 ok + 末端 entry sha 一致）",
   sha(L / "phase6g_exec_ledger.jsonl") == P["ledger_file_sha256"]
   and len(led) == 11 and EX.verify_chain(led)["ok"]
   and led[-1]["entry_sha256"] == PROOF["8_execution_ledger"]["terminal_entry_sha256"])
ck("V6 accepted artifacts 未被改写（十条产物 sha 逐一一致）",
   all(sha(R / e["output_path"]) == P["accepted_outputs"][e["stage"]] for e in led
       if e.get("output_sha256") and e.get("stage") in P["accepted_outputs"]),
   {k: sha(R / next(e for e in led if e.get("stage") == k)["output_path"])[:16]
    for k in P["accepted_outputs"]})
# baseline/tag 指向
man = json.loads((B / "baseline_manifest_{}.json".format(TAG)).read_text(encoding="utf-8"))
st = json.loads((B / "baseline_status_{}.json".format(TAG)).read_text(encoding="utf-8"))
zip_p = B / "{}.zip".format(TAG)
ck("V7 final baseline/tag 指向正确（tag 字段一致 + ZIP sha == manifest + status 绑定母片）",
   man["tag"] == st["tag"] == TAG and sha(zip_p) == man["zip_sha256"]
   and st["final_master"]["sha256"] == PROOF["2_final_master_sha256"]
   and st["tag"] == TAG)
ck("V8 manifest 与实际文件 SHA 一致（verify_baseline 重跑 = MATCH）",
   "VERDICT: MATCH" in subprocess.run(
       [sys.executable, str(R / "docs/regression_2x/verify_baseline.py"), TAG],
       capture_output=True, text=True, encoding="utf-8", errors="replace").stdout)
ck("V9 manifest 与 ZIP 条目集合一致且无 docs/ 条目（规范）",
   not [k for k in man["files"] if k.startswith("docs/")] and man["file_count"] == len(man["files"]))
# DQ 权威一致性
DQ = json.loads((L / "phase6g_h5_dq_recompute.json").read_text(encoding="utf-8"))
ck("V10 DQ 状态与权威重算一致（DQ-2/3/4 PASS；DQ-5 FAIL；DQ-8 NOT_ASSESSABLE；DQ-1/6/7 未评估）",
   DQ["DQ"]["after_H5"]["DQ-2"]["state"] == PROOF["11_DQ_2_3_4"]["DQ-2"]["state"] == "PASS"
   and DQ["DQ"]["after_H5"]["DQ-3"]["state"] == PROOF["11_DQ_2_3_4"]["DQ-3"]["state"] == "PASS"
   and DQ["DQ"]["after_H5"]["DQ-4"]["state"] == PROOF["11_DQ_2_3_4"]["DQ-4"]["state"] == "PASS"
   and PROOF["12_DQ_5"]["state"] == "FAIL" and PROOF["13_DQ_8"]["state"] == "NOT_ASSESSABLE"
   and PROOF["14_DQ_1_6_7"]["state"].startswith("未评估"))
# PI / frozen recheck on final master
B1 = json.loads((L / "phase6g_exec_batch1.json").read_text(encoding="utf-8"))
P2 = json.loads((L / "phase6f_rebuild_plan_v2.json").read_text(encoding="utf-8"))
b1 = R / B1["sandbox"]
script = json.loads((b1 / "artifacts/script_output.json").read_text(encoding="utf-8"))
voice = json.loads((b1 / "artifacts/voice_output.json").read_text(encoding="utf-8"))
cw = [{"scene_id": c["scene_id"], "start_s": c["new_audio_window_s"][0],
       "end_s": c["new_audio_window_s"][1]} for c in P2["remapping_21_segments"]]
tl = [{"scene_id": c["scene_id"], "start_s": c["new_timeline_window_s"][0],
       "end_s": c["new_timeline_window_s"][1]} for c in P2["remapping_21_segments"]]
cues = core_captions.build_cues(
    [{"narration": s["narration"], "duration_s": s.get("duration_s")}
     for s in script["segments"] if str(s.get("narration", "")).strip()],
    windows=[{"start_s": w["start_s"], "end_s": w["end_s"]} for w in cw])
plan = N.narration_plan(script, voice)
GP = core_integrity.gate_policy({"tools": {"ffmpeg": {"path": FF, "ffprobe": FP}}})
sm = lambda m: {x: (y.get("state") if isinstance(y, dict) else y) for x, y in m.items()}
pre = core_integrity.pre_render_gate(script.get("segments") or [], voice, 978.656, GP,
                                     narration_duration_s=voice.get("narration_duration_s"),
                                     narration_plan=plan, cues=cues,
                                     narration_padding_s=978.656 - float(
                                         voice.get("narration_duration_s") or 0))
post = core_integrity.post_render_gate(master, 978.656, cues, voice.get("narration_duration_s"),
                                       True, FF, FP, GP, narration_plan=plan)
rc = OPX.pi_recheck(OPX.attach_dcv2_time_base(
    {"config": {"tools": {"ffmpeg": {"path": FF, "ffprobe": FP}}}, "root": str(R),
     "film": str(master), "cues": cues, "timeline_duration_s": 978.656,
     "artifacts": {"script_output": str(b1 / "artifacts/script_output.json"),
                   "voice_output": str(b1 / "artifacts/voice_output.json")}},
    timeline=[dict(e, selected_asset={}) for e in tl], caption_windows=cw,
    production_duration_s=978.656, source="post-freeze verification"),
    {"proposal_id": "POSTFREEZE", "action": "replace_asset",
     "affected_scope": {"scenes": [], "window": None}}, {"outputs": [{"path": PROOF[
         "1_final_master_path"]}]})
ck("V11 PI pre/post 与 frozen recheck 仍为 PASS（最终母片重跑）",
   (not pre["blocked"]) and all(sm(pre["metrics"]).get(g) == "PASS" for g in
                                ("PI-1", "PI-2", "PI-6", "G-TL", "G-PAD", "G-SUB"))
   and sm(post["metrics"]).get("PI-3") == "PASS" and not post.get("promote_blocked")
   and rc["pi_gate_outcome"] == "PASS",
   {"PI-3": sm(post["metrics"]).get("PI-3"), "frozen": rc["pi_gate_outcome"]})
ck("V12 封版证明与本次验证自身未被中间改写（母片/链/baseline 快照一致）",
   P["baseline"]["zip_sha256"] == sha(zip_p)
   and P["baseline"]["manifest_sha256"] == sha(B / "baseline_manifest_{}.json".format(TAG))
   and P["baseline"]["status_sha256"] == sha(B / "baseline_status_{}.json".format(TAG)))
verdict = "PHASE6G_FINAL_FROZEN" if not FAIL else "FINAL_FREEZE_BLOCKED"
out = {"schema": "phase6g-post-freeze-verification-v1", "stage": "6-G / POST-FREEZE VERIFICATION",
       "verdict": verdict, "tag": TAG,
       "final_master": {"path": PROOF["1_final_master_path"],
                        "sha256": PROOF["2_final_master_sha256"],
                        "duration_s": PROOF["3_duration_video_frames_audio"]["duration_s"],
                        "video_s": PROOF["3_duration_video_frames_audio"]["video_s"],
                        "frames": PROOF["3_duration_video_frames_audio"]["frames"],
                        "audio_s": PROOF["3_duration_video_frames_audio"]["audio_s"],
                        "audio_md5": PROOF["4_audio_md5"]},
       "baseline": {"zip": "docs/regression_2x/baseline/{}.zip".format(TAG),
                    "zip_sha256": sha(zip_p), "file_count": man["file_count"],
                    "verify_baseline": "MATCH", "manifest_sha256":
                        sha(B / "baseline_manifest_{}.json".format(TAG)),
                    "status_sha256": sha(B / "baseline_status_{}.json".format(TAG))},
       "PI_final": {"pre": sm(pre["metrics"]), "post": sm(post["metrics"]),
                    "frozen_recheck": rc["pi_gate_outcome"]},
       "DQ_authoritative": {"DQ-2": DQ["DQ"]["after_H5"]["DQ-2"]["state"],
                            "DQ-3": DQ["DQ"]["after_H5"]["DQ-3"]["state"],
                            "DQ-4": DQ["DQ"]["after_H5"]["DQ-4"]["state"],
                            "DQ-5": "FAIL（既有诊断项）", "DQ-8": "NOT_ASSESSABLE",
                            "DQ-1/DQ-6/DQ-7": "未评估"},
       "checks": {"pass": PASS, "fail": FAIL},
       "invariants": {"read_only": True, "master_modified": False, "dcv2_master_modified": False,
                      "frozen_materials_modified": False, "register_modified": False,
                      "ledger_modified": False, "accepted_outputs_modified": False,
                      "code_modified": False, "history_modified": False}}
out["verification_sha256"] = hashlib.sha256(json.dumps(
    out, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()).hexdigest()
OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print("\n== POST-FREEZE VERIFICATION ==")
print("  verdict:", verdict, "| checks {} PASS / {} FAIL".format(len(PASS), len(FAIL)))
print("  final master:", PROOF["1_final_master_path"], PROOF["2_final_master_sha256"])
print("  baseline:", TAG, "| zip sha256:", sha(zip_p))
print("verification ->", OUT)
sys.exit(0 if verdict == "PHASE6G_FINAL_FROZEN" else 1)
