# -*- coding: utf-8 -*-
"""Phase 59 / P59-3：**语音链小样**（定稿 v2.1 · 最小验证，不渲染不出片）。

链路：Yunxi TTS（真实 WordBoundary）→ 静音吸附切景（P41-2 同参数：
-32dB/d=0.28/容差 1.5s/贪心装箱 ≤25s/句中切分=0）→ 词级字幕
（build_cues_from_words_exact + 生产断言）→ Duration Contract
（narration_plan v2）→ **现有 PI 硬门禁**（core_integrity.pre_render_gate，
v2 语义含 G-SEG/G-TL/G-SUB/G-PAD）。

铁律：任何断言失败 ⇒ BLOCKED，如实报告，不静音填充、不降级、不绕过。
产出：`output/p59_ep3/voice_sample/`（para/wav/seg/manifest/timebase/cues/PI 门报告）。
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import pathlib
import re
import socket
import statistics
import subprocess
import sys
import time

import aiohttp
import edge_tts

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
OUT = R / "output" / "p59_ep3" / "voice_sample"
PARA, WAV, SEG = OUT / "para", OUT / "wav", OUT / "seg"
FROZEN = R / "output" / "p59_ep3" / "narration_script_ep3_v2_1_frozen.txt"
FF = str(R / "bin" / "ffmpeg.exe")
FFPROBE = str(R / "bin" / "ffprobe.exe")

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


def sents(t):
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
    r = run([FF, "-v", "info", "-i", str(wav), "-af",
             "silencedetect=noise={}:d={}".format(SIL_NOISE, SIL_MIN_D),
             "-f", "null", "-"])
    txt = (r.stderr or "") + (r.stdout or "")
    starts = [float(m) for m in re.findall(r"silence_start:\s*([0-9.]+)", txt)]
    ends = [float(m) for m in re.findall(r"silence_end:\s*([0-9.]+)", txt)]
    return [round((s + e) / 2.0, 3) for s, e in zip(starts, ends)], len(starts)


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
                raise RuntimeError("音频过短")
            if not words:
                raise RuntimeError("未捕获到 WordBoundary")
            dest.write_bytes(bytes(audio))
            return {"ok": True, "words": words}
        except Exception as exc:                                            # noqa: BLE001
            last = "{}: {}".format(type(exc).__name__, str(exc)[:120])
            time.sleep(min(2 ** attempt, 20))
    return {"ok": False, "error": last, "words": []}


async def main() -> int:
    for d in (PARA, WAV, SEG):
        d.mkdir(parents=True, exist_ok=True)
    blocks = [b.strip() for b in FROZEN.read_text(encoding="utf-8").split("\n\n")
              if b.strip()]
    paras = {}
    for b in blocks:
        pid, _, t = b.partition("\n")
        paras[pid.strip()] = t.strip()
    print("定稿段数:", len(paras))
    frozen_sha = hashlib.sha256(
        FROZEN.read_text(encoding="utf-8").encode("utf-8")).hexdigest()

    # ---- 1. Yunxi 合成（真实 WordBoundary）----
    manifest, para_dur, fails = [], {}, []
    for pid, text in paras.items():
        dest = PARA / "{}.mp3".format(pid)
        res = await synth_words(text, dest)
        if not res["ok"]:
            fails.append({"para": pid, "error": res.get("error")})
            continue
        para_dur[pid] = dur(dest)
        manifest.append({"para": pid, "text_sha256": hashlib.sha256(
            text.encode("utf-8")).hexdigest(), "duration_s": para_dur[pid],
            "words": [{"i": i, "text": w["text"],
                       "start_s": round(w["offset_100ns"] / 1e7, 3),
                       "dur_s": round(w["duration_100ns"] / 1e7, 3)}
                      for i, w in enumerate(res["words"])]})
        print("  {} {:.3f}s words {}".format(pid, para_dur[pid], len(res["words"])))
    if fails:
        print("**BLOCKED** 合成失败:", fails)
        return 1
    (OUT / "words_manifest.json").write_text(json.dumps(
        {"schema": "p59-3-words-manifest-v1", "voice": VOICE, "paras": manifest},
        ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- 2. 静音吸附切景（贪心装箱，句中切分=0）----
    all_scenes, snap_log = [], []
    for pid, text in paras.items():
        wav = WAV / "{}.wav".format(pid)
        run([FF, "-y", "-v", "error", "-i", str(PARA / "{}.mp3".format(pid)),
             "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", str(wav)])
        total = dur(wav) or 0.0
        pts, nsil = silence_points(wav)
        ss = sents(text)
        total_chars = sum(len(s) for s in ss)
        bounds, cum = [], 0
        for i, s in enumerate(ss):
            cum += len(s)
            if i == len(ss) - 1:
                bounds.append(round(total, 3))
                continue
            ratio_t = round(total * cum / total_chars, 3)
            best = min(pts, key=lambda c: abs(c - ratio_t)) if pts else None
            bounds.append(best if (best is not None
                                   and abs(best - ratio_t) <= SNAP_TOL_S) else ratio_t)
        snap_log.append({"para": pid, "sentences": len(ss), "silences": nsil,
                         "snap_silence": sum(1 for b in bounds[:-1]
                                             if b in pts)})
        cur = {"sents": [], "start": 0.0}
        pack = []
        for i, s in enumerate(ss):
            t_end = bounds[i]
            cand_len = t_end - cur["start"]
            if cur["sents"] and cand_len > MAX_SCENE_S:
                pack.append(cur)
                cur = {"sents": [], "start": bounds[i - 1]}
                cand_len = t_end - cur["start"]
            cur["sents"].append({"text": s, "end_t": t_end})
        if cur["sents"]:
            pack.append(cur)
        for k, sc in enumerate(pack):
            sid = "{}_{}".format(pid, k + 1)
            t0, t1 = sc["start"], sc["sents"][-1]["end_t"]
            seg_text = "".join(x["text"] for x in sc["sents"])
            dest = SEG / "{}.wav".format(sid)
            run([FF, "-y", "-v", "error", "-ss", "{:.3f}".format(t0),
                 "-to", "{:.3f}".format(t1), "-i", str(wav),
                 "-c:a", "pcm_s16le", str(dest)])
            all_scenes.append({
                "scene_id": sid, "parent_para": pid,
                "start_s": round(t0, 3), "end_s": round(t1, 3),
                "text": seg_text, "sentence_count": len(sc["sents"]),
                "sentences": [x["text"] for x in sc["sents"]],
                "slice_dur_s": dur(dest), "audio": "seg/{}.wav".format(sid)})
    n_scenes = len(all_scenes)
    print("切景: {} 景".format(n_scenes))

    # ---- 3. 断言：连续性 / 单景 ≤25s / 覆盖全部段 ----
    gate = {"frozen_sha256": frozen_sha, "voice": VOICE, "paras": len(paras),
            "scenes": n_scenes, "checks": {}, "fail": []}
    for pid in paras:
        tot = sum(s["slice_dur_s"] or 0 for s in all_scenes
                  if s["parent_para"] == pid)
        dv = round(tot - (para_dur.get(pid) or 0), 3)
        gate["checks"]["continuity_" + pid] = {
            "sum_slices": round(tot, 3), "para_audio": para_dur.get(pid), "delta": dv}
        if abs(dv) > 0.35:
            gate["fail"].append("切片不连续:{} Δ{:.3f}".format(pid, dv))
    over = [s["scene_id"] for s in all_scenes if (s["slice_dur_s"] or 0) > 25.01]
    if over:
        gate["fail"].append("单景超 25s: " + ",".join(over))
    mid_cut = sum(1 for s in all_scenes
                  if not s["text"].rstrip().endswith(("。", "！", "？")))
    gate["checks"]["mid_sentence_cuts"] = mid_cut
    if mid_cut:
        gate["fail"].append("句中切分 = {}".format(mid_cut))

    # ---- 4. 整条旁白 ----
    work = OUT / "_assemble"
    work.mkdir(exist_ok=True)
    parts = [work / "p{:03d}.wav".format(i) for i in range(n_scenes)]
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
    narr_dur = dur(narr)
    print("旁白: wav {:.3f}s | mp3 {:.3f}s".format(dur(joined) or 0, narr_dur or 0))

    # ---- 5. 时间基 + 词级字幕（生产构建器）----
    cursor, wins = 0.0, []
    for i, s in enumerate(all_scenes):
        d = s["slice_dur_s"]
        wins.append({"scene_id": s["scene_id"],
                     "start_s": round(cursor, 3), "end_s": round(cursor + d, 3),
                     "actual_s": round(d, 3)})
        cursor = round(cursor + d, 3)
    base = round(cursor + TRAILING_S, 3)
    wins[-1]["end_s"] = base
    script = {"segments": [{"scene_id": s["scene_id"], "index": i,
                            "parent_scene_id": s["parent_para"],
                            "narration": s["text"], "duration_s": wins[i]["window_s"]
                            if "window_s" in wins[i] else s["slice_dur_s"],
                            "audio_window_s": [wins[i]["start_s"], wins[i]["end_s"]],
                            "actual_tts_duration_s": s["slice_dur_s"]}
                           for i, s in enumerate(all_scenes)]}
    voice_payload = {"audio": "narration_yunxi.mp3", "provider": "edge-tts",
                     "voice": VOICE, "complete": True, "status": "COMPLETE",
                     "all_segments_ok": True, "segments_total": n_scenes,
                     "audio_time_base_s": base,
                     "narration_duration_s": round(cursor, 3),
                     "segments": [{"scene_id": s["scene_id"], "index": i,
                                   "audio": "media/voice/" + s["audio"],
                                   "duration_s": s["slice_dur_s"],
                                   "text": s["text"], "status": "SUCCESS"}
                                  for i, s in enumerate(all_scenes)],
                     "pause_attribution": {"policy": "v2.1",
                                           "derived_boundary_pause_s": 0.0,
                                           "boundaries": [
                                               {"after_index": i, "pause_s": 0.0,
                                                "kind": "derived"}
                                               for i in range(n_scenes - 1)]}}
    from video_studio.core import captions as C
    from video_studio.core.strip import strip_claims
    man = {p["para"]: p for p in manifest}
    segs = [{"scene_id": s["scene_id"], "narration": s["text"],
             "duration_s": s["slice_dur_s"]} for s in all_scenes]
    wrec = [{"scene_id": s["scene_id"], "start_s": wins[i]["start_s"],
             "end_s": wins[i]["end_s"],
             "actual_s": s["slice_dur_s"]} for i, s in enumerate(all_scenes)]
    cues = C.build_cues_from_words_exact(segs, man, windows=wrec)
    n_sent = 0
    for pid, text in paras.items():
        ss = sents(C.normalize(text))
        merged = C._merge_short(ss, 8)
        n_sent += len(merged)
    viol = C.production_cue_violations(cues, audio_dur_s=narr_dur,
                                       count_range=(n_sent - 2, n_sent + 2))
    durs = [c["dur"] for c in cues]
    span = round(max(c["end"] for c in cues) - min(c["start"] for c in cues), 3)
    ovl = sum(1 for i in range(1, len(cues)) if cues[i]["start"] < cues[i - 1]["end"] - 1e-9)
    gate["checks"]["captions"] = {
        "cues": len(cues), "sentences_expected": n_sent, "span_s": span,
        "audio_s": narr_dur, "span_delta": round(span - (narr_dur or 0), 3),
        "median_dur": round(statistics.median(durs), 3) if durs else None,
        "overlap": ovl, "violations": viol}
    if viol:
        gate["fail"].append("字幕生产断言: " + "; ".join(viol)[:200])
    (OUT / "cues.json").write_text(json.dumps(cues, ensure_ascii=False, indent=1),
                                   encoding="utf-8")

    # ---- 6. Duration Contract v2 + PI 硬门禁 ----
    from video_studio.core import narration as CN
    from video_studio.core import integrity as CI
    plan = CN.narration_plan(script, voice_payload, config=None)
    pad = max(base - (narr_dur or 0), 0.0)
    pir = CI.pre_render_gate(script["segments"], voice_payload, base,
                             policy=None, narration_duration_s=narr_dur,
                             narration_plan=plan, cues=cues, narration_padding_s=pad)
    gate["checks"]["duration_contract"] = {
        "audio_time_base_s": plan.get("audio_time_base_s"),
        "expected_base": base, "match": abs((plan.get("audio_time_base_s") or 0) - base) <= 0.05,
        "concat_consistent": plan.get("concat_consistent"),
        "narration_mp3_s": narr_dur, "trailing_s": TRAILING_S}
    gate["checks"]["pre_render_gate"] = {
        "blocked": pir.get("blocked"), "reasons": pir.get("reasons"),
        "detail": pir.get("detail")}
    if pir.get("blocked"):
        gate["fail"].append("PI 硬门禁阻断: " + "; ".join(
            map(str, pir.get("reasons") or []))[:300])

    (OUT / "timebase_sample.json").write_text(json.dumps(
        {"schema": "p59-3-timebase-sample-v1", "voice": VOICE,
         "audio_time_base_s": base, "scene_count": n_scenes,
         "sum_measured_speech_s": round(cursor, 3), "trailing_pad_s": TRAILING_S,
         "windows": wins, "snap_log": snap_log}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    (OUT / "voice_sample_payload.json").write_text(json.dumps(
        voice_payload, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "script_sample.json").write_text(json.dumps(
        script, ensure_ascii=False, indent=1), encoding="utf-8")

    verdict = "PASS" if not gate["fail"] else "BLOCKED"
    gate["verdict"] = verdict
    (OUT / "voice_sample_report.json").write_text(json.dumps(
        gate, ensure_ascii=False, indent=1), encoding="utf-8")
    print()
    print("== 小样结论:", verdict, "==")
    for f in gate["fail"]:
        print("  FAIL:", f)
    print("checks.captions:", json.dumps(gate["checks"]["captions"],
                                         ensure_ascii=False))
    print("checks.pre_render_gate.blocked:", pir.get("blocked"))
    print("->", OUT.relative_to(R))
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
