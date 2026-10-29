"""真实外部素材 Provider（Phase 2-E，**仅此一个**）：Wikimedia Commons。

选择理由（2026-09-13 实测可达性见 `logs/provider_reachability.txt`）：
  · 免费、**无需 API key**、无付费授权、无不可逆额度消耗（不触发"先停止并报告"的条件）；
  · 响应自带明确许可证元数据（`extmetadata.LicenseShortName / UsageTerms / Artist / Credit /
    AttributionRequired / LicenseUrl`）——不需要我们猜测许可证；
  · 真实搜索 + 真实下载（upload.wikimedia.org 直链）；
  · 提供方 API：MediaWiki `action=query&generator=search&prop=imageinfo`。

## 凭据规则（需求 1）
  · token/密钥**只能**来自环境变量或项目根 `.env`（复用 `core.env.load_env`），**绝不硬编码**；
  · `auth.require_key=true` 且环境里没有对应变量 → `PROVIDER_NOT_CONFIGURED`（不伪造候选）；
  · 本 provider 匿名即可用（`require_key=false` 默认）；若配置了 token 则按 OAuth Bearer 发送；
  · 证据里只记录 `auth.mode` 与 `token_present`，**不记录 token 本身**。

## 许可证机械分类（需求 4；不做语义猜测）
  由**声明值**映射到类别：CC0/PD/Public domain → `PUBLIC_DOMAIN`；CC BY*/CC BY-SA* → `FREE_ATTRIBUTION`
  （可用但必须署名）；fair use/non-free/copyright/all rights reserved → `RESTRICTED` → **拒收 + HITL**
  （"需要先授权/购买"的许可模式即落在此类，绝不当作已获授权素材）；
  空/unknown/unchecked → `UNKNOWN` → **拒收 + HITL**。
"""

from __future__ import annotations

import html
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import quote_plus, urlencode

from .material_provider import (DEFAULT_POLICY, LICENSE_CLASSES, MaterialProvider,  # noqa: F401
                                ProviderCandidate, TransportError, UrllibTransport, _apply_verdict,
                                _dir_bytes, classify_license, verify_material)
from ..core.env import load_env

API = "https://commons.wikimedia.org/w/api.php"
UPLOAD_HOST = "upload.wikimedia.org"
DEFAULT_UA = "video-studio-material/1.0 (offline video pipeline; local research use)"


def _clean(text: str | None) -> str | None:
    if not text:
        return None
    t = re.sub(r"<[^>]+>", " ", str(text))
    t = html.unescape(t)
    t = re.sub(r"\s+", " ", t).strip()
    return t or None


def _ext_of(url: str, mime: str | None) -> str:
    ext = Path(str(url).split("?")[0]).suffix.lower()
    if ext:
        return ext
    return {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}.get(
        (mime or "").lower(), "")


class WikimediaCommonsProvider(MaterialProvider):
    """真实 Provider：Wikimedia Commons（免费、无 key、许可证元数据完整）。"""

    name = "wikimedia_commons"
    is_external = True
    # 该 provider 的请求应当温和：串行 + 最小间隔 + 单次运行请求预算
    default_min_interval_s = 1.0
    default_max_requests = 12

    def __init__(self, policy: dict | None = None, transport=None, api_url: str = API):
        pol = {**DEFAULT_POLICY, **(policy or {})}
        auth = {"mode": "none", "api_key_env": "WIKIMEDIA_API_TOKEN", "require_key": False,
                **(pol.get("auth") or {})}
        pol["auth"] = auth
        pol.setdefault("min_interval_s", self.default_min_interval_s)
        pol.setdefault("max_requests", self.default_max_requests)
        pol.setdefault("search_limit", 10)
        super().__init__(pol, transport)
        self.api_url = api_url
        self._last_request = 0.0
        self.stats.update(requests=0, requests_failed=0, search_ms=None, download_ms=0,
                          auth_mode=auth["mode"], token_present=False, response_digests=[],
                          license_classes={})
        # 凭据只从环境变量 / .env 读取
        load_env(Path(".env"))
        token = os.environ.get(str(auth["api_key_env"]), "").strip()
        self.token = token
        self.stats["token_present"] = bool(token)
        if token:
            self.transport = transport or UrllibTransport(self.policy, auth_token=token)

    # ---------- 请求（含节流、预算、可审计摘要、错误码映射）----------
    def _throttle(self) -> None:
        """Wikimedia 礼仪：请求与下载都保持最小间隔（实测下载会 429）。"""
        gap = float(self.policy["min_interval_s"]) - (time.time() - self._last_request)
        if gap > 0:
            time.sleep(min(gap, 5.0))
        self._last_request = time.time()

    def _request(self, params: dict, timeout_s: float | None = None) -> bytes:
        if self.stats["requests"] >= int(self.policy["max_requests"]):
            raise TransportError("PROVIDER_REQUEST_BUDGET", "本次运行请求预算已用尽（{}）".format(
                self.policy["max_requests"]))
        # 必须用 urlencode（UTF-8 百分号编码）：查询里可能含中文，直接拼串会 UnicodeEncodeError
        url = self.api_url + "?" + urlencode(params, quote_via=quote_plus)
        t0 = time.time()
        try:
            self._throttle()
            data = self.transport.get(url, int(self.policy["max_bytes"]) * 4,
                                      float(timeout_s or self.policy["timeout_s"]))
        except TransportError as exc:
            self.stats["requests"] += 1
            self.stats["requests_failed"] += 1
            self.stats["response_digests"].append({
                "kind": "search_or_api", "status": "error", "error_code": exc.code,
                "detail": exc.detail[:160], "latency_ms": int((time.time() - t0) * 1000),
                "url_host": url.split("/")[2]})
            raise
        self.stats["requests"] += 1
        self.stats["search_ms"] = int((time.time() - t0) * 1000)
        return data

    def _digest(self, data: bytes, parsed: dict | None, kind: str, extra: dict | None = None):
        """可审计摘要：状态/耗时/字节/条目数 + 截断的原始响应片段（**绝不含 token**）。"""
        snippet = data[:400].decode("utf-8", "replace")
        self.stats["response_digests"].append({
            "kind": kind, "bytes": len(data), "latency_ms": self.stats.get("search_ms"),
            "raw_head": snippet, **(extra or {})})

    # ---------- 查询整形（机械规则，非语义）----------
    @staticmethod
    def _latin_clusters(text: str, max_terms: int = 3,
                        max_clusters: int = 6) -> list[list[str]]:
        """把文本切成**拉丁/数字词簇**：源码位置上连续的拉丁词属于同一簇，被 CJK/标点隔开即断簇。

        Phase 3-A 实测（`logs/phase3a_query_ladder.txt`，2026-09-13）：
          跨镜头把所有品牌 AND 到一起（`Quest PSVR2 PICO Valve`）→ **0 命中**；
          同一处的**品牌+型号**短语（`Meta Quest` / `Meta Quest 3`）→ **8 条高相关命中**。
        所以"把整段旁白里的拉丁词并成一个查询"本身就是缺陷：不同镜头的品牌不该 AND 在一起。
        """
        toks = list(re.finditer(r"[A-Za-z][A-Za-z0-9._\-]*|\d{1,4}", str(text or "")))
        clusters: list[list[str]] = []
        cur: list[str] = []
        prev_end: int | None = None
        for m in toks:
            if prev_end is not None and str(text)[prev_end:m.start()].strip(" \t\u3000") != "":
                if cur:
                    clusters.append(cur)
                cur = []
            tok = m.group(0)
            ascii_word = bool(re.match(r"[A-Za-z]", tok))
            if (ascii_word and len(tok) >= 2) or (not ascii_word and len(tok) <= 4):
                if tok.lower() not in (t.lower() for t in cur):
                    cur.append(tok)
            prev_end = m.end()
            if len(cur) >= max_terms:
                clusters.append(cur)
                cur = []
        if cur:
            clusters.append(cur)
        # 只保留"含拉丁字母"的簇（纯数字簇没有检索意义）
        clusters = [c for c in clusters if any(re.match(r"[A-Za-z]", t) for t in c)]
        return clusters[:max_clusters]

    @classmethod
    def shape_queries(cls, text: str, term_limit: int = 4, max_searches: int = 3,
                      max_chars: int = 100) -> tuple[list[str], dict]:
        """给出**按精度排序的查询序列**（多词簇优先，即"品牌+型号"这种最精确的形态）。

        与 `shape_query` 的区别：后者把所有拉丁词并成一个 AND 查询（跨镜头混合 → 实测 0 命中）；
        本方法按**簇**分别查询（同一处的词才 AND），由 `search()` 逐条尝试并在拿到足够候选后提前停止。
        规则仍是机械的（位置切分/去重/限量），**不做翻译、不做语义判断**。
        """
        max_terms = max(1, min(int(term_limit), 3))
        clusters = cls._latin_clusters(text, max_terms=max_terms)
        multi = [c for c in clusters if len(c) >= 2]
        single = [c for c in clusters if len(c) == 1]
        queries: list[str] = []
        seen: set[str] = set()
        for c in multi + single:
            q = " ".join(c)[:max_chars].strip()
            k = q.lower()
            if not q or k in seen:
                continue
            seen.add(k)
            queries.append(q)
            if len(queries) >= max(1, int(max_searches)):
                break
        mode = "latin_clusters" if queries else "cjk_only"
        if not queries:                                  # 无拉丁词 → 退回既有 CJK 块规则
            fallback, _meta = cls.shape_query(text, term_limit, max_chars)
            if fallback and fallback != "image":
                queries = [fallback]
        meta = {"mode": mode, "used": queries[0] if queries else "image",
                "terms": (queries[0].split() if queries else []),
                "queries": queries, "term_limit": max_terms,
                "clusters": clusters, "multi_word_clusters": len(multi),
                "latin_available": bool(clusters)}
        return queries, meta

    @staticmethod
    def shape_query(text: str, term_limit: int = 4, max_chars: int = 100) -> tuple[str, dict]:
        """把长旁白/拼接查询压成适合 AND 检索的短查询（**单查询**版本，保留兼容）。

        实测（`logs/query_shaping_probe.txt`，2026-09-13）：
          完整拼接查询 → 0 命中；去重后取前 3–4 个词 → 命中理想结果。
        真实链路实测（Phase 3-A）：中文旁白（无空格）被当成整块词 → Commons 0 命中；
        同一段旁白里的拉丁词（品牌/型号，如 Quest/PSVR2/PICO）才是英文语料能匹配的部分。

        因此规则为**语料偏好**（不是翻译、不做语义）：
          1) 若查询里存在拉丁/数字词（≥2 字符）→ 只取这些词（去重、保序、限量）；
          2) 否则退回按空白/标点切分的 CJK 词块（去重、限量）。
        命中率随语料而变；中文-only 查询对 Commons 命中率低属**已知限制**，如实记录不伪造。
        """
        raw = str(text or "")
        latin = []
        seen_l = set()
        for w in re.findall(r"[A-Za-z][A-Za-z0-9._\-]{1,}", raw):
            k = w.lower()
            if k in seen_l:
                continue
            seen_l.add(k)
            latin.append(w)
            if len(latin) >= term_limit:
                break
        parts = re.split(r"[\s，。；、,;.!?()\[\]{}<>\"'“”‘’/\\|—–-]+", raw)
        cjk, seen_c = [], set()
        for p in parts:
            p = p.strip()
            if len(p) < 2 or not re.search(r"[\u4e00-\u9fff]", p):
                continue
            k = p.lower()
            if k in seen_c:
                continue
            seen_c.add(k)
            cjk.append(p)
            if len(cjk) >= term_limit:
                break
        if latin:
            terms, mode = latin, "latin_preferred"
        else:
            terms, mode = cjk, "cjk_only"
        used = " ".join(terms)[:max_chars] or "image"
        return used, {"original_chars": len(raw), "used": used, "terms": terms,
                      "mode": mode, "term_limit": term_limit,
                      "latin_available": bool(latin)}

    # ---------- 搜索 ----------
    def search(self, query, ctx) -> list[ProviderCandidate]:
        limit = int(query.limit)
        queries, shaping = self.shape_queries(
            query.text, int(self.policy.get("query_term_limit", 4)),
            int(self.policy.get("query_max_searches", 3)),
            int(self.policy.get("query_max_chars", 100)))
        self.stats["query_shaping"] = {**shaping, "attempts": []}
        self.stats["last_query"] = shaping["used"]
        from ..agents.retrieval.agent import matched_tokens, score
        out: list[ProviderCandidate] = []
        skipped_kind = 0
        seen_ids: set[str] = set()
        for q in queries:
            if len(out) >= limit:
                break                                    # 已够候选：不再多发请求（省请求/省下载）
            params = {"action": "query", "format": "json", "formatversion": "2",
                      "generator": "search", "gsrsearch": q,
                      "gsrnamespace": "6", "gsrlimit": str(int(self.policy["search_limit"])),
                      "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata",
                      "iiextmetadatafilter": ("LicenseShortName|UsageTerms|Artist|Credit|"
                                              "AttributionRequired|LicenseUrl|Restrictions"),
                      "maxlag": "5"}
            try:
                data = self._request(params)
            except TransportError as exc:
                self.stats["search_error"] = exc.code
                raise
            try:
                parsed = json.loads(data.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                self._digest(data, None, "search", {"status": "invalid_json"})
                raise TransportError("PROVIDER_SEARCH_FAILED",
                                     "响应非 JSON: {}".format(exc)) from None
            pages = ((parsed.get("query") or {}).get("pages") or [])
            self._digest(data, parsed, "search", {"status": "ok", "items": len(pages),
                                                  "query_used": q,
                                                  "totalhits": ((parsed.get("query") or {})
                                                                .get("searchinfo") or {}
                                                                ).get("totalhits")})
            added = 0
            for pg in pages:
                ii = (pg.get("imageinfo") or [{}])[0]
                url = ii.get("url") or ""
                if not url or UPLOAD_HOST not in url:
                    skipped_kind += 1
                    continue                                # 只收本站媒体直链（安全性）
                mime = str(ii.get("mime") or "").lower()
                if not mime.startswith("image/"):
                    skipped_kind += 1
                    continue                                # PDF/音视频等非图片结果：本阶段只做 kind=image
                title = str(pg.get("title") or "").replace("File:", "")
                sid = str(pg.get("pageid") or title)
                if sid in seen_ids:
                    continue                                # 跨查询去重（同一文件只算一次）
                seen_ids.add(sid)
                em = ii.get("extmetadata") or {}

                def val(key):
                    v = (em.get(key) or {}).get("value")
                    return _clean(v) if isinstance(v, str) else v

                declared = val("LicenseShortName") or val("UsageTerms") or val("LicenseUrl")
                lic_class, cleared = classify_license(declared)
                self.stats["license_classes"][lic_class] = \
                    self.stats["license_classes"].get(lic_class, 0) + 1
                attribution = val("Artist") or val("Credit")
                site = "https://commons.wikimedia.org/wiki/File:" + title.replace(" ", "_")
                restrictions = val("UsageTerms") or (
                    "署名要求" if val("AttributionRequired") == "true" else None)
                hay = "{} {}".format(title, mime)
                c = ProviderCandidate(
                    provider=self.name, source_id=sid,
                    name=title, source_url=url, ext=_ext_of(url, mime),
                    license=declared, attribution=attribution, usage_restrictions=restrictions,
                    bytes=ii.get("size"), match_score=score(hay, query.keywords),
                    matched_tokens=matched_tokens(hay, query.keywords))
                c.media_type = mime.replace("image/", "") or None
                c.width, c.height = ii.get("width"), ii.get("height")
                c.probe_result = {"source": "provider_metadata", "mime": mime,
                                  "width": ii.get("width"), "height": ii.get("height"),
                                  "declared_bytes": ii.get("size"), "page": site,
                                  "query_used": q}
                c.license_class = lic_class              # type: ignore[attr-defined]
                c.license_cleared = cleared
                # 生成阶段仍会做完整校验；这里只把"提供方声明的许可证类别"带上
                out.append(c)
                added += 1
            self.stats["query_shaping"]["attempts"].append(
                {"query": q, "items": len(pages), "images_added": added,
                 "cumulative": len(out)})
        self.stats["skipped_non_image"] = skipped_kind
        self.stats["searched"] = len(out)
        out.sort(key=lambda c: -c.match_score)
        return out[:limit]

    # ---------- 下载 + 校验（复用 Phase 2-D 边界，不新开旁路）----------
    def _fetch_one(self, c: ProviderCandidate, ctx) -> ProviderCandidate:
        from .material_provider import safe_filename
        media = Path(ctx.project_dir) / "media"
        cache_dir = media / str(self.policy["cache_dir"])
        ok, _clean_name, err = safe_filename(c.name + c.ext if not c.name.endswith(c.ext) else c.name)
        if not ok:
            c.status, c.error_code, c.error_detail = "REJECTED", err, "危险文件名: {}".format(c.name)
            self.stats["rejected"] += 1
            return c
        lic_class = getattr(c, "license_class", None) or classify_license(c.license)[0]
        if self.policy["license_required"] and not classify_license(c.license)[1]:
            # 许可证未明/受限：**不进下载**（省流量）也不进候选；RESTRICTED 明确标记"需先授权"
            c.status = "REJECTED"
            c.license_class = lic_class
            c.error_code = ("ASSET_LICENSE_RESTRICTED" if lic_class == "RESTRICTED"
                            else "ASSET_LICENSE_MISSING" if not (c.license or "").strip()
                            else "ASSET_LICENSE_UNCLEAR")
            c.error_detail = "license={!r} class={}（需人工确认/授权，不猜测）".format(
                c.license, lic_class)
            c.needs_hitl = True
            self.stats["rejected"] += 1
            return c
        t0 = time.time()
        try:
            path, code, detail = self._download(c.source_url or "", cache_dir, ctx,
                                                source_id=c.source_id)
        except TransportError as exc:
            path, code, detail = None, exc.code, exc.detail
        self.stats["download_ms"] += int((time.time() - t0) * 1000)
        if path is None:
            c.status, c.error_code, c.error_detail = "REJECTED", code, detail
            c.download_status = "FAILED"
            self.stats["rejected"] += 1
            return c
        c.download_status = "DOWNLOADED"
        c.downloaded_path = path.relative_to(media).as_posix()
        res = verify_material(path, policy=self.policy, ctx=ctx, check_license=None)
        _apply_verdict(c, res)
        if c.status == "VERIFIED":
            c.license_cleared = True                 # 已在下载前按类别判定
            c.needs_hitl = False
            self.stats["fetched"] = self.stats.get("fetched", 0) + 1
        else:
            self.stats["rejected"] += 1
        return c
