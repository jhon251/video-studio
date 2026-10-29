# -*- coding: utf-8 -*-
"""E2 字幕缺陷核实（只读）：**字幕 cue 时间基 vs 音频语音段**是否对齐。

人工报告："字幕没有一条能对的上旁白的"。
本脚本用**可测证据**回答：
  A. 旁白 cue 表（与生产同一函数：core.strip + core.captions.build_cues）的累计时间基；
  B. v9 成片的**音频语音活动段**（能量法，100 ms 分辨率）；
  C. 两者对齐度：覆盖率 / 逐段偏移 / 互相关最佳 lag；
  D. 并在 [245,300] 窗口内逐条列出 cue 与语音段，供人对照。

只读：不执行 proposal、不改任何文件（仅写本报告 JSON）。
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

LOGS = ROOT / "docs" / "regression_2x" / "logs"
DB = ROOT / "projects" / "video_studio.db"
FILM = ROOT / "projects" / "p_96efdc03e1aa" / "output" / "t_d0a54bdf1810_draft.mp4"
CAND = ROOT / "output" / "phase6b_m4_sandbox" / "p_96efdc03e1aa_6e2" / "output" / \
    "t_d0a54bdf1810_draft_6c_rp-bee31dff3335_vaid.mp4"
OUT = LOGS / "phase6e_e2_subtitle_audio_sync.json"
WINDOW = (245.0, 300.0)
CFG = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8-sig"))
FFMPEG = CFG["tools"]["ffmpeg"]["path"]

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


script = payload("script_output")
render = payload("render_output", "t_d0a54bdf1810")
segs = script.get("segments") or []
timeline = render.get("material_timeline") or []
total = float((render.get("duration_contract") or {}).get("timeline_duration_s") or 1532.0)

# A) 旁白累计时间基 + cue 表（与生产同函数）
narr = []
t = 0.0
for s in segs:
    txt = core_strip.strip_claims(s.get("narration", ""))
    d = float(s.get("duration_s") or 0.0)
    if txt.strip():
        narr.append({"start": round(t, 3), "end": round(t + d, 3), "dur": round(d, 3),
                     "text": txt})
    t += d
narr_total = round(t, 3)
cues = core_captions.build_cues([{"narration": core_strip.strip_claims(s.get("narration", "")),
                                  "duration_s": s.get("duration_s")} for s in segs])

# B) 音频语音活动（100 ms）
def audio_env(film: Path):
    out = subprocess.run([FFMPEG, "-v", "error", "-i", str(film), "-ac", "1", "-ar", "8000",
                          "-f", "s16le", "-"], capture_output=True)
    a = np.frombuffer(out.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    hop = 800                                        # 100 ms @ 8 kHz
    n = len(a) // hop
    rms = np.sqrt((a[:n * hop].reshape(n, hop) ** 2).mean(axis=1))
    return rms


def speech_segments(rms, thr):
    act = rms > thr
    segs_out, i = [], 0
    while i < len(act):
        if act[i]:
            j = i
            while j + 1 < len(act) and act[j + 1]:
                j += 1
            if (j - i + 1) >= 3:                     # ≥300 ms 视为语音
                segs_out.append({"start": round(i * 0.1, 3), "end": round((j + 1) * 0.1, 3)})
            i = j + 1
        else:
            i += 1
    return segs_out


rms = audio_env(FILM)
thr = float(max(0.015, 0.20 * float(np.percentile(rms[rms > 0.005], 60)) if (rms > 0.005).any()
                else 0.015))
speech = speech_segments(rms, thr)
speech_total = round(sum(s["end"] - s["start"] for s in speech), 3)

# 指示信号（1 s 分辨率）与互相关
def indicator(spans, n_sec):
    v = np.zeros(n_sec, dtype=np.float32)
    for s in spans:
        a, b = int(s["start"]), int(min(s["end"], n_sec))
        v[a:b] = 1.0
    return v


n_sec = int(total) + 1
ind_cue = indicator(cues, n_sec)
ind_sp = indicator(speech, n_sec)
max_lag = 180
corr = []
for lag in range(-max_lag, max_lag + 1):
    a = ind_cue[max(0, lag):n_sec + min(0, lag)]
    b = ind_sp[max(0, -lag):n_sec - max(0, lag)] if lag > 0 else ind_sp[:n_sec + lag]
    b = ind_sp[-lag:n_sec] if lag > 0 else ind_sp[:n_sec + lag] if lag != 0 else ind_sp
    m = min(len(a), len(b))
    if m > 60:
        corr.append((lag, float(np.corrcoef(a[:m], b[:m])[0, 1])))
best = max(corr, key=lambda x: x[1]) if corr else (0, 0.0)
corr0 = next((c for l, c in corr if l == 0), None)

# C) 逐语音段的最佳匹配旁白段 + 偏移
def best_match(sp, spans):
    best, bo = None, None
    for s in spans:
        ov = min(sp["end"], s["end"]) - max(sp["start"], s["start"])
        if ov <= 0:
            continue
        if best is None or ov > best[0]:
            best, bo = (ov, s), round(sp["start"] - s["start"], 3)
    return bo, (best[1] if best else None)


offsets = []
for sp in speech:
    off, s = best_match(sp, narr)
    if off is not None:
        offsets.append({"speech": [sp["start"], sp["end"]], "narr_offset_s": off,
                        "narr_text": (s["text"][:40] if s else None)})
offs = np.array([o["narr_offset_s"] for o in offsets]) if offsets else np.array([0.0])

# D) 窗口内清单
win_cues = [c for c in cues if c["start"] < WINDOW[1] and c["end"] > WINDOW[0]]
win_speech = [s for s in speech if s["start"] < WINDOW[1] and s["end"] > WINDOW[0]]
win_narr = [n for n in narr if n["start"] < WINDOW[1] and n["end"] > WINDOW[0]]

report = {
    "schema": "phase6e-subtitle-audio-sync-v1", "stage": "6-E",
    "note": "只读核实：字幕 cue 时间基 vs v9 音频语音活动段。未执行任何 proposal。",
    "film": {"path": str(FILM.relative_to(ROOT)), "timeline_total_s": total,
             "narration_total_s": narr_total, "speech_total_s": speech_total,
             "silence_total_s": round(total - speech_total, 3),
             "narration_shortfall_s": round(total - narr_total, 3)},
    "counts": {"script_segments": len(segs), "narr_spans": len(narr), "cues": len(cues),
               "speech_segments": len(speech), "timeline_scenes": len(timeline)},
    "alignment": {
        "speech_threshold_rms": round(thr, 5),
        "best_lag_s": int(best[0]), "best_corr": round(best[1], 4),
        "corr_at_lag0": round(corr0, 4) if corr0 is not None else None,
        "offset_stats": {"n": int(len(offs)), "mean_s": round(float(offs.mean()), 3),
                         "median_s": round(float(np.median(offs)), 3),
                         "p10_s": round(float(np.percentile(offs, 10)), 3),
                         "p90_s": round(float(np.percentile(offs, 90)), 3),
                         "abs_gt_2s_share": round(float((np.abs(offs) > 2).mean()), 4),
                         "abs_gt_10s_share": round(float((np.abs(offs) > 10).mean()), 4)},
    },
    "window_245_300": {
        "cues": [{"start": c["start"], "end": c["end"], "text": c["text"][:50]} for c in win_cues],
        "speech": win_speech,
        "narration_spans": [{"start": n["start"], "end": n["end"], "text": n["text"][:50]}
                            for n in win_narr]},
    "sample_offsets": offsets[:12],
}
OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

print("时间轴总长 {:.1f}s | 旁白累计 {:.1f}s | 语音活动 {:.1f}s | 静音 {:.1f}s".format(
    total, narr_total, speech_total, total - speech_total))
print("段数: script {} | 旁白 span {} | cue {} | 语音段 {} | 时间轴镜头 {}".format(
    len(segs), len(narr), len(cues), len(speech), len(timeline)))
print("对齐: 最佳 lag {}s (corr {:.3f}) | lag0 corr {}".format(
    best[0], best[1], report["alignment"]["corr_at_lag0"]))
print("逐段偏移: 中位数 {:.1f}s | |偏移|>2s 占比 {:.1%} | >10s 占比 {:.1%}".format(
    report["alignment"]["offset_stats"]["median_s"],
    report["alignment"]["offset_stats"]["abs_gt_2s_share"],
    report["alignment"]["offset_stats"]["abs_gt_10s_share"]))
print("\n[245,300] cue（起点/文本）:")
for c in win_cues[:14]:
    print("  {:8.2f}  {}".format(c["start"], c["text"][:46]))
print("[245,300] 语音段:", json.dumps(win_speech[:10]))
print("[245,300] 旁白累计段:", [n["start"] for n in win_narr][:10])
print("report ->", OUT)
