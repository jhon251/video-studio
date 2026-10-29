# -*- coding: utf-8 -*-
"""P33 诊断：渲染产物的窗口总和 / fps / 分辨率 / 时长契约明细。"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import subprocess
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
PID = sys.argv[1] if len(sys.argv) > 1 else "p_23cd348beed8"
FFPROBE = R / "bin" / "ffprobe.exe"
con = sqlite3.connect("file:" + (R / "projects" / "video_studio.db").as_posix()
                      + "?mode=ro", uri=True)
con.row_factory = sqlite3.Row
for r in con.execute("select artifact_id,path,type from artifacts where project_id=?",
                     (PID,)):
    p = pathlib.Path(r["path"])
    if r["type"] not in ("render_output",) or not p.is_file():
        continue
    d = json.loads(p.read_text(encoding="utf-8"))
    print("artifact:", r["artifact_id"], r["type"])
    for k in ("duration_contract", "render_params", "resolution", "fps",
              "video_duration_s", "timeline_duration_s"):
        if k in d:
            print("  {} = {}".format(k, json.dumps(d[k], ensure_ascii=False)[:300]))
    mt = d.get("material_timeline") or []
    print("  material_timeline 条数 =", len(mt))
    if mt:
        tot = sum(float(s["end_s"]) - float(s["start_s"]) for s in mt)
        print("  Σ窗口 = {:.3f}".format(tot))
        print("  首窗口 =", mt[0]["start_s"], mt[0]["end_s"])
        print("  末窗口 =", mt[-1]["start_s"], mt[-1]["end_s"])
        print("  首 3 段时长 =", [round(float(s["end_s"]) - float(s["start_s"]), 3)
                                  for s in mt[:3]])
    np_ = d.get("narration_plan") or {}
    if np_:
        print("  narration_plan.audio_time_base_s =", np_.get("audio_time_base_s"))
        print("  narration_plan.pause_budget_s   =", np_.get("pause_budget_s"))
    print()
film = sorted((R / "projects" / PID / "output").glob("*with_outro_v2.mp4"))
if film:
    f = film[0]
    r = subprocess.run([str(FFPROBE), "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "stream=width,height,avg_frame_rate,duration",
                        "-of", "json", str(f)], capture_output=True, text=True)
    print("成片视频流:", r.stdout.strip())
    r2 = subprocess.run([str(FFPROBE), "-v", "error", "-select_streams", "a:0",
                         "-show_entries", "stream=codec_name,sample_rate,channels,duration",
                         "-of", "json", str(f)], capture_output=True, text=True)
    print("成片音频流:", r2.stdout.strip())
