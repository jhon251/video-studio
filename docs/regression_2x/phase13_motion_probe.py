# -*- coding: utf-8 -*-
"""Phase 13 P13-1 只读自检：闭式 ⇔ 权威逐帧矩形等价、策略上限、确定性、滤镜串样例。"""
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import motion as M                                             # noqa: E402

scenes = [{"scene_id": "S{:02d}".format(i), "duration_s": d, "src_path": "x{}.png".format(i),
           "hook": i in (1, 5, 9)} for i, d in enumerate(
    [12, 73, 20, 6, 35, 18, 9, 44, 27, 60, 15, 11, 13, 30, 22, 8, 19, 25, 40, 16, 33], start=1)]
plan = M.build_plan(scenes, out_w=1920, out_h=1080, fps=25)
print("策略:", json.dumps({k: v["value"] for k, v in plan["policy"].items()}, ensure_ascii=False))
print("计数:", json.dumps(plan["counts"], ensure_ascii=False), "| 校验:", M.validate_plan(plan))
worst = 0
for p in plan["scenes"]:
    diffs = [i for i in range(p["n_frames"]) if p["rects"][i] != M.evaluate_closed_form(p, i)]
    worst = max(worst, len(diffs))
    if p["enabled"]:
        z = p["out_w"] / p["params"]["w_end"] if p["motion_type"] == "SLOW_ZOOM_IN" else 1.0
        print("  {} {} dur={:.0f}s n={} zoom_end={:.4f} pan={} rects[0]={} rects[-1]={}".format(
            p["scene_id"], p["motion_type"], p["duration_s"], p["n_frames"], z,
            p["params"]["pan_px"], p["rects"][0], p["rects"][-1]))
print("闭式与矩形不一致的帧数（全部场景合计最大值）:", worst)
p0 = json.dumps(plan, ensure_ascii=False, sort_keys=True)
p1 = json.dumps(M.build_plan(scenes, out_w=1920, out_h=1080, fps=25), ensure_ascii=False,
                sort_keys=True)
print("确定性（两次构建逐字节一致）:", p0 == p1)
en = [p for p in plan["scenes"] if p["enabled"]]
print("启用比例:", "{:.2f}".format(len(en) / len(plan["scenes"])), "（上限 0.60）")
print("滤镜串样例:", M.crop_filter(en[0])[:200] if en else "n/a")
print("静止样例:", M.crop_filter(plan["scenes"][3]))
