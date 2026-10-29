"""V2.1 Stage 8F：Evidence readiness 决策准备层（隔离实现，未接生产链）。

- 只做评估/统计，不产出最终 support 状态（Aggregation 四结构冻结，本层不裁决）。
- 只读复用冻结规则侧组件（不改语义）：_claim_profile/_matched_core/_scoped_negation（semantic_judge）、
  _qualifier_present/_num_present（evidence_signal）、claim_element_keys/normalize_text（evidence_pool）、
  source_quality（evidence_retrieval 8E）。
- 四维 readiness：completeness（确定性元素覆盖）× source_quality（可靠性分层）×
  balance（支持/矛盾方向）× independence（独立来源数）。
"""

from __future__ import annotations

from collections import Counter

from .evidence_pool import claim_element_keys, normalize_text
from .evidence_signal import _qualifier_present, _num_present          # 只读
from .evidence_retrieval import source_quality                        # 8E
from .search_provider import _claim_tokens
from .semantic_judge import _claim_profile, _matched_core, _scoped_negation  # 只读
from .sufficiency_judge import t2s
from .claim_aggregation import _numeric_conflict_class                # 只读（8B.1 冻结）


def _as_evidence(e: dict) -> dict:
    """8E/池证据统一到 semantic_judge 期望的 {title,snippet,text,url} 形状。"""
    return {"url": e.get("url", ""), "title": e.get("title", ""),
            "snippet": e.get("snippet", ""), "text": e.get("body") or e.get("text") or ""}


def completeness(claim_text: str, evidence_list: list[dict]) -> dict:
    """确定性元素覆盖：限定词 + 数字/年份 + 内容 token 覆盖。语义 S/P/O 覆盖归冻结聚合层。"""
    keys = claim_element_keys(claim_text)
    hay = " ".join(normalize_text(_as_evidence(e)["text"]) for e in evidence_list)
    quals = keys["qualifiers"]
    nums = keys["numbers_years"]
    qcov = sum(1 for q in quals if _qualifier_present(q, hay))
    ncov = sum(1 for n in nums if _num_present(n, hay))
    tokens = _claim_tokens({"text": claim_text})
    tcv = sum(1 for t in tokens if t in hay) / len(tokens) if tokens else 0.0
    score = round((qcov / len(quals) if quals else 1.0) * 0.4 +
                  (ncov / len(nums) if nums else 1.0) * 0.4 + tcv * 0.2, 3)
    return {"qualifier_covered": qcov, "qualifier_total": len(quals),
            "number_covered": ncov, "number_total": len(nums),
            "token_coverage": round(tcv, 3), "completeness_score": score}


def source_quality_profile(evidence_list: list[dict]) -> dict:
    """来源可靠性分布（8E source_quality）与加权质量分。"""
    if not evidence_list:
        return {"n": 0, "bands": {}, "high": 0, "medium": 0, "low": 0, "quality_score": 0.0}
    sqs = [source_quality(e.get("url", ""), e.get("title", ""), _as_evidence(e)["text"])
           for e in evidence_list]
    bands = Counter(s["band"] for s in sqs)
    high = sum(1 for s in sqs if s["band"] == "high")
    med = sum(1 for s in sqs if s["band"] == "medium")
    low = len(sqs) - high - med
    return {"n": len(evidence_list), "bands": dict(bands),
            "high": high, "medium": med, "low": low,
            "quality_score": round((high * 1.0 + med * 0.6 + low * 0.2) / len(sqs), 3)}


def _direction(claim_text: str, e: dict) -> tuple[str, bool]:
    """规则侧证据方向（确定性；语义方向判定归冻结信号层）。

    返回 (direction, negation_hit, numeric_rule_conflict)。
    direction 仅区分 supporting（命中核心词）/ context（未命中）——可词面复核的可靠方向；
    否定命中（_scoped_negation 命中核心词 ±60 内）与数字规则冲突（_numeric_conflict_class=="A"，
    同单位异值、对象歧义未消解）均只作审计信号，不据此判方向——与冻结 EvidenceSignal 将
    negation_rule_signal 仅作审计、最终矛盾由 LLM signal+聚合裁决的口径一致。
    """
    ev = _as_evidence(e)
    prof = _claim_profile(t2s(claim_text))
    matched, _ = _matched_core(prof, ev)
    body = t2s(ev["text"])
    neg = _scoped_negation(body, matched, prof.get("feasible", False))
    num_a = _numeric_conflict_class(claim_text, body) == "A"
    if matched:
        return "supporting", neg, num_a
    return "context", neg, num_a


def balance(claim_text: str, evidence_list: list[dict]) -> dict:
    """证据方向平衡统计：supporting（核心词命中）/ context 计数 + 否定/数字规则冲突审计。"""
    dirs: Counter = Counter()
    n_neg = 0
    n_num_a = 0
    for e in evidence_list:
        d, neg, num_a = _direction(claim_text, e)
        dirs[d] += 1
        n_neg += int(neg)
        n_num_a += int(num_a)
    n = len(evidence_list)
    return {"n": n, "supporting": dirs["supporting"], "context": dirs["context"],
            "negation_rule_hits": n_neg, "numeric_rule_conflicts": n_num_a,
            "support_balance": round(dirs["supporting"] / n, 3) if n else 0.0,
            "context_balance": round(dirs["context"] / n, 3) if n else 0.0}


def readiness(claim_text: str, evidence_list: list[dict]) -> dict:
    """Evidence readiness 四维评估 + 决策准备级置信度（非聚合状态）。"""
    comp = completeness(claim_text, evidence_list)
    sq = source_quality_profile(evidence_list)
    bal = balance(claim_text, evidence_list)
    n = len(evidence_list)
    independence = len({(e.get("url") or "").split("/")[2] for e in evidence_list if e.get("url")})

    score = round(0.4 * comp["completeness_score"] + 0.35 * sq["quality_score"] +
                  0.15 * bal["support_balance"] + 0.10 * (min(independence, 3) / 3), 3)

    if comp["completeness_score"] >= 0.6 and bal["supporting"] >= 1 and sq["quality_score"] >= 0.5:
        grade = "ready"
    elif bal["supporting"] >= 1 or comp["completeness_score"] >= 0.3:
        grade = "partial"
    else:
        grade = "insufficient"

    if grade == "ready" and sq["high"] >= 1:
        confidence = "high"
    elif grade in ("ready", "partial") and sq["high"] + sq["medium"] >= 1:
        confidence = "medium"
    else:
        confidence = "low"

    return {"n_evidence": n, "independent_sources": independence,
            "completeness": comp, "source_quality": sq, "balance": bal,
            "readiness_score": score, "grade": grade, "decision_confidence": confidence}


def readiness_summary(rows: list[dict]) -> dict:
    """跨 Claim 的 readiness 汇总（分布 + 高低质量对置信度的影响）。"""
    grades = Counter(r["grade"] for r in rows)
    confs = Counter(r["decision_confidence"] for r in rows)
    scores = [r["readiness_score"] for r in rows]
    n = len(rows)

    # 高低质量对 decision_confidence 的影响
    hi = [r for r in rows if r["source_quality"]["high"] > 0]
    lo = [r for r in rows if r["source_quality"]["high"] == 0]
    def conf_frac(sub):
        if not sub:
            return {}
        c = Counter(r["decision_confidence"] for r in sub)
        return {k: round(v / len(sub), 3) for k, v in c.items()}

    # balance 统计（supporting/context 为可靠方向；否定/数字规则冲突为审计信号，可靠矛盾归冻结信号+聚合）
    support_dir_total = sum(r["balance"]["supporting"] for r in rows)
    context_dir_total = sum(r["balance"]["context"] for r in rows)
    neg_rule_total = sum(r["balance"]["negation_rule_hits"] for r in rows)
    num_rule_total = sum(r["balance"]["numeric_rule_conflicts"] for r in rows)

    return {
        "n_claims": n,
        "grade_dist": dict(grades),
        "confidence_dist": dict(confs),
        "avg_readiness_score": round(sum(scores) / n, 3) if n else 0.0,
        "high_quality_claims": len(hi), "low_quality_claims": len(lo),
        "high_quality_confidence": conf_frac(hi),
        "low_quality_confidence": conf_frac(lo),
        "avg_score_high": round(sum(r["readiness_score"] for r in hi) / len(hi), 3) if hi else 0.0,
        "avg_score_low": round(sum(r["readiness_score"] for r in lo) / len(lo), 3) if lo else 0.0,
        "balance": {
            "total_supporting": support_dir_total,
            "total_context": context_dir_total,
            "total_negation_rule_hits": neg_rule_total,
            "total_numeric_rule_conflicts": num_rule_total,
        },
    }
