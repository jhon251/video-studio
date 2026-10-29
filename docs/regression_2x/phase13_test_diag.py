# -*- coding: utf-8 -*-
"""Phase 13 诊断：测试三处失败的真因。"""
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import motion as M                                             # noqa: E402

SCENES = [{"scene_id": "S{:02d}".format(i), "duration_s": d, "src_path": "x{}.png".format(i),
           "hook": i in (2, 7)} for i, d in enumerate(
    [12, 73, 20, 6, 35, 18, 9, 44, 27, 8, 15, 11], start=1)]
print("== 1b：输入顺序 ==")
p1 = M.build_plan(SCENES, out_w=1920, out_h=1080)
p3 = M.build_plan(list(reversed(SCENES)), out_w=1920, out_h=1080)
print("  输出顺序 p1:", [s["scene_id"] for s in p1["scenes"]])
print("  输出顺序 p3:", [s["scene_id"] for s in p3["scenes"]])
order_same = [s["scene_id"] for s in p1["scenes"]] == sorted(s["scene_id"] for s in SCENES)
print("  p1 是否按 scene_id 排序:", order_same)

print("== 3b：hook 选取 ==")
sel = M.select_scenes(SCENES)
print("  eligible/hook:", [(s["scene_id"], s["duration_s"], s["hook"]) for s in sel
                           if s["motion_enabled"]])
print("  S07 输入:", [s for s in SCENES if s["scene_id"] == "S07"])
cap = int(len(SCENES) * M.MAX_ENABLED_RATIO)
print("  cap:", cap, "| 启用数:", sum(1 for s in sel if s["motion_enabled"]))
print("  p1 中 S07:", next((s for s in p1["scenes"] if s["scene_id"] == "S07"), None) and
      {k: next(s for s in p1["scenes"] if s["scene_id"] == "S07")[k]
       for k in ("enabled", "motion_type", "reason")})

print("== 5d：concat 位置 ==")
src = (R / "src/video_studio/agents/editing/agent.py").read_text(encoding="utf-8")
pat = 'concat=n={n}:v=1:a=0[vc]'
idxs = []
i = src.find(pat)
while i != -1:
    idxs.append(i)
    i = src.find(pat, i + 1)
midx = src.find("_motion.crop_filter(_p13)")
line = lambda k: src[:k].count("\n") + 1
print("  concat 出现行:", [line(k) for k in idxs], "| 运动注入行:", line(midx))
print("  第一条 concat 上下文:", repr(src[idxs[0] - 60:idxs[0] + 30]))
