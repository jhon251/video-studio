# -*- coding: utf-8 -*-
"""Phase 58 / P58-7：**云希重配音**（zh-CN-YunxiNeural）——整条语音链重建。

授权背景：用户选定 Yunxi 样本替换旁白音色（ licensed neural voice，edge-tts）。

铁律（本轮设计）：
  · **36 景结构与逐景文本不变**（text_sha256 守恒）⇒ F14 画面 pins（scene_id→素材）
    与字幕句流全部有效，只有音频层换掉；
  · 重切景 = **同句子分组**（v6.5 `scenes.json` 的逐景句子列表），新音频上重新
    「句末比例 → 静音中点吸附」（P41-2 同参数：-32dB / d=0.28 / 容差 1.5s）；
  · 断言（违反即 fail-closed）：36 景、逐景文本 sha == v6.5、单景 ≤25s、
    Σ切片 == 段音频（±0.35s）、9 段全部成功且带 WordBoundary。

产出：`output/p58_voice_yunxi/{para/*.mp3, seg/*.wav, wav/*.wav,
words_manifest.json, voice_output_yunxi.json, timebase_yunxi.json,
script_yunxi_36seg.json, scenes.json, runs_by_scene.json, recoveries.json,
narration_yunxi.mp3}`
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import pathlib
import re
import socket
import subprocess
import sys
import time

import aiohttp
import edge_tts

R = pathlib.Path(r"C:\mp4agent\video-studio")
OUT = R / "output" / "p58_voice_yunxi"
PARA, WAV, SEG = OUT / "para", OUT / "wav", OUT / "seg"
OLD = R / "output" / "phase36_voice"
FF = str(R / "bin" / "ffmpeg.exe")
FFPROBE = str(R / "bin" / "ffprobe.exe")
SCRIPT = R / "output/p36_script/v6_5_fulltext.json"
sys.stdout.reconfigure(encoding="utf-8")

VOICE = "zh-CN-YunxiNeural"
MAX_ATTEMPTS = 5
MAX_SCENE_S = 25.0
SNAP_TOL_S = 1.5
SIL_NOISE, SIL_MIN_D = "-32dB", 0.28
TRAILING_S = 2.0


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, errors="ignore")


def dur(p):
    r = run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(p)])
    v = (r.stdout or "").strip().splitlines()
    return round(float(v[0]), 3) if v and v[0] else None


def sha_text(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


async def synth_words(text: str, dest: pathlib.Path):
    last = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            conn = aiohttp.TCPConnector(family=socket.AF_INET, ttl_dns_cache=300)
            comm = edge_tts.Communicate(text, VOICE, connector=conn,
                                        boundary="WordBoundary")
            audio, words = bytearray(), []
            async for chunk in comm.stream():
                if chunk.get("type") == "audio":
                    audio.extend(chunk["data"])
                elif chunk.get("type") == "WordBoundary":
                    words.append({"offset_100ns": chunk.get("offset"),
                                  "duration_100ns": chunk.get("duration"),
                                  "text": chunk.get("text")})
            if len(audio) < 1024:
                raise RuntimeError("音频过短（{} 字节）".format(len(audio)))
            if not words:
                raise RuntimeError("未捕获到 WordBoundary")
            dest.write_bytes(bytes(audio))
            return {"ok": True, "attempts": attempt, "words": words}
        except Exception as exc:                                            # noqa: BLE001
            last = "{}: {}".format(type(exc).__name__, str(exc)[:140])
            time.sleep(min(2 ** attempt, 20))
    return {"ok": False, "attempts": MAX_ATTEMPTS, "error": last, "words": []}


def silence_points(wav: pathlib.Path):
    r = run([FF, "-v", "info", "-i", str(wav), "-af",
             "silencedetect=noise={}:d={}".format(SIL_NOISE, SIL_MIN_D),
             "-f", "null", "-"])
    txt = (r.stderr or "") + (r.stdout or "")
    starts = [float(m) for m in re.findall(r"silence_start:\s*([0-9.]+)", txt)]
    ends = [float(m) for m in re.findall(r"silence_end:\s*([0-9.]+)", txt)]
    return [round((s + e) / 2.0, 3) for s, e in zip(starts, ends)], len(starts)


async def main() -> int:
    for d in (PARA, WAV, SEG):
        d.mkdir(parents=True, exist_ok=True)
    doc = json.loads(SCRIPT.read_text(encoding="utf-8"))
    para_text = {p["id"]: p["text"].strip() for p in doc["paragraphs"]}
    old_scenes = json.loads((OLD / "scenes.json").read_text(encoding="utf-8"))["scenes"]
    fails = []

    # ---- 1. 逐段合成（Yunxi + WordBoundary）----
    manifest, para_dur = [], {}
    for pid, text in para_text.items():
        dest = PARA / "{}.mp3".format(pid)
        res = await synth_words(text, dest)
        if not res["ok"]:
            fails.append({"para": pid, "error": res.get("error")})
            print("  {} **FAIL** {}".format(pid, res.get("error")))
            continue
        para_dur[pid] = dur(dest)
        manifest.append({"para": pid, "text_sha256": sha_text(text),
                         "duration_s": para_dur[pid],
                         "words": [{"i": i, "text": w["text"],
                                    "start_s": round(w["offset_100ns"] / 1e7, 3),
                                    "dur_s": round(w["duration_100ns"] / 1e7, 3)}
                                   for i, w in enumerate(res["words"])]})
        print("  {} {:.3f}s words {}".format(pid, para_dur[pid], len(res["words"])))
    if fails:
        print("**FAIL-CLOSED**：合成失败段", fails)
        return 1
    (OUT / "words_manifest.json").write_text(json.dumps(
        {"schema": "p58-7-words-manifest-v1", "voice": VOICE,
         "unit": "offset/duration 原始为 100ns，已换算为秒",
         "paras": manifest}, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- 2. 同分组重切景（P41-2 同参数；分组 = v6.5 scenes.json）----
    all_scenes, snap_log = [], []
    for pid, text in para_text.items():
        src, wav = PARA / "{}.mp3".format(pid), WAV / "{}.wav".format(pid)
        run([FF, "-y", "-v", "error", "-i", str(src), "-ar", "24000", "-ac", "1",
             "-c:a", "pcm_s16le", str(wav)])
        total = dur(wav) or 0.0
        pts, nsil = silence_points(wav)
        group = [s for s in old_scenes if s["parent_para"] == pid]
        sents_all = [x["text"] for s in group for x in
                     [{"text": t} for t in s["sentences"]]]
        total_chars = sum(len(s) for s in sents_all)
        # 句末比例时刻 → 吸附静音中点（末句 = 段末）
        bounds, cum = [], 0
        for i, s in enumerate(sents_all):
            cum += len(s)
            if i == len(sents_all) - 1:
                bounds.append(round(total, 3))
                continue
            ratio_t = round(total * cum / total_chars, 3)
            best = min(pts, key=lambda c: abs(c - ratio_t)) if pts else None
            bounds.append(best if (best is not None
                                   and abs(best - ratio_t) <= SNAP_TOL_S) else ratio_t)
        snap_log.append({"para": pid, "sentences": len(sents_all),
                         "silences": nsil, "duration_s": total})
        # 按原分组切
        k, si = 0, 0
        for old in group:
            n = old["sentence_count"]
            t0 = bounds[si - 1] if si else 0.0
            t1 = bounds[si + n - 1]
            sid = "{}_{}".format(pid, k + 1)
            text_new = "".join(sents_all[si:si + n])
            if sha_text(text_new) != old["text_sha256"]:
                fails.append({"scene": sid, "why": "文本 sha 与 v6.5 不符"})
            dest = SEG / "{}.wav".format(sid)
            run([FF, "-y", "-v", "error", "-ss", "{:.3f}".format(t0),
                 "-to", "{:.3f}".format(t1), "-i", str(wav),
                 "-c:a", "pcm_s16le", str(dest)])
            d_slice = dur(dest)
            all_scenes.append({
                "scene_id": sid, "parent_para": pid,
                "start_s": round(t0, 3), "end_s": round(t1, 3),
                "window_s": round(t1 - t0, 3), "slice_dur_s": d_slice,
                "text": text_new, "text_sha256": sha_text(text_new),
                "sentence_count": n, "sentences": sents_all[si:si + n],
                "snaps_old": old["snaps"], "audio": "seg/{}.wav".format(sid)})
            if (d_slice or 0) > MAX_SCENE_S + 0.01:
                fails.append({"scene": sid, "why": "单景 {:.2f}s > 25s".format(d_slice)})
            si += n
            k += 1
    if len(all_scenes) != 36:
        fails.append({"why": "景数 {} != 36".format(len(all_scenes))})
    for s in all_scenes:
        if not (SEG / "{}.wav".format(s["scene_id"])).is_file():
            fails.append({"scene": s["scene_id"], "why": "切片缺失"})
    # Σ切片 == 段音频
    for pid in para_text:
        tot = sum(s["slice_dur_s"] or 0 for s in all_scenes if s["parent_para"] == pid)
        if abs(tot - (para_dur.get(pid) or 0)) > 0.35:
            fails.append({"para": pid, "why": "Σ切片 {:.3f} != 段 {:.3f}".format(
                tot, para_dur.get(pid) or 0)})
    if fails:
        print("**FAIL-CLOSED**：{} 项".format(len(fails)))
        for f in fails[:8]:
            print("  ", f)
        return 1
    (OUT / "scenes.json").write_text(json.dumps(
        {"schema": "p58-7-scenes-v1", "voice": VOICE, "scene_count": 36,
         "mid_sentence_cuts": 0, "note": "分组 = v6.5 scenes.json（文本/句结构守恒）",
         "snap_log": snap_log, "scenes": all_scenes}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print("切景: 36 景全过（文本 sha 守恒 / ≤25s / Σ切片==段音频）")

    # ---- 3. 整条旁白（wav concat → mp3 48k 24kHz 单声道）----
    work = OUT / "_assemble"
    work.mkdir(exist_ok=True)
    parts = [work / "p{:03d}.wav".format(i) for i in range(36)]
    for w, s in zip(parts, all_scenes):
        run([FF, "-y", "-v", "error", "-i", str(SEG / "{}.wav".format(s["scene_id"])),
             "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", str(w)])
    lst = work / "concat.txt"
    lst.write_text("".join("file '{}'\n".format(p.as_posix()) for p in parts),
                   encoding="utf-8")
    joined = work / "narration_joined.wav"
    run([FF, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
         "-c", "copy", str(joined)])
    narr = OUT / "narration_yunxi.mp3"
    run([FF, "-y", "-v", "error", "-i", str(joined), "-c:a", "libmp3lame", "-b:a",
         "48k", "-ar", "24000", "-ac", "1", str(narr)])
    print("旁白拼装: wav {:.3f}s | mp3 {:.3f}s".format(dur(joined) or 0, dur(narr) or 0))

    # ---- 4. 时基 + 脚本产物（窗口 = 切片实测；末景 +2s trailing）----
    cursor, wins = 0.0, []
    for i, s in enumerate(all_scenes):
        d = s["slice_dur_s"]
        wins.append({"index": i, "scene_id": s["scene_id"],
                     "parent_scene_id": s["parent_para"],
                     "start_s": round(cursor, 3), "end_s": round(cursor + d, 3),
                     "window_s": round(d, 3), "actual_s": round(d, 3),
                     "pause_s": 0.0, "sentence_count": s["sentence_count"],
                     "text_sha256": s["text_sha256"],
                     "audio": "seg/{}.wav".format(s["scene_id"])})
        cursor = round(cursor + d, 3)
    base = round(cursor + TRAILING_S, 3)
    wins[-1]["end_s"] = base
    wins[-1]["window_s"] = round(base - wins[-1]["start_s"], 3)
    wins[-1]["trailing_s"] = TRAILING_S
    timebase = {"schema": "p58-7-timebase-v1", "voice": VOICE,
                "audio_time_base_s": base, "scene_count": 36,
                "sum_measured_speech_s": round(cursor, 3),
                "sum_pause_s": 0.0, "trailing_pad_s": TRAILING_S,
                "mid_sentence_cuts": 0, "max_scene_s": max(
                    w["window_s"] for w in wins), "zero_llm": True,
                "windows": wins}
    (OUT / "timebase_yunxi.json").write_text(json.dumps(
        timebase, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- 5. voice_output + 渲染用脚本（结构 = v6.5 同构）----
    segs_out = []
    for i, s in enumerate(all_scenes):
        segs_out.append({"scene_id": s["scene_id"], "index": i,
                         "parent_scene_id": s["parent_para"], "text": s["text"],
                         "text_sha256": s["text_sha256"],
                         "audio": "para/{}.mp3".format(s["parent_para"]),
                         "seg_audio": "seg/{}.wav".format(s["scene_id"]),
                         "duration_s": s["slice_dur_s"],
                         "window_s": wins[i]["window_s"],
                         "start_s": wins[i]["start_s"], "end_s": wins[i]["end_s"],
                         "sentence_count": s["sentence_count"],
                         "status": "SUCCESS", "voice": VOICE,
                         "provider": "edge-tts"})
    voice_out = {"schema": "p58-7-voice-output-v1", "voice": VOICE,
                 "provider": "edge-tts", "text_source": "v6.5（word-for-word）",
                 "audio": "narration_yunxi.mp3",
                 "narration_duration_s": round(cursor, 3),
                 "audio_time_base_s": base,
                 "segments_total": 36, "all_segments_ok": True,
                 "zero_llm": True, "segments": segs_out,
                 "pause_attribution": {
                     "policy": "v2.1", "source": "段落级合成 + 同分组静音吸附切景"
                     " ⇒ 景间不加额外静音（pause=0）",
                     "default_pause_s": 0.0, "derived_boundary_pause_s": 0.0,
                     "by_index": {}, "boundaries": [
                         {"after_index": i, "pause_s": 0.0, "kind": "derived"}
                         for i in range(35)]}}
    (OUT / "voice_output_yunxi.json").write_text(json.dumps(
        voice_out, ensure_ascii=False, indent=1), encoding="utf-8")

    old_sc = json.loads((R / "output/phase36_script_sandbox/"
                         "script_p36_v65_36seg.json").read_text(encoding="utf-8"))
    old_by_id = {s["scene_id"]: s for s in old_sc["segments"]}
    new_segments = []
    for i, s in enumerate(all_scenes):
        o = old_by_id[s["scene_id"]]
        new_segments.append({
            "scene_id": s["scene_id"], "index": i,
            "parent_scene_id": s["parent_para"], "chapter": o.get("chapter"),
            "narration": s["text"], "narration_sha256": s["text_sha256"],
            "duration_s": wins[i]["window_s"],
            "audio_window_s": [wins[i]["start_s"], wins[i]["end_s"]],
            "actual_tts_duration_s": s["slice_dur_s"], "pause_budget_s": 0.0,
            "timing_source": "p58-7 yunxi silence-snap (same grouping as v6.5)",
            "text_source": o.get("text_source")})
    script_out = {"schema": "p58-7-script-v1", "voice": VOICE,
                  "text_source": old_sc.get("text_source"),
                  "scene_count": 36, "segments": new_segments,
                  "audio_time_base_s": base, "zero_llm": True,
                  "note": "与 v6.5 逐景文本相同（sha 守恒）；窗口 = Yunxi 实测"}
    (OUT / "script_yunxi_36seg.json").write_text(json.dumps(
        script_out, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- 6. runs_by_scene（P52-1 口径）+ recoveries（P43-1 全片口径）----
    runs = {}
    for s in all_scenes:
        wav = SEG / "{}.wav".format(s["scene_id"])
        r = run([FF, "-v", "info", "-i", str(wav), "-af",
                 "silencedetect=noise=-30dB:d=0.05", "-f", "null", "-"])
        txt = (r.stderr or "") + (r.stdout or "")
        sts = [float(x) for x in re.findall(r"silence_start:\s*([0-9.]+)", txt)]
        ens = [float(x) for x in re.findall(r"silence_end:\s*([0-9.]+)", txt)]
        rr, cur = [], 0.0
        for a, b in zip(sts, ens):
            if a > cur:
                rr.append([round(cur, 3), round(a, 3)])
            cur = max(cur, b)
        if cur < (s["slice_dur_s"] or 0) - 0.02:
            rr.append([round(cur, 3), round(s["slice_dur_s"], 3)])
        runs[s["scene_id"]] = [x for x in rr if x[1] - x[0] > 0.02]
    (OUT / "runs_by_scene.json").write_text(json.dumps(
        {"schema": "p58-7-runs-v1", "voice": VOICE, "scene_count": 36,
         "runs_by_scene": runs,
         "total_runs": sum(len(v) for v in runs.values())},
        ensure_ascii=False, indent=1), encoding="utf-8")
    r = run([FF, "-v", "info", "-i", str(narr), "-af",
             "silencedetect=noise=-35dB:d=0.28", "-f", "null", "-"])
    txt = (r.stderr or "") + (r.stdout or "")
    ends = [round(float(x), 3) for x in
            re.findall(r"silence_end:\s*([0-9.]+)", txt)]
    (OUT / "recoveries.json").write_text(json.dumps(
        {"schema": "p58-7-recoveries-v1", "voice": VOICE,
         "absolute_count": len(ends), "recoveries": {
             str(i): ends}, "note": "全片口径（整条 Yunxi 旁白 -35dB/0.28）"},
        ensure_ascii=False, indent=1), encoding="utf-8")

    print()
    print("P58-7 完成：36 景 / 时间基 {:.3f}s（v6.5 为 695.528）/ 全部断言过".format(base))
    print("-> " + str(OUT.relative_to(R)))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
