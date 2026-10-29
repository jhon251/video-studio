# -*- coding: utf-8 -*-
"""Phase 43 / P43-1：**全片语音恢复点检测**（silencedetect -35dB, d=0.28）。

输出 `output/phase36_voice/recoveries.json`：
  `{scene_index: [局部恢复点秒, ...]}`（每个景切片内，停顿**结束**处 = 语音恢复点）。
用途：字幕 cue 的**切换点**在 ±0.4s 内吸附到这些恢复点（`core.captions.build_cues`
的 `recoveries=` 参数）。
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
VOICE = R / "output" / "phase36_voice"
FF = str(R / "bin" / "ffmpeg.exe")
FFPROBE = str(R / "bin" / "ffprobe.exe")
sys.stdout.reconfigure(encoding="utf-8")
NOISE, MIN_D = "-35dB", 0.28


def dur(p):
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(p)], capture_output=True, text=True)
    v = (r.stdout or "").strip().splitlines()
    return round(float(v[0]), 3) if v and v[0] else None


def recoveries(p):
    """停顿**结束**时刻（语音恢复点）= silencedetect 的 `silence_end`。"""
    r = subprocess.run([FF, "-v", "info", "-i", str(p), "-af",
                        "silencedetect=noise={}:d={}".format(NOISE, MIN_D),
                        "-f", "null", "-"], capture_output=True, text=True, errors="ignore")
    txt = (r.stderr or "") + (r.stdout or "")
    return sorted({round(float(x), 3)
                   for x in re.findall(r"silence_end:\s*([0-9.]+)", txt)})


def main() -> int:
    tb = json.loads((VOICE / "timebase_v65.json").read_text(encoding="utf-8"))
    wins = tb["windows"]
    seg_of = {w["index"]: w["scene_id"] for w in wins}
    out, tot = {}, 0
    for i in sorted(seg_of):
        # 景切片为 wav（seg/<scene_id>.wav）；若无则用整段 wav 按窗口裁
        p = VOICE / "seg" / "{}.wav".format(seg_of[i])
        if not p.is_file():
            p = VOICE / "wav" / "{}.wav".format(str(seg_of[i]).split("_")[0])
            if not p.is_file():
                continue
        rec = recoveries(p)
        out[str(i)] = rec
        tot += len(rec)
    (VOICE / "recoveries.json").write_text(json.dumps(
        {"schema": "p43-1-recoveries-v1", "noise": NOISE, "min_d": MIN_D,
         "source": "seg/<scene_id>.wav（silencedetect silence_end）",
         "scene_count": len(out), "total_recoveries": tot,
         "recoveries": out}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("景 {} | 恢复点合计 {} 个 | 参数 noise={} d={}".format(
        len(out), tot, NOISE, MIN_D))
    sample = list(out.items())[:4]
    for k, v in sample:
        print("  景#{}: {} 个恢复点 {}".format(k, len(v), v[:6]))
    print("-> output/phase36_voice/recoveries.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
