# -*- coding: utf-8 -*-
"""P32-4：核查 H7 施加后的**视频轨时间覆盖**（是否在 975.77–977.88 出现"无新帧"的补齐）。

方法：
  · 取末段若干时刻抽帧，计算相邻帧**逐像素差**（若某区间完全无变化 ⇒ 只有最后一帧被停住）；
  · 读取包级 pts 最大值。
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

import numpy as np
from PIL import Image

R = pathlib.Path(r"C:\mp4agent\video-studio")
FF = R / "bin" / "ffmpeg.exe"
FFPROBE = R / "bin" / "ffprobe.exe"
PDIR = R / "projects" / "p_b9a90ed75d67" / "output"
PROBE = R / "output" / "p32_probe"
PROBE.mkdir(parents=True, exist_ok=True)
sys.stdout.reconfigure(encoding="utf-8")


def frame(film, t, tag):
    o = PROBE / "tail_{}_{}.png".format(tag, str(t).replace(".", "_"))
    subprocess.run([str(FF), "-v", "error", "-y", "-ss", "{}".format(t), "-i", str(film),
                    "-frames:v", "1", str(o)], capture_output=True)
    if not o.is_file():
        return None
    with Image.open(o) as im:
        return np.asarray(im.convert("L"), dtype=np.float64)


def main() -> int:
    base = sorted(PDIR.glob("*draft.mp4"))[0]
    final = sorted(PDIR.glob("*with_outro.mp4"))[0]
    times = [974.0, 975.0, 975.6, 975.8, 976.0, 976.5, 977.0, 977.5, 977.8]
    print("=== 末段抽帧：base vs final，及 final 相邻帧差异 ===")
    prev = None
    for t in times:
        a = frame(base, t, "b")
        b = frame(final, t, "f")
        d_ab = float(np.abs(a - b).mean()) if (a is not None and b is not None) else None
        d_prev = (float(np.abs(b - prev).mean())
                  if (b is not None and prev is not None) else None)
        print("  t={:>6.1f}s | |base-final|={:>7.3f} | final 与前一抽样帧差={}".format(
            t, d_ab if d_ab is not None else -1,
            ("{:.3f}".format(d_prev) if d_prev is not None else "-")))
        if b is not None:
            prev = b
    print()
    print("=== 视频包最大 pts（final / base）===")
    for lab, f in (("base", base), ("final", final)):
        r = subprocess.run([str(FFPROBE), "-v", "error", "-select_streams", "v:0",
                            "-show_entries", "packet=pts_time", "-of", "csv=p=0",
                            "-read_intervals", "970%+8", str(f)],
                           capture_output=True, text=True)
        pts = [float(x) for x in (r.stdout or "").split() if x.strip().replace(".", "").isdigit()]
        print("  {}: n={} first={} last={}".format(
            lab, len(pts), pts[0] if pts else None, pts[-1] if pts else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
