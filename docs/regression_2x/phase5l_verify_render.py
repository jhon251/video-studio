# -*- coding: utf-8 -*-
"""5-L：重渲染（render v8 = `t_30070f93a77e`）**验收**：视频轨 21 s 问题是否消除 + 其余一切未变。

用法: python docs/regression_2x/phase5l_verify_render.py
产出: docs/regression_2x/logs/phase5l_render_verify.json
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
PID = "p_96efdc03e1aa"
NEW_TASK = "t_30070f93a77e"            # render v8（5-L 重渲染）
OLD_TASK = "t_898378f6b0f8"            # render v7（5-K 前，视频轨短 21 s）
OLD_FILM_SHA = "3f3f0c010d178e415d0f19f7855e5f69249ec562550a94e23e045f0653a411d1"
CFG = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8-sig"))
FFPROBE = CFG["tools"]["ffmpeg"]["ffprobe"]
FFMPEG = CFG["tools"]["ffmpeg"]["path"]


def sha(p: Path) -> str:
    import hashlib
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
res = {"project_id": PID, "new_task": NEW_TASK, "old_task": OLD_TASK}

# 新任务/产物
row = con.execute("select task_id, task_type, version, status, error, artifacts from tasks "
                  "where task_id=?", (NEW_TASK,)).fetchone()
res["new_task_row"] = dict(row) if row else None
arts = [dict(r) for r in con.execute(
    "select artifact_id, type, path, sha256, size from artifacts where task_id=?", (NEW_TASK,))]
res["new_artifacts"] = [{k: str(v)[:200] for k, v in a.items()} for a in arts]
render = next((a for a in arts if a["type"] == "render_output"), None)
attr = next((a for a in arts if a["type"] == "attribution"), None)

# 新成片
new_film = None
if render:
    rp = Path(render["path"])
    rp = rp if rp.is_absolute() else ROOT / rp
    meta = json.loads(rp.read_text(encoding="utf-8"))
    film = meta.get("path") or meta.get("film") or meta.get("output")
    fp = Path(film) if film else None
    if fp and not fp.is_absolute():
        fp = ROOT / fp
    new_film = fp
    res["render_meta_keys"] = sorted(meta.keys())[:20]
    res["render_meta"] = {k: str(v)[:200] for k, v in meta.items()
                          if k in ("path", "duration_s", "timeline_duration_s", "material_assembly",
                                   "scenes", "scenes_with_asset", "codec", "resolution",
                                   "video_duration_s", "audio_duration_s", "loudness", "summary")}

old_film = ROOT / "projects" / PID / "output" / "{}_draft.mp4".format(OLD_TASK)
res["old_film"] = {"path": str(old_film), "sha256": sha(old_film) if old_film.is_file() else None,
                   "unchanged": (sha(old_film) == OLD_FILM_SHA) if old_film.is_file() else None}
res["old_film_probe"] = probe(old_film) if old_film.is_file() else None
res["new_film"] = {"path": str(new_film) if new_film else None,
                   "exists": bool(new_film and new_film.is_file()),
                   "sha256": sha(new_film) if new_film and new_film.is_file() else None,
                   "bytes": new_film.stat().st_size if new_film and new_film.is_file() else None}
if new_film and new_film.is_file():
    res["new_film_probe"] = probe(new_film)
    res["new_film_loudness"] = ebur128(new_film)

# 时间轴权威总时长（来自 render 元数据或旧成片容器）
tl_total = None
for k in ("timeline_duration_s", "duration_s"):
    if render:
        m = res.get("render_meta") or {}
        if m.get(k):
            try:
                tl_total = float(m[k])
            except ValueError:
                pass
    if tl_total:
        break
if tl_total is None and res.get("old_film_probe"):
    tl_total = res["old_film_probe"]["fmt_s"]
res["timeline_total_s"] = tl_total

# 前后快照对比（topic/script/claims/人工决策必须未变）
before_p = LOGS / "phase5l_snapshot_before.json"
after_p = LOGS / "phase5l_snapshot_after.json"
if before_p.is_file() and after_p.is_file():
    b = json.loads(before_p.read_text(encoding="utf-8"))
    a = json.loads(after_p.read_text(encoding="utf-8"))
    key_types = ("topic_output", "script_output", "claims_map", "editing_plan_output",
                 "structure_output", "research_output", "voice_output", "subtitle")
    def sig(snap, t):
        return sorted((x["artifact_id"], x["file_sha256"]) for x in snap["artifacts"]
                      if x["type"] == t)
    res["content_unchanged"] = {t: {"same": sig(b, t) == sig(a, t), "before": sig(b, t)[:2],
                                    "after": sig(a, t)[:2]} for t in key_types}
    res["claims_unchanged"] = (b["claims_by_status"] == a["claims_by_status"]
                               and b["claim_ids"] == a["claim_ids"])
    res["decisions_unchanged"] = (b["decisions"]["count"] == a["decisions"]["count"]
                                  and b["decisions"]["by_made_by"] == a["decisions"]["by_made_by"])
    res["films_before"] = sorted(b["films"])
    res["films_after"] = sorted(a["films"])
    res["films_changed"] = sorted(k for k in b["films"]
                                  if k in a["films"] and b["films"][k]["sha256"] != a["films"][k]["sha256"])
    res["films_added"] = sorted(set(a["films"]) - set(b["films"]))

# 归因 1:1 校验
if attr:
    ap = Path(attr["path"])
    ap = ap if ap.is_absolute() else ROOT / ap
    am = json.loads(ap.read_text(encoding="utf-8"))
    entries = am if isinstance(am, list) else (am.get("entries") or am.get("items") or [])
    res["attribution"] = {"entries": len(entries),
                          "ids": [e.get("scene_id") for e in entries][:30]}
    bad = []
    for e in entries:
        f = (e.get("selected_asset") or {}).get("path") or e.get("path")
        s = (e.get("selected_asset") or {}).get("sha256") or e.get("sha256")
        if f and s:
            fp2 = Path(f)
            fp2 = fp2 if fp2.is_absolute() else ROOT / fp2
            if fp2.is_file() and sha(fp2) != s:
                bad.append(str(fp2))
    res["attribution"]["sha_mismatch"] = bad
con.close()

(LOGS / "phase5l_render_verify.json").write_text(json.dumps(res, ensure_ascii=False, indent=1),
                                                 encoding="utf-8")
print("new task:", res["new_task_row"])
print("new film :", res["new_film"])
print("new probe:", res.get("new_film_probe"))
print("loudness :", res.get("new_film_loudness"))
print("old film unchanged:", res["old_film"].get("unchanged"), "| old probe:", res.get("old_film_probe"))
print("timeline total:", res.get("timeline_total_s"))
print("content unchanged:", {k: v["same"] for k, v in (res.get("content_unchanged") or {}).items()})
print("claims unchanged:", res.get("claims_unchanged"), "| decisions unchanged:",
      res.get("decisions_unchanged"))
print("films changed:", res.get("films_changed"), "| added:", res.get("films_added"))
print("attribution:", res.get("attribution"))
print("json ->", LOGS / "phase5l_render_verify.json")
