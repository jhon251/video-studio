"""Minimal real-API probe: does the configured model name still work?

Three single-shot calls (max_tokens=8), no retries. Records status, error body, usage, latency.
Cost of this probe is negligible (a few tokens).

Usage: python docs/regression_2x/probe_llm.py
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")


def load_env():
    p = ROOT / ".env"
    if not p.exists():
        return
    for ln in p.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#") or "=" not in ln:
            continue
        k, v = ln.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_env()
key = os.environ.get("DEEPSEEK_API_KEY", "")
cfg = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8"))["llm"]
base = cfg.get("deepseek", {}).get("base_url", "https://api.deepseek.com").rstrip("/")
print("base_url:", base)
print("api_key:", "present({} chars)".format(len(key)) if key else "MISSING")
print("config tiers:", json.dumps(cfg.get("tiers"), ensure_ascii=False))
print()

models = ["deepseek-chat", "deepseek-reasoner", "deepseek-flash"]
results = []
for m in models:
    body = json.dumps({"model": m,
                       "messages": [{"role": "user", "content": "ping"}],
                       "max_tokens": 8, "temperature": 0}).encode()
    req = urllib.request.Request(base + "/chat/completions", data=body,
                                 headers={"Authorization": "Bearer " + key,
                                          "Content-Type": "application/json"})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            payload = json.loads(r.read().decode("utf-8"))
            el = (time.perf_counter() - t0) * 1000
            usage = payload.get("usage", {})
            txt = (payload.get("choices") or [{}])[0].get("message", {}).get("content", "")
            rec = {"model": m, "http": r.status, "ok": True, "latency_ms": round(el),
                   "usage": usage, "reply": str(txt)[:40]}
    except urllib.error.HTTPError as e:
        el = (time.perf_counter() - t0) * 1000
        detail = e.read().decode("utf-8", "replace")[:300]
        rec = {"model": m, "http": e.code, "ok": False, "latency_ms": round(el), "error": detail}
    except Exception as e:  # noqa: BLE001
        el = (time.perf_counter() - t0) * 1000
        rec = {"model": m, "http": None, "ok": False, "latency_ms": round(el),
               "error": "{}: {}".format(type(e).__name__, str(e)[:200])}
    results.append(rec)
    print(json.dumps(rec, ensure_ascii=False))

(ROOT / "docs" / "regression_2x" / "logs" / "llm_probe.json").write_text(
    json.dumps({"base_url": base, "key_present": bool(key), "results": results},
               ensure_ascii=False, indent=1), encoding="utf-8")
print("\nprobe saved -> docs/regression_2x/logs/llm_probe.json")
