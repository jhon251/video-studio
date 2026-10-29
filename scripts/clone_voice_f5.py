"""F5-TTS 声音克隆脚本（CPU）：用一段参考音频克隆说话人，按 v2 稿 10 段生成配音。

用法：
  python scripts/clone_voice_f5.py --ref <参考音频路径> --ref-text <参考音频的对应文本文件>
      --out build_v2/wav_clone   # 生成 10 段 wav
  然后：python scripts/build_video_v2.py --scenes --wav-dir wav_clone  重合成片

环境：.venv_tts（torch CPU + f5-tts）；模型经 HF_ENDPOINT=hf-mirror.com 下载。
"""
import argparse
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "production_002"
SRC = OUT / "V2_FINAL_SCRIPT_JARVIS.md"
MARKER = re.compile(r"\*\*〔(.+?)〕\*\*")

# torchaudio 2.11 无 soundfile 后端（torchcodec 需 FFmpeg DLL），用 soundfile 替换 load
import torchaudio as _ta
import soundfile as _sf
import torch as _torch


def _load_any(uri, frame_offset=0, num_frames=-1, normalize=True, channels_first=True):
    wav, sr = _sf.read(str(uri), dtype="float32")
    wav = _torch.from_numpy(wav)
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


def parse_sections() -> list[dict]:
    lines = SRC.read_text(encoding="utf-8").splitlines()
    sections, cur = [], None
    for ln in lines:
        m = MARKER.search(ln)
        if m:
            cur = {"title": m.group(1), "body": []}
            sections.append(cur)
        elif cur is not None:
            cur["body"].append(ln)
    for s in sections:
        s["text"] = re.sub(r"\*\*", "", "\n".join(s["body"])).strip()
        paras = [p.strip() for p in s["text"].splitlines() if p.strip()]
        s["speech"] = "".join(paras)
    return sections


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True, help="参考音频（3-10 分钟人声）")
    ap.add_argument("--ref-text", required=True, help="参考音频对应文本文件（UTF-8）")
    ap.add_argument("--out", default="build_v2/wav_clone")
    args = ap.parse_args()

    ref = Path(args.ref)
    if not ref.exists():
        sys.exit(f"参考音频不存在: {ref}")
    ref_text = Path(args.ref_text).read_text(encoding="utf-8").strip()
    out_dir = OUT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    from f5_tts.api import F5TTS

    models_dir = ROOT / "models" / "f5"
    ckpt = models_dir / "F5TTS_v1_Base" / "F5TTS_v1_Base" / "model_1250000.safetensors"
    vocab = models_dir / "F5TTS_v1_Base" / "F5TTS_v1_Base" / "vocab.txt"
    vocoder_dir = models_dir / "vocos-mel-24khz"
    if ckpt.exists() and vocab.exists() and (vocoder_dir / "config.yaml").exists():
        print("使用本地模型：", ckpt.parent)
        f5 = F5TTS(device="cpu", ckpt_file=str(ckpt), vocab_file=str(vocab),
                   vocoder_local_path=str(vocoder_dir))
    else:
        print("加载 F5-TTS（首次会自动从 hf-mirror 下载模型，约 1.3GB）...")
        f5 = F5TTS(device="cpu")

    sections = parse_sections()
    total = 0
    for i, s in enumerate(sections, 1):
        sid = f"S{i:02d}"
        print(f"--- 生成 {sid} {s['title']}（{len(s['speech'])} 字）---")
        wav, sr, seed = f5.infer(ref_file=str(ref), ref_text=ref_text,
                                 gen_text=s["speech"])
        outp = out_dir / f"{sid}.wav"
        import soundfile as sf

        sf.write(str(outp), wav, sr)
        dur = len(wav) / sr
        total += dur
        print(f"    {outp}  {dur:.1f}s  seed={seed}")
    print(f"10 段完成，合计 {total:.1f}s ≈ {total/60:.1f} 分钟")
    print(f"下一步：python scripts/build_video_v2.py --scenes --wav-dir {args.out}")


if __name__ == "__main__":
    main()
