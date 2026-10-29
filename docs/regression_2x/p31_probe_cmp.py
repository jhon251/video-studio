# -*- coding: utf-8 -*-
"""对照 P30 实际 MATERIAL_TIMELINE 决策 与 retrieval artifact 的 _p30_binding。只读。"""
from __future__ import annotations

import collections
import json
import pathlib
import sqlite3
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import narration as NAR                                # noqa: E402

SCRIPT = R / "output" / "phase27_script_sandbox" / "script_p27_v41_40seg.json"
VOICE = R / "output" / "phase20_voice_sandbox" / "voice_output_40seg_v21.json"


def main() -> int:
    con = sqlite3.connect("file:" + (R / "projects" / "video_studio.db").as_posix()
                          + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    script = json.loads(SCRIPT.read_text(encoding="utf-8"))
    voice = json.loads(VOICE.read_text(encoding="utf-8"))
    pol = NAR.narration_plan(script, voice)
    wins = pol["segments"]
    segs = script["segments"]
    idmap = {}
    for i, s in enumerate(segs):
        sid = str(s.get("scene_id") or "S%02d" % (i + 1))
        idmap[sid] = (wins[i]["actual_s"] + wins[i]["pause_s"], wins[i]["start_s"],
                      wins[i]["end_s"])
    for pid in ("p_8b48148d4bf3", "p_ddb17cfbacf8"):
        r = con.execute("select payload from events where project_id=? and "
                        "type='MATERIAL_TIMELINE' order by ts desc limit 1", (pid,)).fetchone()
        if not r:
            continue
        ds = json.loads(r["payload"])["decisions"]
        print("=== {} : {} decisions ===".format(pid, len(ds)))
        tot, secs, scen = 0.0, collections.Counter(), collections.Counter()
        miss = []
        for d in ds:
            sid = d["scene_id"]
            if sid not in idmap:
                miss.append(sid)
                continue
            dur = idmap[sid][0]
            a = (d.get("selected_asset") or {}).get("sha256") or "SOLID"
            secs[a] += dur
            scen[a] += 1
            tot += dur
        print("  窗口命中 {} / {} | 未命中 {}".format(len(ds) - len(miss), len(ds), miss[:6]))
        print("  total={:.3f} uniq={}".format(
            tot, len([k for k in secs if k != "SOLID"])))
        for k in sorted(secs, key=lambda z: -secs[z])[:6]:
            print("    {:<14} scenes={:<3} secs={:<8.2f} share={:.4f}".format(
                str(k)[:12], scen[k], secs[k], secs[k] / tot if tot else 0))
        print()

    # P30 fixture reselect vs binding
    fx = json.loads((R / "output/phase30_p30_3_sandbox/fixture.json").read_text(encoding="utf-8"))
    retr = json.loads((R / "projects/p_8b48148d4bf3/artifacts/a_331e853a4bb9.json")
                      .read_text(encoding="utf-8"))
    b = retr.get("_p30_binding") or {}
    print("fixture reselect={} | binding={}".format(len(fx.get("reselect") or []), len(b)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
