"""GPT-SoVITS v3 逐拍合成驱动（走官方 WebUI 推理路径 inference_webui.py，不启服务）。

为什么不用 api_v2：本整合包（20250228 v3lora）里的 TTS_infer_pack/TTS.py 只有 v1/v2 分支，
没有 v3/v4/v2Pro 与 sample_steps —— 包内 api_v2 是 v2 时代管线。v3 的官方入口是
GPT_SoVITS/inference_webui.py（WebUI 与 inference_cli.py 都走它）。

关键实现（来自读源码）：
  · change_sovits_weights 是生成器函数，必须用 next(...) 触发（官方在 import 时也是这么做的）
  · device/is_half 自动判定：无 CUDA → cpu / is_half=False
  · v3 需要 BigVGAN：model_version=="v3" 时在首次推理惰性 init_bigvgan(use_cuda_kernel=False)
  · sample_steps 是 v3 专属的"电音"旋钮（官方 UI 原文：采样步数，如果觉得电，提高试试）
  · get_tts_wav 生成器：list(gen)[-1] 才是完整音频

用法（用包内自带 Python 运行）：
  & "<pkg>\\runtime\\python.exe" scripts\\gsv_run.py --beats S27-B01 --sample-steps 32 \
      --out output/run05/tts_gsv_v3_smoke
"""
import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

PKG_DEFAULT = r"C:\mp4agent\gpt-sovits\GPT-SoVITS-v3lora-20250228"
VS = Path(r"C:\mp4agent\video-studio")


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
    ap.add_argument("--package", default=PKG_DEFAULT)
    ap.add_argument("--gpt", default="GPT_SoVITS/pretrained_models/s1v3.ckpt")
    ap.add_argument("--sovits", default="GPT_SoVITS/pretrained_models/s2Gv3.pth")
    ap.add_argument("--ref", required=True)
    ap.add_argument("--ref-text", required=True)
    ap.add_argument("--beats", default="S17-B02,S12-B02,S27-B01")
    ap.add_argument("--out", required=True)
    ap.add_argument("--how-to-cut", default="不切", help="不切 / 按标点切 等 i18n 键")
    ap.add_argument("--text-lang-val", default="all_zh",
                    help="文本语言（FunASR 值）：all_zh=全部按中文 / zh=中英混合 / auto=多语种混合")
    ap.add_argument("--prompt-lang-val", default="all_zh",
                    help="参考音语言：all_zh / zh / auto 等")
    ap.add_argument("--sample-steps", type=int, default=32)
    ap.add_argument("--top-k", type=int, default=20)
    ap.add_argument("--top-p", type=float, default=0.6)
    ap.add_argument("--temperature", type=float, default=0.6)
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--pause-second", type=float, default=0.3)
    ap.add_argument("--if-sr", action="store_true", help="v3 输出超分（24k→48k）")
    ap.add_argument("--seed", type=int, default=20260912)
    ap.add_argument("--loudness", choices=["match", "none"], default="match")
    ap.add_argument("--label", default="")
    ap.add_argument("--expect-version", default="", help="非空时断言检测到的 model_version（如 v3）")
    ap.add_argument("--force", action="store_true", help="已存在的 wav 也重做")
    ap.add_argument("--index", default="", help="额外写出 run03 同构索引的路径（默认输出目录下 tts_index.json）")
    ap.add_argument("--narr", default="output/run05/narration_final.json",
                    help="文案真源 JSON（默认 v1.3；v1.6.1 生产用 output/run05/narration_final_v16.json）")
    args = ap.parse_args()

    pkg = Path(args.package).resolve()
    os.chdir(pkg)
    sys.path.insert(0, str(pkg))
    sys.path.insert(0, str(pkg / "GPT_SoVITS"))   # inference_webui 内部用 from text.../AR... 导入
    sys.path.insert(0, str(pkg / "GPT_SoVITS" / "BigVGAN"))  # bigvgan.py 内部 import activations 是扁平导入
    os.environ["is_half"] = "False"
    os.environ.setdefault("language", "zh_CN")
    print("包根:", pkg)

    t_imp = time.perf_counter()
    import GPT_SoVITS.inference_webui as gsv

    print("import 完成 {:.1f}s | device={} is_half={} version(env)={}".format(
        time.perf_counter() - t_imp, gsv.device, gsv.is_half, gsv.version))

    gpt = str((pkg / args.gpt).resolve()) if not os.path.isabs(args.gpt) else args.gpt
    sov = str((pkg / args.sovits).resolve()) if not os.path.isabs(args.sovits) else args.sovits
    t = time.perf_counter()
    try:
        next(gsv.change_sovits_weights(sov))   # 生成器：必须 next() 才真正执行加载
    except StopIteration:
        pass
    gsv.change_gpt_weights(gpt)
    print("加载权重 {:.1f}s | version={} model_version={} | BigVGAN={}".format(
        time.perf_counter() - t, gsv.version, gsv.model_version,
        "loaded" if gsv.bigvgan_model is not None else "None(将在首次推理惰性加载)"))
    assert (not args.expect_version) or gsv.model_version == args.expect_version, \
        "期望 {} 实际 {}".format(args.expect_version, gsv.model_version)

    def key_for(val):
        for k, v in gsv.dict_language.items():
            if v == val:
                return k
        raise SystemExit("语言值不支持: {}（可选 {}）".format(val, sorted(set(gsv.dict_language.values()))))

    zh = key_for(args.text_lang_val)
    plang = key_for(args.prompt_lang_val)
    cut = args.how_to_cut
    print("语言: prompt={}（{}）| text={}（{}）| 切分: {}".format(
        plang, args.prompt_lang_val, zh, args.text_lang_val, cut))

    ref = Path(args.ref)
    if not ref.is_absolute():
        ref = VS / args.ref
    rt = Path(args.ref_text)
    ref_text = (rt.read_text(encoding="utf-8") if rt.exists() else args.ref_text).strip().replace("\n", "")
    out = Path(args.out)
    if not out.is_absolute():
        out = VS / args.out
    out.mkdir(parents=True, exist_ok=True)

    rows = json.loads((VS / args.narr).read_text(encoding="utf-8"))
    print("文案真源:", (VS / args.narr).as_posix())
    want = [b.strip() for b in args.beats.split(",") if b.strip()]
    if not want or want == ["ALL"]:
        beats = [r for r in rows if str(r.get("final", "")).strip()]   # 全片，按文件（canonical）顺序
    else:
        beats = [r for r in rows if r["beat"] in want and str(r.get("final", "")).strip()]
    if not beats:
        sys.exit("没有匹配的拍")

    tgt = {}
    if args.loudness == "match":
        idx = json.loads((VS / "output/run03/tts/tts_index.json").read_text(encoding="utf-8"))
        for b, rec in idx["beats"].items():
            p = VS / "output" / str(rec["wav"]).replace("\\", "/")
            if p.exists():
                a, _ = sf.read(str(p), dtype="float32", always_2d=True)
                m = a.mean(axis=1) if a.shape[1] > 1 else a[:, 0]
                tgt[b] = float(np.sqrt((m ** 2).mean()))

    print("=" * 78)
    print("GPT-SoVITS 合成 | 标签:", args.label or "(未命名)")
    print("参考:", ref.name, "| prompt {} 字".format(len(ref_text)))
    print("参数: sample_steps={} top_k={} top_p={} temp={} speed={} if_sr={} loudness={}".format(
        args.sample_steps, args.top_k, args.top_p, args.temperature, args.speed, args.if_sr, args.loudness))
    print("=" * 78)

    results, t0 = [], time.perf_counter()
    for i, r in enumerate(beats, 1):
        fp = out / (r["beat"] + ".wav")
        if fp.exists() and not args.force:
            info = measure(fp)
            td = float(r.get("dur") or 0)
            info.update({"beat": r["beat"], "chars": len(r["final"]), "wall_s": 0.0,
                         "gain": 1.0, "peak_guard": False, "skipped": True,
                         "target_dur": td, "delta": round(info["dur"] - td, 3),
                         "chars_per_sec": round(len(r["final"]) / info["dur"], 2)})
            results.append(info)
            print("[{:3d}/{:3d}] {} 已存在，跳过（{:.2f}s）".format(i, len(beats), r["beat"], info["dur"]))
            continue
        gsv.set_seed(args.seed + i)
        t = time.perf_counter()
        gen = gsv.get_tts_wav(
            ref_wav_path=str(ref), prompt_text=ref_text, prompt_language=plang,
            text=r["final"], text_language=zh, how_to_cut=cut,
            top_k=args.top_k, top_p=args.top_p, temperature=args.temperature,
            speed=args.speed, sample_steps=args.sample_steps, if_sr=args.if_sr,
            pause_second=args.pause_second,
        )
        last = None
        for item in gen:
            last = item
        el = time.perf_counter() - t
        if last is None:
            print("[{}/{}] {} 无输出".format(i, len(beats), r["beat"]))
            continue
        sr, audio = last
        m = np.asarray(audio, dtype=np.float32).reshape(-1)
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
        sf.write(str(fp), m, int(sr), subtype="PCM_16")
        info = measure(fp)
        td = float(r.get("dur") or 0)
        info.update({"beat": r["beat"], "chars": len(r["final"]), "wall_s": round(el, 2),
                     "gain": round(gain, 3), "peak_guard": guard, "skipped": False,
                     "target_dur": td, "delta": round(info["dur"] - td, 3),
                     "chars_per_sec": round(len(r["final"]) / info["dur"], 2)})
        results.append(info)
        done = [x for x in results if not x.get("skipped")]
        avg = sum(x["wall_s"] for x in done) / max(1, len(done))
        print("[{:3d}/{:3d}] {} {}字 → {:.2f}s（目标 {:.2f}s）| 耗时 {:.1f}s | 均值 {:.1f}s/拍 | 剩余约 {:.0f} 分钟".format(
            i, len(beats), r["beat"], len(r["final"]), info["dur"], info["target_dur"],
            el, avg, (len(beats) - i) * avg / 60))

    if not results:
        sys.exit("全部失败")
    rep = {"label": args.label, "engine": "GPT-SoVITS v3 (inference_webui, CPU)",
           "package": str(pkg), "gpt": args.gpt, "sovits": args.sovits,
           "ref": str(ref), "ref_text": ref_text, "how_to_cut": cut,
           "sample_steps": args.sample_steps, "top_k": args.top_k, "top_p": args.top_p,
           "temperature": args.temperature, "speed": args.speed, "if_sr": args.if_sr,
           "seed_base": args.seed, "loudness": args.loudness, "beats": results,
           "wall_total_s": round(time.perf_counter() - t0, 1),
           "sum_dur": round(sum(x["dur"] for x in results), 3),
           "sum_target": round(sum(x["target_dur"] for x in results), 3)}
    (out / "gsv_report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")

    # run03 同构索引（便于下游按同一 schema 消费）
    by_beat = {x["beat"]: x for x in results}
    rel_base = (VS / "output" / "run05").resolve()
    idx = {"voice": "gpt-sovits-{}:{}".format(gsv.model_version, ref.stem),
           "rate": "natural",
           "engine": "GPT-SoVITS {} (CPU, inference_webui)".format(gsv.model_version),
           "sample_steps": args.sample_steps, "top_k": args.top_k, "top_p": args.top_p,
           "temperature": args.temperature, "speed": args.speed, "how_to_cut": cut,
           "ref": {"wav": str(ref), "text": ref_text, "sec": round(sf.info(str(ref)).duration, 3)},
           "loudness": args.loudness,
           "total_s": round(sum(x["dur"] for x in results), 2),
           "beats": {}}
    for r in beats:
        x = by_beat.get(r["beat"])
        if not x:
            continue
        wa = (out / (r["beat"] + ".wav")).resolve()
        try:
            rel = str(wa.relative_to(rel_base)).replace("\\", "/")
        except ValueError:
            rel = r["beat"] + ".wav"
        idx["beats"][r["beat"]] = {
            "narration": list(r["final"]), "text": r["final"], "wav": rel, "wav_abs": str(wa),
            "dur": x["dur"], "target_dur": x["target_dur"], "delta": x["delta"],
            "chars": x["chars"], "rms": round(x["rms"], 5), "gaps": x["gaps"],
        }
    ip = Path(args.index) if args.index else (out / "tts_index.json")
    if not ip.is_absolute():
        ip = VS / ip
    ip.parent.mkdir(parents=True, exist_ok=True)
    ip.write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")

    print("-" * 78)
    print("合计 {:.2f}s（现有时间轴 {:.2f}s，Δ{:+.2f}s）| 总耗时 {:.1f} 分钟".format(
        rep["sum_dur"], rep["sum_target"], rep["sum_dur"] - rep["sum_target"], rep["wall_total_s"] / 60))
    print("报告:", out / "gsv_report.json")
    print("索引:", ip)


if __name__ == "__main__":
    main()
