# -*- coding: utf-8 -*-
"""Phase 44 / P44-2：**全片单文件语音恢复点**（消除「切片边界自测」的循环论证）。

监理口径要求：恢复点必须在**全片单条旁白音频**上 `silencedetect` 检出，
而非在 36 个景切片上各检一次（切片边界本身会产生伪恢复点 ⇒ 循环论证）。

产出 `output/phase36_voice/recoveries_fullfilm.json`：
  · `absolute`：全片绝对时刻的恢复点（供**独立复测门**使用）；
  · `scene_local`：`{scene_index: [局部秒, ...]}`（供 cue 吸附，与窗口对齐）。
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
sys.stdout.reconfigure(encoding="utf-8")
NOISE, MIN_D = "-35dB", 0.28


def detect_ends(path):
    r = subprocess.run([FF, "-v", "info", "-i", str(path), "-af",
                        "silencedetect=noise={}:d={}".format(NOISE, MIN_D),
                        "-f", "null", "-"], capture_output=True, text=True, errors="ignore")
    txt = (r.stderr or "") + (r.stdout or "")
    return sorted({round(float(x), 3)
                   for x in re.findall(r"silence_end:\s*([0-9.]+)", txt)})


def main() -> int:
    wav = V / "_assemble" / "narration_joined.wav"
    if not wav.is_file():
        print("缺整条旁白 WAV:", wav)
        return 1
    abs_rec = detect_ends(wav)
    tb = json.loads((V / "timebase_v65.json").read_text(encoding="utf-8"))
    wins = tb["windows"]
    scene_local = {}
    for i, w in enumerate(wins):
        s0, s1 = float(w["start_s"]), float(w["end_s"])
        scene_local[str(i)] = [round(x - s0, 3) for x in abs_rec
                               if s0 < x < s1]
    out = {"schema": "p44-2-recoveries-fullfilm-v1",
           "source": "output/phase36_voice/_assemble/narration_joined.wav（**整条**）",
           "noise": NOISE, "min_d": MIN_D,
           "absolute": abs_rec, "absolute_count": len(abs_rec),
           "scene_local": scene_local,
           "note": ("全片单文件检出 ⇒ 避免「切片边界自测」循环论证；"
                    "监理称全片句界 211 个，本机在整条 WAV 上检出 {} 个"
                    "（**检测参数不同源**，如实登记差异）").format(len(abs_rec))}
    (V / "recoveries_fullfilm.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("整条 WAV 检出恢复点 {} 个（监理称 211，参数不同源）".format(len(abs_rec)))
    print("分配到景内（局部时刻）合计 {} 个".format(
        sum(len(v) for v in scene_local.values())))
    print("-> output/phase36_voice/recoveries_fullfilm.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
