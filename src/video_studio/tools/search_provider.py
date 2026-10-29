"""SearchProvider 抽象层（V2）。

- 统一接口：search / fetch / extract_evidence
- 搜索结果只是候选来源：必须经 fetch + extract_evidence 才能进入证据库
- 无 Key / provider 未配置 / provider 不存在 → 自动降级 OfflineProvider，系统照常运行
- 在线 provider 通过注册表插拔，fact_check 只依赖接口，不绑定任何一家搜索服务
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class SearchResult:
    url: str
    title: str = ""
    snippet: str = ""
    date: str | None = None
    domain: str = ""


@dataclass
class FetchedPage:
    url: str
    ok: bool
    title: str = ""
    text: str = ""
    fetched_at: float = 0.0


@dataclass
class EvidenceCandidate:
    excerpt: str
    source: str
    source_type: str = "unknown"
    publication_date: str | None = None
    reliability: str = "unknown"
    contradicts: bool = False      # 兼容旧约定（【矛盾证据】前缀），新逻辑用 support_level
    # 支持程度：只描述"该证据与 Claim 的支持关系"，不等同事实真假。
    # DIRECT_SUPPORT / PARTIAL_SUPPORT / CONTEXT_ONLY / CONTRADICTS / IRRELEVANT
    support_level: str = "DIRECT_SUPPORT"


class SearchProvider(Protocol):
    """在线检索能力接口。实现方：Tavily/Bocha/自建服务等（在注册表登记）。"""
    name: str = "base"
    api_key_env: str | None = None

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        ...

    def fetch(self, url: str) -> FetchedPage:
        ...

    def extract_evidence(self, page: FetchedPage, claim: dict) -> EvidenceCandidate | None:
        ...


class OfflineProvider:
    """离线模式：不发起任何网络请求，仅依赖资料卡/项目资料/人工来源。"""
    name = "offline"
    api_key_env = None

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        return []

    def fetch(self, url: str) -> FetchedPage:
        return FetchedPage(url=url, ok=False)

    def extract_evidence(self, page: FetchedPage, claim: dict) -> EvidenceCandidate | None:
        return None


REGISTRY: dict[str, SearchProvider] = {"offline": OfflineProvider()}


def register_search_provider(provider: SearchProvider) -> None:
    """在线 provider 插拔入口：register_search_provider(MyProvider())。"""
    REGISTRY[provider.name] = provider


# ---------------- 通用提取辅助 ----------------
def _strip_tags(text: str) -> str:
    import re as _re
    text = _re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", text)
    text = _re.sub(r"<[^>]+>", " ", text)
    return _re.sub(r"\s+", " ", text)


def _decode_response(resp) -> str:
    """通用、数据无关的响应解码：header charset → meta charset → BOM → utf-8 严格 → gb18030。
    仅作编码探测/回退，不含任何针对具体 URL/domain 的规则。"""
    import re as _re
    raw = resp.content or b""
    enc = (resp.encoding or "").lower()
    if enc in ("", "iso-8859-1", "latin-1", "ascii"):
        m = _re.search(rb"<meta[^>]+charset\s*=\s*[\"']?\s*([\w-]+)", raw[:4096], _re.I)
        if m:
            enc = m.group(1).decode("ascii", "ignore").lower()
    for candidate in (enc,):
        if candidate:
            try:
                text = raw.decode(candidate)
                return text[1:] if text.startswith("\ufeff") else text
            except (LookupError, UnicodeDecodeError):
                pass
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return raw.decode("gb18030")
        except UnicodeDecodeError:
            return raw.decode("utf-8", "replace")


def _classify_host(host: str) -> str:
    if host.endswith((".gov", ".gov.cn", ".edu", ".edu.cn")):
        return "official" if ".gov" in host else "academic"
    for seg in ("nature.com", "science.org", "cell.com", "pnas.org", "sciencedirect",
                "springer.com", "wiley.com", "nih.gov", "who.int"):
        if seg in host:
            return "academic" if not host.endswith((".gov", ".int")) else "regulatory"
    if host.endswith((".org", ".org.cn")):
        return "media"
    return "media"


def _claim_tokens(claim: dict) -> list[str]:
    """Claim 词元（保序去重）：英文 3+ 字母、数字 2+ 位、
    中文连续串按 2 字滑动窗口切词（中文无空格，切 2 字词才可作关键词匹配）。"""
    import re as _re
    text = claim.get("text", "")
    tokens = list(dict.fromkeys(
        _re.findall(r"[A-Za-z]{3,}|\d{2,}", text)))
    for run in _re.findall(r"[\u4e00-\u9fff]{2,}", text):
        tokens.extend(run[i:i + 2] for i in range(len(run) - 1))
    return list(dict.fromkeys(tokens))


def _load_quality_rules() -> dict:
    import json
    from pathlib import Path as _P
    try:
        return json.loads((_P(__file__).resolve().parents[3]
                           / "config" / "search_quality.json").read_text(encoding="utf-8"))
    except OSError:
        return {}


def filter_candidates(results: list["SearchResult"], claim: dict,
                      rules: dict) -> tuple[list["SearchResult"], dict]:
    """搜索结果质量预过滤：URL 有效性 / 域名黑名单 / 关键词相关性预筛。

    注意：关键词规则只作候选筛选，不能单独证明语义支持——讨论级判断在提取阶段。
    返回 (保留候选, 拒绝原因计数)。
    """
    import re as _re
    from urllib.parse import urlparse

    rejected: dict = {}
    kept = []
    blacklist = set(rules.get("domain_blacklist", []))
    patterns = rules.get("domain_blacklist_patterns", [])
    tokens = _claim_tokens(claim)
    for r in results:
        parsed = urlparse(r.url)
        domain = (parsed.netloc or "").lower()
        r.domain = domain
        reason = None
        if parsed.scheme not in ("http", "https") or not domain:
            reason = "BAD_URL"
        elif domain in blacklist or any(p in domain for p in patterns):
            reason = "BLACKLISTED_DOMAIN"
        elif tokens and not any(t.lower() in (r.title + " " + r.snippet).lower() for t in tokens):
            reason = "NO_KEYWORD_OVERLAP"
        if reason:
            rejected[reason] = rejected.get(reason, 0) + 1
            continue
        kept.append(r)
    return kept, rejected


def order_candidates(results: list["SearchResult"], claim: dict,
                     rules: dict) -> list["SearchResult"]:
    """按来源优先级排序（官方/学术 > 监管/数据库 > 媒体 > 百科 > 论坛），
    并按 Claim 类型加权首选来源。仅影响候选顺序，不影响核查逻辑。"""
    priority = {name: i for i, name in enumerate(rules.get("source_priority", []))}
    prefs = rules.get("claim_type_source_prefs", {})
    ctype = claim.get("type", "FACT")
    preferred = prefs.get(ctype.lower(), [])

    def rank(r: "SearchResult") -> tuple:
        stype = _classify_host(r.domain)
        if preferred and stype in preferred:
            base = -1
        else:
            base = priority.get(stype, len(priority))
        return (base, -len(r.snippet or ""))

    return sorted(results, key=rank)


def _extract_from_page(page: "FetchedPage", claim: dict,
                       rules: dict | None = None) -> "EvidenceCandidate | None":
    """讨论级判断：从抓取原文提取证据片段并判定支持程度。

    返回 None = IRRELEVANT（相关性不足，不入库）。
    CONTEXT_ONLY 候选由调用方决定不入库（仅个别词出现，不构成讨论）。
    关键词规则在此仅作定位，支持程度由"多关键词 + 关键数字 + 否定语境"综合判定。
    """
    import re as _re
    rules = rules or _load_quality_rules()
    rel = rules.get("relevance", {})
    text = _strip_tags(page.text or "")
    if len(text) < rel.get("min_body_len", 40):
        return None
    tokens = _claim_tokens(claim)
    if not tokens:
        return None
    present = [t for t in tokens if t.lower() in text.lower()]
    if not present:
        return None
    idx = text.lower().find(present[0].lower())
    window = text[max(0, idx - 120): idx + 300].strip()
    digits = _re.findall(r"\d{2,}", claim.get("text", ""))
    digit_hit = any(d in window for d in digits)
    neg_words = rules.get("negation_words", [])
    negated = any(w.lower() in window.lower() for w in neg_words)

    direct_k = rel.get("direct_keywords", 2)
    direct_k_no_digit = rel.get("direct_keywords_no_digit", 3)
    if negated and (digit_hit or len(present) >= direct_k):
        level = "CONTRADICTS"
    elif len(present) >= direct_k and digit_hit:
        level = "DIRECT_SUPPORT"
    elif len(present) >= direct_k_no_digit:
        level = "DIRECT_SUPPORT"
    elif len(present) >= direct_k or digit_hit:
        level = "PARTIAL_SUPPORT"
    else:
        level = "CONTEXT_ONLY"

    date_m = _re.search(r"(20\d{2})\s*年|(20\d{2}-\d{2}(?:-\d{2})?)", text)
    host = _re.sub(r"^https?://", "", page.url).split("/")[0]
    return EvidenceCandidate(excerpt=window[:500], source=page.title or host,
                             source_type=_classify_host(host),
                             publication_date=date_m.group(0) if date_m else None,
                             reliability="medium", support_level=level)


class BingSearchProvider:
    """免密钥真实搜索（cn.bing.com HTML）。无 Key 场景的默认在线 provider。

    需要会话 Cookie 预热（无 Cookie 时 Bing 会降级返回无关内容）。
    """
    name = "bing"
    api_key_env = None

    def __init__(self):
        import requests
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })
        try:
            self._session.get("https://cn.bing.com/", timeout=10)
        except Exception:
            pass

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        import re as _re
        import time as _t
        _t.sleep(0.2)
        try:
            resp = self._session.get(
                "https://cn.bing.com/search",
                params={"q": query, "count": max(3, min(max_results, 8))},
                timeout=15,
            )
        except Exception:
            return []
        if resp.status_code != 200:
            return []
        html = resp.text
        results = []
        for block in _re.findall(r'<li class="b_algo"[\s\S]*?</li>', html):
            url_m = _re.search(r'<a[^>]+href="(http[^"]+)"', block)
            title_m = _re.search(r'<h2[^>]*>[\s\S]*?<a[^>]*>([\s\S]*?)</a>', block)
            snip_m = _re.search(r'<p[^>]*>([\s\S]*?)</p>', block)
            if not url_m:
                continue
            results.append(SearchResult(
                url=url_m.group(1),
                title=_strip_tags(title_m.group(1)) if title_m else "",
                snippet=_strip_tags(snip_m.group(1)) if snip_m else "",
            ))
        return results[:max_results]

    def fetch(self, url: str) -> FetchedPage:
        import time as _t
        _t.sleep(0.2)
        try:
            resp = self._session.get(url, timeout=12)
            if resp.status_code != 200:
                return FetchedPage(url=url, ok=False)
            return FetchedPage(url=url, ok=True, title="", text=_decode_response(resp)[:200000])
        except Exception:
            return FetchedPage(url=url, ok=False)

    def extract_evidence(self, page: FetchedPage, claim: dict) -> EvidenceCandidate | None:
        return _extract_from_page(page, claim)


class TavilySearchProvider:
    """Tavily 搜索（密钥从环境变量 TAVILY_API_KEY 读取，禁止硬编码）。"""
    name = "tavily"
    api_key_env = "TAVILY_API_KEY"

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        import os as _os
        import requests
        resp = requests.post(
            "https://api.tavily.com/search",
            json={"api_key": _os.environ.get("TAVILY_API_KEY", ""),
                  "query": query, "max_results": max(3, min(max_results, 8))},
            timeout=20)
        if resp.status_code != 200:
            return []
        data = resp.json()
        return [SearchResult(url=r.get("url", ""), title=r.get("title", ""),
                             snippet=(r.get("content") or "")[:300])
                for r in data.get("results", [])]

    def fetch(self, url: str) -> FetchedPage:
        return BingSearchProvider().fetch(url)

    def extract_evidence(self, page: FetchedPage, claim: dict) -> EvidenceCandidate | None:
        return _extract_from_page(page, claim)


class BaiduSearchProvider:
    """免密钥真实搜索（www.baidu.com HTML，中文相关性优于 Bing）。

    需会话 Cookie 预热；连续请求间节流防反爬；单次失败返回空（由调用方走回退链）。
    """
    name = "baidu"
    api_key_env = None

    def __init__(self):
        import requests
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })
        try:
            self._session.get("https://www.baidu.com/", timeout=10)
        except Exception:
            pass

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        import re as _re
        import time as _t
        _t.sleep(0.6)
        try:
            resp = self._session.get("https://www.baidu.com/s",
                                     params={"wd": query, "rn": "10"}, timeout=15)
        except Exception:
            return []
        if resp.status_code != 200 or len(resp.text) < 20000:
            return []   # 触发验证页/限流：返回空，由调用方回退
        html = resp.text
        results = []
        for m in _re.finditer(r"<h3[^>]*>[\s\S]*?</h3>", html):
            block = m.group(0)
            title = _strip_tags(block).strip()
            url_m = _re.search(r'href="([^"]+)"', block)
            if not url_m or not title:
                continue
            url = url_m.group(1)
            if url.startswith("/"):
                url = "https://www.baidu.com" + url
            # 摘要：h3 之后的 content-right / c-abstract 文本
            tail = html[m.end(): m.end() + 4000]
            snip_m = (_re.search(r'<span[^>]*class="content-right[^"]*"[^>]*>([\s\S]*?)</span>', tail)
                      or _re.search(r'<div[^>]*class="[^"]*c-abstract[^"]*"[^>]*>([\s\S]*?)</div>', tail))
            snippet = _strip_tags(snip_m.group(1))[:300] if snip_m else ""
            results.append(SearchResult(url=url, title=title[:120], snippet=snippet))
        return results[:max_results]

    def fetch(self, url: str) -> FetchedPage:
        import time as _t
        _t.sleep(0.3)
        try:
            resp = self._session.get(url, timeout=12, allow_redirects=True)
            if resp.status_code != 200:
                return FetchedPage(url=url, ok=False)
            return FetchedPage(url=url, ok=True, title="", text=_decode_response(resp)[:200000])
        except Exception:
            return FetchedPage(url=url, ok=False)

    def extract_evidence(self, page: FetchedPage, claim: dict) -> EvidenceCandidate | None:
        return _extract_from_page(page, claim)


register_search_provider(BingSearchProvider())
register_search_provider(BaiduSearchProvider())
register_search_provider(TavilySearchProvider())


def resolve_provider(config: dict) -> SearchProvider:
    """按配置解析 provider；任何缺失/无密钥情况自动降级 OfflineProvider。"""
    cfg = (config or {}).get("tools", {}).get("search", {}) or {}
    name = cfg.get("provider", "none")
    if not name or name in ("none", "offline"):
        return REGISTRY["offline"]
    provider = REGISTRY.get(name)
    if provider is None:
        return REGISTRY["offline"]
    if getattr(provider, "api_key_env", None):
        if not os.environ.get(provider.api_key_env):
            return REGISTRY["offline"]
    return provider
