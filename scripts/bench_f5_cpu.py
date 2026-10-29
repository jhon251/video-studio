"""F5-TTS CPU 速度基准（只读，不改任何冻结产物）。

目的：在本机（Ryzen 7 8745HS, 8C/16T, 无 CUDA, torch CPU）测出真实 RTF，
      再用真实 101 拍文案长度外推全片工时，作为「换商用引擎」的可行性依据。

参考音频：output/run03/tts/S01-B01.wav（6.43s / 24kHz）
          ref_text 取自 tts_index.json 的逐字数组 —— 音频与文本严格对齐。
          上一次 smoke 用的是 47s 截断音频 + 188 字整段文本，二者不匹配，
          导致 38 字只生成 2.53s（估算时长被带偏），本次刻意修正。

待合成文本：output/run05/narration_final.json 里三档真实长度（最短/中位/p95）。

输出：output/run05/bench_tts_cpu/（wav + bench_report.json）
用法：.venv_tts\\Scripts\\python.exe scripts\\bench_f5_cpu.py
"""
import json
import math
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

import torch
import torchaudio as _ta
import soundfile as _sf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "run05" / "bench_tts_cpu"
OUT.mkdir(parents=True, exist_ok=True)


def _load_any(uri, frame_offset=0, num_frames=-1, normalize=True, channels_first=True):
    wav, sr = _sf.read(str(uri), dtype="float32")
    wav = torch.from_numpy(wav)
    if wav.ndim == 1:
        wav = wav.unsqueeze(0)
    else:
        wav = wav.T
    if num_frames >= 0:
        wav = wav[:, frame_offset:frame_offset + num_frames]
    elif frame_offset:
        wav = wav[:, frame_offset:]
    return wav, sr


_ta.load = _load_any

# ---------------- 参考音频 ----------------
idx = json.loads((ROOT / "output" / "run03" / "tts" / "tts_index.json").read_text(encoding="utf-8"))
REF_BEAT = "S01-B01"
REF_WAV = ROOT / "output" / "run03" / "tts" / (REF_BEAT + ".wav")
if not REF_WAV.exists():
    cand = list((ROOT / "output" / "run03" / "tts").glob(REF_BEAT + "*.wav"))
    if not cand:
        sys.exit("找不到参考音频: " + str(REF_WAV))
    REF_WAV = cand[0]
REF_TEXT = "".join(idx["beats"][REF_BEAT]["narration"])
ref_info = _sf.info(str(REF_WAV))

# ---------------- 待合成文本（真实文案） ----------------
nar = json.loads((ROOT / "output" / "run05" / "narration_final.json").read_text(encoding="utf-8"))
beats = [r for r in nar if r.get("final")]
for r in beats:
    r["n"] = len(r["final"])
sb = sorted(beats, key=lambda r: r["n"])
picks = [
    ("short", sb[0]),
    ("median", sb[len(sb) // 2]),
    ("long", sb[min(len(sb) - 1, int(len(sb) * 0.95))]),
]

print("=" * 78)
print("F5-TTS CPU 基准")
print("参考:", REF_WAV.name, "|", round(ref_info.duration, 2), "s |", ref_info.samplerate, "Hz")
print("ref_text:", REF_TEXT)
print("来料拍数:", len(beats), "| 总字数:", sum(r["n"] for r in beats))
for tag, r in picks:
    edge = idx["beats"].get(r["beat"], {}).get("dur")
    print("  [" + tag + "]", r["beat"], r["n"], "字 | Edge 现时长", edge, "s |", r["final"][:40])
print("=" * 78)

# ---------------- 模型 ----------------
models_dir = ROOT / "models" / "f5"
ckpt = models_dir / "F5TTS_v1_Base" / "F5TTS_v1_Base" / "model_1250000.safetensors"
vocab = models_dir / "F5TTS_v1_Base" / "F5TTS_v1_Base" / "vocab.txt"
vocoder_dir = models_dir / "vocos-mel-24khz"

from f5_tts.api import F5TTS  # noqa: E402

torch.set_num_threads(16)
t0 = time.perf_counter()
f5 = F5TTS(device="cpu", ckpt_file=str(ckpt), vocab_file=str(vocab), vocoder_local_path=str(vocoder_dir))
LOAD_S = time.perf_counter() - t0
print("模型加载完成:", round(LOAD_S, 1), "s | torch", torch.__version__, "| 线程", torch.get_num_threads())

# ---------------- 运行计划 ----------------
# (标签, nfe_step, 线程数, 重复次数)
PLAN = [
    ("short", 32, 16, 2),
    ("median", 32, 16, 2),
    ("long", 32, 16, 1),
    ("median", 16, 16, 1),   # nfe 减半：速度/质量旋钮
    ("median", 32, 8, 1),    # 线程数减半：SMT 收益
]
MAX_SECONDS = float(os.environ.get("BENCH_MAX_SECONDS", "2400"))
text_by_tag = {tag: r for tag, r in picks}
results = []
report = {
    "machine": {
        "cpu": "AMD Ryzen 7 8745HS 8C/16T",
        "cuda": torch.cuda.is_available(),
        "torch": torch.__version__,
        "threads_default": torch.get_num_threads(),
    },
    "ref": {"beat": REF_BEAT, "wav": str(REF_WAV), "sec": round(ref_info.duration, 3),
            "sr": ref_info.samplerate, "text": REF_TEXT},
    "load_seconds": round(LOAD_S, 2),
    "runs": [],
}
(OUT / "bench_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

start_all = time.perf_counter()
stopped = False
for tag, nfe, threads, reps in PLAN:
    if stopped:
        break
    r = text_by_tag[tag]
    for i in range(reps):
        if time.perf_counter() - start_all > MAX_SECONDS:
            print("!! 超过时间预算，停止后续用例")
            stopped = True
            break
        torch.set_num_threads(threads)
        seed = 1000 + len(results)
        t = time.perf_counter()
        wav, sr, _spec = f5.infer(ref_file=str(REF_WAV), ref_text=REF_TEXT,
                                  gen_text=r["final"], nfe_step=nfe, seed=seed)
        el = time.perf_counter() - t
        dur = len(wav) / sr
        name = tag + "_nfe" + str(nfe) + "_t" + str(threads) + "_" + str(i + 1) + ".wav"
        _sf.write(str(OUT / name), wav, sr)
        edge = idx["beats"].get(r["beat"], {}).get("dur")
        rec = {
            "tag": tag, "beat": r["beat"], "chars": r["n"], "nfe_step": nfe, "threads": threads,
            "rep": i + 1, "seed": seed, "wall_s": round(el, 3), "audio_s": round(dur, 3),
            "rtf": round(el / dur, 3), "chars_per_s": round(r["n"] / el, 3),
            "edge_dur_s": edge, "wav": name,
        }
        results.append(rec)
        report["runs"] = results
        (OUT / "bench_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print("[{}/{}] {} nfe={} t={} | {}字 | 耗时 {:.1f}s | 音频 {:.2f}s | RTF {:.2f} | {:.2f} 字/s".format(
            len(results), sum(p[3] for p in PLAN), tag, nfe, threads, r["n"], el, dur, el / dur, r["n"] / el))

# ---------------- 拟合与外推 ----------------
base = [x for x in results if x["nfe_step"] == 32 and x["threads"] == 16]
proj = {}
if len(base) >= 2:
    xs = [float(x["chars"]) for x in base]
    ys = [x["wall_s"] for x in base]
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    den = sum((v - mx) ** 2 for v in xs)
    b = sum((xs[i] - mx) * (ys[i] - my) for i in range(n)) / den if den else 0.0
    a = my - b * mx
    total_chars = sum(r["n"] for r in beats)

    def chunks_for(chars):
        # 复用 F5 自身的分块公式：max_chars = ref_chars_bytes/ref_sec*(22-ref_sec)
        ref_sec = ref_info.duration
        max_chars = int(len(REF_TEXT.encode("utf-8")) / ref_sec * (22 - ref_sec))
        return max_chars, max(1, math.ceil(chars / max(1, max_chars)))

    max_chars, _ = chunks_for(0)
    per_beat = len(beats) * a + b * total_chars

    groups = {}
    for r in beats:
        g = r["beat"].split("-")[0]
        groups[g] = groups.get(g, 0) + r["n"]
    batched = 0.0
    for g, chars in groups.items():
        _, nc = chunks_for(chars)
        per_chunk = chars / nc
        batched += nc * (a + b * per_chunk)

    proj = {
        "fit": {"intercept_s": round(a, 3), "per_char_s": round(b, 4),
                "note": "wall = a + b*chars（同参考音频、nfe=32、16 线程）"},
        "max_chars_per_chunk": max_chars,
        "total_chars": total_chars,
        "beats": len(beats),
        "projection_per_beat_calls_s": round(per_beat, 1),
        "projection_per_beat_calls_min": round(per_beat / 60, 1),
        "groups": len(groups),
        "projection_grouped_s": round(batched, 1),
        "projection_grouped_min": round(batched / 60, 1),
        "rtf_median": sorted(x["rtf"] for x in base)[len(base) // 2],
    }
    print("-" * 78)
    print("拟合: wall = {:.2f}s + {:.4f}s/字   (每块上限 {} 字)".format(a, b, max_chars))
    print("逐拍 101 次调用外推: {:.1f} 分钟".format(per_beat / 60))
    print("按 {} 组批量外推: {:.1f} 分钟".format(len(groups), batched / 60))
    knob = [x for x in results if x["nfe_step"] == 16]
    thr = [x for x in results if x["threads"] == 8 and x["nfe_step"] == 32]
    if knob:
        print("nfe 32→16 提速: {:.2f}x".format(
            sorted(x["wall_s"] for x in base if x["tag"] == "median")[0] / knob[0]["wall_s"]))
    if thr:
        print("线程 16→8 变慢: {:.2f}x".format(
            thr[0]["wall_s"] / sorted(x["wall_s"] for x in base if x["tag"] == "median")[0]))

report["projection"] = proj
report["total_seconds"] = round(time.perf_counter() - start_all, 1)
(OUT / "bench_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print("报告:", OUT / "bench_report.json")
