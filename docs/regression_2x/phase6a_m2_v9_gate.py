# -*- coding: utf-8 -*-
"""6-A/M2：把**真实 v9 成片**（p_96efdc03e1aa / t_d0a54bdf1810_draft.mp4）喂给 M2 硬门（只读）。

与 `tests/integrity_gates_test.py` G1（真值集数值复算）互补：这里用**真实产物 + 真实成片文件**
直接调用 `pre_render_gate` / `post_render_gate`，证明"v9 这类短旁白成片在 M2 之后会被阻断"。

严格只读：
  · DB 以 `mode=ro` + `PRAGMA query_only=ON` 打开；
  · 只对既有 MP4 做 ffprobe / silencedetect（不产出文件、不重渲染、不写项目目录）；
  · 前后对项目 output/ 目录与成片 sha256 取证（必须逐字节不变）；
  · 报告写到 `logs/phase6a_m2_v9_gate.json`（报告文件，不是产线产物）。

用法: python docs/regression_2x/phase6a_m2_v9_gate.py
"""
import hashlib
import json
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
LOGS = ROOT / "docs" / "regression_2x" / "logs"
DB = ROOT / "projects" / "video_studio.db"
PID = "p_96efdc03e1aa"
FILM_TASK = "t_d0a54bdf1810"
CFG = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8-sig"))
FFMPEG = CFG["tools"]["ffmpeg"]["path"]
FFPROBE = CFG["tools"]["ffmpeg"]["ffprobe"]

from video_studio.core import integrity as I  # noqa: E402


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def manifest(d: Path) -> dict:
    return {p.relative_to(d).as_posix(): (p.stat().st_size, round(p.stat().st_mtime, 3))
            for p in sorted(d.rglob("*")) if p.is_file()}


con = sqlite3.connect("file:{}?mode=ro".format(DB.as_posix()), uri=True)
con.row_factory = sqlite3.Row
con.execute("PRAGMA query_only=ON")
recs = [dict(r) for r in con.execute(
    "select artifact_id, task_id, type, path, created_at from artifacts where project_id=? "
    "order by created_at", (PID,))]
con.close()
by_type = {}
for r in recs:
    by_type.setdefault(r["type"], []).append(r)


def newest(t):
    lst = by_type.get(t) or []
    return lst[-1] if lst else None


def payload(rec):
    if not rec:
        return {}
    p = Path(rec["path"])
    if not p.is_absolute():
        p = ROOT / p
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:                                            # noqa: BLE001
        return {}


voice, script, sub = payload(newest("voice_output")), payload(newest("script_output")), \
    payload(newest("subtitle"))
render_rec = next((r for r in (by_type.get("render_output") or [])
                   if r["task_id"] == FILM_TASK), None) or newest("render_output")
render = payload(render_rec)
timeline = render.get("material_timeline") or []
timeline_total = float((render.get("duration_contract") or {}).get("timeline_duration_s")
                       or (timeline[-1]["end_s"] if timeline else 0.0) or 0.0)
film = Path(render.get("output") or "")
if not film.is_absolute():
    film = ROOT / film
project_out = film.parent

# 旁白时长：**实测**（ffprobe 读既有音轨），与产线同源；失败才回退 voice 产物自报值
narr_audio = ROOT / "projects" / PID / (voice.get("audio") or "")
narr_measured = None
if narr_audio.is_file():
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(narr_audio)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        narr_measured = float((r.stdout or "").strip())
    except ValueError:
        narr_measured = None
narr = narr_measured if narr_measured is not None else voice.get("narration_duration_s")

print("film:", film)
print("timeline_total:", timeline_total, "| narration(实测):", narr_measured,
      "| narration(产物自报):", voice.get("narration_duration_s"))
print("script_segments:", len(script.get("segments") or []),
      "| voice_segment_details:", len(voice.get("segment_details") or []),
      "| srt_chars:", len(sub.get("srt") or ""))

out_before = manifest(project_out) if project_out.is_dir() else {}
film_sha_before = sha(film) if film.is_file() else None
film_mtime_before = film.stat().st_mtime if film.is_file() else None

pre = I.pre_render_gate(script.get("segments") or [], voice, timeline_total,
                        I.gate_policy(CFG), narration_duration_s=narr)
post = I.post_render_gate(film, timeline_total, sub.get("srt") or [], narr, True,
                          FFMPEG, FFPROBE, I.gate_policy(CFG))

out_after = manifest(project_out) if project_out.is_dir() else {}
film_sha_after = sha(film) if film.is_file() else None
film_mtime_after = film.stat().st_mtime if film.is_file() else None

report = {
    "schema": "production-integrity-gate-v1",
    "kind": "m2_gate_verdict_on_real_v9_film",
    "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "read_only": True, "mode": "M2（硬门判定；不重渲染、不写项目目录）",
    "project_id": PID, "film_task": FILM_TASK, "film": str(film),
    "inputs": {"timeline_duration_s": timeline_total,
               "narration_duration_s_measured": narr_measured,
               "narration_duration_s_from_artifact": voice.get("narration_duration_s"),
               "script_segments": len(script.get("segments") or []),
               "voice_segment_details": len(voice.get("segment_details") or []),
               "subtitle_artifact": (newest("subtitle") or {}).get("artifact_id"),
               "policy": I.gate_policy(CFG)},
    "pre_render": {"blocked": pre["blocked"],
                   "states": {k: v.get("state") for k, v in pre["metrics"].items()},
                   "reasons": pre["reasons"], "metrics": pre["metrics"]},
    "post_render": {"blocked": post["blocked"],
                    "states": {k: v.get("state") for k, v in post["metrics"].items()},
                    "reasons": post["reasons"], "metrics": post["metrics"]},
    "verdict": ("BLOCKED" if (pre["blocked"] or post["blocked"]) else "PASS"),
    "read_only_evidence": {
        "output_manifest_unchanged": out_before == out_after,
        "film_sha256_before": film_sha_before, "film_sha256_after": film_sha_after,
        "film_sha256_unchanged": film_sha_before == film_sha_after,
        "film_mtime_unchanged": film_mtime_before == film_mtime_after,
        "new_files_in_output": sorted(k for k in out_after if k not in out_before),
    },
    "note": "v9 未重渲染（授权禁止）；本报告只把**既有成片**喂给 M2 硬门做只读判定。"
            "pre/post 任一阻断 ⇒ 该成片在 M2 之后不允许作为交付物登记。",
}
(LOGS / "phase6a_m2_v9_gate.json").write_text(json.dumps(report, ensure_ascii=False, indent=1),
                                              encoding="utf-8")
print("pre_render  blocked:", pre["blocked"], {k: v.get("state") for k, v in pre["metrics"].items()})
print("post_render blocked:", post["blocked"], {k: v.get("state") for k, v in post["metrics"].items()})
print("verdict:", report["verdict"])
print("只读取证: 成片 sha 不变", report["read_only_evidence"]["film_sha256_unchanged"],
      "| mtime 不变", report["read_only_evidence"]["film_mtime_unchanged"],
      "| output 无新增", not report["read_only_evidence"]["new_files_in_output"])
print("json ->", LOGS / "phase6a_m2_v9_gate.json")
