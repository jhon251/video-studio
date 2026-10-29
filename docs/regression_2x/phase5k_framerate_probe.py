# -*- coding: utf-8 -*-
"""5-K 探针：`-framerate 1` 在不同参数形态下的输出时长/帧数（用于确定真实语义，只读临时文件）。"""
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
tmp = pathlib.Path(tempfile.mkdtemp(prefix="vs_5k_probe_"))
img = tmp / "img.png"
subprocess.run([FF, "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=0x204060:size=640x360",
                "-frames:v", "1", str(img)], capture_output=True)


def probe(p):
    r = subprocess.run([FP, "-v", "error", "-print_format", "json", "-show_format", "-show_streams",
                        str(p)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    d = json.loads(r.stdout or "{}")
    v = next((s for s in d.get("streams") or [] if s.get("codec_type") == "video"), {})
    return {"dur": round(float((d.get("format") or {}).get("duration") or 0), 3),
            "fps": v.get("avg_frame_rate"), "frames": int(v.get("nb_frames") or 0)}


SHAPES = {
    "A_old_vf": ["-loop", "1", "-t", "2.0", "-i", str(img), "-vf", "fps=30", "-t", "2.0"],
    "B_new_vf": ["-loop", "1", "-framerate", "1", "-t", "2.0", "-i", str(img), "-vf", "fps=30",
                 "-t", "2.0"],
    "C_old_filter_complex": ["-loop", "1", "-t", "2.0", "-i", str(img), "-filter_complex",
                             "[0:v]scale=640:360,setsar=1,fps=30[v]", "-map", "[v]", "-t", "2.0"],
    "D_new_filter_complex": ["-loop", "1", "-framerate", "1", "-t", "2.0", "-i", str(img),
                             "-filter_complex", "[0:v]scale=640:360,setsar=1,fps=30[v]",
                             "-map", "[v]", "-t", "2.0"],
    "E_new_no_output_t": ["-loop", "1", "-framerate", "1", "-t", "2.0", "-i", str(img),
                          "-filter_complex", "[0:v]scale=640:360,setsar=1,fps=30[v]",
                          "-map", "[v]"],
    "F_new_frac_2p5": ["-loop", "1", "-framerate", "1", "-t", "2.5", "-i", str(img),
                       "-filter_complex", "[0:v]scale=640:360,setsar=1,fps=30[v]", "-map", "[v]",
                       "-t", "2.5"],
}
print("图片 2 秒场景在不同参数形态下的输出（期望：2.0s / 30fps / 60 帧）")
for name, args in SHAPES.items():
    out = tmp / (name + ".mp4")
    r = subprocess.run([FF, "-y", "-v", "error", *args, "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        str(out)], capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    print("  {:<24} rc={} {}".format(name, r.returncode,
                                     probe(out) if out.is_file() else (r.stderr or "")[-120:]))

# 生产同形：两段（图片 + 纯色底）concat，总时长 5s
print("\n生产同形（图片 2s + 纯色 3s，fps=30，总 -t 5.0）")
for tag, fr in (("G_old", []), ("H_new", ["-framerate", "1"])):
    out = tmp / (tag + ".mp4")
    args = [*fr, "-loop", "1", "-t", "2.0", "-i", str(img),
            "-f", "lavfi", "-t", "3.0", "-i", "color=c=0x0b1226:size=640x360:rate=30",
            "-filter_complex",
            "[0:v]scale=640:360:force_original_aspect_ratio=increase,crop=640:360,setsar=1,fps=30[v0];"
            "[1:v]scale=640:360:force_original_aspect_ratio=increase,crop=640:360,setsar=1,fps=30[v1];"
            "[v0][v1]concat=n=2:v=1:a=0[vc];[vc]format=yuv420p[vout]",
            "-map", "[vout]", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-t", "5.0"]
    r = subprocess.run([FF, "-y", "-v", "error", *args, str(out)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    print("  {:<8} rc={} {}".format(tag, r.returncode,
                                    probe(out) if out.is_file() else (r.stderr or "")[-140:]))
print("\ntmp:", tmp)
