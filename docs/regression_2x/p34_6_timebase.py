# -*- coding: utf-8 -*-
"""P33-3：由 **v4.1 实测音频** 派生新时基并拼装整条旁白。

新时基规则（**登记版本** `p34-v42-timebase-v1`）：
    Σ(逐段实测) + Σ(逐边界 pause) + trailing
    · **逐边界 pause = 0**：v4.1 为**逐段独立合成**，段间不留额外静音
      （实测踩坑：若计边界 pause 而生产 `_build_material_timeline` 不计入窗口，
        会得到"音频比时间轴长 11s"的尾部静音缺陷；故权威口径取 0，让音频事实 == 时间轴事实）；
    · trailing = 2.0s（沿用既有常量语义，由渲染链 `apad` 承担）。

产出：
  · `output/phase34_voice/narration_v42.mp3`   整条旁白
  · `output/phase34_voice/timebase_v42.json`   新时基 + 逐段窗口 + 断言
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
OUT = R / "output" / "phase34_voice"
SEGD = OUT / "seg"
WORK = OUT / "_assemble"
FFMPEG = R / "bin" / "ffmpeg.exe"
FFPROBE = R / "bin" / "ffprobe.exe"
sys.stdout.reconfigure(encoding="utf-8")

TRAILING_S = 2.0
TB_RULE = "p34-v42-timebase-v1:sum(measured)+0.0*pause+trailing"


def dur(p):
    r = subprocess.run([str(FFPROBE), "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(p)], capture_output=True, text=True)
    v = (r.stdout or "").strip().splitlines()
    return round(float(v[0]), 3) if v and v[0] else None


def main() -> int:
    voice = json.loads((OUT / "voice_output_v42.json").read_text(encoding="utf-8"))
    segs = voice["segments"]
    WORK.mkdir(parents=True, exist_ok=True)
    for f in WORK.glob("sil_*.wav"):
        f.unlink()

    parts, cursor, windows = [], 0.0, []
    for i, s in enumerate(segs):
        d = float(s["duration_s"])
        w = WORK / "seg_{:02d}.wav".format(i)
        if not w.is_file():
            subprocess.run([str(FFMPEG), "-y", "-v", "error", "-i",
                            str(SEGD / "{}.mp3".format(s["scene_id"])),
                            "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", str(w)],
                           check=True)
        parts.append(w)
        start = cursor
        end = start + d
        cursor = end
        windows.append({"index": i, "scene_id": s["scene_id"],
                        "parent_scene_id": s.get("parent_scene_id"),
                        "start_s": round(start, 3), "end_s": round(end, 3),
                        "window_s": round(end - start, 3),
                        "actual_s": round(d, 3), "pause_s": 0.0,
                        "text_sha256": s["text_sha256"], "audio": s["audio"]})
    base = round(cursor + TRAILING_S, 3)
    windows[-1]["end_s"] = base
    windows[-1]["window_s"] = round(base - windows[-1]["start_s"], 3)
    windows[-1]["trailing_s"] = TRAILING_S

    lst = WORK / "concat.txt"
    lst.write_text("".join("file '{}'\n".format(p.as_posix()) for p in parts),
                   encoding="utf-8")
    joined_wav = WORK / "narration_joined.wav"
    subprocess.run([str(FFMPEG), "-y", "-v", "error", "-f", "concat", "-safe", "0",
                    "-i", str(lst), "-c", "copy", str(joined_wav)], check=True)
    narr = OUT / "narration_v42.mp3"
    subprocess.run([str(FFMPEG), "-y", "-v", "error", "-i", str(joined_wav),
                    "-c:a", "libmp3lame", "-b:a", "48k", "-ar", "24000", "-ac", "1",
                    str(narr)], check=True)
    measured = dur(joined_wav)

    spoken = round(sum(float(s["duration_s"]) for s in segs), 3)
    tb = {
        "schema": "p34-v42-timebase-v1",
        "rule": TB_RULE,
        "audio_time_base_s": base,
        "sum_measured_speech_s": spoken,
        "sum_pause_s": 0.0,
        "trailing_pad_s": TRAILING_S,
        "narration_file": "output/phase34_voice/narration_v42.mp3",
        "narration_measured_s": measured,
        "narration_sha256": hashlib.sha256(narr.read_bytes()).hexdigest(),
        "segments_total": len(segs),
        "windows": windows,
        "assertion_frozen_before_render": {
            "claimed_time_base_s": base,
            "expected_audio_content_s": round(spoken, 3),
            "measured_narration_s": measured,
            "trailing_handled_by": "渲染链 apad（音频补齐到时间轴；既有契约，语义未改）",
            "tolerance_s": 0.1,
            "delta_s": (round(measured - spoken, 3) if measured else None),
            "ok": (measured is not None and abs(measured - spoken) <= 0.1),
        },
        "old_timebase_retired": {"old_contract_s": 978.7, "old_measured_s": 977.88,
                                 "note": "旧 978.7±1 契约随 v3/V20 谱系废止；本版按新时基登记"},
        "zero_text_change": True,
    }
    (OUT / "timebase_v42.json").write_text(
        json.dumps(tb, ensure_ascii=False, indent=1), encoding="utf-8")
    print("段数 {}".format(len(segs)))
    print("Σ实测语音      = {:.3f}s".format(spoken))
    print("边界 pause     = 0.000s（口径：段间不留额外静音）")
    print("trailing       = {:.3f}s".format(TRAILING_S))
    print("**新时基**     = {:.3f}s".format(base))
    print("整条旁白实测   = {}s".format(measured))
    a = tb["assertion_frozen_before_render"]
    print("断言 Δ={}s (容差 0.1) => {}".format(a["delta_s"], "OK" if a["ok"] else "FAIL"))
    print("旧契约 978.7s -> 新 {:.1f}s（缩短 {:.1f}s）".format(base, 977.88 - base))
    print("-> " + str((OUT / "timebase_v42.json").relative_to(R)))
    return 0 if a["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
