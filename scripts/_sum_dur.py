import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "output" / "production_002" / "build"
FFMPEG = str(ROOT / "bin" / "ffmpeg.exe")
total = 0.0
for p in sorted(BUILD.glob("scene_*.mp4"), key=lambda x: x.name):
    r = subprocess.run([FFMPEG, "-i", str(p), "-hide_banner"], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):(\d+)\.(\d+)", r.stderr)
    if m:
        d = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) + int(m.group(4)) / 100
        total += d
        if d > 25:
            print(p.name, "=", round(d, 1), "s  <-- 异常长")
print("总时长 sum =", round(total, 1), "s =", round(total/60, 1), "min")
