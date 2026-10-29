# -*- coding: utf-8 -*-
"""Phase 52 / P52-1：**逐景语音运行提取**（独立信号源）。

对每个景的**实际音频切片**（`output/phase36_voice/seg/<scene>.wav`）做
`silencedetect(noise=-30dB, d=0.05)`，取**非静音区间**作为**细粒度语音运行**，
落盘 `output/phase52_voice/runs_by_scene.json`（景内**局部**秒 + 绝对秒两套）。

这是 cue 构建的**唯一时间来源**（弃用合成 manifest 的绝对时刻换算）。
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
V36 = R / "output" / "phase36_voice"
OUT = R / "output" / "phase52_voice"
FF = str(R / "bin" / "ffmpeg.exe")
FFPROBE = str(R / "bin" / "ffprobe.exe")
sys.stdout.reconfigure(encoding="utf-8")
NOISE, MIN_D = "-30dB", 0.05


def dur(p):
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(p)],
                       capture_output=True, text=True)
    v = (r.stdout or "").strip().splitlines()
    return round(float(v[0]), 3) if v and v[0] else None


def runs_of(path):
    r = subprocess.run([FF, "-v", "info", "-i", str(path), "-af",
                        "silencedetect=noise={}:d={}".format(NOISE, MIN_D),
                        "-f", "null", "-"], capture_output=True, text=True,
                       errors="ignore")
    t = (r.stderr or "") + (r.stdout or "")
    ss = [float(x) for x in re.findall(r"silence_start:\s*([0-9.]+)", t)]
    se = [float(x) for x in re.findall(r"silence_end:\s*([0-9.]+)", t)]
    d = dur(path)
    sil = list(zip(ss, se + ([d] if (d and len(se) < len(ss)) else [])))
    out, cur = [], 0.0
    for a, b in sil:
        if a > cur:
            out.append((round(cur, 3), round(a, 3)))
        cur = max(cur, b)
    if d and d > cur:
        out.append((round(cur, 3), round(d, 3)))
    return [x for x in out if x[1] - x[0] > 0.02], d


def main() -> int:
    tb = json.loads((V36 / "timebase_v65.json").read_text(encoding="utf-8"))
    wins = tb["windows"]
    OUT.mkdir(parents=True, exist_ok=True)
    local, absolute, missing, total_speech = {}, {}, [], 0.0
    for w in wins:
        sid = w["scene_id"]
        p = V36 / "seg" / "{}.wav".format(sid)
        if not p.is_file():
            missing.append(sid)
            continue
        rns, d = runs_of(p)
        local[sid] = [[a, b] for a, b in rns]
        w0 = float(w["start_s"])
        absolute[sid] = [[round(w0 + a, 3), round(w0 + b, 3)] for a, b in rns]
        total_speech += sum(b - a for a, b in rns)
    art = {"schema": "p52-1-speech-runs-v1",
           "source": "每景**实际音频切片** seg/<scene>.wav",
           "detector": "silencedetect noise={} d={}".format(NOISE, MIN_D),
           "note": ("取**非静音区间**为细粒度语音运行；这是 cue 构建的**唯一时间来源**"
                    "（弃用合成 manifest 绝对时刻换算 —— 其时钟与实际音频不同源）。"),
           "scene_count": len(local), "missing_scenes": missing,
           "total_speech_s": round(total_speech, 3),
           "runs_by_scene": local, "runs_by_scene_absolute": absolute}
    (OUT / "runs_by_scene.json").write_text(
        json.dumps(art, ensure_ascii=False, indent=1), encoding="utf-8")
    n = sum(len(v) for v in local.values())
    print("景 {} | 语音运行合计 **{}** 个 | 语音总时长 {:.1f}s".format(
        len(local), n, total_speech))
    print("缺切片景:", missing or "无")
    print("样例（P01_1 前 5 运行）:", local.get("P01_1", [])[:5])
    print("-> output/phase52_voice/runs_by_scene.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
