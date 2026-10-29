"""参考窗口选取 v2：用「停顿↔句子边界」边界匹配法对齐 160s 录音，挑出 ≤12s 窗口。

思路（比逐句吸附更稳）：
  对每个实测停顿，按全局字速反推「读到这里大约读了多少字」，再与朗读稿各句末的
  累计字数比对，残差小者即认为是同一处边界。若多数停顿都能低残差匹配，说明映射可信。

输出：匹配表（前若干条）+ 可用窗口（8–12s）+ 置信度评估。只读输入。
"""
import re
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.stdout.reconfigure(encoding="utf-8")
SCRIPT = Path(r"C:\mp4agent\voice_ref\朗读稿_参考段1-4.txt")
WAV = Path(r"C:\mp4agent\voice_ref\ref_short.wav")

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

d, sr = sf.read(str(WAV), dtype="float32", always_2d=True)
mono = d.mean(axis=1)
dur = len(mono) / sr
hop_ms = 20
hop = int(sr * hop_ms / 1000)
nf = len(mono) // hop
frms = np.sqrt((mono[:nf * hop].reshape(nf, hop) ** 2).mean(axis=1))
sil = frms < 10 ** (-45 / 20)

runs, i = [], 0
while i < nf:
    if sil[i]:
        j = i
        while j < nf and sil[j]:
            j += 1
        runs.append((i * hop_ms / 1000, j * hop_ms / 1000))
        i = j
    else:
        i += 1
lead_end = next((b for a, b in runs if a <= 0.001), 0.0)
pauses = [(a, b) for a, b in runs if (b - a) >= 0.10 and a > lead_end]

sents, buf = [], ""
for ch in full:
    buf += ch
    if ch in "。！？；":
        sents.append(buf)
        buf = ""
if buf:
    sents.append(buf)
cum, acc = [], 0
for s in sents:
    acc += len(s)
    cum.append(acc)

rate = len(full) / dur
print("朗读稿 {} 字 / {} 句 | 音频 {:.2f}s | 全局字速 {:.2f} 字/秒 | 开头静音 {:.2f}s".format(
    len(full), len(sents), dur, rate, lead_end))
print("停顿(≥0.10s，不含开头) {} 个".format(len(pauses)))

print()
print("=== 停顿 ↔ 句边界 匹配 ===")
print("{:>8s} {:>7s} {:>9s} {:>9s} {:>8s}  {}".format(
    "时刻", "时长", "估计字数", "最近边界", "残差", "边界处文本（末 18 字）"))
matched = []
for a, b in pauses:
    c = (a + b) / 2
    est = (c - lead_end) * rate
    k = min(range(len(cum)), key=lambda t: abs(cum[t] - est))
    resid = est - cum[k]
    ok = abs(resid) <= 8
    if ok:
        matched.append((c, cum[k], k))
    print("{:8.2f} {:7.2f} {:9.1f} {:9d} {:8.1f}  {}".format(
        c, b - a, est, cum[k], resid, sents[k][-18:]))
    if len(matched) >= 40:
        pass

conf = sum(1 for a, b in pauses
           if abs((a + b) / 2 - lead_end) * rate - cum[min(range(len(cum)),
              key=lambda t: abs(cum[t] - ((a + b) / 2 - lead_end) * rate))] <= 8)
print()
print("低残差(≤8 字)匹配: {}/{} = {:.0%}".format(conf, len(pauses), conf / max(1, len(pauses))))

print()
print("=== 可用窗口（连续匹配边界 / 8–12s）===")
pts = [(lead_end, 0)] + [(c, ch) for c, ch, _ in matched]
pts.sort()
found = 0
for i in range(len(pts)):
    for j in range(i + 1, len(pts)):
        span = pts[j][0] - pts[i][0]
        if span > 12.0:
            break
        if span < 8.0:
            continue
        txt = full[pts[i][1]:pts[j][1]]
        if not txt:
            continue
        asc = bool(re.search(r"[A-Za-z0-9]", txt))
        print("  {:.2f}–{:.2f}s ({:.2f}s) | {:3d}字 | {:.2f}字/秒 | {} | {}".format(
            pts[i][0], pts[j][0], span, len(txt), len(txt) / span,
            "含ASCII" if asc else "纯中文", txt))
        found += 1
        if found >= 10:
            break
    if found >= 10:
        break
if not found:
    print("  无：匹配边界之间凑不出 8–12s 的整句窗口")
