"""扫描并校验 output/run05 下所有 tts_* 目录的 wav 完整性（只读）。

判断：能否解码、时长是否 >0.5s、是否与索引/时长报告一致；标记 PARTIAL（有 wav 无索引）。
"""
import glob
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.stdout.reconfigure(encoding="utf-8")
BASE = Path(r"C:\mp4agent\video-studio\output\run05")
bad = []
for d in sorted([p for p in BASE.glob("tts*") if p.is_dir()]):
    wavs = sorted(d.glob("*.wav"))
    idx = d / "tts_index_clone.json"
    has_idx = idx.exists()
    tot = 0.0
    print("=" * 78)
    print("[{}] wav {} 个 | 索引 {} | {}".format(
        d.name, len(wavs), "有" if has_idx else "无", "COMPLETE" if has_idx else "PARTIAL"))
    for w in wavs:
        try:
            a, sr = sf.read(str(w), dtype="float32", always_2d=True)
            dur = len(a) / sr
            rms = float(np.sqrt((a.mean(axis=1) ** 2).mean()))
            tot += dur
            flag = "OK" if dur > 0.5 and rms > 0.005 else "SUSPECT"
            if flag != "OK":
                bad.append(str(w))
            print("   {:28s} {:6.2f}s rms={:.4f} peak={:.3f} {}".format(
                w.name, dur, rms, float(np.abs(a).max()), flag))
        except Exception as e:
            bad.append(str(w))
            print("   {:28s} 读取失败: {}".format(w.name, e))
    if has_idx:
        meta = json.loads(idx.read_text(encoding="utf-8"))
        print("   索引 total_s={} | 盘上 wav 合计 {:.2f}s | 一致: {}".format(
            meta.get("total_s"), tot, abs(float(meta.get("total_s", 0)) - tot) < 0.05))
        print("   引擎/参数: nfe={} threads={} loudness={} ref={}".format(
            meta.get("nfe_step"), meta.get("threads"), meta.get("loudness"),
            Path(str(meta.get("ref", {}).get("wav", ""))).name))
    else:
        print("   !! PARTIAL：无索引（该轮未跑完）")

print()
print("异常文件数:", len(bad))
for b in bad:
    print("  -", b)
sys.exit(0)
