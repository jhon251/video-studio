# -*- coding: utf-8 -*-
"""精确复算 DQ-2：用 core.direction.asset_reuse 走**生产口径**，对比 P27 验证日志的 0.3638。只读。

同时给出「按 v2.1 逐景窗口」与「按 timeline 声明窗口」两种时基下的 DQ-2，
以定位 0.3638 的分母来源。
"""
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
from video_studio.core import direction as DIR                                # noqa: E402

SCRIPT = R / "output" / "phase27_script_sandbox" / "script_p27_v41_40seg.json"
VOICE = R / "output" / "phase20_voice_sandbox" / "voice_output_40seg_v21.json"


def dq2_of(tl):
    return DIR.asset_reuse(tl)


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
        idmap[sid] = {"start_s": wins[i]["start_s"],
                      "end_s": wins[i]["end_s"] + wins[i]["pause_s"],
                      "actual": wins[i]["actual_s"], "pause": wins[i]["pause_s"]}
    # 修正：场景窗口 = 段内时长 + 该段之后的 pause
    for i, s in enumerate(segs):
        sid = str(s.get("scene_id") or "S%02d" % (i + 1))
        st = wins[i]["start_s"]
        en = wins[i]["end_s"] + wins[i]["pause_s"]
        idmap[sid] = {"start_s": st, "end_s": en}
    if segs:
        last = str(segs[-1].get("scene_id") or "S%02d" % len(segs))
        idmap[last]["end_s"] = pol["audio_time_base_s"]

    for pid in ("p_8b48148d4bf3",):
        r = con.execute("select payload from events where project_id=? and "
                        "type='MATERIAL_TIMELINE' order by ts desc limit 1", (pid,)).fetchone()
        ds = json.loads(r["payload"])["decisions"]
        tl = []
        for d in ds:
            sid = d["scene_id"]
            w = idmap.get(sid) or {}
            tl.append({"scene_id": sid, "start_s": w.get("start_s", 0.0),
                       "end_s": w.get("end_s", 0.0),
                       "selected_asset": d.get("selected_asset")})
        out = dq2_of(tl)
        print("=== core.direction.asset_reuse (v2.1 窗口) ===")
        print("state={} unique={} max_share={} total_s={}".format(
            out["state"], out["unique_assets"], out["max_asset_share"], out["total_s"]))
        top = sorted(out["per_asset"].items(), key=lambda kv: -kv[1]["share"])[:6]
        for k, v in top:
            print("   {:<26} scenes={:<3} secs={:<8.2f} share={:.4f}".format(
                str(k)[:26], v["scenes"], v["seconds"], v["share"]))
        print()
        # 声明窗口（脚本 duration_s）
        tl2 = []
        cur = 0.0
        for i, s in enumerate(segs):
            d = float(s.get("duration_s") or 0)
            sid = str(s.get("scene_id") or "S%02d" % (i + 1))
            sa = next((x for x in ds if x["scene_id"] == sid), {})
            tl2.append({"scene_id": sid, "start_s": cur, "end_s": cur + d,
                        "selected_asset": sa.get("selected_asset")})
            cur += d
        out2 = dq2_of(tl2)
        print("=== 声明窗口口径 (declared) ===")
        print("state={} unique={} max_share={} total_s={}".format(
            out2["state"], out2["unique_assets"], out2["max_asset_share"], out2["total_s"]))
    print()
    print("P27 验证日志 dq2: max_share=0.3638 unique=11 max_reuse=15")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
