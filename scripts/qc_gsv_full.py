"""全片合成质检：时长/响度/削波/内部停顿/异常拍排序，输出可直接引用的报告。

用法：python scripts/qc_gsv_full.py --dir output/run05/tts_gsv_v2_full
"""
import argparse
import json
import statistics as st
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.stdout.reconfigure(encoding="utf-8")
VS = Path(r"C:\mp4agent\video-studio")


def gaps_of(m, sr, min_s=0.25):
    hop = int(sr * 0.02)
    n = len(m) // hop
    fr = np.sqrt((m[:n * hop].reshape(n, hop) ** 2).mean(axis=1))
    sil = fr < 10 ** (-45 / 20)
    out, i = [], 0
    while i < n:
        if sil[i]:
            j = i
            while j < n and sil[j]:
                j += 1
            if (j - i) * 0.02 >= min_s and i > 2 and j < n - 2:
                out.append((round(i * 0.02, 2), round((j - i) * 0.02, 2)))
            i = j
        else:
            i += 1
    return out


ap = argparse.ArgumentParser()
ap.add_argument("--dir", required=True)
ap.add_argument("--fail-gap", type=float, default=0.80, help="内部停顿超过此值记为可疑")
ap.add_argument("--fail-delta", type=float, default=3.0, help="与目标时长偏差超过此值记为可疑")
a = ap.parse_args()
d = Path(a.dir)
if not d.is_absolute():
    d = VS / d
idx = json.loads((d / "tts_index.json").read_text(encoding="utf-8"))
beats = idx["beats"]
print("=" * 100)
print("全片质检:", d.name, "| 引擎:", idx.get("engine"), "| 拍数:", len(beats))
print("=" * 100)

rows, missing = [], []
for b, r in beats.items():
    p = Path(r["wav_abs"]) if r.get("wav_abs") else (d / (b + ".wav"))
    if not p.exists():
        missing.append(b)
        continue
    x, sr = sf.read(str(p), dtype="float32", always_2d=True)
    m = x.mean(axis=1) if x.shape[1] > 1 else x[:, 0]
    dur = len(m) / sr
    rms = float(np.sqrt((m ** 2).mean()))
    peak = float(np.abs(m).max())
    clip = float((np.abs(m) >= 0.999).mean())
    g = gaps_of(m, sr)
    rows.append({"beat": b, "dur": dur, "target": r["target_dur"], "delta": dur - r["target_dur"],
                 "chars": r["chars"], "cps": r["chars"] / dur if dur else 0,
                 "rms": rms, "peak": peak, "clip": clip, "gaps": g,
                 "gap_total": sum(y for _, y in g), "sr": sr})

if missing:
    print("!! 缺失 wav:", len(missing), missing[:10])
R = [x["rms"] for x in rows]
tot = sum(x["dur"] for x in rows)
tgt = sum(x["target"] for x in rows)
print("时长: 新片 {:.1f}s（{:.1f} 分钟） | 现片对应 {:.1f}s | Δ{:+.1f}s（{:+.1%}）".format(
    tot, tot / 60, tgt, tot - tgt, tot / tgt - 1 if tgt else 0))
print("响度: RMS {:.4f}–{:.4f}（{:.1f}–{:.1f} dBFS）| 标准差 {:.4f} | 峰值最大 {:.3f} | 削波拍数 {}".format(
    min(R), max(R), 20 * np.log10(min(R)), 20 * np.log10(max(R)), st.pstdev(R),
    max(x["peak"] for x in rows), sum(1 for x in rows if x["clip"] > 0)))
print("采样率:", sorted({x["sr"] for x in rows}))
print("内部停顿: 合计 {} 个 | ≥{:.2f}s 的 {} 个 | 停顿总时长 {:.1f}s".format(
    sum(len(x["gaps"]) for x in rows), a.fail_gap,
    sum(1 for x in rows for y in x["gaps"] if y[1] >= a.fail_gap),
    sum(x["gap_total"] for x in rows)))
print("字速: 中位 {:.2f} 字/秒 | 范围 {:.2f}–{:.2f}".format(
    st.median([x["cps"] for x in rows]), min(x["cps"] for x in rows), max(x["cps"] for x in rows)))

sus_gap = sorted([x for x in rows if any(y[1] >= a.fail_gap for y in x["gaps"])],
                 key=lambda x: -max(y[1] for y in x["gaps"]))
sus_del = sorted(rows, key=lambda x: -abs(x["delta"]))
print()
print("--- 内部停顿 ≥{:.2f}s 的拍（{} 个）---".format(a.fail_gap, len(sus_gap)))
for x in sus_gap[:15]:
    worst = max(x["gaps"], key=lambda y: y[1])
    print("   {:10s} {:6.2f}s {:3d}字 | 最长停顿 {:.2f}s @{:.2f}s | 停顿合计 {:.2f}s".format(
        x["beat"], x["dur"], x["chars"], worst[1], worst[0], x["gap_total"]))
print()
print("--- 时长偏差最大的 15 拍 ---")
for x in sus_del[:15]:
    print("   {:10s} 新 {:6.2f}s / 目标 {:6.2f}s  Δ{:+.2f}s  ({:3d}字, {:.2f}字/秒)".format(
        x["beat"], x["dur"], x["target"], x["delta"], x["chars"], x["cps"]))

rep = {"dir": str(d), "engine": idx.get("engine"), "beats": len(rows),
       "sum_dur": round(tot, 2), "sum_target": round(tgt, 2), "delta": round(tot - tgt, 2),
       "rms_min": round(min(R), 5), "rms_max": round(max(R), 5), "rms_std": round(st.pstdev(R), 5),
       "peak_max": round(max(x["peak"] for x in rows), 4),
       "clipped_beats": sum(1 for x in rows if x["clip"] > 0),
       "gaps_total": sum(len(x["gaps"]) for x in rows),
       "gaps_ge_threshold": sum(1 for x in rows for y in x["gaps"] if y[1] >= a.fail_gap),
       "cps_median": round(st.median([x["cps"] for x in rows]), 3),
       "suspect_gap_beats": [x["beat"] for x in sus_gap],
       "suspect_delta_beats": [x["beat"] for x in sus_del if abs(x["delta"]) > a.fail_delta],
       "missing": missing}
(d / "qc_report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
print()
print("报告:", d / "qc_report.json")
