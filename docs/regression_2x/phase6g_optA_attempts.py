# -*- coding: utf-8 -*-
"""留存 **OPT-A 首次尝试失败**证据（音频被 -frames:v 截断），不覆盖任何既有记录。"""
import hashlib
import json
import pathlib
import subprocess

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
FF, FP = str(R / "bin" / "ffmpeg.exe"), str(R / "bin" / "ffprobe.exe")
OUT = L / "phase6g_optA_attempt1_failure.json"
cands = sorted((R / "output" / "phase6g_exec_batch2_optA").glob("*/out/*.mp4"))


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def amd5(p):
    r = subprocess.run([FF, "-v", "error", "-i", str(p), "-map", "0:a", "-c", "copy", "-f", "md5",
                        "-"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return (r.stdout or "").strip().split("=")[-1]


def streams(p):
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


rows = []
for p in cands:
    rows.append({"path": str(p.relative_to(R)), "sha256": sha(p), "audio_md5": amd5(p),
                 "streams": streams(p),
                 "is_first_attempt": amd5(p).startswith("6dff062c6537")})
first = next((r for r in rows if r["is_first_attempt"]), None)
final = next((r for r in rows if r["audio_md5"].startswith("de1effbc09d7")), None)
out = {"schema": "phase6g-optA-attempts-v1",
       "attempt1_impl": "单次 ffmpeg `-frames:v N -c:a copy`（**缺陷**：容器在视频结束处收尾 ⇒ 音轨被截断）",
       "attempt1_failure": first,
       "attempt1_diagnosis": {"audio_md5_expected": "de1effbc09d7…（母版）",
                              "audio_md5_observed": (first or {}).get("audio_md5"),
                              "audio_duration_s": ((first or {}).get("streams") or
                                                   {}).get("audio", {}).get("duration_s"),
                              "consequence": "A2（audio identity）硬门失败 ⇒ 立即 STOP，未继续、未绕过"},
       "attempt2_impl": "两步：① 仅视频精确到整帧（-an）；② 生产同一条 `_mux_master_audio` 复制母版音轨",
       "attempt2_result": final,
       "all_candidate_outputs": rows,
       "note": "两次 OPT-A 的产物均保留在各自沙箱中；失败尝试未被删除，也未覆盖任何既有记录。"}
OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print("attempt1: audio_md5={} audio_dur={}".format(
    (first or {}).get("audio_md5", "")[:14],
    ((first or {}).get("streams") or {}).get("audio", {}).get("duration_s")))
print("attempt2: audio_md5={} format_dur={}".format(
    (final or {}).get("audio_md5", "")[:14],
    (final or {}).get("streams", {}).get("format_duration_s")))
print("evidence ->", OUT.relative_to(R))
