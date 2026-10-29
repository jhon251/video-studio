# -*- coding: utf-8 -*-
"""Phase 44 诊断 v3：**全片单文件** silencedetect（复现监理口径）。

监理口径要点（授权书 §2）：「**禁止用切片边界自测——循环论证已登记**」
⇒ 恢复点应在**全片单条旁白音频**上检出，而不是在 36 个景切片上各检一次。
本脚本在全片 mp3 上检恢复点，并与我 F5 用的「切片内检出」对比数量与时刻。
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
V = R / "output" / "phase36_voice"
FF = str(R / "bin" / "ffmpeg.exe")
FFPROBE = str(R / "bin" / "ffprobe.exe")
sys.stdout.reconfigure(encoding="utf-8")


def detect(path, noise, d):
    r = subprocess.run([FF, "-v", "info", "-i", str(path), "-af",
                        "silencedetect=noise={}:d={}".format(noise, d),
                        "-f", "null", "-"], capture_output=True, text=True, errors="ignore")
    txt = (r.stderr or "") + (r.stdout or "")
    starts = [float(x) for x in re.findall(r"silence_start:\s*([0-9.]+)", txt)]
    ends = [float(x) for x in re.findall(r"silence_end:\s*([0-9.]+)", txt)]
    return sorted({round(x, 3) for x in ends}), len(starts)


def dur(p):
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(p)], capture_output=True, text=True)
    v = (r.stdout or "").strip().splitlines()
    return round(float(v[0]), 3) if v and v[0] else None


def main() -> int:
    wav = V / "_assemble" / "narration_joined.wav"
    mp3 = V / "narration_v65.mp3"
    for label, p in (("整条 WAV", wav), ("整条 MP3", mp3)):
        if not p.is_file():
            print("{} 缺失: {}".format(label, p))
            continue
        for noise, d in (("-35dB", 0.28), ("-35dB", 0.30), ("-32dB", 0.28)):
            rec, nsil = detect(p, noise, d)
            print("{:<10} {:<7} d={:<5} 时长 {:.3f}s ⇒ 静音段 {} / **恢复点 {}**".format(
                label, noise, d, dur(p) or 0, nsil, len(rec)))
    print()
    # 我 F5 用的切片内检出
    sl = json.loads((V / "recoveries.json").read_text(encoding="utf-8"))
    print("F5 用的『切片内检出』: {} 个恢复点（{} 景）".format(
        sl["total_recoveries"], sl["scene_count"]))
    print("→ 监理称全片句界 **211** 个；若整条检出接近 211，则应以**整条**为准（避免切片边界自测）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
