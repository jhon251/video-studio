"""P0-1 VO 生成（F5-TTS adapter + 段合成 + 合并 + loudnorm + provenance）。

设计契约（docs/STAGE32B_DESIGN.md §4/§5/§14/§15/§18）：
- 按句/segment 生成；失败重试 2 次；仍失败显式 ERROR，不静默跳过；
- 文本逐字来自冻结稿（不修改）；
- 记录每段 text/file/duration/sha/engine；
- 合成 voiceover.wav 并做统一 loudnorm；
- 幂等：输入指纹不变则跳过。
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FFMPEG = ROOT / "bin" / "ffmpeg.exe"
F5_DIR = ROOT / "models" / "f5"
DEFAULT_REF = ROOT / "output" / "stage32b" / "assets" / "ref_voice.wav"
DEFAULT_REF_TEXT = ROOT / "output" / "stage32b" / "assets" / "ref_voice.txt"

# Phase 3-B：响度目标取自 core.audio 的统一契约（不再写死字符串）
from ..core.audio import loudnorm_filter  # noqa: E402

_f5 = None


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _f5_model():
    global _f5
    if _f5 is None:
        import torchaudio as _ta
        import soundfile as _sf
        import torch as _t

        def _load_any(uri, frame_offset=0, num_frames=-1, normalize=True, channels_first=True):
            wav, sr = _sf.read(str(uri), dtype="float32")
            wav = _t.from_numpy(wav)
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
        ckpt = F5_DIR / "F5TTS_v1_Base" / "F5TTS_v1_Base" / "model_1250000.safetensors"
        vocab = F5_DIR / "F5TTS_v1_Base" / "F5TTS_v1_Base" / "vocab.txt"
        vocoder = F5_DIR / "vocos-mel-24khz"
        _f5 = F5TTS(device="cpu", ckpt_file=str(ckpt), vocab_file=str(vocab),
                    vocoder_local_path=str(vocoder))
    return _f5


def split_sentences(text: str) -> list[str]:
    """按标点切句（保留引号内完整）；空句过滤。"""
    parts = re.split(r"(?<=[。！？；])", text)
    out = [p.strip() for p in parts if p.strip()]
    if not out and text.strip():
        out = [text.strip()]
    return out


def synth_segment(text: str, ref_file: Path, ref_text: str) -> tuple[Path | None, str]:
    """单句合成：失败重试 2 次；仍失败返回 (None, error)。"""
    import soundfile as sf
    model = _f5_model()
    last_err = ""
    for attempt in range(3):
        try:
            wav, sr, _ = model.infer(ref_file=str(ref_file), ref_text=ref_text,
                                     gen_text=text)
            return wav, sr, ""
        except Exception as e:  # noqa: BLE001
            last_err = f"{type(e).__name__}: {e}"
            time.sleep(3 * (attempt + 1))
    return None, 0, last_err


def parse_narration(text: str) -> list[dict]:
    """解析冻结稿：跳过标题行，按【Sxx】切镜头，剥离标记，逐句切分。

    返回 [{shot_id, text, sentences:[...]}]；文本逐字保留（仅剥离【Sxx】行标记）。
    """
    items, cur = [], None
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith(">"):
            continue
        m = re.match(r"^【(S\d+)】(.*)$", s)
        if m:
            cur = {"shot_id": m.group(1), "text": m.group(2).strip()}
            items.append(cur)
        elif cur is not None:
            cur["text"] = (cur["text"] + s).strip()
    out = []
    for it in items:
        for sent in split_sentences(it["text"]):
            out.append({"shot_id": it["shot_id"], "text": sent})
    return out


def build_vo(narration_path: Path, out_dir: Path, ref_file: Path | None = None,
             ref_text_path: Path | None = None, force: bool = False) -> dict:
    """P0-1 主流程。"""
    text = narration_path.read_text(encoding="utf-8")
    units = parse_narration(text)
    ref_file = Path(ref_file) if ref_file else DEFAULT_REF
    ref_text = (Path(ref_text_path).read_text(encoding="utf-8").strip()
                if ref_text_path else DEFAULT_REF_TEXT.read_text(encoding="utf-8").strip())

    fp_in = hashlib.sha256(
        (text + str(ref_file) + ref_text).encode("utf-8")).hexdigest()[:16]
    seg_dir = out_dir / "audio" / "segments"
    seg_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifests" / "vo_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    if manifest_path.exists() and not force:
        m = json.loads(manifest_path.read_text(encoding="utf-8"))
        if m.get("input_fingerprint") == fp_in and all(
                (out_dir / s["audio_file"]).exists() for s in m["segments"]):
            print(f"VO 已存在（指纹一致），跳过：{manifest_path}")
            return m

    import soundfile as sf
    import numpy as np
    segments, errors, all_audio = [], [], []
    t0 = time.time()
    for i, unit in enumerate(units, 1):
        sent = unit["text"]
        seg_id = f"VO_{unit['shot_id']}_{i:03d}"
        wav, sr, err = synth_segment(sent, ref_file, ref_text)
        if wav is None:
            errors.append({"segment_id": seg_id, "shot_id": unit["shot_id"],
                           "text": sent, "error": err})
            segments.append({"id": seg_id, "shot_id": unit["shot_id"], "text": sent,
                             "status": "ERROR", "error": err, "audio_file": "",
                             "start": 0.0, "end": 0.0, "duration": 0.0})
            continue
        fname = f"{seg_id}.wav"
        p = seg_dir / fname
        sf.write(str(p), wav, sr)
        dur = float(len(wav)) / sr
        segments.append({"id": seg_id, "shot_id": unit["shot_id"], "text": sent,
                         "status": "OK", "audio_file": f"audio/segments/{fname}",
                         "sample_rate": sr, "duration": round(dur, 3),
                         "sha": _sha256(p), "engine": "f5-tts"})
        all_audio.append(wav)
        print(f"[{i}/{len(units)}] {seg_id} {dur:.2f}s {sent[:18]}")

    # 合并 + loudnorm
    vo_raw = out_dir / "audio" / "voiceover_raw.wav"
    vo_final = out_dir / "voiceover.wav"
    if all_audio:
        joined = np.concatenate(all_audio)
        sf.write(str(vo_raw), joined, sr)
        subprocess.run([str(FFMPEG), "-y", "-i", str(vo_raw),
                        "-af", loudnorm_filter(),
                        "-ar", "48000", str(vo_final)],
                       capture_output=True, check=True)
    total_dur = round(sum(s["duration"] for s in segments), 3)
    manifest = {
        "input_fingerprint": fp_in,
        "narration_file": str(narration_path),
        "narration_sha": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "engine": "f5-tts", "ref_audio": str(ref_file),
        "ref_text_sha": hashlib.sha256(ref_text.encode("utf-8")).hexdigest(),
        "segments": segments, "errors": errors,
        "total_duration": total_dur,
        "voiceover": "voiceover.wav",
        "elapsed_s": round(time.time() - t0, 1),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                             encoding="utf-8")
    print(f"VO 完成：{len(segments) - len(errors)}/{len(segments)} 段成功，"
          f"总时长 {total_dur:.1f}s，错误 {len(errors)}")
    return manifest
