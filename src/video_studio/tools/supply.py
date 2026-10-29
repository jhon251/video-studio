"""4.x Phase 4-D：供给韧性 façade —— 把"缓存 / 分类 / 可解释 / 可控降级"包在**既有 Provider 之外**。

设计原则（最小增量、零行为漂移）：

  · **不修改任何 provider 实现的判定**：搜索仍由 provider 做，下载/校验/许可仍由
    `verify_material` + 许可门禁做；本类只做"缓存查找、失败归类、过程记录、降级解释"。
  · **缓存只存元数据**：命中缓存恢复出来的候选一律 `status="CANDIDATE"`、`download_status="NOT_DOWNLOADED"`、
    `verified=False`，必须重新走下载+校验+许可门禁 —— 因此**缓存无法提升任何素材的可信度**。
  · **默认关闭**：`supply_cache=False` 时本类行为与"直接调用 provider"逐值一致（缓存分支被跳过）。
  · **失败不吞**：所有失败都进 `SupplyDiagnostics`（含错误码→类别→处置动作），并原样保留 provider 的
    `error_code`/`error_detail`，供上层按 2-C/2-E 既有语义阻断或转人工。
"""

from __future__ import annotations

from pathlib import Path

from ..core.supply import (SUPPLY_SCHEMA, SupplyCache, SupplyDiagnostics, cache_key,
                           degradation_plan, policy_fingerprint, summarize)
from .material_provider import ProviderCandidate, TransportError, fetch_many

__all__ = ["ResilientSupply", "candidate_metadata", "candidate_from_metadata"]


def candidate_metadata(c: ProviderCandidate) -> dict:
    """缓存里允许保存的字段：**只有来源元数据**，绝不含"已验证"结论与本地路径。"""
    return {"provider": c.provider, "source_id": c.source_id, "name": c.name,
            "source_url": c.source_url, "ext": c.ext, "license": c.license,
            "attribution": c.attribution, "usage_restrictions": c.usage_restrictions,
            "bytes": c.bytes, "sha256": c.sha256, "match_score": c.match_score,
            "matched_tokens": list(c.matched_tokens or [])}


def candidate_from_metadata(meta: dict) -> ProviderCandidate:
    """从缓存恢复候选：**显式重置为未验证状态**（这是"缓存不得放行未验证素材"的实现点）。"""
    return ProviderCandidate(
        provider=str(meta.get("provider") or ""), source_id=str(meta.get("source_id") or ""),
        name=str(meta.get("name") or ""), source_url=meta.get("source_url"),
        ext=str(meta.get("ext") or ""), license=meta.get("license"),
        attribution=meta.get("attribution"), usage_restrictions=meta.get("usage_restrictions"),
        bytes=meta.get("bytes"), sha256=meta.get("sha256"),
        match_score=int(meta.get("match_score") or 0),
        matched_tokens=list(meta.get("matched_tokens") or []),
        # ---- 关键：一律回到"未下载/未校验/未清权" ----
        downloaded_path=None, download_status="NOT_DOWNLOADED", probe_result=None,
        decodable=None, media_type=None, width=None, height=None,
        status="CANDIDATE", error_code=None, error_detail=None,
        needs_hitl=False, license_cleared=False, license_class=None)


class ResilientSupply:
    """供给韧性 façade：`search` / `fetch` 两个入口 + 结构化报告。"""

    def __init__(self, provider, *, policy: dict | None = None, project_dir=None,
                 cache_enabled: bool = False, cache_ttl_s: float = 900.0, now=None):
        self.provider = provider
        self.policy = dict(policy or getattr(provider, "policy", {}) or {})
        self.project_dir = Path(project_dir) if project_dir else None
        mat = (self.policy.get("supply") or {}) if isinstance(self.policy.get("supply"), dict) else {}
        enabled = bool(cache_enabled or mat.get("cache") or self.policy.get("supply_cache"))
        ttl = float(mat.get("ttl_s", self.policy.get("supply_cache_ttl_s", cache_ttl_s)))
        root = self.project_dir / ".supply_cache" if self.project_dir else None
        self.cache = SupplyCache(root, enabled=enabled, ttl_s=ttl, now=now)
        self.diag = SupplyDiagnostics(provider=getattr(provider, "name", None))
        self.searches = 0
        self.cache_hits = 0
        self.last_query_key: str | None = None

    # ---------------- 搜索（缓存命中 / 分类失败）----------------
    def search(self, query, ctx) -> tuple[list[ProviderCandidate], dict]:
        key = cache_key(getattr(self.provider, "name", ""), query.text, query.limit, query.kinds,
                        query.keywords, self.policy)
        self.last_query_key = key
        meta: dict = {"cache_key": key, "policy_fingerprint": policy_fingerprint(self.policy),
                      "cache": None, "error_code": None, "error_detail": None,
                      "provider_calls": 0}
        cached, cinfo = self.cache.get(key)
        meta["cache"] = cinfo
        if cached is not None:
            self.cache_hits += 1
            self.provider.stats["cache_hits"] = self.provider.stats.get("cache_hits", 0) + 1
            meta["from_cache"] = True
            return [candidate_from_metadata(m) for m in cached], meta
        meta["from_cache"] = False
        self.searches += 1
        try:
            found = self.provider.search(query, ctx)
            meta["provider_calls"] = 1
        except TransportError as exc:
            retry = self.diag.record(stage="search", code=exc.code, detail=exc.detail,
                                     scene_id=query.scene_id)
            meta.update(error_code=exc.code, error_detail=exc.detail, classified=retry)
            self.cache.stats["misses"] += 1
            return [], meta
        except Exception as exc:                        # noqa: BLE001 —— 未知异常也归类（不吞、不伪装）
            self.diag.record(stage="search", code="PROVIDER_SEARCH_FAILED",
                             detail="{}: {}".format(type(exc).__name__, str(exc)[:160]),
                             scene_id=query.scene_id)
            meta.update(error_code="PROVIDER_SEARCH_FAILED",
                        error_detail="{}: {}".format(type(exc).__name__, str(exc)[:160]))
            return [], meta
        if self.cache.enabled:
            store = self.cache.put(key, [candidate_metadata(c) for c in found],
                                  {"provider": getattr(self.provider, "name", None),
                                   "query": str(query.text or "")[:200]})
            meta["cache"] = {**cinfo, "store": store}
        return found, meta

    # ---------------- 获取（下载 + 校验 + 许可门禁，逐候选归类）----------------
    def fetch(self, candidates, ctx) -> tuple[list[ProviderCandidate], dict]:
        before = dict(getattr(self.provider, "stats", {}) or {})
        fetched = fetch_many(self.provider, list(candidates), ctx)
        for c in fetched:
            if c.status != "VERIFIED":
                self.diag.record(stage="fetch", code=c.error_code,
                                 detail=c.error_detail or "未通过校验（拒绝）",
                                 source_id=c.source_id, attempt=0)
        after = dict(getattr(self.provider, "stats", {}) or {})
        meta = {"attempts": len(fetched),
                "verified": sum(1 for c in fetched if c.status == "VERIFIED"),
                "rejected": sum(1 for c in fetched if c.status != "VERIFIED"),
                "download_cache_hits": int(after.get("cache_hits", 0)) - int(before.get("cache_hits", 0)),
                "retries": int(after.get("retries", 0)) - int(before.get("retries", 0)),
                "rate_limited": int(after.get("rate_limited", 0)) - int(before.get("rate_limited", 0))}
        return fetched, meta

    # ---------------- 只返回已校验候选（fail-closed 的唯一出口）----------------
    @staticmethod
    def verified_only(fetched) -> list[ProviderCandidate]:
        """**唯一**允许进入渲染素材池的出口：只有 `status == "VERIFIED"` 才通过。"""
        return [c for c in fetched if c.status == "VERIFIED"]

    # ---------------- 降级事实（把既有 2-C 策略翻译成阶梯入参，不新增策略）----------------
    @staticmethod
    def degradation_facts(*, has_verified_external: bool, has_local_index: bool,
                          material_policy: dict | None = None,
                          provider_requested: bool = False) -> dict:
        """由**既有** 2-C 策略键（zero_match/low_match/unusable/conflict/exhausted）推导阶梯事实。"""
        from ..core.materials import DEFAULT_POLICY as MATERIAL_POLICY
        pol = {**MATERIAL_POLICY, **(material_policy or {})}
        keys = ("zero_match_policy", "low_match_policy", "unusable_policy", "conflict_policy",
                "exhausted_policy")
        vals = {k: pol.get(k) for k in keys}
        return {"has_verified_external": bool(has_verified_external),
                "has_local_index": bool(has_local_index),
                "theme_fallback_allowed": any(v == "theme_fallback" for v in vals.values()),
                "card_allowed": any(v != "block" for v in vals.values()),
                "requires_human": bool(provider_requested),
                "policy_values": vals}

    # ---------------- 报告（失败可解释 + 可控降级 + 不变量）----------------
    def report(self, *, fetched=None, facts: dict | None = None, extra: dict | None = None) -> dict:
        polished = [c.to_record() for c in (fetched or [])]
        rep = {"schema": SUPPLY_SCHEMA, "provider": getattr(self.provider, "name", None),
               "cache_enabled": self.cache.enabled,
               "cache": {**self.cache.stats, "last_miss_reason": self.cache.last_miss_reason,
                         "ttl_s": self.cache.ttl_s,
                         "dir": (str(self.cache.dir) if self.cache.dir else None)},
               "searches": self.searches, "cache_hits": self.cache_hits,
               "diagnostics": self.diag.to_dict(),
               "outcomes": summarize(polished) if polished else None,
               "provider_stats": dict(getattr(self.provider, "stats", {}) or {}),
               "fail_closed": True}
        if facts is not None:
            rep["degradation"] = degradation_plan(facts)
        if extra:
            rep.update(extra)
        return rep
