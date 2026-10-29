import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "output" / "production_002" / "build"
FFMPEG = str(ROOT / "bin" / "ffmpeg.exe")
scene_files = sorted(BUILD.glob("scene_*.mp4"), key=lambda p: p.name)
concat = BUILD / "concat_abs.txt"
concat.write_text("\n".join(f"file '{p.as_posix()}'" for p in scene_files), encoding="ascii")
final = ROOT / "output" / "production_002" / "JARVIS_final.mp4"
# 重编码拼接：规范化时间戳，避免 -c copy 的 pts 断裂
r = subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "concat", "-safe", "0", "-i", str(concat),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "25",
                    "-c:a", "aac", str(final)])
print("re-encode concat rc:", r.returncode)
if final.exists():
    print("final size MB:", round(final.stat().st_size/1e6, 2))
