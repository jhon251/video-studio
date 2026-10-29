# -*- coding: utf-8 -*-
"""Phase 51 / P51-1：**ASS cue 重叠扫描器**。

对**最终烧录的 ASS** 以 0.1s 步进扫描，统计**同时活跃 cue 数**：
  · `max_concurrent`：全片同时活跃的最大条数；
  · `overlap_moments`：同时活跃 >1 的采样时刻数；
  · 并给出**最长重叠区间**与前若干重叠样例（便于定位）。

用法：`python -c "..."` 或直接跑本文件（默认扫 F7.1 的 ASS）。
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
STEP = 0.1
TOL = 0.1


def parse_ass(path: pathlib.Path):
    """解析 ASS 的 Dialogue 行，返回 [(start_s, end_s, text), ...]（按 start 排序）。"""
    out = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.startswith("Dialogue:"):
            continue
        parts = line.split(",", 9)
        if len(parts) < 10:
            continue
        try:
            h1, m1, s1 = parts[1].strip().split(":")
            h2, m2, s2 = parts[2].strip().split(":")
            st = int(h1) * 3600 + int(m1) * 60 + float(s1)
            en = int(h2) * 3600 + int(m2) * 60 + float(s2)
        except ValueError:
            continue
        out.append((round(st, 3), round(en, 3), parts[9].strip()[:24]))
    return sorted(out)


def scan(cues, step: float = STEP):
    """0.1s 步进扫描同时在屏条数（用区间判定的精确法 + 步进取样）。"""
    if not cues:
        return {"cues": 0, "max_concurrent": 0, "overlap_moments": 0,
                "samples": 0, "longest_overlap_s": 0.0, "examples": []}
    t_end = max(c[1] for c in cues)
    samples = int(t_end / step) + 1
    worst, moments, run_start, longest, examples = 0, 0, None, 0.0, []
    for i in range(samples):
        t = round(i * step, 3)
        active = [c for c in cues if c[0] - 1e-9 <= t < c[1] - 1e-9]
        n = len(active)
        if n > worst:
            worst = n
        if n > 1:
            moments += 1
            if run_start is None:
                run_start = t
            if len(examples) < 5:
                examples.append({"t": t, "concurrent": n,
                                 "texts": [a[2] for a in active[:3]]})
        else:
            if run_start is not None:
                longest = max(longest, t - run_start)
                run_start = None
    if run_start is not None:
        longest = max(longest, t_end - run_start)
    return {"cues": len(cues), "max_concurrent": worst,
            "overlap_moments": moments, "samples": samples,
            "longest_overlap_s": round(longest, 3), "examples": examples}


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--ass", required=True)
    a = ap.parse_args()
    p = pathlib.Path(a.ass)
    cues = parse_ass(p)
    res = scan(cues)
    res["ass"] = str(p)
    res["step_s"] = STEP
    print(json.dumps(res, ensure_ascii=False, indent=1)[:1400])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
