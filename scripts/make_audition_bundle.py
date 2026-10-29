"""把试听目录里的逐拍 wav 拼成一个单文件试听包（段间 0.7s 静音），并生成文本清单。

不依赖 ffmpeg：用 soundfile 读写，统一采样率（取首个文件的 sr），单声道。
用法：python scripts/make_audition_bundle.py --dir output/run05/tts_clone_audition
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
    ap.add_argument("--dir", default=str(ROOT / "output" / "run05" / "tts_clone_audition"))
    ap.add_argument("--gap", type=float, default=0.7)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    d = Path(args.dir)
    idx_p = None
    for name in ("tts_index_clone.json", "tts_index.json"):
        if (d / name).exists():
            idx_p = d / name
            break
    if idx_p is None:
        sys.exit("找不到索引（tts_index_clone.json / tts_index.json）: " + str(d))
    idx = json.loads(idx_p.read_text(encoding="utf-8"))
    beats = list(idx["beats"].keys())
    out = Path(args.out) if args.out else d / "_audition_all.wav"

    sr_target, chunks, lines, cursor = None, [], [], 0.0
    for b in beats:
        w = d / (b + ".wav")
        if not w.exists():
            continue
        a, sr = sf.read(str(w), dtype="float32", always_2d=True)
        m = a.mean(axis=1) if a.shape[1] > 1 else a[:, 0]
        if sr_target is None:
            sr_target = sr
        if sr != sr_target:
            n = int(len(m) * sr_target / sr)
            m = np.interp(np.linspace(0, len(m) - 1, n), np.arange(len(m)), m).astype(np.float32)
        chunks.append(m)
        t = idx["beats"][b]["text"]
        lines.append("{:10s} {:>5.2f}s | {}".format(b, len(m) / sr_target, t))
        cursor += len(m) / sr_target
        chunks.append(np.zeros(int(args.gap * sr_target), dtype=np.float32))
        cursor += args.gap

    if not chunks:
        sys.exit("没有可拼接的 wav")
    full = np.concatenate(chunks)
    peak = float(np.abs(full).max())
    if peak > 0.99:
        full = (full * (0.99 / peak)).astype(np.float32)
    sf.write(str(out), full, sr_target, subtype="PCM_16")
    txt = out.with_suffix(".txt")
    txt.write_text("试听包（{} 拍 / {:.1f}s，段间 {:.1f}s 静音）\n\n".format(
        len(lines), len(full) / sr_target, args.gap) + "\n".join(lines) + "\n", encoding="utf-8")
    print("试听包:", out)
    print("时长 {:.1f}s | 采样率 {} | 拍数 {} | 峰值归一 {}".format(
        len(full) / sr_target, sr_target, len(lines), "是" if peak > 0.99 else "否（原峰值 {:.3f}）".format(peak)))
    print("清单:", txt)


if __name__ == "__main__":
    main()
