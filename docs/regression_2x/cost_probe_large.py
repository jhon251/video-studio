"""Phase 1.1 large controlled measurement (raw balance JSON + ~0.7 CNY single call).

Purpose: separate three hypotheses with a signal well above the balance noise seen so far
(observed unexplained 0.35 CNY drift between readings with no matching API call):
  A) price table wrong (real price >> table)
  B) balance display lagging/coarse
  C) the same API key is used by other consumers (usage not from this project)
"""
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
HDR = {"Authorization": "Bearer " + KEY, "Content-Type": "application/json"}


def balance_raw():
    req = urllib.request.Request("https://api.deepseek.com/user/balance", headers=HDR)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def bal():
    d = balance_raw()
    return float(d["balance_infos"][0]["total_balance"]), d


print("=== 调用前 ===")
b0, raw0 = bal()
print("raw:", json.dumps(raw0, ensure_ascii=False))

para = ("黑洞是时空曲率极大的区域，事件视界是因果边界；史瓦西半径与质量成正比，"
        "太阳的史瓦西半径约三公里。霍金辐射使黑洞缓慢蒸发，温度与质量成反比。")
prompt = para * 1800            # ~ 180k 汉字 → 预计 ~120k+ tokens
body = json.dumps({"model": "deepseek-v4-pro",
                   "messages": [{"role": "user", "content": prompt}],
                   "max_tokens": 256}).encode()
print("\nprompt 字符数:", len(prompt))
t0 = time.perf_counter()
req = urllib.request.Request("https://api.deepseek.com/chat/completions", data=body, headers=HDR)
with urllib.request.urlopen(req, timeout=600) as r:
    d = json.loads(r.read().decode())
lat = (time.perf_counter() - t0) * 1000
u = d.get("usage", {})
print("延迟 {:.0f}ms | usage: {}".format(lat, json.dumps(u, ensure_ascii=False)))

pin = int(u.get("prompt_tokens") or 0)
hit = int(u.get("prompt_cache_hit_tokens") or 0)
miss = int(u.get("prompt_cache_miss_tokens") or pin)
out = int(u.get("completion_tokens") or 0)
expect = (miss * 4.5 + hit * 0.15 + out * 13.5) / 1e6     # v4-pro 空闲（CNY/1M）
print("按官方中文价目表（v4-pro 空闲）应为: {:.4f} 元".format(expect))

print("\n=== 立即读取余额 ===")
b1, raw1 = bal()
print("raw:", json.dumps(raw1, ensure_ascii=False))
print("立即差额: {:.4f} 元".format(b0 - b1))

print("\n=== 等待 20s 后再读（排除结算延迟）===")
time.sleep(20)
b2, raw2 = bal()
print("raw:", json.dumps(raw2, ensure_ascii=False))
print("20s 后差额: {:.4f} 元".format(b0 - b2))
if expect > 0:
    print("实测/理论（20s 口径）= {:.2f}x".format((b0 - b2) / expect))
