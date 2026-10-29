"""Phase 1.1: observe balance settlement trajectory (no API cost; read-only polling)."""
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
KEY = ""
for ln in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if ln.strip().startswith("DEEPSEEK_API_KEY="):
        KEY = ln.split("=", 1)[1].strip()
HDR = {"Authorization": "Bearer " + KEY}

print("t(s)  balance(CNY)")
prev = None
for i in range(19):                      # ~3 分钟，每 10s 一次
    req = urllib.request.Request("https://api.deepseek.com/user/balance", headers=HDR)
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.loads(r.read().decode())
    b = d["balance_infos"][0]["total_balance"]
    mark = "" if prev is None or b == prev else "  <- changed {:.2f}".format(float(prev) - float(b))
    print("{:4d}  {}{}".format(i * 10, b, mark), flush=True)
    prev = b
    time.sleep(10)
