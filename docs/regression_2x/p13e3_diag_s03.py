# -*- coding: utf-8 -*-
"""诊断：成片逐景抽帧 vs 全部参考素材的相关矩阵（定位 S03 失败原因）。只读。"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core.materials import frame_corr, gray48      # noqa: E402

PID = sys.argv[1] if len(sys.argv) > 1 else "p_e4c65c1c58ed"
proj = R / "projects" / PID
art_dir = proj / "artifacts"

# 参考素材池 = retrieval 载荷候选 ∩ 真实存在文件
retr = None
for f in sorted(art_dir.glob("*.json")):
    j = json.loads(f.read_text(encoding="utf-8"))
    if isinstance(j, dict) and j.get("candidates") and j.get("material_mode"):
        retr = j
if retr is None:
    print("找不到 retrieval 载荷")
    sys.exit(1)

media = proj / "media"
refs = {}
for c in retr["candidates"]:
    rel = str(c.get("path") or "")
    p = media / rel
    if p.is_file() and p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
        refs[p.name] = p

print("参考素材（真实存在，可与画面比对）:")
for k, v in refs.items():
    print("   ", k, v.stat().st_size, "B")

grays = {}
for k, v in refs.items():
    try:
        grays[k] = gray48(v)
    except Exception as exc:                                                # noqa: BLE001
        print("   !! gray48 失败", k, exc)

frames = sorted(art_dir.glob("_frame_S*.png"))
print()
print("成片抽帧:", len(frames))
for fp in frames:
    g = gray48(fp)
    scores = sorted(((round(float(frame_corr(g, ref)), 3), name)
                     for name, ref in grays.items()), reverse=True)
    print("  {} -> {}".format(fp.name, scores[:3]))

# ---------------- 引擎实际选材（MATERIAL_TIMELINE 事件）----------------
import sqlite3                                                          # noqa: E402
con = sqlite3.connect("file:" + (R / "projects" / "video_studio.db").as_posix() + "?mode=ro",
                      uri=True)
con.row_factory = sqlite3.Row
print()
print("=== 引擎选材决策 ===")
for r in con.execute("select payload from events where project_id=? and type='MATERIAL_TIMELINE'",
                     (PID,)):
    j = json.loads(r["payload"])
    for d in j.get("decisions") or []:
        if d.get("scene_id") not in ("S03", "S04"):
            continue
        sa = d.get("selected_asset") or {}
        print("  {} | state={} | class={} | asset={} | score={} | {}x{}".format(
            d.get("scene_id"), d.get("fallback_state"), d.get("insufficiency_class"),
            (sa.get("asset_id") or "-"), sa.get("retrieval_match_score"),
            sa.get("width"), sa.get("height")))
        print("      name:", str(sa.get("name"))[:90])
        print("      path:", sa.get("path"))
con.close()

# ---------------- 复现生产滤镜链：素材 → 静态全幅 / S03 缩放后 ----------------
print()
print("=== 复现生产链：素材经 scale/crop 后与成片的 corr ===")
import subprocess                                                       # noqa: E402
FF = str(R / "bin" / "ffmpeg.exe")
work = proj / "render" / "diag"
work.mkdir(parents=True, exist_ok=True)

src = None
for name, p in grays.items():
    if name.startswith("Four color"):
        src = refs[name]
print("S03 期望素材文件:", src.name if src else None)

if src is not None:
    # 静态全幅（=关闭运动时的模板）
    out_static = work / "s03_static.png"
    vf_static = ("scale=1920:1080:force_original_aspect_ratio=increase,"
                 "crop=1920:1080,setsar=1,fps=25")
    rc1 = subprocess.run([FF, "-v", "error", "-y", "-i", str(src), "-vf", vf_static,
                          "-frames:v", "1", str(out_static)],
                         capture_output=True, text=True)
    print("  static rc={} err={}".format(rc1.returncode, (rc1.stderr or "")[:200]))
    # 运动缩放后（zoom_end 1.0799 → 1778x1000，取 x/y 居中）
    out_zoom = work / "s03_zoom.png"
    vf_zoom = ("scale=2074:1167:force_original_aspect_ratio=increase,"
               "crop=1778:1000:148:84,setsar=1,fps=25")
    rc2 = subprocess.run([FF, "-v", "error", "-y", "-i", str(src), "-vf", vf_zoom,
                          "-frames:v", "1", str(out_zoom)],
                         capture_output=True, text=True)
    print("  zoom   rc={} err={}".format(rc2.returncode, (rc2.stderr or "")[:200]))
    frame = art_dir / "_frame_S03.png"
    for label, p in (("素材原图", src), ("静态全幅", out_static), ("运动缩放后", out_zoom)):
        if p.is_file():
            print("  corr(S03成片帧, {}): {}".format(
                label, round(float(frame_corr(gray48(frame), gray48(p))), 4)))
        else:
            print("  corr(S03成片帧, {}): 文件未生成".format(label))

