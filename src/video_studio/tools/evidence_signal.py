"""V2.1 Stage 7：EvidenceSignal 提取器（B 路线前置验收，隔离实现，未接生产链）。

- ① 信号 schema：单条 Evidence 的多维信号（不输出最终 support_level）。
- ② 提取器：LLM 结构化调用（topic/proposition 分离、否定落点、键集注入）
  + 规则侧确定性信号（claim_type 规则裁决、限定词/数字原文复核、否定辖域审计、词面重叠）。
- 只产信号；Evidence Pool / Coverage Matrix / Claim 聚合不在本阶段实现。

信号字段（EVIDENCE_SIGNAL_SCHEMA）：
  topic_relevance / proposition_relevance / claim_type_compat /
  subject_match / object_match / predicate_match /
  qualifier_match{原文:bool} / numeric_match{原文:bool}（确定性原文复核）/
  llm_qualifier / llm_numbers（LLM 打分，仅审计）/
  contradiction_candidate / contradiction_scope / negation_rule_signal（仅审计）/
  rule_topic_hint / rule_overlap / evidence_quote / fallback_reason
"""

from __future__ import annotations

import hashlib
import json
import re
import time

from ..llm.router import SchemaError, validate_json
from .semantic_judge import (  # 只读复用，不修改
    _claim_profile, _generic_overlap, _matched_core,
    _qualifier_requirements, _scoped_negation)
from .sufficiency_judge import (  # 复用 S6 已验证组件（同模块族，不修改）
    _contrast_construction, _extract_numbers_corrected, _parse_cn_num_corrected,
    rule_claim_type, t2s)

PROMPT_VERSION = "evidence-signal-v1"
MODEL_DEFAULT = "deepseek-chat"
TIER = "F"

SCOPE_ENUM = ["subject", "predicate", "object", "qualifier", "number", "temporal", "context"]

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "topic_relevance": {"type": "boolean"},
        "proposition_relevance": {"type": "boolean"},
        "claim_type": {"type": "string", "enum": ["ASSERTION", "QUESTION", "DEFINITION",
                                                 "RHETORICAL", "NARRATIVE", "CONTRAST"]},
        "subject_match": {"type": "boolean"},
        "object_match": {"type": "boolean"},
        "predicate_match": {"type": "boolean"},
        "contradiction_candidate": {"type": "boolean"},
        "contradiction_scope": {"type": "string", "enum": SCOPE_ENUM},
        "qualifiers": {"type": "object"},
        "numbers_years": {"type": "object"},
        "evidence_quote": {"type": "string"},
    },
    "required": ["topic_relevance", "proposition_relevance", "claim_type",
                 "subject_match", "object_match", "predicate_match",
                 "contradiction_candidate", "contradiction_scope",
                 "qualifiers", "numbers_years", "evidence_quote"],
}

SYSTEM_PROMPT = (
    "你是事实核查系统的证据信号提取模块。给定 Claim 与 Evidence（标题/摘要/正文窗口），"
    "只提取结构化信号并输出 JSON，不要输出任何结论或支持等级。\n\n"
    "字段定义：\n"
    "1. topic_relevance：Evidence 是否与 Claim 处于同一主题域（宽松）。\n"
    "2. proposition_relevance：Evidence 是否针对该命题本身的谓词/对象/限定词层面"
    "展开讨论（严格）。仅同一主题但未涉及该命题 → topic=true, proposition=false。\n"
    "3. claim_type：Claim 句式类型（ASSERTION/QUESTION/DEFINITION/RHETORICAL/NARRATIVE/CONTRAST）。\n"
    "4. subject_match / object_match / predicate_match：Evidence 与 Claim 的主体/对象/谓词"
    "是否一致（同形异义词判 false；讨论同一命题即使结论相反也判 true——本字段不要求极性相同）。\n"
    "5. contradiction_candidate：仅当 Claim 是可验证断言且 Evidence 对同一命题给出相反"
    "结论/数字/年份/判断时为 true；问句/定义句/修辞句/叙事句/对照构式一律 false。\n"
    "6. contradiction_scope：contradiction_candidate=true 时，否定落在哪个要素"
    "（subject/predicate/object/qualifier/number/temporal/context 之一）；"
    "false 时填 context。\n"
    "7. qualifiers / numbers_years：键为下方清单原文，值为 Evidence 是否明确背书（同值同单位）。\n"
    "8. evidence_quote：支撑判断的原文引用（≤80字）。\n\n"
    "只输出 JSON，不要解释。"
)

FEW_SHOT: list[tuple] = []


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def build_prompt(claim_text: str, evidence: dict, qualifier_list: list[str],
                 number_list: list[str], rule_hint: str) -> tuple[str, str]:
    lines = []
    for claim, ev, fields in FEW_SHOT:
        lines.append(f"Claim: {claim}\nEvidence: {ev}\nJSON: {json.dumps(fields, ensure_ascii=False)}\n")
    system = SYSTEM_PROMPT + ("\n\n示例：\n" + "\n".join(lines) if lines else "")
    title = (evidence.get("title") or "")[:200]
    snippet = (evidence.get("snippet") or "")[:300]
    text = (evidence.get("text") or "")[:600]
    user = (f"Claim: {claim_text}\n"
            f"Evidence 标题: {title}\nEvidence 摘要: {snippet}\nEvidence 正文窗口: {text}\n"
            f"Evidence URL: {(evidence.get('url') or '')[:200]}\n"
            f"规则层句式提示: {rule_hint}\n"
            f"限定词清单（逐项 true/false）: {qualifier_list or '[]'}\n"
            f"数字/年份清单（逐项 true/false）: {number_list or '[]'}")
    return system, user


def cache_key(claim_text: str, evidence: dict, model: str = MODEL_DEFAULT) -> str:
    raw = "\x00".join([_norm(claim_text), _norm(evidence.get("title", "")),
                       _norm(evidence.get("snippet", "")),
                       _norm((evidence.get("text") or "")[:600]),
                       PROMPT_VERSION, model])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _extract_json(text: str) -> dict:
    text = (text or "").strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        text = text[start:end + 1]
    data = json.loads(text)
    if not isinstance(data, dict):
        raise SchemaError("LLM 输出顶层应为对象")
    return data


def _qualifier_present(q: str, ev_norm: str) -> bool:
    from .semantic_judge import QUALIFIER_SYN
    forms = QUALIFIER_SYN.get(q, {q}) | {q}
    return any(f in ev_norm for f in forms)


def _num_present(raw: str, ev_norm: str) -> bool:
    if re.fullmatch(r"(19|20)\d{2}", raw):
        return raw in ev_norm
    cn = _extract_numbers_corrected(raw)
    en = _extract_numbers_corrected(ev_norm)
    for cv, cu, _ in cn:
        for evv, eu, _ in en:
            if cu == eu and abs(cv - evv) < 1e-6:
                return True
    return False


def extract_signals(claim_text: str, evidence: dict, router, cache_db=None,
                    l1_cache: dict | None = None) -> dict:
    """② 信号提取：LLM 结构化字段 + 规则侧确定性字段。任何失败回退规则侧信号，不抛出。"""
    key = cache_key(claim_text, evidence)
    claim_norm = t2s(claim_text)
    ev_plain = evidence.get("title", "") + evidence.get("snippet", "") + evidence.get("text", "")
    ev_norm = t2s(ev_plain)
    prof = _claim_profile(claim_norm)
    matched, num_conflict = _matched_core(prof, evidence)
    rule_overlap = len(matched) + _generic_overlap(claim_norm, ev_norm)
    rule_hint_ct = rule_claim_type(claim_text)
    topic_hint = rule_overlap > 0
    quals = _qualifier_requirements(claim_norm)
    cn = _extract_numbers_corrected(claim_norm)
    nums = [raw for _, _, raw in cn] + re.findall(r"(19|20)\d{2}", claim_norm)

    deterministic = {
        "claim_type_compat": rule_hint_ct or "ASSERTION",
        "qualifier_match": {q: _qualifier_present(q, ev_norm) for q in quals},
        "numeric_match": {raw: _num_present(raw, ev_norm) for raw in nums},
        "negation_rule_signal": bool(_scoped_negation(t2s(evidence.get("text", "") or ev_plain),
                                                      matched, prof["feasible"])),
        "rule_topic_hint": topic_hint,
        "rule_overlap": rule_overlap,
        "cache_key": key,
        "model": MODEL_DEFAULT,
        "prompt_version": PROMPT_VERSION,
        "fallback_reason": "",
        "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "latency_ms": 0,
        "cache_hit": False,
    }

    if l1_cache is not None and key in l1_cache:
        return {**deterministic, **l1_cache[key], "cache_hit": True}
    if cache_db is not None:
        row = cache_db.get_llm_judge_row(key)
        if row and row.get("fallback_reason") in ("", None):
            if l1_cache is not None:
                l1_cache[key] = row
            return {**deterministic, "cache_hit": True, "llm_label": row.get("llm_label")}

    client = getattr(router, "client", None)
    tier_cfg = (router.config.get("tiers", {}) or {}).get(TIER, {})
    model = tier_cfg.get("model", MODEL_DEFAULT)

    def fallback(reason: str) -> dict:
        out = {**deterministic,
               "topic_relevance": topic_hint, "proposition_relevance": False,
               "claim_type": rule_hint_ct or "ASSERTION",
               "subject_match": False, "object_match": False, "predicate_match": False,
               "contradiction_candidate": False, "contradiction_scope": "context",
               "llm_qualifier": {}, "llm_numbers": {}, "evidence_quote": "",
               "fallback_reason": reason, "model": model}
        if cache_db is not None:
            cache_db.put_llm_judge_row({**out, "llm_label": "SIGNAL_FALLBACK"})
        if l1_cache is not None:
            l1_cache[key] = {k: v for k, v in out.items() if k not in deterministic}
        return out

    if client is None or not getattr(client, "available", True):
        return fallback("LLM 未配置")

    system, user = build_prompt(claim_text, evidence, quals, nums, rule_hint_ct or "无")
    max_tokens = tier_cfg.get("max_tokens", 512)
    last_error, llm = "", None
    for attempt in (1, 2):
        t0 = time.perf_counter()
        try:
            result = client.complete(model, system, user, max_tokens)
            cost_usd = 0.0
            if hasattr(router, "account_direct_call"):     # 3.x Phase 1.1：直连调用也记账
                cost_usd = router.account_direct_call(model, result, tag="judge:signal")[0]
            data = _extract_json(result.get("text", ""))
            validate_json(data, OUTPUT_SCHEMA)
            llm = data
            deterministic.update({
                "latency_ms": int((time.perf_counter() - t0) * 1000),
                "tokens_in": int(result.get("prompt_tokens", 0) or 0),
                "tokens_out": max(int(result.get("tokens", 0) or 0)
                                  - int(result.get("prompt_tokens", 0) or 0), 0),
                "cost_usd": cost_usd})
            break
        except SchemaError as exc:
            last_error = f"解析/校验失败({attempt}): {exc}"
            continue
        except Exception as exc:
            last_error = f"调用失败({attempt}): {type(exc).__name__}"
            continue
    if llm is None:
        return fallback(last_error or "LLM 失败")

    out = {**deterministic,
           "topic_relevance": bool(llm.get("topic_relevance")),
           "proposition_relevance": bool(llm.get("proposition_relevance")),
           "claim_type": llm.get("claim_type") or "ASSERTION",
           "subject_match": bool(llm.get("subject_match")),
           "object_match": bool(llm.get("object_match")),
           "predicate_match": bool(llm.get("predicate_match")),
           "contradiction_candidate": bool(llm.get("contradiction_candidate")),
           "contradiction_scope": llm.get("contradiction_scope") or "context",
           "llm_qualifier": llm.get("qualifiers") or {},
           "llm_numbers": llm.get("numbers_years") or {},
           "evidence_quote": (llm.get("evidence_quote") or "")[:120],
           "model": model}
    if cache_db is not None:
        cache_db.put_llm_judge_row({**out, "llm_label": "SIGNAL"})
    if l1_cache is not None:
        l1_cache[key] = {k: v for k, v in out.items() if k not in deterministic}
    return out
