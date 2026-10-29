# -*- coding: utf-8 -*-
"""P7-4：**视觉相关性判定**（`visual-relevance-v1`；确定性、离线、零网络、零 LLM/VLM 调用）。

回答：**这个视觉素材是否真的适合这个 Scene？** —— 且**不得**把"有素材可用"当成"相关"。

四态（machine-readable，写入 POLICY）
------------------------------------
* `RELEVANT`        —— 存在**足够可靠**的正向证据且无明确负向冲突
* `PARTIAL`         —— 只有**部分**正向证据（如仅词面重叠），关键**视觉**条件无法验证
* `IRRELEVANT`      —— 存在**可靠**负向证据（人类判定/否决）证明不符
* `NOT_ASSESSABLE`  —— 缺少必要视觉证据，无法可靠判断（**默认**，禁止臆测）

四层判定（任一层失败即按该层语义收敛）
--------------------------------------
L1 身份/完整性：asset 存在于索引、sha256 一致、decode 有效、身份与索引一致 —— 失败 ⇒ NOT_ASSESSABLE
L2 需求证据：VisualRequirement 当前**可证明**的字段（NOT_DERIVABLE **不等于**不存在，需显式区分）
L3 既有确定性证据：
   · **人类判定证据**（review ledger 的 pair 级 REJECT/ACCEPT、6-G `forbidden_material` 人工否决、
     `material_timeline.human_selection`、H5 人工验收）—— 视为**可靠证据**
   · 词面重叠（requirement token ↔ candidate name/path）—— 仅作 evidence；
     **词面重叠 ≠ 视觉相关性**（`lexical_is_visual_semantics = False`）
L4 视觉判定能力：仓库是否存在可安全复用的视觉判定能力。
   实测：`core/mm_judge.judge_scene` 需要**已存**的三层多模态证据（4b/5a/5d）；
   本阶段不存在此类证据 ⇒ `judge_scene({})` 返回 `UNKNOWN/JUDGE_NO_EVIDENCE`
   ⇒ **视觉判定能力 = NOT_AVAILABLE**（**不伪造 VLM 结果**）。

禁止：文件名/路径/source_url 当作视觉语义；license/provider 当作相关性；主观质量分；
用"素材数量"宣称视觉质量提升。`evidence_strength` 仅作证据强度记录，**不得**用于排名或替代 decision。
"""
from __future__ import annotations

from .asset_candidate import UNKNOWN
from .visual_requirement import canonical, sha256_text

SCHEMA = "visual-relevance-v1"
VERSION = 1

RELEVANT = "RELEVANT"
PARTIAL = "PARTIAL"
IRRELEVANT = "IRRELEVANT"
NOT_ASSESSABLE = "NOT_ASSESSABLE"
DECISIONS = (RELEVANT, PARTIAL, IRRELEVANT, NOT_ASSESSABLE)

#: 固定决策优先级（仅用于 `best_decision` 的确定性排序，**不表示质量排名**）
DECISION_PRECEDENCE = (IRRELEVANT, RELEVANT, PARTIAL, NOT_ASSESSABLE)

#: 判定规则（machine-readable；**先命中先返回**）
DECISION_RULES = [
    {"rule": "R0_L1_IDENTITY", "decision": NOT_ASSESSABLE,
     "when": "L1 身份/完整性失败（不存在/未入索引/sha 不一致/decode 失败/身份不一致）",
     "code": "IDENTITY_OR_INTEGRITY_FAILED"},
    {"rule": "R1_HUMAN_NEGATIVE", "decision": IRRELEVANT,
     "when": "存在 **pair 级人类负向证据**（该 scene×该 asset 被人类 REJECT 或被人工明确否决）",
     "code": "HUMAN_NEGATIVE_EVIDENCE"},
    {"rule": "R2_HUMAN_POSITIVE", "decision": RELEVANT,
     "when": "存在 **pair 级人类正向证据**（人工选材理由 / 人工验收绑定）且无 pair 级负向证据",
     "code": "HUMAN_POSITIVE_EVIDENCE"},
    {"rule": "R3_NEGATIVE_UNVERIFIED", "decision": NOT_ASSESSABLE,
     "when": "requirement 有 avoid_list/concepts_neg，且 candidate 存在**未经验证**的负向命中"
             "（如仅文件名词面命中）——不得静默忽略负向约束，也不得凭文件名判 IRRELEVANT",
     "code": "NEGATIVE_CONSTRAINT_UNVERIFIED"},
    {"rule": "R4_LEXICAL_ONLY", "decision": PARTIAL,
     "when": "仅有词面重叠证据（requirement token ↔ candidate name/path），视觉条件无法验证",
     "code": "LEXICAL_ONLY_PARTIAL"},
    {"rule": "R5_INSUFFICIENT", "decision": NOT_ASSESSABLE,
     "when": "既无人类证据、也无词面证据（或 requirement 视觉字段本身不足）",
     "code": "INSUFFICIENT_EVIDENCE"},
]

EVIDENCE_STRENGTH = {RELEVANT: 1.0, IRRELEVANT: 1.0, PARTIAL: 0.4, NOT_ASSESSABLE: 0.0}

VISUAL_JUDGE_CAPABILITY = {
    "module": "core/mm_judge.py（judge_scene(layers) 纯函数融合三层证据）",
    "available_for_p7_4": False,
    "status": NOT_ASSESSABLE,
    "reason": "该 Judge 融合**已存**的三层多模态证据（4b/5a/5d verdict）；当前不存在面向"
              "'本地 asset × VisualRequirement' 的该类证据 ⇒ 只能返回 UNKNOWN/JUDGE_NO_EVIDENCE",
    "proof": "judge_scene({}) ⇒ verdict=UNKNOWN, reason_code=JUDGE_NO_EVIDENCE, unknown_is_final=True",
    "not_faked": "本阶段**未**调用任何 VLM/外部 API，也未伪造视觉判定结果",
    "what_is_needed_next": [
        "面向（asset 图像, requirement）的多模态证据层（4b/5a/5d 形态）：逐帧/逐图内容判定，"
        "带 evidence_ref 与可复算记录",
        "确定性/可缓存的视觉 judge adapter（同输入同判定；结果落盘 + sha256 绑定）",
        "证据必须可追溯到具体像素帧与模型版本；不得写入 6-G frozen 产物",
    ],
}


def lexical_tokens(text: str) -> list[str]:
    """词面 token（按**非字母数字**切分，≥2 字符，小写去重）——仅用于 L3 evidence，
    不作为视觉语义。切分包含下划线/连字符/点，避免 "Lean_mathlib_x" 被当成单一 token。"""
    import re
    out = []
    for m in re.finditer(r"[A-Za-z0-9]{2,}", text or ""):
        t = m.group(0).lower()
        if t not in out:
            out.append(t)
    return out


def judge_candidate(*, requirement: dict, candidate: dict, index_asset: dict | None,
                    human_pair_evidence: dict, policy: dict | None = None,
                    is_scene_current_asset: bool = False) -> dict:
    """单 (scene, candidate) 判定（纯函数、确定性）。"""
    pol = {**POLICY, **(policy or {})}
    rid = requirement.get("requirement_id")
    sid = requirement.get("scene_id")
    aid = candidate.get("asset_id")
    ev: list[dict] = []
    L1 = {"asset_in_index": index_asset is not None, "sha256_match": None,
          "decode_ok": None, "identity_consistent": None, "status": NOT_ASSESSABLE}
    if index_asset is not None:
        L1["sha256_match"] = (index_asset.get("sha256") == candidate.get("sha256"))
        L1["decode_ok"] = (index_asset.get("decode_status") == "OK")
        L1["identity_consistent"] = (index_asset.get("asset_id") == aid)
        L1["status"] = "OK" if (L1["sha256_match"] and L1["decode_ok"]
                                and L1["identity_consistent"]) else NOT_ASSESSABLE
    # L2 需求证据
    fs = requirement.get("field_status") or {}
    avail = sorted(f for f, m in fs.items() if m.get("status") == "DERIVABLE")
    unavailable = sorted(f for f, m in fs.items() if m.get("status") != "DERIVABLE")
    L2 = {"derivable_fields": avail, "not_derivable_fields": unavailable,
          "visual_fields": [f for f in ("visual_goal", "expected_kind") if f in avail],
          "constraint_fields": [f for f in ("avoid_list", "concepts_neg") if f in avail],
          "status": "OK" if avail else NOT_ASSESSABLE}
    # L3a 人类证据（pair 级）
    neg = human_pair_evidence.get("negative", {}).get((sid, aid))
    pos = human_pair_evidence.get("positive", {}).get((sid, aid))
    # L3b 词面证据（明确标注非视觉）
    req_tokens = set()
    for f in ("queries_en", "concepts_pos"):
        for t in (requirement.get(f) or []):
            req_tokens.update(lexical_tokens(str(t)))
    cand_text = candidate.get("name") or ""
    if not cand_text:
        import pathlib as _pl
        cand_text = _pl.Path(str(candidate.get("path") or "")).name      # **仅文件名**
    cand_tokens = set(lexical_tokens(cand_text))
    overlap = sorted(req_tokens & cand_tokens)
    neg_terms = []
    for f in ("avoid_list", "concepts_neg"):
        for t in (requirement.get(f) or []):
            neg_terms.append(str(t))
    neg_hits = []
    for term in neg_terms:
        tt = set(lexical_tokens(term))
        if tt and tt & cand_tokens:
            neg_hits.append({"term": term, "hit_kind": "filename_lexical", "verified": False,
                             "why": "文件名/路径词面命中**不等于**画面包含该元素"})
    L3 = {"human_negative_evidence": neg, "human_positive_evidence": pos,
          "lexical_overlap_tokens": overlap,
          "lexical_is_visual_semantics": False,
          "unverified_negative_hits": neg_hits,
          "status": "OK"}
    # L4 视觉判定能力
    L4 = dict(VISUAL_JUDGE_CAPABILITY)
    # ---- 决策（先命中先返回）----
    decision, code, rule = NOT_ASSESSABLE, "INSUFFICIENT_EVIDENCE", "R5_INSUFFICIENT"
    if L1["status"] != "OK":
        decision, code, rule = NOT_ASSESSABLE, "IDENTITY_OR_INTEGRITY_FAILED", "R0_L1_IDENTITY"
        ev.append({"kind": "identity_failure", "detail": L1})
    elif neg:
        decision, code, rule = IRRELEVANT, "HUMAN_NEGATIVE_EVIDENCE", "R1_HUMAN_NEGATIVE"
        ev.append({"kind": "human_negative", "detail": neg})
    elif pos:
        decision, code, rule = RELEVANT, "HUMAN_POSITIVE_EVIDENCE", "R2_HUMAN_POSITIVE"
        ev.append({"kind": "human_positive", "detail": pos})
    elif neg_hits:
        decision, code, rule = (NOT_ASSESSABLE, "NEGATIVE_CONSTRAINT_UNVERIFIED",
                                "R3_NEGATIVE_UNVERIFIED")
        ev.append({"kind": "negative_unverified", "detail": neg_hits})
    elif overlap:
        decision, code, rule = PARTIAL, "LEXICAL_ONLY_PARTIAL", "R4_LEXICAL_ONLY"
        ev.append({"kind": "lexical_overlap", "tokens": overlap,
                   "caveat": "词面重叠 ≠ 视觉相关性（仅 evidence）"})
    else:
        decision, code, rule = NOT_ASSESSABLE, "INSUFFICIENT_EVIDENCE", "R5_INSUFFICIENT"
        ev.append({"kind": "no_evidence",
                   "detail": {"requirement_derivable": avail,
                              "candidate_tokens": len(cand_tokens)}})
    matched = sorted((["visual_goal"] if "visual_goal" in avail else [])
                     + (["expected_kind"] if "expected_kind" in avail else [])
                     + (["lexical:{}".format(t) for t in overlap[:6]]))
    unmatched = sorted(set(unavailable))
    body = {
        "schema": SCHEMA, "scene_id": sid, "requirement_id": rid, "asset_id": aid,
        "is_scene_current_asset": bool(is_scene_current_asset),
        "decision": decision, "decision_code": code, "decision_rule": rule,
        "evidence": ev, "matched_requirement_fields": matched,
        "unmatched_requirement_fields": unmatched, "negative_conflicts": neg_hits,
        "visual_evidence": {"status": L4["status"], "available": L4["available_for_p7_4"],
                            "reason": L4["reason"],
                            "human_recorded_evidence_used": bool(neg or pos)},
        "confidence": ("HUMAN_RECORDED" if (neg or pos) else
                       "LEXICAL_ONLY" if overlap else "NONE"),
        "evidence_strength": EVIDENCE_STRENGTH[decision],
        "evidence_strength_note": "仅证据强度记录；**不是**质量分，不得用于排名",
        "judge_method": pol["judge_method"],
        "assessability": ("ASSESSABLE" if decision in (RELEVANT, IRRELEVANT, PARTIAL)
                          else NOT_ASSESSABLE),
        "layers": {"L1_identity_integrity": L1, "L2_requirement_evidence": L2,
                   "L3_deterministic_evidence": L3, "L4_visual_judge": L4},
        "provenance": {"policy": pol["policy_id"], "policy_version": pol["policy_version"],
                       "human_evidence_sources": sorted({e.get("source") for e in
                                                          ([neg] if neg else []) + ([pos] if pos else [])}),
                       "index_artifact_hash": pol.get("index_artifact_hash"),
                       "requirements_artifact_hash": pol.get("requirements_artifact_hash")},
    }
    dh = sha256_text(canonical(body))
    body["relevance_id"] = "vr-" + dh[:16]
    body["deterministic_hash"] = dh
    return body


POLICY = {
    "policy_id": "visual-relevance-policy-v1",
    "policy_version": 1,
    "judge_method": "deterministic-offline（L1 身份/L2 需求证据/L3 人类可靠证据+词面 evidence/L4 视觉能力探测；"
                    "零网络、零 LLM/VLM 调用）",
    "decisions": list(DECISIONS),
    "precedence": list(DECISION_PRECEDENCE),
    "rules": DECISION_RULES,
    "lexical_is_visual_semantics": False,
    "forbidden_as_relevance_evidence": ["file name", "path", "source_url", "license",
                                        "provider", "asset count"],
    "score_usage": "evidence_strength 仅作证据强度；不得输出总体质量排名",
    "default_when_insufficient": NOT_ASSESSABLE,
}


def validate_result(r: dict) -> list[str]:
    errs = []
    for f in ("relevance_id", "requirement_id", "scene_id", "asset_id", "decision", "evidence",
              "matched_requirement_fields", "unmatched_requirement_fields", "negative_conflicts",
              "visual_evidence", "confidence", "judge_method", "assessability", "provenance",
              "deterministic_hash"):
        if f not in r:
            errs.append("缺少字段 {}".format(f))
    if r.get("schema") != SCHEMA:
        errs.append("schema 必须为 {}".format(SCHEMA))
    if r.get("decision") not in DECISIONS:
        errs.append("decision 非法：{!r}".format(r.get("decision")))
    body = {k: v for k, v in r.items() if k not in ("deterministic_hash", "relevance_id")}
    if r.get("deterministic_hash") != sha256_text(canonical(body)):
        errs.append("deterministic_hash 不一致")
    if r.get("relevance_id") != "vr-" + sha256_text(canonical(body))[:16]:
        errs.append("relevance_id 与 body 不一致")
    if r.get("confidence") == "LEXICAL_ONLY" and r.get("decision") == RELEVANT:
        errs.append("禁止：仅词面证据即判 RELEVANT")
    return errs


def build_artifact(*, scene_results: list[dict], policy: dict, sources: list[dict],
                   aggregate: dict, requirements_snapshot: dict,
                   index_snapshot: dict) -> dict:
    art = {"schema": SCHEMA, "version": VERSION,
           "generation_method": policy["judge_method"],
           "policy": policy, "sources": sources,
           "requirements_snapshot": requirements_snapshot,
           "asset_index_snapshot": index_snapshot,
           "visual_judge_capability": VISUAL_JUDGE_CAPABILITY,
           "scene_results": scene_results, "aggregate": aggregate,
           "determinism_note": "无随机数/时间戳/UUID；canonical JSON（sort_keys+compact+utf-8）",
           "dq_note": "P7-4 **不修改 DQ-2 或任何 DQ 阈值**；仅新增相关性判定证据",
           "artifact_hash": ""}
    art["artifact_hash"] = artifact_hash(art)
    return art


def artifact_body(art: dict) -> dict:
    return {k: v for k, v in art.items() if k != "artifact_hash"}


def artifact_hash(art: dict) -> str:
    return sha256_text(canonical(artifact_body(art)))


def _has_time_or_uuid(obj, depth: int = 0) -> list[str]:
    """递归检测**键名**形式的 timestamp/UUID（不误伤说明文本）。"""
    import re
    bad_keys = {"created", "created_at", "created_utc", "generated_at", "timestamp", "uuid",
                "random_seed", "nonce"}
    uuid_re = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
    hits = []
    if depth > 12:
        return hits
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).lower() in bad_keys:
                hits.append("key:{}".format(k))
            hits += _has_time_or_uuid(v, depth + 1)
    elif isinstance(obj, list):
        for v in obj:
            hits += _has_time_or_uuid(v, depth + 1)
    elif isinstance(obj, str) and uuid_re.match(obj.strip()):
        hits.append("value:uuid")
    return hits


def validate_artifact(art: dict) -> list[str]:
    errs = []
    if art.get("schema") != SCHEMA:
        errs.append("schema 非法")
    if art.get("artifact_hash") != artifact_hash(art):
        errs.append("artifact_hash 不一致")
    for s in art.get("scene_results") or []:
        for c in s.get("candidate_results") or []:
            for e in validate_result(c):
                errs.append("{}: {}".format(c.get("relevance_id"), e))
        if s.get("best_decision") not in DECISIONS + (None,):
            errs.append("best_decision 非法")
    tu = _has_time_or_uuid(art)
    if tu:
        errs.append("含时间戳/UUID 键或值（破坏确定性）：{}".format(sorted(set(tu))[:4]))
    return errs
