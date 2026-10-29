# -*- coding: utf-8 -*-
"""Phase 45 / P45-3：**词级重配音（O-voice）** —— 同音色同文本重合成 + WordBoundary 捕获。

· 音色 `zh-CN-XiaoxiaoNeural`（与 v6.5 同）；文本 = v6.5 九段（word-for-word）；
· **强制 IPv4**（P33 修法）；
· 逐词捕获 `WordBoundary`（offset / duration / text）⇒ `words_manifest`（段级 + 全片）；
· **一致性断言**：新音频逐段时长 vs 旧音频偏差 **≤2%**（同引擎同文本预期一致）；
  文本 sha 守恒；超限 ⇒ fail-closed 报告，**不静默采用**。

产出：`output/phase45_voice/{para/*.mp3, words_manifest.json, voice_output_v65_ovoice.json}`
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
OUT = R / "output" / "phase45_voice"
PARA = OUT / "para"
OLD = R / "output" / "phase36_voice"
FFPROBE = str(R / "bin" / "ffprobe.exe")
SCRIPT = R / "output/p36_script/v6_5_fulltext.json"
sys.stdout.reconfigure(encoding="utf-8")

VOICE = "zh-CN-XiaoxiaoNeural"
MAX_ATTEMPTS = 5
TOL = 0.02          # 允许的时长偏差（≤2%）


def dur(p):
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(p)], capture_output=True, text=True)
    v = (r.stdout or "").strip().splitlines()
    return round(float(v[0]), 3) if v and v[0] else None


async def synth_words(text: str, dest: pathlib.Path):
    """合成并把 **WordBoundary** 逐词落盘（offset/duration 单位 100ns）。"""
    last = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            conn = aiohttp.TCPConnector(family=socket.AF_INET, ttl_dns_cache=300)
            # **关键（实测）**：edge-tts 7.2.8 的 `boundary` **默认是 `SentenceBoundary`**
            # ⇒ 只吐句界、**不吐词界**（首版 9 段全部「未捕获到 WordBoundary」而
            # fail-closed）。必须显式传 `WordBoundary`。
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
                raise RuntimeError("未捕获到 WordBoundary（{} 词）".format(len(words)))
            dest.write_bytes(bytes(audio))
            return {"ok": True, "attempts": attempt, "words": words}
        except Exception as exc:                                            # noqa: BLE001
            last = "{}: {}".format(type(exc).__name__, str(exc)[:140])
            time.sleep(min(2 ** attempt, 20))
    return {"ok": False, "attempts": MAX_ATTEMPTS, "error": last, "words": []}


async def main() -> int:
    doc = json.loads(SCRIPT.read_text(encoding="utf-8"))
    paras = doc["paragraphs"]
    oldv = json.loads((OLD / "voice_output_v65.json").read_text(encoding="utf-8"))
    old_dur = {s["scene_id"]: float(s.get("duration_s") or 0)
               for s in oldv["segments"]}
    PARA.mkdir(parents=True, exist_ok=True)
    segs, manifest, fails = [], [], []
    for p in paras:
        pid = p["id"]
        text = p["text"].strip()
        dest = PARA / "{}.mp3".format(pid)
        res = await synth_words(text, dest)
        if not res["ok"]:
            fails.append({"para": pid, "error": res.get("error")})
            print("  {} **FAIL** {}".format(pid, res.get("error")))
            continue
        d_new = dur(dest)
        d_old = old_dur.get(pid) or 0
        dev = abs(d_new - d_old) / d_old if d_old else 0
        sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
        segs.append({"scene_id": pid, "index": len(segs), "parent_scene_id": pid,
                     "text": text, "text_sha256": sha,
                     "audio": "para/{}.mp3".format(pid),
                     "duration_s": d_new, "old_duration_s": d_old,
                     "deviation": round(dev, 4), "within_2pct": dev <= TOL,
                     "bytes": dest.stat().st_size, "status": "SUCCESS",
                     "word_count": len(res["words"]), "voice": VOICE,
                     "provider": "edge-tts"})
        manifest.append({"para": pid, "text_sha256": sha, "duration_s": d_new,
                         "words": [{"i": i, "text": w["text"],
                                    "start_s": round(w["offset_100ns"] / 1e7, 3),
                                    "dur_s": round(w["duration_100ns"] / 1e7, 3)}
                                   for i, w in enumerate(res["words"])]})
        print("  {} new {:>7.3f}s old {:>7.3f}s dev {:>6.2%} words {:>3} {}".format(
            pid, d_new, d_old, dev, len(res["words"]),
            "OK" if dev <= TOL else "**超 2%**"))
    total = round(sum(float(s["duration_s"]) for s in segs), 3)
    over = [s["scene_id"] for s in segs if not s["within_2pct"]]
    art = {"schema": "p45-3-ovoice-v1", "voice": VOICE,
           "text_source": "v6.5（word-for-word）",
           "segments_total": len(segs), "all_segments_ok": not fails,
           "narration_duration_s": total,
           "old_narration_duration_s": round(sum(old_dur.values()), 3),
           "tolerance": TOL, "over_tolerance_paras": over,
           "failed": fails, "segments": segs,
           "script_sha256": hashlib.sha256(SCRIPT.read_bytes()).hexdigest(),
           "zero_llm": True}
    (OUT / "voice_output_v65_ovoice.json").write_text(
        json.dumps(art, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "words_manifest.json").write_text(json.dumps(
        {"schema": "p45-3-words-manifest-v1", "voice": VOICE,
         "unit": "offset/duration 原始为 100ns，已换算为秒",
         "paras": manifest}, ensure_ascii=False, indent=1), encoding="utf-8")
    print()
    print("Σ新 {:.3f}s | Σ旧 {:.3f}s | 超容差段 {} | 失败 {}".format(
        total, art["old_narration_duration_s"], over or "无", len(fails)))
    print("all_segments_ok = {}".format(not fails))
    if fails or over:
        print("=> **fail-closed**：存在失败段或超容差段，交由监理裁定，不静默采用")
        return 1
    print("-> output/phase45_voice/{voice_output_v65_ovoice.json, words_manifest.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
