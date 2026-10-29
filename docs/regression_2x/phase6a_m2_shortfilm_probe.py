# -*- coding: utf-8 -*-
"""6-A/M2 取证（只读）：历史"短旁白"成片（mock/早期用例）在 PI-3 下是否本就是违约片。

目的：判断 M2 前置门拦住的那类夹具成片，究竟是"合规片被误伤"还是"本就有长尾静音的违约片"。
方法：从 DB 找 narration≈4.248 s 的历史项目 → 取其已渲染成片 → 实测 silencedetect/profile。
只读：不写任何项目文件。
用法: python docs/regression_2x/phase6a_m2_shortfilm_probe.py
产出: logs/phase6a_m2_shortfilm_probe.json
"""
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
from video_studio.core import integrity as I  # noqa: E402

LOGS = ROOT / "docs" / "regression_2x" / "logs"
CFG = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8-sig"))
FFMPEG = CFG["tools"]["ffmpeg"]["path"]
FFPROBE = CFG["tools"]["ffmpeg"]["ffprobe"]

con = sqlite3.connect("file:projects/video_studio.db?mode=ro", uri=True)
con.row_factory = sqlite3.Row
rows = con.execute(
    "select a.project_id as pid, a.path as vpath, a.task_id as vtask, r.path as rpath, "
    "r.task_id as rtask, r.created_at as at "
    "from artifacts a join artifacts r on r.project_id = a.project_id and r.type='render_output' "
    "where a.type='voice_output' order by r.created_at desc limit 400").fetchall()

cases = []
seen = set()
for r in rows:
    if r["pid"] in seen:
        continue
    try:
        voice = json.loads(Path(r["vpath"]).read_text(encoding="utf-8"))
        render = json.loads(Path(r["rpath"]).read_text(encoding="utf-8"))
    except Exception:                                            # noqa: BLE001
        continue
    narr = voice.get("narration_duration_s")
    if narr is None or abs(float(narr) - 4.248) > 0.05:
        continue
    tl = float((render.get("duration_contract") or {}).get("timeline_duration_s")
               or 0.0)
    film = render.get("output")
    if not tl or not film:
        continue
    fp = Path(film)
    if not fp.is_absolute():
        fp = ROOT / film
    if not fp.is_file():
        continue
    seen.add(r["pid"])
    pi1 = I.narration_coverage(narr, tl, I.DEFAULT_POLICY)
    pi3 = I.audio_silence_profile(fp, FFMPEG, tl, I.DEFAULT_POLICY)
    cases.append({"project_id": r["pid"], "film": str(fp.relative_to(ROOT)),
                  "narration_duration_s": narr, "timeline_duration_s": tl,
                  "PI-1": pi1["state"], "coverage_ratio": pi1.get("coverage_ratio"),
                  "PI-3": pi3["state"], "tail_silence_s": pi3.get("tail_silence_s"),
                  "longest_silence_s": pi3.get("longest_silence_s"),
                  "silence_ratio": pi3.get("silence_ratio")})
    if len(cases) >= 5:
        break

out = {"schema": "m2-shortfilm-probe-v1", "read_only": True,
       "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
       "note": "历史 4.248 s 旁白（mock/早期用例）成片：检查它们是否本就属于 'PI-3 长尾静音' 违约类",
       "cases": cases}
(LOGS / "phase6a_m2_shortfilm_probe.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                                      encoding="utf-8")
for c in cases:
    print("pid={} narr={} tl={} PI-1={}({}) PI-3={} tail={} longest={} ratio={}".format(
        c["project_id"], c["narration_duration_s"], c["timeline_duration_s"], c["PI-1"],
        c["coverage_ratio"], c["PI-3"], c["tail_silence_s"], c["longest_silence_s"],
        c["silence_ratio"]))
print("json ->", LOGS / "phase6a_m2_shortfilm_probe.json")
