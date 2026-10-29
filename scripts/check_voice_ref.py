"""参考录音质检（只读输入）：拿到 ref_short.wav 后先跑这个，再决定是否开跑克隆。

检查项：
  1. 基本规格（时长/采样率/声道）
  2. 电平（RMS/峰值 dBFS）与削波比例
  3. 静音占比（20ms 帧，<-45 dBFS 记为静音）
  4. 文本-时长一致性（中文正常语速约 3.5–5.5 字/秒）
  5. F5 的 12s 裁剪警告：若音频 >12s，按比例估算「前 12s 覆盖了多少字」
  6. 可选 --trim-out：把前 12s 内的干净片段导出为 ≤12s 的 WAV（不依赖 ffmpeg）

用法：
  python scripts/check_voice_ref.py --wav C:\\mp4agent\\voice_ref\\ref_short.wav \
         --ref-text C:\\mp4agent\\voice_ref\\参考音专用短段.txt
  # 需要时顺便裁一份可用片段：
  python scripts/check_voice_ref.py --wav ... --ref-text ... --trim-out output/run05/tts_clone/ref_12s.wav
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wav", required=True)
    ap.add_argument("--ref-text", default="", help="参考文本文件（用于文字-时长一致性）")
    ap.add_argument("--trim-out", default="", help="可选：导出 ≤12s 片段")
    ap.add_argument("--report", default=str(ROOT / "output" / "run05" / "tts_clone" / "ref_qc.json"))
    args = ap.parse_args()

    wav = Path(args.wav)
    if not wav.exists():
        sys.exit("找不到音频: " + str(wav))
    d, sr = sf.read(str(wav), dtype="float32", always_2d=True)
    mono = d.mean(axis=1) if d.shape[1] > 1 else d[:, 0]
    info = sf.info(str(wav))
    dur = len(mono) / sr
    peak = float(np.abs(mono).max()) if len(mono) else 0.0
    rms = float(np.sqrt((mono ** 2).mean())) if len(mono) else 0.0
    clip = float((np.abs(mono) >= 0.999).mean())
    frames = 20
    hop = int(sr * frames / 1000)
    nf = max(1, len(mono) // hop)
    fr = mono[:nf * hop].reshape(nf, hop)
    frms = np.sqrt((fr ** 2).mean(axis=1))
    sil = float((frms < 10 ** (-45 / 20)).mean())
    lead = 0
    while lead < nf and frms[lead] < 10 ** (-45 / 20):
        lead += 1
    tail = 0
    while tail < nf and frms[nf - 1 - tail] < 10 ** (-45 / 20):
        tail += 1

    text = ""
    if args.ref_text:
        p = Path(args.ref_text)
        text = (p.read_text(encoding="utf-8") if p.exists() else args.ref_text).strip().replace("\n", "")
    cps = len(text) / dur if (text and dur) else 0.0

    fails, warns = [], []
    if dur < 6:
        fails.append("时长 {:.1f}s 偏短，建议 8–12s".format(dur))
    if dur > 12.5:
        warns.append("时长 {:.1f}s >12.5s，F5 会裁到约 12s".format(dur))
    if info.samplerate < 16000:
        fails.append("采样率 {} Hz 偏低，建议 ≥16 kHz（最好 24/44.1/48 kHz）".format(info.samplerate))
    if peak >= 0.999 or clip > 0.001:
        fails.append("存在削波（峰值 {:.3f}，削波样本 {:.2%}），请降增益重录".format(peak, clip))
    if rms < 10 ** (-40 / 20):
        warns.append("整体电平偏低（RMS {:.1f} dBFS）".format(20 * np.log10(max(rms, 1e-9))))
    if sil > 0.45:
        warns.append("静音占比 {:.0%} 偏高，可能有大段空白或停顿过多".format(sil))
    if text and not (3.0 <= cps <= 6.0):
        fails.append("文本-时长不一致：{} 字 / {:.1f}s = {:.2f} 字/秒（正常 3.5–5.5）".format(
            len(text), dur, cps))
    if text and dur > 12.5:
        inside = int(len(text) * min(12.0, dur) / dur)
        warns.append("按比例，前 12s 只覆盖约 {} 字（全文 {} 字）—— 若 ref_text 用全文，"
                     "裁剪后会错位".format(inside, len(text)))

    print("=" * 70)
    print("文件:", wav)
    print("规格: {:.2f}s | {} Hz | {} ch | {}".format(dur, info.samplerate, info.channels, info.subtype))
    print("电平: RMS {:.1f} dBFS | 峰值 {:.3f} ({:.1f} dBFS) | 削波样本 {:.3%}".format(
        20 * np.log10(max(rms, 1e-9)), peak, 20 * np.log10(max(peak, 1e-9)), clip))
    print("静音: 占比 {:.1%} | 开头 {:.2f}s | 结尾 {:.2f}s".format(sil, lead * frames / 1000, tail * frames / 1000))
    if text:
        print("文本: {} 字 | 语速 {:.2f} 字/秒".format(len(text), cps))
    print("-" * 70)
    for f in fails:
        print("FAIL:", f)
    for w in warns:
        print("WARN:", w)
    verdict = "FAIL" if fails else ("WARN" if warns else "PASS")
    print("VERDICT:", verdict)

    report = {"wav": str(wav), "duration_s": round(dur, 3), "samplerate": info.samplerate,
              "channels": info.channels, "subtype": info.subtype,
              "rms_dbfs": round(20 * np.log10(max(rms, 1e-9)), 2),
              "peak": round(peak, 4), "clip_ratio": round(clip, 6),
              "silence_ratio": round(sil, 4), "lead_silence_s": round(lead * frames / 1000, 3),
              "tail_silence_s": round(tail * frames / 1000, 3),
              "ref_text_chars": len(text), "chars_per_sec": round(cps, 3),
              "fails": fails, "warns": warns, "verdict": verdict}
    if args.trim_out:
        limit = int(min(12.0, dur) * sr)
        out = Path(args.trim_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        seg = mono[int(lead * frames / 1000 * sr):][:limit]
        sf.write(str(out), seg, sr)
        report["trim_out"] = {"path": str(out), "duration_s": round(len(seg) / sr, 3),
                              "note": "已去掉开头静音并截到 ≤12s；ref_text 需与之逐字对应"}
        print("已导出片段:", out, "|", round(len(seg) / sr, 2), "s")
    rp = Path(args.report)
    rp.parent.mkdir(parents=True, exist_ok=True)
    rp.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print("报告:", rp)
    if verdict == "FAIL":
        sys.exit(2)


if __name__ == "__main__":
    main()
