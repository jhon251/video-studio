# -*- coding: utf-8 -*-
"""6-C —— 字幕连续性实测：在被修改的窗口内，取母版同一 cue 时刻抽帧，
用「描边白字墨水」指标做**同窗口自身对照**（cue 时刻 vs 无字幕时刻），
证明候选成片在该窗口**仍有字幕**，并保存抽帧 PNG 供人工观看。

指标：`outline_ink` = 底部带内「黑像素紧邻近白像素」的像素占比
（字幕 = 白字 + 黑描边 ⇒ 成对结构；纯背景缺少该结构，故对背景颜色不敏感）。
判定：`outline_ink(cue) ≥ 0.0005` 且 `≥ 1.5 × outline_ink(同窗口无字幕时刻)`。

用法: python docs/regression_2x/phase6c_subtitle_check.py
产出: logs/phase6c_subtitle_check.json + logs/phase6c_frames/*.png
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
LOGS = ROOT / "docs" / "regression_2x" / "logs"
FRAMES = LOGS / "phase6c_frames"
BATCH = LOGS / "phase6c_batch.json"
FFMPEG = str(ROOT / "bin" / "ffmpeg.exe")

from video_studio.core import captions as core_captions      # noqa: E402
from video_studio.core import strip as core_strip            # noqa: E402


def bottom_ink(png: Path, band: float = 0.18) -> dict:
    """底部字幕带的**描边白字墨水**（对背景颜色不敏感）。"""
    with Image.open(png) as im:
        g = np.asarray(im.convert("L"), dtype=np.uint8)
    h = g.shape[0]
    sl = g[int(h * (1 - band)):, :]
    white = (sl >= 200).astype(np.uint8) * 255
    dark = (sl <= 60)
    white_dil = np.asarray(Image.fromarray(white).filter(ImageFilter.MaxFilter(5))) > 0
    return {"white_ratio": round(float((sl >= 200).mean()), 5),
            "dark_ratio": round(float(dark.mean()), 5),
            "outline_ink": round(float((dark & white_dil).mean()), 5),
            "std": round(float(sl.std()), 2)}


def frame(film: Path, t: float, out: Path) -> None:
    subprocess.run([FFMPEG, "-y", "-v", "error", "-ss", "{:.3f}".format(t), "-i", str(film),
                    "-frames:v", "1", str(out)], capture_output=True, text=True,
                   encoding="utf-8", errors="replace")


def gap_time(cues: list, w0: float, w1: float, fallback: float) -> float:
    """窗口内**无字幕**的时刻（同窗口自身对照用）。"""
    cands = [c for c in cues if c["end"] > w0 + 0.5 and c["start"] < w1 - 0.5]
    if not cands:
        return fallback
    for a, b in zip(cands, cands[1:]):
        mid = (a["end"] + b["start"]) / 2
        if b["start"] - a["end"] > 0.6 and w0 + 0.2 < mid < w1 - 0.2:
            return round(mid, 3)
    return round(min(max(cands[-1]["end"] + 0.3, w0 + 0.2), w1 - 0.2), 3)


d = json.loads(BATCH.read_text(encoding="utf-8"))
FRAMES.mkdir(parents=True, exist_ok=True)
master = ROOT / d["inputs"]["v9_film"]

script = json.loads((ROOT / d["inputs"]["sandbox"] / "artifacts" /
                     "script_output.json").read_text(encoding="utf-8"))
segs = [s for s in (script.get("segments") or [])
        if core_strip.strip_claims(s.get("narration", "")).strip()]
cues = core_captions.build_cues([{"narration": core_strip.strip_claims(s.get("narration", "")),
                                  "duration_s": s.get("duration_s")} for s in segs])

windows = []
for c in d["candidates"]:
    ev = c.get("exec_evidence") or {}
    if ev.get("scene_projection"):
        for w in ev["scene_projection"]:
            windows.append({"cand_index": c["index"], "proposal": c["proposal_label"],
                            "scene_id": w["scene_id"], "window": w["window"]})
    elif ev.get("asset_evidence"):
        ae = ev["asset_evidence"]
        per = ae.get("per_scene") or ([ae] if ae.get("window") else [])
        for x in per:
            if x.get("window"):
                windows.append({"cand_index": c["index"], "proposal": c["proposal_label"],
                                "scene_id": x.get("scene_id") or "S21", "window": x["window"]})
    elif (c.get("steps") or []):
        w = next((s.get("window") for s in c["steps"] if s.get("window")), None)
        if w:
            windows.append({"cand_index": c["index"], "proposal": c["proposal_label"],
                            "scene_id": "S21", "window": w})

rows = []
for w in windows:
    w0, w1 = [float(x) for x in w["window"]]
    cue = next((c for c in cues if c["end"] > w0 + 1.0 and c["start"] < w1 - 1.0), None)
    t = (max(cue["start"], w0) + min(cue["end"], w1)) / 2 if cue else (w0 + w1) / 2
    t_gap = gap_time(cues, w0, w1, fallback=w1 - 0.5)
    tag = "c{}_{}_{}".format(w["cand_index"], w["scene_id"], int(t))
    m_png, c_png = FRAMES / (tag + "_master.png"), FRAMES / (tag + "_cand.png")
    g_png = FRAMES / (tag + "_candgap.png")
    cand_film = ROOT / d["candidates"][w["cand_index"] - 1]["film"]
    frame(master, t, m_png)
    frame(cand_film, t, c_png)
    frame(cand_film, t_gap, g_png)
    mi, ci, gi = bottom_ink(m_png), bottom_ink(c_png), bottom_ink(g_png)
    present = bool(ci["outline_ink"] >= 0.0005
                   and ci["outline_ink"] >= 1.5 * max(gi["outline_ink"], 1e-9))
    rows.append({**w, "t_s": round(t, 2), "t_gap_s": t_gap, "cue_text": (cue or {}).get("text"),
                 "master_ink": mi, "candidate_ink": ci, "gap_ink": gi,
                 "ink_gain_vs_gap": (round(ci["outline_ink"] / gi["outline_ink"], 3)
                                     if gi["outline_ink"] else None),
                 "subtitle_present": present,
                 "frames": [str(m_png.relative_to(ROOT)), str(c_png.relative_to(ROOT)),
                            str(g_png.relative_to(ROOT))]})

out = {"schema": "phase6c-subtitle-continuity-v1", "stage": "6-C",
       "method": "在被修改窗口内取母版同一 cue 时刻抽帧；用底部 18% 条带的『描边白字墨水』"
                 "做同窗口自身对照（cue 时刻 vs 无字幕时刻），避免背景颜色干扰。",
       "master_film": d["inputs"]["v9_film"], "master_sha256": d["inputs"]["v9_sha256"],
       "candidate_count": d["candidate_count"], "window_count": len(rows),
       "checked": len(rows), "present": sum(1 for r in rows if r["subtitle_present"]),
       "rows": rows,
       "note": "字幕『存在性』实测；样式/时间轴由与生产 pipeline 相同的 cue 表 + to_ass 保证；"
               "抽帧 PNG 供人工观看。"}
(LOGS / "phase6c_subtitle_check.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                                  encoding="utf-8")
print("窗口数", len(rows), "| 字幕存在", out["present"])
for r in rows:
    print("  cand{} {} [{:.1f},{:.1f}] t={} outline_ink cue/gap/master {}/{}/{} gain {} present={}".format(
        r["cand_index"], r["scene_id"], r["window"][0], r["window"][1], r["t_s"],
        r["candidate_ink"]["outline_ink"], r["gap_ink"]["outline_ink"],
        r["master_ink"]["outline_ink"], r["ink_gain_vs_gap"], r["subtitle_present"]))
print("json ->", LOGS / "phase6c_subtitle_check.json")
