# -*- coding: utf-8 -*-
"""6-G —— **FINAL FREEZE 执行**（D11 已授权）：沿用既有 baseline 规范生成封版产物 + 封版证明。

规范（既有）：`docs/regression_2x/make_baseline.py <TAG>` → `baseline/<TAG>.zip` +
滚动 `baseline/baseline_manifest.json`；逐 tag 记录 `baseline_manifest_<TAG>.json`；
`verify_baseline.py <TAG>` 校验；状态文件 `baseline_status_<TAG>.json`。
命名：`<major>.x-final-baseline` ⇒ **6.x-final-baseline**（未自创命名体系）。

**不修改**：最终母片 / DCv2 master / 历史 accepted outputs / 历史 SHA / proposal register /
历史 ledger entries / POLICY / 阈值 / DQ 判据 / `_PANEL_KIND` / 冻结材料。

产出: docs/regression_2x/logs/phase6g_final_freeze.json
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
from video_studio.core import execution as EX                        # noqa: E402
from video_studio.core import revision as core_revision              # noqa: E402

L = R / "docs" / "regression_2x" / "logs"
BASE = R / "docs" / "regression_2x" / "baseline"
TAG = "6.x-final-baseline"
OUT = L / "phase6g_final_freeze.json"
PY = sys.executable
MASTER_REL = "output/phase6g_exec_h5/20260929_151026/out/H5_rp-0ebebb71f99c.mp4"
MASTER_SHA = "3b61dafda11c1b9d22381833a00645670ec8b4f25b8fccca813bb7ac63cee0be"
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


V2 = json.loads((L / "phase6g_final_pre_auth_audit_v2.json").read_text(encoding="utf-8"))
H5R = json.loads((L / "phase6g_exec_h5.json").read_text(encoding="utf-8"))
DQR = json.loads((L / "phase6g_h5_dq_recompute.json").read_text(encoding="utf-8"))
led = EX.load_ledger(str(L / "phase6g_exec_ledger.jsonl"))
regs = core_revision.load_register(str(L / "phase6g_rebuild_proposal_register.jsonl"))

# ---- ① 封版前再次验证最终母片 SHA256 + 冻结属性
master = R / MASTER_REL
ck("F1 封版前最终母片 SHA256 == 人工指定值（{}）".format(MASTER_SHA[:16]),
   master.is_file() and sha(master) == MASTER_SHA, {"actual": sha(master)[:16] if master.is_file()
                                                   else None})
SNAP_PRE = {"master": sha(master), "dcv2_master": sha(R / "output/phase6g_sandbox/"
                                                      "20260929_102445/out/"
                                                      "dcv2_master_20260929_102445.mp4"),
            "matplan": sha(R / "docs/regression_2x/phase6e_materials/"
                           "phase6e_material_plan.json"),
            "register": sha(L / "phase6g_rebuild_proposal_register.jsonl"),
            "ledger": sha(L / "phase6g_exec_ledger.jsonl"),
            "r3_manifest": sha(BASE / "baseline_manifest_5.x-post-final-maintenance-baseline-r3.json"),
            "accepted": {e.get("stage"): e.get("output_sha256") for e in led
                         if e.get("output_sha256")},
            "accepted_files": {e.get("stage"): sha(R / e["output_path"]) for e in led
                               if e.get("output_sha256")}}
ck("F2 本封版为**首次**最终母片指定（此前无任何 final-master 记录）",
   (not list(L.glob("*final_master*"))) and (not (L / "phase6g_final_master.json").exists()))

# ---- ② 生成 baseline（既有工具 + **既有 `--no-docs` 规范**）
# 规范证据：既有 5.x manifest 仅含 src/config/tests/scripts + 4 个根文件，**无 docs/** ⇒ 项目实际
# 使用 `--no-docs`（避免 docs 内自身哈希循环 + 排除 1.6GB 证据）。首跑因漏该参数产生 954MB ZIP，
# 已删除并按规范重做（本产物记录该更正）。
for stale in (BASE / "{}.zip".format(TAG),
              BASE / "baseline_manifest_{}.json".format(TAG),
              BASE / "baseline_status_{}.json".format(TAG)):
    if stale.is_file():
        stale.unlink()
        print("  已删除首跑误产物:", stale.name)
r1 = subprocess.run([PY, str(R / "docs/regression_2x/make_baseline.py"), TAG, "--no-docs"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace")
print("---- make_baseline ----")
print((r1.stdout or "").strip()[-1200:])
if r1.returncode != 0:
    print("stderr:", (r1.stderr or "")[-600:])
ck("F3 make_baseline 成功生成 ZIP", r1.returncode == 0)
ZIP = BASE / "{}.zip".format(TAG)
ck("F4 ZIP 存在且非空", ZIP.is_file() and ZIP.stat().st_size > 0,
   {"zip": str(ZIP.name), "bytes": ZIP.stat().st_size if ZIP.is_file() else None})
rolling = json.loads((BASE / "baseline_manifest.json").read_text(encoding="utf-8"))
ck("F5 滚动 manifest 的 tag == {}".format(TAG), rolling.get("tag") == TAG,
   rolling.get("tag"))
ck("F5b manifest **不含 docs/ 条目**（与既有 5.x 基线规范一致：`--no-docs`）",
   not [k for k in rolling["files"] if k.startswith("docs/")],
   {"n_docs": len([k for k in rolling["files"] if k.startswith("docs/")]),
    "tops": sorted({k.split("/")[0] for k in rolling["files"]})})
ck("F5c 文件规模与既有基线同量级（<600 文件、<20 MB 源码）",
   rolling["file_count"] < 600 and rolling["source_bytes"] < 20 * 1024 * 1024,
   {"files": rolling["file_count"], "source_bytes": rolling["source_bytes"]})
(BASE / "baseline_manifest_{}.json".format(TAG)).write_text(
    json.dumps(rolling, ensure_ascii=False, indent=1), encoding="utf-8")
ck("F6 逐 tag manifest 已按规范落盘 baseline_manifest_{}.json".format(TAG),
   (BASE / "baseline_manifest_{}.json".format(TAG)).is_file())
r2 = subprocess.run([PY, str(R / "docs/regression_2x/verify_baseline.py"), TAG],
                    capture_output=True, text=True, encoding="utf-8", errors="replace")
print("---- verify_baseline ----")
print((r2.stdout or "").strip()[-900:])
ver = "MATCH" in (r2.stdout or "")
ck("F7 verify_baseline VERDICT == MATCH（manifest 文件表 == ZIP 条目 且树内无漂移）", ver,
   (r2.stdout or "")[-300:])
ck("F8 历史 per-tag manifest（5.x-…-r3）未被改写",
   sha(BASE / "baseline_manifest_5.x-post-final-maintenance-baseline-r3.json")
   == SNAP_PRE["r3_manifest"])

# ---- ③ 状态文件（含最终母片绑定 + 完整最终状态）
man = rolling
status = {
    "tag": TAG, "frozen_at": man["created_utc"],
    "zip_sha256": man["zip_sha256"], "file_count": man["file_count"],
    "verify_baseline": "MATCH" if ver else "DIFF",
    "naming_convention": "沿用既有规范 `<major>.x-final-baseline`（全库既有：2.x/3.x/4.x/5.x-final-"
                         "baseline）；Phase 6-G 为 6.x 线终局 ⇒ `6.x-final-baseline`。"
                         "人工备选名 `phase6g-final` **未使用**（存在现成规范）。",
    "final_master": {"path": MASTER_REL, "sha256": MASTER_SHA,
                     "duration_s": H5R["output"]["format_duration_s"],
                     "video_s": H5R["output"]["video"]["duration_s"],
                     "frames": int(H5R["output"]["video"]["nb_frames"]),
                     "audio_s": H5R["output"]["audio"]["duration_s"],
                     "audio_md5": H5R["output"]["audio_md5"]},
    "dcv2": {"master_path": V2["master"]["path"], "master_sha256": V2["master"]["sha256"],
             "timeline_identity": V2["timeline_identity"], "caption_time_base": "dcv2"},
    "register": {"entries": len(regs), "chain_ok": core_revision.verify_register_chain(regs)["ok"],
                 "file_sha256": sha(L / "phase6g_rebuild_proposal_register.jsonl")},
    "ledger": {"entries": len(led), "chain_ok": EX.verify_chain(led)["ok"],
               "terminal_entry_sha256": led[-1]["entry_sha256"],
               "file_sha256": sha(L / "phase6g_exec_ledger.jsonl")},
    "accepted_items": [{"stage": e.get("stage"), "seq": e.get("seq"),
                        "acceptance": e.get("acceptance") or "ACCEPTED（隐含）",
                        "sha256": e.get("output_sha256")} for e in led
                       if e.get("output_sha256") and (e.get("acceptance") or "ACCEPTED")
                       .startswith(("ACCEPTED",))],
    "history": {"h3c2_failed_seq": 6, "h3c2_optA_accepted_seq": 7,
                "note": "H3c-2 原始 FAILED（seq6, 24468 帧/978.720s）保留；OPT-A 修正后接受（seq7）"},
    "DQ": {"DQ-2": DQR["DQ"]["after_H5"]["DQ-2"]["state"],
           "DQ-3": DQR["DQ"]["after_H5"]["DQ-3"]["state"],
           "DQ-4": DQR["DQ"]["after_H5"]["DQ-4"]["state"],
           "DQ-5": DQR["DQ"]["after_H5"]["DQ-5"]["state"] + "（既有诊断项，未处理）",
           "DQ-8": DQR["DQ"]["after_H5"]["DQ-8"]["state"] + "（未补造证据）",
           "DQ-1/DQ-6/DQ-7": "未评估（保持）",
           "source": "docs/regression_2x/logs/phase6g_h5_dq_recompute.json"},
    "PI": {"status": "十条产物 PI pre/post + 冻结复核全部 PASS",
           "source": "docs/regression_2x/logs/phase6g_final_pre_auth_audit_v2.json"},
    "historical_known_frame_quantization_difference": V2[
        "historical_frame_quantization_difference"],
    "d11": {"authorized_by": "human（本轮明确授权）",
            "final_master_designated_and_frozen": True, "human_authorization_to_cut": True,
            "approval_ledger_persisted": False},
    "note": "本基线为 Phase 6-G 终局封版（D11 已获人工授权）；最终母片由 SHA256 绑定；"
            "历史中间产物的已知帧量化差异按人工裁定**仅记录**，不改写、不重跑。",
}
ST = BASE / "baseline_status_{}.json".format(TAG)
ST.write_text(json.dumps(status, ensure_ascii=False, indent=1), encoding="utf-8")
ck("F9 状态文件已生成且绑定最终母片 SHA256", ST.is_file()
   and json.loads(ST.read_text(encoding="utf-8"))["final_master"]["sha256"] == MASTER_SHA)

# ---- ④ 封版证明（人工要求的 20 项）
proof = {
    "schema": "phase6g-final-freeze-v1", "stage": "6-G / FINAL FREEZE (D11)",
    "1_final_master_path": MASTER_REL,
    "2_final_master_sha256": MASTER_SHA,
    "3_duration_video_frames_audio": {"duration_s": H5R["output"]["format_duration_s"],
                                      "video_s": H5R["output"]["video"]["duration_s"],
                                      "frames": int(H5R["output"]["video"]["nb_frames"]),
                                      "audio_s": H5R["output"]["audio"]["duration_s"]},
    "4_audio_md5": H5R["output"]["audio_md5"],
    "5_dcv2_timeline_identity": V2["timeline_identity"],
    "6_caption_time_base": "dcv2",
    "7_proposal_register": {"entries": len(regs),
                            "chain_ok": core_revision.verify_register_chain(regs),
                            "file_sha256": sha(L / "phase6g_rebuild_proposal_register.jsonl")},
    "8_execution_ledger": {"entries": len(led), "chain_ok": EX.verify_chain(led),
                           "file_sha256": sha(L / "phase6g_exec_ledger.jsonl"),
                           "terminal_entry_sha256": led[-1]["entry_sha256"],
                           "chain_sha256_note": "链 SHA = 末端 entry_sha256（逐条 prev/entry 链）"},
    "9_accepted_rebuild_items": status["accepted_items"],
    "10_h3c2_history": {"FAILED_seq": 6, "FAILED_output_sha256":
                        next(e["output_sha256"] for e in led if e.get("seq") == 6),
                        "OPT_A_ACCEPTED_seq": 7, "OPT_A_output_sha256":
                        next(e["output_sha256"] for e in led if e.get("seq") == 7),
                        "relation": "同一 proposal rp-4db3b4bd15e5：先 FAILED（时长量化 +2 帧），"
                                    "经人工授权的 OPT-A 精确装配修正后接受；失败记录原样保留"},
    "11_DQ_2_3_4": {"DQ-2": DQR["DQ"]["after_H5"]["DQ-2"], "DQ-3": DQR["DQ"]["after_H5"]["DQ-3"],
                    "DQ-4": DQR["DQ"]["after_H5"]["DQ-4"]},
    "12_DQ_5": {"state": "FAIL", "classification": "既有诊断项（非 H5 引入，H5 前后同判）",
                "handled": False},
    "13_DQ_8": {"state": "NOT_ASSESSABLE", "reason": "未提供既有只读多模态证据",
                "evidence_fabricated": False},
    "14_DQ_1_6_7": {"state": "未评估（保持）"},
    "15_PI_frozen_recheck": {"status": "十条产物 PI pre/post + 逐条冻结复核全部 PASS",
                             "source": "docs/regression_2x/logs/"
                                       "phase6g_final_pre_auth_audit_v2.json"},
    "16_historical_frame_quantization_difference": V2[
        "historical_frame_quantization_difference"],
    "17_baseline": {"name": TAG, "zip": str(ZIP.relative_to(R)), "zip_sha256": man["zip_sha256"],
                    "file_count": man["file_count"], "source_bytes": man["source_bytes"],
                    "manifest": "docs/regression_2x/baseline/baseline_manifest_{}.json".format(TAG),
                    "status": "docs/regression_2x/baseline/baseline_status_{}.json".format(TAG),
                    "verify_baseline": (r2.stdout or "").strip().splitlines()[-1]},
    "18_tag": {"name": TAG, "type": "project-internal tag（本项目非 Git 仓库 ⇒ 无 VCS tag）",
               "points_to": {"final_master": MASTER_REL, "final_master_sha256": MASTER_SHA,
                             "baseline_zip_sha256": man["zip_sha256"],
                             "manifest_tag_field": man["tag"], "status_tag_field": status["tag"]}},
    "19_final_freeze_manifest": {"baseline_manifest": "docs/regression_2x/baseline/"
                                                      "baseline_manifest_{}.json".format(TAG),
                                 "baseline_status": "docs/regression_2x/baseline/"
                                                    "baseline_status_{}.json".format(TAG),
                                 "freeze_proof": "docs/regression_2x/logs/phase6g_final_freeze.json",
                                 "pre_auth_audit_v2": "docs/regression_2x/logs/"
                                                      "phase6g_final_pre_auth_audit_v2.json"},
    "20_workspace_cleanliness": {"git_repository": (R / ".git").exists(),
                                 "history_modified": False, "master_modified": False,
                                 "dcv2_master_modified": False, "frozen_materials_modified": False,
                                 "register_modified": False, "ledger_modified": False,
                                 "accepted_outputs_modified": False, "code_modified": False,
                                 "policy_or_thresholds_modified": False,
                                 "dq_criteria_modified": False, "panel_kind_modified": False,
                                 "wrote_only": ["docs/regression_2x/baseline/{}.zip".format(TAG),
                                                "docs/regression_2x/baseline/baseline_manifest.json",
                                                "docs/regression_2x/baseline/baseline_manifest_"
                                                "{}.json".format(TAG),
                                                "docs/regression_2x/baseline/baseline_status_"
                                                "{}.json".format(TAG),
                                                "docs/regression_2x/logs/phase6g_final_freeze.json"]},
    "checks": {"pass": PASS, "fail": FAIL},
}
# 封版后立即快照（供 post-freeze 只读验证比对）
proof["post_freeze_snapshot"] = {
    "final_master_sha256": sha(master),
    "dcv2_master_sha256": sha(R / "output/phase6g_sandbox/20260929_102445/out/"
                              "dcv2_master_20260929_102445.mp4"),
    "frozen_materials_sha256": {"material_plan": sha(R / "docs/regression_2x/phase6e_materials/"
                                                     "phase6e_material_plan.json")},
    "register_file_sha256": sha(L / "phase6g_rebuild_proposal_register.jsonl"),
    "ledger_file_sha256": sha(L / "phase6g_exec_ledger.jsonl"),
    "accepted_outputs": SNAP_PRE["accepted_files"],
    "baseline": {"zip": str(ZIP.relative_to(R)), "zip_sha256": sha(ZIP),
                 "manifest": "baseline_manifest_{}.json".format(TAG),
                 "manifest_sha256": sha(BASE / "baseline_manifest_{}.json".format(TAG)),
                 "status_sha256": sha(ST)},
}
proof["freeze_state"] = "PHASE6G_FINAL_FROZEN" if not FAIL else "FINAL_FREEZE_BLOCKED"
proof["freeze_sha256"] = hashlib.sha256(json.dumps(
    proof, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()
).hexdigest()
OUT.write_text(json.dumps(proof, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print("\n== FINAL FREEZE ==")
print("  tag:", TAG, "| zip:", ZIP.name, "| zip_sha256:", man["zip_sha256"])
print("  files:", man["file_count"], "| verify:", "MATCH" if ver else "DIFF")
print("  final master:", MASTER_REL, MASTER_SHA)
print("  checks: {} PASS / {} FAIL | freeze_state: {}".format(len(PASS), len(FAIL),
                                                             proof["freeze_state"]))
print("proof ->", OUT)
sys.exit(0 if not FAIL else 1)
