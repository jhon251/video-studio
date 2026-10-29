import subprocess
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "output" / "production_002" / "build"
FFPROBE = str(ROOT / "bin" / "ffprobe.exe")
wav = BUILD / "wav" / "S01.wav"

b = wav.read_bytes()
print("size:", len(b), "| head:", b[:12])
print("fmt:", b[12:16], "| audio_fmt:", struct.unpack("<H", b[20:22])[0],
      "| ch:", struct.unpack("<H", b[22:24])[0],
      "| rate:", struct.unpack("<I", b[24:28])[0],
      "| byte_rate:", struct.unpack("<I", b[28:32])[0],
      "| bits:", struct.unpack("<H", b[34:36])[0],
      "| data@40:", struct.unpack("<I", b[40:44])[0])
r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                    "-of", "csv=p=0", str(wav)], capture_output=True, text=True)
print("ffprobe rc:", r.returncode, "| out:", repr(r.stdout), "| err:", repr(r.stderr[:200]))
