# -*- coding: utf-8 -*-
"""用**冻结指标**（48×48 灰度 Pearson，min_corr 0.30 / margin 0.15）在**独立采样点**复测 H5 输出。"""
import hashlib
import json
import pathlib
import subprocess
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import materials as core_materials             # noqa: E402
from video_studio.ops import execution as OPX                         # noqa: E402

FF = str(R / "bin/ffmpeg.exe")
SB1 = R / "output/phase6g_exec_h5/20260929_150733"
SB2 = R / "output/phase6g_exec_h5/20260929_150838"
a1 = SB1 / "out/H5_rp-0ebebb71f99c.mp4"
a2 = SB2 / "out/H5_rp-0ebebb71f99c.mp4"
sha = lambda p: hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
print("attempt-1 sha:", sha(a1))
print("attempt-2 sha:", sha(a2), "| byte-identical:", sha(a1) == sha(a2))
WIN = {"S05": [181.776, 221.862], "S11": [487.572, 539.346]}
ASSET = {"S05": str(pathlib.Path(r"C:\mp4agent\h5_asset_candidates\S05\Russell_PM_1+1=2.png")),
         "S11": str(pathlib.Path(r"C:\mp4agent\h5_asset_candidates\S11\research"
                                 r"\S11-D0_LIPIcs-ITP-2023-24_p08_tactic-state-rw.png"))}
OLD = {"S05": None, "S11": None}
PKG = json.loads((R / "docs/regression_2x/logs/phase6g_exec_h4.json").read_text(encoding="utf-8")) \
    if (R / "docs/regression_2x/logs/phase6g_exec_h4.json").is_file() else None
gp = core_materials.DEFAULT_POLICY
print("frozen policy: min_corr={} margin={}".format(gp["frame_match_min_corr"],
                                                    gp["frame_argmax_margin"]))
work = SB2 / "work" / "independent"
work.mkdir(parents=True, exist_ok=True)
res = {}
for s, (w0, w1) in WIN.items():
    rows = []
    for i, frac in enumerate((0.12, 0.5, 0.88), start=1):
        t = w0 + (w1 - w0) * frac
        png = work / "ind_{}_{}.png".format(s, i)
        subprocess.run([FF, "-y", "-v", "error", "-ss", "{:.3f}".format(t), "-i", str(a2),
                        "-frames:v", "1", str(png)], capture_output=True)
        pair = OPX._frame_corr_pair(png, ASSET[s], OLD[s])
        pair["t_s"] = round(t, 3)
        rows.append(pair)
    new_mean = round(sum(r["vs_new"] for r in rows) / len(rows), 4)
    prev_vals = [r["vs_prev"] for r in rows if r.get("vs_prev") is not None]
    prev_mean = round(sum(prev_vals) / len(prev_vals), 4) if prev_vals else None
    res[s] = {"samples": rows, "corr_new_mean": new_mean, "corr_prev_mean": prev_mean,
              "frozen_min_corr": gp["frame_match_min_corr"],
              "frozen_margin": gp["frame_argmax_margin"],
              "passes_frozen_metric": bool(new_mean >= gp["frame_match_min_corr"]
                                           and (prev_mean is None
                                                or new_mean - prev_mean >= gp["frame_argmax_margin"]))}
    print(s, "corr_new_mean", new_mean, "| corr_prev_mean", prev_mean,
          "| passes frozen metric:", res[s]["passes_frozen_metric"])
    print("   samples:", json.dumps(rows, ensure_ascii=False))
print()
# 身份变化：窗内 H5 vs pre-H5（E5 产物）帧差
e5 = R / "output/phase6g_exec_e4_e5/20260929_133616/out/E5_rp-c80345481716.mp4"
from PIL import Image                                                     # noqa: E402
import numpy as np                                                        # noqa: E402


def g(p, size=(256, 144)):
    return np.asarray(Image.open(p).convert("L").resize(size), dtype=np.float32) / 255.0


for s, (w0, w1) in WIN.items():
    t = (w0 + w1) / 2
    f1, f2 = work / "d1.png", work / "d2.png"
    for f, src in ((f1, a2), (f2, e5)):
        subprocess.run([FF, "-y", "-v", "error", "-ss", "{:.3f}".format(t), "-i", str(src),
                        "-frames:v", "1", str(f)], capture_output=True)
    d = float(abs(g(f1) - g(f2)).mean())
    print("{} 窗内 H5 vs pre-H5 帧差 = {:.4f}（>0.05 ⇒ 画面确实改变）".format(s, round(d, 4)))
work_out = SB2 / "work" / "independent_measure.json"
work_out.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print("measure ->", work_out)
