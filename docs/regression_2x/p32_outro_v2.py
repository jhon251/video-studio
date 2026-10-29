# -*- coding: utf-8 -*-
"""P32-4：在既有基片上**重新施加修正后的 H7 片尾卡**（TS 拼接），并核验：

  · 容器时长不变（977.880 ±0.08）
  · **视频轨时长回到 ~977.87**（不得再出现 975.7 的"无新帧"补齐）
  · 音轨 streamhash 与基片**逐字节一致**
  · 片尾卡确实出现在末段（抽帧与基片差异显著）
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys

import numpy as np
from PIL import Image

R = pathlib.Path(r"C:\mp4agent\video-studio")
FF = str(R / "bin" / "ffmpeg.exe")
FFPROBE = str(R / "bin" / "ffprobe.exe")
SB = R / "output" / "phase32_p32_4_sandbox"
PROBE = R / "output" / "p32_probe"
PROBE.mkdir(parents=True, exist_ok=True)
PDIR = R / "projects" / "p_b9a90ed75d67" / "output"
sys.stdout.reconfigure(encoding="utf-8")

OUTRO_TEXT = "感谢观看　我们下期再见"
OUTRO_FONT = "msyh.ttc"
OUTRO_FONTSDIR = r"C:\Windows\Fonts"
OUTRO_TAIL_S = 2.2


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def dur(p, kind="format"):
    if kind == "format":
        r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                            "-of", "default=nw=1:nk=1", str(p)],
                           capture_output=True, text=True)
    else:
        r = subprocess.run([FFPROBE, "-v", "error", "-select_streams", kind,
                            "-show_entries", "stream=duration", "-of",
                            "default=nw=1:nk=1", str(p)], capture_output=True, text=True)
    v = (r.stdout or "").strip().splitlines()
    return round(float(v[0]), 3) if v and v[0] else None


def streamhash(p, kind):
    r = subprocess.run([FF, "-v", "error", "-i", str(p), "-map", "0:{}:0".format(kind),
                        "-c", "copy", "-f", "streamhash", "-hash", "sha256", "-"],
                       capture_output=True, text=True)
    return (r.stdout or "").strip()


def gray(p, t, tag):
    o = PROBE / "h7_{}_{}.png".format(tag, str(t).replace(".", "_"))
    subprocess.run([FF, "-v", "error", "-y", "-ss", "{}".format(t), "-i", str(p),
                    "-frames:v", "1", str(o)], capture_output=True)
    if not o.is_file():
        return None
    with Image.open(o) as im:
        return np.asarray(im.convert("L"), dtype=float)


def apply_outro(film: pathlib.Path, out: pathlib.Path) -> dict:
    total = dur(film)
    t0 = max(total - OUTRO_TAIL_S, 0.0)
    tail = max(total - t0, 0.5)
    fp = pathlib.Path(OUTRO_FONTSDIR) / OUTRO_FONT
    if not fp.is_file():
        raise RuntimeError("OUTRO_FONT_MISSING: {}".format(fp))
    fontopt = "fontfile='{}':".format(str(fp).replace("\\", "/").replace(":", "\\:"))
    vf = ("drawtext=text='{}':{}fontcolor=white:fontsize=64:"
          "box=1:boxcolor=black@0.55:boxborderw=24:x=(w-text_w)/2:y=h-300").format(
        OUTRO_TEXT, fontopt)
    work = SB / "work2"
    work.mkdir(parents=True, exist_ok=True)
    for f in work.glob("*"):
        f.unlink()
    head, tailf, joined = work / "head.ts", work / "tail.ts", work / "joined.ts"
    steps = []
    subprocess.run([FF, "-y", "-v", "error", "-t", "{:.3f}".format(t0), "-i", str(film),
                    "-an", "-c:v", "copy", "-bsf:v", "h264_mp4toannexb", "-f", "mpegts",
                    str(head)], check=True)
    subprocess.run([FF, "-y", "-v", "error", "-ss", "{:.3f}".format(t0), "-t",
                    "{:.3f}".format(tail), "-i", str(film), "-vf", vf, "-an",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                    "-pix_fmt", "yuv420p", "-video_track_timescale", "25000",
                    "-f", "mpegts", str(tailf)], check=True)
    subprocess.run([FF, "-y", "-v", "error", "-i",
                    "concat:{}|{}".format(head.as_posix(), tailf.as_posix()),
                    "-c", "copy", "-f", "mpegts", str(joined)], check=True)
    subprocess.run([FF, "-y", "-v", "error", "-i", str(joined), "-i", str(film),
                    "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "copy",
                    "-movflags", "+faststart", str(out)], check=True)
    steps = [{"step": "head_stream_copy_ts", "s": dur(head), "bytes": head.stat().st_size,
              "sha256": sha(head)},
             {"step": "tail_reencode_ts", "s": dur(tailf), "bytes": tailf.stat().st_size,
              "sha256": sha(tailf), "drawtext": vf},
             {"step": "ts_concat", "s": dur(joined), "sha256": sha(joined)},
             {"step": "mux_audio_copy", "s": dur(out), "sha256": sha(out)}]
    return {"steps": steps, "outro_text": OUTRO_TEXT, "window": [t0, total],
            "t0": t0, "tail_s": tail,
            "duration_before_s": total, "duration_after_s": dur(out),
            "video_dur_before_s": dur(film, "v:0"), "video_dur_after_s": dur(out, "v:0"),
            "duration_unchanged": abs((dur(out) or 0) - (total or 0)) <= 0.08}


def main() -> int:
    base = sorted(PDIR.glob("*draft.mp4"))[0]
    out = PDIR / (base.stem + "_with_outro_v2.mp4")
    print("基片:", base.name, "| 视频轨 {:.3f}s | 容器 {:.3f}s".format(
        dur(base, "v:0") or 0, dur(base) or 0))
    info = apply_outro(base, out)
    print()
    print("=== 修正后 H7（TS 拼接）===")
    for s in info["steps"]:
        print("  {:<24} dur={:>9.3f}s {:,}B".format(
            s["step"], s.get("s") or 0, s.get("bytes", 0)))
    print()
    print("容器时长: {:.3f} -> {:.3f}  {}".format(
        info["duration_before_s"], info["duration_after_s"],
        "✔ 不变" if info["duration_unchanged"] else "✘ 变了"))
    print("视频轨  : {:.3f} -> {:.3f}  {}".format(
        info["video_dur_before_s"], info["video_dur_after_s"],
        "✔ 恢复满覆盖" if (info["video_dur_after_s"] or 0) >= 977.5
        else "✘ 仍有缺口"))
    ha, hb = streamhash(base, "a"), streamhash(out, "a")
    print("音轨    : {} vs {} => {}".format(ha[:20], hb[:20],
                                            "逐字节一致 ✔" if ha == hb else "不同 ✘"))
    print()
    print("=== 片尾卡可见性（final vs base 逐像素差）===")
    for t in (975.8, 976.5, 977.0, 977.5, 977.8):
        a, b = gray(base, t, "b"), gray(out, t, "f")
        d = float(np.abs(a - b).mean()) if (a is not None and b is not None) else None
        print("  t={:>6.1f}s |diff|={}".format(
            t, "{:.3f}".format(d) if d is not None else "抽帧失败"))
    (SB / "outro_v2.json").write_text(json.dumps(info, ensure_ascii=False, indent=1),
                                      encoding="utf-8")
    print()
    print("-> 成片", out.name, "|", "{:,}B".format(out.stat().st_size))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
