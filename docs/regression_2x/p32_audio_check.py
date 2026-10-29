# -*- coding: utf-8 -*-
"""P32-4：H7 片尾卡是否**保持音轨逐字节一致**——用 ffmpeg 的 streamhash/md5 直接比对，
避免"解封装到 mka"引入的容器级差异。只读。
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
FF = str(R / "bin" / "ffmpeg.exe")
FFPROBE = str(R / "bin" / "ffprobe.exe")
SB = R / "output" / "phase32_p32_4_sandbox"
PDIR = R / "projects" / "p_b9a90ed75d67" / "output"
sys.stdout.reconfigure(encoding="utf-8")


def streamhash(p, kind):
    r = subprocess.run([FF, "-v", "error", "-i", str(p), "-map", "0:{}:0".format(kind),
                        "-c", "copy", "-f", "streamhash", "-hash", "sha256", "-"],
                       capture_output=True, text=True)
    return (r.stdout or "").strip()


def probe_streams(p):
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries",
                        "stream=index,codec_type,codec_name,sample_rate,channels,"
                        "time_base,start_time,duration,nb_frames",
                        "-of", "json", str(p)], capture_output=True, text=True)
    import json
    return json.loads(r.stdout or "{}").get("streams", [])


def main() -> int:
    base = sorted(PDIR.glob("*draft.mp4"))[0]
    final = sorted(PDIR.glob("*with_outro.mp4"))[0]
    print("base :", base.name)
    print("final:", final.name)
    for kind, lab in (("a", "音频"), ("v", "视频")):
        hb, hf = streamhash(base, kind), streamhash(final, kind)
        print("{} streamhash base ={}".format(lab, hb))
        print("{} streamhash final={}".format(lab, hf))
        print("  => {}".format("一致 ✔" if hb == hf else "不同"))
    print()
    for name, p in (("base", base), ("final", final)):
        print("=== {} streams ===".format(name))
        for s in probe_streams(p):
            print("  #{} {} {} sr={} ch={} start={} dur={} frames={}".format(
                s.get("index"), s.get("codec_type"), s.get("codec_name"),
                s.get("sample_rate"), s.get("channels"), s.get("start_time"),
                str(s.get("duration"))[:10], s.get("nb_frames")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
