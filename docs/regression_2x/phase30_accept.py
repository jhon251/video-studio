# -*- coding: utf-8 -*-
"""P30-1/30-3 验收：**旧黑板区（955–975s）灰度探针复测** + 全片无 ≥3s 连续近黑 + 三指标。"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import numpy as np
from PIL import Image

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import motion_metrics as MM                              # noqa: E402

FF = str(R / "bin" / "ffmpeg.exe")
FFPROBE = str(R / "bin" / "ffprobe.exe")
fx = json.loads((R / "output/phase30_p30_3_sandbox/fixture.json").read_text(encoding="utf-8"))
proj = R / "projects" / fx["sandbox_project_id"]
film = next((proj / "output").glob("*.mp4"))
r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                    "-of", "default=nw=1:nk=1", str(film)], capture_output=True, text=True)
dur = float(r.stdout.strip().splitlines()[0])
print("成片 {} ({:,}B) | 时长 {:.3f}s".format(film.name, film.stat().st_size, dur))

prev = R / "projects/p_ddb17cfbacf8/output/t_5f76c2d95573_draft.mp4"
out = R / "output/p30_probe"
out.mkdir(parents=True, exist_ok=True)


def scan(f: pathlib.Path, times, tag):
    rows = []
    for t in times:
        o = out / "{}_{}.png".format(tag, str(t).replace(".", "_"))
        rr = subprocess.run([FF, "-v", "error", "-y", "-ss", "{}".format(t), "-i", str(f),
                             "-frames:v", "1", str(o)], capture_output=True)
        if rr.returncode != 0 or not o.is_file():
            continue
        with Image.open(o) as im:
            a = np.asarray(im.convert("L"), dtype=float)
        rows.append({"t_s": t, "mean": round(float(a.mean()), 2),
                     "std": round(float(a.std()), 2)})
    return rows


TIMES = [940, 946, 952, 955, 958, 961, 964, 967, 970, 973, 975]
print("\n=== 旧黑板区（955–975s）灰度复测 ===")
print("{:>8s} {:>12s} {:>12s}".format("t(s)", "旧版 mean", "**P30 mean**"))
cur = scan(film, TIMES, "p30")
old = {x["t_s"]: x for x in scan(prev, TIMES, "p27")} if prev.is_file() else {}
for c in cur:
    o = old.get(c["t_s"], {})
    print("{:>8.0f} {:>12} {:>12.2f}".format(
        c["t_s"], ("{:.2f}".format(o["mean"]) if o else "N/A"), c["mean"]))

# 全片连续近黑扫描（同源采样：1fps，416x234 灰度，mean<60 视为近黑）
print("\n=== 全片近黑扫描（1fps）===")
wd = out / "frames"
wd.mkdir(exist_ok=True)
for f_ in wd.glob("*.png"):
    f_.unlink()
subprocess.run([FF, "-v", "error", "-y", "-i", str(film), "-vf", "fps=1,scale=416:234",
                str(wd / "f%05d.png")], capture_output=True)
frames = sorted(wd.glob("f*.png"))
means = []
for f_ in frames:
    with Image.open(f_) as im:
        means.append(float(np.asarray(im.convert("L"), dtype=float).mean()))
dark = [i for i, m in enumerate(means) if m < 60]
longest = cur_run = 0
for m in means:
    cur_run = cur_run + 1 if m < 60 else 0
    longest = max(longest, cur_run)
print("抽帧 {} 张 | 近黑秒数 {} ({:.1%}) | **最长连续近黑 {}s**".format(
    len(means), len(dark), len(dark) / max(len(means), 1), longest))
print("阈值: 全片无 ≥3s 连续近黑 ⇒ {}".format("通过 ✔" if longest < 3 else "**失败 ✘**"))

mm = MM.evaluate(str(film), FF)
print("\n=== 三指标（320×180 MAD，阈值不变）===")
print("冻结占比 {:.1%} | 最长静止 {}s | 开场变化 {} | 全过 {}".format(
    mm["freeze_ratio"], mm["longest_static_s"], mm["opening_changes"], mm["all_pass"]))

rep = {
    "schema": "phase30-p30-1-acceptance-v1",
    "film": str(film.relative_to(R)).replace("\\", "/"),
    "film_bytes": film.stat().st_size, "duration_s": dur,
    "dark_region_rescan": {"times": TIMES, "p30": cur,
                           "p27_reference": [old.get(t, {}) for t in TIMES]},
    "no_dark_assertion": {"sampled_seconds": len(means), "dark_seconds": len(dark),
                          "longest_consecutive_dark_s": longest,
                          "threshold_s": 3, "passed": bool(longest < 3)},
    "motion_metrics": mm,
    "zero_llm": True, "zero_vlm": True, "zero_network": True,
}
p = L / "phase30_p30_1_acceptance.json"
p.write_text(json.dumps(rep, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
print("\n->", p.relative_to(R).as_posix())
