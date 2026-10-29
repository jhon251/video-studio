"""生成交错试听包的时间轴提示（cue sheet），便于在播放器里直接跳段。"""
import json
import sys
from pathlib import Path

import soundfile as sf

sys.stdout.reconfigure(encoding="utf-8")
VS = Path(r"C:\mp4agent\video-studio")
OUT = VS / "output" / "run05"
dirs = [("F5 nfe16", OUT / "tts_clone_audition_lv"),
        ("GSV v2", OUT / "tts_gsv_v2"),
        ("GSV v3@8", OUT / "tts_gsv_v3_s8"),
        ("GSV v3@32", OUT / "tts_gsv_v3_s32")]
beats = ["S17-B02", "S12-B02", "S27-B01"]
GAP = 0.6

t = 0.0
lines = ["交错试听包时间轴（每 beat 依次：F5 nfe16 → GSV v2 → GSV v3@8 → GSV v3@32）",
         "文件: output/run05/AB_bundle_4engines.wav", "", "起始       时长    引擎          beat",
         "-" * 64]
for b in beats:
    lines.append("# {} ----------".format(b))
    for lab, d in dirs:
        p = d / (b + ".wav")
        if not p.exists():
            lines.append("  缺失: " + str(p))
            continue
        dur = sf.info(str(p)).duration
        lines.append("{:>7.2f}s  {:>5.2f}s  {:<12s}  {}".format(t, dur, lab, b))
        t += dur + GAP
    t += GAP
lines.append("-" * 64)
lines.append("合计 {:.2f}s".format(t))
txt = "\n".join(lines) + "\n"
(VS / "output" / "run05" / "AB_bundle_4engines_cues.txt").write_text(txt, encoding="utf-8")
print(txt)
