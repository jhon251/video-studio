"""4.x Phase 4-D 单测：供给韧性底座（**全离线、确定性、不访问网络**）。

覆盖（授权要求的路径 + fail-closed + 不污染）：
  A. 失败分类表：既有全部错误码均被登记；未知码保守处理（UNKNOWN、不重试、不放行）
  B. 重试计划：与 2-D/2-E 逐值一致（429 线性 10/20/30、其它 0.2 线性且 ≤2.0、预算耗尽即停、
     Retry-After 只在 30s 上限内被采纳、许可类错误绝不重试）
  C. 供给缓存：默认关闭；命中/过期/损坏/schema 不符/策略指纹变化；**只缓存元数据**，
     恢复出的候选一律回到"未下载/未校验/未清权"
  D. 八条供给路径：正常 / 缓存命中 / 429 / 超时 / 空候选 / 下载失败 / 校验失败 / 许可不明
  E. 可控降级阶梯：5 档 + 三条不变量（不静默、不用未验证素材、不绕许可）
  F. 引擎级 fail-closed 与不污染：失败不产出 render_output/attribution、无成片、
     既有项目产物/台账/版本链不变、真实 `projects/video_studio.db` 字节不变
  G. 默认配置不变：`supply_cache=False`；`provider=none` 仍是默认且不产生外部请求

用法：python tests/supply_resilience_test.py
"""
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core.supply import (FAILURE_CLASSES, SUPPLY_LADDER, SUPPLY_SCHEMA,  # noqa: E402
                                      SupplyCache, cache_key, classify_failure,
                                      degradation_plan, policy_fingerprint, retry_decision,
                                      summarize, taxonomy_table)
from video_studio.tools.base import ToolContext  # noqa: E402
from video_studio.tools.material_provider import (ASSET_ERRORS, DEFAULT_POLICY,  # noqa: E402
                                                 PROVIDER_ERRORS, LocalCatalogProvider,
                                                 MaterialQuery, TransportError,
                                                 provider_from_config)
from video_studio.tools.supply import (ResilientSupply, candidate_from_metadata,  # noqa: E402
                                       candidate_metadata)

FFMPEG = ROOT / "bin" / "ffmpeg.exe"
FFPROBE = ROOT / "bin" / "ffprobe.exe"
REAL_JPG = ROOT / "output" / "run03" / "asset_cache" / "files" / "r3_S01-B01_3.img.jpg"
REAL_DB = ROOT / "projects" / "video_studio.db"
PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(("PASS  " if ok else "FAIL  ") + name + (" | " + str(detail)[:220] if detail else ""))


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


WORK = Path(tempfile.mkdtemp(prefix="vs_4d_supply_"))
MEDIA = WORK / "media"
CAT = WORK / "catalog"
MEDIA.mkdir(parents=True, exist_ok=True)
CAT.mkdir(parents=True, exist_ok=True)
NAME = "virtual reality headset demo.jpg"
GOOD = WORK / "good.jpg"
shutil.copy2(REAL_JPG, GOOD)
BAD_TRUNC = WORK / "truncated.jpg"
BAD_TRUNC.write_bytes(REAL_JPG.read_bytes()[:2048])          # 去掉 JPEG EOI → ASSET_TRUNCATED
FAKE_MEDIA = WORK / "fake.jpg"
FAKE_MEDIA.write_text("这不是图片，只是文本", encoding="utf-8")   # magic bytes 不符
LICENSE_OK = "CC BY-SA 4.0"
TEXT = "virtual reality headset device form factor"


def cfg():
    return {"tools": {"ffmpeg": {"path": str(FFMPEG), "ffprobe": str(FFPROBE)}}}


def make_ctx(project_dir=WORK):
    return ToolContext(role="retrieval", project_id="p_4d", project_dir=project_dir,
                       db=None, config=cfg())


def kw_query(text=TEXT):
    from video_studio.agents.retrieval.agent import kw_tokens
    return MaterialQuery(text=text, keywords=kw_tokens(text))


def write_catalog(items, name="catalogue.json"):
    (CAT / name).write_text(json.dumps({"items": items}, ensure_ascii=False), encoding="utf-8")


def item(path: Path, source_id="src_good", license=LICENSE_OK, name=NAME, **extra):
    rec = {"source_id": source_id, "name": name, "file": str(path), "license": license,
           "attribution": "Test Author / CC BY-SA 4.0"}
    rec.update(extra)
    return rec


def item_url(url, source_id="src_http", license=LICENSE_OK, name=NAME, **extra):
    rec = {"source_id": source_id, "name": name, "url": url, "license": license,
           "attribution": "Test Author / CC BY-SA 4.0"}
    rec.update(extra)
    return rec


def make_provider(items=None, policy=None, transport=None):
    write_catalog(items if items is not None else [item(GOOD)])
    pol = {**DEFAULT_POLICY, "provider": "local_catalog", "catalog": str(CAT),
           "timeout_s": 5, "max_retries": 2, "rate_limit_backoff_s": 0.0, "backoff_base_s": 0.0,
           **(policy or {})}
    return LocalCatalogProvider(pol, transport=transport, catalog_dir=CAT)


class CountingCatalog(LocalCatalogProvider):
    """记录 search 调用次数；可选在 search 阶段抛指定错误（模拟 429/超时/搜索失败）。"""

    def __init__(self, *a, search_error=None, **kw):
        super().__init__(*a, **kw)
        self.search_calls = 0
        self.search_error = search_error

    def search(self, query, ctx):
        self.search_calls += 1
        if self.search_error:
            raise TransportError(*self.search_error)
        return super().search(query, ctx)


class CountingTransport:
    """固定错误传输层（离线）：记录调用次数，可携带 Retry-After。"""

    def __init__(self, code="PROVIDER_TIMEOUT", retry_after_s=None):
        self.code, self.retry_after_s = code, retry_after_s
        self.calls = 0

    def get(self, url, max_bytes, timeout_s):
        self.calls += 1
        raise TransportError(self.code, "注入失败：{}".format(self.code),
                             retry_after_s=self.retry_after_s)


# ============ A. 失败分类表 ============
print("== A. 失败分类（限流/超时/永久/策略/许可）==")
table = {r["code"]: r for r in taxonomy_table()}
missing = [c for c in (PROVIDER_ERRORS + ASSET_ERRORS) if c not in table]
check("A1 既有全部错误码均已登记（PROVIDER_* + ASSET_*）", not missing, missing)
check("A2 分类取值均在允许集合内", all(r["class"] in FAILURE_CLASSES for r in table.values()),
      sorted({r["class"] for r in table.values()}))
check("A3 429 → TRANSIENT 且可重试",
      classify_failure("PROVIDER_RATE_LIMITED")["class"] == "TRANSIENT"
      and classify_failure("PROVIDER_RATE_LIMITED")["retryable"])
check("A4 超时 → TRANSIENT；404/鉴权 → PERMANENT",
      classify_failure("PROVIDER_TIMEOUT")["class"] == "TRANSIENT"
      and classify_failure("PROVIDER_HTTP_404")["class"] == "PERMANENT"
      and classify_failure("PROVIDER_AUTH_FAILED")["class"] == "PERMANENT")
check("A5 本地资源/预算/未配置 → POLICY（不重试）",
      all(classify_failure(c)["class"] == "POLICY" and not classify_failure(c)["retryable"]
          for c in ("PROVIDER_CACHE_LIMIT", "PROVIDER_REQUEST_BUDGET",
                    "PROVIDER_NOT_CONFIGURED", "PROVIDER_UNKNOWN")))
check("A6 许可缺失/不明/受限 → LICENSE 且不可重试",
      all(classify_failure(c)["class"] == "LICENSE" and not classify_failure(c)["retryable"]
          for c in ("ASSET_LICENSE_MISSING", "ASSET_LICENSE_UNCLEAR", "ASSET_LICENSE_RESTRICTED")))
unreg = classify_failure("SOMETHING_NEW")
check("A7 未登记错误码 → UNKNOWN（不重试、不放行、如实记录）",
      unreg["class"] == "UNKNOWN" and not unreg["retryable"] and not unreg["registered"], unreg)

# ============ B. 重试计划 ============
print("== B. 重试计划（有界、确定性、与 2-D/2-E 逐值一致）==")
pol_legacy = {"max_retries": 2, "rate_limit_retries": 3, "rate_limit_backoff_s": 10.0,
              "backoff_base_s": 0.2, "max_backoff_s": 30.0, "retry_after_max_s": 30.0}
rl = [retry_decision("PROVIDER_RATE_LIMITED", i, pol_legacy) for i in range(4)]
check("B1 429 线性退避 10/20/30，预算 3 次后停止",
      [r["sleep_s"] for r in rl[:3]] == [10.0, 20.0, 30.0] and rl[3]["retry"] is False,
      [r["sleep_s"] for r in rl])
to = [retry_decision("PROVIDER_TIMEOUT", i, pol_legacy) for i in range(3)]
check("B2 超时 0.2 线性退避、上限 2.0、预算 2 次后停止",
      [r["sleep_s"] for r in to[:2]] == [0.2, 0.4] and to[2]["retry"] is False,
      [r["sleep_s"] for r in to])
check("B3 非可重试类别（404/许可/策略）一律不重试",
      all(not retry_decision(c, 0, pol_legacy)["retry"] for c in
          ("PROVIDER_HTTP_404", "ASSET_LICENSE_UNCLEAR", "PROVIDER_REQUEST_BUDGET",
           "ASSET_TRUNCATED")))
capped = retry_decision("PROVIDER_RATE_LIMITED", 0, pol_legacy, retry_after_s=45)
smaller = retry_decision("PROVIDER_RATE_LIMITED", 0, pol_legacy, retry_after_s=5)
check("B4 Retry-After 只在 30s 上限内被采纳（45→30；5 不覆盖本地 10）",
      capped["sleep_s"] == 30.0 and smaller["sleep_s"] == 10.0,
      {"capped": capped["sleep_s"], "smaller": smaller["sleep_s"]})
check("B5 EMPTY_RESPONSE 描述为 TRANSIENT，但传输层重试集合仍与 2-D/2-E 一致（不重试）",
      classify_failure("PROVIDER_EMPTY_RESPONSE")["class"] == "TRANSIENT"
      and not retry_decision("PROVIDER_EMPTY_RESPONSE", 0, pol_legacy)["retry"])

# ============ C. 供给缓存 ============
print("== C. 供给缓存（默认关闭 / 命中 / 过期 / 损坏 / 指纹）==")
cache_off = SupplyCache(WORK / "cache_off", enabled=False)
got, meta = cache_off.get("k")
check("C1 默认关闭：不命中且不落盘", got is None and meta["reason"] == "DISABLED"
      and not (WORK / "cache_off").exists())
cache = SupplyCache(WORK / "cache_on", enabled=True, ttl_s=900)
cands = [candidate_metadata(c) for c in make_provider().search(kw_query(), make_ctx())]
check("C2 缓存只存元数据（不含本地路径/已验证结论）",
      all(("downloaded_path" not in c) and ("status" not in c) and ("verified" not in c)
          for c in cands), list(cands[0])[:6] if cands else None)
key = cache_key("local_catalog", TEXT, 10, ("image",), {"virtual", "reality"}, {"provider": "x"})
check("C3 首次未命中并写入", cache.get(key)[0] is None and cache.put(key, cands)["stored"])
hit, hmeta = cache.get(key)
check("C4 二次命中且条数一致", hit is not None and hmeta["reason"] == "HIT" and len(hit) == len(cands),
      hmeta)
restored = candidate_from_metadata(hit[0])
check("C5 命中恢复出的候选**回到未验证状态**（缓存不能提升可信度）",
      restored.status == "CANDIDATE" and restored.download_status == "NOT_DOWNLOADED"
      and restored.license_cleared is False and restored.downloaded_path is None
      and restored.to_candidate()["verified"] is False,
      {"status": restored.status, "cleared": restored.license_cleared})
cache.put(key, cands)                      # 覆盖写入，含原子替换
check("C6 原子写入：无残留 .tmp 文件", not list((WORK / "cache_on" / "search").glob("*.tmp")),
      [p.name for p in (WORK / "cache_on" / "search").glob("*")])
finger = policy_fingerprint({"max_bytes": 1, "allowed_ext": [".jpg"]})
check("C7 策略指纹随配置变化（换策略即换 key）",
      finger != policy_fingerprint({"max_bytes": 2, "allowed_ext": [".jpg"]})
      and key != cache_key("local_catalog", TEXT, 10, ("image",), {"virtual", "reality"},
                          {"provider": "y"}))
old = cache._now
cache._now = lambda: old() + 10_000                 # 时钟前推 → 过期
check("C8 TTL 过期 → 视为未命中（EXPIRED）", cache.get(key)[0] is None
      and cache.last_miss_reason == "EXPIRED")
cache._now = old
p = cache.dir / "{}.json".format(key)
p.write_text("{ 坏 JSON", encoding="utf-8")
check("C9 缓存损坏 → 未命中且不抛异常（CORRUPT）",
      cache.get(key)[0] is None and cache.last_miss_reason == "CORRUPT")
p.write_text(json.dumps({"schema": "old-schema", "candidates": []}), encoding="utf-8")
check("C10 schema 不符 → 未命中（SCHEMA_MISMATCH，不误用旧格式）",
      cache.get(key)[0] is None and cache.last_miss_reason == "SCHEMA_MISMATCH")

# ============ D. 八条供给路径 ============
print("== D. 八条路径（正常/缓存命中/429/超时/空候选/下载失败/校验失败/许可不明）==")
ctx = make_ctx()


def run_supply(provider=None, query=None, cache_enabled=False, project_dir=WORK,
               cache_ttl_s=900, items=None, policy=None, transport=None):
    prov = provider or make_provider(items=items, policy=policy, transport=transport)
    sup = ResilientSupply(prov, policy=prov.policy, project_dir=project_dir,
                          cache_enabled=cache_enabled, cache_ttl_s=cache_ttl_s)
    found, smeta = sup.search(query or kw_query(), ctx)
    fetched, fmeta = sup.fetch(found, ctx)
    return prov, sup, found, fetched, smeta, fmeta


# D1 正常
prov, sup, found, fetched, smeta, fmeta = run_supply()
ok = ResilientSupply.verified_only(fetched)
rep = sup.report(fetched=fetched, facts=ResilientSupply.degradation_facts(
    has_verified_external=bool(ok), has_local_index=False, provider_requested=True))
check("D1 正常路径：候选通过全量校验 + 许可门禁 → VERIFIED 且可入池",
      len(found) == 1 and len(ok) == 1 and ok[0].license_cleared
      and ok[0].to_candidate()["verified"] is True, fmeta)
check("D1b 报告可解释：无失败记录、阶梯=EXTERNAL_VERIFIED、不变量成立、未验证提升=0",
      rep["diagnostics"]["counts"] == {} and rep["degradation"]["rung"] == "EXTERNAL_VERIFIED"
      and rep["degradation"]["invariants"]["unverified_external_used"] is False
      and rep["degradation"]["invariants"]["license_bypass"] is False
      and rep["outcomes"]["unverified_promoted"] == 0 and rep["fail_closed"] is True,
      {"rung": rep["degradation"]["rung"], "outcomes": rep["outcomes"]})

# D2 缓存命中（搜索请求数不增加）
cprov = CountingCatalog({**DEFAULT_POLICY, "provider": "local_catalog", "catalog": str(CAT)},
                        catalog_dir=CAT)
sup2 = ResilientSupply(cprov, policy=cprov.policy, project_dir=WORK, cache_enabled=True)
c1, m1 = sup2.search(kw_query(), ctx)
c2, m2 = sup2.search(kw_query(), ctx)
v1 = ResilientSupply.verified_only(sup2.fetch(c1, ctx)[0])
v2 = ResilientSupply.verified_only(sup2.fetch(c2, ctx)[0])
check("D2 缓存命中：搜索只调用 1 次、第二次 from_cache=True，且仍重新下载校验后入池",
      cprov.search_calls == 1 and m1.get("from_cache") is False and m2.get("from_cache") is True
      and len(v1) == 1 and len(v2) == 1 and len(sup2.cache.stats) > 0,
      {"search_calls": cprov.search_calls, "m2": m2.get("from_cache"), "hits": sup2.cache.stats["hits"]})

# D3 缓存无法放行未验证素材：命中后源文件消失 → 仍然 REJECTED
#    （用**独立查询词**避免与 D2 的缓存 key 相同：缓存键 = (provider, 查询, 策略指纹)）
summoned = WORK / "vanishing.jpg"
shutil.copy2(GOOD, summoned)
VQ = "vanishing candidate check"
vprov = CountingCatalog({**DEFAULT_POLICY, "provider": "local_catalog", "catalog": str(CAT)},
                        catalog_dir=CAT)
write_catalog([item(summoned, source_id="src_vanish")])
vsup = ResilientSupply(vprov, policy=vprov.policy, project_dir=WORK, cache_enabled=True)
vc1, vm1 = vsup.search(kw_query(VQ), ctx)
summoned.unlink()                                     # 缓存已写入，但源文件没了
vc2, vm2 = vsup.search(kw_query(VQ), ctx)
vf2 = vsup.fetch(vc2, ctx)[0]
check("D3 缓存命中也不能放行未验证素材（源消失 → REJECTED，入池 0）",
      vm2.get("from_cache") is True and len(vf2) == 1 and vf2[0].status == "REJECTED"
      and ResilientSupply.verified_only(vf2) == []
      and vf2[0].error_code in ("PROVIDER_DOWNLOAD_FAILED", "ASSET_DECODE_FAILED"),
      {"code": vf2[0].error_code, "verified": len(ResilientSupply.verified_only(vf2)),
       "from_cache": vm2.get("from_cache")})
write_catalog([item(GOOD)])                           # 复原目录

# D4 429（限流）：传输层注入（HTTP 形态才会走传输层）
t429 = CountingTransport("PROVIDER_RATE_LIMITED")
prov4 = make_provider(items=[item_url("https://example.invalid/a.jpg", source_id="src_429")],
                      policy={"max_retries": 2, "rate_limit_backoff_s": 0.0,
                              "max_backoff_s": 0.0}, transport=t429)
prov4, sup4, f4, fetched4, sm4, fm4 = run_supply(provider=prov4)
rep4 = sup4.report(fetched=fetched4)
check("D4 429：有界重试后仍失败 → 候选 REJECTED、入池 0、错误码保留",
      t429.calls == 3 and fetched4[0].error_code == "PROVIDER_RATE_LIMITED"
      and not ResilientSupply.verified_only(fetched4)
      and rep4["diagnostics"]["by_class"]["TRANSIENT"] >= 1
      and rep4["diagnostics"]["attempts"][0]["retryable"] is True,
      {"calls": t429.calls, "code": fetched4[0].error_code, "stats": prov4.stats["retries"]})
check("D4b 429 计数与 2-E 逐值一致：3 次尝试 / retries=3 / rate_limited=3（预算是 rate_limit_retries，"
      "循环上限仍是 1+max_retries，故计数含最后一次未执行的计划重试——既有语义，本次未改）",
      prov4.stats.get("rate_limited") == 3 and prov4.stats["retries"] == 3,
      {"rate_limited": prov4.stats.get("rate_limited"), "retries": prov4.stats["retries"],
       "attempts": t429.calls})

# D5 超时
t_to = CountingTransport("PROVIDER_TIMEOUT")
prov5 = make_provider(items=[item_url("https://example.invalid/b.jpg", source_id="src_timeout")],
                      policy={"max_retries": 1, "backoff_base_s": 0.0, "max_backoff_s": 0.0},
                      transport=t_to)
prov5, sup5, f5, fetched5, sm5, fm5 = run_supply(provider=prov5)
rep5 = sup5.report(fetched=fetched5)
check("D5 超时：重试 1 次后失败（共 2 次尝试）→ REJECTED、入池 0、分类 TRANSIENT",
      t_to.calls == 2 and fetched5[0].error_code == "PROVIDER_TIMEOUT"
      and not ResilientSupply.verified_only(fetched5)
      and rep5["diagnostics"]["by_class"]["TRANSIENT"] == 1,
      {"calls": t_to.calls, "code": fetched5[0].error_code})

# D6 空候选
prov6 = make_provider(items=[])
prov6, sup6, f6, fetched6, sm6, fm6 = run_supply(provider=prov6, query=kw_query("毫不相关的主题内容"))
rep6 = sup6.report(fetched=fetched6, facts=ResilientSupply.degradation_facts(
    has_verified_external=False, has_local_index=False, provider_requested=True))
check("D6 空候选：不是异常、无伪造候选、降级阶梯给出显式兜底（非 EXTERNAL）",
      f6 == [] and fm6["attempts"] == 0 and rep6["outcomes"] is None
      and rep6["degradation"]["rung"] in ("THEME_FALLBACK", "SOLID_COLOR_CARD",
                                          "BLOCKED_FOR_HUMAN")
      and rep6["degradation"]["requires_human"] is True, rep6["degradation"]["rung"])

# D7 下载失败
prov7 = make_provider(items=[item(WORK / "not_exists.jpg", source_id="src_missing")])
prov7, sup7, f7, fetched7, sm7, fm7 = run_supply(provider=prov7)
rep7 = sup7.report(fetched=fetched7)
check("D7 下载失败：PROVIDER_DOWNLOAD_FAILED、download_status=FAILED、入池 0",
      fetched7[0].error_code == "PROVIDER_DOWNLOAD_FAILED"
      and fetched7[0].download_status == "FAILED"
      and not ResilientSupply.verified_only(fetched7)
      and rep7["outcomes"]["rejected"] == 1, {"code": fetched7[0].error_code})

# D8 校验失败（截断 + 伪装成图片的文本）
prov8 = make_provider(items=[item(BAD_TRUNC, source_id="src_trunc", name="virtual reality headset truncated.jpg"),
                             item(FAKE_MEDIA, source_id="src_fake", name="virtual reality headset fake.jpg")])
prov8, sup8, f8, fetched8, sm8, fm8 = run_supply(provider=prov8)
codes8 = sorted(c.error_code or "" for c in fetched8)
rep8 = sup8.report(fetched=fetched8)
check("D8 校验失败：截断/伪装文件被拒（ASSET_TRUNCATED / 非媒体），入池 0",
      len(fetched8) == 2 and all(c.status == "REJECTED" for c in fetched8)
      and "ASSET_TRUNCATED" in codes8
      and any(c in ("ASSET_TYPE_MISMATCH", "ASSET_PROBE_FAILED") for c in codes8)
      and not ResilientSupply.verified_only(fetched8)
      and all(c["class"] in ("TRANSIENT", "PERMANENT") and c["retryable"] is False
              or c["class"] == "TRANSIENT" for c in rep8["diagnostics"]["attempts"]),
      codes8)
classes8 = {c["code"]: c["class"] for c in rep8["diagnostics"]["attempts"]}
check("D8b 截断=TRANSIENT（可重下，但当前不自动重下）/ 伪装=PERMANENT，且都不重试",
      classes8.get("ASSET_TRUNCATED") == "TRANSIENT"
      and classes8.get("ASSET_TYPE_MISMATCH") == "PERMANENT"
      and all(c["retry"] is False for c in rep8["diagnostics"]["attempts"]), classes8)

# D9 许可不明 / 缺失 / 受限
for lic, want in ((None, "ASSET_LICENSE_MISSING"), ("unknown", "ASSET_LICENSE_UNCLEAR"),
                  ("fair use", "ASSET_LICENSE_RESTRICTED")):
    provL = make_provider(items=[item(GOOD, source_id="src_lic", license=lic,
                                      name="virtual reality headset license case.jpg")])
    provL, supL, fL, fetchedL, smL, fmL = run_supply(provider=provL)
    c0 = fetchedL[0]
    check("D9 许可 {}：{} + needs_hitl + 入池 0（许可门禁未被绕过）".format(lic, want),
          c0.error_code == want and c0.status == "REJECTED" and c0.needs_hitl is True
          and not ResilientSupply.verified_only(fetchedL),
          {"code": c0.error_code, "hitl": c0.needs_hitl,
           "license_class": c0.license_class})

# ============ E. 可控降级阶梯 ============
print("== E. 可控降级阶梯（显式、有界、三条不变量）==")
plan_cases = [
    ({"has_verified_external": True}, "EXTERNAL_VERIFIED"),
    ({"has_local_index": True}, "LOCAL_INGEST"),
    ({"theme_fallback_allowed": True}, "THEME_FALLBACK"),
    ({"card_allowed": True}, "SOLID_COLOR_CARD"),
    ({}, "BLOCKED_FOR_HUMAN"),
]
got_rungs = [degradation_plan(f)["rung"] for f, _ in plan_cases]
check("E1 五档阶梯按顺序选取（外部已校验→本地→主题兜底→纯色卡→阻断）",
      got_rungs == [want for _, want in plan_cases], got_rungs)
check("E2 阶梯定义与 2-C 既有词汇一致（不新增 fallback 语义）",
      set(SUPPLY_LADDER) >= {"EXTERNAL_VERIFIED", "LOCAL_INGEST", "THEME_FALLBACK",
                             "SOLID_COLOR_CARD", "BLOCKED_FOR_HUMAN"})
inv = degradation_plan({"has_verified_external": True})["invariants"]
check("E3 三条不变量：不用未验证素材 / 不绕许可 / 不静默兜底",
      inv == {"unverified_external_used": False, "license_bypass": False,
              "silent_fallback": False}, inv)
check("E4 兜底档一律标记需人工（needs_hitl 语义不退化；LOCAL_INGEST 属正常命中不算兜底）",
      all(degradation_plan(f)["requires_human"] for f, want in plan_cases
          if want in ("THEME_FALLBACK", "SOLID_COLOR_CARD", "BLOCKED_FOR_HUMAN"))
      and degradation_plan({"has_local_index": True})["requires_human"] is False,
      {want: degradation_plan(f)["requires_human"] for f, want in plan_cases})
summ = summarize([{"status": "VERIFIED", "error_code": None},
                  {"status": "REJECTED", "error_code": "ASSET_LICENSE_UNCLEAR"},
                  {"status": "REJECTED", "error_code": "PROVIDER_TIMEOUT"}])
check("E5 结局汇总：入池只数 VERIFIED，未验证提升恒为 0，许可阻断单独计数",
      summ["verified"] == 1 and summ["rejected"] == 2 and summ["unverified_promoted"] == 0
      and summ["license_blocks"] == 1 and summ["rejected_by_class"]["LICENSE"] == 1, summ)

# ============ G. 默认配置不变 ============
print("== G. 默认配置不变（provider=none / 缓存默认关闭）==")
check("G1 默认策略：provider=none 且供给缓存默认关闭",
      DEFAULT_POLICY["provider"] == "none" and DEFAULT_POLICY["supply_cache"] is False)
p_none, err_none, _ = provider_from_config({"tools": {"material": {"provider": "none"}}})
check("G2 provider=none → 不构造 provider、无错误码（纯 no-op）",
      p_none is None and err_none is None)
check("G3 供给 schema 版本化（便于将来识别缓存/报告格式）", SUPPLY_SCHEMA == "supply-resilience-v1")

# ============ F. 引擎级 fail-closed 与不污染 ============
print("== F. 引擎级 fail-closed 与不污染（临时工作区，真实 DB 只做哈希对比）==")
real_db_before = sha256_file(REAL_DB) if REAL_DB.is_file() else None

from video_studio.agents.base import AGENTS  # noqa: E402
from video_studio.core.engine import Engine  # noqa: E402
from video_studio.db.schema import Database  # noqa: E402
from video_studio.llm.router import MockLLM, Router  # noqa: E402

import video_studio.agents.asset.agent  # noqa: E402,F401
import video_studio.agents.editing.agent  # noqa: E402,F401
import video_studio.agents.retrieval.agent  # noqa: E402,F401
import video_studio.agents.script.agent  # noqa: E402,F401

WS = Path(tempfile.mkdtemp(prefix="vs_4d_engine_"))
CONFIG = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8"))
RULES = json.loads((ROOT / "config" / "rules.json").read_text(encoding="utf-8"))
SCRIPT = {"segments": [{"chapter": "s1", "narration": TEXT, "duration_s": 4}],
          "summary": "4-D supply resilience"}
ENGINE_JPG = WORK / "engine asset.jpg"
shutil.copy2(REAL_JPG, ENGINE_JPG)


def build_engine(material_cfg):
    cfg = json.loads(json.dumps(CONFIG))
    cfg["tools"]["material"] = material_cfg
    db = Database(WS / "state.db")
    mock = MockLLM(cfg["llm"].get("mock", {}).get("responses", {}),
                   cfg["llm"].get("mock", {}).get("default", {}))
    return Engine(db, Router(cfg["llm"], mock), RULES, WS / "projects", cfg, AGENTS), db


def engine_run(label, material_cfg, provider_patch=None, do_render=True, reuse_project=None):
    """建项目 → script 产物 → retrieval →（可选）render；返回证据字典。"""
    eng, db = (engine_run.engines.get(label) or (None, None)) if reuse_project else (None, None)
    if eng is None:
        eng, db = build_engine(material_cfg)
        engine_run.engines[label] = (eng, db)
    else:
        eng.config["tools"]["material"] = dict(material_cfg)      # 复用引擎时按本次配置更新
    pid = reuse_project or eng.create_project("4-D supply {}".format(label))
    if not reuse_project:
        t_script = eng.create_task(pid, "script", "script")
        aid = eng.write_artifact(pid, t_script, "script_output", SCRIPT, summary="脚本")
        eng.attach_artifact(t_script, aid)
        eng.db.set_task_status(t_script, "SUCCEEDED")
    else:
        t_script = [t["task_id"] for t in db.list_tasks(pid) if t["agent_role"] == "script"][0]
    import video_studio.tools.material_provider as mp
    orig = mp.LocalCatalogProvider
    if provider_patch is not None:
        mp.LocalCatalogProvider = provider_patch
    try:
        t_ret = eng.create_task(pid, "retrieval", "retrieval", dependencies=[t_script])
        eng.run_cycle(pid, limit=4)
    finally:
        mp.LocalCatalogProvider = orig
    r = eng.db.conn.execute(
        "select path from artifacts where task_id=? and type='retrieval_candidates' "
        "order by created_at desc limit 1", (t_ret,)).fetchone()
    ret = json.loads(Path(r["path"]).read_text(encoding="utf-8")) if r else None
    status, error, films = None, None, []
    if do_render:
        t_rend = eng.create_task(pid, "render", "editing", dependencies=[t_script, t_ret])
        for _ in range(3):
            eng.run_cycle(pid, limit=4)
            if eng.db.get_task(t_rend)["status"] not in ("PENDING", "DISPATCHED", "RUNNING"):
                break
        row = eng.db.conn.execute("select status, error from tasks where task_id=?",
                                  (t_rend,)).fetchone()
        status, error = row["status"], row["error"]
        films = sorted((eng.project_dir(pid) / "output").glob("*.mp4"))
    return {"pid": pid, "db": db, "eng": eng, "retrieval": ret, "render_status": status,
            "render_error": error, "films": films, "t_ret": t_ret}


engine_run.engines = {}

MAT_BASE = {"provider": "local_catalog", "catalog": str(CAT), "timeout_s": 5,
            "max_retries": 2, "backoff_base_s": 0.0, "rate_limit_backoff_s": 0.0,
            "license_required": True}
write_catalog([item(ENGINE_JPG)])

# F1 正常：外部已校验候选 + 报告可解释（不渲染，避免真实 TTS 依赖）
norm = engine_run("normal", MAT_BASE, do_render=False)
ret_n = norm["retrieval"] or {}
sup_n = ((ret_n.get("external_provider") or {}).get("supply_report") or {})
check("F1 正常：external_verified=1 且报告显示 EXTERNAL_VERIFIED + 无失败记录",
      ret_n.get("external_verified") == 1
      and sup_n.get("degradation", {}).get("rung") == "EXTERNAL_VERIFIED"
      and sup_n.get("diagnostics", {}).get("counts") == {},
      {"verified": ret_n.get("external_verified"),
       "rung": sup_n.get("degradation", {}).get("rung"),
       "cache": ((ret_n.get("external_provider") or {}).get("supply") or {}).get("from_cache")})
proj_n = norm["eng"].project_dir(norm["pid"])

# F2 缓存命中：同项目再跑两次 retrieval（同 query）→ 第二次 from_cache=True
first = engine_run("normal", {**MAT_BASE, "supply_cache": True}, do_render=False,
                   reuse_project=norm["pid"])
second = engine_run("normal", {**MAT_BASE, "supply_cache": True}, do_render=False,
                    reuse_project=norm["pid"])
check("F2 引擎级缓存命中：第二次 retrieval 的 supply.from_cache=True、cache_key 相同",
      ((first["retrieval"]["external_provider"] or {}).get("supply") or {}).get("from_cache") is False
      and ((second["retrieval"]["external_provider"] or {}).get("supply") or {}).get("from_cache")
      is True
      and (((first["retrieval"]["external_provider"] or {}).get("supply") or {}).get("cache_key")
           == ((second["retrieval"]["external_provider"] or {}).get("supply") or {}).get("cache_key")),
      {"first": ((first["retrieval"]["external_provider"] or {}).get("supply") or {}).get("from_cache"),
       "second": ((second["retrieval"]["external_provider"] or {}).get("supply") or {}).get("from_cache"),
       "hits": (((second["retrieval"]["external_provider"] or {}).get("supply_report") or {})
                .get("cache") or {}).get("hits")})

# 快照：**失败运行之前**的"既有项目"状态（此后只允许失败项目自己变化）
before_files = {str(p.relative_to(proj_n)): sha256_file(p)
                for p in sorted(proj_n.rglob("*")) if p.is_file()}
before_tasks = len(norm["db"].list_tasks(norm["pid"]))
before_arts = norm["db"].conn.execute(
    "select count(*) from artifacts where project_id=?", (norm["pid"],)).fetchone()[0]
before_events = len(norm["db"].events_since(norm["pid"], 0))


class Fail429Provider(LocalCatalogProvider):
    def search(self, query, ctx):
        raise TransportError("PROVIDER_RATE_LIMITED", "HTTP 429（受控注入，离线）")


class FailTimeoutProvider(LocalCatalogProvider):
    def search(self, query, ctx):
        raise TransportError("PROVIDER_TIMEOUT", "读取超时 5s（受控注入，离线）")


# F3 429 失败 → fail-closed
f429 = engine_run("fail429", MAT_BASE, provider_patch=Fail429Provider)
ret_f = f429["retrieval"] or {}
sup_f = ((ret_f.get("external_provider") or {}).get("supply_report") or {})
check("F3 429：external_error=PROVIDER_RATE_LIMITED、external_verified=0、失败被分类为 TRANSIENT",
      ret_f.get("external_error") == "PROVIDER_RATE_LIMITED"
      and ret_f.get("external_verified") == 0
      and sup_f.get("diagnostics", {}).get("counts", {}).get("PROVIDER_RATE_LIMITED") == 1
      and sup_f.get("diagnostics", {}).get("by_class", {}).get("TRANSIENT") == 1, sup_f.get("stage"))
check("F3b 429：降级阶梯显式给出兜底档并要求人工（不静默出片）",
      sup_f.get("degradation", {}).get("rung") in ("THEME_FALLBACK", "SOLID_COLOR_CARD",
                                                   "BLOCKED_FOR_HUMAN")
      and sup_f.get("degradation", {}).get("requires_human") is True,
      sup_f.get("degradation", {}).get("rung"))

# F4 超时失败 → fail-closed（render 必须 BLOCKED 且无成片）
f_to = engine_run("failtimeout", MAT_BASE, provider_patch=FailTimeoutProvider)
ret_t = f_to["retrieval"] or {}
check("F4 超时：PROVIDER_TIMEOUT、无已验证候选、render BLOCKED 且无成片",
      ret_t.get("external_error") == "PROVIDER_TIMEOUT" and ret_t.get("external_verified") == 0
      and f_to["render_status"] == "BLOCKED" and not f_to["films"]
      and "[ASSET_INSUFFICIENT]" in (f_to["render_error"] or ""),
      {"status": f_to["render_status"], "error": (f_to["render_error"] or "")[:80],
       "films": len(f_to["films"])})

# F5 失败不污染：既有项目产物/台账/版本链不变 + 无 render_output/attribution 新增
after_files = {str(p.relative_to(proj_n)): sha256_file(p)
               for p in sorted(proj_n.rglob("*")) if p.is_file()}
after_tasks = len(norm["db"].list_tasks(norm["pid"]))
after_arts = norm["db"].conn.execute(
    "select count(*) from artifacts where project_id=?", (norm["pid"],)).fetchone()[0]
rend_out = norm["db"].conn.execute(
    "select count(*) from artifacts where project_id=? and type='render_output'",
    (norm["pid"],)).fetchone()[0]
attrib = norm["db"].conn.execute(
    "select count(*) from artifacts where project_id=? and type='attribution'",
    (norm["pid"],)).fetchone()[0]
fail_arts = [r[0] for r in norm["db"].conn.execute(
    "select type from artifacts where project_id=?", (f429["pid"],)).fetchall()]
fail_rend = f429["eng"].db.conn.execute(
    "select count(*) from artifacts where project_id=? and type='render_output'",
    (f429["pid"],)).fetchone()[0]
fail_attr = f429["eng"].db.conn.execute(
    "select count(*) from artifacts where project_id=? and type='attribution'",
    (f429["pid"],)).fetchone()[0]
to_rend = f_to["eng"].db.conn.execute(
    "select count(*) from artifacts where project_id=? and type='render_output'",
    (f_to["pid"],)).fetchone()[0]
check("F5 失败未污染既有项目：既有项目所有文件（含 manifest/缓存）逐字节未变",
      all(after_files.get(k) == v for k, v in before_files.items())
      and set(before_files) == set(after_files),
      {"before": len(before_files), "after": len(after_files),
       "changed": sorted(k for k, v in before_files.items() if after_files.get(k) != v)[:5]})
check("F5b 失败项目无 render_output / attribution 产物、无成片（台账与版本链未被写入）",
      rend_out == 0 and attrib == 0 and fail_rend == 0 and fail_attr == 0 and to_rend == 0
      and not f429["films"] and not f_to["films"]
      and "render_output" not in fail_arts and "attribution" not in fail_arts,
      {"normal_render_output": rend_out, "normal_attribution": attrib,
       "fail429": [fail_rend, fail_attr], "fail_timeout": to_rend,
       "arts": sorted(set(fail_arts))})
check("F5c 全库 decisions/changelog 零新增（供给失败不写人工决定台账）",
      norm["db"].conn.execute("select count(*) from decisions").fetchone()[0] == 0
      and norm["db"].conn.execute("select count(*) from changelog").fetchone()[0] == 0)
check("F5d 既有项目的任务/产物计数与失败运行前完全一致（失败未产生任何隐式写入）",
      after_arts == before_arts and after_tasks == before_tasks
      and fail_arts.count("retrieval_candidates") == 1
      and fail_arts.count("asset_index") == 0,
      {"tasks_before": before_tasks, "tasks_after": after_tasks,
       "arts_before": before_arts, "arts_after": after_arts, "fail_arts": sorted(fail_arts)})
check("F5e 事件流 append-only：既有项目事件条数与失败运行前完全一致（失败未写任何事件）",
      len(norm["db"].events_since(norm["pid"], 0)) == before_events
      and norm["db"].events_since(norm["pid"], 0)[0]["type"] == "PROJECT_CREATED",
      {"before": before_events, "after": len(norm["db"].events_since(norm["pid"], 0)),
       "first": norm["db"].events_since(norm["pid"], 0)[0]["type"]})

real_db_after = sha256_file(REAL_DB) if REAL_DB.is_file() else None
check("F6 真实数据库 `projects/video_studio.db` 字节级未变（本测试全程用临时工作区）",
      real_db_before == real_db_after,
      {"before": (real_db_before or "")[:16], "after": (real_db_after or "")[:16]})

for eng_db in engine_run.engines.values():
    try:
        eng_db[1].close()
    except Exception:                                     # noqa: BLE001
        pass

print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print("失败项:", FAIL)
sys.exit(1 if FAIL else 0)
