# -*- coding: utf-8 -*-
"""P31-2 前置侦查：用与生产**同一公式**重建 40 段窗口，复算 DQ-2 与 cap=2 可行性。

窗口公式（`_build_material_timeline`）：
    dur_i = max(actual_s_i, 3.0) + (pause if i < n-1 else trailing_pad)
    最后一景 end_s = max(end_s, cursor + 2.0)
只读。
"""
from __future__ import annotations

import collections
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
OUT = R / "output" / "p31_probe"
OUT.mkdir(parents=True, exist_ok=True)

SCRIPT = R / "output" / "phase27_script_sandbox" / "script_p27_v41_40seg.json"
VOICE = R / "output" / "phase20_voice_sandbox" / "voice_output_40seg_v21.json"
PAUSE = 0.75
TRAIL = 2.0
CAP = 2


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    script = json.loads(SCRIPT.read_text(encoding="utf-8"))
    voice = json.loads(VOICE.read_text(encoding="utf-8"))
    segs = script["segments"]
    vs = voice["segments"]
    print("script 段 {} | voice 段 {}".format(len(segs), len(vs)))
    acts = []
    for i, v in enumerate(vs):
        acts.append(float(v.get("actual_s") or v.get("duration_s") or 0.0))
    n = len(segs)
    wins, cursor = [], 0.0
    for i, seg in enumerate(segs):
        dur = max(acts[i], 3.0)
        dur = dur + (PAUSE if i < n - 1 else TRAIL)
        wins.append({"i": i, "scene_id": str(seg.get("scene_id") or "S%02d" % (i + 1)),
                     "parent": str(seg.get("parent_scene_id") or ""),
                     "start_s": round(cursor, 3), "end_s": round(cursor + dur, 3),
                     "dur": round(dur, 3)})
        cursor += dur
    if wins:
        wins[-1]["end_s"] = round(max(wins[-1]["end_s"], cursor + 2.0), 3)
    total = wins[-1]["end_s"] if wins else 0.0
    print("重建总时长 {:.3f}s（声明时基 977.884）".format(total))
    print("前 3 景: " + str([(w["scene_id"], w["start_s"], w["end_s"]) for w in wins[:3]]))
    print("末 3 景: " + str([(w["scene_id"], w["start_s"], w["end_s"]) for w in wins[-3:]]))

    # 当前绑定（P30 交付候选）
    bind = json.loads((L / "phase31_binding_p30.json").read_text(encoding="utf-8")) \
        if (L / "phase31_binding_p30.json").exists() else None
    if bind is None:
        # 从 P30 fixture 的 _p30_binding 重建
        fx = json.loads((R / "output/phase30_p30_3_sandbox/fixture.json")
                        .read_text(encoding="utf-8"))
        print("P30 fixture reselect: {}".format(fx.get("reselect")))
        print("(需从 render 项目 retrieval artifact 取 _p30_binding)")
    print()
    print("窗口表写出 -> " + str(OUT / "windows.json"))
    (OUT / "windows.json").write_text(json.dumps(
        {"schema": "p31-windows-v1", "pause": PAUSE, "trail": TRAIL,
         "total_s": round(total, 3), "windows": wins}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
