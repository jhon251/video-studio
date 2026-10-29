# -*- coding: utf-8 -*-
"""P33-3 核心：**v4.1 逐段配音入库**（edge-tts 原音色 `zh-CN-XiaoxiaoNeural`）。

产出 `output/phase34_voice/`：
  · `seg/<scene_id>.mp3`        逐段音频（**时长 = 新时基唯一权威**）
  · `voice_output_v42.json`     既有 `voice_output` 契约的产物（段/时长/状态/文本哈希）
  · `synth_ledger.json`         逐段账面（尝试次数、错误码、字节、时长、耗时）

纪律（沿用既有 voice 契约）：
  · 完整性与重试：逐段独立状态；网络类错误可重试（指数退避）；**任一段最终失败 ⇒ fail-closed**；
  · 文本**逐字不改**（`narration_sha256` 与脚本一致）；
  · 成功段复用：台账里文本哈希+音色相同且文件合法 ⇒ 不再请求 TTS（可重入）。
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import pathlib
import socket
import sys
import time

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")

SCRIPT = R / "output/phase34_script_sandbox/script_p34_v42_40seg.json"
OUT = R / "output/phase34_voice"
SEGD = OUT / "seg"
FFPROBE = R / "bin" / "ffprobe.exe"
VOICE = "zh-CN-XiaoxiaoNeural"
PROVIDER = "edge-tts"
MAX_ATTEMPTS = 3
CONCURRENCY = 4
RETRYABLE = ("ClientConnectorError", "ClientOSError", "ServerDisconnectedError",
             "TimeoutError", "WSServerHandshakeError", "ConnectionResetError")


def sha_text(t: str) -> str:
    return hashlib.sha256((t or "").encode("utf-8")).hexdigest()


def probe_dur(p: pathlib.Path):
    import subprocess
    r = subprocess.run([str(FFPROBE), "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(p)],
                       capture_output=True, text=True)
    v = (r.stdout or "").strip().splitlines()
    return round(float(v[0]), 3) if v and v[0] else None


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    SEGD.mkdir(parents=True, exist_ok=True)
    script = json.loads(SCRIPT.read_text(encoding="utf-8"))
    segs = script["segments"]

    import aiohttp
    import edge_tts

    ledger_p = OUT / "synth_ledger.json"
    ledger = {"schema": "p34-v42-synth-ledger-v1", "voice": VOICE,
              "provider": PROVIDER, "segments": {}, "requests": 0, "retries": 0}
    if ledger_p.is_file():
        try:
            ledger = json.loads(ledger_p.read_text(encoding="utf-8"))
            ledger.setdefault("segments", {})
        except Exception:                                                   # noqa: BLE001
            pass
    prev = ledger.get("segments") or {}

    async def synth_one(sid, text, sem, results):
        mp3 = SEGD / "{}.mp3".format(sid)
        th = sha_text(text)
        old = prev.get(sid) or {}
        # 复用：文本与音色未变且文件合法
        if (old.get("text_sha256") == th and old.get("voice") == VOICE
                and mp3.is_file() and mp3.stat().st_size > 1024):
            d = probe_dur(mp3)
            if d and d > 0.2:
                results[sid] = {"status": "REUSED", "duration_s": d,
                                "bytes": mp3.stat().st_size, "text_sha256": th,
                                "voice": VOICE, "attempts": 0, "audio": str(mp3),
                                "error_code": "", "error_detail": ""}
                print("  [{}] REUSED {:.3f}s".format(sid, d), flush=True)
                return
        async with sem:
            for attempt in range(1, MAX_ATTEMPTS + 1):
                try:
                    conn = aiohttp.TCPConnector(family=socket.AF_INET, ttl_dns_cache=300)
                    c = edge_tts.Communicate(text, VOICE, connector=conn)
                    try:
                        await c.save(str(mp3))
                    finally:
                        await conn.close()
                    ledger["requests"] = int(ledger.get("requests") or 0) + 1
                    if attempt > 1:
                        ledger["retries"] = int(ledger.get("retries") or 0) + 1
                    d = probe_dur(mp3)
                    if not d or d <= 0.2:
                        raise RuntimeError("SYNTH_EMPTY_AUDIO")
                    results[sid] = {"status": "SUCCESS", "duration_s": d,
                                    "bytes": mp3.stat().st_size, "text_sha256": th,
                                    "voice": VOICE, "attempts": attempt,
                                    "audio": str(mp3), "error_code": "",
                                    "error_detail": ""}
                    print("  [{}] SUCCESS {:.3f}s (attempt {})".format(sid, d, attempt),
                          flush=True)
                    return
                except Exception as exc:                                    # noqa: BLE001
                    name = type(exc).__name__
                    etxt = "{}: {}".format(name, str(exc)[:160])
                    retryable = any(m in name or m in str(exc) for m in RETRYABLE)
                    if retryable and attempt < MAX_ATTEMPTS:
                        print("  [{}] retry {}/{} ({})".format(
                            sid, attempt, MAX_ATTEMPTS, name), flush=True)
                        await asyncio.sleep(1.5 * attempt)
                        continue
                    results[sid] = {"status": "FAILED", "duration_s": None,
                                    "bytes": (mp3.stat().st_size if mp3.is_file() else 0),
                                    "text_sha256": th, "voice": VOICE,
                                    "attempts": attempt,
                                    "error_code": ("TTS_NETWORK" if retryable
                                                   else "TTS_SYNTHESIS_FAILED"),
                                    "error_detail": etxt, "audio": ""}
                    print("  [{}] FAILED {}".format(sid, etxt), flush=True)
                    return

    async def run_all():
        sem = asyncio.Semaphore(CONCURRENCY)
        results = {}
        await asyncio.gather(*[
            synth_one(str(s.get("scene_id") or "S%02d" % (i + 1)),
                      s.get("narration") or "", sem, results)
            for i, s in enumerate(segs)])
        return results

    t0 = time.time()
    results = asyncio.run(run_all())
    dt = time.time() - t0

    ledger["segments"] = {**prev, **results}
    ledger["elapsed_s"] = round(dt, 1)
    ledger["segments_total"] = len(segs)
    ledger["failed"] = [k for k, v in results.items() if v["status"] == "FAILED"]
    ledger_p.write_text(json.dumps(ledger, ensure_ascii=False, indent=1), encoding="utf-8")

    print()
    print("合成完成 {:.1f}s | 请求 {} | 重试 {} | 失败 {}".format(
        dt, ledger["requests"], ledger["retries"], len(ledger["failed"])))

    # ---- 组装既有 voice_output 契约 ----
    vsegs, total = [], 0.0
    for i, s in enumerate(segs):
        sid = str(s.get("scene_id") or "S%02d" % (i + 1))
        r = results[sid]
        vsegs.append({
            "index": i, "scene_id": sid,
            "parent_scene_id": s.get("parent_scene_id"),
            "text": s.get("narration") or "",
            "text_sha256": r["text_sha256"],
            "audio": "seg/{}.mp3".format(sid),
            "status": r["status"] if r["status"] != "REUSED" else "REUSED",
            "duration_s": r["duration_s"], "bytes": r["bytes"],
            "voice": VOICE, "provider": PROVIDER, "attempts": r["attempts"],
            "error_code": r["error_code"], "error_detail": r["error_detail"],
            "pause_budget_s": s.get("pause_budget_s"),
            "visual_hint": s.get("visual_hint"),
        })
        total += float(r["duration_s"] or 0)
    voice = {
        "schema": "voice-output-v1",
        "provider": PROVIDER, "voice": VOICE,
        "audio": "narration_v41.mp3",
        "script_source": "output/phase34_script_sandbox/script_p34_v42_40seg.json",
        "segments_total": len(segs),
        "segments": vsegs,
        "narration_duration_s": round(total, 3),
        "all_segments_ok": all(v["status"] in ("SUCCESS", "REUSED") for v in vsegs),
        # ---- P33-3：**pause 归因表**（v2.1 语义）----
        # 实测踩坑（两次）：
        #  ① 无归因表时 `narration_plan` 回落冻结常量 `PAUSE_BUDGET_S=0.75`
        #     ⇒ 时基 714.842s（音频仅 698.592s）⇒ 16.25s 幻影膨胀（#75.2 老病）；
        #  ② 带 0.384615/边界后，生产 `_build_material_timeline` 仍**未把边界 pause 计入窗口**
        #     （实测 Σ窗口 = Σactual + trailing = 687.592），而音频含 15.0s 边界静音
        #     ⇒ **成片比旁白短 11.07s**（尾部静音）。
        # ⇒ 权威口径定为：**逐段独立合成 ⇒ 段间不留额外静音**（pause=0），
        #    仅保留 trailing（由渲染链 apad 承担）。这样"音频事实"与"生产时间轴"完全一致。
        "pause_attribution": {
            "policy": "v2.1",
            "source": "P33-3：逐段独立合成；段间**不留额外静音**（pause=0，音频事实即时间轴事实）",
            "default_pause_s": 0.0,
            "derived_boundary_pause_s": 0.0,
            "boundaries": [{"after_index": i, "pause_s": 0.0, "kind": "derived",
                            "basis": "P33-3 新时基：无边界静音"}
                           for i in range(len(segs) - 1)],
        },
        "note": ("P33-3：v4.1 逐段配音（edge-tts 原音色）。**音频为事实来源**；"
                 "窗口/时基由本产物的实测时长派生（v2.1 语义：Σ实测 + pause 归因 + trailing）。"),
    }
    (OUT / "voice_output_v42.json").write_text(
        json.dumps(voice, ensure_ascii=False, indent=1), encoding="utf-8")
    print("Σ实测语音 = {:.3f}s".format(total))
    print("all_segments_ok =", voice["all_segments_ok"])
    print("-> " + str((OUT / "voice_output_v42.json").relative_to(R)))
    return 0 if voice["all_segments_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
