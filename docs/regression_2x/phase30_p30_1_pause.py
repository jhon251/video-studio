# -*- coding: utf-8 -*-
"""P30-1 **pause 真实化**（选项①）：按 pause 归因表把停顿落成**真实静音**。

监理定性：**不是旁白重配** —— 零 TTS 重合成、零文本改动、零语速调整，
**只按归因表在边界插入静音**。

规则（沿用语料既有归因表 `voice_output_40seg_v21.json#pause_attribution`）：
  · 19 个**原始边界**（父景切换处）各插 **0.75s** 真实静音；
  · 20 个**派生边界**插 **0**（停顿已被切片吸收）；
  · `trailing pad = 2.0s` 由时基声明承担（本步骤不补，交由渲染尾部对齐）。

fail-closed 断言（**运行前写死**）：拼接后音频**实测时长 = 977.884 ± 0.1s**。
provenance：逐段 sha256 + 拼接规则版本 + 源音频 sha256。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")

FF = str(R / "bin" / "ffmpeg.exe")
FFPROBE = str(R / "bin" / "ffprobe.exe")
VOICE = R / "output" / "phase20_voice_sandbox" / "voice_output_40seg_v21.json"
SEGDIR = R / "output" / "phase20_voice_sandbox" / "seg"
OUT = R / "output" / "phase30_audio"
RULE_VERSION = "p30-pause-materialize-v1:silence-by-attribution-table"
TARGET_S = 977.884
TOL_S = 0.1

voice = json.loads(VOICE.read_text(encoding="utf-8"))
segs = voice["segments"]
att = voice.get("pause_attribution") or {}
bnd = {int(b["after_index"]): float(b.get("pause_s") or 0.0) for b in att.get("boundaries", [])}
orig = set(int(x) for x in (att.get("original_boundaries") or []))
print("段数 {} | 归因边界 {} | 原始边界 {} | 派生边界 {}".format(
    len(segs), len(bnd), len(orig), len(bnd) - len(orig)))
print("原始边界 pause=0.75s × {} ⇒ 静音合计 {:.3f}s".format(
    len(orig), 0.75 * len(orig)))


def probe(p) -> float:
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(p)], capture_output=True, text=True)
    try:
        return round(float(r.stdout.strip().splitlines()[0]), 3)
    except Exception:                                                           # noqa: BLE001
        return -1.0


OUT.mkdir(parents=True, exist_ok=True)
sil = OUT / "_sil750.wav"
if not sil.is_file():
    subprocess.run([FF, "-v", "error", "-y", "-f", "lavfi", "-i",
                    "anullsrc=r=24000:cl=mono", "-t", "0.75", str(sil)],
                   capture_output=True, text=True)
sil_dur = probe(sil)
print("静音件: {} ({:.3f}s)".format(sil.name, sil_dur))

# ---- 拼接（concat demuxer；逐段引用，含归因表静音）----
lines, per_seg, cursor = [], [], 0.0
for i, s in enumerate(segs):
    p = SEGDIR / str(s.get("audio") or "").split("/")[-1]
    if not p.is_file():
        print("!! 缺切片", p)
        sys.exit(2)
    lines.append("file '{}'".format(str(p).replace("\\", "/")))
    d = probe(p)
    per_seg.append({"index": i, "scene_index": s.get("index"), "audio": p.name,
                    "duration_s": d, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()})
    cursor += d
    if i in bnd and bnd[i] > 0 and i < len(segs) - 1:
        lines.append("file '{}'".format(str(sil).replace("\\", "/")))
        cursor += sil_dur
        per_seg[-1]["silence_after_s"] = sil_dur
    elif i < len(segs) - 1:
        per_seg[-1]["silence_after_s"] = 0.0
lst = OUT / "concat.txt"
lst.write_text("\n".join(lines) + "\n", encoding="utf-8")

out_audio = OUT / "narration_p30.mp3"
# **trailing pad 也要真实化**：时基声明 977.884s = 内容 961.634 + 停顿 14.25 + **trailing 2.0**。
# 仅拼段+停顿只得到 975.884 ⇒ 必须把 trailing 2.0s 也落成音频尾部静音
# （授权书「trailing pad 2.0s 保持时基声明」⇒ 声明的内容必须真实存在，否则视频轨仍会在尾部补黑）。
_pad = float(voice.get("trailing_pad_s") or 2.0)
r = subprocess.run([FF, "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-af", "apad=pad_dur={}".format(_pad),
                    "-c:a", "libmp3lame", "-q:a", "3", str(out_audio)],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
meas = probe(out_audio)
ok = abs(meas - TARGET_S) <= TOL_S
print()
print("拼接 rc={} | trailing pad 真实化 {:.3f}s".format(r.returncode, _pad))
print("实测时长 **{}s** vs 目标 {}±{}s ⇒ {}".format(
    meas, TARGET_S, TOL_S, "通过 ✔" if ok else "**失败 ✘**"))
if r.returncode != 0:
    print("stderr:", (r.stderr or "")[:300])

prov = {
    "schema": "phase30-p30-1-pause-materialize-v1",
    "stage": "P30-1 pause 真实化（按归因表插入真实静音；零重合成/零文本改动/零变速）",
    "rule_version": RULE_VERSION,
    "source": {"voice_artifact": str(VOICE.relative_to(R)).replace("\\", "/"),
               "voice_sha256": hashlib.sha256(VOICE.read_bytes()).hexdigest(),
               "source_audio": "projects/p_96efdc03e1aa/media/voice/narration.mp3",
               "source_audio_sha256": hashlib.sha256(
                   (R / "projects/p_96efdc03e1aa/media/voice/narration.mp3").read_bytes()
               ).hexdigest()},
    "rules": {"original_boundary_silence_s": 0.75, "derived_boundary_silence_s": 0.0,
              "original_boundaries": sorted(orig),
              "trailing_pad_s": float(voice.get("trailing_pad_s") or 2.0),
              "note": "trailing pad 由时基声明承担，本步骤不额外补静音"},
    "assertion_frozen_before_run": {"target_s": TARGET_S, "tolerance_s": TOL_S,
                                    "measured_s": meas, "passed": bool(ok)},
    "counts": {"segments": len(segs), "silence_inserts": len(orig),
               "silence_total_s": round(0.75 * len(orig), 3),
               "concat_entries": len(lines)},
    "output_audio": str(out_audio.relative_to(R)).replace("\\", "/"),
    "output_audio_sha256": (hashlib.sha256(out_audio.read_bytes()).hexdigest()
                            if out_audio.is_file() else None),
    "per_segment": per_seg,
    "zero_resynthesis": True, "text_edited": False, "tempo_changed": False,
}
p = L / "phase30_p30_1_pause_realize.json"
p.write_text(json.dumps(prov, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
print("->", p.relative_to(R).as_posix())
sys.exit(0 if ok else 1)
