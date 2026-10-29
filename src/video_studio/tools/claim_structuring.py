"""V2.1 Stage 8G：Claim Structuring / Research Brief Layer（隔离实现，未接生产链）。

- 只读复用冻结规则侧组件（不改语义）：_claim_profile/_claim_domains/_domain_words/_extract_latin/
  _qualifier_requirements（semantic_judge）、rule_claim_type/t2s/_extract_numbers_corrected（sufficiency_judge）、
  _qualifier_present/_num_present（evidence_signal）、readiness 层（8F）。
- Claim decomposition：claim_type + 实体/领域 + 限定词 + 数字/年份 + 子命题 + 句式 flags（确定性）。
- Research Brief：把 Evidence 映射到 Claim 元素 + source_quality/readiness + 未覆盖缺口，
  输出"创作前研究包"（brief_text 可读）。仅作上游输入，不产出/不改变 truth 状态。
"""

from __future__ import annotations

import re

from .semantic_judge import (_claim_profile, _claim_domains, _domain_words,
                             _extract_latin, _qualifier_requirements)
from .sufficiency_judge import rule_claim_type, t2s, _extract_numbers_corrected
from .evidence_signal import _qualifier_present, _num_present
from .evidence_pool import normalize_text
from .evidence_readiness import completeness, source_quality_profile, balance, readiness

_SUB_SPLIT = re.compile(r"[。；？！]")
_STEP_SPLIT = re.compile(r"(?=第[一二三四五六七八九十\d]+步)")
_COUNTER = re.compile(r"(个|条|只|次|倍|瓦|年|名|家|台)$")
_STEP_ORDINAL = re.compile(r"^第[一二三四五六七八九十\d]+$")
_QUESTION_TAIL_EXTRA = ("是什么", "为什么", "怎么办", "吗", "呢", "？", "?")
_QUESTION_MARKER_EXTRA = ("是否", "能不能", "会不会", "算不算", "是不是", "凭什么")


def _supplement_claim_type(text: str) -> str:
    """补充判定（新层，不改冻结 rule_claim_type）：补 '是什么/为什么' 疑问尾、'谁…' 疑问。"""
    t = text.strip()
    if t.endswith(_QUESTION_TAIL_EXTRA) or any(m in t for m in _QUESTION_MARKER_EXTRA):
        return "QUESTION"
    if t.startswith("谁"):
        return "QUESTION"
    return "ASSERTION"


def split_sub_claims(claim_text: str) -> list[str]:
    """确定性子命题切分：句末切分 + '第X步' + 冒号枚举（'步骤：A、B、C'）。"""
    parts = [p.strip() for p in _SUB_SPLIT.split(claim_text) if p.strip()]
    out: list[str] = []
    for p in parts:
        steps = [s.strip() for s in _STEP_SPLIT.split(p) if s.strip()]
        if len(steps) > 1:
            out.extend(steps)
            continue
        m = re.match(r"^[^：:]{0,40}[：:](.+)$", p)
        if m and "、" in m.group(1) and re.search(r"步骤|包括|分为|包含|如下", p):
            items = [s.strip() for s in re.split(r"[、；;]", m.group(1)) if s.strip()]
            if len(items) > 1:
                out.extend(items)
                continue
        out.append(p)
    return out or [claim_text.strip()]


def decompose_claim(claim_text: str) -> dict:
    """Claim 结构拆解（确定性；语义 S/P/O 由领域/实体近似，不改冻结信号语义）。"""
    norm = t2s(claim_text)
    prof = _claim_profile(norm)
    ct = rule_claim_type(claim_text) or _supplement_claim_type(claim_text)
    dom_words = _domain_words(norm)
    latin = _extract_latin(norm)
    nums = _extract_numbers_corrected(norm)
    years = sorted(set(re.findall(r"(?:19|20)\d{2}", norm)))
    num_raw = [_COUNTER.sub("", raw) for _, _, raw in nums
               if _COUNTER.sub("", raw) not in years]
    quals = sorted(_qualifier_requirements(norm))
    if prof["step_def"]:
        quals = [q for q in quals if not _STEP_ORDINAL.match(q)]
    return {
        "claim_text": claim_text,
        "claim_type": ct,
        "entities": sorted({e.lower() for e in set(dom_words.keys()) | set(latin)}),
        "domains": sorted(_claim_domains(norm)),
        "qualifiers": quals,
        "numbers_years": sorted(set(num_raw) | set(years)),
        "sub_claims": split_sub_claims(claim_text),
        "flags": {"fiction": prof["fiction"], "negation": prof["neg"],
                  "rhetorical": prof["rhetorical"], "question": prof["question"],
                  "step_def": prof["step_def"]},
    }


def _element_coverage(struct: dict, evidence_list: list[dict]) -> dict:
    """Evidence → Claim 元素映射（确定性原文存在性）。返回 元素→覆盖证据条数。"""
    hay = " ".join(normalize_text(e.get("body") or e.get("text") or "") for e in evidence_list)
    cov: dict[str, int] = {}
    for ent in struct["entities"]:
        cov[f"entity:{ent}"] = 1 if normalize_text(ent) in hay else 0
    for q in struct["qualifiers"]:
        cov[f"qualifier:{q}"] = 1 if _qualifier_present(q, hay) else 0
    for n in struct["numbers_years"]:
        cov[f"number:{n}"] = 1 if _num_present(n, hay) else 0
    return cov


def build_research_brief(claim_text: str, evidence_list: list[dict]) -> dict:
    """创作前研究包：Claim 结构 + Evidence 映射 + source_quality/readiness + 缺口 + 可读文本。"""
    struct = decompose_claim(claim_text)
    cov = _element_coverage(struct, evidence_list)
    total_elems = len(cov)
    covered_elems = sum(cov.values())
    gaps = [k for k, v in cov.items() if not v]

    sq = source_quality_profile(evidence_list)
    comp = completeness(claim_text, evidence_list)
    bal = balance(claim_text, evidence_list)
    rd = readiness(claim_text, evidence_list)

    evidence_citations = []
    for e in evidence_list:
        ev_body = e.get("body") or e.get("text") or ""
        evidence_citations.append({
            "url": e.get("url", ""),
            "title": (e.get("title") or "")[:80],
            "source_tier": e.get("source_quality", {}).get("tier") if isinstance(e.get("source_quality"), dict) else None,
            "excerpt": normalize_text(ev_body)[:2000],
        })

    lines = [
        f"【研究简报】{claim_text}",
        f"类型：{struct['claim_type']}",
        f"实体：{'、'.join(struct['entities']) or '（未识别）'}",
        f"限定条件：{'、'.join(struct['qualifiers']) or '（无）'}",
        f"数字/年份：{'、'.join(struct['numbers_years']) or '（无）'}",
        f"证据条数：{len(evidence_list)}；元素覆盖：{covered_elems}/{total_elems}",
        f"来源可靠性：高 {sq['high']} / 中 {sq['medium']} / 低 {sq['low']}",
        f"readiness：{rd['grade']}（score={rd['readiness_score']}，confidence={rd['decision_confidence']}）",
    ]
    if gaps:
        lines.append(f"未覆盖元素：{'、'.join(gaps)}")
    for c in evidence_citations:
        tier = c["source_tier"] or "?"
        lines.append(f"- [{tier}] {c['title']} ({c['url'][:60]})")

    return {
        "structure": struct,
        "element_coverage": cov,
        "covered_elements": covered_elems,
        "total_elements": total_elems,
        "gaps": gaps,
        "source_quality": sq,
        "completeness": comp,
        "balance": bal,
        "readiness": rd,
        "evidence": evidence_citations,
        "brief_text": "\n".join(lines),
    }
