# -*- coding: utf-8 -*-
"""6-G / Batch 2 收尾（只读取证 + 如实落盘）：
  · 核实登记链/执行台账状态（H3c-1 已落账；H3c-2 因 A1 硬门失败被拒绝验收）
  · 复测 H3c-2 成败因（duration 误差来源：视频/音频流时长、PI-4、逐窗口帧数）
  · 追加 H3c-2 的**执行记录（acceptance=FAILED）**到 append-only 台账（如实记录）
  · 生成 batch2 报告（STOPPED_AT_HARD_GATE）

不修改任何阈值/门禁；不 promote；不写 DB/baseline/tag；不改历史 artifact。
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
from video_studio.core import revision as core_revision              # noqa: E402

L = R / "docs" / "regression_2x" / "logs"
OUT = L / "phase6g_exec_batch2.json"
LEDGER = L / "phase6g_exec_ledger.jsonl"
REGISTER = L / "phase6g_rebuild_proposal_register.jsonl"
FF, FP = str(R / "bin" / "ffmpeg.exe"), str(R / "bin" / "ffprobe.exe")
PROD = 978.656
B1 = json.loads((L / "phase6g_exec_batch1.json").read_text(encoding="utf-8"))
P2 = json.loads((L / "phase6f_rebuild_plan_v2.json").read_text(encoding="utf-8"))
N0 = json.loads((L / "phase6g_n0_dcv2_master.json").read_text(encoding="utf-8"))
regs = core_revision.load_register(str(REGISTER))
led = EX.load_ledger(str(LEDGER))
chain = EX.verify_chain(led)
print("登记链 {} 条 chain_ok={} | 执行台账 {} 条 chain_ok={}".format(
    len(regs), core_revision.verify_register_chain(regs).get("ok"), len(led), chain.get("ok")))
for e in led:
    print("   seq {} {} {} state={}".format(e.get("seq"), e.get("stage"),
                                            str(e.get("proposal_id"))[:18],
                                            e.get("acceptance", "ACCEPTED")))


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def streams(p):
    r = subprocess.run([FP, "-v", "error", "-show_entries",
                        "format=duration:stream=codec_type,duration,nb_frames", "-of", "json", str(p)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    j = json.loads(r.stdout or "{}")
    out = {"format_duration_s": round(float((j.get("format") or {}).get("duration") or 0), 4)}
    for s in (j.get("streams") or []):
        out[s.get("codec_type")] = {"duration_s": round(float(s.get("duration") or 0), 4),
                                    "nb_frames": s.get("nb_frames")}
    return out


def amd5(p):
    r = subprocess.run([FF, "-v", "error", "-i", str(p), "-map", "0:a", "-c", "copy", "-f", "md5", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return (r.stdout or "").strip().split("=")[-1]


# ---- 找到两次执行的输出（H3c-1 来自台账；H3c-2 来自沙箱，未验收）
sb = sorted((R / "output" / "phase6g_exec_batch2").glob("*"))
sb_ok = [d for d in sb if (d / "out" / "H3c-1_rp-6596bbd35bc9.mp4").is_file()]
sandbox = sb_ok[-1] if sb_ok else sb[-1]
h1 = sandbox / "out" / "H3c-1_rp-6596bbd35bc9.mp4"
h2 = sandbox / "out" / "H3c-2_rp-4db3b4bd15e5.mp4"
print("\nsandbox:", sandbox.relative_to(R), "| H3c-1 exists:", h1.is_file(),
      "| H3c-2 exists:", h2.is_file())
meas = {}
for tag, p in (("H3c-1", h1), ("H3c-2", h2)):
    if p.is_file():
        st = streams(p)
        meas[tag] = {"path": str(p.relative_to(R)), "sha256": sha(p), "bytes": p.stat().st_size,
                     "streams": st, "audio_md5": amd5(p),
                     "format_duration_s": st["format_duration_s"],
                     "delta_vs_timeline_s": round(st["format_duration_s"] - PROD, 4),
                     "video_duration_s": (st.get("video") or {}).get("duration_s"),
                     "audio_duration_s": (st.get("audio") or {}).get("duration_s"),
                     "video_frames": (st.get("video") or {}).get("nb_frames")}
        print("  {} dur={} (delta {:+.4f}) video={} frames={} audio_md5={}".format(
            tag, meas[tag]["format_duration_s"], meas[tag]["delta_vs_timeline_s"],
            meas[tag]["video_duration_s"], meas[tag]["video_frames"],
            meas[tag]["audio_md5"][:12]))

# ---- H3c-2 误差来源诊断（逐窗口帧量化）
diag = {"tolerance_s": 0.05, "note": "A1 硬门 ±0.05 s（未修改，不绕过）"}
if h2.is_file() and h1.is_file():
    diag["delta_h2_minus_h1_s"] = round(meas["H3c-2"]["format_duration_s"]
                                        - meas["H3c-1"]["format_duration_s"], 4)
diag["hypothesis"] = ("窗口重编码的帧量化累积：每个重编码窗口按 25fps 向上取整到整帧"
                      "（≤40 ms/窗口），H3c-2 的窗口集合（含末镜 S21 收尾）累计 +64 ms；"
                      "母版音轨为流复制 ⇒ 音轨时长不变（见 audio_md5 与 audio duration）")
diag["determinism"] = ("执行器为确定性编码（固定参数/无随机）⇒ 直接重跑预期复现同一 +64 ms；"
                       "需要**确定性修正**（组装后按时间轴精确 trim/pad）或**显式复核该容差**")
diag["not_a_subtitle_or_audio_issue"] = True

# ---- 若台账尚无 H3c-2 记录，则如实追加（acceptance = FAILED）
if h2.is_file() and not any(e.get("stage") == "H3c-2" for e in led):
    rec = EX.append_execution(str(LEDGER), {
        "schema": "revision-execution-v1", "proposal_id": "rp-4db3b4bd15e5", "label": "H3c-2",
        "action": "split_scene", "proposal_sha256": next(
            EX.proposal_sha256(r) for r in regs if r.get("label") == "H3c-2"),
        "approval_id": EX.approval_id("rp-4db3b4bd15e5", "APPROVE", "human"),
        "approved_by": "human", "stage": "H3c-2",
        "input_sha256": sha(R / B1["stages"][-1]["output"]["path"]),
        "output_path": str(h2.relative_to(R)), "output_sha256": sha(h2),
        "duration_s": meas["H3c-2"]["format_duration_s"], "audio_md5": meas["H3c-2"]["audio_md5"],
        "timeline_identity": N0["timeline_identity"]["identity_sha256"],
        "caption_time_base": "dcv2",
        "acceptance": "FAILED", "acceptance_gate": "A1 duration == 978.656±0.05",
        "acceptance_measured_s": meas["H3c-2"]["format_duration_s"],
        "acceptance_delta_s": meas["H3c-2"]["delta_vs_timeline_s"],
        "why": "执行器 SUCCEEDED，但**验收硬门 A1 失败**（时长超差 +0.064s > ±0.05s）⇒ 按规则 STOP，"
               "不得绕过/降低阈值；该产物**未被接受**、不进入后续链路",
        "sandbox": str(sandbox.relative_to(R)),
        "executed_at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S")})
    print("\n追加 H3c-2 台账记录 seq={} acceptance=FAILED".format(rec.get("seq")))

led = EX.load_ledger(str(LEDGER))
chain = EX.verify_chain(led)
# ---- 已接受状态下仍 >25s 的场景（H3c-1 已接受；H3c-2 未被接受 ⇒ 其 6 场景仍未切分）
h3c2_scenes = ["S21", "S13", "S19", "S02", "S05", "S20"]
remaining = [{"scene_id": s, "duration_s": round(next(
    c["new_timeline_window_s"][1] - c["new_timeline_window_s"][0] for c in
    P2["remapping_21_segments"] if c["scene_id"] == s), 3)} for s in h3c2_scenes]
report = {
    "schema": "phase6g-exec-batch2-v1", "stage": "6-G / Batch 2",
    "state": "BATCH2_STOPPED_AT_HARD_GATE",
    "authorized": "OPT-1（H3c → H3c-1 + H3c-2）；未选择 OPT-2；未修改局部化策略",
    "policy_unchanged": {"max_scenes_per_proposal": EX.POLICY["max_scenes_per_proposal"],
                         "max_share_of_film_per_proposal":
                             EX.POLICY["max_share_of_film_per_proposal"],
                         "target_hold_s": 25.0, "duration_tolerance_s": 0.05},
    "proposals_created": [{"label": r.get("label"), "proposal_id": r.get("proposal_id"),
                           "proposal_sha256": EX.proposal_sha256(r), "register_seq": r.get("seq"),
                           "scenes": (r.get("affected_scope") or {}).get("scenes"),
                           "share_of_film": (r.get("affected_scope") or {}).get("share_of_film"),
                           "origin": "本回合 OPT-1 裁定后新登记（此前不存在整体 H3c proposal）"}
                          for r in regs],
    "proposal_register": {"path": str(REGISTER.relative_to(R)), "entries": len(regs),
                          "chain": core_revision.verify_register_chain(regs)},
    "input_chain": {"batch1_final": B1["stages"][-1]["output"]["path"],
                    "sha256": B1["stages"][-1]["output"]["sha256"]},
    "sandbox": str(sandbox.relative_to(R)),
    "stages": [
        {"stage": "H3c-1", "proposal_id": "rp-6596bbd35bc9", "state": "PASS",
         "measured": meas.get("H3c-1"), "ledger": next((e for e in led if e.get("stage") == "H3c-1"),
                                                       None),
         "gates": ["B0 输入 sha 一致", "提案身份/登记一致", "DCv2 timeline identity",
                   "caption time base = dcv2", "execution gate", "执行 SUCCEEDED",
                   "A1 duration 978.656", "A2 audio identity", "B1 ASS==DCv2 (13 窗口)",
                   "B2 负对照 v1 不同", "B3 字形差分<0.15", "C1 切点 all_distinct (7)",
                   "C2 子镜<=25s", "D1 DCv2 pre 全 PASS", "D2 post PI-3 PASS",
                   "D3 冻结复核 PASS", "E1 无黑帧", "F1 隔离全部未变"],
         "DQ_measured": {"DQ-2": "FAIL(unique 5)", "DQ-3": "PASS(max_hold 50.816, 41 entries)",
                         "DQ-4": "PASS(2.514/min)"}},
        {"stage": "H3c-2", "proposal_id": "rp-4db3b4bd15e5", "state": "FAIL",
         "failed_gate": "A1 duration == 978.656±0.05",
         "measured": meas.get("H3c-2"),
         "detail": {"required_s": PROD, "tolerance_s": 0.05,
                    "measured_s": meas["H3c-2"]["format_duration_s"],
                    "delta_s": meas["H3c-2"]["delta_vs_timeline_s"],
                    "action": "立即 STOP（未继续、未绕过、未降低阈值）；产物未被接受"},
         "accepted": False}],
    "diagnosis": diag,
    "remaining_over_25s_in_accepted_lineage": remaining,
    "remaining_count": len(remaining),
    "batch1_unchanged": all(sha(R / s["output"]["path"]) == s["output"]["sha256"]
                            for s in B1["stages"]),
    "ledger": {"path": str(LEDGER.relative_to(R)), "entries": len(led), "chain": chain},
    "claims": {"promoted": False, "db_written": False, "baseline_or_tag_changed": False,
               "historical_artifact_changed": False, "historical_candidates_used": False,
               "threshold_relaxed": False, "third_batch_authorized": False,
               "h5_e3_e4_e5_executed": False, "h3c2_accepted": False},
}
report["report_sha256"] = hashlib.sha256(json.dumps(
    report, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()
).hexdigest()
OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print("\nstate:", report["state"], "| >25s 剩余（已接受链路）:", len(remaining), remaining)
print("batch1_unchanged:", report["batch1_unchanged"], "| ledger", len(led), chain.get("ok"))
print("report ->", OUT)
