# -*- coding: utf-8 -*-
"""5-M 验收：新字幕渲染（render v9）——成片契约 + 画面抽帧 + 内容/决策未变。

用法: python docs/regression_2x/phase5m_verify_render.py [task_id]
产出: docs/regression_2x/logs/phase5m_render_verify.json + logs/phase5m_frames/*.png
"""
import hashlib
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
LOGS = ROOT / "docs" / "regression_2x" / "logs"
FRAMES = LOGS / "phase5m_frames"
FRAMES.mkdir(parents=True, exist_ok=True)
PID = "p_96efdc03e1aa"
TASK = sys.argv[1] if len(sys.argv) > 1 else "t_d0a54bdf1810"      # render v9
PREV = "t_30070f93a77e"                                            # render v8（5-L，无字幕样式问题）
CFG = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8-sig"))
FFMPEG = CFG["tools"]["ffmpeg"]["path"]
FFPROBE = CFG["tools"]["ffmpeg"]["ffprobe"]
TIMELINE_S = 1532.0


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def probe(p: Path) -> dict:
    r = subprocess.run([FFPROBE, "-v", "error", "-print_format", "json", "-show_format",
                        "-show_streams", str(p)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    d = json.loads(r.stdout or "{}")
    v = next((s for s in d.get("streams") or [] if s.get("codec_type") == "video"), {})
    a = next((s for s in d.get("streams") or [] if s.get("codec_type") == "audio"), {})
    return {"fmt_s": round(float((d.get("format") or {}).get("duration") or 0), 3),
            "v_s": round(float(v.get("duration") or 0), 3),
            "a_s": round(float(a.get("duration") or 0), 3),
            "frames": int(v.get("nb_frames") or 0), "r_fps": v.get("r_frame_rate"),
            "v_codec": v.get("codec_name"), "a_codec": a.get("codec_name"),
            "wxh": "{}x{}".format(v.get("width"), v.get("height"))}


def ebur128(p: Path) -> dict:
    r = subprocess.run([FFMPEG, "-hide_banner", "-nostats", "-i", str(p), "-filter_complex",
                        "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = (r.stderr or "") + (r.stdout or "")
    i = re.findall(r"I:\s*(-?\d+\.\d+)\s*LUFS", out)
    tp = re.findall(r"Peak:\s*(-?\d+\.\d+)\s*dBFS", out)
    return {"I_LUFS": float(i[-1]) if i else None, "TP_dBFS": float(tp[-1]) if tp else None}


con = sqlite3.connect("file:{}?mode=ro".format((ROOT / "projects" / "video_studio.db").as_posix()),
                      uri=True)
con.row_factory = sqlite3.Row
res = {"project_id": PID, "task": TASK, "prev_task": PREV}
row = con.execute("select task_id, task_type, version, status, error, artifacts from tasks "
                  "where task_id=?", (TASK,)).fetchone()
res["task_row"] = dict(row) if row else None
arts = [dict(r) for r in con.execute(
    "select artifact_id, type, path, sha256, size from artifacts where task_id=?", (TASK,))]
res["artifacts"] = [{k: str(v)[:200] for k, v in a.items()} for a in arts]
render = next((a for a in arts if a["type"] == "render_output"), None)
if render:
    rp = Path(render["path"])
    rp = rp if rp.is_absolute() else ROOT / rp
    meta = json.loads(rp.read_text(encoding="utf-8"))
    res["render_meta"] = {k: meta.get(k) for k in
                          ("output", "video_duration_s", "video_duration_delta_s",
                           "video_duration_ok", "material_assembly", "scene_count",
                           "scenes_with_asset", "narration_state", "duration_contract",
                           "audio_loudness", "summary")}
    film = Path(meta.get("output") or "")
    if film.is_file():
        res["film"] = {"path": str(film), "bytes": film.stat().st_size, "sha256": sha(film),
                       "probe": probe(film), "loudness": ebur128(film)}
        # 抽帧（覆盖不同镜头/字幕位置）供人工核验
        frames = []
        for t in (20, 120, 420, 900, 1400):
            fp = FRAMES / "v9_t{:04d}s.png".format(t)
            subprocess.run([FFMPEG, "-y", "-v", "error", "-ss", str(t), "-i", str(film),
                            "-frames:v", "1", str(fp)], capture_output=True)
            if fp.is_file():
                frames.append(str(fp.relative_to(ROOT)))
        res["frames"] = frames
# 前版成片（v8）仍在且未变
prev_film = ROOT / "projects" / PID / "output" / "{}_draft.mp4".format(PREV)
res["prev_film"] = {"path": str(prev_film), "exists": prev_film.is_file(),
                    "sha256": sha(prev_film) if prev_film.is_file() else None,
                    "probe": probe(prev_film) if prev_film.is_file() else None}
# 字幕产物（新 cue 版）
subs = [dict(r) for r in con.execute(
    "select artifact_id, task_id, type, path, created_at from artifacts where project_id=? and "
    "type='subtitle' order by created_at", (PID,))]
res["subtitle_artifacts"] = [{k: str(v)[:160] for k, v in s.items()} for s in subs]
if subs:
    sp = Path(subs[-1]["path"])
    sp = sp if sp.is_absolute() else ROOT / sp
    d = json.loads(sp.read_text(encoding="utf-8"))
    srt = d.get("srt", "")
    res["subtitle"] = {"artifact": subs[-1]["artifact_id"], "segments": d.get("segments"),
                       "cues": d.get("cues"), "srt_entries": srt.count("-->"),
                       "srt_chars": len(srt),
                       "first_cues": [b.splitlines()[2] for b in srt.strip().split("\n\n")[:4]]}
# 内容/决策未变（与 5-L after 快照对比）
snap = LOGS / "phase5l_snapshot_after.json"
if snap.is_file():
    b = json.loads(snap.read_text(encoding="utf-8"))
    key_types = ("topic_output", "script_output", "claims_map", "editing_plan_output",
                 "structure_output", "research_output", "voice_output")
    now_arts = [dict(r) for r in con.execute(
        "select artifact_id, type, path, sha256 from artifacts where project_id=?", (PID,))]

    def sig(items, t):
        out = []
        for a in items:
            if a["type"] != t:
                continue
            p = Path(a["path"])
            p = p if p.is_absolute() else ROOT / p
            out.append((a["artifact_id"], sha(p) if p.is_file() else None))
        return sorted(out)
    res["content_unchanged"] = {t: sig(b["artifacts"], t) == sig(now_arts, t) for t in key_types}
    res["claims_unchanged"] = ({r[0]: r[1] for r in con.execute(
        "select status, count(*) from claims where project_id=? group by status", (PID,))}
        == b["claims_by_status"])
    res["decisions_unchanged"] = con.execute(
        "select count(*) from decisions where project_id=?", (PID,)).fetchone()[0] == \
        b["decisions"]["count"]
con.close()
(LOGS / "phase5m_render_verify.json").write_text(json.dumps(res, ensure_ascii=False, indent=1),
                                                 encoding="utf-8")
print("task:", res["task_row"])
print("film:", (res.get("film") or {}).get("path"), (res.get("film") or {}).get("bytes"), "bytes")
print("probe:", (res.get("film") or {}).get("probe"))
print("loudness:", (res.get("film") or {}).get("loudness"))
print("video_duration_ok:", (res.get("render_meta") or {}).get("video_duration_ok"),
      "| delta:", (res.get("render_meta") or {}).get("video_duration_delta_s"))
print("subtitle:", res.get("subtitle"))
print("content unchanged:", res.get("content_unchanged"))
print("claims/decisions unchanged:", res.get("claims_unchanged"), res.get("decisions_unchanged"))
print("frames:", res.get("frames"))
print("json ->", LOGS / "phase5m_render_verify.json")
