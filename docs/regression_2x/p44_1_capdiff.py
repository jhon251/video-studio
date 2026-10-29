# -*- coding: utf-8 -*-
"""Phase 43 诊断：字幕 C3a/C3c/C8 失败是**我引入的**还是**既有**的？

做法：从 5.x 基线 ZIP 取出**原始** `core/captions.py`，在临时目录里以**同一份测试输入**
跑两类实现并对比。
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
import tempfile
import zipfile

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
ZIP = R / "docs/regression_2x/baseline/5.x-post-final-maintenance-baseline.zip"
REL = "src/video_studio/core/captions.py"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main() -> int:
    with zipfile.ZipFile(ZIP) as z:
        names = [n for n in z.namelist() if n.replace("\\", "/").endswith(REL)]
        raw = z.read(names[0]) if names else None
    if not raw:
        print("基线 ZIP 内未找到", REL)
        return 1
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="cap_base_"))
    bp = tmp / "captions_base.py"
    bp.write_bytes(raw)
    base = load("cap_base", bp)
    new = load("cap_new", R / REL)

    segs = [{"narration": "第一句话在这里。第二句话也跟着来了。第三句收尾一下。",
             "duration_s": 40.0},
            {"narration": "这是第二段的旁白内容。", "duration_s": 12.0}]
    for tag, mod in (("基线", base), ("当前", new)):
        cc = mod.build_cues(segs)
        mono = all(cc[i]["end"] <= cc[i + 1]["start"] + 1e-6 for i in range(len(cc) - 1))
        pos = all(c["dur"] > 0 for c in cc)
        mx = max(c["dur"] for c in cc)
        seg0 = [c for c in cc if c["segment_index"] == 0]
        print("{}: 条数 {} | mono={} pos={} max_dur={:.2f} | seg0 首起={:.2f} 末终={:.2f}".format(
            tag, len(cc), mono, pos, mx, seg0[0]["start"], seg0[-1]["end"]))
    # 逐条对比
    a, b = base.build_cues(segs), new.build_cues(segs)
    diff = [(x["index"], x["start"], x["end"], y["start"], y["end"])
            for x, y in zip(a, b) if (x["start"], x["end"]) != (y["start"], y["end"])]
    print()
    print("与基线逐条时间差异: {} 条".format(len(diff)))
    for d in diff[:6]:
        print("   idx {} 基线({},{}) 当前({},{})".format(*d))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
