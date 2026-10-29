"""检查 wav 的内部停顿（≥0.25s，排除首尾）——用于判断参考段里是否含犹豫/卡顿。

用法：python scripts/check_internal_pauses.py --wav a.wav [--wav b.wav ...]
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.stdout.reconfigure(encoding="utf-8")
ap = argparse.ArgumentParser()
ap.add_argument("--wav", action="append", required=True)
ap.add_argument("--min", type=float, default=0.25)
a = ap.parse_args()

for w in a.wav:
    p = Path(w)
    if not p.exists():
        print("缺失:", p)
        continue
    d, sr = sf.read(str(p), dtype="float32", always_2d=True)
    m = d.mean(axis=1) if d.shape[1] > 1 else d[:, 0]
    hop = int(sr * 0.02)
    n = len(m) // hop
    fr = np.sqrt((m[:n * hop].reshape(n, hop) ** 2).mean(axis=1))
    sil = fr < 10 ** (-45 / 20)
    runs, i = [], 0
    while i < n:
        if sil[i]:
            j = i
            while j < n and sil[j]:
                j += 1
            if (j - i) * 0.02 >= a.min and i > 2 and j < n - 2:
                runs.append((i * 0.02, (j - i) * 0.02))
            i = j
        else:
            i += 1
    tot = sum(x[1] for x in runs)
    print("{:22s} {:5.2f}s | 内部停顿 {} 个（合计 {:.2f}s，占 {:.1%}）{}".format(
        p.name, len(m) / sr, len(runs), tot, tot / (len(m) / sr),
        ["{:.2f}s@{:.2f}".format(d, t) for t, d in runs]))
