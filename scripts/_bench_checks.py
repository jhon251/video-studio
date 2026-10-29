"""基准后续校验：1) 生成的 wav 是否有实际音量（防 CPU 静默 bug）
                2) narration_final(v1.1) 与已渲染音频(run03 Edge) 的逐拍文本差异 → 预估时间轴变化
只读，不改任何冻结产物。"""
import json
import re
import sys
from pathlib import Path

import soundfile as sf
import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "output" / "run05" / "bench_tts_cpu"

print("=" * 78)
print("1) 生成音频音量检查（防静默/防截断）")
print("=" * 78)
for w in sorted(BENCH.glob("*.wav")):
    d, sr = sf.read(str(w), dtype="float32")
    rms = float(np.sqrt((d ** 2).mean()))
    peak = float(np.abs(d).max())
    silent_ratio = float((np.abs(d) < 1e-4).mean())
    print("{:34s} {:6.2f}s sr={} rms={:.4f} peak={:.3f} 近零样本={:.1%}".format(
        w.name, len(d) / sr, sr, rms, peak, silent_ratio))

print()
print("=" * 78)
print("2) 文案版本差：narration_final(v1.1) vs run03 已渲染音频文本")
print("=" * 78)
R = ROOT / "output"
final = json.loads((R / "run05" / "narration_final.json").read_text(encoding="utf-8"))
idx = json.loads((R / "run03" / "tts" / "tts_index.json").read_text(encoding="utf-8"))
old_b = idx["beats"]


def nz(s):
    return re.sub(r"\s", "", s or "")


changed, same, blank = [], 0, []
old_total = new_total = 0.0
rows = []
for r in final:
    b = r.get("beat")
    if b not in old_b:
        rows.append((b, "MISSING-IN-RUN03", "", 0, 0, 0.0))
        continue
    o = nz("".join(old_b[b]["narration"]))
    n = nz(r.get("final") or "")
    d = old_b[b]["dur"]
    old_total += len(o)
    new_total += len(n)
    if not n:
        blank.append((b, d, len(o), o))
        continue
    if o == n:
        same += 1
    else:
        changed.append(b)
    ratio = len(n) / len(o) if o else 0
    rows.append((b, "same" if o == n else "CHANGED", d, len(o), len(n), d * ratio))

print("拍数:", len(final), "| run03 总字数:", int(old_total), "| final 总字数:", int(new_total))
print("文本完全一致:", same, "| 文本有改动:", len(changed), "| final 为空:", len(blank))
print("按字数等比外推: 现片音频总长 {:.1f}s → 新文案约 {:.1f}s (Δ {:+.1f}s / {:+.1%})".format(
    sum(x[2] for x in rows if x[1] != "MISSING-IN-RUN03"),
    sum(x[5] for x in rows if x[1] != "MISSING-IN-RUN03"),
    sum(x[5] for x in rows if x[1] != "MISSING-IN-RUN03") - sum(x[2] for x in rows if x[1] != "MISSING-IN-RUN03"),
    (sum(x[5] for x in rows if x[1] != "MISSING-IN-RUN03") / sum(x[2] for x in rows if x[1] != "MISSING-IN-RUN03")) - 1))
print()
print("改动最大的 12 拍（按 |Δ时长| 排序）：")
big = sorted([x for x in rows if x[1] == "CHANGED"], key=lambda x: -abs(x[5] - x[2]))[:12]
print("{:10s} {:>6s} {:>5s} {:>5s} {:>8s}".format("beat", "旧dur", "旧字", "新字", "外推新dur"))
for b, st, d, lo, ln, nd in big:
    print("{:10s} {:6.2f} {:5d} {:5d} {:8.2f}".format(b, d, lo, ln, nd))
print()
print("final 为空的 3 拍（会让对应时长静音）：")
for b, d, lo, o in blank:
    print("  {} dur={:.2f}s  v3_text={}".format(b, d, o))
