# -*- coding: utf-8 -*-
"""6-A / M1 —— 合成故障夹具构建器（**离线、确定性、只写临时目录**）。

用途：为 `tests/integrity_test.py` / `tests/direction_test.py` 生成可复算的媒体与时间轴夹具。
**不写项目目录、不写 DB、不触碰任何基线**；全部产物落在调用方传入的临时目录。
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _run(cmd: list[str]) -> tuple[int, str]:
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def make_film(out: Path, ffmpeg: str, *, duration_s: float = 20.0, speech_s: float = 20.0,
              silence_codec_args=None) -> Path:
    """生成"彩条+字幕变更"的短片：`speech_s` 秒有声（正弦），其余静音。

    · `speech_s >= duration_s` → 无静音；`speech_s < duration_s` → 尾部静音（apad 语义）。
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    args = silence_codec_args or ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset",
                                 "ultrafast", "-c:a", "aac"]
    cmd = [ffmpeg, "-y", "-v", "error",
           "-f", "lavfi", "-t", "{:.3f}".format(duration_s), "-i",
           "testsrc=size=320x180:rate=25",
           "-f", "lavfi", "-t", "{:.3f}".format(speech_s), "-i",
           "sine=frequency=440:sample_rate=24000",
           "-filter_complex",
           "[1:a]apad[a]" if speech_s < duration_s else "[1:a]anull[a]",
           "-map", "0:v", "-map", "[a]", "-shortest", *args,
           "-t", "{:.3f}".format(duration_s), str(out)]
    rc, err = _run(cmd)
    if rc != 0 or not out.is_file():
        raise RuntimeError("make_film failed rc={}: {}".format(rc, err[-300:]))
    return out


def make_track_mismatch(out: Path, ffmpeg: str, *, video_s: float = 8.0, audio_s: float = 20.0,
                        speech_s: float = 20.0) -> Path:
    """视频轨比音频轨短（复现 v7 的"视频轨短 21 s"形态）。"""
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ffmpeg, "-y", "-v", "error",
           "-f", "lavfi", "-t", "{:.3f}".format(video_s), "-i", "testsrc=size=320x180:rate=25",
           "-f", "lavfi", "-t", "{:.3f}".format(speech_s), "-i",
           "sine=frequency=440:sample_rate=24000",
           "-filter_complex", "[1:a]apad[a]", "-map", "0:v", "-map", "[a]",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast", "-c:a", "aac",
           "-t", "{:.3f}".format(audio_s), str(out)]
    rc, err = _run(cmd)
    if rc != 0 or not out.is_file():
        raise RuntimeError("make_track_mismatch failed rc={}: {}".format(rc, err[-300:]))
    return out


def srt_from_cues(cues: list[tuple[float, float, str]]) -> str:
    def ts(t: float) -> str:
        ms = int(round(t * 1000))
        h, rem = divmod(ms, 3600000)
        m, rem = divmod(rem, 60000)
        s, ms = divmod(rem, 1000)
        return "{:02d}:{:02d}:{:02d},{:03d}".format(h, m, s, ms)
    return "\n".join("{}\n{} --> {}\n{}\n".format(i, ts(a), ts(b), t)
                     for i, (a, b, t) in enumerate(cues, 1))


def timeline(n_scenes: int, hold_s: float, assets: list[str] | None = None) -> list[dict]:
    """构造时间轴夹具：每镜 hold_s 秒，素材按 `assets` 轮转（缺省每镜不同素材）。"""
    out, t = [], 0.0
    for i in range(n_scenes):
        aid = (assets[i % len(assets)] if assets else "asset_{:02d}".format(i + 1))
        out.append({"scene_id": "S{:02d}".format(i + 1), "start_s": round(t, 3),
                    "end_s": round(t + hold_s, 3), "selected_asset": {"asset_id": aid}})
        t += hold_s
    return out


def segments(n: int, text: str, duration_s: float) -> list[dict]:
    return [{"duration_s": duration_s, "narration": "{}（第 {} 段）".format(text, i + 1)}
            for i in range(n)]


def write_json(path: Path, obj) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    return path
