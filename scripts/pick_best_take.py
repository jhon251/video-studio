"""多 take 择优：在候选中挑出「内部空洞最小、时长最接近预期」的一版，替换主目录文件。

评分（越低越好）：
    score = 3.0 × 最长内部停顿(≥0.4s)
          + 1.0 × (≥0.8s 的停顿个数)
          + |时长 − 预期时长|
  预期时长 = 字数 ÷ 中位字速（默认 4.27 字/秒，来自全片实测中位数）
被替换的原文件会移到 <主目录>/_replaced/ 存档，并写出 replace_log.json。

用法：
  python scripts/pick_best_take.py --main output/run05/tts_gsv_v2_full \
      --cands output/run05/retake_A output/run05/retake_B \
      --beats S16-B03,S31-B01 --expect-cps 4.27
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.stdout.reconfigure(encoding="utf-8")
VS = Path(r"C:\mp4agent\video-studio")


def analyse(p):
    a, sr = sf.read(str(p), dtype="float32", always_2d=True)
    m = a.mean(axis=1) if a.shape[1] > 1 else a[:, 0]
    dur = len(m) / sr
    hop = int(sr * 0.02)
    n = len(m) // hop
    fr = np.sqrt((m[:n * hop].reshape(n, hop) ** 2).mean(axis=1))
    sil = fr < 10 ** (-45 / 20)
    gaps, i = [], 0
    while i < n:
        if sil[i]:
            j = i
            while j < n and sil[j]:
                j += 1
            if (j - i) * 0.02 >= 0.40 and i > 2 and j < n - 2:
                gaps.append(round((j - i) * 0.02, 2))
            i = j
        else:
            i += 1
    return {"dur": dur, "sr": sr, "max_gap": max(gaps) if gaps else 0.0,
            "n_gap80": sum(1 for g in gaps if g >= 0.8),
            "gaps": sorted(gaps, reverse=True)[:4],
            "rms": float(np.sqrt((m ** 2).mean())), "peak": float(np.abs(m).max())}


ap = argparse.ArgumentParser()
ap.add_argument("--main", required=True)
ap.add_argument("--cands", nargs="+", required=True)
ap.add_argument("--beats", required=True)
ap.add_argument("--expect-cps", type=float, default=4.27)
ap.add_argument("--chars", default="", help="可选：字符数 JSON（默认读主目录 tts_index.json）")
ap.add_argument("--tolerance", type=float, default=0.0, help="候选需比原版好多少分才替换（默认 0）")
a = ap.parse_args()

main = Path(a.main)
if not main.is_absolute():
    main = VS / main
cands = [Path(c) if Path(c).is_absolute() else VS / c for c in a.cands]
beats = [b.strip() for b in a.beats.split(",") if b.strip()]

chars = {}
ip = main / "tts_index.json"
if ip.exists():
    j = json.loads(ip.read_text(encoding="utf-8"))
    for b, r in j.get("beats", {}).items():
        chars[b] = r.get("chars") or len(r.get("text", "") or "")

repl = Path(main) / "_replaced"
repl.mkdir(exist_ok=True)
log = []
for b in beats:
    if b not in chars:
        print("跳过（无字数信息）:", b)
        continue
    exp = chars[b] / a.expect_cps
    best_p, best_src, best_m = main / (b + ".wav"), "keep", None
    if best_p.exists():
        m0 = analyse(best_p)
        best_score = 3.0 * m0["max_gap"] + m0["n_gap80"] + abs(m0["dur"] - exp)
        best_m = m0
    else:
        best_score = 1e9
    for c in cands:
        p = c / (b + ".wav")
        if not p.exists():
            continue
        m = analyse(p)
        s = 3.0 * m["max_gap"] + m["n_gap80"] + abs(m["dur"] - exp)
        if s < best_score - a.tolerance:
            best_score, best_p, best_src, best_m = s, p, c.name, m
    if best_src != "keep":
        shutil.copy2(str(main / (b + ".wav")), str(repl / (b + ".wav")))  # 存档原版
        shutil.copy2(str(best_p), str(main / (b + ".wav")))
        print("{:10s} {}字 预期{:5.2f}s | 换用 {:<9s} 新 {:5.2f}s 最长停顿 {:.2f}s (原最长停顿 {:.2f}s)".format(
            b, chars[b], exp, best_src, best_m["dur"], best_m["max_gap"], analyse(repl / (b + ".wav"))["max_gap"]))
        log.append({"beat": b, "chars": chars[b], "expected": round(exp, 2),
                    "chosen": best_src, "dur": round(best_m["dur"], 3),
                    "max_gap": best_m["max_gap"], "score": round(best_score, 3)})
    else:
        print("{:10s} {}字 预期{:5.2f}s | 保留原版（候选均未更优）原 {:5.2f}s 最长停顿 {:.2f}s".format(
            b, chars[b], exp, best_m["dur"], best_m["max_gap"]))

(main / "replace_log.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
print()
print("替换 {} 拍 | 原版存档: {} | 记录: {}".format(len(log), repl, main / "replace_log.json"))
