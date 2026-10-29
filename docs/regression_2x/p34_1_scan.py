# -*- coding: utf-8 -*-
"""P34-1 诊断：扫描成片中的**无画面**（纯色卡 + 持续近黑窗口）。

定义（依授权书 §0③）：
  · **纯色卡景**：素材决策为 `SOLID_COLOR_CARD`（无 selected_asset）⇒ 画面为纯色 `0x0b1226`；
  · **持续近黑窗口**：灰度 `mean < 30` 且持续 **> 3s**（1 fps 同源采样）。

输出：逐景/逐窗口证据（时间戳 + 灰度统计）落盘 `logs/p34_1_no_picture_scan.json`。
零 LLM、零 VLM、零网络。
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import numpy as np
from PIL import Image

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
PROBE = R / "output" / "p34_probe" / "frames"
FF = str(R / "bin" / "ffmpeg.exe")
FFPROBE = str(R / "bin" / "ffprobe.exe")
TAG = "phase33_p33_4_sandbox"
NEAR_BLACK = 30.0
MIN_DARK_S = 3.0
sys.stdout.reconfigure(encoding="utf-8")


def dur(p):
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(p)], capture_output=True, text=True)
    v = (r.stdout or "").strip().splitlines()
    return round(float(v[0]), 3) if v and v[0] else None


def main() -> int:
    fx = json.loads((R / "output" / TAG / "fixture.json").read_text(encoding="utf-8"))
    pid = fx["sandbox_project_id"]
    pdir = R / "projects" / pid / "output"
    film = next(f for f in sorted(pdir.glob("*.mp4")) if f.name.endswith("_with_outro_v2.mp4"))
    tb = json.loads((R / "output/phase33_voice/timebase_v41.json").read_text(encoding="utf-8"))
    dec = json.loads((R / "output" / TAG / "material_timeline.json")
                     .read_text(encoding="utf-8"))["decisions"]
    wins = {w["scene_id"]: w for w in tb["windows"]}
    total = dur(film)
    print("成片 {} ({:,}B) | {:.3f}s | 沙箱 {}".format(
        film.name, film.stat().st_size, total or 0, pid))

    # ---- ① 纯色卡景（来自素材决策）----
    cards = []
    for d in dec:
        a = d.get("selected_asset") or {}
        if not a.get("asset_id"):
            w = wins.get(d["scene_id"]) or {}
            cards.append({"scene_id": d["scene_id"],
                          "start_s": w.get("start_s"), "end_s": w.get("end_s"),
                          "window_s": w.get("window_s"),
                          "has_narration": True,          # 40 段均有旁白（脚本无空段）
                          "fallback_state": d.get("fallback_state"),
                          "insufficiency_class": d.get("insufficiency_class")})
    print()
    print("=== 纯色卡景（无素材）：{} 个 ===".format(len(cards)))
    for c in cards:
        print("      {} [{:.3f}, {:.3f}] {:.2f}s  {}".format(
            c["scene_id"], c["start_s"] or 0, c["end_s"] or 0, c["window_s"] or 0,
            c["insufficiency_class"]))

    # ---- ② 逐秒灰度扫描（1 fps，320x180）----
    PROBE.mkdir(parents=True, exist_ok=True)
    for f in PROBE.glob("f*.png"):
        f.unlink()
    subprocess.run([FF, "-v", "error", "-y", "-i", str(film), "-vf",
                    "fps=1,scale=320:180", str(PROBE / "f%05d.png")], check=True)
    frames = sorted(PROBE.glob("f*.png"))
    stats = []
    for i, fp in enumerate(frames):
        with Image.open(fp) as im:
            a = np.asarray(im.convert("L"), dtype=float)
        stats.append({"t_s": i, "mean": round(float(a.mean()), 2),
                      "std": round(float(a.std()), 2),
                      "uniq": int(len(np.unique(a.astype(np.uint8))))})
    dark = [s for s in stats if s["mean"] < NEAR_BLACK]
    # 连续近黑窗口
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
    dark_windows = [{"start_s": r[0]["t_s"], "end_s": r[-1]["t_s"] + 1,
                     "duration_s": len(r), "mean_avg": round(
                         sum(x["mean"] for x in r) / len(r), 2),
                     "uniq_avg": round(sum(x["uniq"] for x in r) / len(r), 1),
                     "over_3s": len(r) > MIN_DARK_S}
                    for r in runs]
    print()
    print("=== 灰度扫描（1fps）===")
    print("  抽帧 {} | 近黑(<{}) {} 秒（{:.1%}）| 连续近黑窗口 {} 段".format(
        len(stats), NEAR_BLACK, len(dark), len(dark) / max(len(stats), 1),
        len(dark_windows)))
    print("  其中 **>{}s** 的窗口（即授权书定义的持续近黑）:".format(MIN_DARK_S))
    for w in dark_windows:
        if w["over_3s"]:
            print("    [{:>6.1f}, {:>6.1f}) {:>5.1f}s mean={:<7} uniq={}".format(
                w["start_s"], w["end_s"], w["duration_s"], w["mean_avg"], w["uniq_avg"]))
    pure = [s for s in stats if s["uniq"] <= 4]
    print("  纯色帧（uniq<=4）: {} 秒 时间点 {}".format(
        len(pure), [s["t_s"] for s in pure][:12]))

    report = {
        "schema": "p34-1-no-picture-scan-v1",
        "film": str(film.relative_to(R)).replace("\\", "/"),
        "film_bytes": film.stat().st_size, "duration_s": total,
        "sandbox_project_id": pid,
        "definition": {"pure_color_card": "素材决策无 selected_asset ⇒ 纯色卡 0x0b1226",
                       "near_black": "mean < {} 且持续 > {}s".format(NEAR_BLACK, MIN_DARK_S)},
        "card_scenes": cards,
        "scan": {"frames": len(stats), "near_black_seconds": len(dark),
                 "near_black_ratio": round(len(dark) / max(len(stats), 1), 4),
                 "pure_color_seconds": len(pure),
                 "dark_windows": dark_windows,
                 "dark_windows_over_3s": [w for w in dark_windows if w["over_3s"]]},
        "zero_llm": True, "zero_vlm": True, "zero_network": True,
    }
    p = L / "p34_1_no_picture_scan.json"
    p.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print()
    print("-> " + p.relative_to(R).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
