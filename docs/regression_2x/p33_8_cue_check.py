# -*- coding: utf-8 -*-
"""P33-3 诊断：字幕 cue 文本 与 脚本 narration 的**逐字一致性**（含空白规整口径）。"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import captions as CAP                                    # noqa: E402

SCRIPT = R / "output/phase27_script_sandbox/script_p27_v41_40seg.json"
TB = R / "output/phase33_voice/timebase_v41.json"


def h(t):
    return hashlib.sha256((t or "").encode("utf-8")).hexdigest()[:12]


def norm(s):
    """空白规整：折叠所有空白/换行。"""
    return re.sub(r"\s+", "", s or "")


script = json.loads(SCRIPT.read_text(encoding="utf-8"))
tb = json.loads(TB.read_text(encoding="utf-8"))
wins = tb["windows"]
segs = script["segments"]
wlist = [{"start_s": w["start_s"], "end_s": w["end_s"]} for w in wins]

cues = CAP.build_cues([{"narration": s.get("narration") or "", "index": i}
                       for i, s in enumerate(segs)], windows=wlist)
print("cues 总数", len(cues))
by_seg = {}
for c in cues:
    by_seg.setdefault(c["segment_index"], []).append(c)

print()
print("{:<8} {:>6} {:>8} {:>10} {:>10} {}".format(
    "scene", "cues", "chars", "cue_h", "script_h", "一致?"))
same_raw = same_norm = 0
for i, s in enumerate(segs):
    sid = s.get("scene_id")
    raw = s.get("narration") or ""
    joined = "".join(c["text"] for c in by_seg.get(i, []))
    ok_raw = joined == raw
    ok_norm = norm(joined) == norm(raw)
    same_raw += ok_raw
    same_norm += ok_norm
    if i < 10 or not ok_norm:
        print("{:<8} {:>6} {:>8} {:>10} {:>10} raw={} norm={}".format(
            str(sid), len(by_seg.get(i, [])), len(raw),
            h(joined), h(raw), "Y" if ok_raw else "n", "Y" if ok_norm else "N"))
print()
print("raw 完全一致: {}/{}".format(same_raw, len(segs)))
print("空白规整后一致: {}/{}".format(same_norm, len(segs)))
print()
print("段内 cue 是否无缝覆盖窗口（首尾贴边）:")
bad = 0
for i, w in enumerate(wins):
    cs = by_seg.get(i, [])
    if not cs:
        continue
    if abs(cs[0]["start"] - w["start_s"]) > 0.05 or abs(cs[-1]["end"] - w["end_s"]) > 0.6:
        bad += 1
        if bad <= 6:
            print("   {} cue [{},{}] vs 窗口 [{},{}]".format(
                w["scene_id"], cs[0]["start"], cs[-1]["end"], w["start_s"], w["end_s"]))
print("   不贴边段数:", bad, "/", len(wins))
