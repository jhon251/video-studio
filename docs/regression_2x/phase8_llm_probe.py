# -*- coding: utf-8 -*-
"""Phase 8 只读探针：确认 deepseek-flash 响应中 content / reasoning 的实际情况（极小成本）。"""
import json
import os
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core.env import load_env                                          # noqa: E402
from video_studio.llm.router import DeepSeekClient, compute_cost                    # noqa: E402

load_env(str(R / ".env"))
cfg = json.loads((R / "config" / "config.json").read_text(encoding="utf-8"))
c = DeepSeekClient(cfg["llm"]["deepseek"])

# 探针 1：极小 prompt + max_tokens=64
r = c.complete("deepseek-flash", "你是测试。", "只回复 {\"ok\":true} 这一个 JSON。", 64)
usage = {k: r.get(k, 0) for k in ("prompt_tokens", "completion_tokens", "cache_hit_tokens",
                                  "cache_miss_tokens")}
print("探针1 keys:", sorted(r.keys()))
print("   text:", repr(r.get("text"))[:200])
print("   reasoning_tokens:", r.get("reasoning_tokens"), "| usage:", usage,
      "| cost:", compute_cost("deepseek-flash", usage))

# 探针 2：直接看原始 HTTP 响应体（仅打印 message 的键与截断预览）
import requests                                                                     # noqa: E402
body = {
    "model": "deepseek-flash",
    "messages": [{"role": "system", "content": "你是测试。"},
                 {"role": "user", "content": "只回复 {\"ok\":true} 这一个 JSON。"}],
    "max_tokens": 64, "temperature": 0.7,
}
resp = requests.post("https://api.deepseek.com/chat/completions",
                     headers={"Authorization": "Bearer " + c.api_key,
                              "Content-Type": "application/json"},
                     json=body, timeout=120)
j = resp.json()
msg = (j.get("choices") or [{}])[0].get("message") or {}
print("探针2 status:", resp.status_code, "| message keys:", sorted(msg.keys()))
print("   content:", repr(msg.get("content"))[:200])
print("   reasoning_content 长度:", len(msg.get("reasoning_content") or ""))
print("   finish_reason:", (j.get("choices") or [{}])[0].get("finish_reason"))
print("   usage:", json.dumps(j.get("usage"), ensure_ascii=False))
