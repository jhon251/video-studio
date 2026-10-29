# -*- coding: utf-8 -*-
"""定位 2s 差异：P30 成片实测时长 vs narration_plan 时基 vs 逐景窗口和。只读。
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
FFPROBE = R / "bin" / "ffprobe.exe"
FF = R / "bin" / "ffmpeg.exe"
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import narration as NAR                                # noqa: E402

SCRIPT = R / "output" / "phase27_script_sandbox" / "script_p27_v41_40seg.json"
VOICE = R / "output" / "phase20_voice_sandbox" / "voice_output_40seg_v21.json"
FILMS = {
    "P30 t_9eb07fd396ea": R / "projects/p_8b48148d4bf3/output/t_9eb07fd396ea_draft.mp4",
    "P27 t_5f76c2d95573": R / "projects/p_ddb17cfbacf8/output/t_5f76c2d95573_draft.mp4",
}


def dur(p):
    if not p.exists():
        return None
    r = subprocess.run([str(FFPROBE), "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(p)], capture_output=True, text=True)
    return float(r.stdout.strip().splitlines()[0]) if r.stdout.strip() else None


def main() -> int:
    script = json.loads(SCRIPT.read_text(encoding="utf-8"))
    voice = json.loads(VOICE.read_text(encoding="utf-8"))
    pol = NAR.narration_plan(script, voice)
    wins = pol["segments"]
    s_actual = sum(w["actual_s"] for w in wins)
    s_pause = sum(w["pause_s"] for w in wins)
    print("narration_plan: base={} Σactual={} Σpause={} trail={} => Σ(actual+pause)+trail={}".format(
        pol["audio_time_base_s"], round(s_actual, 3), round(s_pause, 3), pol["trailing_pad_s"],
        round(s_actual + s_pause + pol["trailing_pad_s"], 3)))
    s_win = sum(w["end_s"] - w["start_s"] for w in wins)
    print("逐景窗口和 (end-start) = {:.3f}  (最后一段不含 trailing ⇒ 差 {:.3f})".format(
        s_win, s_actual + s_pause - s_win))
    print("末窗口 end_s={} start_s={}".format(wins[-1]["end_s"], wins[-1]["start_s"]))
    print()
    print("measured_narration_track_s =", pol["measured_narration_track_s"])
    for k, p in FILMS.items():
        print("{:<22} {}  {}".format(k, dur(p), ("{:,}B".format(p.stat().st_size) if p.exists() else "-")))
    na = R / "output/phase30_audio/narration_p30.mp3"
    print("narration_p30.mp3        ", dur(na))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
