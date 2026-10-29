# -*- coding: utf-8 -*-
"""P33-1 诊断：对 v4.1 的真实景（新窗口）构建运动计划，逐帧检验
  ① 单调性（宽度/位置是否单调不减）；
  ② 振荡（帧间增量的符号翻转次数，阈值：每景 >2 次即不通过）；
  ③ 居中锚定（x0 是否恒为 (src_w-w)/2 —— 有无净漂移）；
  ④ 净漂移（末帧位置 − 首帧位置 vs 宣称幅度）。
纯函数，不渲染。
"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import motion as M                                        # noqa: E402

A = json.loads((R / "output/phase27_script_sandbox/script_p27_v41_40seg.json")
               .read_text(encoding="utf-8"))


def flips(seq):
    """相邻增量的符号翻转次数（忽略零增量）。"""
    d = [seq[i + 1] - seq[i] for i in range(len(seq) - 1)]
    nz = [x for x in d if x != 0]
    return sum(1 for i in range(len(nz) - 1) if (nz[i] > 0) != (nz[i + 1] > 0))


def main() -> int:
    scenes = []
    for i, s in enumerate(A["segments"]):
        # 新时基未定 ⇒ 先用声明时长占位，只为检验**算法性质**
        scenes.append({"scene_id": str(s.get("scene_id")),
                       "duration_s": float(s.get("duration_s") or 20.0),
                       "hook": i == 0})
    print("景数", len(scenes), "| 总时长 {:.1f}s".format(
        sum(s["duration_s"] for s in scenes)))
    plan = M.build_plan(scenes, out_w=1920, out_h=1080, fps=25)
    print("policy:", json.dumps(plan.get("counts"), ensure_ascii=False))
    print()
    print("{:<8} {:>7} {:>9} {:>8} {:>7} {:>7} {}".format(
        "scene", "dur", "frames", "type", "flips", "drift", "x0恒居中?"))
    bad = []
    for p in plan["scenes"]:
        rects = p["rects"]
        w = [r[2] for r in rects]
        x0 = [r[0] for r in rects]
        y0 = [r[1] for r in rects]
        fw = flips(w)
        # 居中锚定只适用于 **SLOW_ZOOM_IN**（窗口在源上居中收缩，x0/y0 恒为 (src−w)/2）；
        # SLOW_PAN 是**有意的单方向位移**（幅度 ≤ 画面宽 3%），不适用居中判据。
        if p["motion_type"] == "SLOW_ZOOM_IN":
            cen_ok = all(x0[k] == (p["src_w"] - w[k]) // 2 for k in range(len(w)))
            cy_ok = all(y0[k] == (p["src_h"] - rects[k][3]) // 2 for k in range(len(w)))
        else:
            cen_ok = cy_ok = True
        drift = (x0[-1] - x0[0], y0[-1] - y0[0])
        claim = p["params"].get("pan_px") if p["motion_type"] == "SLOW_PAN" \
            else p["params"].get("delta_full")
        # 净漂移 ≤ 宣称幅度（逐轴）
        drift_ok = all(abs(d) <= (claim or 0) + 1e-9 for d in drift)
        ok = (fw <= 2) and cen_ok and cy_ok and drift_ok
        if not ok:
            bad.append(p["scene_id"])
        print("{:<8} {:>7.1f} {:>9} {:>8} {:>7} {:>7} {} {}".format(
            p["scene_id"], p["duration_s"], p["n_frames"], p["motion_type"][:8],
            fw, "({},{})".format(*drift), "Y" if (cen_ok and cy_ok) else "N",
            "" if ok else "  <== 不通过  claim={}".format(claim)))
    print()
    print("不通过景数: {} {}".format(len(bad), bad[:10]))
    print()
    # 平移方向的系统性（zoom 型不计）
    dirs = {}
    for p in plan["scenes"]:
        if p["motion_type"] == "SLOW_PAN":
            dirs[p["scene_id"]] = p["params"].get("sign")
    print("SLOW_PAN 景与方向:", dirs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
