# -*- coding: utf-8 -*-
"""P29-1 #80 诊断：末段深色画面的定位（成片时长 vs 内容结束点 vs 末段窗口）。

已知：t=860..950s 画面 mean≈136（有内容）；t=965/975s mean≈18.6（近黑）。
本脚本：① 测成片实际时长；② 二分定位"内容结束点"；③ 与 40 段窗口表对齐，
判断是**窗口越界**（映射问题）还是**时基缺内容**（渲染问题）。
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import numpy as np
from PIL import Image

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")
FF = str(R / "bin" / "ffmpeg.exe")
FFPROBE = str(R / "bin" / "ffprobe.exe")
film = R / "projects/p_ddb17cfbacf8/output/t_5f76c2d95573_draft.mp4"
sc = json.loads((R / "output/phase27_script_sandbox/script_p27_v41_40seg.json")
                .read_text(encoding="utf-8"))
voice = json.loads((R / "output/phase20_voice_sandbox/voice_output_40seg_v21.json")
                   .read_text(encoding="utf-8"))
r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                    "-of", "default=nw=1:nk=1", str(film)], capture_output=True, text=True)
dur = float(r.stdout.strip().splitlines()[0])
print("成片时长: {:.3f}s".format(dur))
print("脚本总时长: {:.3f}s | voice 时基: {:.3f}s".format(
    sc["total_duration_s"], voice.get("audio_time_base_s")))

# 逐段窗口（按脚本声明时长累计）
segs = sc["segments"]
wins, cur = [], 0.0
for s in segs:
    d = float(s["duration_s"])
    wins.append({"scene_id": s["scene_id"], "start_s": round(cur, 3),
                 "end_s": round(cur + d, 3), "dur": round(d, 3),
                 "chars": len(str(s.get("narration") or ""))})
    cur += d
print("Σ窗口 = {:.3f}s（与成片时长差 {:+.3f}s）".format(cur, dur - cur))


def mean_at(t: float) -> float | None:
    o = R / "output/p29_probe" / "probe.png"
    o.parent.mkdir(parents=True, exist_ok=True)
    rr = subprocess.run([FF, "-v", "error", "-y", "-ss", "{:.3f}".format(t), "-i", str(film),
                         "-frames:v", "1", str(o)], capture_output=True)
    if rr.returncode != 0 or not o.is_file():
        return None
    with Image.open(o) as im:
        return float(np.asarray(im.convert("L"), dtype=float).mean())


# 定位内容结束点：从 950s 起每 2s 采样
print("\n尾段亮度扫描（mean<60 视为近黑）:")
dark_from = None
for t in [x * 2.0 for x in range(470, 491)]:
    if t > dur:
        break
    m = mean_at(t)
    if m is None:
        continue
    tag = "近黑" if m < 60 else "有内容"
    if m < 60 and dark_from is None:
        dark_from = t
    print("  t={:6.1f}s mean={:7.2f}  {}".format(t, m, tag))
print("\n首个近黑时刻: {}s".format(dark_from))

# 该时刻落在哪个段窗口
def seg_at(t):
    for w in wins:
        if w["start_s"] <= t < w["end_s"]:
            return w
    return None


if dark_from:
    w = seg_at(dark_from)
    print("落在段: {}".format(json.dumps(w, ensure_ascii=False) if w else "越界（超出 Σ窗口）"))
    # 末 5 段窗口与亮度
    print("\n末 5 段窗口的实测亮度（取窗口中点）:")
    for w in wins[-5:]:
        mid = (w["start_s"] + w["end_s"]) / 2
        m = mean_at(mid) if mid < dur else None
        print("  {:8s} [{:7.2f},{:7.2f}] mid={:7.2f} mean={} chars={}".format(
            w["scene_id"], w["start_s"], w["end_s"], mid,
            "N/A" if m is None else "{:.2f}".format(m), w["chars"]))

out = {"schema": "phase29-p29-1-dark-tail-diagnosis-v1",
       "film": str(film.relative_to(R)).replace("\\", "/"),
       "film_duration_s": dur,
       "script_total_s": sc["total_duration_s"],
       "voice_base_s": voice.get("audio_time_base_s"),
       "sum_windows_s": round(cur, 3),
       "first_dark_t_s": dark_from,
       "segments": wins,
       "hypothesis": ("成片在 {:.0f}s 之后近黑（mean≈18），而脚本/voice 时基到 {:.1f}s ⇒ "
                      "**末尾存在『无内容的黑板』区间**：视频轨在内容用尽后被补齐到音频时基。"
                      "属**渲染侧时基缺内容**，不是映射越界。".format(
                          dark_from or -1, dur))}
p = L / "phase29_p29_1_dark_tail.json"
p.write_text(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
print("\n->", p.relative_to(R).as_posix())
