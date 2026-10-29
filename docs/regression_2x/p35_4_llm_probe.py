# -*- coding: utf-8 -*-
"""P35-1：验证真实 LLM 连通性（**一次最小调用**，记录成本与 token）。"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import urllib.request

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core.env import load_env                                  # noqa: E402


def main() -> int:
    load_env(R / ".env")
    cfg = json.loads((R / "config/config.json").read_text(encoding="utf-8"))
    llm = cfg["llm"]
    key = os.environ.get(llm["deepseek"]["api_key_env"])
    print("provider:", llm["provider"], "| key present:", bool(key),
          "| base:", llm["deepseek"]["base_url"])
    body = json.dumps({
        "model": llm["tiers"]["F"]["model"],
        "messages": [{"role": "user", "content": "回复两个字：连通"}],
        "max_tokens": 16, "temperature": 0,
    }).encode("utf-8")
    req = urllib.request.Request(
        llm["deepseek"]["base_url"].rstrip("/") + "/chat/completions",
        data=body, method="POST",
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer {}".format(key)})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            j = json.loads(r.read().decode("utf-8"))
        msg = (j.get("choices") or [{}])[0].get("message", {}).get("content", "")
        u = j.get("usage") or {}
        print("回复:", msg.strip()[:60])
        print("usage:", json.dumps(u, ensure_ascii=False))
        pr = llm["pricing"][llm["tiers"]["F"]["model"]]["off_peak"]
        cost = (u.get("prompt_tokens", 0) * pr["cache_miss"]
                + u.get("completion_tokens", 0) * pr["output"]) / 1_000_000
        print("估算成本: ${:.6f}".format(cost))
        return 0
    except Exception as exc:                                                # noqa: BLE001
        print("LLM 调用失败:", type(exc).__name__, str(exc)[:200])
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
