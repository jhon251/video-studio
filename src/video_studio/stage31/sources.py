"""Stage 3.1 素材检索层。

主源：Wikimedia Commons API（无 key，全部文件自带自由许可证元数据）。
其他源状态（诚实记录，不假装检索成功）：
- Openverse API：无 key、当前环境超时 -> 登记缺口
- Pexels API：可达但需 API key（未提供）-> 登记缺口
- Pixabay API：可达但需 API key（未提供）-> 登记缺口

每个候选返回完整 provenance 字段；许可证判定交给 rights 层。
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Optional

import requests

from .query_plan import _backoff_get

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "video-studio-3.1/0.1 (material research; contact: local)"}


@dataclass
class Candidate:
    source: str                    # wikimedia_commons | openverse | pexels | pixabay
    source_url: str                # 文件描述页
    original_url: str              # 原始文件
    download_url: str              # 推荐下载（缩略/转码）
    source_name: str = ""
    creator: str = ""
    license: str = ""
    license_url: str = ""
    content_type: str = ""         # image | video
    duration: Optional[float] = None
    resolution: str = ""
    width: int = 0
    height: int = 0
    visual_description: str = ""
    raw: dict = field(default_factory=dict)


@dataclass
class SearchOutcome:
    query: str
    source: str
    status: str          # OK | EMPTY | ERROR | GAP
    candidates: list = field(default_factory=list)
    note: str = ""


def check_source_availability() -> dict:
    """探测各源可达性/凭证状态（用于 search_log 与 README 缺口说明）。"""
    out = {}
    try:
        r = requests.get(COMMONS_API, params={
            "action": "query", "format": "json", "meta": "siteinfo",
            "siprop": "general"}, headers=UA, timeout=15)
        out["wikimedia_commons"] = "OK" if r.status_code == 200 else f"HTTP {r.status_code}"
    except Exception as e:  # noqa: BLE001
        out["wikimedia_commons"] = f"UNREACHABLE: {type(e).__name__}"
    try:
        r = requests.get("https://api.openverse.org/v1/images/?q=test&page_size=1",
                         headers=UA, timeout=10)
        out["openverse"] = "OK" if r.status_code == 200 else f"HTTP {r.status_code}"
    except Exception as e:  # noqa: BLE001
        out["openverse"] = f"UNREACHABLE: {type(e).__name__}（无 API key，环境不可达）"
    try:
        if not os.environ.get("PEXELS_API_KEY"):
            out["pexels"] = "NEEDS_API_KEY（未配置，运行时不可用）"
        else:
            r = requests.get("https://api.pexels.com/v1/search?query=test&per_page=1",
                             headers={**UA, "Authorization": os.environ["PEXELS_API_KEY"]},
                             timeout=10)
            out["pexels"] = "OK" if r.status_code == 200 else f"HTTP {r.status_code}"
    except Exception as e:  # noqa: BLE001
        out["pexels"] = f"UNREACHABLE: {type(e).__name__}"
    try:
        if not os.environ.get("PIXABAY_API_KEY"):
            out["pixabay"] = "NEEDS_API_KEY（未配置，运行时不可用）"
        else:
            r = requests.get("https://pixabay.com/api/",
                             params={"key": os.environ["PIXABAY_API_KEY"],
                                     "q": "test", "per_page": 3},
                             headers=UA, timeout=10)
            out["pixabay"] = "OK" if r.status_code == 200 else f"HTTP {r.status_code}"
    except Exception as e:  # noqa: BLE001
        out["pixabay"] = f"UNREACHABLE: {type(e).__name__}"
    return out


def _ext(d: dict, key: str) -> str:
    v = d.get(key) or {}
    return str(v.get("value", ""))


def commons_search(query: str, per_query: int = 8, filetype: str = "bitmap",
                   timeout: int = 20, neg_terms: list | None = None) -> SearchOutcome:
    q = query
    if neg_terms:
        q = query + " " + " ".join("-" + t for t in neg_terms)
    params = {
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": f"{q} filetype:{filetype}", "gsrnamespace": 6,
        "gsrlimit": per_query,
        "prop": "imageinfo|videoinfo",
        "iiprop": "url|size|mime|extmetadata|mediatype", "iiurlwidth": 1280,
        "viv": "derivatives",
        "maxlag": 5,
    }
    try:
        status, data, note = _backoff_get(COMMONS_API, params)
        if not data:
            return SearchOutcome(query=query, source="wikimedia_commons",
                                 status="RATE_LIMIT" if status == 429 else "ERROR",
                                 note=note or "重试后仍失败")
    except Exception as e:  # noqa: BLE001
        return SearchOutcome(query=query, source="wikimedia_commons",
                             status="ERROR", note=f"{type(e).__name__}: {e}")
    pages = data.get("query", {}).get("pages", {})
    cands = []
    for p in pages.values():
        if p.get("ns") != 6 or "imageinfo" not in p:
            continue
        ii = p["imageinfo"][0]
        em = ii.get("extmetadata", {})
        mime = ii.get("mime", "")
        title = p.get("title", "").replace("File:", "")
        file_page = f"https://commons.wikimedia.org/wiki/File:{title}"
        ctype = "video" if mime.startswith("video/") else "image"
        duration = None
        download_url = ii.get("thumburl", "") or ii.get("url", "")
        vi = p.get("videoinfo", [{}])
        if vi and vi[0].get("duration") is not None:
            duration = vi[0]["duration"]
            derivs = vi[0].get("derivatives", [])
            if derivs:
                # 优先 480p 转码
                best = max(derivs, key=lambda d: d.get("width", 0))
                download_url = best.get("src", download_url)
        cands.append(Candidate(
            source="wikimedia_commons", source_url=file_page,
            original_url=ii.get("url", ""), download_url=download_url,
            source_name="Wikimedia Commons",
            creator=_ext(em, "Artist"),
            license=_ext(em, "LicenseShortName"),
            license_url=_ext(em, "LicenseUrl"),
            content_type=ctype, duration=duration,
            resolution=f"{ii.get('width','')}x{ii.get('height','')}",
            width=ii.get("width", 0), height=ii.get("height", 0),
            visual_description=(_ext(em, "ImageDescription") or _ext(em, "ObjectName"))[:300],
            raw={"title": p.get("title", ""), "usage_terms": _ext(em, "UsageTerms"),
                 "credit": _ext(em, "Credit")},
        ))
    status = "OK" if cands else "EMPTY"
    return SearchOutcome(query=query, source="wikimedia_commons",
                         status=status, candidates=cands,
                         note="" if cands else "无结果（换 filetype 或关键词）")


def retrieve_for_intent(intent, per_query: int = 8, include_video: bool = True,
                        sleep: float = 1.0, max_queries: int = 2,
                        min_candidates: int = 6) -> list[SearchOutcome]:
    """按查询阶梯逐级检索（literal→conceptual→demonstrative→metaphorical）。

    - 视频优先：RHYTHM / EMOTIONAL / DIRECT 镜先查 video 再查 bitmap；
    - 逐级扩展：某级无结果不直接 NO_SAFE_MATCH，继续下一级；
    - 集满 min_candidates 个候选即停止（不浪费请求）；
    - 负向过滤：concepts_neg 作为搜索否定词（-term）。
    """
    if intent.material_kind != "broll":
        return []
    video_first = intent.match_type in ("RHYTHM", "EMOTIONAL", "DIRECT")
    ladder = intent.query_ladder or [("literal", list(intent.queries_en[:max_queries]))]
    neg = list(intent.concepts_neg or [])[:6]
    outcomes: list[SearchOutcome] = []
    total = 0
    for stage, queries in ladder:
        for q in queries[:max_queries]:
            filetypes = (["video", "bitmap"] if include_video and video_first
                         else ["bitmap", "video"] if include_video else ["bitmap"])
            for ft in filetypes:
                oc = commons_search(q, per_query=per_query if ft == "bitmap" else 4,
                                    filetype=ft, neg_terms=neg)
                oc.query = f"[{stage}] {q} ({ft})"
                outcomes.append(oc)
                total += len(oc.candidates)
                time.sleep(sleep)
                if total >= min_candidates:
                    return outcomes
        if total >= 3:
            break  # 已有一定候选，不再下探隐喻级
    return outcomes


RHYTHM_EXTRA = "city skyline night"


# ---------- 3.1.4 多路召回 ----------

def _candidate_from_page(p: dict) -> Candidate | None:
    if p.get("ns") != 6 or "imageinfo" not in p:
        return None
    ii = p["imageinfo"][0]
    em = ii.get("extmetadata", {})
    mime = ii.get("mime", "")
    title = p.get("title", "").replace("File:", "")
    ctype = "video" if mime.startswith("video/") else "image"
    duration = None
    download_url = ii.get("thumburl", "") or ii.get("url", "")
    vi = p.get("videoinfo", [{}])
    if vi and vi[0].get("duration") is not None:
        duration = vi[0]["duration"]
        derivs = vi[0].get("derivatives", [])
        if derivs:
            best = max(derivs, key=lambda d: d.get("width", 0))
            download_url = best.get("src", download_url)
    return Candidate(
        source="wikimedia_commons",
        source_url=f"https://commons.wikimedia.org/wiki/File:{title}",
        original_url=ii.get("url", ""), download_url=download_url,
        source_name="Wikimedia Commons",
        creator=_ext(em, "Artist"), license=_ext(em, "LicenseShortName"),
        license_url=_ext(em, "LicenseUrl"), content_type=ctype, duration=duration,
        resolution=f"{ii.get('width','')}x{ii.get('height','')}",
        width=ii.get("width", 0), height=ii.get("height", 0),
        visual_description=(_ext(em, "ImageDescription") or _ext(em, "ObjectName"))[:300],
        raw={"title": p.get("title", ""), "usage_terms": _ext(em, "UsageTerms"),
             "credit": _ext(em, "Credit"), "route": p.get("_route", "")})


def commons_category_search(query: str, limit: int = 3,
                            timeout: int = 15) -> list[str]:
    try:
        status, data, _ = _backoff_get(COMMONS_API, {
            "action": "query", "format": "json", "generator": "search",
            "gsrsearch": query, "gsrnamespace": 14, "gsrlimit": limit,
            "maxlag": 5})
        if not data:
            return []
        return [p["title"] for p in data.get("query", {}).get("pages", {}).values()
                if p.get("title", "").startswith("Category:")]
    except Exception:  # noqa: BLE001
        return []


def category_files(category: str, limit: int = 10, timeout: int = 15) -> list[Candidate]:
    try:
        status, data, _ = _backoff_get(COMMONS_API, {
            "action": "query", "format": "json", "generator": "categorymembers",
            "gcmtitle": category, "gcmtype": "file", "gcmlimit": limit,
            "prop": "imageinfo|videoinfo",
            "iiprop": "url|size|mime|extmetadata|mediatype", "iiurlwidth": 1280,
            "viv": "derivatives", "maxlag": 5})
        if not data:
            return []
        pages = data.get("query", {}).get("pages", {})
    except Exception:  # noqa: BLE001
        return []
    out = []
    for p in pages.values():
        p["_route"] = f"category:{category}"
        c = _candidate_from_page(p)
        if c:
            out.append(c)
    return out


def retrieve_multi(intent, plan: dict, per_query: int = 8, include_video: bool = True,
                   sleep: float = 1.2) -> list[SearchOutcome]:
    """3.1.4 多路召回：R1–R5 全部执行（非串行失败切换），merge→dedupe。

    每路记录 query/route/returned；accepted/rejected 由 package 层在
    rights gate + 语义阈值后统计（search_log 保留全量明细）。
    """
    if intent.material_kind != "broll":
        return []
    outcomes: list[SearchOutcome] = []
    seen: set = set()
    neg = list(intent.concepts_neg or [])[:6]
    routes = plan.get("routes", {})

    def add(route: str, query: str, cands: list, note: str = ""):
        fresh = []
        for c in cands:
            if c.source_url in seen:
                continue
            seen.add(c.source_url)
            c.raw = {**c.raw, "route": route}
            fresh.append(c)
        outcomes.append(SearchOutcome(
            query=f"[{route}] {query}", source="wikimedia_commons",
            status="OK" if fresh else "EMPTY", candidates=fresh, note=note))

    # R1 实体路由：Wikidata sitelink → Commons 分类 → 文件
    for q in routes.get("R1_entity", [])[:3]:
        cands = category_files(q["query"], limit=10) if q["type"] == "commons_category" else \
            [c for oc in [commons_search(q["query"], per_query=6, filetype="bitmap", neg_terms=neg)]
             for c in oc.candidates]
        add("R1_entity", q["query"], cands)
        time.sleep(sleep)

    # R2 分类路由：分类搜索 → 前 2 个分类 → 文件
    for q in routes.get("R2_category", [])[:3]:
        cats = commons_category_search(q["query"], limit=2)
        cands = []
        for cat in cats[:2]:
            cands += category_files(cat, limit=8)
            time.sleep(sleep)
        add("R2_category", q["query"], cands, note=f"cats={cats}")

    # R3 全文本路由：中文短语直搜文件
    for q in routes.get("R3_fulltext", [])[:4]:
        cands = []
        for ft in (["video", "bitmap"] if include_video else ["bitmap"]):
            oc = commons_search(q["query"], per_query=6 if ft == "bitmap" else 3,
                                filetype=ft, neg_terms=neg)
            cands += oc.candidates
            time.sleep(sleep)
        add("R3_fulltext", q["query"], cands)

    # R4 旧词库（辅助）
    for q in routes.get("R4_legacy", [])[:4]:
        oc = commons_search(q["query"], per_query=6, filetype="bitmap", neg_terms=neg)
        add("R4_legacy", q["query"], oc.candidates)
        time.sleep(sleep)

    # R5 情绪/隐喻
    for q in routes.get("R5_emotion", [])[:2]:
        cands = []
        for ft in (["video", "bitmap"] if include_video else ["bitmap"]):
            oc = commons_search(q["query"], per_query=5 if ft == "bitmap" else 3,
                                filetype=ft)
            cands += oc.candidates
            time.sleep(sleep)
        add("R5_emotion", q["query"], cands)

    return outcomes
