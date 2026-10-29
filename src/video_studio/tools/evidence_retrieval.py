"""V2.1 Stage 8E：证据检索回退 + 来源可靠性分层 + 覆盖率统计（隔离实现，未接生产链）。

- 不修改 EvidenceSignal 语义 / Aggregation 结构 / truth 判断 / 冻结测试；不针对具体网站/domain 写 parser。
- ① 来源可靠性分层：在 evidence_pool.source_tier（10 类来源类型，只读复用）之上叠加
   reliability_level(0..5) 与 band(high/medium/low/unknown)，数据无关、确定性。
- ② 检索回退：provider 链（bing→baidu→tavily）顺序检索；单 URL fetch 失败逐条分类
   （timeout/connection_error/http_403/…/js_shell/empty/encoding_error/low_content），
   仅保留 usable（valid 或 salvage 成功）证据，未达标自动切下一 provider。
- ③ 覆盖率统计：retrieved/fetch_attempts/usable/valid 计数 + 失败原因分布 + 来源可靠性分布
   + claim 元素覆盖（复用 claim_element_keys）。
- ④ 回放：每条证据保留 raw_html + 最终正文 + source_quality。
"""

from __future__ import annotations

from collections import Counter
from urllib.parse import urlparse

from .evidence_pool import source_tier, normalize_text, claim_element_keys
from .evidence_text_quality import extract_body
from .search_provider import (BingSearchProvider, BaiduSearchProvider,
                              TavilySearchProvider, _decode_response,
                              _claim_tokens, filter_candidates, _load_quality_rules)

# ---------- ① 来源可靠性分层（在 source_tier 之上叠加可靠性维度） ----------
_RELIABILITY_LEVEL = {
    "paper_publisher": 5, "official": 5,
    "academic": 4, "mainstream_media": 4,
    "professional_media": 3, "encyclopedia": 3,
    "aggregator": 2,
    "commercial": 1, "forum_social": 1,
    "unknown": 0,
}
_BAND = {5: "high", 4: "high", 3: "medium", 2: "low", 1: "low", 0: "unknown"}


def source_quality(url: str, title: str = "", text: str = "") -> dict:
    """来源可靠性分层：{tier, reliability_level, band, confidence, rationale}。"""
    t = source_tier(url, title, text)
    lvl = _RELIABILITY_LEVEL.get(t["tier"], 0)
    return {"tier": t["tier"], "reliability_level": lvl, "band": _BAND[lvl],
            "tier_confidence": t["confidence"], "rationale": t["rationale"]}


# ---------- ② 检索回退 ----------
_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                     "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
       "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
       "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}


def _fetch_classified(session, url: str, timeout: int = 12) -> dict:
    """单 URL fetch 并分类失败原因（数据无关；无具体站点特例）。"""
    import requests
    try:
        resp = session.get(url, timeout=timeout, allow_redirects=True, headers=_UA)
    except requests.exceptions.Timeout:
        return {"url": url, "ok": False, "failure": "timeout", "raw_html": ""}
    except requests.exceptions.ConnectionError:
        return {"url": url, "ok": False, "failure": "connection_error", "raw_html": ""}
    except Exception as e:  # noqa: BLE001
        return {"url": url, "ok": False, "failure": f"err_{type(e).__name__}", "raw_html": ""}
    if resp.status_code != 200:
        return {"url": url, "ok": False, "failure": f"http_{resp.status_code}", "raw_html": ""}
    return {"url": url, "ok": True, "failure": "", "raw_html": _decode_response(resp)[:200000]}


def _outcome(raw_html: str) -> tuple[str, str, bool]:
    """raw_html → (status, 最终正文, usable)。"""
    res = extract_body(raw_html)
    usable = res["status"] == "valid" or res.get("salvaged") is True
    status = "valid" if res.get("salvaged") else res["status"]
    return status, res["text"], usable


def _relevant(tokens: list[str], title: str, snippet: str, body: str) -> bool:
    """检索级关键词相关预筛（数据无关；语义相关由冻结的 EvidenceSignal 判定，不在此层）。"""
    if not tokens:
        return False
    hay = f"{title} {snippet} {body}".lower()
    return any(t.lower() in hay for t in tokens)


def retrieve_with_fallback(claim_text: str, session=None, max_usable: int = 2,
                           per_provider: int = 3) -> dict:
    """对单个 Claim 做检索回退：provider 链依次检索+关键词预筛+fetch，仅保留 usable 证据。

    provider 链 = bing → baidu → tavily（tavily.search 依赖 TAVILY_API_KEY，失败静默跳过）。
    usable = 正文 valid/打捞成功 且 与 Claim 关键词重叠（检索级预筛，非信号级语义判断）。
    返回 {evidence, usable, failures, chain, snippets}。
    """
    if session is None:
        import requests
        session = requests.Session()
    claim = {"text": claim_text, "type": "FACT"}
    tokens = _claim_tokens(claim)
    rules = _load_quality_rules()
    providers = [BingSearchProvider(), BaiduSearchProvider(), TavilySearchProvider()]
    evidence: list[dict] = []
    failures: Counter = Counter()
    chain: list[str] = []
    snippets: list[dict] = []

    def n_usable():
        return sum(1 for e in evidence if e["usable"])

    for p in providers:
        if n_usable() >= max_usable:
            break
        chain.append(p.name)
        try:
            results = p.search(claim_text, max_results=per_provider)
        except Exception:  # noqa: BLE001
            failures["search_error"] += 1
            continue
        if not results:
            failures["search_empty"] += 1
            continue
        kept, rejected = filter_candidates(results, claim, rules)
        for reason, n in rejected.items():
            failures[f"search_{reason}"] += n
        if not kept:
            failures["search_no_candidate"] += 1
            continue
        for sr in kept:
            if n_usable() >= max_usable:
                break
            if sr.snippet:
                snippets.append({"url": sr.url, "title": sr.title, "snippet": sr.snippet})
            fc = _fetch_classified(session, sr.url)
            if not fc["ok"]:
                failures[fc["failure"]] += 1
                evidence.append({"url": sr.url, "title": sr.title, "snippet": sr.snippet,
                                 "raw_html": "", "body": "", "status": fc["failure"],
                                 "usable": False, "source_quality": None, "failure": fc["failure"]})
                continue
            status, body, usable = _outcome(fc["raw_html"])
            if usable and not _relevant(tokens, sr.title, sr.snippet, body):
                status, usable = "irrelevant", False
            failures[status] += 1
            sq = source_quality(sr.url, sr.title, body) if usable else None
            evidence.append({"url": sr.url, "title": sr.title, "snippet": sr.snippet,
                             "raw_html": fc["raw_html"], "body": body, "status": status,
                             "usable": usable, "source_quality": sq, "failure": ""})
    return {"evidence": evidence, "usable": [e for e in evidence if e["usable"]],
            "failures": dict(failures), "chain": chain, "snippets": snippets[:per_provider]}


# ---------- ③ 覆盖率统计增强 ----------
def retrieval_coverage(claim_text: str, evidence: list[dict], failures: dict) -> dict:
    """单 Claim 的检索覆盖率统计（计数 + 来源可靠性分布 + 元素覆盖）。"""
    usable = [e for e in evidence if e["usable"]]
    tiers = Counter(e["source_quality"]["tier"] for e in usable if e.get("source_quality"))
    bands = Counter(e["source_quality"]["band"] for e in usable if e.get("source_quality"))

    keys = claim_element_keys(claim_text)
    elems = [("core", k) for k in keys["core"]] + \
            [("qualifier", q) for q in keys["qualifiers"]] + \
            [("number", n) for n in keys["numbers_years"]]
    covered_elems = 0
    norm_all = " ".join(normalize_text(e["body"]) for e in usable)
    for _, e in elems:
        if normalize_text(e) and normalize_text(e) in norm_all:
            covered_elems += 1
    return {
        "retrieved": len(evidence),
        "usable": len(usable),
        "valid": sum(1 for e in usable if e["status"] == "valid"),
        "salvaged": sum(1 for e in usable if e.get("salvaged")),
        "failure_dist": dict(failures),
        "source_tiers": dict(tiers),
        "reliability_bands": dict(bands),
        "element_coverage": f"{covered_elems}/{len(elems)}" if elems else "n/a",
        "domains": sorted({(urlparse(e["url"]).netloc or "?").lower() for e in usable}),
    }
