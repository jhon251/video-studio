# -*- coding: utf-8 -*-
"""6-A 只读审计：Production Integrity + Directorial Quality（**不改代码/不重渲染/不动基线**）。

用法: python docs/regression_2x/phase6a_audit.py [project_id] [film_task_id]
产出: docs/regression_2x/logs/phase6a_audit.json
      docs/regression_2x/logs/phase6a_frames/*.png（供人工核验 Hook / 片尾）
"""
import json
import re
import sqlite3
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
LOGS = ROOT / "docs" / "regression_2x" / "logs"
FR = LOGS / "phase6a_frames"
FR.mkdir(parents=True, exist_ok=True)
PID = sys.argv[1] if len(sys.argv) > 1 else "p_96efdc03e1aa"
TASK = sys.argv[2] if len(sys.argv) > 2 else "t_d0a54bdf1810"     # v9（人工判 FAIL 的成片）
CFG = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8-sig"))
FFMPEG = CFG["tools"]["ffmpeg"]["path"]
FFPROBE = CFG["tools"]["ffmpeg"]["ffprobe"]
out = {"project_id": PID, "film_task": TASK, "mode": "6-A read-only audit"}


def sh(args, timeout=3600):
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=timeout)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def probe(p: Path) -> dict:
    rc, o = sh([FFPROBE, "-v", "error", "-print_format", "json", "-show_format", "-show_streams",
                str(p)])
    d = json.loads(o or "{}")
    v = next((s for s in d.get("streams") or [] if s.get("codec_type") == "video"), {})
    a = next((s for s in d.get("streams") or [] if s.get("codec_type") == "audio"), {})
    return {"container_s": round(float((d.get("format") or {}).get("duration") or 0), 3),
            "video_s": round(float(v.get("duration") or 0), 3),
            "audio_s": round(float(a.get("duration") or 0), 3),
            "frames": int(v.get("nb_frames") or 0), "v_codec": v.get("codec_name"),
            "a_codec": a.get("codec_name"), "a_rate": a.get("sample_rate"),
            "a_channels": a.get("channels"), "res": "{}x{}".format(v.get("width"), v.get("height")),
            "r_fps": v.get("r_frame_rate")}


con = sqlite3.connect("file:{}?mode=ro".format((ROOT / "projects" / "video_studio.db").as_posix()),
                      uri=True)
con.row_factory = sqlite3.Row
arts = {}
for r in con.execute("select artifact_id, task_id, type, path from artifacts where project_id=?",
                     (PID,)):
    arts.setdefault(r["type"], []).append(dict(r))


def newest(t, n=1):
    return (arts.get(t) or [])[-n:]


def load(a):
    p = Path(a["path"])
    p = p if p.is_absolute() else ROOT / p
    return json.loads(p.read_text(encoding="utf-8"))


script = load(newest("script_output")[0])
voice = load(newest("voice_output")[0])
render_meta = load(next(a for a in arts["render_output"] if a["task_id"] == TASK))
timeline = render_meta.get("material_timeline") or []
film = Path(render_meta.get("output") or "")
out["film"] = {"path": str(film), "exists": film.is_file(),
               "probe": probe(film) if film.is_file() else None,
               "bytes": film.stat().st_size if film.is_file() else None}
out["timeline_total_s"] = float(render_meta.get("duration_contract", {}).get("timeline_duration_s")
                                or 0.0)
out["narration_duration_s"] = voice.get("narration_duration_s")
out["voice_segment_durations"] = [d.get("duration_s") for d in voice.get("segment_details", [])]
out["voice_duration_contract"] = voice.get("duration_contract")
out["render_duration_contract"] = render_meta.get("duration_contract")
out["render_narration_completeness"] = render_meta.get("narration_completeness")
out["render_audio_loudness"] = render_meta.get("audio_loudness")

# ---------- 1. 音频连续性（silencedetect） ----------
if film.is_file():
    rc, o = sh([FFMPEG, "-hide_banner", "-nostats", "-i", str(film), "-af",
                "silencedetect=noise=-45dB:d=2", "-f", "null", "-"])
    starts = [float(x) for x in re.findall(r"silence_start:\s*(-?[\d.]+)", o)]
    ends = [float(x) for x in re.findall(r"silence_end:\s*(-?[\d.]+)", o)]
    durs = [float(x) for x in re.findall(r"silence_duration:\s*([\d.]+)", o)]
    gaps = [{"start": s, "end": (ends[i] if i < len(ends) else None),
             "dur": (durs[i] if i < len(durs) else None)} for i, s in enumerate(starts)]
    total_sil = sum(d for d in durs)
    out["audio_silence"] = {
        "noise_db": -45, "min_dur_s": 2, "blocks": len(starts),
        "first_start_s": starts[0] if starts else None,
        "longest_s": max(durs) if durs else None,
        "total_silence_s": round(total_sil, 2),
        "silence_ratio": round(total_sil / (out["timeline_total_s"] or 1), 4),
        "blocks_over_30s": [g for g in gaps if (g["dur"] or 0) > 30],
        "tail_gap_s": round((out["timeline_total_s"] or 0) - (starts[0] if starts else 0), 1),
        "sample": gaps[:6]}

# ---------- 2. 静态画面（freezedetect，降采样加速） ----------
if film.is_file():
    rc, o = sh([FFMPEG, "-hide_banner", "-nostats", "-i", str(film), "-an", "-vf",
                "scale=320:-2,freezedetect=n=-60dB:d=1", "-f", "null", "-"])
    fstarts = [float(x) for x in re.findall(r"freeze_start:\s*(-?[\d.]+)", o)]
    fends = [float(x) for x in re.findall(r"freeze_end:\s*(-?[\d.]+)", o)]
    fdurs = [float(x) for x in re.findall(r"freeze_duration:\s*([\d.]+)", o)]
    out["video_freeze"] = {
        "blocks": len(fstarts), "total_frozen_s": round(sum(fdurs), 1),
        "frozen_ratio": round(sum(fdurs) / (out["timeline_total_s"] or 1), 4),
        "longest_s": max(fdurs) if fdurs else None,
        "blocks_over_30s": sum(1 for d in fdurs if d > 30),
        "blocks_over_60s": sum(1 for d in fdurs if d > 60),
        "sample": [{"start": fstarts[i], "dur": fdurs[i]} for i in range(min(8, len(fstarts)))]}

# ---------- 3. 场景/素材：复用、静态保持、密度 ----------
holds, asset_secs, asset_scenes = [], Counter(), Counter()
for s in timeline:
    d = round(float(s.get("end_s", 0)) - float(s.get("start_s", 0)), 3)
    a = (s.get("selected_asset") or {}).get("asset_id") or "SOLID_COLOR"
    holds.append({"scene_id": s.get("scene_id"), "start": s.get("start_s"), "end": s.get("end_s"),
                  "hold_s": d, "asset": a,
                  "name": ((s.get("selected_asset") or {}).get("name") or "")[:60]})
    asset_secs[a] += d
    asset_scenes[a] += 1
tot = out["timeline_total_s"] or sum(h["hold_s"] for h in holds)
out["visual"] = {
    "scenes": len(timeline), "unique_assets": len(asset_scenes),
    "per_asset": {k: {"scenes": asset_scenes[k], "seconds": round(asset_secs[k], 1),
                      "share": round(asset_secs[k] / tot, 3)} for k in asset_scenes},
    "scene_changes_per_min": round(len(timeline) / (tot / 60), 2),
    "mean_hold_s": round(sum(h["hold_s"] for h in holds) / len(holds), 1),
    "holds_over_30s": sum(1 for h in holds if h["hold_s"] > 30),
    "holds_over_60s": sum(1 for h in holds if h["hold_s"] > 60),
    "holds": holds}

# ---------- 4. 旁白/时间轴错位 + 字幕 orphan ----------
segs = script.get("segments", [])
vd = [float(x or 0) for x in out["voice_segment_durations"]]
drift, acc_s, acc_v = [], 0.0, 0.0
for i, s in enumerate(segs):
    sd = float(s.get("duration_s") or 0)
    vdd = vd[i] if i < len(vd) else 0.0
    drift.append({"scene": i + 1, "script_start": round(acc_s, 1), "voice_start": round(acc_v, 1),
                  "drift_s": round(acc_v - acc_s, 1), "script_dur": round(sd, 1),
                  "voice_dur": round(vdd, 1)})
    acc_s += sd
    acc_v += vdd
out["narration_alignment"] = {
    "per_scene": drift, "final_drift_s": round(acc_v - acc_s, 1),
    "coverage_ratio": round((out["narration_duration_s"] or 0) / tot, 4),
    "narration_end_s": out["narration_duration_s"],
    "silent_tail_s": round(tot - (out["narration_duration_s"] or 0), 1)}
# 字幕 cue（v9 烧录用 ASS 在 artifacts 下；这里用字幕产物的 SRT 做 orphan 判定）
subs = newest("subtitle")[0]
sub_p = Path(subs["path"])
sub_p = sub_p if sub_p.is_absolute() else ROOT / sub_p
srt = load(subs).get("srt", "")
cues = [(float(a.split(":")[0]) * 3600 + float(a.split(":")[1]) * 60 + float(a.split(":")[2].replace(",", ".")),
         float(b.split(":")[0]) * 3600 + float(b.split(":")[1]) * 60 + float(b.split(":")[2].replace(",", ".")),
         t) for a, b, t in re.findall(
    r"(\d\d:\d\d:\d\d,\d\d\d) --> (\d\d:\d\d:\d\d,\d\d\d)\n(.+)", srt)]
narr_end = out["narration_duration_s"] or 0
orphan = [c for c in cues if c[0] > narr_end]
out["subtitles"] = {
    "artifact": subs["artifact_id"], "cues": len(cues),
    "first_cue_s": round(cues[0][0], 2) if cues else None,
    "last_cue_end_s": round(cues[-1][1], 2) if cues else None,
    "display_total_s": round(sum(b - a for a, b, _ in cues), 1),
    "coverage_ratio": round(sum(b - a for a, b, _ in cues) / tot, 4),
    "orphan_cues_over_silence": len(orphan),
    "orphan_share": round(len(orphan) / len(cues), 4) if cues else None,
    "orphan_first_s": round(orphan[0][0], 1) if orphan else None,
    "sample": [{"start": round(a, 1), "text": t[:40]} for a, b, t in cues[:3]]}

# ---------- 5. 关键词定位"核心论点/高潮"场景 ----------
KEY = ("AlphaGeometry", "Lean", "mathlib", "四色定理", "开普勒", "计算机", "机器", "形式化",
       "证明", "检查")
core = []
for i, s in enumerate(segs):
    txt = s.get("narration", "")
    hit = [k for k in KEY if k in txt]
    if hit:
        core.append({"scene": i + 1, "start_s": holds[i]["start"] if i < len(holds) else None,
                     "asset": holds[i]["asset"] if i < len(holds) else None,
                     "hits": hit[:4], "text": txt[:70]})
out["core_argument_scenes"] = {"count": len(core), "scenes": core[:12],
                              "distinct_assets_in_core": len({c["asset"] for c in core})}

# ---------- 6. 片尾/尾部 ----------
tail_from = max(tot - 120, 0)
tail_holds = [h for h in holds if h["end"] > tail_from]
out["ending"] = {"timeline_total_s": tot, "narration_end_s": narr_end,
                 "silent_tail_s": round(tot - narr_end, 1),
                 "tail_scenes": tail_holds,
                 "has_outro_keyword": any(
                     any(k in s.get("narration", "") for k in ("感谢", "订阅", "下期", "再见", "关注"))
                     for s in segs),
                 "last_narration": (segs[-1].get("narration", "")[:120] if segs else None),
                 "last_narration_time_s": round(sum(float(x.get("duration_s") or 0)
                                                    for x in segs[:-1]), 1) if segs else None}

# ---------- 7. QA / compliance / critic 判定（本项目的既有闸门输出） ----------
for t in ("qa_report", "compliance_output", "critic_final_output", "analytics_output",
          "thumbnail_output", "platform_output", "metadata_output"):
    lst = arts.get(t) or []
    if lst:
        d = load(lst[-1])
        out.setdefault("agent_reports", {})[t] = {
            k: (d.get(k) if not isinstance(d.get(k), (dict, list)) else str(d.get(k))[:160])
            for k in list(d)[:8]}
con.close()

# ---------- 8. 抽帧（Hook / 中段 / 片尾）供人工核验 ----------
if film.is_file():
    frames = []
    for t in (5, 40, 16 * 60 + 1, 16 * 60 + 30, int(out["timeline_total_s"]) - 20):
        fp = FR / "v9_t{:05d}s.png".format(t)
        sh([FFMPEG, "-y", "-v", "error", "-ss", str(t), "-i", str(film), "-frames:v", "1", str(fp)])
        if fp.is_file():
            frames.append(fp.relative_to(ROOT).as_posix())
    out["frames"] = frames

(LOGS / "phase6a_audit.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                        encoding="utf-8")
print("film:", out["film"]["path"], out["film"]["probe"])
print("silence:", {k: out["audio_silence"][k] for k in
                   ("blocks", "first_start_s", "longest_s", "total_silence_s", "silence_ratio",
                    "tail_gap_s")})
print("freeze :", {k: out["video_freeze"][k] for k in
                   ("blocks", "total_frozen_s", "frozen_ratio", "longest_s", "blocks_over_60s")})
print("visual :", {k: out["visual"][k] for k in
                   ("scenes", "unique_assets", "scene_changes_per_min", "mean_hold_s",
                    "holds_over_60s")}, "| per_asset:",
      {k: v["scenes"] for k, v in out["visual"]["per_asset"].items()})
print("narr   :", {k: out["narration_alignment"][k] for k in
                   ("final_drift_s", "coverage_ratio", "silent_tail_s")})
print("subs   :", {k: out["subtitles"][k] for k in
                   ("cues", "coverage_ratio", "orphan_cues_over_silence", "orphan_share",
                    "orphan_first_s")})
print("core   :", out["core_argument_scenes"]["count"], "scenes |",
      "distinct assets:", out["core_argument_scenes"]["distinct_assets_in_core"])
print("ending :", {k: out["ending"][k] for k in
                   ("narration_end_s", "silent_tail_s", "has_outro_keyword")})
print("json ->", LOGS / "phase6a_audit.json")
