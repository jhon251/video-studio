# -*- coding: utf-8 -*-
"""P33 诊断：渲染产物里的 voice_output 是否携带 pause_attribution，及其对时基的影响。"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import narration as NAR                                    # noqa: E402

PID = "p_23cd348beed8"
con = sqlite3.connect("file:" + (R / "projects" / "video_studio.db").as_posix()
                      + "?mode=ro", uri=True)
con.row_factory = sqlite3.Row
art = None
for r in con.execute("select artifact_id,path from artifacts where project_id=? "
                     "and type='voice_output'", (PID,)):
    art = r
print("voice artifact:", art["artifact_id"] if art else None)
vo = json.loads(pathlib.Path(art["path"]).read_text(encoding="utf-8"))
print("keys:", sorted(vo.keys()))
print("has pause_attribution:", "pause_attribution" in vo)
if "pause_attribution" in vo:
    pa = vo["pause_attribution"]
    print("  policy:", pa.get("policy"), "| boundaries:", len(pa.get("boundaries") or []),
          "| default:", pa.get("default_pause_s"))
    print("  前 3 边界:", (pa.get("boundaries") or [])[:3])
print("segments[0] keys:", sorted((vo.get("segments") or [{}])[0].keys()))
print("segments[0]:", {k: (vo["segments"][0].get(k)) for k in
                       ("scene_id", "duration_s", "status", "audio")})
print()
# 直接跑 narration_plan
SCRIPTS = [R / "output/phase33_script_sandbox/script_p33_v41_40seg.json",
           R / "output/phase27_script_sandbox/script_p27_v41_40seg.json"]
for sp in SCRIPTS:
    sc = json.loads(sp.read_text(encoding="utf-8"))
    plan = NAR.narration_plan(sc, vo)
    print("{} -> base={} Σactual={} pause={}".format(
        sp.name, plan["audio_time_base_s"], plan["actual_total_narration_s"],
        plan["pause_budget_s"]))
