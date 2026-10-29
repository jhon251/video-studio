"""从整段录音里切出一个 ≤12s 的参考窗口，并同时导出与之逐字对应的文本。

文本由 --chars a:b 的累计字数区间从朗读稿里精确取出（不手打，避免抄错）。
切完自动做一致性自检：字数/时长 应落在 3.5–6.0 字/秒。

用法：
  python scripts/cut_voice_ref.py --start 38.46 --end 48.00 --chars 187:234 \
         --out C:\\mp4agent\\voice_ref\\ref_win.wav
"""
import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.stdout.reconfigure(encoding="utf-8")
SCRIPT = Path(r"C:\mp4agent\voice_ref\朗读稿_参考段1-4.txt")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wav", default=r"C:\mp4agent\voice_ref\ref_short.wav")
    ap.add_argument("--start", type=float, required=True)
    ap.add_argument("--end", type=float, required=True)
    ap.add_argument("--chars", required=True, help="朗读稿累计字数区间，如 187:234")
    ap.add_argument("--out", default=r"C:\mp4agent\voice_ref\ref_win.wav")
    ap.add_argument("--channel", default="auto", help="auto/0/1/mix —— 默认 auto")
    args = ap.parse_args()

    secs, cur = [], None
    for ln in SCRIPT.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if re.match(r"^【第\s*\d+\s*段】$", ln):
            cur = []
            secs.append(cur)
            continue
        if ln and cur is not None:
            cur.append(ln)
    full = "".join("".join(s) for s in secs)
    a, b = (int(x) for x in args.chars.split(":"))
    text = full[a:b]
    assert text, "取出的文本为空"

    d, sr = sf.read(args.wav, dtype="float32", always_2d=True)
    corr = None
    if d.shape[1] > 1:
        corr = float(np.corrcoef(d[:, 0], d[:, 1])[0, 1])
        r0 = float(np.sqrt((d[:, 0] ** 2).mean()))
        r1 = float(np.sqrt((d[:, 1] ** 2).mean()))
        if args.channel == "mix":
            mono, note = d.mean(axis=1), "显式混音（注意：双麦混音会引入梳状滤波）"
        elif args.channel in ("0", "1"):
            i = int(args.channel)
            mono, note = d[:, i], "显式指定声道 {}".format(i)
        elif corr >= 0.95:
            mono, note = d[:, 0], "双声道近乎相同（corr {:.3f}）→ 取左声道".format(corr)
        else:
            i = 0 if r0 >= r1 else 1
            mono, note = d[:, i], ("双麦立体声（corr {:.3f}，RMS L {:.4f} / R {:.4f}）→ "
                                   "取较响的{}声道单声道，避免混音梳状滤波").format(
                corr, r0, r1, "左右"[i] if False else ("左" if i == 0 else "右"))
    else:
        mono, note = d[:, 0], "单声道"

    s, e = int(args.start * sr), int(args.end * sr)
    seg = mono[max(0, s):min(len(mono), e)].copy()
    fade = int(0.01 * sr)
    if len(seg) > 2 * fade:
        seg[:fade] *= np.linspace(0, 1, fade)
        seg[-fade:] *= np.linspace(1, 0, fade)
    dur = len(seg) / sr
    cps = len(text) / dur

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out), seg, sr, subtype="PCM_16")
    txt_out = out.with_suffix(".txt")
    txt_out.write_text(text + "\n", encoding="utf-8")

    rms = float(np.sqrt((seg ** 2).mean()))
    peak = float(np.abs(seg).max())
    print("=" * 74)
    print("源文件:", args.wav, "|", note)
    print("窗口: {:.2f}–{:.2f}s → {:.2f}s | {} Hz | 字数 {}".format(
        args.start, args.end, dur, sr, len(text)))
    print("文本:", text)
    print("局部字速: {:.2f} 字/秒 | 全局 4.92 ← 越接近越说明对齐正确".format(cps))
    print("电平: RMS {:.1f} dBFS | 峰值 {:.3f} (-{:.1f} dB) | 削波 {:d} 样本".format(
        20 * np.log10(max(rms, 1e-9)), peak, -20 * np.log10(max(peak, 1e-9)),
        int((np.abs(seg) >= 0.999).sum())))
    ok = 3.5 <= cps <= 6.0 and dur <= 12.0
    print("VERDICT:", "PASS" if ok else "FAIL")
    print("写出:", out, "|", txt_out)
    rec = {"src": args.wav, "start": args.start, "end": args.end, "dur": round(dur, 3),
           "sr": sr, "text": text, "chars": len(text), "chars_per_sec": round(cps, 3),
           "rms_dbfs": round(20 * np.log10(max(rms, 1e-9)), 2), "peak": round(peak, 4),
           "verdict": "PASS" if ok else "FAIL", "note": note}
    rp = Path(r"C:\mp4agent\video-studio\output\run05\tts_clone\ref_window.json")
    rp.parent.mkdir(parents=True, exist_ok=True)
    rp.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    print("记录:", rp)
    if not ok:
        sys.exit(2)


if __name__ == "__main__":
    main()
