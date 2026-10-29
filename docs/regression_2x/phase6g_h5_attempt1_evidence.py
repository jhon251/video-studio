# -*- coding: utf-8 -*-
"""保全 H5 attempt-1（执行成功但验收 harness 读错证据键 ⇒ 未写台账）的完整证据。"""
import hashlib
import json
import pathlib
import subprocess
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
SB = R / "output/phase6g_exec_h5/20260929_150733"
FF, FP = str(R / "bin/ffmpeg.exe"), str(R / "bin/ffprobe.exe")
OUT = R / "docs/regression_2x/logs/phase6g_h5_attempt1_harness_issue.json"
ASSETS = {"S05": ("65377b888b778226", "Russell_PM_1+1=2.png"),
          "S11": ("1e9d2ab4e64ef982", "S11-D0_LIPIcs-ITP-2023-24_p08_tactic-state-rw.png")}


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def probe(p):
    r = subprocess.run([FP, "-v", "error", "-show_entries",
                        "format=duration:stream=codec_type,duration,nb_frames", "-of", "json",
                        str(p)], capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    j = json.loads(r.stdout or "{}")
    o = {"duration_s": round(float((j.get("format") or {}).get("duration") or 0), 4)}
    for s in (j.get("streams") or []):
        o[s["codec_type"]] = {"duration_s": round(float(s.get("duration") or 0), 4),
                              "nb_frames": s.get("nb_frames")}
    return o


def amd5(p):
    r = subprocess.run([FF, "-v", "error", "-i", str(p), "-map", "0:a", "-c", "copy", "-f", "md5",
                        "-"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return (r.stdout or "").strip().split("=")[-1]


out = SB / "out/H5_rp-0ebebb71f99c.mp4"
master = R / "output/phase6g_sandbox/20260929_102445/out/dcv2_master_20260929_102445.mp4"
rec = {"schema": "phase6g-h5-attempt1-evidence-v1", "stage": "6-G / H5 (attempt 1)",
       "sandbox": str(SB.relative_to(R)),
       "status": "EXECUTION_SUCCEEDED_BUT_ACCEPTANCE_HARNESS_BUG__NO_LEDGER_ENTRY_WRITTEN",
       "harness_bug": {
           "gate": "C1 内置逐镜替换证据",
           "cause": "验收脚本从 `res['asset_evidence']` 读取，但执行器证据实际位于 "
                    "`res['exec_evidence']['asset_evidence']`（见 core/execution.py L212-216）"
                    "⇒ 读到空 dict，误判 replaced=None、per_scene=[]",
           "consequence": "该次运行未通过自定义验收 ⇒ 依设计**未写台账、未报告成功**；"
                          "沙箱产物与中间证据全部保留（fail-closed：先验收后记录）",
           "not_a_proposal_failure": True,
           "fixed_in": "docs/regression_2x/phase6g_exec_h5.py（改读 exec_evidence）"},
       "output": {"path": str(out.relative_to(R)), "bytes": out.stat().st_size,
                  "sha256": sha(out), "audio_md5": amd5(out), **probe(out)},
       "master_audio_md5": amd5(master),
       "per_scene_renders": [
           {"scene": s, "file": str(p.relative_to(R)), "bytes": p.stat().st_size,
            "sha256": sha(p), **probe(p)}
           for s in ("S05", "S11")
           for p in sorted((SB / "work/H5/work").glob("sv_*_a{}_*.mp4".format(s)))],
       "caption_ass": [{"file": p.name, "sha256": sha(p), "bytes": p.stat().st_size}
                       for p in sorted((SB / "work/H5/work").glob("cap_*.ass"))],
       "evidence_frames": [{"file": p.name, "sha256": sha(p), "bytes": p.stat().st_size}
                           for p in sorted((SB / "work/H5/work").glob("ev_*.png"))],
       "duration_check_files": [p.name for p in sorted((SB / "work/H5/work").glob("cv_*.txt"))],
       "notes": "attempt-1 与 attempt-2 为**同一 proposal/同一素材/同一绑定**（无任何参数变化）；"
                "attempt-2 仅修正验收脚本的读取键。素材文件 sha256 在两次运行间未变（见 attempt-2 报告）。"}
rec["record_sha256"] = hashlib.sha256(json.dumps(
    rec, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()
).hexdigest()
OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print(json.dumps({k: rec[k] for k in ("sandbox", "output", "master_audio_md5")},
                 ensure_ascii=False, indent=1, default=str))
print("per_scene_renders:", json.dumps(rec["per_scene_renders"], ensure_ascii=False)[:400])
print("attempt1 evidence ->", OUT)
