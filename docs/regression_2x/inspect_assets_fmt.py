"""Inspect the real format/size of cached asset files and stage copies for viewing."""
import shutil
import sys
from pathlib import Path

from PIL import Image

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
DIRS = [ROOT / "output/run03/asset_cache/files", ROOT / "output/run05/asset_cache/files"]
TMP = Path(r"C:\Users\DUALAN~1\AppData\Local\Temp\v161audit\assets")
TMP.mkdir(parents=True, exist_ok=True)

cands = []
for d in DIRS:
    if d.exists():
        cands += [p for p in d.glob("*.jpg")] + [p for p in d.glob("*.png")]
cands.sort(key=lambda p: -p.stat().st_size)
print("{:26s} {:>9s} {:>10s} {:>6s} {}".format("file", "bytes", "dim", "fmt", "mode"))
rows = []
for p in cands[:20]:
    try:
        with Image.open(p) as im:
            print("{:26s} {:9d} {:>10s} {:>6s} {}".format(
                p.name, p.stat().st_size, "{}x{}".format(*im.size), im.format, im.mode))
            rows.append((p, im.format, im.size))
    except Exception as e:  # noqa: BLE001
        print("{:26s} 打不开: {}".format(p.name, e))

print("\n已把前 8 个复制到 {}（按真实格式命名）".format(TMP))
for i, (p, fmt, size) in enumerate(rows[:8]):
    ext = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp", "GIF": ".gif"}.get(fmt, ".bin")
    dst = TMP / "cand{:02d}_{}{}".format(i + 1, p.stem, ext)
    shutil.copy2(p, dst)
    print("  {} <- {} ({})".format(dst.name, p.name, fmt))
