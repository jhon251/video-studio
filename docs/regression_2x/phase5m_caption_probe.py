# -*- coding: utf-8 -*-
"""5-M 视觉探针：把 `core.captions` 生成的 ASS 用**真实渲染同款滤镜**烧到真实素材上，抽帧供人工核验。

与渲染路径一致：`ass=filename='...':fontsdir='C\\:/Windows/Fonts'`（libass），底部居中 + 描边。
用法: python docs/regression_2x/phase5m_caption_probe.py
产出: docs/regression_2x/logs/phase5m_caption_probe/{cap_over_photo.mp4, frame_*.png, captions.ass, report.json}
"""
import json
import re
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
from video_studio.core.captions import build_cues, to_ass  # noqa: E402

OUT = ROOT / "docs" / "regression_2x" / "logs" / "phase5m_caption_probe"
OUT.mkdir(parents=True, exist_ok=True)
CFG = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8-sig"))
FFMPEG = CFG["tools"]["ffmpeg"]["path"]
FFPROBE = CFG["tools"]["ffmpeg"]["ffprobe"]

# 真实素材（p_96efdc03e1aa 的 4 张上屏素材之一）+ 真实脚本文本（前 3 段）
assets = []
for p in sorted((ROOT / "projects" / "p_96efdc03e1aa" / "media" / "external").glob("*.jpg")):
    assets.append(p)
img = assets[0] if assets else None
script = json.loads((ROOT / "projects" / "p_96efdc03e1aa" / "artifacts"
                     / "a_49b58fb3dc01.json").read_text(encoding="utf-8"))
segs = [{"narration": s["narration"], "duration_s": 12.0} for s in script["segments"][:3]]
cues = build_cues(segs)
ass_text = to_ass(cues, resolution="1920x1080")
ass_path = OUT / "captions.ass"
ass_path.write_text(ass_text, encoding="utf-8")
total = 36.0
cap = "ass=filename='{}':fontsdir='C\\:/Windows/Fonts'".format(
    ass_path.as_posix().replace(":", "\\:"))

mp4 = OUT / "cap_over_photo.mp4"
cmd = [FFMPEG, "-y", "-v", "warning", "-stats"]
if img:
    cmd += ["-loop", "1", "-framerate", "25", "-t", str(total), "-i", str(img)]
else:
    cmd += ["-f", "lavfi", "-t", str(total), "-i", "color=c=0x204060:size=1920x1080:rate=25"]
cmd += ["-vf",
        "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,setsar=1," + cap,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "23",
        "-t", str(total), str(mp4)]
r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
print("render rc:", r.returncode, "| stderr tail:", (r.stderr or "")[-200:].replace("\n", " "))

frames = []
for t in (4.0, 9.0, 14.0, 25.0):
    fp = OUT / "frame_{:05.1f}s.png".format(t)
    subprocess.run([FFMPEG, "-y", "-v", "error", "-ss", str(t), "-i", str(mp4), "-frames:v", "1",
                    str(fp)], capture_output=True)
    if fp.is_file():
        frames.append(str(fp.relative_to(ROOT)))

rep = {"image": str(img) if img else None, "cues": len(cues), "ass": str(ass_path.relative_to(ROOT)),
       "mp4": str(mp4.relative_to(ROOT)) if mp4.is_file() else None,
       "mp4_bytes": mp4.stat().st_size if mp4.is_file() else None,
       "frames": frames,
       "cue_table": [{"start": c["start"], "end": c["end"], "text": c["text"],
                      "lines": c["lines"]} for c in cues]}
(OUT / "report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
print("cues:", len(cues), "| mp4:", rep["mp4"], rep["mp4_bytes"], "bytes")
for c in cues:
    print("  {:5.2f}-{:5.2f}  {}".format(c["start"], c["end"], " / ".join(c["lines"])))
print("frames:", frames)
