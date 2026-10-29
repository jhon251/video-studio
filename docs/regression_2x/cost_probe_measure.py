"""Phase 1.1 controlled cost measurement: measure the provider's ACTUAL CNY deduction for a
known-size call, then compare with the local cost table.

Why: the ledger (USD, computed from the official price table) says $0.1517, while the account
balance dropped ~3.60 CNY. This script measures the real per-token price empirically.

Cost of this probe: ~0.1 CNY (bounded, single call, max_tokens=256).
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
os.environ["DEEPSEEK_API_KEY"] = KEY
HDR = {"Authorization": "Bearer " + KEY, "Content-Type": "application/json"}


def balance():
    req = urllib.request.Request("https://api.deepseek.com/user/balance", headers=HDR)
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.loads(r.read().decode())
    b = d["balance_infos"][0]
    return float(b["total_balance"]), b["currency"]


def chat(model, prompt, max_tokens):
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}],
                       "max_tokens": max_tokens}).encode()
    req = urllib.request.Request("https://api.deepseek.com/chat/completions", data=body, headers=HDR)
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=300) as r:
        d = json.loads(r.read().decode())
    return d, (time.perf_counter() - t0) * 1000


para = ("黑洞是时空曲率极大的区域，事件视界是因果边界。史瓦西半径与质量成正比，"
        "太阳的史瓦西半径约为三公里。霍金辐射使黑洞缓慢蒸发，温度与质量成反比。"
        "引力波探测为恒星级黑洞并合提供了直接证据。无毛定理指出外部只可观测质量与自转。")
prompt = para * 900          # 约 4.5 万汉字 → 数量级 ~45k tokens
print("prompt 字符数:", len(prompt))

b0, cur = balance()
print("调用前余额: {} {}".format(b0, cur))
d, lat = chat("deepseek-flash", prompt, 256)
u = d.get("usage", {})
print("延迟 {:.0f}ms | usage: {}".format(lat, json.dumps(u, ensure_ascii=False)))
b1, _ = balance()
print("调用后余额: {} {}".format(b1, cur))

delta = round(b0 - b1, 4)
pin = int(u.get("prompt_tokens") or 0)
cin = int(u.get("prompt_cache_hit_tokens") or 0)
min_ = int(u.get("prompt_cache_miss_tokens") or pin)
out = int(u.get("completion_tokens") or 0)
print("\n余额变化: {:.4f} {}".format(delta, cur))
print("tokens: prompt={} (hit={} miss={}) completion={}".format(pin, cin, min_, out))

# 官方中文价（空闲时段, CNY/1M）：flash 输入 miss 1 元, 输出 4 元; 缓存命中 0.02 元
expect = (min_ * 1.0 + cin * 0.02 + out * 4.0) / 1e6
print("按官方中文价目表（空闲）应为: {:.4f} 元".format(expect))
if delta > 0:
    print("实测/理论 = {:.2f}x".format(delta / expect if expect else float("nan")))
else:
    print("余额未变化（精度 0.01 元）→ 本次测量量级不足，需更大调用")
print("\n本次实测同时给出：真实单价 ≈ {:.4f} 元/千输入token（含输出分摊）".format(
    (delta * 1000 / max(1, pin + out)) if delta > 0 else float("nan")))
