"""JARVIS 成片构建 · 步骤3：ffmpeg 渲染 44 镜 + 拼接成片（cwd=build，相对路径）。"""
import json
import shutil
import struct
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "output" / "production_002" / "build"
FFMPEG = str(ROOT / "bin" / "ffmpeg.exe")
FONT = BUILD / "msyh.ttc"
if not FONT.exists():
    shutil.copy(r"C:\Windows\Fonts\msyh.ttc", FONT)


def wav_duration(path: Path) -> float:
    b = path.read_bytes()
    if len(b) < 44:
        return 5.0
    pos = b.find(b"data", 12, 100)
    if pos < 0:
        return 5.0
    data_size = struct.unpack("<I", b[pos + 4:pos + 8])[0]
    byte_rate = struct.unpack("<I", b[28:32])[0]
    return round(data_size / byte_rate, 2) if byte_rate else 5.0


manifest = json.loads((BUILD / "manifest.json").read_text(encoding="utf-8"))
logf = open(BUILD / "ffmpeg.log", "w", encoding="utf-8")
scene_files = []
ok = 0
for m in manifest:
    sid = m["scene_id"]
    beat = m["beat"].replace("'", "")
    txt = m["txt"].replace("\\", "/")          # 相对 build 的 textfile
    wav = BUILD / "wav" / f"{sid}.wav"
    mp4 = f"scene_{sid}.mp4"
    if wav.exists():
        dur = wav_duration(wav) + 0.6
        audio_in = [f"wav/{sid}.wav"]
    else:
        dh = m["duration_hint"].replace("s", "")
        dur = float(dh) if dh else 6.0
        audio_in = []
    dur = round(dur, 2)
    vf = (f"drawtext=fontfile=msyh.ttc:text='{beat}':fontsize=38:fontcolor=0x9aa5b1:"
          f"x=(w-text_w)/2:y=56,"
          f"drawtext=fontfile=msyh.ttc:textfile={txt}:fontsize=32:fontcolor=white:"
          f"x=(w-text_w)/2:y=(h-text_h)/2:line_spacing=16")
    cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
           "-f", "lavfi", "-i", f"color=c={m['bg']}:s=1280x720:r=25:d={dur}"]
    if audio_in:
        cmd += ["-i", audio_in[0]]
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
    cmd += ["-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest", mp4]
    r = subprocess.run(cmd, cwd=str(BUILD), stdout=logf, stderr=subprocess.STDOUT)
    if r.returncode == 0 and (BUILD / mp4).exists():
        scene_files.append(mp4)
        ok += 1
        print(f"render {sid} dur={dur}s OK")
    else:
        print(f"render {sid} FAILED")

# 拼接
concat = BUILD / "concat.txt"
concat.write_text("\n".join(f"file '{f}'" for f in scene_files), encoding="ascii")
final = ROOT / "output" / "production_002" / "JARVIS_final.mp4"
r = subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-f", "concat",
                    "-safe", "0", "-i", str(concat), "-c", "copy", str(final)],
                   stdout=logf, stderr=subprocess.STDOUT)
logf.close()
if r.returncode == 0 and final.exists():
    print(f"FINAL OK: {final} ({round(final.stat().st_size/1e6,2)} MB) | scenes {ok}/{len(manifest)}")
else:
    print(f"FINAL FAILED | scenes {ok}/{len(manifest)}")
