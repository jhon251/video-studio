"""Run05 配音克隆驱动（F5-TTS / CPU）—— 按 narration_final(v1.3) 逐拍克隆音色。

设计要点（全部来自本机实测，见 output/run05/bench_tts_cpu/bench_report.json）：
  · 线程数 8（实测 8 线程比 16 线程略快，SMT 无益）；nfe_step 默认 16（实测比 32 快 2.17×）
  · 每拍一次调用，成本 ≈ 43.7s + 1.82s/字（nfe=32 实测拟合）；全片 98–101 拍预计 1.1–1.6h
  · 支持断点续跑（已存在的 wav 默认跳过）、小样本试听（--limit）、指定拍（--beats）
  · 参考音频会被 F5 自动裁到 ≤12s；因此 ref_text 必须与「被裁后那一段」严格对应
    —— 旧 smoke 就是拿 47s 音频配 188 字整段文本，导致 38 字只生成 2.53s

**只写入 output/run05/tts_clone/**，不触碰 run03/tts、prod01/tts 及任何冻结产物。

用法：
  # 1) 先试听 6 拍（约 4–6 分钟）
  python scripts/clone_voice_run05.py --ref voice_ref/ref_short.wav \
         --ref-text voice_ref/参考音专用短段.txt --limit 6

  # 2) 全片（后台跑，约 1.1–1.6h）
  python scripts/clone_voice_run05.py --ref voice_ref/ref_short.wav \
         --ref-text voice_ref/参考音专用短段.txt

  # 3) 只重做某几拍 / 强制重跑 / 拟合现有时间轴
  ... --beats S17-B02,S17-B03 --force --fix-duration
"""
import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

import numpy as _np
import torch
import torchaudio as _ta
import soundfile as _sf

ROOT = Path(__file__).resolve().parents[1]
NARR = ROOT / "output" / "run05" / "narration_final.json"
OUT = ROOT / "output" / "run05" / "tts_clone"
CHARS_PER_SEC = 4.32  # 由现状 20 字 / 4.63s 推得，仅用于一致性告警


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True, help="参考音频（建议 WAV，10–12s 连续人声）")
    ap.add_argument("--ref-text", required=True, help="参考音频对应文本（文件路径或直接文本）")
    ap.add_argument("--out", default=str(OUT), help="输出目录（默认 output/run05/tts_clone）")
    ap.add_argument("--limit", type=int, default=0, help="只做前 N 拍（试听用；0=全部）")
    ap.add_argument("--offset", type=int, default=0, help="跳过前 N 拍")
    ap.add_argument("--beats", default="", help="只做指定拍，逗号分隔，如 S17-B02,S17-B03")
    ap.add_argument("--nfe", type=int, default=16, help="NFE 步数，默认 16（32 更慢但可能更稳）")
    ap.add_argument("--threads", type=int, default=8, help="torch 线程数，默认 8")
    ap.add_argument("--force", action="store_true", help="已存在的 wav 也重做")
    ap.add_argument("--fix-duration", action="store_true",
                    help="用 fix_duration 拟合约现有时间轴时长（默认自然语速，只记录差值）")
    ap.add_argument("--verbose", action="store_true", help="打印 F5 内部信息与进度条")
    ap.add_argument("--loudness", choices=["match", "fixed", "none"], default="match",
                    help="响度归一：match=对齐 run03 同拍 RMS（默认，避免成片响度跳变）；"
                         "fixed=统一到 --target-dbfs；none=只做峰值防削波")
    ap.add_argument("--target-dbfs", type=float, default=-25.1,
                    help="--loudness fixed 的目标 RMS（dBFS），默认 -25.1（run03 实测均值）")
    args = ap.parse_args()

    ref = Path(args.ref)
    if not ref.is_absolute():
        cand = ROOT / args.ref
        ref = cand if cand.exists() else Path(args.ref)
    if not ref.exists():
        sys.exit("参考音频不存在: " + str(ref))
    rt = Path(args.ref_text)
    if rt.exists():
        ref_text = rt.read_text(encoding="utf-8").strip().replace("\n", "")
    else:
        ref_text = args.ref_text.strip()
    if not ref_text:
        sys.exit("ref_text 为空")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    info = _sf.info(str(ref))
    est_sec = len(ref_text) / CHARS_PER_SEC
    print("=" * 78)
    print("参考音频:", ref.name, "|", round(info.duration, 2), "s |", info.samplerate, "Hz |",
          info.channels, "ch")
    print("ref_text:", ref_text)
    print("ref_text 字数:", len(ref_text), "| 按 4.32 字/s 估算需", round(est_sec, 1), "s")
    if info.duration > 12.5:
        print("!! 参考音频 >12.5s，F5 会把它裁到约 12s；若 ref_text 对应的是整段，",
              "裁剪后文本与音频将不匹配（旧的 smoke 就是这样坏掉的）")
    if abs(info.duration - est_sec) > 4:
        print("!! 警告：音频时长({:.1f}s) 与 ref_text 估算时长({:.1f}s) 相差超过 4s，"
              "文本可能对不上被裁后的片段".format(info.duration, est_sec))
    print("=" * 78)

    rows = json.loads(NARR.read_text(encoding="utf-8"))
    beats = [r for r in rows if str(r.get("final", "")).strip()]
    if args.beats:
        want = [b.strip() for b in args.beats.split(",") if b.strip()]
        beats = [r for r in beats if r["beat"] in want]
    else:
        beats = beats[args.offset:]
        if args.limit:
            beats = beats[:args.limit]
    if not beats:
        sys.exit("选中的拍为空，检查 --beats/--limit")
    print("本次拍数:", len(beats), "| 目标文案总字数:",
          sum(len(r["final"]) for r in beats))

    from f5_tts.api import F5TTS  # noqa: E402

    models_dir = ROOT / "models" / "f5"
    ckpt = models_dir / "F5TTS_v1_Base" / "F5TTS_v1_Base" / "model_1250000.safetensors"
    vocab = models_dir / "F5TTS_v1_Base" / "F5TTS_v1_Base" / "vocab.txt"
    vocoder_dir = models_dir / "vocos-mel-24khz"

    torch.set_num_threads(args.threads)
    t0 = time.perf_counter()
    f5 = F5TTS(device="cpu", ckpt_file=str(ckpt), vocab_file=str(vocab),
               vocoder_local_path=str(vocoder_dir))
    print("模型加载 {:.1f}s | 线程 {} | nfe {}".format(
        time.perf_counter() - t0, torch.get_num_threads(), args.nfe))

    infokw = {"show_info": print, "progress": None} if args.verbose else \
             {"show_info": lambda *a, **k: None, "progress": None}

    # 预处理的参考时长（fix_duration 用）：F5 裁剪到 ≤12s 并加 50ms 静音
    ref_clip = min(info.duration, 12.0) + 0.05

    # 响度目标：match 模式读 run03 同拍的 RMS，缺失则用实测全局均值
    target_rms_map = {}
    if args.loudness == "match":
        run03_idx = ROOT / "output" / "run03" / "tts" / "tts_index.json"
        run03_root = ROOT / "output"
        if run03_idx.exists():
            _idx = json.loads(run03_idx.read_text(encoding="utf-8"))
            for b, rec in _idx.get("beats", {}).items():
                p = run03_root / str(rec.get("wav", "")).replace("\\", "/")
                if p.exists():
                    _a, _sr = _sf.read(str(p), dtype="float32", always_2d=True)
                    _m = _a.mean(axis=1) if _a.shape[1] > 1 else _a[:, 0]
                    target_rms_map[b] = float(_np.sqrt((_m ** 2).mean()))
            print("响度匹配: 已载入 run03 的 {} 拍参考 RMS（均值 {:.4f}）".format(
                len(target_rms_map),
                sum(target_rms_map.values()) / max(1, len(target_rms_map))))
        else:
            print("!! 未找到 run03 索引，回退到固定目标 {:.1f} dBFS".format(args.target_dbfs))
    DEFAULT_RMS = 10 ** (args.target_dbfs / 20)

    results, t_start = [], time.perf_counter()
    for i, r in enumerate(beats, 1):
        beat = r["beat"]
        wav_path = out_dir / (beat + ".wav")
        target = float(r.get("dur") or 0)
        if wav_path.exists() and not args.force:
            d, sr = _sf.read(str(wav_path), dtype="float32")
            dur = len(d) / sr
            results.append({"beat": beat, "dur": round(dur, 3), "target_dur": target,
                            "delta": round(dur - target, 3), "chars": len(r["final"]),
                            "seed": None, "skipped": True, "wav": wav_path.name,
                            "wall_s": 0.0})
            print("[{:3d}/{:3d}] {} 已存在，跳过（{:.2f}s / 目标 {:.2f}s）".format(
                i, len(beats), beat, dur, target))
            continue
        kw = dict(infokw)
        if args.fix_duration and target > 0:
            kw["fix_duration"] = ref_clip + target
        seed = 20260912 + i
        t = time.perf_counter()
        wav, sr, _spec = f5.infer(ref_file=str(ref), ref_text=ref_text,
                                  gen_text=r["final"], nfe_step=args.nfe, seed=seed, **kw)
        el = time.perf_counter() - t
        # 响度处理：F5 的 float 输出电平随参考音走高（实测 RMS ~0.25、尖峰 >1），
        # 若直接写 PCM_16 会被硬夹平；这里按响度目标整体缩放，再做峰值保险。
        raw_rms = float(_np.sqrt((wav ** 2).mean())) if len(wav) else 0.0
        raw_peak = float(_np.abs(wav).max()) if len(wav) else 0.0
        want = target_rms_map.get(beat, DEFAULT_RMS) if args.loudness != "none" else None
        gain = (want / raw_rms) if (want and raw_rms > 1e-9) else 1.0
        wav = (wav * gain).astype(wav.dtype)
        peak = float(_np.abs(wav).max()) if len(wav) else 0.0
        guard = False
        if peak > 0.98:
            g2 = 0.98 / peak
            wav = (wav * g2).astype(wav.dtype)
            gain *= g2
            guard = True
        _sf.write(str(wav_path), wav, sr)
        dur = len(wav) / sr
        final_rms = float(_np.sqrt((wav ** 2).mean())) if len(wav) else 0.0
        results.append({"beat": beat, "dur": round(dur, 3), "target_dur": target,
                        "delta": round(dur - target, 3), "chars": len(r["final"]),
                        "seed": seed, "skipped": False, "wav": wav_path.name,
                        "wall_s": round(el, 2), "raw_rms": round(raw_rms, 4),
                        "raw_peak": round(raw_peak, 4),
                        "want_rms": round(want, 4) if want else None,
                        "gain_applied": round(gain, 4), "peak_guard": guard,
                        "final_rms": round(final_rms, 4),
                        "final_peak": round(float(_np.abs(wav).max()), 4)})
        done = [x for x in results if not x["skipped"]]
        avg = sum(x["wall_s"] for x in done) / len(done)
        left = len(beats) - i
        print("[{:3d}/{:3d}] {} {:>2d}字 → {:.2f}s（目标 {:.2f}s，Δ{:+.2f}s）"
              " 耗时 {:.0f}s | 已完成均值 {:.0f}s/拍 | 剩余约 {:.0f} 分钟".format(
                  i, len(beats), beat, len(r["final"]), dur, target, dur - target, el,
                  avg, left * avg / 60))

    # ---- 索引（与 run03/tts/tts_index.json 同构）----
    rel_base = (ROOT / "output" / "run05").resolve()
    idx = {
        "voice": "f5-tts-clone:" + ref.stem,
        "rate": "natural",
        "engine": "F5-TTS_v1_Base (local, CPU)",
        "nfe_step": args.nfe,
        "threads": args.threads,
        "ref": {"wav": str(ref), "text": ref_text, "sec": round(info.duration, 3)},
        "fix_duration": bool(args.fix_duration),
        "loudness": args.loudness,
        "target_dbfs": args.target_dbfs,
        "total_s": round(sum(x["dur"] for x in results), 2),
        "beats": {},
    }
    for r, x in zip(beats, results):
        wav_abs = (out_dir / x["wav"]).resolve()
        try:
            rel = str(wav_abs.relative_to(rel_base)).replace("\\", "/")
        except ValueError:
            rel = x["wav"]
        idx["beats"][x["beat"]] = {
            "narration": list(r["final"]),
            "text": r["final"],
            "wav": rel,
            "wav_abs": str(wav_abs),
            "dur": x["dur"],
            "target_dur": x["target_dur"],
            "delta": x["delta"],
            "nfe_step": args.nfe,
            "seed": x["seed"],
        }
    (out_dir / "tts_index_clone.json").write_text(
        json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")

    rep = {
        "engine": "F5-TTS_v1_Base CPU",
        "nfe_step": args.nfe, "threads": args.threads,
        "fix_duration": bool(args.fix_duration),
        "ref": {"wav": str(ref), "sec": round(info.duration, 3),
                "ref_text": ref_text, "chars": len(ref_text)},
        "beats_done": len(results),
        "wall_s_total": round(time.perf_counter() - t_start, 1),
        "sum_new_dur": round(sum(x["dur"] for x in results), 2),
        "sum_target_dur": round(sum(x["target_dur"] for x in results), 2),
        "beats": results,
    }
    (out_dir / "clone_duration_report.json").write_text(
        json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")

    print("-" * 78)
    _fr = [x["final_rms"] for x in results if x.get("final_rms")]
    if _fr:
        print("响度: 目标模式 {} | 成品 RMS {:.4f}–{:.4f}（{:.1f}–{:.1f} dBFS）| 峰值 ≤ {:.3f}".format(
            args.loudness, min(_fr), max(_fr), 20 * math.log10(max(min(_fr), 1e-9)),
            20 * math.log10(max(max(_fr), 1e-9)),
            max(x.get("final_peak", 0) for x in results)))
    print("完成 {} 拍 | 新音频合计 {:.2f}s | 现有时间轴对应 {:.2f}s | Δ{:+.2f}s".format(
        len(results), rep["sum_new_dur"], rep["sum_target_dur"],
        rep["sum_new_dur"] - rep["sum_target_dur"]))
    worst = sorted(results, key=lambda x: -abs(x["delta"]))[:8]
    print("时长偏差最大的拍：")
    for x in worst:
        print("   {:10s} 新 {:.2f}s / 目标 {:.2f}s  Δ{:+.2f}s  ({}字)".format(
            x["beat"], x["dur"], x["target_dur"], x["delta"], x["chars"]))
    print("索引:", out_dir / "tts_index_clone.json")
    print("时长报告:", out_dir / "clone_duration_report.json")
    print("总耗时 {:.1f} 分钟".format(rep["wall_s_total"] / 60))


if __name__ == "__main__":
    main()
