# -*- coding: utf-8 -*-
"""诊断：core.direction.measure_freeze / core.integrity.measure_silence 直连调用（只读）。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(r"C:\mp4agent\video-studio") / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import direction as D  # noqa: E402
from video_studio.core import integrity as I  # noqa: E402

ROOT = Path(r"C:\mp4agent\video-studio")
film = ROOT / "projects" / "p_96efdc03e1aa" / "output" / "t_d0a54bdf1810_draft.mp4"
cfg = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8-sig"))
ff = cfg["tools"]["ffmpeg"]["path"]

print("film:", film.is_file(), film.stat().st_size if film.is_file() else None)
try:
    blocks, err = D.measure_freeze(film, ff, 1532.0)
    print("freeze blocks:", len(blocks), "| first 3:", blocks[:3])
    print("stderr tail:", (err or "")[-300:].replace("\n", " "))
except Exception as exc:                                     # noqa: BLE001
    print("measure_freeze EXC:", type(exc).__name__, exc)
try:
    sil, err2 = I.measure_silence(film, ff)
    print("silence blocks:", len(sil), sil[:2])
except Exception as exc:                                     # noqa: BLE001
    print("measure_silence EXC:", type(exc).__name__, exc)
