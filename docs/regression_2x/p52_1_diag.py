# -*- coding: utf-8 -*-
"""Phase 52 诊断：核对监理三条（①时钟漂移 ②clamp 级联 ③覆盖缺口）。"""
from __future__ import annotations

import json
import pathlib
import re
import statistics
import subprocess
import sys
import wave

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "docs" / "regression_2x"))
sys.stdout.reconfigure(encoding="utf-8")
from ass_overlap_scan import parse_ass                                       # noqa: E402

FF = str(R / "bin" / "ffmpeg.exe")
V = R / "output" / "phase36_voice"


def runs_of(path, noise="-30dB", d=0.05):
    """细粒度语音运行（silencedetect 的**非静音**区间）。"""
    r = subprocess.run([FF, "-v", "info", "-i", str(path), "-af",
                        "silencedetect=noise={}:d={}".format(noise, d),
                        "-f", "null", "-"], capture_output=True, text=True,
                       errors="ignore")
    t = (r.stderr or "") + (r.stdout or "")
    # 解析 silence_start/end 得静音区间，再取补集
    ss = [float(x) for x in re.findall(r"silence_start:\s*([0-9.]+)", t)]
    se = [float(x) for x in re.findall(r"silence_end:\s*([0-9.]+)", t)]
    try:
        dur = float(subprocess.run(
            [str(R / "bin" / "ffprobe.exe"), "-v", "error", "-show_entries",
             "format=duration", "-of", "default=nw=1:nk=1", str(path)],
            capture_output=True, text=True).stdout.strip().splitlines()[0])
    except Exception:                                                           # noqa: BLE001
        dur = None
    sil = list(zip(ss, se + [dur] if dur else se))
    out, cur = [], 0.0
    for a, b in sil:
        if a > cur:
            out.append((round(cur, 3), round(a, 3)))
        cur = max(cur, b)
    if dur and dur > cur:
        out.append((round(cur, 3), round(dur, 3)))
    return out, dur


def main() -> int:
    sc = json.loads((R / "output/phase36_script_sandbox/script_p36_v65_36seg.json")
                    .read_text(encoding="utf-8"))
    tb = json.loads((V / "timebase_v65.json").read_text(encoding="utf-8"))
    wins = tb["windows"]
    print("=== ② clamp 级联：F8 烧录 ASS 的 cue 时长分布 ===")
    ass = R / "projects/p_379bd4637469/artifacts/_captions_t_bfe0eb0375b0.ass"
    cues = parse_ass(ass)
    durs = [round(e - s, 3) for s, e, _ in cues]
    exactly_1 = sum(1 for d in durs if abs(d - 1.0) <= 0.1)
    print("  cue {} 条 | 时长 median {:.3f}s | min {:.3f} | max {:.3f}".format(
        len(cues), statistics.median(durs), min(durs), max(durs)))
    print("  时长 =1.0s±0.1 的 cue = **{} / {}**（{:.0%}）".format(
        exactly_1, len(durs), exactly_1 / len(durs)))

    print()
    print("=== ③ 覆盖：F8 cue 对**语音运行**的覆盖 ===")
    # 逐景取实际音频切片 → 语音运行
    segs = {s["scene_id"]: s for s in sc["segments"]}
    tot_speech, covered = 0.0, 0.0
    nocov = []
    for i, w in enumerate(wins):
        sid = w["scene_id"]
        p = V / "seg" / "{}.wav".format(sid)
        if not p.is_file():
            continue
        rns, _ = runs_of(p)
        w0 = float(w["start_s"])
        win_cues = [c for c in cues if w0 - 1e-6 <= c[0] < float(w["end_s"])]
        for a, b in rns:
            L = b - a
            tot_speech += L
            aa, bb = w0 + a, w0 + b
            # 该运行被任一 cue 覆盖的比例
            best = 0.0
            for cs, ce, _ in win_cues:
                ov = max(0.0, min(ce, bb) - max(cs, aa))
                best = max(best, ov)
            covered += best
            if best / max(L, 1e-9) < 0.5:
                nocov.append({"scene": sid, "run": [round(a, 2), round(b, 2)],
                              "cov": round(best / max(L, 1e-9), 2)})
    print("  语音总时长 {:.1f}s | cue 覆盖 {:.1f}s ⇒ **覆盖率 {:.1%}**（门限 ≥95%）".format(
        tot_speech, covered, covered / max(tot_speech, 1e-9)))
    print("  覆盖 <50% 的语音运行数 = {}（样例 {}）".format(
        len(nocov), nocov[:4]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
