"""V2.1 Stage 8A.1：Evidence Pool 基础设施修复（统一正文规范化 + 内容指纹 + 来源分层）。

- 无最终裁决；无 LLM；不改任何既有规则/Prompt/冻结集/fact_check/reliability/fetch/provider。
- ① 统一正文规范化：HTML 剥离 → 实体解码 → Unicode NFC → 繁简 → URL/脚注去噪 →
  标点归一 → 空白归一 → 连续重复字符归一。原文保留，规范化文本仅作派生指纹字段。
- ② 内容指纹：8-gram Jaccard ≥ 0.8 或 子集包含率 ≥ 0.8（摘录窗口 ⊆ 正文）。
- ③ 来源分层 10 类（数据无关通用规范；无把握保留 UNKNOWN 并记录依据/置信度）。
"""

from __future__ import annotations

import html as _html
import re
import unicodedata
from urllib.parse import urlparse

from .sufficiency_judge import _extract_numbers_corrected, t2s
from .semantic_judge import _qualifier_requirements
from .search_provider import _strip_tags


def normalize_text(text: str | None) -> str:
    """统一正文规范化（派生字段；不改原始文本）。"""
    if not text:
        return ""
    t = _strip_tags(text or "")
    t = _html.unescape(t)
    t = unicodedata.normalize("NFC", t)
    t = t2s(t)
    t = re.sub(r"https?://\S+|www\.\S+", " ", t)          # URL
    t = re.sub(r"\[\d+\]|【\d+】|（[^）]{0,20}注[^）]{0,20}）|脚注|参考文献|免责声明|转自|来源：", " ", t)
    t = t.lower()
    t = re.sub(r"[^\u4e00-\u9fff a-z0-9]+", " ", t)        # 标点归一
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"(.)\1{3,}", r"\1\1\1", t)                # 连续重复字符归一
    return t


def _shingles(text: str, k: int = 8) -> set[str]:
    t = re.sub(r"\s+", "", text)
    return {t[i:i + k] for i in range(max(0, len(t) - k + 1))}


def _similar(a: set[str], b: set[str]) -> bool:
    if not a or not b:
        return False
    inter = len(a & b)
    if inter / max(1, len(a | b)) >= 0.8:     # Jaccard
        return True
    small, big = (a, b) if len(a) <= len(b) else (b, a)
    return inter / max(1, len(small)) >= 0.8  # 子集包含（摘录 ⊆ 正文）


# ---------------- 来源分层（10 类，数据无关通用规范） ----------------
_TIER_DOMAINS = {
    "paper_publisher": ("nature.com", "science.org", "cell.com", "pnas.org",
                        "pmc.ncbi.nlm.nih.gov", "nih.gov", "sciencedirect",
                        "springer.com", "wiley.com", "arxiv.org", "ieee.org",
                        "acm.org", "cambridge.org", "oup.com", "tandfonline",
                        "sagepub.com", "frontiersin.org", "mdpi.com"),
    "academic": (".edu", ".edu.cn", "cas.cn", "ac.cn", "tsinghua", "ruc.edu.cn",
                 "pku.edu.cn", "nwsuaf", "sinica.edu.tw", "ntu.edu.tw", "univ"),
    "encyclopedia": ("baike.", "wikipedia.org", "wiki", "hudong.com", "britannica",
                     "encyclopedia"),
    "official": (".gov", ".gov.cn", ".int", "court.gov"),
    "mainstream_media": ("news.cn", "xinhuanet", "people.com.cn", "cctv.com",
                         "gmw.cn", "chinanews", "thepaper", "bbc.com", "nytimes",
                         "reuters", "dw.com", "cnn.com", "apnews"),
    "professional_media": ("tmtpost", "jiemian", "huxiu", "36kr", "stdaily",
                           "sciencenet", "wallstreetcn", "mittrchina", "caixin",
                           "zaobao", "yicai", "ft.com"),
    "commercial": ("taobao", "tmall", "jd.com", "amazon", "alibabacloud", "shopify",
                   "pricing", "sell.", "store", "mall", "1688.com"),
    "forum_social": ("tieba", "douban", "reddit", "forum", "bbs", "threads.com",
                     "facebook.com", "instagram.com", "twitter.com", "x.com",
                     "weibo.com", "tgfcer", "jandan.net", "zhihu.com/question",
                     "zhihu.com/answer"),
    "aggregator": ("toutiao", "ishare", "zhuanlan.zhihu.com", "news.qq.com",
                   "sohu.com", "163.com", "ifeng.com", "sina.com"),
}

_TIER_CONTENT = {
    "official": ("管理办法", "条例", "判决书", "最高人民法院", "人民政府", "征求意见稿"),
    "paper_publisher": ("abstract", "doi:", "journal", "et al", "发表于", "预印本"),
    "academic": ("课题组", "实验室", "研究员", "教授", "大学", "研究所"),
    "aggregator": ("转载自", "转自", "图文来源于", "免责声明", "原标题"),
    "commercial": ("定价", "立即购买", "加入购物车", "促销", "优惠", "支付"),
    "forum_social": ("楼主", "回帖", "# Thread", "转发", "点赞", "评论区"),
}

_DECISIVE = ("official", "paper_publisher", "academic", "encyclopedia", "forum_social")


def source_tier(url: str, title: str = "", text: str = "") -> dict:
    """返回 {tier, confidence, rationale}。无把握保留 UNKNOWN，不强行分类。"""
    host = (urlparse(url or "").netloc or "").lower()
    body = f"{title} {text}"[:600].lower()

    # 1) 决定性域名后缀（高置信）
    for tier, keys in _TIER_DOMAINS.items():
        for k in keys:
            if k in host:
                conf = "high" if tier in _DECISIVE else "medium"
                return {"tier": tier, "confidence": conf,
                        "rationale": f"域名命中 {k}"}

    # 2) 内容标记（仅低风险类：聚合/商业/论坛；一手/论文/学术 必须域名佐证，避免转载站→一手）
    if any(m in body for m in _TIER_CONTENT["aggregator"]):
        return {"tier": "aggregator", "confidence": "low",
                "rationale": "正文含转载/来源标记"}
    for tier in ("commercial", "forum_social"):
        for m in _TIER_CONTENT.get(tier, ()):
            if m in body:
                return {"tier": tier, "confidence": "low",
                        "rationale": f"内容标记 {m}"}
    return {"tier": "unknown", "confidence": "low", "rationale": "无域名/内容标记可判定"}


class Pool:
    """一个 Claim 的证据池：candidates → clusters（独立证据簇）。"""

    MAX_CANDIDATES = 12
    MAX_CLUSTERS = 8
    JACCARD_THRESHOLD = 0.8

    def __init__(self, claim_id: str, candidates: list[dict]):
        self.claim_id = claim_id
        self.candidates = candidates[: self.MAX_CANDIDATES]
        self.clusters: list[dict] = []
        self._build()

    @staticmethod
    def _best(entries: list[dict]) -> dict:
        return max(entries, key=lambda e: len(normalize_text(e.get("text"))) )

    def _build(self) -> None:
        # 1) URL 精确去重
        by_url: dict[str, list[dict]] = {}
        for c in self.candidates:
            by_url.setdefault(c.get("url") or f"idx:{id(c)}", []).append(c)
        uniq = [self._best(v) for v in by_url.values()]

        # 2) 统一规范化 + 内容指纹聚类
        fps = [(_shingles(normalize_text(e.get("text"))) |
                _shingles(normalize_text(e.get("title"))) |
                _shingles(normalize_text(e.get("snippet")))) for e in uniq]
        assigned = [-1] * len(uniq)
        cluster_of: list[list[int]] = []
        for i in range(len(uniq)):
            if assigned[i] != -1:
                continue
            cid = len(cluster_of)
            cluster_of.append([i])
            assigned[i] = cid
            for j in range(i + 1, len(uniq)):
                if assigned[j] == -1 and _similar(fps[i], fps[j]):
                    assigned[j] = cid
                    cluster_of[cid].append(j)

        for members in cluster_of[: self.MAX_CLUSTERS]:
            entries = [uniq[i] for i in members]
            rep = self._best(entries)
            domains = {(urlparse(e.get("url") or "").netloc or "").lower() for e in entries}
            t = source_tier(rep.get("url", ""), rep.get("title", ""), rep.get("text", ""))
            self.clusters.append({
                "cluster_id": f"{self.claim_id}-cl{len(self.clusters)}",
                "representative_url": rep.get("url"),
                "title": rep.get("title", ""),
                "text": rep.get("text", ""),
                "normalized_text": normalize_text(rep.get("text")),
                "source_tier": t["tier"],
                "tier_confidence": t["confidence"],
                "tier_rationale": t["rationale"],
                "domains": sorted(domains),
                "member_count": len(entries),
                "dup_count": len(entries),          # 同簇页面总数（用户口径：dup_count=网页数）
                "copy_count": len(entries) - 1,     # 副本数
                "syndicated": len(domains) > 1,
                "independent_weight": 1.0,
            })

        seen_domains: dict[str, int] = {}
        for cl in self.clusters:
            d = (cl["domains"] or ["?"])[0]
            seen_domains[d] = seen_domains.get(d, 0) + 1
        for cl in self.clusters:
            d = (cl["domains"] or ["?"])[0]
            if seen_domains[d] > 1:
                cl["independent_weight"] = 0.5

    def stats(self) -> dict:
        tiers = {}
        for c in self.clusters:
            tiers[c["source_tier"]] = tiers.get(c["source_tier"], 0) + 1
        n_cand, n_cl = len(self.candidates), len(self.clusters)
        n_dup = sum(c["copy_count"] for c in self.clusters)
        return {
            "claim_id": self.claim_id,
            "candidate_count": n_cand,
            "cluster_count": n_cl,
            "url_dedup_rate": (n_cand - len(set(c.get("url") for c in self.candidates))) / n_cand
            if n_cand else 0.0,
            "content_dedup_collapse": (n_cand - n_cl) / n_cand if n_cand else 0.0,
            "duplicate_clusters": sum(1 for c in self.clusters if c["copy_count"] > 0),
            "avg_members": n_cand / n_cl if n_cl else 0.0,
            "total_dup_count": n_dup,
            "syndicated_clusters": sum(1 for c in self.clusters if c["syndicated"]),
            "independent_clusters": n_cl,
            "independent_weight_sum": sum(c["independent_weight"] for c in self.clusters),
            "source_tiers": tiers,
            "unknown_rate": tiers.get("unknown", 0) / n_cl if n_cl else 0.0,
        }


def claim_element_keys(claim_text: str) -> dict:
    quals = _qualifier_requirements(t2s(claim_text))
    cn = _extract_numbers_corrected(t2s(claim_text))
    nums = [raw for _, _, raw in cn] + re.findall(r"(19|20)\d{2}", t2s(claim_text))
    return {"core": ["subject", "predicate", "object"],
            "qualifiers": quals, "numbers_years": nums}


def build_coverage_structure(claim_text: str, pool: Pool) -> dict:
    keys = claim_element_keys(claim_text)
    matrix = {k: [None] * len(pool.clusters) for k in keys["core"]}
    for q in keys["qualifiers"]:
        matrix[q] = [None] * len(pool.clusters)
    for n in keys["numbers_years"]:
        matrix[n] = [None] * len(pool.clusters)
    return {
        "claim_id": pool.claim_id,
        "elements": {"core": keys["core"], "qualifiers": keys["qualifiers"],
                     "numbers_years": keys["numbers_years"]},
        "clusters": [c["cluster_id"] for c in pool.clusters],
        "matrix": matrix,
        "independent_weight": [c["independent_weight"] for c in pool.clusters],
    }
