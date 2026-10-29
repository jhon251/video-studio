"""F5-TTS 冒烟测试：以 Huihui 的 S01 配音为参考音色，克隆一句短文本。"""
import os
import sys

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path

OUT = Path("output/production_002/build_v2")
ROOT = Path(__file__).resolve().parents[1]

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

from f5_tts.api import F5TTS

models_dir = ROOT / "models" / "f5"
ckpt = models_dir / "F5TTS_v1_Base" / "F5TTS_v1_Base" / "model_1250000.safetensors"
vocab = models_dir / "F5TTS_v1_Base" / "F5TTS_v1_Base" / "vocab.txt"
vocoder_dir = models_dir / "vocos-mel-24khz"
print("加载 F5-TTS（本地模型）...")
f5 = F5TTS(device="cpu", ckpt_file=str(ckpt), vocab_file=str(vocab),
           vocoder_local_path=str(vocoder_dir))

ref_file = OUT / "wav" / "S01.wav"
ref_text = (OUT / "tts" / "S01.txt").read_text(encoding="utf-8").strip()
gen_text = "你好，这是一段声音克隆的冒烟测试。如果这句话听起来像参考音色，就说明整条链路是通的。"

print("推理中（CPU，短句约 1-3 分钟）...")
wav, sr, seed = f5.infer(ref_file=str(ref_file), ref_text=ref_text, gen_text=gen_text)
import soundfile as sf

outp = OUT / "smoke_clone.wav"
sf.write(str(outp), wav, sr)
print(f"OK: {outp} | sr={sr} | {len(wav)/sr:.1f}s | seed={seed}")
