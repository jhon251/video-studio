"""参考音预处理：高通滤波去隆隆声/喷麦低频 + 电平归一化（供 F5 使用）。

为什么需要：
  · 你的录音低频（<150Hz）能量占比很高（房间隆隆声 + 近讲效应 + 喷麦）
  · F5 会把这个低频特征一并学走 → 输出容易"喷/闷/金属"
  · 但高通截止不能压到嗓音基音，所以先估基频（自相关法）再给建议

用法：
  python scripts/prep_voice_ref.py --in voice_ref/ref_win.wav --out voice_ref/ref_win_hp.wav \
         --highpass 75 --target-dbfs -20.4
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.stdout.reconfigure(encoding="utf-8")


def band_rms(x, sr, lo, hi):
    from scipy.signal import butter, sosfilt

    if lo <= 0:
        sos = butter(4, hi, btype="low", fs=sr, output="sos")
    else:
        sos = butter(4, [lo, hi], btype="band", fs=sr, output="sos")
    y = sosfilt(sos, x)
    return float(np.sqrt((y ** 2).mean()))


def est_f0(x, sr):
    """自相关法估基频中位数（仅用有声帧）。"""
    hop, win = int(sr * 0.04), int(sr * 0.08)
    lo_lag, hi_lag = int(sr / 350), int(sr / 70)
    f0s = []
    for st in range(0, len(x) - win, hop):
        f = x[st:st + win]
        if np.sqrt((f ** 2).mean()) < 0.02:
            continue
        f = f - f.mean()
        ac = np.correlate(f, f, mode="full")[win - 1:]
        if ac[0] <= 0:
            continue
        seg = ac[lo_lag:hi_lag]
        if not len(seg):
            continue
        lag = lo_lag + int(np.argmax(seg))
        if ac[lag] / ac[0] > 0.3:
            f0s.append(sr / lag)
    return (float(np.median(f0s)), len(f0s)) if f0s else (0.0, 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", required=True)
    ap.add_argument("--out", dest="dst", required=True)
    ap.add_argument("--highpass", type=float, default=75.0, help="高通截止 Hz，0=关闭")
    ap.add_argument("--target-dbfs", type=float, default=-20.4,
                    help="输出 RMS 目标 dBFS（F5 标称 0.1≈-20 dBFS）")
    ap.add_argument("--no-normalize", action="store_true")
    args = ap.parse_args()

    a, sr = sf.read(args.src, dtype="float32", always_2d=True)
    x = a.mean(axis=1) if a.shape[1] > 1 else a[:, 0]
    rms0 = float(np.sqrt((x ** 2).mean()))
    peak0 = float(np.abs(x).max())
    lf0 = band_rms(x, sr, 0, 150)
    f0, nvo = est_f0(x, sr)
    print("输入: {} | {:.2f}s | {} Hz".format(Path(args.src).name, len(x) / sr, sr))
    print("  RMS {:.4f}（{:.1f} dBFS）| 峰值 {:.3f} | <150Hz 能量占比 {:.1%}".format(
        rms0, 20 * np.log10(max(rms0, 1e-9)), peak0, lf0 / max(rms0, 1e-9)))
    print("  估计基频中位数 {:.1f} Hz（有声帧 {}）".format(f0, nvo))
    if args.highpass and f0 and args.highpass > f0 * 0.8:
        print("  !! 警告：高通截止 {:.0f} Hz 接近/高于基频 {:.1f} Hz，可能削薄嗓音；"
              "建议降到 {:.0f} Hz 以下".format(args.highpass, f0, f0 * 0.7))

    y = x.astype(np.float64)
    if args.highpass:
        from scipy.signal import butter, sosfilt

        sos = butter(4, args.highpass, btype="high", fs=sr, output="sos")
        y = sosfilt(sos, y)
    if not args.no_normalize:
        r = float(np.sqrt((y ** 2).mean()))
        g = (10 ** (args.target_dbfs / 20)) / max(r, 1e-9)
        y = y * g
    peak1 = float(np.abs(y).max())
    if peak1 > 0.98:
        y = y * (0.98 / peak1)
        print("  （峰值保险：整体缩放 {:.3f}）".format(0.98 / peak1))
    y = y.astype(np.float32)

    rms1 = float(np.sqrt((y ** 2).mean()))
    lf1 = band_rms(y, sr, 0, 150)
    out = Path(args.dst)
    sf.write(str(out), y, sr, subtype="PCM_16")
    print("输出: {} | RMS {:.4f}（{:.1f} dBFS）| 峰值 {:.3f}".format(
        out.name, rms1, 20 * np.log10(max(rms1, 1e-9)), float(np.abs(y).max())))
    print("  高通 {} Hz 后 <150Hz 能量占比 {:.1%}（原 {:.1%}）".format(
        int(args.highpass) if args.highpass else 0, lf1 / max(rms1, 1e-9), lf0 / max(rms0, 1e-9)))
    rec = {"src": args.src, "dst": str(out), "sr": sr, "dur": round(len(y) / sr, 3),
           "highpass_hz": args.highpass, "target_dbfs": args.target_dbfs,
           "rms_in": round(rms0, 5), "rms_out": round(rms1, 5),
           "peak_in": round(peak0, 4), "peak_out": round(float(np.abs(y).max()), 4),
           "lf_ratio_in": round(lf0 / max(rms0, 1e-9), 4),
           "lf_ratio_out": round(lf1 / max(rms1, 1e-9), 4),
           "f0_median_hz": round(f0, 1), "voiced_frames": nvo}
    rp = Path(r"C:\mp4agent\video-studio\output\run05\tts_clone\ref_prep.json")
    rp.parent.mkdir(parents=True, exist_ok=True)
    rp.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    print("记录:", rp)


if __name__ == "__main__":
    main()
