"""A/B 客观指标对比：时长、语速、内部停顿、频谱重心、高频占比、"口吃"迹象。

用法：python scripts/ab_metrics.py --dirs d1 d2 d3 --labels L1 L2 L3
每个目录需含 tts_index_clone.json（或直接用目录内 wav）。
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.stdout.reconfigure(encoding="utf-8")


def analyze(p):
    d, sr = sf.read(str(p), dtype="float32", always_2d=True)
    m = d.mean(axis=1) if d.shape[1] > 1 else d[:, 0]
    dur = len(m) / sr
    hop = int(sr * 0.02)
    n = len(m) // hop
    fr = np.sqrt((m[:n * hop].reshape(n, hop) ** 2).mean(axis=1))
    sil = fr < 10 ** (-45 / 20)
    runs, i, gaps = [], 0, []
    while i < n:
        if sil[i]:
            j = i
            while j < n and sil[j]:
                j += 1
            if (j - i) * 0.02 >= 0.25 and i > 2 and j < n - 2:
                gaps.append((i * 0.02, (j - i) * 0.02))
            i = j
        else:
            i += 1
    # 频谱
    f, P = None, None
    seg = m[: int(12 * sr)]
    win = 2048
    nf = len(seg) // win
    if nf > 0:
        S = np.abs(np.fft.rfft(seg[: nf * win].reshape(nf, win) * np.hanning(win), axis=1)) ** 2
        P = S.mean(axis=0)
        f = np.fft.rfftfreq(win, 1 / sr)
    centroid = float((f * P).sum() / P.sum()) if P is not None else 0.0
    def band(lo, hi):
        if P is None:
            return 0.0
        m_ = (f >= lo) & (f < hi)
        return float(P[m_].sum())
    hf = band(4000, 8000) / max(band(500, 4000), 1e-12)
    # 包络抖动（"口吃"会让包络出现多次短促的起停）
    env = fr / (fr.max() + 1e-9)
    on = env > 0.15
    onsets = int(np.sum((~on[:-1]) & on[1:]))
    return {"dur": dur, "rms": float(np.sqrt((m ** 2).mean())), "gaps": gaps,
            "gap_total": sum(g[1] for g in gaps), "centroid": centroid, "hf_ratio": hf,
            "onsets": onsets, "onset_rate": onsets / dur}


ap = argparse.ArgumentParser()
ap.add_argument("--dirs", nargs="+", required=True)
ap.add_argument("--labels", nargs="+", required=True)
ap.add_argument("--beats", default="S17-B02,S12-B02,S27-B01")
a = ap.parse_args()
beats = [b.strip() for b in a.beats.split(",")]
chars = {}
for d in a.dirs:
    for fn in ("tts_index_clone.json", "gsv_report.json"):
        ip = Path(d) / fn
        if not ip.exists():
            continue
        idx = json.loads(ip.read_text(encoding="utf-8"))
        bs = idx.get("beats")
        if isinstance(bs, dict):
            for b, r in bs.items():
                chars[b] = len(r.get("text", "") or "")
        elif isinstance(bs, list):
            for r in bs:
                chars[r.get("beat")] = r.get("chars") or len(r.get("text", "") or "")

print("=" * 100)
for b in beats:
    print("### {}（{} 字）".format(b, chars.get(b, "?")))
    print("{:24s} {:>7s} {:>7s} {:>9s} {:>9s} {:>9s} {:>8s} {:>7s}".format(
        "配置", "时长", "字/秒", "内部停顿", "停顿时长", "谱重心", "4-8k/0.5-4k", "起停数"))
    for lab, d in zip(a.labels, a.dirs):
        p = Path(d) / (b + ".wav")
        if not p.exists():
            print("{:24s} {:>7s}".format(lab, "缺失"))
            continue
        m = analyze(p)
        print("{:24s} {:7.2f} {:7.2f} {:9d} {:9.2f} {:9.0f} {:8.2f} {:7d}".format(
            lab, m["dur"], (chars.get(b, 0) / m["dur"]) if m["dur"] else 0,
            len(m["gaps"]), m["gap_total"], m["centroid"], m["hf_ratio"], m["onsets"]))
        if m["gaps"]:
            print("{:24s}   停顿位置: {}".format(
                "", ["{:.2f}s×{:.2f}s".format(t, x) for t, x in m["gaps"]]))
    print()
print("说明：谱重心越高通常越「亮」、也可能越「金属」；4-8k/0.5-4k 比值高 = 高频偏多；")
print("      内部停顿数/时长为 0.25s 以上的静音，是「口吃/异常断句」的最直接迹象。")
print("      起停数（起音次数）明显偏多 = 包络反复起停，可能对应「口吃」。")
