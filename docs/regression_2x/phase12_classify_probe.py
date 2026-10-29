# -*- coding: utf-8 -*-
"""Phase 12 只读探针：classify_license 的真实行为表（不发明期望值）。"""
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core.materials import classify_license, license_gate_applies  # noqa: E402

for t in ("Public domain", "PD-US", "PD", "CC0", "CC BY 4.0", "CC BY-SA 4.0", "CC BY-NC 4.0",
          "CC BY-NC-SA 4.0", "All rights reserved", "unchecked", "UNKNOWN", None, ""):
    print("  {!r:24s} -> {}".format(t, classify_license(t)))
print("  gate:", license_gate_applies({"license": "CC BY 4.0", "license_class": "FREE_ATTRIBUTION"},
                                     require_license=True))
