import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "output" / "production_002" / "build"
FFMPEG = str(ROOT / "bin" / "ffmpeg.exe")
scenes = sorted(BUILD.glob("scene_*.mp4"), key=lambda p: p.name)

cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y"]
for p in scenes:
    cmd += ["-i", str(p)]
n = len(scenes)
fc = f"concat=n={n}:v=1:a=1[v][a]"
cmd += ["-filter_complex", fc, "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        "-ar", "22050", "-ac", "1", str(ROOT / "output" / "production_002" / "JARVIS_final.mp4")]
r = subprocess.run(cmd)
print("concat filter rc:", r.returncode)
