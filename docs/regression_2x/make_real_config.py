"""Generate config/config.real.json from config/config.json (mock removed) + real-run LLM settings.

Deriving programmatically guarantees every non-LLM section (tools/hitl/retry/workspace) stays identical
to the frozen baseline config, and keeps the mock config untouched for the free mechanical regression.

Usage: python docs/regression_2x/make_real_config.py
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
src = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8"))
assert "mock" in src.get("llm", {}), "config.json 无 mock 段，行为与预期不符"

real = json.loads(json.dumps(src))
real["llm"].pop("mock", None)          # 关闭 MockLLM：缺 mock 键 → build_engine 走 DeepSeekClient
real["llm"]["deepseek"] = {
    "api_key_env": "DEEPSEEK_API_KEY",
    "base_url": "https://api.deepseek.com",
    "timeout_s": 120,
    "max_retries": 2,                  # 429/5xx/超时/连接失败重试 2 次（退避 5s,10s）
    "backoff_base_s": 5,
}
# 使用官方文档中的现行模型名（/models 只返回这两个），以便按公开价目表精算费用
real["llm"]["tiers"] = {
    "R": {"model": "deepseek-v4-pro", "max_tokens": 8192},
    # M 档提到 16384：实测 script 任务在 8192 上限处被截断成非法 JSON（Phase 1 真实运行证据）
    "M": {"model": "deepseek-flash", "max_tokens": 16384},
    "F": {"model": "deepseek-flash", "max_tokens": 2048},
}
real["llm"]["pricing"] = {
    "deepseek-flash": {"peak": {"cache_hit": 0.006, "cache_miss": 0.30, "output": 1.20},
                       "off_peak": {"cache_hit": 0.003, "cache_miss": 0.15, "output": 0.60}},
    "deepseek-v4-pro": {"peak": {"cache_hit": 0.044, "cache_miss": 1.32, "output": 3.96},
                        "off_peak": {"cache_hit": 0.022, "cache_miss": 0.66, "output": 1.98}},
}
real["llm"]["max_total_usd"] = 0.60    # 运行级预算闸门：超出即 LLM_BUDGET_EXCEEDED，不再发请求
out = ROOT / "config" / "config.real.json"
out.write_text(json.dumps(real, ensure_ascii=False, indent=2), encoding="utf-8")
print("written:", out)
print("llm:", json.dumps(real["llm"], ensure_ascii=False)[:400])
print("tools unchanged:", real["tools"] == src["tools"])
print("hitl/retry unchanged:", real["hitl"] == src["hitl"], real["retry"] == src["retry"])
