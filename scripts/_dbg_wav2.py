import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "output" / "production_002" / "build"
wav = BUILD / "wav" / "S01.wav"
b = wav.read_bytes()
# 找 "data" chunk 位置
idx = b.find(b"data", 0, 200)
print("data chunk at offset:", idx)
print("first 48 bytes hex:", b[:48].hex())
print("--- ffprobe version ---")
FFPROBE = str(ROOT / "bin" / "ffprobe.exe")
r = subprocess.run([FFPROBE, "-version"], capture_output=True, text=True)
print("rc", r.returncode, "| out head:", repr(r.stdout[:120]), "| err:", repr(r.stderr[:120]))
