# -*- coding: utf-8 -*-
"""Phase 47 / P47-1 侦察：VLM 平台与 base_url；百炼文生图（wanx）可用性探测。"""
from __future__ import annotations

import json
import os
import pathlib
import re
import socket
import ssl
import sys
import urllib.request

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core.env import load_env                                      # noqa: E402

load_env(R / ".env")
for name in ("config/vlm.json", "config/vlm_judge.json", "config.json",
             "config/model.json"):
    fp = R / name
    if not fp.is_file():
        continue
    s = fp.read_text(encoding="utf-8")
    for pat, lbl in ((r'"base_url"\s*:\s*"([^"]+)"', "base_url"),
                     (r'"model"\s*:\s*"([^"]+)"', "model")):
        for m in sorted(set(re.findall(pat, s)))[:5]:
            print("{:<26} {:<9} {}".format(name, lbl, m))
print()
key = os.environ.get("VLM_API_KEY") or ""
print("VLM_API_KEY prefix:", key[:8], "len", len(key))
# 百炼（DashScope）文生图 endpoint 探测
# **踩坑**：header 里直接放含中文的 JSON 会触发 `UnicodeEncodeError: 'latin-1'` ——
# 必须 `encode("utf-8")` 后作为 data 传，并显式声明 charset。
DS = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis"
body = json.dumps({"model": "wanx2.1-t2i-turbo",
                   "input": {"prompt": "minimalist white chalk formula lines on dark blackboard"},
                   "parameters": {"size": "1024*1024", "n": 1}}).encode("utf-8")
req = urllib.request.Request(DS, data=body, headers={
    "Authorization": "Bearer " + key,
    "Content-Type": "application/json; charset=utf-8",
    "X-DashScope-Async": "enable"})
try:
    with urllib.request.urlopen(req, timeout=45) as r:
        j = json.loads(r.read().decode("utf-8"))
    print("wanx 提交响应:", json.dumps(j, ensure_ascii=False)[:300])
except Exception as exc:                                                        # noqa: BLE001
    print("wanx 探测失败:", type(exc).__name__, str(exc)[:220])
    try:
        print("  响应体:", exc.read().decode("utf-8", "ignore")[:300])          # type: ignore[attr-defined]
    except Exception:                                                           # noqa: BLE001
        pass
