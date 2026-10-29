"""打印 2-E 基线与当前代码的 _license_flags 函数体，逐字对比。"""
import sys
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
ZIP = ROOT / "docs" / "regression_2x" / "baseline" / "3.x-phase2e-baseline.zip"
REL = "src/video_studio/tools/material_provider.py"


def body(text: str, start_marker: str, lines: int = 16) -> str:
    i = text.find(start_marker)
    if i < 0:
        return "(not found)"
    return "\n".join(text[i:].splitlines()[:lines])


with zipfile.ZipFile(ZIP) as z:
    base = z.read(REL).decode("utf-8")
cur = (ROOT / REL).read_text(encoding="utf-8")

print("============ 2-E baseline _license_flags")
print(body(base, "def _license_flags"))
print("\n============ current _license_flags")
print(body(cur, "def _license_flags"))
print("\n============ 2-E baseline provider gate (LocalIngestProvider)")
i = base.find('if self.policy["license_required"]')
print("\n".join(base[i - 120:i + 260].splitlines()))
