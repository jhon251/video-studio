# -*- coding: utf-8 -*-
"""P27-3 诊断：逐一验证 40 景的 crop 滤镜串是否能被 ffmpeg 接受。"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import motion as M                                       # noqa: E402

FF = str(R / "bin" / "ffmpeg.exe")
script = json.loads((R / "output" / "phase27_script_sandbox" / "script_p27_v41_40seg.json")
                    .read_text(encoding="utf-8"))
scenes = [{"scene_id": s["scene_id"], "duration_s": float(s["duration_s"]),
           "hook": i == 0, "src_w": round(1920 * M.MAX_ZOOM_END),
           "src_h": round(1080 * M.MAX_ZOOM_END)}
          for i, s in enumerate(script["segments"])]
plan = M.build_plan(scenes, out_w=1920, out_h=1080, fps=25)
print("景 {} | 启用 {}".format(plan["counts"]["scenes"], plan["counts"]["enabled"]))

bad = []
for p in plan["scenes"]:
    if not p["enabled"]:
        continue
    cf = M.crop_filter(p)
    vf = ("scale={}:{}:force_original_aspect_ratio=increase,crop={}:{},{}"
          ",scale=1920:1080,setsar=1,fps=25").format(
              p["src_w"], p["src_h"], p["src_w"], p["src_h"], cf)
    r = subprocess.run([FF, "-v", "error", "-f", "lavfi", "-i",
                        "color=c=gray:s=1920x1080:d=0.2:r=25", "-vf", vf,
                        "-frames:v", "2", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        bad.append({"scene_id": p["scene_id"], "type": p["motion_type"],
                    "src": [p["src_w"], p["src_h"]], "out": [p["out_w"], p["out_h"]],
                    "params": {k: p["params"].get(k) for k in
                               ("head_static", "motion_frames", "n1", "n2", "n3",
                                "s1", "s2", "s3", "w_start", "w_end", "delta_full",
                                "pan_px", "sign", "v2_progress")},
                    "crop": cf, "stderr": (r.stderr or "").strip()[:400]})
        print("FAIL {} {} :: {}".format(p["scene_id"], p["motion_type"],
                                        (r.stderr or "").strip()[:160]))
print()
print("失败景数:", len(bad))
if bad:
    b = bad[0]
    print("首个失败景:", b["scene_id"], b["type"])
    print("  src", b["src"], "out", b["out"])
    print("  params", json.dumps(b["params"], ensure_ascii=False))
    print("  crop:", b["crop"][:300])
    print("  stderr:", b["stderr"])
out = {"schema": "phase27-crop-filter-diagnosis-v1", "scenes": plan["counts"]["scenes"],
       "enabled": plan["counts"]["enabled"], "failed": len(bad), "failures": bad[:10],
       "first_crop": (M.crop_filter(next(p for p in plan["scenes"] if p["enabled"])))}
p = R / "docs" / "regression_2x" / "logs" / "phase27_crop_diag.json"
p.write_text(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
print("->", p.relative_to(R).as_posix())
