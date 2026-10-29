# -*- coding: utf-8 -*-
"""Phase 13 诊断：闭式与矩形的逐帧差异定位（取 S01 前后差异帧）。"""
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import motion as M                                             # noqa: E402

plan = M.plan_scene({"scene_id": "S01", "duration_s": 12, "src_path": "x.png"},
                    out_w=1920, out_h=1080, fps=25, enabled=True, motion_type="SLOW_ZOOM_IN")
p = plan["params"]
print("params:", {k: p[k] for k in ("w_start", "w_end", "h_start", "h_end", "n1", "n2", "n3",
                                    "s1", "s2", "s3", "head_static", "motion_frames")})
print("src:", plan["src_w"], plan["src_h"], "| n_frames:", plan["n_frames"])
bad = []
for n in range(plan["n_frames"]):
    r, e = plan["rects"][n], M.evaluate_closed_form(plan, n)
    if r != e:
        bad.append((n, r, e))
print("不一致帧数:", len(bad), "| 前 5:", bad[:5], "| 末 3:", bad[-3:])
n = bad[0][0] if bad else 0
print("样例帧", n, "矩形", plan["rects"][n], "闭式", M.evaluate_closed_form(plan, n))
print("c 闭式:", (p["s1"] * min(max(n - p["head_static"], 0), p["n1"])
                + p["s2"] * min(max(n - p["head_static"] - p["n1"], 0), p["n2"])
                + p["s3"] * min(max(n - p["head_static"] - p["n1"] - p["n2"], 0), p["n3"])))
print("滤镜串:", M.crop_filter(plan)[:160])
