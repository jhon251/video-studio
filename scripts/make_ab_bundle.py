"""交错式多引擎 A/B 试听包：同一拍把各引擎版本连续播放，便于盲听分辨。

顺序：beat1[A][B][C] … beat2[A][B][C] …（段间 gap 秒静音）
用法：
  python scripts/make_ab_bundle.py --dirs d1 d2 d3 --labels "F5 nfe16" "GSV v3@32" "GSV v2" \
      --beats S17-B02,S12-B02,S27-B01 --out output/run05/ab_bundle.wav
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.stdout.reconfigure(encoding="utf-8")
VS = Path(r"C:\mp4agent\video-studio")


def load_mono(p, sr_target):
    a, sr = sf.read(str(p), dtype="float32", always_2d=True)
    m = a.mean(axis=1) if a.shape[1] > 1 else a[:, 0]
    if sr != sr_target:
        n = int(len(m) * sr_target / sr)
        m = np.interp(np.linspace(0, len(m) - 1, n), np.arange(len(m)), m).astype(np.float32)
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dirs", nargs="+", required=True)
    ap.add_argument("--labels", nargs="+", required=True)
    ap.add_argument("--beats", default="S17-B02,S12-B02,S27-B01")
    ap.add_argument("--gap", type=float, default=0.6)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    assert len(args.dirs) == len(args.labels), "--dirs 与 --labels 数量必须一致"

    beats = [b.strip() for b in args.beats.split(",") if b.strip()]
    dirs = [Path(d) if Path(d).is_absolute() else VS / d for d in args.dirs]
    txt = {}
    for d in dirs:
        for f in ("tts_index_clone.json", "gsv_report.json"):
            p = d / f
            if p.exists():
                j = json.loads(p.read_text(encoding="utf-8"))
                if "beats" in j and isinstance(j["beats"], dict):
                    for b, r in j["beats"].items():
                        txt[b] = r.get("text", "")
                elif "beats" in j and isinstance(j["beats"], list):
                    for r in j["beats"]:
                        txt[r["beat"]] = r.get("text", "")

    raw = {}
    sr_target = None
    for d, lab in zip(dirs, args.labels):
        for i, b in enumerate(beats):
            p = d / (b + ".wav")
            if not p.exists():
                print("缺失:", p)
                continue
            info = sf.info(str(p))
            if sr_target is None:
                sr_target = info.samplerate
            raw[(lab, b)] = str(p)
    if not raw:
        sys.exit("没有任何可用 wav")

    chunks, lines = [], []
    for b in beats:
        lines.append("=== {} （{} 字）：{} ===".format(b, len(txt.get(b, "")), txt.get(b, "")[:40]))
        for lab in args.labels:
            p = raw.get((lab, b))
            if not p:
                continue
            m = load_mono(p, sr_target)
            chunks.append(m)
            chunks.append(np.zeros(int(args.gap * sr_target), dtype=np.float32))
            lines.append("    {:<14s} {:5.2f}s".format(lab, len(m) / sr_target))
        chunks.append(np.zeros(int(args.gap * sr_target), dtype=np.float32))
        lines.append("")

    full = np.concatenate(chunks)
    peak = float(np.abs(full).max())
    if peak > 0.99:
        full = (full * (0.99 / peak)).astype(np.float32)
    out = Path(args.out)
    if not out.is_absolute():
        out = VS / out
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out), full, sr_target, subtype="PCM_16")
    tp = out.with_suffix(".txt")
    tp.write_text("交错 A/B 试听包（每个 beat 依次为：{}）\n总时长 {:.1f}s | {:.1f} kHz\n\n".format(
        " → ".join(args.labels), len(full) / sr_target, sr_target / 1000) + "\n".join(lines) + "\n",
        encoding="utf-8")
    print("试听包:", out, "| {:.1f}s | {} Hz".format(len(full) / sr_target, sr_target))
    print("清单:", tp)


if __name__ == "__main__":
    main()
