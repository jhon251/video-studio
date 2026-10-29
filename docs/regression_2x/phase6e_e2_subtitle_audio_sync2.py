# -*- coding: utf-8 -*-
"""E2 字幕缺陷核实（第二轮，只读）：**旁白音频真实时长 vs 脚本时长** 与分块对齐。

第一轮缺陷：把语音段与 21 个 ~72 s 的"旁白累计大块"相减，得到的中位偏移 33.8 s **无意义**。
本轮改用：
  ① `voice_output` 中每个片段的**真实音频时长**（若可读）与脚本 `duration_s` 对比 ⇒ 漂移根因；
  ② 60 s 分块：**语音活动占比**（音频能量）vs **字幕活动占比**（cue 表）⇒ 对齐/漂移曲线；
  ③ 窗口内母版 vs 候选的**字幕带像素一致性**（证明 E2 未改字幕、缺陷继承自 v9）。
"""
import json
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
from video_studio.core import captions as core_captions             # noqa: E402
from video_studio.core import strip as core_strip                   # noqa: E402
import sqlite3                                                      # noqa: E402
import numpy as np                                                  # noqa: E402
from PIL import Image                                               # noqa: E402

LOGS = ROOT / "docs" / "regression_2x" / "logs"
DB = ROOT / "projects" / "video_studio.db"
FILM = ROOT / "projects" / "p_96efdc03e1aa" / "output" / "t_d0a54bdf1810_draft.mp4"
CAND = ROOT / "output" / "phase6b_m4_sandbox" / "p_96efdc03e1aa_6e2" / "output" / \
    "t_d0a54bdf1810_draft_6c_rp-bee31dff3335_vaid.mp4"
OUT = LOGS / "phase6e_e2_subtitle_audio_sync2.json"
CFG = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8-sig"))
FFMPEG = CFG["tools"]["ffmpeg"]["path"]
FFPROBE = CFG["tools"]["ffmpeg"]["ffprobe"]
FR = LOGS / "phase6e_e2_review_frames"

con = sqlite3.connect("file:{}?mode=ro".format(DB.as_posix()), uri=True)
con.row_factory = sqlite3.Row
con.execute("PRAGMA query_only=ON")
rows = [dict(r) for r in con.execute(
    "select type, task_id, path from artifacts where project_id=? order by created_at",
    ("p_96efdc03e1aa",))]
con.close()


def payload(t, task=None):
    lst = [r for r in rows if r["type"] == t]
    x = next((y for y in lst if task and y["task_id"] == task), lst[-1] if lst else None)
    if not x:
        return {}
    p = Path(x["path"])
    return json.loads((p if p.is_absolute() else ROOT / p).read_text(encoding="utf-8"))


script, voice = payload("script_output"), payload("voice_output")
render = payload("render_output", "t_d0a54bdf1810")
segs = script.get("segments") or []
vsegs = voice.get("segments") or []
total = float((render.get("duration_contract") or {}).get("timeline_duration_s") or 1532.0)
timeline = render.get("material_timeline") or []

# ① 脚本时长 vs 真实音频时长
per_seg = []
cum_s = cum_v = 0.0
for i, s in enumerate(segs):
    d_s = float(s.get("duration_s") or 0.0)
    v = vsegs[i] if i < len(vsegs) else {}
    d_v = v.get("duration_s") or v.get("duration") or v.get("narration_duration_s")
    if d_v is not None:
        d_v = float(d_v)
    aud = v.get("audio_path") or v.get("path") or v.get("file")
    if d_v is None and aud:
        p = Path(str(aud))
        p = p if p.is_absolute() else ROOT / p
        if p.is_file():
            o = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                                "-of", "csv=p=0", str(p)], capture_output=True, text=True)
            try:
                d_v = float(o.stdout.strip())
            except Exception:                                                 # noqa: BLE001
                d_v = None
    per_seg.append({"i": i, "scene": s.get("scene_id"),
                    "script_dur_s": round(d_s, 3),
                    "voice_dur_s": (round(d_v, 3) if d_v is not None else None),
                    "delta_s": (round(d_s - d_v, 3) if d_v is not None else None),
                    "cum_script_s": round(cum_s, 3),
                    "cum_voice_s": (round(cum_v, 3) if d_v is not None else None),
                    "text_head": core_strip.strip_claims(s.get("narration", ""))[:30]})
    cum_s += d_s
    if d_v is not None:
        cum_v += d_v

have_voice = [p for p in per_seg if p["voice_dur_s"] is not None]
voice_total = round(cum_v, 3) if have_voice else None
drift_curve = [{"scene": p["scene"], "cum_script_s": p["cum_script_s"],
                "cum_voice_s": p["cum_voice_s"],
                "drift_s": (round(p["cum_script_s"] - p["cum_voice_s"], 3)
                            if p["cum_voice_s"] is not None else None)} for p in per_seg]

# ② 60 s 分块：语音活动 vs 字幕活动
def audio_rms(film: Path, hop=800, rate=8000):
    out = subprocess.run([FFMPEG, "-v", "error", "-i", str(film), "-ac", "1", "-ar", str(rate),
                          "-f", "s16le", "-"], capture_output=True)
    a = np.frombuffer(out.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    n = len(a) // hop
    return np.sqrt((a[:n * hop].reshape(n, hop) ** 2).mean(axis=1))


rms = audio_rms(FILM)
# 平滑 + 相对阈值（自适应，报告阈值本身）
k = 5
sm = np.convolve(rms, np.ones(k) / k, mode="same")
thr = float(max(0.008, 0.25 * float(np.percentile(sm, 75))))
act = sm > thr
cues = core_captions.build_cues([{"narration": core_strip.strip_claims(s.get("narration", "")),
                                  "duration_s": s.get("duration_s")} for s in segs])
n_sec = int(total) + 1
ind_cue = np.zeros(n_sec, dtype=np.float32)
for c in cues:
    a, b = int(c["start"]), int(min(c["end"], n_sec))
    ind_cue[max(0, a):b] = 1.0
blocks = []
for i in range(0, int(total) // 60 + 1):
    a_s, b_s = i * 60, min((i + 1) * 60, len(act) // 10)
    a_c, b_c = i * 60, min((i + 1) * 60, n_sec)
    if b_s <= a_s:
        continue
    sp = act[a_s * 10:b_s * 10]
    blocks.append({"block_s": [a_s, b_s],
                   "speech_frac": round(float(sp.mean()), 3) if sp.size else None,
                   "cue_frac": round(float(ind_cue[a_c:b_c].mean()), 3) if b_c > a_c else None})
# ③ 窗口内母版/候选字幕带像素一致性
def band(film: Path, t: float):
    p = FR / "{}_{}.png".format("x", "x")
    out = FR / "_tmp_{}_{}.png".format(film.stem[-8:], int(t * 1000))
    subprocess.run([FFMPEG, "-y", "-v", "error", "-ss", "{:.3f}".format(t), "-i", str(film),
                    "-frames:v", "1", str(out)], capture_output=True, text=True, encoding="utf-8",
                   errors="replace")
    a = np.asarray(Image.open(out).convert("L"), dtype=np.float32) / 255.0
    out.unlink(missing_ok=True)
    return a[int(a.shape[0] * 0.82):]


consistency = []
for t in (246.0, 255.0, 262.0, 272.0, 285.0, 292.0, 297.0):
    bm, bc = band(FILM, t), band(CAND, t)
    d = float(np.abs(bm - bc).mean() * 255)
    consistency.append({"t": t, "subtitle_band_gray_diff_master_vs_candidate": round(d, 4),
                        "identical": d < 1.0})
report = {
    "schema": "phase6e-subtitle-audio-sync2-v1", "stage": "6-E",
    "note": "只读；不执行、不改任何产物。第一轮 offset 统计无效（与 72 s 大块相减），本轮作废该指标。",
    "totals": {"timeline_s": total, "script_narration_s": round(cum_s, 3),
               "voice_total_s": voice_total,
               "voice_vs_script_delta_s": (round(cum_s - voice_total, 3) if voice_total else None),
               "audio_speech_frac": round(float(act.mean()), 4),
               "speech_threshold_rms": round(thr, 5),
               "timeline_scenes": len(timeline), "script_segments": len(segs),
               "voice_segments": len(vsegs), "cues": len(cues)},
    "per_segment_script_vs_voice": per_seg,
    "drift_curve": drift_curve,
    "blocks_60s": blocks,
    "subtitle_band_master_vs_candidate": consistency,
    "invalidated_metrics": ["phase6e_e2_subtitle_audio_sync.json 的 offset_stats / best_lag（与 72 s 大块相减，无意义）"],
}
OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

print("时间轴 {:.1f}s | 脚本旁白累计 {:.1f}s | voice 音频总长 {} | 差值 {}".format(
    total, cum_s, voice_total, report["totals"]["voice_vs_script_delta_s"]))
print("voice 段数 {} | 有真实时长的段数 {}".format(len(vsegs), len(have_voice)))
if have_voice:
    print("每段（脚本 vs voice）前 8 段:")
    for p in per_seg[:8]:
        print("  seg{:2d} {:5s} script {:7.3f}s voice {:7.3f}s Δ{:7.3f}s cumΔ {}".format(
            p["i"], str(p["scene"]), p["script_dur_s"] or 0, p["voice_dur_s"] or 0,
            p["delta_s"] or 0,
            next((d["drift_s"] for d in drift_curve if d["scene"] == p["scene"]), None)))
print("\n60 s 分块（语音占比 vs 字幕占比）:")
for b in blocks:
    print("  {:5d}-{:5d}s  speech {:.2f}  cue {:.2f}".format(b["block_s"][0], b["block_s"][1],
                                                             b["speech_frac"] or 0,
                                                             b["cue_frac"] or 0))
print("\n字幕带母版 vs 候选:", json.dumps(consistency, ensure_ascii=False))
print("report ->", OUT)
