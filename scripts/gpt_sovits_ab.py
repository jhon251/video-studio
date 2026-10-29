"""GPT-SoVITS 与 F5-TTS 的同拍 A/B 驱动：调用本地 api_v2 的 /tts 逐拍合成。

设计要点（与 clone_voice_run05.py 保持一致，便于横向对比）：
  · 文本取自 output/run05/narration_final.json（v1.3），与 F5 侧完全相同
  · 默认 text_split_method=cut0（不切分），与 F5 的"整拍一次生成"对齐；
    cut5 会按标点切 fragment 并在之间插 fragment_interval(默认 0.3s) 静音，会干扰时长对比
  · 默认 sample_steps=32（官方 wiki：音质最佳）、repetition_penalty=1.35（官方默认，针对重复漏字）
  · --loudness match：逐拍对齐 run03 同拍 RMS，避免把"响度差"误判成"音质差"
  · 记录 wall/dur/字速/内部停顿/电平，并输出与 F5 目录的对比表
  · 可选 --set-sovits/--set-gpt 在合成前切换版本权重（api_v2 提供 /set_sovits_weights）

用法：
  python scripts/gpt_sovits_ab.py --beats S17-B02,S12-B02,S27-B01 \
      --ref C:\\mp4agent\\voice_ref\\ref_win3.wav --ref-text C:\\mp4agent\\voice_ref\\ref_win3.txt \
      --out output/run05/tts_gsv_v3
"""
import argparse
import json
import math
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import soundfile as sf

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
NARR = ROOT / "output" / "run05" / "narration_final.json"


def post_json(url, payload, timeout=1800):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read()


def get(url, timeout=60):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", "replace")


def measure(path):
    d, sr = sf.read(str(path), dtype="float32", always_2d=True)
    m = d.mean(axis=1) if d.shape[1] > 1 else d[:, 0]
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
            if (j - i) * 0.02 >= 0.25 and i > 2 and j < n - 2:
                gaps.append((round(i * 0.02, 2), round((j - i) * 0.02, 2)))
            i = j
        else:
            i += 1
    return {"dur": dur, "sr": sr, "rms": float(np.sqrt((m ** 2).mean())),
            "peak": float(np.abs(m).max()), "gaps": gaps,
            "gap_total": round(sum(g[1] for g in gaps), 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:9880")
    ap.add_argument("--ref", required=True)
    ap.add_argument("--ref-text", required=True)
    ap.add_argument("--beats", default="S17-B02,S12-B02,S27-B01")
    ap.add_argument("--out", required=True)
    ap.add_argument("--text-lang", default="zh")
    ap.add_argument("--prompt-lang", default="zh")
    ap.add_argument("--text-split", default="cut0")
    ap.add_argument("--sample-steps", type=int, default=32)
    ap.add_argument("--repetition-penalty", type=float, default=1.35)
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=20260912)
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--top-k", type=int, default=15)
    ap.add_argument("--top-p", type=float, default=1.0)
    ap.add_argument("--loudness", choices=["match", "none"], default="match")
    ap.add_argument("--set-sovits", default="", help="可选：合成前切换 SoVITS(s2) 权重，绝对路径或相对包根")
    ap.add_argument("--set-gpt", default="", help="可选：合成前切换 GPT(s1) 权重")
    ap.add_argument("--label", default="", help="本次配置标签，写进报告")
    args = ap.parse_args()

    ref = Path(args.ref)
    if not ref.is_absolute():
        ref = ROOT / args.ref
    rt = Path(args.ref_text)
    ref_text = (rt.read_text(encoding="utf-8") if rt.exists() else args.ref_text).strip().replace("\n", "")
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)

    # 健康检查
    try:
        st, body = get(args.api + "/docs", timeout=15)
        print("API 存活:", args.api, "HTTP", st)
    except Exception as e:
        sys.exit("API 不可达: " + str(e))

    if args.set_gpt:
        try:
            st, body = get(args.api + "/set_gpt_weights?weights_path=" + urllib.parse.quote(args.set_gpt))
            print("set_gpt_weights:", st, body)
        except urllib.error.HTTPError as e:
            print("!! set_gpt_weights 失败:", e.code, e.read().decode("utf-8", "replace")[:300])
    if args.set_sovits:
        try:
            st, body = get(args.api + "/set_sovits_weights?weights_path=" + urllib.parse.quote(args.set_sovits))
            print("set_sovits_weights:", st, body)
        except urllib.error.HTTPError as e:
            print("!! set_sovits_weights 失败:", e.code, e.read().decode("utf-8", "replace")[:300])

    rows = json.loads(NARR.read_text(encoding="utf-8"))
    want = [b.strip() for b in args.beats.split(",") if b.strip()]
    beats = [r for r in rows if r["beat"] in want and str(r.get("final", "")).strip()]
    if not beats:
        sys.exit("没有匹配的拍")

    # 响度目标（与 clone_voice_run05 一致：对齐 run03 同拍 RMS）
    tgt = {}
    if args.loudness == "match":
        idx = json.loads((ROOT / "output" / "run03" / "tts" / "tts_index.json").read_text(encoding="utf-8"))
        for b, rec in idx["beats"].items():
            p = ROOT / "output" / str(rec["wav"]).replace("\\", "/")
            if p.exists():
                a, _ = sf.read(str(p), dtype="float32", always_2d=True)
                m = a.mean(axis=1) if a.shape[1] > 1 else a[:, 0]
                tgt[b] = float(np.sqrt((m ** 2).mean()))

    print("=" * 78)
    print("GPT-SoVITS A/B | 标签:", args.label or "(未命名)")
    print("参考:", ref.name, "| ref_text {} 字".format(len(ref_text)))
    print("配置: text_split={} sample_steps={} rep_pen={} speed={} seed={} loudness={}".format(
        args.text_split, args.sample_steps, args.repetition_penalty, args.speed, args.seed, args.loudness))
    print("=" * 78)

    results, t0 = [], time.perf_counter()
    for i, r in enumerate(beats, 1):
        payload = {
            "text": r["final"], "text_lang": args.text_lang,
            "ref_audio_path": str(ref), "prompt_text": ref_text, "prompt_lang": args.prompt_lang,
            "top_k": args.top_k, "top_p": args.top_p, "temperature": args.temperature,
            "text_split_method": args.text_split, "batch_size": 1, "batch_threshold": 0.75,
            "split_bucket": True, "speed_factor": args.speed, "fragment_interval": 0.3,
            "seed": args.seed + i, "media_type": "wav", "streaming_mode": False,
            "parallel_infer": True, "repetition_penalty": args.repetition_penalty,
            "sample_steps": args.sample_steps, "super_sampling": False,
        }
        t = time.perf_counter()
        try:
            st, raw = post_json(args.api + "/tts", payload)
        except urllib.error.HTTPError as e:
            print("[{}/{}] {} 失败 HTTP {}: {}".format(i, len(beats), r["beat"], e.code,
                                                       e.read().decode("utf-8", "replace")[:400]))
            continue
        el = time.perf_counter() - t
        tmp = out / (r["beat"] + ".raw.wav")
        tmp.write_bytes(raw)
        a, sr = sf.read(str(tmp), dtype="float32", always_2d=True)
        m = a.mean(axis=1) if a.shape[1] > 1 else a[:, 0]
        want_rms = tgt.get(r["beat"]) if args.loudness == "match" else None
        gain = 1.0
        if want_rms:
            cur = float(np.sqrt((m ** 2).mean()))
            if cur > 1e-9:
                gain = want_rms / cur
        m = (m * gain).astype(np.float32)
        peak = float(np.abs(m).max())
        guard = False
        if peak > 0.98:
            m = (m * (0.98 / peak)).astype(np.float32)
            guard = True
        final_p = out / (r["beat"] + ".wav")
        sf.write(str(final_p), m, sr, subtype="PCM_16")
        tmp.unlink(missing_ok=True)
        info = measure(final_p)
        info.update({"beat": r["beat"], "chars": len(r["final"]), "wall_s": round(el, 2),
                     "gain": round(gain, 3), "peak_guard": guard,
                     "target_dur": float(r.get("dur") or 0),
                     "chars_per_sec": round(len(r["final"]) / info["dur"], 2)})
        results.append(info)
        print("[{}/{}] {} {}字 → {:.2f}s（目标 {:.2f}s） 耗时 {:.1f}s | 字速 {:.2f} | 内部停顿 {} 个".format(
            i, len(beats), r["beat"], len(r["final"]), info["dur"], info["target_dur"],
            el, info["chars_per_sec"], len(info["gaps"])))

    if not results:
        sys.exit("全部失败")
    rep = {"label": args.label, "engine": "GPT-SoVITS (api_v2)", "api": args.api,
           "ref": str(ref), "ref_text": ref_text, "text_split_method": args.text_split,
           "sample_steps": args.sample_steps, "repetition_penalty": args.repetition_penalty,
           "speed_factor": args.speed, "seed_base": args.seed, "loudness": args.loudness,
           "beats": results, "wall_total_s": round(time.perf_counter() - t0, 1),
           "sum_dur": round(sum(x["dur"] for x in results), 3),
           "sum_target": round(sum(x["target_dur"] for x in results), 3)}
    (out / "gsv_report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print("-" * 78)
    print("合计 {:.2f}s（现有时间轴 {:.2f}s，Δ{:+.2f}s）| 总耗时 {:.1f} 分钟".format(
        rep["sum_dur"], rep["sum_target"], rep["sum_dur"] - rep["sum_target"], rep["wall_total_s"] / 60))
    print("报告:", out / "gsv_report.json")


if __name__ == "__main__":
    main()
