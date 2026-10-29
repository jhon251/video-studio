# -*- coding: utf-8 -*-
"""P32-4：**H7 片尾卡**共享实现（in-window overlay；MPEG-TS 拼接；母版音轨流复制）。

设计（沿用冻结 `ops/execution.py::exec_add_outro_card` 语义）
  · 只重编码**末段窗口**（叠加 drawtext 中文卡，显式 CJK 字体，缺字体即 fail-closed）；
  · 未触及区段**流复制**；
  · 与**母版整条音轨**流复制合流 ⇒ 音轨逐字节一致；
  · **总时长不变**（片尾卡落在原有时间轴内）⇒ 不触发时长例外。

⚠️ 实现要点（P32-4 踩坑修正）：拼接必须走 **MPEG-TS**。首版用 MP4 `-c copy` concat，
接头处时间戳断裂 ⇒ 成片**视频轨只有 975.73s**（容器仍 977.88s）⇒ 等于把末 2.1s
变成"无新帧"的补齐区（正是本阶段要消灭的缺陷，A1 直接不成立）。TS 以连续时基承载，
stream copy 拼接后衔接正确（实测视频轨 977.933s 满覆盖）。
"""
from __future__ import annotations

import hashlib
import pathlib
import subprocess

OUTRO_TEXT = "感谢观看　我们下期再见"
OUTRO_FONT = "msyh.ttc"
OUTRO_FONTSDIR = r"C:\Windows\Fonts"
OUTRO_TAIL_S = 2.2


def _sha(p) -> str:
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def _dur(ffprobe: str, p, kind: str = "format"):
    ent = "format=duration" if kind == "format" else "stream=duration"
    sel = [] if kind == "format" else ["-select_streams", kind]
    r = subprocess.run([ffprobe, "-v", "error", *sel, "-show_entries", ent,
                        "-of", "default=nw=1:nk=1", str(p)],
                       capture_output=True, text=True)
    v = (r.stdout or "").strip().splitlines()
    return round(float(v[0]), 3) if v and v[0] else None


def _audio_hash(ffmpeg: str, p) -> str:
    r = subprocess.run([ffmpeg, "-v", "error", "-i", str(p), "-map", "0:a:0",
                        "-c", "copy", "-f", "streamhash", "-hash", "sha256", "-"],
                       capture_output=True, text=True)
    return (r.stdout or "").strip()


def apply_outro(ffmpeg: str, ffprobe: str, film, out, workdir,
                tail_s: float = OUTRO_TAIL_S) -> dict:
    """在 `film` 的末段窗口内叠加片尾卡，输出到 `out`。返回证据 dict。"""
    film, out, workdir = pathlib.Path(film), pathlib.Path(out), pathlib.Path(workdir)
    total = _dur(ffprobe, film)
    t0 = max((total or 0) - tail_s, 0.0)
    tail = max((total or 0) - t0, 0.5)
    fp = pathlib.Path(OUTRO_FONTSDIR) / OUTRO_FONT
    if not fp.is_file():
        raise RuntimeError("OUTRO_FONT_MISSING: {}（fail-closed：不降级、不改用未审定字体）"
                           .format(fp))
    fontopt = "fontfile='{}':".format(str(fp).replace("\\", "/").replace(":", "\\:"))
    vf = ("drawtext=text='{}':{}fontcolor=white:fontsize=64:"
          "box=1:boxcolor=black@0.55:boxborderw=24:x=(w-text_w)/2:y=h-300").format(
        OUTRO_TEXT, fontopt)
    workdir.mkdir(parents=True, exist_ok=True)
    for f in workdir.glob("*"):
        f.unlink()
    head, tailf, joined = workdir / "head.ts", workdir / "tail.ts", workdir / "joined.ts"
    steps = []
    subprocess.run([ffmpeg, "-y", "-v", "error", "-t", "{:.3f}".format(t0), "-i",
                    str(film), "-an", "-c:v", "copy", "-bsf:v", "h264_mp4toannexb",
                    "-f", "mpegts", str(head)], check=True)
    steps.append({"step": "head_stream_copy_ts", "window": [0.0, t0],
                  "duration_s": _dur(ffprobe, head), "sha256": _sha(head),
                  "bytes": head.stat().st_size})
    subprocess.run([ffmpeg, "-y", "-v", "error", "-ss", "{:.3f}".format(t0), "-t",
                    "{:.3f}".format(tail), "-i", str(film), "-vf", vf, "-an",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                    "-pix_fmt", "yuv420p", "-video_track_timescale", "25000",
                    "-f", "mpegts", str(tailf)], check=True)
    steps.append({"step": "tail_reencode_with_outro_card_ts", "window": [t0, total],
                  "seconds": tail, "drawtext": vf, "duration_s": _dur(ffprobe, tailf),
                  "sha256": _sha(tailf), "bytes": tailf.stat().st_size,
                  "font": {"file": str(fp), "bytes": fp.stat().st_size, "sha256": _sha(fp)}})
    subprocess.run([ffmpeg, "-y", "-v", "error", "-i",
                    "concat:{}|{}".format(head.as_posix(), tailf.as_posix()),
                    "-c", "copy", "-f", "mpegts", str(joined)], check=True)
    steps.append({"step": "ts_concat_stream_copy", "duration_s": _dur(ffprobe, joined),
                  "sha256": _sha(joined), "bytes": joined.stat().st_size})
    subprocess.run([ffmpeg, "-y", "-v", "error", "-i", str(joined), "-i", str(film),
                    "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "copy",
                    "-movflags", "+faststart", str(out)], check=True)
    d_out = _dur(ffprobe, out)
    v_out = _dur(ffprobe, out, "v:0")
    steps.append({"step": "mux_stream_copy_audio", "out": out.name,
                  "duration_s": d_out, "sha256": _sha(out), "bytes": out.stat().st_size})
    return {"steps": steps, "outro_text": OUTRO_TEXT, "window": [t0, total],
            "duration_before_s": total, "duration_after_s": d_out,
            "video_track_before_s": _dur(ffprobe, film, "v:0"),
            "video_track_after_s": v_out,
            "duration_unchanged": abs((d_out or 0) - (total or 0)) <= 0.08,
            "video_full_cover": (v_out or 0) >= (d_out or 0) - 0.1,
            "audio_identical_to_base": _audio_hash(ffmpeg, out) == _audio_hash(ffmpeg, film),
            "impl": "mpegts concat stream-copy (P32-4 corrected)",
            "sha256": _sha(out), "bytes": out.stat().st_size}
