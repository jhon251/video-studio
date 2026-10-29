"""克隆质量诊断：定位「吞字/吃尾音/口吃」的机制来源。

1) 分块分析：按 F5 的真实公式算出每块的字节上限，列出会被切成多块的拍
   （多块之间 F5 用 0.15s 交叉淡化拼接 → 会吃掉前一块尾音）
2) 生成音频内部停顿分析：找 ≥0.25s 的内部静音（口吃/断句异常的迹象）
3) 参考音喷麦扫描：低频（<150Hz）爆破能量事件，并对候选窗口排序
只读，不改任何文件。
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
WAV_FULL = Path(r"C:\mp4agent\voice_ref\ref_short.wav")
REF = Path(r"C:\mp4agent\voice_ref\ref_win.wav")
AUD = ROOT / "output/run05/tts_clone_audition_lv"

# ---------- 1) 分块分析 ----------
nar = json.loads((ROOT / "output/run05/narration_final.json").read_text(encoding="utf-8"))
ref_text = (REF.with_suffix(".txt")).read_text(encoding="utf-8").strip()
ref_sec = sf.info(str(REF)).duration + 0.05  # F5 预处理会加 50ms 静音
max_chars = int(len(ref_text.encode("utf-8")) / ref_sec * (22 - ref_sec))
print("=" * 78)
print("参考音 ref_win: {:.2f}s | ref_text {} 字 / {} 字节".format(
    sf.info(str(REF)).duration, len(ref_text), len(ref_text.encode("utf-8"))))
print("F5 每块字节上限 max_chars = {}".format(max_chars))
print("（公式：ref_bytes / ref_sec × (22 − ref_sec)；块间用 0.15s 交叉淡化拼接）")


def chunks_of(text):
    chunks, cur = [], ""
    for s in re.split(r"(?<=[;:,.!?])\s+|(?<=[；：，。！？])", text):
        if not s:
            continue
        if len(cur.encode("utf-8")) + len(s.encode("utf-8")) <= max_chars:
            cur += s
        else:
            if cur:
                chunks.append(cur.strip())
            cur = s
    if cur:
        chunks.append(cur.strip())
    return chunks


multi = []
for r in nar:
    t = str(r.get("final", "")).strip()
    if not t:
        continue
    c = chunks_of(t)
    if len(c) > 1:
        multi.append((r["beat"], len(t), len(t.encode("utf-8")), len(c),
                      [len(x) for x in c]))
print()
print("会被切成多块的拍：{} / {}（这些拍在块边界有尾音被吃掉的风险）".format(
    len(multi), sum(1 for r in nar if str(r.get("final", "")).strip())))
for b, n, nb, k, sizes in multi:
    print("   {:10s} {:3d}字 {:4d}字节 → {}块 {}".format(b, n, nb, k, sizes))
if not multi:
    print("   （无）")

# ---------- 2) 生成音频内部停顿 ----------
print()
print("=== 生成音频内部停顿（≥0.25s，口吃/断句异常迹象）===")
for f in sorted(AUD.glob("S*.wav")):
    a, sr = sf.read(str(f), dtype="float32", always_2d=True)
    m = a.mean(axis=1) if a.shape[1] > 1 else a[:, 0]
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
            if (j - i) * 0.02 >= 0.25 and i > 2 and j < n - 2:
                runs.append(((i) * 0.02, (j - i) * 0.02))
            i = j
        else:
            i += 1
    txt = next((r["final"] for r in nar if r["beat"] == f.stem), "")
    print("   {:10s} {:5.2f}s {:3d}字 {:4.2f}字/秒 | 内部停顿 {} 个 {}".format(
        f.stem, len(m) / sr, len(txt), len(txt) / (len(m) / sr), len(runs),
        ["{:.2f}s@{:.2f}".format(d, t) for t, d in runs]))

# ---------- 3) 参考音喷麦扫描 ----------
print()
print("=== 参考音喷麦扫描（<150Hz 爆破能量）===")
d, sr = sf.read(str(WAV_FULL), dtype="float32", always_2d=True)
mono = d[:, 1] if d.shape[1] > 1 else d[:, 0]  # 与选用参考同声道
try:
    from scipy.signal import butter, sosfilt

    sos = butter(4, 150, btype="low", fs=sr, output="sos")
    lf = sosfilt(sos, mono)
except Exception as e:  # 退化：简单滑动均值当低通
    print("   (scipy 不可用，改用滑动均值近似:", e, ")")
    k = int(sr / 300)
    lf = np.convolve(mono, np.ones(k) / k, mode="same")

hop = int(sr * 0.02)
n = len(lf) // hop
fr = np.sqrt((lf[:n * hop].reshape(n, hop) ** 2).mean(axis=1))
med = float(np.median(fr)) + 1e-9
thr = max(med * 8, 10 ** (-38 / 20))
events = []
i = 0
while i < n:
    if fr[i] > thr:
        j = i
        while j < n and fr[j] > thr:
            j += 1
        peak = float(fr[i:j].max())
        events.append((i * 0.02, (j - i) * 0.02, peak))
        i = j
    else:
        i += 1
print("   全片 {} 帧 | 低频中位 {:.5f} | 阈值 {:.5f} | 喷麦事件 {} 个".format(
    n, med, thr, len(events)))
if events:
    top = sorted(events, key=lambda e: -e[2])[:10]
    print("   最强的 10 个（时刻/时长/峰值）：",
          ["{:.2f}s({:.2f}s,{:.3f})".format(t, dur, p) for t, dur, p in top])
print("   当前选用窗口 38.46–48.00s 内的喷麦事件: {} 个".format(
    sum(1 for t, dur, p in events if 38.46 <= t <= 48.00)))
