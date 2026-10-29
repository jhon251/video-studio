# -*- coding: utf-8 -*-
"""P33-3 前置：edge-tts 连通性与**时长测量口径**验证（单段试合成）。

只发 1 次 TTS 请求；验证：
  · 指定音色（`zh-CN-XiaoxiaoNeural`，与原片一致）可合成中文；
  · 产物可被 ffprobe 量出时长（新时基的唯一权威来源）。
"""
from __future__ import annotations

import pathlib
import subprocess
import sys
import time

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
OUT = R / "output" / "p33_probe"
OUT.mkdir(parents=True, exist_ok=True)
FFPROBE = R / "bin" / "ffprobe.exe"
VOICE = "zh-CN-XiaoxiaoNeural"
TEXT = "1977 年，Appel 和 Haken 宣布四色定理被证出来了，数学界那会儿的第一反应不是鼓掌。"


def dur(p):
    r = subprocess.run([str(FFPROBE), "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(p)], capture_output=True, text=True)
    return float(r.stdout.strip().splitlines()[0]) if r.stdout.strip() else None


def main() -> int:
    import asyncio
    import socket

    import aiohttp
    import edge_tts

    async def synth(text, mp3):
        # 本机可解析 AAAA 但无 IPv6 出口 ⇒ 默认双栈会先失败。
        # edge-tts 7.x 允许注入 connector ⇒ 强制 **IPv4**。
        conn = aiohttp.TCPConnector(family=socket.AF_INET, ttl_dns_cache=300)
        c = edge_tts.Communicate(text, VOICE, connector=conn)
        try:
            await c.save(str(mp3))
        finally:
            await conn.close()

    mp3 = OUT / "edge_probe.mp3"
    t0 = time.time()
    asyncio.run(synth(TEXT, mp3))
    dt = time.time() - t0
    print("合成耗时 {:.1f}s | bytes {:,} | 存在 {}".format(
        dt, mp3.stat().st_size, mp3.is_file()))
    d = dur(mp3)
    print("ffprobe 时长 = {:.3f}s".format(d or 0))
    print("字符数 = {} | 语速 ≈ {:.2f} 字/秒".format(len(TEXT), len(TEXT) / (d or 1)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
