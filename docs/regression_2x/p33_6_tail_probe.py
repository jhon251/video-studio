# -*- coding: utf-8 -*-
"""P33-1：核验头/尾帧实际行为（为 Q6 断言定性）。"""
from __future__ import annotations

import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import motion as M                                        # noqa: E402

for sid, dur in (("S03", 22.5), ("S07", 32.9), ("S09", 29.2), ("S02", 21.1)):
    p = M.plan_scene({"scene_id": sid, "duration_s": dur}, out_w=1920, out_h=1080,
                     fps=25, direction="RIGHT",
                     motion_type="SLOW_PAN" if sid == "S02" else "SLOW_ZOOM_IN")
    r = p["rects"]
    h = p["params"]["head_static"]
    print("{} type={} frames={} motion={} head_static={}".format(
        sid, p["motion_type"], p["n_frames"], p["params"]["motion_frames"], h))
    print("   first 3 rects:", r[:3])
    print("   last  4 rects:", r[-4:])
    print("   head 同位(0..h-1)?", len(set(r[:h])) == 1)
    print("   末帧 == 闭式末端?", tuple(r[-1]) == tuple(M.evaluate_closed_form(p, p["n_frames"] - 1)))
    print("   末两帧相同?", r[-1] == r[-2])
    print("   严格单调(宽单调不减且至少变化一次)?",
          all(r[i + 1][2] <= r[i][2] for i in range(len(r) - 1)) and r[0][2] != r[-1][2])
    print()
