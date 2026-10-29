import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "output" / "production_002" / "build"
FFMPEG = str(ROOT / "bin" / "ffmpeg.exe")
scenes = sorted(BUILD.glob("scene_*.mp4"), key=lambda p: p.name)

# 逐段累加拼接，定位从哪一镜开始"跳变"
def concat_measure(subset, out):
    lst = BUILD / f"_tmp_{out}.txt"
    lst.write_text("\n".join(f"file '{p.as_posix()}'" for p in subset), encoding="ascii")
    outp = BUILD / f"_tmp_{out}.mp4"
    subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(outp)])
    r = subprocess.run([FFMPEG, "-i", str(outp), "-hide_banner"], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):(\d+)\.(\d+)", r.stderr)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) + int(m.group(4)) / 100 if m else -1

# 每镜的 start/duration 检查
for p in scenes[:8] + scenes[-4:]:
    r = subprocess.run([FFMPEG, "-i", str(p), "-hide_banner"], capture_output=True, text=True)
    d = re.search(r"Duration: (\d+):(\d+):(\d+)\.(\d+)", r.stderr)
    st = re.search(r"start: (\d+\.\d+)", r.stderr)
    print(p.name, "dur", d.group(0)[9:] if d else "?", "start", st.group(1) if st else "?")

# 二分：前 22 / 后 22
first22 = concat_measure(scenes[:22], "first22")
last22 = concat_measure(scenes[22:], "last22")
print("前22镜拼接:", first22, "s | 后22镜拼接:", last22, "s")
