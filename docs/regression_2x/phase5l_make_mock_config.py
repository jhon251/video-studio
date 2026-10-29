# -*- coding: utf-8 -*-
"""5-L：生成**独立离线 mock 配置** `config/config.mock.json`（生产默认仍是 `config/config.json`）。

规则（授权 item 1/2/3）：
  · `config/config.json` = **生产默认**，继续使用真实 DeepSeek（本脚本**不修改它**）；
  · `config/config.mock.json` = 生产配置的**逐字副本 + 仅追加 `llm.mock`**，供离线回归**显式**指定使用；
  · `llm.mock`（responses/default）来源 = 冻结基线 `5.x-final-baseline.zip` 内的 `config/config.json`
    （只读提取，可复算：脚本会打印该 ZIP 的 sha256 与提取内容的 sha256）。

用法: python docs/regression_2x/phase5l_make_mock_config.py [--check]
产出: config/config.mock.json（`--check` 只校验不写）
"""
import hashlib
import json
import sys
import zipfile
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
PROD = ROOT / "config" / "config.json"
MOCK = ROOT / "config" / "config.mock.json"
BASE_ZIP = ROOT / "docs" / "regression_2x" / "baseline" / "5.x-final-baseline.zip"
CHECK_ONLY = "--check" in sys.argv


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha_file(p: Path) -> str:
    return sha_bytes(p.read_bytes())


prod_raw = PROD.read_bytes()
prod = json.loads(prod_raw.decode("utf-8-sig"))
with zipfile.ZipFile(BASE_ZIP) as z:
    base_raw = z.read("config/config.json")
base = json.loads(base_raw.decode("utf-8-sig"))
mock_section = base["llm"]["mock"]
mock_bytes_sha = sha_bytes(json.dumps(mock_section, ensure_ascii=False, sort_keys=True)
                           .encode("utf-8"))

# 生产配置**不得**含 mock（item 3 守卫；若含则本脚本拒写）
if prod.get("llm", {}).get("mock"):
    print("REFUSE: 生产配置 config/config.json 含 llm.mock —— 违反 item 3（禁止把 mock 作为生产默认）")
    sys.exit(2)

out = json.loads(json.dumps(prod))  # deep copy
out["llm"]["mock"] = mock_section
out["_offline"] = {
    "purpose": "offline mock config for regression tests only; NOT the production default",
    "production_default": "config/config.json",
    "mock_source": "docs/regression_2x/baseline/5.x-final-baseline.zip:config/config.json#llm.mock",
    "mock_source_zip_sha256": sha_file(BASE_ZIP),
    "mock_section_sha256": mock_bytes_sha,
    "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "invariant": "除 llm.mock 与 _offline 外，其余键值与 config/config.json 完全一致（模型/价格/HITL/tools 语义不变）",
}

# 不变式校验：除 mock/_offline 外逐键一致
a = {k: v for k, v in out.items() if k not in ("_offline",)}
a["llm"] = {k: v for k, v in out["llm"].items() if k != "mock"}
b = json.loads(json.dumps(prod))
same = json.dumps(a, ensure_ascii=False, sort_keys=True) == json.dumps(b, ensure_ascii=False,
                                                                       sort_keys=True)

payload = json.dumps(out, ensure_ascii=False, indent=1) + "\n"
print("生产默认 config/config.json sha256 :", sha_file(PROD)[:32], "(不含 llm.mock ✓)")
print("mock 来源 ZIP sha256              :", sha_file(BASE_ZIP)[:32])
print("llm.mock 段 sha256                :", mock_bytes_sha[:32])
print("mock responses 角色数             :", len(mock_section.get("responses", {})),
      "| default 键:", sorted((mock_section.get("default") or {}).keys())[:6])
print("除 mock/_offline 外与生产配置一致 :", same)
if CHECK_ONLY:
    ok = MOCK.is_file() and MOCK.read_text(encoding="utf-8") == payload
    print("CHECK: 现有 config.mock.json 与期望内容一致 =", ok)
    sys.exit(0 if same else 1)
MOCK.write_text(payload, encoding="utf-8")
print("written:", MOCK, "bytes:", len(payload.encode("utf-8")))
print("mock config sha256:", sha_file(MOCK)[:32])
