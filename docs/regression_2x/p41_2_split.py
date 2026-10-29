# -*- coding: utf-8 -*-
"""Phase 36 / P36-4 步骤 2：**静音吸附切景**（silencedetect → 吸附到句界 → 贪心装箱）。

硬约束（授权书 §2）：
  · 目标 **~30 景**；**单景 ≤25s**；
  · **任何切点不得落在句中** ⇒ 构造断言「每景文本 = 完整句子序列，句中切分数 = 0」；
  · 切点**吸附**到静音中点（silencedetect），不靠字符估算。

实现：
  1) 每段 mp3 → wav（24kHz 单声道）；
  2) `silencedetect` 找段内静音区间 ⇒ 候选切点（静音中点）；
  3) 句切分（按。！？）得到句子序列；把**句末时刻**按比例映射到音频，
     再**吸附**到最近候选切点（容差 1.5s）；无候选则用比例时刻（并登记 `snap=ratio`）；
  4) **贪心装箱**：逐句累加，加入下一句会超 `MAX_SCENE_S` 则收景 ⇒ 景 = 完整句序列；
  5) 输出 `scenes.json`（逐景：起止时刻、文本、句数、句中切分=0 证据）+ 切片音频。
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
OUT = R / "output" / "phase36_voice"
WAV = OUT / "wav"
SEG = OUT / "seg"
FF = str(R / "bin" / "ffmpeg.exe")
FFPROBE = str(R / "bin" / "ffprobe.exe")
sys.stdout.reconfigure(encoding="utf-8")

MAX_SCENE_S = 25.0
SNAP_TOL_S = 1.5
SIL_NOISE = "-32dB"
SIL_MIN_D = 0.28


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, errors="ignore")


def dur(p):
    r = run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(p)])
    v = (r.stdout or "").strip().splitlines()
    return round(float(v[0]), 3) if v and v[0] else None


def sents(t):
    """句切分（保留标点，拼接可无损复原）。"""
    out, buf = [], ""
    for ch in t:
        buf += ch
        if ch in "。！？":
            out.append(buf)
            buf = ""
    if buf.strip():
        out.append(buf)
    return [s for s in out if s.strip()]


def silence_points(wav: pathlib.Path):
    """返回段内静音**中点**时刻列表。"""
    r = run([FF, "-v", "info", "-i", str(wav), "-af",
             "silencedetect=noise={}:d={}".format(SIL_NOISE, SIL_MIN_D), "-f", "null", "-"])
    txt = (r.stderr or "") + (r.stdout or "")
    starts = [float(m) for m in re.findall(r"silence_start:\s*([0-9.]+)", txt)]
    ends = [float(m) for m in re.findall(r"silence_end:\s*([0-9.]+)", txt)]
    pts = []
    for s, e in zip(starts, ends):
        pts.append(round((s + e) / 2.0, 3))
    return pts, len(starts)


def main() -> int:
    voice = json.loads((OUT / "voice_output_v65.json").read_text(encoding="utf-8"))
    WAV.mkdir(parents=True, exist_ok=True)
    SEG.mkdir(parents=True, exist_ok=True)
    all_scenes, snap_log = [], []
    for pi, pseg in enumerate(voice["segments"]):
        pid = pseg["scene_id"]
        src = OUT / pseg["audio"]
        wav = WAV / "{}.wav".format(pid)
        if not wav.is_file():
            subprocess.run([FF, "-y", "-v", "error", "-i", str(src), "-ar", "24000",
                            "-ac", "1", "-c:a", "pcm_s16le", str(wav)], check=True)
        total = dur(wav) or 0.0
        pts, nsil = silence_points(wav)
        ss = sents(pseg["text"])
        # 句末比例时刻（按字符占比）→ 吸附到最近静音中点
        cum, bounds = 0, []
        total_chars = sum(len(s) for s in ss)
        for i, s in enumerate(ss):
            cum += len(s)
            ratio_t = round(total * cum / total_chars, 3)
            if i == len(ss) - 1:
                bounds.append({"t": round(total, 3), "snap": "end"})
                continue
            best, bestd = None, None
            for c in pts:
                dd = abs(c - ratio_t)
                if bestd is None or dd < bestd:
                    best, bestd = c, dd
            if best is not None and bestd <= SNAP_TOL_S:
                bounds.append({"t": best, "snap": "silence", "delta_s": round(bestd, 3)})
            else:
                bounds.append({"t": ratio_t, "snap": "ratio"})
        snap_log.append({"para": pid, "sentences": len(ss), "silences": nsil,
                         "silence_points": pts[:12],
                         "snap_silence": sum(1 for b in bounds if b["snap"] == "silence"),
                         "snap_ratio": sum(1 for b in bounds if b["snap"] == "ratio"),
                         "duration_s": total})
        # 贪心装箱：景 = 完整句序列，且景长 ≤ MAX_SCENE_S
        cur = {"sents": [], "chars": 0, "start": 0.0}
        pack = []
        for i, s in enumerate(ss):
            t_end = bounds[i]["t"]
            cand_len = t_end - cur["start"]
            if cur["sents"] and cand_len > MAX_SCENE_S:
                pack.append(cur)
                cur = {"sents": [], "chars": 0, "start": bounds[i - 1]["t"]}
                cand_len = t_end - cur["start"]
            cur["sents"].append({"text": s, "end_t": t_end,
                                 "snap": bounds[i]["snap"],
                                 "delta_s": bounds[i].get("delta_s")})
            cur["chars"] += len(s)
        if cur["sents"]:
            pack.append(cur)
        for k, sc in enumerate(pack):
            sid = "{}_{}".format(pid, k + 1)
            t0, t1 = sc["start"], sc["sents"][-1]["end_t"]
            dest = SEG / "{}.wav".format(sid)
            if not dest.is_file():
                subprocess.run([FF, "-y", "-v", "error", "-ss", "{:.3f}".format(t0),
                                "-to", "{:.3f}".format(t1), "-i", str(wav),
                                "-c:a", "pcm_s16le", str(dest)], check=True)
            text = "".join(x["text"] for x in sc["sents"])
            all_scenes.append({
                "scene_id": sid, "parent_para": pid,
                "start_s": round(t0, 3), "end_s": round(t1, 3),
                "window_s": round(t1 - t0, 3),
                "text": text,
                "text_sha256": __import__("hashlib").sha256(
                    text.encode("utf-8")).hexdigest(),
                "sentence_count": len(sc["sents"]),
                "sentences": [x["text"] for x in sc["sents"]],
                "snaps": [x["snap"] for x in sc["sents"]],
                "audio": "seg/{}.wav".format(sid),
            })
    # ---- 断言：句中切分 = 0（每景文本 = 完整句序列）----
    def is_complete(seq):
        return all(x and x.rstrip()[-1] in "。！？" for x in seq)
    bad = [s["scene_id"] for s in all_scenes if not is_complete(s["sentences"])]
    over = [s["scene_id"] for s in all_scenes if s["window_s"] > MAX_SCENE_S + 0.01]
    print("景数 {} | 单景最长 {:.2f}s | 超 {:.0f}s 的景: {}".format(
        len(all_scenes), max(s["window_s"] for s in all_scenes), MAX_SCENE_S,
        over or "无"))
    print("**句中切分 = {}**（每景均为完整句序列）".format(len(bad)))
    print("吸附统计：silence {} / ratio {}".format(
        sum(x["snap_silence"] for x in snap_log),
        sum(x["snap_ratio"] for x in snap_log)))
    for x in snap_log:
        print("  {} 句 {:>3} 静音点 {:>3} 吸附 {:>3} 比例 {:>3} | {:.2f}s".format(
            x["para"], x["sentences"], x["silences"], x["snap_silence"],
            x["snap_ratio"], x["duration_s"]))
    art = {"schema": "p36-scenes-silence-snap-v1",
           "max_scene_s": MAX_SCENE_S, "scene_count": len(all_scenes),
           "mid_sentence_cuts": len(bad), "over_long": over,
           "snap_log": snap_log, "scenes": all_scenes}
    (OUT / "scenes.json").write_text(json.dumps(art, ensure_ascii=False, indent=1),
                                    encoding="utf-8")
    print()
    print("-> output/phase36_voice/scenes.json")
    return 1 if (bad or over) else 0


if __name__ == "__main__":
    raise SystemExit(main())
