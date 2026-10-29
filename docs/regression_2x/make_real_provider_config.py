"""生成 Phase 3-A 的真实链路配置档：config.real.json + Wikimedia 素材 Provider。

原则：
  · **不改默认 `config/config.json`**（保持 `provider=none`），只新增一个派生档；
  · llm / hitl / retry / 其余 tools 段从 `config.real.json` **原样复制**（逐字不变）；
  · 只新增 `tools.material` 块（provider + 资源/许可策略）。

用法：python docs/regression_2x/make_real_provider_config.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(r"C:\mp4agent\video-studio")
SRC = ROOT / "config" / "config.real.json"
DST = ROOT / "config" / "config.real.provider.json"

if not SRC.is_file():
    print("缺少 config.real.json；先运行 make_real_config.py")
    sys.exit(1)

cfg = json.loads(SRC.read_text(encoding="utf-8"))
cfg["tools"]["material"] = {
    "provider": "wikimedia_commons",
    "search_limit": 8,
    "max_bytes": 8388608,
    "timeout_s": 25,
    "min_interval_s": 3.0,
    "rate_limit_retries": 3,
    "rate_limit_backoff_s": 10.0,
    "max_retries": 2,
    "max_concurrent_downloads": 2,
    "max_cache_bytes": 268435456,
    "allowed_ext": [".jpg", ".jpeg", ".png", ".webp"],
    "min_width": 320,
    "min_height": 180,
    "min_asset_width": 320,
    "min_asset_height": 180,
    "license_required": True,
    "require_https": True,
    "query_term_limit": 4,
    "query_max_chars": 100,
    "auth": {"mode": "none", "api_key_env": "WIKIMEDIA_API_TOKEN", "require_key": False},
}
DST.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
prov = cfg["tools"]["material"]["provider"]
print("written {} | provider={}".format(DST, prov))
diff = [k for k in cfg if k != "tools"]
print("llm/hitl/retry 段与 config.real.json 一致:",
      all(json.dumps(cfg[k], sort_keys=True) == json.dumps(
          json.loads(SRC.read_text(encoding='utf-8'))[k], sort_keys=True) for k in diff))
print("默认 config.json 未改动:",
      json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8"))
      ["tools"].get("material") is None)
