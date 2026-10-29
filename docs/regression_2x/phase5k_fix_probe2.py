# -*- coding: utf-8 -*-
"""5-K 修复探针 2：S4 = 1fps 输入（-t d+1）+ 每段滤镜 `trim=duration=d,setpts=PTS-STARTPTS`。

目标：每镜头**精确** d 秒（含小数 d），且解码量仍为 ~d 帧（1fps），远低于旧形态的 25·d 帧。
"""
import json
import pathlib
import subprocess
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
cfg = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8-sig"))
FF = cfg["tools"]["ffmpeg"]["path"]
FP = cfg["tools"]["ffmpeg"]["ffprobe"]
tmp = pathlib.Path(tempfile.mkdtemp(prefix="vs_5k_s4_"))
img = tmp / "img.png"
subprocess.run([FF, "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=0x204060:size=640x360",
                "-frames:v", "1", str(img)], capture_output=True)


def probe(p):
    r = subprocess.run([FP, "-v", "error", "-print_format", "json", "-show_format", "-show_streams",
                        str(p)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    d = json.loads(r.stdout or "{}")
    v = next((s for s in d.get("streams") or [] if s.get("codec_type") == "video"), {})
    return (round(float((d.get("format") or {}).get("duration") or 0), 3),
            round(float(v.get("duration") or 0), 3), int(v.get("nb_frames") or 0), v.get("avg_frame_rate"))


print("S4 单镜精确性（期望 视频时长 == d；d 含小数）")
for d in (2.0, 2.5, 5.0, 20.0, 73.4):
    for tag, setpts in (("S4_setpts", True), ("S4b_plain", False)):
        out = tmp / "{}_{}.mp4".format(tag, d)
        fc = ("[0:v]scale=640:360,setsar=1,fps=30,trim=duration={:.3f}".format(d)
              + (",setpts=PTS-STARTPTS" if setpts else "") + "[v]")
        cmd = [FF, "-y", "-v", "error", "-loop", "1", "-framerate", "1", "-t", "{:.3f}".format(d + 1),
               "-i", str(img), "-filter_complex", fc, "-map", "[v]", "-c:v", "libx264",
               "-pix_fmt", "yuv420p", "-t", "{:.3f}".format(d), str(out)]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        got = probe(out) if out.is_file() else "rc={}".format(r.returncode)
        exact = isinstance(got, tuple) and abs(got[1] - d) <= 0.034
        print("  d={:<6} {:<10} {:<30} exact={}".format(d, tag, str(got), exact))

print("\nS4 两段 concat（图片 20.0s + 纯色 10.0s，期望 30.0s）")
out = tmp / "cat_s4.mp4"
fc = ("[0:v]scale=640:360,setsar=1,fps=30,trim=duration=20.000,setpts=PTS-STARTPTS[v0];"
      "[1:v]scale=640:360,setsar=1,fps=30[v1];[v0][v1]concat=n=2:v=1:a=0[v]")
r = subprocess.run([FF, "-y", "-v", "error", "-loop", "1", "-framerate", "1", "-t", "21.000",
                    "-i", str(img), "-f", "lavfi", "-t", "10.000", "-i",
                    "color=c=0x0b1226:size=640x360:rate=30", "-filter_complex", fc, "-map", "[v]",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-t", "30.000", str(out)],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
print("  rc={} {}".format(r.returncode, probe(out) if out.is_file() else (r.stderr or "")[-160:]))

print("\nS4 混入小数场景（图片 7.5s + 纯色 4.25s = 11.75s，期望 11.75s）")
out2 = tmp / "cat_s4_frac.mp4"
fc2 = ("[0:v]scale=640:360,setsar=1,fps=30,trim=duration=7.500,setpts=PTS-STARTPTS[v0];"
       "[1:v]scale=640:360,setsar=1,fps=30,trim=duration=4.250,setpts=PTS-STARTPTS[v1];"
       "[v0][v1]concat=n=2:v=1:a=0[v]")
r2 = subprocess.run([FF, "-y", "-v", "error", "-loop", "1", "-framerate", "1", "-t", "8.500",
                     "-i", str(img), "-f", "lavfi", "-t", "4.250", "-i",
                     "color=c=0x0b1226:size=640x360:rate=30", "-filter_complex", fc2, "-map", "[v]",
                     "-c:v", "libx264", "-pix_fmt", "yuv420p", "-t", "11.750", str(out2)],
                    capture_output=True, text=True, encoding="utf-8", errors="replace")
print("  rc={} {}".format(r2.returncode, probe(out2) if out2.is_file() else (r2.stderr or "")[-160:]))
print("\ntmp:", tmp)
