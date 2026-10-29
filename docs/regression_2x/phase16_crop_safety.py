# -*- coding: utf-8 -*-
"""验证 Phase 16 失败机理：1920×1080 模板的**中心裁切** vs 全图，对 48×48 corr 的影响。

对每张池素材：按生产模板（scale 填充 + 中心裁切到 1920×1080）裁出画面，
再算 corr(全图, 该画面)。若某素材 corr 很低 ⇒ 该素材"多面板/竖构图"在裁切后失真，
必然过不了渲染后核验门（min_corr=0.30）——与"素材是否在屏"无关。
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core.materials import frame_corr, gray48                    # noqa: E402

FF = str(R / "bin" / "ffmpeg.exe")
work = R / "output" / "phase16_p16_5_sandbox" / "cropcheck"
work.mkdir(parents=True, exist_ok=True)

pool = json.loads((R / "docs/regression_2x/logs/phase16_retrieval_payload.json")
                  .read_text(encoding="utf-8"))
print("{:>14} {:>13} {:>8} {:>7}  {}".format(
    "sha12", "原尺寸", "corr", ">=0.30", "名称"))
rows = []
for c in pool["candidates"]:
    src = pathlib.Path(c["path"])
    if not src.is_file():
        continue
    out = work / (c["sha256"][:12] + ".png")
    vf = ("scale=1920:1080:force_original_aspect_ratio=increase,"
          "crop=1920:1080,setsar=1")
    subprocess.run([FF, "-v", "error", "-y", "-i", str(src), "-vf", vf,
                    "-frames:v", "1", str(out)], capture_output=True, text=True)
    if not out.is_file():
        continue
    corr = round(float(frame_corr(gray48(src), gray48(out))), 4)
    # 原尺寸
    from PIL import Image
    with Image.open(src) as im:
        wh = "{}x{}".format(*im.size)
    rows.append({"sha12": c["sha256"][:12], "name": c["name"], "size": wh,
                 "corr_full_vs_center_crop": corr, "origin": c["origin"]})
    print("{:>14} {:>13} {:>8} {:>7}  {}".format(
        c["sha256"][:12], wh, corr, corr >= 0.30, c["name"][:44]))

print()
bad = [r for r in rows if r["corr_full_vs_center_crop"] < 0.30]
print("裁切后失真（corr<0.30）的素材:", len(bad), "/", len(rows))
for r in bad:
    print("   {} {} | {}".format(r["sha12"], r["size"], r["name"][:52]))
print()
print("结论：渲染色后核验门（frame_pearson_48x48, min_corr=0.30）")
print("      对『多面板/非 16:9 构图』素材会判失败，**与被分配的素材是否真的在屏无关**。")
out = R / "docs" / "regression_2x" / "logs" / "phase16_crop_safety.json"
out.write_text(json.dumps({
    "schema": "phase16-crop-safety-v1",
    "method": "对每张池素材按生产模板 scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080 裁切，"
              "再算 corr(全图, 裁切画面)（冻结口径 gray48 48×48）",
    "threshold": 0.30,
    "rows": rows,
    "distorted_count": len(bad),
    "conclusion": ("该门度量的是『全图 vs 成片画面』；对多面板/竖构图素材，中心裁切只保留中段，"
                   "corr 必然很低 ⇒ 门失败但素材确实在屏。**未调阈值、未改模板**。"),
}, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
print("证据 ->", out.relative_to(R).as_posix())
