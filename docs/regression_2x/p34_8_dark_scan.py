# -*- coding: utf-8 -*-
"""P34-1 复核：新成片的近黑窗口明细（含 std/uniq，区分"内容性暗场"与"无画面"）。"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import numpy as np
from PIL import Image

R = pathlib.Path(r"C:\mp4agent\video-studio")
FF = str(R / "bin" / "ffmpeg.exe")
SB = R / "output" / "phase34_p34_4_sandbox"
PROBE = R / "output" / "p34_probe" / "scan42"
sys.stdout.reconfigure(encoding="utf-8")
NEAR_BLACK = 30.0


def main() -> int:
    fx = json.loads((SB / "fixture.json").read_text(encoding="utf-8"))
    pid = fx["sandbox_project_id"]
    pdir = R / "projects" / pid / "output"
    film = next(f for f in sorted(pdir.glob("*.mp4")) if f.name.endswith("_with_outro_v2.mp4"))
    tb = json.loads((R / "output/phase34_voice/timebase_v42.json").read_text(encoding="utf-8"))
    wins = {w["scene_id"]: (w["start_s"], w["end_s"]) for w in tb["windows"]}
    dec = json.loads((SB / "material_timeline.json").read_text(encoding="utf-8"))["decisions"]
    PROBE.mkdir(parents=True, exist_ok=True)
    for f in PROBE.glob("s*.png"):
        f.unlink()
    subprocess.run([FF, "-v", "error", "-y", "-i", str(film), "-vf", "fps=1,scale=320:180",
                    str(PROBE / "s%05d.png")], check=True)
    frames = sorted(PROBE.glob("s*.png"))
    stats = []
    for i, fp in enumerate(frames):
        with Image.open(fp) as im:
            a = np.asarray(im.convert("L"), dtype=float)
        stats.append({"t": i, "mean": round(float(a.mean()), 2),
                      "std": round(float(a.std()), 2),
                      "uniq": int(len(np.unique(a.astype(np.uint8))))})
    runs, cur = [], []
    for s in stats:
        if s["mean"] < NEAR_BLACK:
            cur.append(s)
        else:
            if cur:
                runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    print("成片 {} | 抽帧 {} | 近黑 {}s".format(film.name, len(stats),
                                               len([s for s in stats if s['mean'] < NEAR_BLACK])))
    print()
    print("{:<16} {:>6} {:>8} {:>9} {:>7} {:>6} {}".format(
        "窗口", "时长", "mean", "std", "uniq", ">3s", "覆盖景"))
    for r in runs:
        if len(r) <= 1:
            continue
        a, b = r[0]["t"], r[-1]["t"] + 1
        cover = [sid for sid, (s0, s1) in wins.items() if not (s1 <= a or s0 >= b)]
        print("[{:>5},{:>5}) {:>6}s {:>8.2f} {:>9.2f} {:>7.1f} {:>6} {}".format(
            a, b, len(r),
            sum(x["mean"] for x in r) / len(r),
            sum(x["std"] for x in r) / len(r),
            sum(x["uniq"] for x in r) / len(r),
            "Y" if len(r) > 3 else "",
            ",".join(cover[:4])))
    print()
    # 判定：有内容（std>5 或 uniq>32）⇒ 内容性暗场；否则疑似无画面
    print("=== 判定 ===")
    for r in runs:
        if len(r) <= 1:
            continue
        a, b = r[0]["t"], r[-1]["t"] + 1
        std = sum(x["std"] for x in r) / len(r)
        uniq = sum(x["uniq"] for x in r) / len(r)
        verdict = "内容性暗场（有内容）" if (std > 5 or uniq > 32) else "**疑似无画面**"
        print("  [{}, {}) {:.1f}s std={:.1f} uniq={:.0f} -> {}".format(
            a, b, len(r), std, uniq, verdict))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
