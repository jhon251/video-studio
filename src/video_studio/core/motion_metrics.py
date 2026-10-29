# -*- coding: utf-8 -*-
"""P24-1 冻结占比度量（**逐秒差分法**，确定性）。

方法（授权书口径）：按 1 fps 抽帧 → 缩放到 160×90 灰度 → 计算相邻抽帧的
平均绝对差（MAD）。`MAD < threshold` ⇒ 该秒判为**冻结**。据此算：
  · 冻结占比 = 冻结秒数 / 总秒数
  · 最长连续静止 = 连续冻结秒的最长长度
  · 开场 90s 内画面变化次数 = 前 90s 内 `MAD >= threshold` 的相邻对数

**为什么不用 freezedetect**：实测在 H.264 CRF20 下，`freezedetect` 因**编码噪声抖动**
对真实冻结画面也报 0%（见 `logs/phase24_p24_1_probe.json`），
故它是"噪声阈值"度量而非**内容运动**度量。逐秒差分法直接量测内容变化，更贴合
"观众看到的画面是否在动"。
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

import numpy as np
from PIL import Image

#: 抽帧分辨率（P25-1 起为 **320×180**：授权书按「1.25 幅度 ⇒ 480px 推进 ⇒ 40 探针 px」推导，
#: 该推导隐含 320px 宽的探针；小图对亚像素运动更敏感，且确定性）
PROBE_W, PROBE_H = 320, 180
#: MAD 阈值（0-255 灰度平均绝对差）：< 阈值 ⇒ 判为冻结。运行前写死。
MAD_THRESHOLD = 0.05
#: 三指标阈值（运行前写死）
FREEZE_RATIO_MAX = 0.50
MAX_STATIC_S = 25.0
OPENING_WINDOW_S = 90.0
OPENING_CHANGES_MIN = 3


def sample_frames(film: str, ffmpeg: str, fps: float = 1.0,
                  workdir: str | pathlib.Path | None = None) -> list[pathlib.Path]:
    """按 fps 抽帧到指定目录（确定性文件名 p%05d.png），返回按序路径。"""
    wd = pathlib.Path(workdir or pathlib.Path(film).parent / "_p24_probe")
    wd.mkdir(parents=True, exist_ok=True)
    for old in wd.glob("p*.png"):
        old.unlink()
    vf = "fps={},scale={}:{}".format(fps, PROBE_W, PROBE_H)
    r = subprocess.run([ffmpeg, "-v", "error", "-y", "-i", str(film), "-vf", vf,
                        str(wd / "p%05d.png")], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError("抽帧失败: {}".format((r.stderr or "")[:200]))
    return sorted(wd.glob("p*.png"))


def _gray(p: pathlib.Path) -> np.ndarray:
    with Image.open(p) as im:
        return np.asarray(im.convert("L"), dtype=np.float64)


def mad_series(frames: list[pathlib.Path]) -> list[float]:
    """相邻抽帧的 MAD 序列（长度 = len(frames)−1；第 i 项 = 第 i→i+1 秒的变化）。"""
    out = []
    prev = None
    for p in frames:
        g = _gray(p)
        if prev is not None:
            out.append(round(float(np.mean(np.abs(g - prev))), 6))
        prev = g
    return out


def measure_motion(film: str, ffmpeg: str, *,
                   mad_threshold: float = MAD_THRESHOLD,
                   fps: float = 1.0,
                   workdir: str | pathlib.Path | None = None) -> dict:
    """逐秒差分的三项指标 + 明细（确定性）。"""
    frames = sample_frames(film, ffmpeg, fps=fps, workdir=workdir)
    mads = mad_series(frames)
    n = len(mads)
    frozen = [i for i, m in enumerate(mads) if m < mad_threshold]
    moving = [i for i, m in enumerate(mads) if m >= mad_threshold]
    # 最长连续冻结（以秒计的相邻索引连续段）
    longest, cur = 0, 0
    for i in range(n):
        if mads[i] < mad_threshold:
            cur += 1
            longest = max(longest, cur)
        else:
            cur = 0
    win = int(OPENING_WINDOW_S * fps)
    opening = [i for i in moving if i < win]
    tot = n if n else 1
    return {
        "method": "per_second_mad-v1",
        "probe_w": PROBE_W, "probe_h": PROBE_H, "fps": fps,
        "mad_threshold": mad_threshold,
        "frames_sampled": len(frames), "intervals": n,
        "freeze_ratio": round(len(frozen) / tot, 4),
        "frozen_seconds": len(frozen),
        "longest_static_s": float(longest),
        "opening_window_s": OPENING_WINDOW_S,
        "opening_changes": len(opening),
        "mad_min": round(min(mads), 6) if mads else None,
        "mad_max": round(max(mads), 6) if mads else None,
        "mad_median": round(float(np.median(mads)), 6) if mads else None,
        "mad_mean": round(float(np.mean(mads)), 6) if mads else None,
        "thresholds": {"freeze_ratio_max": FREEZE_RATIO_MAX,
                       "max_static_s": MAX_STATIC_S,
                       "opening_changes_min": OPENING_CHANGES_MIN},
        "pass": {"freeze_ratio": None, "longest_static": None, "opening_changes": None},
    }


def evaluate(film: str, ffmpeg: str, **kw) -> dict:
    """量测并判定三指标（运行前写死的阈值）。"""
    r = measure_motion(film, ffmpeg, **kw)
    r["pass"] = {
        "freeze_ratio": bool(r["freeze_ratio"] < FREEZE_RATIO_MAX),
        "longest_static": bool(r["longest_static_s"] < MAX_STATIC_S),
        "opening_changes": bool(r["opening_changes"] >= OPENING_CHANGES_MIN),
    }
    r["all_pass"] = all(r["pass"].values())
    return r


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    R = pathlib.Path(r"C:\mp4agent\video-studio")
    ff = str(R / "bin" / "ffmpeg.exe")
    for f in sys.argv[1:]:
        print("=" * 78)
        print(f)
        r = evaluate(f, ff)
        print("  抽帧 {} 张 | 间隔 {} | MAD: min {} med {} max {}".format(
            r["frames_sampled"], r["intervals"], r["mad_min"], r["mad_median"], r["mad_max"]))
        print("  冻结占比 {:.1%}（<{:.0%}? {}）| 最长静止 {:.1f}s（<{:.0f}s? {}）| "
              "开场 90s 变化 {} 次（>={}? {}）".format(
                  r["freeze_ratio"], FREEZE_RATIO_MAX, r["pass"]["freeze_ratio"],
                  r["longest_static_s"], MAX_STATIC_S, r["pass"]["longest_static"],
                  r["opening_changes"], OPENING_CHANGES_MIN, r["pass"]["opening_changes"]))
        print("  三指标全过:", r["all_pass"])
