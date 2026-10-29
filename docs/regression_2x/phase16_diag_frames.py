# -*- coding: utf-8 -*-
"""Phase 16 渲染后核验失败逐景诊断：成片抽帧 vs 全部 12 张池素材的相关矩阵。"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core.materials import frame_corr, gray48                    # noqa: E402

fix = json.loads((R / "output/phase16_p16_5_sandbox/fixture.json").read_text(encoding="utf-8"))
pid = fix["sandbox_project_id"]
proj = R / "projects" / pid
con = sqlite3.connect("file:" + (R / "projects" / "video_studio.db").as_posix() + "?mode=ro",
                      uri=True)
con.row_factory = sqlite3.Row
print("sandbox:", pid)
for r in con.execute("select task_id, status, error from tasks where project_id=? "
                     "and agent_role='editing'", (pid,)):
    print("task:", r["task_id"], "status:", r["status"])
    print("error:", str(r["error"])[:2000])
    print()

# 池素材灰度
pool = json.loads((R / "docs/regression_2x/logs/phase16_retrieval_payload.json")
                  .read_text(encoding="utf-8"))
refs = {}
for c in pool["candidates"]:
    p = pathlib.Path(c["path"])
    if p.is_file():
        refs[pathlib.Path(c["path"]).name] = p
print("池素材:", len(refs))

# 选材（MATERIAL_TIMELINE）
sel = {}
for r in con.execute("select payload from events where project_id=? and type='MATERIAL_TIMELINE'",
                     (pid,)):
    j = json.loads(r["payload"])
    for d in j.get("decisions") or []:
        sa = d.get("selected_asset") or {}
        sel[d["scene_id"]] = {"asset_id": sa.get("asset_id"), "name": sa.get("name"),
                              "path": sa.get("path")}
con.close()

frames = sorted((proj / "artifacts").glob("_frame_S*.png"))
print("成片抽帧:", len(frames))
print()
# 关注场景的分配明细（含素材路径/尺寸）
WA = ("S02", "S06", "S07", "S08", "S13", "S12", "S17", "S20")
from PIL import Image                                                          # noqa: E402
print("关注场景的引擎分配:")
for sid in WA:
    s = sel.get(sid) or {}
    p = pathlib.Path(s.get("path") or "")
    wh = ""
    if p.is_file():
        with Image.open(p) as im:
            wh = "{}x{}".format(*im.size)
    print("  {} asset={} {} {}".format(sid, s.get("asset_id"), wh,
                                       str(s.get("name"))[:44]))
print()
print("{:>4} {:>26} {:>7} {:>7}  其它候选前三".format(
    "景", "引擎分配素材", "corr", ">=0.30"))
bad = []
for fp in frames:
    sid = fp.stem.replace("_frame_", "")
    s = sel.get(sid) or {}
    g = gray48(fp)
    scores = sorted(((round(float(frame_corr(g, gray48(p))), 3), n)
                     for n, p in refs.items()), reverse=True)
    want = None
    for sc, n in scores:
        if n == s.get("name"):
            want = sc
            break
    ok = (want is not None and want >= 0.30)
    if not ok:
        bad.append((sid, want, scores[:3]))
    print("{:>4} {:>26} {:>7} {:>7}  {}".format(
        sid, str(s.get("name"))[:26], want, ok,
        ", ".join("{}({})".format(n[:16], sc) for sc, n in scores[:3])))
print()
print("不达标景:", [b[0] for b in bad])
