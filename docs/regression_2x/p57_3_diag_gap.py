# -*- coding: utf-8 -*-
"""P57-3 诊断：cue 间隙与词→句归属解剖（临时工具，不作为门）。"""
import json
import re
import sys
from pathlib import Path

R = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
PDIR = R / "projects" / "p_3e9292101f10"
ASS = PDIR / "artifacts" / "_captions_t_17e0e4f43b48.ass"


def sec(ts):
    h, mm, rest = ts.split(":")
    return int(h) * 3600 + int(mm) * 60 + float(rest)


rows = []
for m in re.finditer(r"Dialogue: 0,([0-9:.]+),([0-9:.]+),Cap,,0,0,0,,(.*)",
                     ASS.read_text(encoding="utf-8")):
    rows.append((sec(m.group(1)), sec(m.group(2)), m.group(3).replace("\\N", "")))

lo, hi = float(sys.argv[1]), float(sys.argv[2])
for i, (s, e, t) in enumerate(rows):
    if lo <= s <= hi:
        print("cue{:3d}: {:8.3f}-{:8.3f} {:6.2f}s {}".format(i, s, e, e - s, t[:46]))
print()
wm = {p["para"]: p for p in json.loads(
    (PDIR / "media/voice/words_manifest.json").read_text(encoding="utf-8"))["paras"]}
sc = json.loads((PDIR / "artifacts/a_aec6a870612e.json").read_text(encoding="utf-8"))
# 段音频起点 = 该段**首个**景的窗起点（与构建器/验证脚本同基）
para_start = {}
for s in sc["segments"]:
    p = str(s["scene_id"]).split("_")[0]
    aw = s.get("audio_window_s") or [0, 0]
    if p not in para_start or aw[0] < para_start[p][0]:
        para_start[p] = [aw[0], s["scene_id"]]
seen = set()
for s in sc["segments"]:
    p = str(s["scene_id"]).split("_")[0]
    if p in seen:
        continue
    ps, first_scene = para_start[p]
    # 粗筛：段窗口与本区间有交叠才打印
    aws = [x.get("audio_window_s") or [0, 0] for x in sc["segments"]
           if str(x["scene_id"]).split("_")[0] == p]
    if not (min(w[0] for w in aws) <= hi and max(w[1] for w in aws) >= lo):
        continue
    seen.add(p)
    print("para {} 音频起点 {:.3f}（{}）".format(p, ps, first_scene))
    for w in (wm.get(p) or {}).get("words") or []:
        a = ps + float(w["start_s"])
        if lo - 1.0 <= a <= hi + 1.0:
            print("   word@{:8.2f} +{:.2f} {}".format(a, float(w["dur_s"]), w["text"]))
