"""V2.1 Stage 8B.1：Claim-level Coverage / Aggregation（四项结构修复；研究态，不接生产）。

① 状态边界重定义：IRRELEVANT / CONTEXT_ONLY(非断言) / NO_SUFFICIENT_EVIDENCE /
   CONTRADICTS(仅精确矛盾或谓词级否定) / PARTIAL / DIRECT(anchor+互补证据)。
② 数字冲突消解 A–H：仅"同单位、同对象、双精确且不可能同时成立"→CONTRADICTS；
   近似/取整→要素冲突(PARTIAL)；时间不同→时间冲突；口径不同→未解决冲突候选。
③ temporal/qualifier 冲突：scope=temporal/qualifier 一律入冲突审计，绝不自动 CONTRADICTS；
   限定词只认原文/同义形存在性，禁止"新闻较新=支持目前"。
④ anchor + complementary：DIRECT = 锚点(S+P+O 单簇、来源≥媒体级) + 限定词/数字由
   锚点∪命题相关独立簇并集全覆盖 + 独立性(一手锚点或权重≥2) + 无关键要素冲突。
无多数票；无样本特例；不改任何既有模块语义。
"""

from __future__ import annotations

import re

from .sufficiency_judge import rule_claim_type, t2s
from .semantic_judge import QUALIFIER_SYN
from .evidence_pool import claim_element_keys, normalize_text

AGG_STATES = ("DIRECT_SUPPORT", "PARTIAL_SUPPORT", "CONTEXT_ONLY", "IRRELEVANT",
              "CONTRADICTS", "NO_SUFFICIENT_EVIDENCE")
PRIMARY_TIERS = {"official", "paper_publisher"}
QUALITY_FLOOR = {"official", "paper_publisher", "academic",
                 "mainstream_media", "professional_media"}

_RHET2 = re.compile(r"是[^。；]{0,40}[，,]?还是")
_SINGLE_UNIT = re.compile(r"^[十百千万亿]$")
_APPROX = ("约", "大约", "左右", "上下", "按", "近", "数", "若干", "余", "大概")


def local_claim_type(claim_text: str) -> str:
    ct = rule_claim_type(claim_text)
    if ct is None and _RHET2.search(claim_text):
        return "RHETORICAL"
    return ct or "ASSERTION"


def _claim_nums(claim_text: str) -> list[str]:
    from .sufficiency_judge import _extract_numbers_corrected
    out = []
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(万亿|亿|万|千|百)?", claim_text):
        out.append(m.group(0))
    for _v, _u, raw in _extract_numbers_corrected(claim_text):
        body = re.sub(r"(个|条|例|次|年|瓦|倍)$", "", raw)
        if _SINGLE_UNIT.match(body):
            continue
        if raw not in out:
            out.append(raw)
    out += re.findall(r"(?:19|20)\d{2}", claim_text)
    return out


def _num_approx(raw: str, text: str) -> bool:
    """该数字原文附近是否带近似标记。"""
    idx = text.find(raw)
    if idx < 0:
        return False
    window = text[max(0, idx - 4): idx + len(raw) + 4]
    return any(m in window for m in _APPROX)


def _numeric_conflict_class(claim_text: str, ev_text: str) -> str:
    """② 数字冲突消解：返回 A/C/E/G/H 之一（A=精确矛盾）。"""
    from .sufficiency_judge import _extract_numbers_corrected
    cn = _extract_numbers_corrected(t2s(claim_text))
    en = _extract_numbers_corrected(t2s(ev_text))
    for cv, cu, craw in cn:
        if not cu:
            continue
        for evv, eu, _ in en:
            if eu != cu:
                continue
            if abs(cv - evv) < 1e-6:
                return "G"                       # 单位换算等价 → 无冲突
            if _num_approx(craw, claim_text):
                return "C"                       # Claim 近似 → 非精确矛盾
            ev_approx = any(m in t2s(ev_text) for m in _APPROX)
            if ev_approx:
                return "C"                       # Evidence 近似 → 非精确矛盾
            return "A"                           # 双精确同单位异值 → 精确矛盾
    c_years = set(re.findall(r"(?:19|20)\d{2}", claim_text))
    e_years = set(re.findall(r"(?:19|20)\d{2}", ev_text))
    if c_years and e_years and c_years != e_years:
        return "E"                               # 时间不同
    return "H"                                   # 未解决


def aggregate_claim(claim_text: str, pool, signals: dict) -> dict:
    rule_ct = local_claim_type(claim_text)
    keys = claim_element_keys(claim_text)
    quals = keys["qualifiers"]
    nums = _claim_nums(claim_text)

    relevant, topic_only = [], []
    for cl in pool.clusters:
        sig = dict(signals.get(cl["cluster_id"], {}))
        if not sig:
            sig = {"topic_relevance": False, "proposition_relevance": False,
                   "subject_match": False, "object_match": False, "predicate_match": False,
                   "contradiction_candidate": False, "contradiction_scope": "context",
                   "qualifier_match": {}, "numeric_match": {}, "fallback_reason": "no signal"}
        sig["cluster"] = cl
        (relevant if sig.get("proposition_relevance") else topic_only).append(sig)

    rows = ["subject", "predicate", "object"] + list(quals) + list(nums)
    matrix = {cl["cluster_id"]: {r: "not mentioned" for r in rows} for cl in pool.clusters}
    for s in relevant:
        cl = s["cluster"]
        cid = cl["cluster_id"]
        matrix[cid]["subject"] = "support" if s.get("subject_match") else "not mentioned"
        matrix[cid]["predicate"] = "support" if s.get("predicate_match") else "not mentioned"
        matrix[cid]["object"] = "support" if s.get("object_match") else "not mentioned"
        for q in quals:
            if s.get("qualifier_match", {}).get(q):
                matrix[cid][q] = "support"
        for n in nums:
            if s.get("numeric_match", {}).get(n):
                matrix[cid][n] = "support"

    covered = {r: any(matrix[cl["cluster_id"]][r] == "support"
                      for cl in pool.clusters if matrix.get(cl["cluster_id"]))
               for r in rows}
    contributors = {r: [cl["cluster_id"] for cl in pool.clusters
                        if matrix.get(cl["cluster_id"], {}).get(r) == "support"]
                    for r in rows}

    # ---------------- CONTRADICTS 独立流水线（消解后） ----------------
    contra_records, conflict_records = [], []
    for s in relevant:
        cl = s["cluster"]
        if not s.get("contradiction_candidate"):
            continue
        scope = s.get("contradiction_scope") or "context"
        rec = {"cluster_id": cl["cluster_id"], "url": cl.get("representative_url"),
               "scope": scope, "source_tier": cl.get("source_tier"),
               "tier_confidence": cl.get("tier_confidence"),
               "independence_weight": cl.get("independent_weight", 1.0),
               "claim_type": rule_ct, "evidence_quote": (s.get("evidence_quote") or "")[:80]}
        if rule_ct != "ASSERTION":
            conflict_records.append({**rec, "resolution": "非断言句式，不构成反驳"})
            continue
        if scope in ("subject", "predicate", "object"):
            contra_records.append({**rec, "resolution": "谓词级真实否定"})
        elif scope in ("number",):
            cls = _numeric_conflict_class(claim_text, cl.get("text", ""))
            if cls == "A":
                contra_records.append({**rec, "resolution": "数字精确矛盾(A)"})
            else:
                conflict_records.append({**rec, "resolution": f"数字冲突消解({cls})，非反驳"})
        else:
            conflict_records.append({**rec, "resolution": f"scope={scope}，非精确否定"})

    # ---------------- anchor + complementary ----------------
    anchors = [s for s in relevant
               if s.get("subject_match") and s.get("predicate_match") and s.get("object_match")
               and s["cluster"].get("source_tier") in QUALITY_FLOOR]
    anchor_ids = {s["cluster"]["cluster_id"] for s in anchors}
    union_clusters = set(anchor_ids)
    for r in rows:
        for cid in contributors.get(r, []):
            union_clusters.add(cid)
    union_weight = sum(cl["independent_weight"] for cl in pool.clusters
                       if cl["cluster_id"] in union_clusters)
    primary_anchor = any(s["cluster"].get("source_tier") in PRIMARY_TIERS for s in anchors)
    independence_ok = primary_anchor or union_weight >= 2.0

    conflict_keys = set()
    for s in relevant:
        cl = s["cluster"]
        if s.get("contradiction_candidate"):
            scope = s.get("contradiction_scope") or "context"
            if scope == "number":
                cls = _numeric_conflict_class(claim_text, cl.get("text", ""))
                if cls != "A":
                    for n in nums:
                        if not s.get("numeric_match", {}).get(n):
                            conflict_keys.add(f"numeric:{n}")
            elif scope in ("temporal", "qualifier"):
                conflict_keys.add(f"scope:{scope}")

    # ---------------- 决策 ----------------
    reasons: list[str] = []
    if not pool.clusters or not any(s.get("topic_relevance") for s in relevant + topic_only):
        state = "IRRELEVANT"
    elif rule_ct != "ASSERTION":
        state = "CONTEXT_ONLY"
    elif not relevant:
        state = "NO_SUFFICIENT_EVIDENCE"
        reasons.append("proposition evidence = 0")
    elif contra_records:
        state = "CONTRADICTS"
    else:
        all_quals = all(covered[q] for q in quals)
        all_nums = all(covered[n] for n in nums)
        core = all(covered[r] for r in ("subject", "predicate", "object"))
        conflicts_on_key = conflict_keys
        if anchors and all_quals and all_nums and core and independence_ok and not conflicts_on_key:
            state = "DIRECT_SUPPORT"
        elif core or anchors:
            state = "PARTIAL_SUPPORT"
            if not all_quals:
                reasons.append("qualifier 未覆盖")
            if not all_nums:
                reasons.append("numeric/year 未覆盖")
            if conflicts_on_key:
                reasons.append(f"要素冲突: {sorted(conflicts_on_key)}")
            if anchors and not independence_ok:
                reasons.append("独立来源不足")
            if not anchors:
                reasons.append("anchor 不存在")
        else:
            state = "NO_SUFFICIENT_EVIDENCE"
            reasons.append("无核心要素支持且无锚点")

    return {
        "claim_id": pool.claim_id,
        "rule_claim_type": rule_ct,
        "state": state,
        "reasons": reasons,
        "relevant_clusters": len(relevant),
        "topic_only_clusters": len(topic_only),
        "anchor_count": len(anchors),
        "primary_anchor": primary_anchor,
        "union_weight": union_weight,
        "independence_ok": independence_ok,
        "covered_elements": {r: covered[r] for r in rows},
        "uncovered": [r for r in rows if not covered[r]],
        "complementary_used": sorted(union_clusters - anchor_ids),
        "coverage_matrix": matrix,
        "contradiction_records": contra_records,
        "conflict_records": conflict_records,
        "conflict_keys": sorted(conflict_keys),
        "numeric_conflict_class": {cl["cluster_id"]: _numeric_conflict_class(claim_text, cl.get("text", ""))
                                   for s in relevant for cl in [s["cluster"]] if s.get("contradiction_candidate")},
        "duplicate_impact": {"duplicate_clusters": pool.stats()["duplicate_clusters"],
                             "syndicated": pool.stats()["syndicated_clusters"]},
    }
