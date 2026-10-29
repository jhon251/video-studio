# -*- coding: utf-8 -*-
"""Phase 36 / P36-4 步骤 1：**段落级 TTS**（9 段整段合成，韵律连贯）。

· 输入：`output/p36_script/v6_5_fulltext.json`（9 段）
· 每段**整段合成**（不切句）⇒ 段内韵律连贯；
· 输出：`output/phase36_voice/para/P01.mp3` … `P09.mp3`；
· 逐段状态/字节/时长/文本哈希 → `voice_output_v65.json`（沿用既有契约）；
· 完整性：逐段重试（指数退避），**任一段失败 ⇒ fail-closed**；
· edge-tts 7.2.8 + **强制 IPv4**（TTS 同款修法；见 P33-3）。
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
OUT = R / "output" / "phase36_voice"
PARA = OUT / "para"
FFPROBE = str(R / "bin" / "ffprobe.exe")
sys.stdout.reconfigure(encoding="utf-8")

VOICE = "zh-CN-XiaoxiaoNeural"
MAX_ATTEMPTS = 5


def dur(p):
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(p)], capture_output=True, text=True)
    v = (r.stdout or "").strip().splitlines()
    return round(float(v[0]), 3) if v and v[0] else None


async def synth(text: str, dest: pathlib.Path) -> dict:
    """整段合成 + 重试（IPv4 强制）。"""
    last = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            conn = aiohttp.TCPConnector(family=socket.AF_INET, ttl_dns_cache=300)
            comm = edge_tts.Communicate(text, VOICE, connector=conn)
            buf = bytearray()
            async for chunk in comm.stream():
                if chunk.get("type") == "audio":
                    buf.extend(chunk["data"])
            if len(buf) < 1024:
                raise RuntimeError("音频过短（{} 字节）".format(len(buf)))
            dest.write_bytes(bytes(buf))
            return {"attempts": attempt, "ok": True}
        except Exception as exc:                                            # noqa: BLE001
            last = "{}: {}".format(type(exc).__name__, str(exc)[:150])
            time.sleep(min(2 ** attempt, 20))
    return {"attempts": MAX_ATTEMPTS, "ok": False, "error": last}


async def main() -> int:
    d = json.loads((R / "output/p36_script/v6_5_fulltext.json")
                   .read_text(encoding="utf-8"))
    paras = d["paragraphs"]
    PARA.mkdir(parents=True, exist_ok=True)
    print("段落数 {} | 音色 {}".format(len(paras), VOICE))
    segs, failed = [], []
    for p in paras:
        pid = p["id"]
        text = p["text"].strip()
        dest = PARA / "{}.mp3".format(pid)
        if dest.is_file() and dest.stat().st_size > 1024:
            r = {"attempts": 0, "ok": True, "reused": True}
        else:
            r = await synth(text, dest)
        if not r["ok"]:
            failed.append({"para": pid, "error": r.get("error")})
            print("  {} FAIL {}".format(pid, r.get("error")))
            continue
        secs = dur(dest)
        segs.append({"scene_id": pid, "index": len(segs), "parent_scene_id": pid,
                     "text": text,
                     "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                     "audio": "para/{}.mp3".format(pid),
                     "duration_s": secs, "bytes": dest.stat().st_size,
                     "status": "SUCCESS", "attempts": r["attempts"],
                     "voice": VOICE, "provider": "edge-tts"})
        print("  {} {:>7.3f}s {:>9,}B attempts={}".format(pid, secs or 0,
                                                         dest.stat().st_size,
                                                         r["attempts"]))
    total = round(sum(float(s["duration_s"] or 0) for s in segs), 3)
    art = {
        "schema": "voice-output-v1-p36-paragraph",
        "provider": "edge-tts", "voice": VOICE,
        "segments_total": len(segs), "all_segments_ok": not failed,
        "narration_duration_s": total,
        "segments": segs,
        "pause_attribution": {
            "policy": "v2.1",
            "source": ("**段落级合成**（P36-4）：段内韵律由 TTS 自身承担，"
                       "段间**不加额外静音**（pause=0），与 P33-3 口径一致"),
            "default_pause_s": 0.0, "derived_boundary_pause_s": 0.0,
            "boundaries": [{"after_index": i, "pause_s": 0.0, "kind": "derived"}
                           for i in range(max(len(segs) - 1, 0))],
        },
        "failed": failed,
        "script_source": "output/p36_script/v6_5_fulltext.json",
        "script_sha256": hashlib.sha256(
            (R / "output/p36_script/v6_5_fulltext.json").read_bytes()).hexdigest(),
        "zero_llm": True,
    }
    (OUT / "voice_output_v65.json").write_text(
        json.dumps(art, ensure_ascii=False, indent=1), encoding="utf-8")
    print()
    print("Σ段落语音 = {:.3f}s | 失败 {} 段".format(total, len(failed)))
    print("all_segments_ok = {}".format(not failed))
    print("-> output/phase36_voice/voice_output_v65.json")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
