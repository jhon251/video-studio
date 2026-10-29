# -*- coding: utf-8 -*-
"""P26 §0 诊断：Phase 20 沙箱 artifacts 里的 `_frame_*.png` 到底是什么？"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")

fx = json.loads((R / "output/phase20_p20_2_sandbox/fixture.json").read_text(encoding="utf-8"))
pid = fx["sandbox_project_id"]
proj = R / "projects" / pid
print("沙箱:", pid)
print("binding 样本:", list((fx.get("binding") or {}).items())[:4])
frames = sorted((proj / "artifacts").glob("_frame_*.png"))
print("artifacts 内 _frame_*.png 数:", len(frames))
for p in frames[:8]:
    print("   ", p.name, p.stat().st_size)

con = sqlite3.connect("file:" + (R / "projects" / "video_studio.db").as_posix() + "?mode=ro",
                      uri=True)
con.row_factory = sqlite3.Row
print("\nevents:")
for r in con.execute("select type, count(*) as n from events where project_id=? group by type",
                     (pid,)):
    print("   ", r["type"], r["n"])
print("\nartifacts (db):")
for r in con.execute("select type, count(*) as n from artifacts where project_id=? group by type",
                     (pid,)):
    print("   ", r["type"], r["n"])
con.close()

# 该 frame 与哪个素材最像？
from video_studio.core.materials import frame_corr, gray48                      # noqa: E402
import hashlib
SRC = R / "projects" / "p_96efdc03e1aa"
POOL = {}
for d in (SRC / "media", SRC / "registered_materials", SRC / "acquired_materials"):
    if d.is_dir():
        for f in sorted(d.rglob("*")):
            if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
                POOL.setdefault(hashlib.sha256(f.read_bytes()).hexdigest(), f)
if frames:
    fp = frames[0]
    g = gray48(fp)
    scored = sorted(((round(float(frame_corr(g, gray48(p))), 4), p.name) for p in POOL.values()),
                    reverse=True)
    print("\n{} 最像的素材（全图口径）:".format(fp.name))
    for s, n in scored[:4]:
        print("   {:.4f}  {}".format(s, n[:64]))
    print("   ...最不像:", scored[-1])
