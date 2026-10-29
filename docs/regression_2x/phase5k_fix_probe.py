# -*- coding: utf-8 -*-
"""5-K 修复探针：寻找**语义等价**（每镜时长精确）且保留低解码负载的图片输入形态。

候选：
  S1 现状  : -loop 1 -framerate 1 -t d -i img                + [i:v]scale...,fps
  S2 单帧+滤镜循环: -framerate 1 -i img + [i:v]scale...,fps,loop=loop=-1:size=1:start=0,trim=duration=d
  S3 现状+1s: -loop 1 -framerate 1 -t (d+1) -i img           + [i:v]scale...,fps
  S0 旧形态 : -loop 1 -t d -i img                            + [i:v]scale...,fps
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
tmp = pathlib.Path(tempfile.mkdtemp(prefix="vs_5k_fix_"))
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


def build(shape, d, out):
    base = "[0:v]scale=640:360,setsar=1,fps=30"
    if shape == "S0":
        args = ["-loop", "1", "-t", "{:.3f}".format(d), "-i", str(img)]
        fc = base + "[v]"
    elif shape == "S1":
        args = ["-loop", "1", "-framerate", "1", "-t", "{:.3f}".format(d), "-i", str(img)]
        fc = base + "[v]"
    elif shape == "S2":
        args = ["-framerate", "1", "-i", str(img)]
        fc = base + ",loop=loop=-1:size=1:start=0,trim=duration={:.3f},setpts=PTS-STARTPTS[v]".format(d)
    elif shape == "S3":
        args = ["-loop", "1", "-framerate", "1", "-t", "{:.3f}".format(d + 1), "-i", str(img)]
        fc = base + "[v]"
    else:
        raise SystemExit("unknown shape")
    cmd = [FF, "-y", "-v", "error", *args, "-filter_complex", fc, "-map", "[v]", "-c:v", "libx264",
           "-pix_fmt", "yuv420p", "-t", "{:.3f}".format(d), str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r


print("单镜时长精确性（期望 视频时长 == d）")
print("{:<8}".format("target") + "".join("{:<28}".format(s) for s in ("S0旧", "S1现状", "S2单帧+loop", "S3+1s")))
for d in (2.0, 2.5, 5.0, 20.0, 73.4):
    row = []
    for shape in ("S0", "S1", "S2", "S3"):
        out = tmp / "{}_{}.mp4".format(shape, d)
        r = build(shape, d, out)
        row.append(probe(out) if out.is_file() and r.returncode == 0 else "rc={}".format(r.returncode))
    print("{:<8}".format(d) + "".join("{:<28}".format(str(x)) for x in row))

print("\n两段 concat（图片 20s + 纯色 10s，总 30s；期望 30.0s）")
for shape in ("S0", "S1", "S2", "S3"):
    out = tmp / "cat_{}.mp4".format(shape)
    d1, d2 = 20.0, 10.0
    if shape == "S2":
        args = ["-framerate", "1", "-i", str(img), "-f", "lavfi", "-t", "{:.3f}".format(d2), "-i",
                "color=c=0x0b1226:size=640x360:rate=30"]
        fc = ("[0:v]scale=640:360,setsar=1,fps=30,loop=loop=-1:size=1:start=0,"
              "trim=duration={:.3f},setpts=PTS-STARTPTS[v0];".format(d1) +
              "[1:v]scale=640:360,setsar=1,fps=30[v1];[v0][v1]concat=n=2:v=1:a=0[v]")
    else:
        extra = {"S0": [], "S1": ["-framerate", "1"], "S3": ["-framerate", "1"]}[shape]
        t1 = d1 + 1 if shape == "S3" else d1
        args = ["-loop", "1", *extra, "-t", "{:.3f}".format(t1), "-i", str(img),
                "-f", "lavfi", "-t", "{:.3f}".format(d2), "-i",
                "color=c=0x0b1226:size=640x360:rate=30"]
        fc = ("[0:v]scale=640:360,setsar=1,fps=30[v0];[1:v]scale=640:360,setsar=1,fps=30[v1];"
              "[v0][v1]concat=n=2:v=1:a=0[v]")
    cmd = [FF, "-y", "-v", "error", *args, "-filter_complex", fc, "-map", "[v]", "-c:v",
           "libx264", "-pix_fmt", "yuv420p", "-t", "30.0", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print("  {:<4} rc={} {}".format(shape, r.returncode,
                                    probe(out) if out.is_file() else (r.stderr or "")[-140:]))
print("\ntmp:", tmp)
