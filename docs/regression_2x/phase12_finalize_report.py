# -*- coding: utf-8 -*-
"""Phase 12 收尾：填充报告 sha256 台账。"""
import hashlib
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
PRODUCED = {
    "__MOD__": "src/video_studio/core/asset_license_join.py",
    "__OPS__": "src/video_studio/ops/visual_binding.py",
    "__CLI__": "src/video_studio/cli.py",
    "__TEST__": "tests/asset_license_join_test.py",
    "__INV__": "docs/regression_2x/logs/phase12_license_sources.json",
    "__OV__": "docs/regression_2x/logs/license_overlay_v1.json",
    "__COV__": "docs/regression_2x/logs/phase12_coverage_after.json",
}
rep = R / "docs" / "regression_2x" / "PHASE12_REPORT.md"
txt = rep.read_text(encoding="utf-8")
for k, f in PRODUCED.items():
    h = hashlib.sha256((R / f).read_bytes()).hexdigest()
    txt = txt.replace(k, h)
    print("  {:10s} -> {}  {}".format(k, h[:16] + "…", f))
rep.write_text(txt, encoding="utf-8")
print("残留占位符:", [k for k in PRODUCED if k in rep.read_text(encoding="utf-8")])
