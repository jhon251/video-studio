# -*- coding: utf-8 -*-
"""5-L 针对性回归：**离线 mock 能力与生产默认隔离** + M5d 测试契约（钉定当前有效基线）。

覆盖（授权 item 1/2/3/4）：
  L1 生产默认仍是真实 DeepSeek：`config/config.json` **不含** `llm.mock`，tiers 为当前官方模型
  L2 独立离线 mock 配置存在且只多出 `llm.mock`/`_offline`：其余键值与生产配置**逐字一致**
  L3 mock 配置**不是**默认：`cli.load_config(None)` 仍解析到 `config/config.json`
  L4 离线用例**显式**引用 mock 配置（源码级）：cost_accounting_test / pipeline_mock /
     run_ingest_test / run_all_tests（四个调用点，逐一断言）
  L5 生产路径**不**引用 mock 配置：`src/**` 与 `run.py` 中不出现 `config.mock.json`
  L6 mock 的 llm 语义与生产一致：tiers / pricing / provider 三键逐字一致（只有 mock 段是增量）
  L7 M5d 契约：`tests/metrics_test.py` 钉定 `5.x-post-final-maintenance-baseline`，
     且该 manifest 中 `config/config.json` 的 sha256 == 磁盘现值（契约可满足）
  L8 真实链路用例未被改成 mock：`real_small_test.py` / `phase2_accept.py` / `phase3a_real_chain.py`
     仍使用 `config/config.real*.json`（**真实** LLM/网络，非 mock）
  L9 旧基线未被改写：`5.x-final-baseline.zip` sha256 仍为授权值

用法: python tests/offline_mock_test.py
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name, "" if ok else "| " + str(detail)[:400]))


def rd(p):
    return (ROOT / p).read_text(encoding="utf-8")


PROD = json.loads(rd("config/config.json"))
MOCK_P = ROOT / "config" / "config.mock.json"
MOCK = json.loads(MOCK_P.read_text(encoding="utf-8")) if MOCK_P.is_file() else {}
NEW_TAG = "5.x-post-final-maintenance-baseline"
FINAL_TAG = "5.x-final-baseline"
FINAL_SHA = "be1717b9c7fe9ed9124be3876db64b5893915a4d0ffad56bd37eded5e6e2141e"

# ---------------- L1 生产默认 = 真实 DeepSeek，且无 mock ----------------
tiers = {k: v.get("model") for k, v in (PROD.get("llm", {}).get("tiers") or {}).items()}
check("L1a 生产默认 config/config.json **不含** llm.mock（禁止 mock 成为生产默认）",
      "mock" not in (PROD.get("llm") or {}), sorted((PROD.get("llm") or {}).keys()))
check("L1b 生产默认 tiers = 当前官方模型（M/F=deepseek-flash、R=deepseek-v4-pro）",
      tiers.get("M") == "deepseek-flash" and tiers.get("F") == "deepseek-flash"
      and tiers.get("R") == "deepseek-v4-pro", tiers)
check("L1c 生产默认 provider 仍为 deepseek 且无内联 mock 响应",
      (PROD.get("llm") or {}).get("provider") == "deepseek"
      and "responses" not in json.dumps(PROD.get("llm", {}), ensure_ascii=False),
      (PROD.get("llm") or {}).get("provider"))

# ---------------- L2 mock 配置 = 生产配置 + llm.mock ----------------
check("L2a 独立离线 mock 配置存在：config/config.mock.json", MOCK_P.is_file(),
      "bytes={}".format(MOCK_P.stat().st_size if MOCK_P.is_file() else 0))
check("L2b mock 配置含 llm.mock.responses（≥10 个角色）与 default",
      len(((MOCK.get("llm") or {}).get("mock") or {}).get("responses") or {}) >= 10
      and isinstance(((MOCK.get("llm") or {}).get("mock") or {}).get("default"), dict),
      sorted((((MOCK.get("llm") or {}).get("mock") or {}).get("responses") or {}).keys())[:6])
_m = json.loads(json.dumps(MOCK))
_m.pop("_offline", None)
(_m.get("llm") or {}).pop("mock", None)
_p = json.loads(json.dumps(PROD))
check("L2c 除 llm.mock/_offline 外，mock 配置与生产配置**逐字一致**（模型/价格/HITL/tools 语义不变）",
      json.dumps(_m, ensure_ascii=False, sort_keys=True)
      == json.dumps(_p, ensure_ascii=False, sort_keys=True),
      [k for k in set(list(_m) + list(_p)) if _m.get(k) != _p.get(k)])
check("L2d mock 配置自述用途与来源（_offline.purpose / mock_source / mock_source_zip_sha256）",
      "offline" in str((MOCK.get("_offline") or {}).get("purpose", ""))
      and "5.x-final-baseline" in str((MOCK.get("_offline") or {}).get("mock_source", ""))
      and (MOCK.get("_offline") or {}).get("mock_source_zip_sha256") == FINAL_SHA,
      MOCK.get("_offline"))

# ---------------- L3 mock 不是默认 ----------------
import video_studio.cli as cli  # noqa: E402
default_cfg = cli.load_config(None)
check("L3a `cli.load_config(None)` 解析到的仍是**生产**配置（无 llm.mock）",
      "mock" not in (default_cfg.get("llm") or {})
      and hashlib.sha256(json.dumps(default_cfg, sort_keys=True).encode()).hexdigest()
      == hashlib.sha256(json.dumps(PROD, sort_keys=True).encode()).hexdigest(),
      sorted((default_cfg.get("llm") or {}).keys()))
src = rd("src/video_studio/cli.py")
check("L3b cli 默认配置路径仍是 config/config.json（未被改成 mock）",
      re.search(r'ROOT\s*/\s*"config"\s*/\s*"config\.json"', src) is not None
      and '"config.mock.json"' not in src, None)

# ---------------- L4 离线用例显式引用 mock ----------------
offline_sites = {
    "tests/cost_accounting_test.py": 'config" / "config.mock.json',
    "tests/pipeline_mock.py": 'config" / "config.mock.json',
    "docs/regression_2x/run_ingest_test.py": 'config/config.mock.json',
    "docs/regression_2x/run_all_tests.py": 'config/config.mock.json',
}
for rel, needle in offline_sites.items():
    body = rd(rel)
    check("L4 离线用例显式使用 mock：{}".format(rel), needle in body,
          [l.strip()[:100] for l in body.splitlines() if "config" in l and "mock" in l][:2])

# ---------------- L5 生产路径不引用 mock ----------------
prod_hits = []
for p in list((ROOT / "src").rglob("*.py")) + [ROOT / "run.py"]:
    if "config.mock.json" in p.read_text(encoding="utf-8", errors="replace"):
        prod_hits.append(p.relative_to(ROOT).as_posix())
check("L5 生产代码（src/**、run.py）**不**引用 config.mock.json（mock 不外溢到生产路径）",
      not prod_hits, prod_hits)

# ---------------- L6 mock 的 llm 语义与生产一致 ----------------
lm, lp = (MOCK.get("llm") or {}), (PROD.get("llm") or {})
check("L6 mock 配置的 tiers/pricing/provider 与生产**逐字一致**（mock 不改变模型与计价语义）",
      lm.get("tiers") == lp.get("tiers") and lm.get("pricing") == lp.get("pricing")
      and lm.get("provider") == lp.get("provider"),
      {"tiers_same": lm.get("tiers") == lp.get("tiers"),
       "pricing_same": lm.get("pricing") == lp.get("pricing")})

# ---------------- L7 M5d 契约（钉定当前有效基线） ----------------
mt = rd("tests/metrics_test.py")
man_p = ROOT / "docs" / "regression_2x" / "baseline" / \
    "baseline_manifest_{}.json".format(NEW_TAG)
man = json.loads(man_p.read_text(encoding="utf-8"))
cfg_now = hashlib.sha256((ROOT / "config" / "config.json").read_bytes()).hexdigest()
check("L7a M5d 已改钉当前有效基线 tag（不再钉 3.x-final）",
      "baseline_manifest_{}.json".format(NEW_TAG) in mt
      and "baseline_manifest_3.x-final-baseline.json" not in mt, None)
check("L7b M5d 契约可满足：manifest 中 config/config.json sha256 == 磁盘现值",
      man["files"]["config/config.json"]["sha256"] == cfg_now,
      "{} vs {}".format(cfg_now[:12], man["files"]["config/config.json"]["sha256"][:12]))
check("L7c M5d 断言强度未变（仍是逐字节 sha256 相等）+ 注明为测试契约更新",
      'cfg_now == (baseline["files"]["config/config.json"]["sha256"])' in mt
      and "测试契约更新" in mt, None)
check("L7d 4-A 证据脚本同步改钉当前有效基线（phase4ab_evidence.py）",
      "baseline_manifest_{}.json".format(NEW_TAG) in rd("docs/regression_2x/phase4ab_evidence.py"),
      None)

# ---------------- L8 真实链路用例仍走真实配置 ----------------
real_sites = {"docs/regression_2x/real_small_test.py": "config/config.real.json",
              "docs/regression_2x/phase2_accept.py": "config/config.real.json",
              "docs/regression_2x/phase3a_real_chain.py": "config/config.real.provider.json"}
for rel, needle in real_sites.items():
    body = rd(rel)
    check("L8 真实链路用例仍用真实配置（未被改成 mock）：{}".format(rel),
          needle in body and "config.mock.json" not in body, None)

# ---------------- L9 旧基线未被改写 ----------------
fz = ROOT / "docs" / "regression_2x" / "baseline" / "{}.zip".format(FINAL_TAG)
check("L9 旧 `5.x-final-baseline.zip` sha256 仍为授权值（未被修改/覆盖）",
      hashlib.sha256(fz.read_bytes()).hexdigest() == FINAL_SHA,
      hashlib.sha256(fz.read_bytes()).hexdigest()[:16])

print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print("失败项:", FAIL)
sys.exit(0 if not FAIL else 1)
