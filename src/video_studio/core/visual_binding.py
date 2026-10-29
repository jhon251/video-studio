# -*- coding: utf-8 -*-
"""P7-6：**通用视觉绑定 + 覆盖闭环**（`visual-binding-proposal-v1`；确定性、离线、零执行）。

架构边界（本阶段最重要）
----------------------
`BindingProposal` **≠** `Execution`。P7-6 只产出 proposal / coverage / working timeline；
**不得**修改 material timeline、不得替换素材、不得 rebuild/render、不得写 execution ledger 或
proposal register、不得改动 6-G frozen 产物。

判定方式：**门禁 + 固定 policy**，不是"打分排序取第一"
--------------------------------------------------
    Integrity → License → Relevance → Diversity/Reuse → Binding Eligibility → Proposal
任一门禁不通过 ⇒ `NOT_BINDABLE`（不得强行选择）。
`RELEVANT ≠ BINDABLE`：相关也可能因许可/完整性/溯源/reuse policy 而不合格。

覆盖闭环（四类，**禁止把 NOT_ASSESSABLE 归入 UNSUPPORTED**）
---------------------------------------------------------
* `COVERED`        存在 BINDABLE candidate
* `HITL_REQUIRED`  有候选，但相关性/治理需人工确认（**未**被证明不适合）
* `UNSUPPORTED`    **全部**候选均被可靠证明不适合（IRRELEVANT / 门禁 DENY）
* `NOT_ASSESSABLE` 没有候选，或需求本身缺必要证据通道 ⇒ 无法判断

优先级纪律：**relevance > semantic coverage > diversity > quantity**。
不得为了多样性把 RELEVANT 换成 NOT_ASSESSABLE（P7-3 已证明身份多样性 ≠ 语义覆盖）。
"""
from __future__ import annotations

from .asset_candidate import UNKNOWN
from .visual_requirement import canonical, sha256_text

SCHEMA = "visual-binding-proposal-v1"
COVERAGE_SCHEMA = "visual-coverage-report-v1"
WORKING_TIMELINE_SCHEMA = "p7-working-timeline-v1"
VERSION = 1

NOT_ASSESSABLE = "NOT_ASSESSABLE"
NOT_BINDABLE = "NOT_BINDABLE"
BINDABLE = "BINDABLE"
BOUND = "BOUND"
CANDIDATE_STATES = ("RELEVANT", "PARTIAL", "IRRELEVANT", NOT_ASSESSABLE, NOT_BINDABLE, BINDABLE,
                    BOUND)

KEEP, REPLACE, ADD, NO_BINDING, HITL_REQUIRED = ("KEEP", "REPLACE", "ADD", "NO_BINDING",
                                                "HITL_REQUIRED")
ACTIONS = (KEEP, REPLACE, ADD, NO_BINDING, HITL_REQUIRED)
COVERED, UNSUPPORTED = "COVERED", "UNSUPPORTED"
COVERAGE_STATES = (COVERED, HITL_REQUIRED, UNSUPPORTED, NOT_ASSESSABLE)

#: 门禁规格（machine-readable：为什么 / 输入 / 不通过时的状态 / 依据）
GATE_SPEC = {
    "integrity": {
        "why": "不可解码/身份不一致的素材绝不进入绑定", "inputs": ["P7-2 asset_index"],
        "pass_when": "asset 在索引内 ∧ sha256 一致 ∧ decode=OK ∧ asset_id 身份一致",
        "fail_state": NOT_BINDABLE, "fail_code": "INTEGRITY_FAILED",
        "provenance": "P7-2 候选契约（read-only，不重算）"},
    "license": {
        "why": "许可治理是硬门槛", "inputs": ["P7-2 candidate.license/license_class",
                                              "core.materials（既有语义，未修改）"],
        "pass_when": "PUBLIC_DOMAIN/FREE_ATTRIBUTION ⇒ ALLOW；门禁不适用（本地自备）⇒ 视为通过（记录依据）；"
                     "UNKNOWN ⇒ HITL_REQUIRED；RESTRICTED ⇒ DENY",
        "fail_state": NOT_BINDABLE, "fail_code": "LICENSE_DENIED",
        "hitl_state": HITL_REQUIRED, "hitl_code": "LICENSE_UNKNOWN_HITL",
        "provenance": "core.materials.classify_license / license_block_reason（既有语义，**未修改**）"},
    "relevance": {
        "why": "相关性是首要目标序（relevance > semantic coverage > diversity > quantity）",
        "inputs": ["P7-4 visual_relevance"],
        "pass_when": "RELEVANT ⇒ 可进入 BINDABLE；PARTIAL ⇒ 默认不得自动绑定（HITL）；"
                     "NOT_ASSESSABLE ⇒ 默认不得自动绑定（HITL）；IRRELEVANT ⇒ DENY",
        "fail_state": NOT_BINDABLE, "fail_code": "RELEVANCE_DENIED",
        "hitl_state": HITL_REQUIRED, "hitl_codes": ["RELEVANCE_PARTIAL_HITL",
                                                    "RELEVANCE_NOT_ASSESSABLE_HITL"],
        "provenance": "P7-4（read-only；不得把 PARTIAL/NA 升级为 RELEVANT）"},
    "reuse": {
        "why": "复用/多样性治理（P7-3 实测；不得修改既有 DQ-2）",
        "inputs": ["P7-3 asset_diversity", "P7-2 source-family（source-family-v1）"],
        "pass_when": "未使用过 ⇒ PASS_PREFERRED；已使用 ⇒ PASS_WITH_NOTE（记录复用次数/来源家族）；"
                     "仅当项目多样性低于**既有冻结**阈值时，对会加剧集中的候选升级为 HITL",
        "fail_state": None, "fail_code": None,
        "thresholds": {"max_reuse": UNKNOWN, "threshold_status": NOT_ASSESSABLE,
                       "why": "P7-6 无既有依据设定新的绑定复用阈值 ⇒ **不拍脑袋设数字**；"
                              "因此复用不构成自动拒绝理由，只记录并（在既有阈值被违反时）升级 HITL"},
        "provenance": "P7-3 度量 + 6-G 冻结重算阈值（数据来源）"},
}

#: 绑定策略（machine-readable；新阈值均标注来源或 NOT_ASSESSABLE）
BINDING_POLICY = {
    "policy_id": "visual-binding-policy-v1", "policy_version": 1,
    "gate_order": ["integrity", "license", "relevance", "reuse", "binding_eligibility"],
    "no_scoring_ranking": True,
    "note_not_auto_best_image": "禁止 `score → sort → 第一名 = 自动绑定`；只做门禁 + 固定 policy",
    "reuse_preferences": {"prefer_unused": True, "allow_reuse_if_no_alternative": True,
                          "max_reuse": UNKNOWN, "source_family_preference": "record_only"},
    "thresholds_from_existing_only": True,
    "add_slot": {"allowed": False,
                 "why": "既有 timeline contract 未定义新增 visual slot；P7-6 不得改变 Scene/镜头数量"
                        "或 timeline schema ⇒ ADD 结构性不可用"},
    "partial_not_promoted": True,
    "not_assessable_not_promoted": True,
    "acquisition_is_not_automatic": True,
    "hitl_timestamp_not_in_identity": True,
    "proposal_not_execution": "P7-6 只产出 proposal；不修改 timeline/素材/6-G，不 rebuild/render",
}

HITL_ACTIONS = ("accept_proposal", "reject_proposal", "keep_current", "request_acquisition",
                "mark_unsupported")


def integrity_gate(candidate: dict | None) -> dict:
    if not candidate:
        return {"gate": "integrity", "result": "FAIL", "state": NOT_BINDABLE,
                "code": "INTEGRITY_FAILED", "why": "候选不在 AssetIndex 中"}
    checks = {"exists_in_index": True,
              "sha256_present": bool(candidate.get("sha256")),
              "decode_ok": candidate.get("decode_status") == "OK",
              "identity_consistent": bool(candidate.get("asset_id"))}
    ok = all(checks.values())
    return {"gate": "integrity", "result": "PASS" if ok else "FAIL",
            "state": BINDABLE if ok else NOT_BINDABLE,
            "code": None if ok else "INTEGRITY_FAILED", "checks": checks,
            "provenance": "P7-2 asset_index（read-only）"}


def license_gate(candidate: dict | None, *, gate_applies: bool | None = None,
                 license_decision: str | None = None, license_class: str | None = None) -> dict:
    if not candidate:
        return {"gate": "license", "result": "FAIL", "state": NOT_BINDABLE,
                "code": "LICENSE_DENIED", "why": "无候选"}
    applies = gate_applies if gate_applies is not None else bool(
        candidate.get("license_gate_applies"))
    lc = license_class or candidate.get("license_class") or UNKNOWN
    dec = license_decision or ("ALLOW" if lc in ("PUBLIC_DOMAIN", "FREE_ATTRIBUTION")
                               else "DENY" if lc == "RESTRICTED" else "HITL_REQUIRED")
    if not applies:
        return {"gate": "license", "result": "PASS", "state": BINDABLE,
                "code": "LICENSE_GATE_NOT_APPLICABLE", "license_class": lc,
                "why": "本地自备素材不在许可门禁范围（既有 policy，未修改）",
                "attribution_required": False}
    if dec == "DENY":
        return {"gate": "license", "result": "FAIL", "state": NOT_BINDABLE,
                "code": "LICENSE_DENIED", "license_class": lc,
                "why": "RESTRICTED 不得绑定（core.materials.license_block_reason）"}
    if dec == "HITL_REQUIRED":
        return {"gate": "license", "result": "HITL", "state": HITL_REQUIRED,
                "code": "LICENSE_UNKNOWN_HITL", "license_class": lc,
                "why": "许可信息不足（UNKNOWN）⇒ 人工确认后才可绑定（**不得**自动当允许）"}
    return {"gate": "license", "result": "PASS", "state": BINDABLE, "code": None,
            "license_class": lc, "attribution_required": lc == "FREE_ATTRIBUTION",
            "why": "许可已清（署名义务按 attribution 记录）"}


def relevance_gate(r: dict | None) -> dict:
    if not r:
        return {"gate": "relevance", "result": "HITL", "state": HITL_REQUIRED,
                "code": "RELEVANCE_NOT_ASSESSABLE_HITL", "decision": NOT_ASSESSABLE,
                "why": "无 P7-4 判定 ⇒ 不得自动绑定"}
    dec = r.get("decision")
    conf = r.get("confidence")
    if dec == "RELEVANT":
        return {"gate": "relevance", "result": "PASS", "state": BINDABLE, "decision": dec,
                "confidence": conf, "evidence_basis": "HUMAN_RECORDED" if conf == "HUMAN_RECORDED"
                else "MACHINE", "code": None}
    if dec == "IRRELEVANT":
        return {"gate": "relevance", "result": "FAIL", "state": NOT_BINDABLE,
                "code": "RELEVANCE_DENIED", "decision": dec,
                "why": "有可靠负向证据（人类判定/否决）"}
    if dec == "PARTIAL":
        return {"gate": "relevance", "result": "HITL", "state": HITL_REQUIRED,
                "code": "RELEVANCE_PARTIAL_HITL", "decision": dec,
                "why": "仅部分正向证据（词面）⇒ **不得**为了填满而升级为 RELEVANT"}
    return {"gate": "relevance", "result": "HITL", "state": HITL_REQUIRED,
            "code": "RELEVANCE_NOT_ASSESSABLE_HITL", "decision": dec,
            "why": "证据不足 ⇒ 无法证明相关，也**不得**自动绑定"}


def reuse_gate(candidate: dict, *, reuse_count: int, source_family: str,
               source_family_reuse: int, project_below_existing_threshold: bool) -> dict:
    """复用门禁：**不新造阈值**（max_reuse=UNKNOWN）⇒ 不自动拒绝，只记录并在既有阈值被违反时升级 HITL。"""
    if reuse_count == 0:
        return {"gate": "reuse", "result": "PASS_PREFERRED", "state": BINDABLE,
                "code": None, "reuse_count": 0, "source_family": source_family,
                "why": "从未使用 ⇒ 优先（prefer_unused）"}
    base = {"gate": "reuse", "reuse_count": reuse_count, "source_family": source_family,
            "source_family_reuse": source_family_reuse,
            "max_reuse_threshold": UNKNOWN, "threshold_status": NOT_ASSESSABLE}
    if project_below_existing_threshold:
        return {**base, "result": "HITL", "state": HITL_REQUIRED,
                "code": "REUSE_CONCENTRATION_HITL",
                "why": "项目多样性低于**既有冻结**阈值，且该候选已被复用 ⇒ 人工确认是否继续复用"
                       "（未新造阈值）"}
    return {**base, "result": "PASS_WITH_NOTE", "state": BINDABLE, "code": None,
            "why": "复用非自动拒绝理由（max_reuse 无既有依据 ⇒ NOT_ASSESSABLE）；记录复用事实"}


def eligibility(*, candidate: dict | None, relevance: dict | None, reuse: dict) -> dict:
    ig = integrity_gate(candidate)
    lg = license_gate(candidate, gate_applies=(candidate or {}).get("license_gate_applies"),
                      license_decision=(candidate or {}).get("_license_decision"),
                      license_class=(candidate or {}).get("license_class"))
    rg = relevance_gate(relevance)
    gates = [ig, lg, rg, reuse]
    if any(g["result"] == "FAIL" for g in gates):
        state, code = NOT_BINDABLE, next(g["code"] for g in gates if g["result"] == "FAIL")
    elif any(g["result"] == "HITL" for g in gates):
        state, code = HITL_REQUIRED, next(g["code"] for g in gates if g["result"] == "HITL")
    else:
        state, code = BINDABLE, None
    return {"state": state, "code": code, "gates": gates,
            "all_required_gates_passed": state == BINDABLE,
            "note": "RELEVANT ≠ BINDABLE：相关也可能因许可/完整性/reuse policy 不合格"}


def propose(*, scene_id: str, requirement_id: str, previous_asset_id: str | None,
            previous_evidence: dict, candidates: list[dict], relevance_by_asset: dict,
            reuse_stats: dict, source_family_reuse: dict, project_below_existing_threshold: bool,
            acquisition: dict, policy: dict) -> dict:
    """单场景绑定提案（纯函数、确定性；**不执行任何动作**）。"""
    evaluated = []
    for c in candidates:
        aid = c["asset_id"]
        reuse = reuse_gate(c, reuse_count=reuse_stats.get(aid, 0),
                           source_family=source_family_reuse.get(aid, {}).get("family", UNKNOWN),
                           source_family_reuse=source_family_reuse.get(aid, {}).get("count", 0),
                           project_below_existing_threshold=project_below_existing_threshold)
        el = eligibility(candidate=c, relevance=relevance_by_asset.get(aid), reuse=reuse)
        evaluated.append({"asset_id": aid, "is_previous": aid == previous_asset_id,
                          "relevance_decision": (relevance_by_asset.get(aid) or {}).get(
                              "decision", NOT_ASSESSABLE),
                          "relevance_confidence": (relevance_by_asset.get(aid) or {}).get(
                              "confidence", "NONE"),
                          "license_class": c.get("license_class", UNKNOWN),
                          "reuse_count": reuse_stats.get(aid, 0),
                          "state": el["state"], "blocking_code": el["code"],
                          "gates": el["gates"]})
    bindable = [e for e in evaluated if e["state"] == BINDABLE]
    prev_eval = next((e for e in evaluated if e["is_previous"]), None)
    # ---- 决策（固定顺序，非评分）----
    if prev_eval and prev_eval["state"] == BINDABLE:
        others = [e for e in bindable if not e["is_previous"]]
        decision = KEEP
        reason = ("现状绑定通过全部必需门禁（integrity/license/relevance/reuse）"
                  + ("；另有 {} 个同样合格的候选，但**无依据**声称其『明显更合适』⇒ 不提出 REPLACE"
                     .format(len(others)) if others else ""))
        chosen = prev_eval["asset_id"]
    elif bindable:
        alt = sorted(bindable, key=lambda e: (not e["is_previous"], e["reuse_count"], e["asset_id"]))
        chosen = alt[0]["asset_id"]
        decision = REPLACE
        reason = ("现状绑定未通过必需门禁（{}）且存在通过全部门禁的候选 ⇒ 提出 REPLACE 提案"
                  "（**不自动执行**）".format((prev_eval or {}).get("blocking_code") or "NO_PREVIOUS"))
    elif any(e["state"] == HITL_REQUIRED for e in evaluated):
        decision, chosen = HITL_REQUIRED, None
        reason = ("无 BINDABLE 候选；存在需人工确认的候选（{}）⇒ 交 HITL，不自动绑定"
                  .format(sorted({e["blocking_code"] for e in evaluated
                                  if e["state"] == HITL_REQUIRED and e["blocking_code"]})))
    else:
        decision, chosen = NO_BINDING, None
        reason = ("无 BINDABLE 候选且全部候选被可靠证明不适合（{}）⇒ NO_BINDING"
                  .format(sorted({e["blocking_code"] for e in evaluated if e["blocking_code"]}))
                  if evaluated else "候选池为空 ⇒ NO_BINDING")
    if decision == NO_BINDING and acquisition.get("acquisition_needed"):
        decision = NO_BINDING
        reason += "；P7-5 判 acquisition_needed=true ⇒ 记 ACQUISITION_REQUIRED（**不自动下载**）"
    body = {
        "schema": SCHEMA, "version": VERSION, "scene_id": scene_id,
        "requirement_id": requirement_id, "candidate_id": chosen,
        "previous_asset_id": previous_asset_id, "decision": decision,
        "decision_reason": reason, "previous_binding_source": previous_evidence.get("source"),
        "previous_selection_evidence": previous_evidence,
        "relevance_decision": (next((e["relevance_decision"] for e in evaluated
                                     if e["asset_id"] == chosen), None)
                               if chosen else (prev_eval or {}).get("relevance_decision")),
        "license_decision": next((g["result"] for g in (next(
            (e["gates"] for e in evaluated if e["asset_id"] == chosen), []) or [])
            if g["gate"] == "license"), None) if chosen else None,
        "integrity_decision": next((g["result"] for g in (next(
            (e["gates"] for e in evaluated if e["asset_id"] == chosen), []) or [])
            if g["gate"] == "integrity"), None) if chosen else None,
        "reuse_decision": next((g["result"] for g in (next(
            (e["gates"] for e in evaluated if e["asset_id"] == chosen), []) or [])
            if g["gate"] == "reuse"), None) if chosen else None,
        "acquisition_required": bool(decision == NO_BINDING
                                     and acquisition.get("acquisition_needed")),
        "acquisition_status": acquisition,
        "candidate_evaluations": evaluated,
        "bindable_candidates": [e["asset_id"] for e in bindable],
        "evidence_refs": sorted({r for e in evaluated for r in []}
                                | set(previous_evidence.get("evidence_refs") or [])),
        "policy_version": {"policy_id": policy["policy_id"],
                           "policy_version": policy["policy_version"]},
        "source_snapshot": policy.get("source_snapshot") or {},
        "execution": {"executed": False, "auto_executed": False,
                      "note": "proposal ≠ execution；P7-6 不修改 timeline/素材/6-G"},
    }
    dh = sha256_text(canonical(body))
    body["proposal_id"] = "bp-" + dh[:16]
    body["deterministic_hash"] = dh
    return body


def coverage_of(proposal: dict) -> dict:
    """覆盖分类（**禁止把 NOT_ASSESSABLE 归入 UNSUPPORTED**）。"""
    ev = proposal["candidate_evaluations"]
    bindable = [e for e in ev if e["state"] == BINDABLE]
    hitl = [e for e in ev if e["state"] == HITL_REQUIRED]
    denied = [e for e in ev if e["state"] == NOT_BINDABLE]
    if bindable:
        state, why = COVERED, "存在 BINDABLE candidate（通过全部门禁）"
        detail = "COVERED_KEEP" if proposal["decision"] == KEEP else (
            "COVERED_REPLACE_PROPOSED" if proposal["decision"] == REPLACE else "COVERED")
    elif not ev:
        state, why, detail = NOT_ASSESSABLE, "候选池为空（无候选可判）", "NO_CANDIDATES"
    elif hitl:
        state = HITL_REQUIRED
        why = "有候选但相关性/治理需人工确认（未被证明不适合）"
        detail = "HITL_PENDING"
    elif denied and len(denied) == len(ev):
        state, why, detail = UNSUPPORTED, "全部候选均被可靠证明不适合", "ALL_DENIED"
    else:
        state, why, detail = NOT_ASSESSABLE, "缺少必要证据，无法判断覆盖状态", "INSUFFICIENT_EVIDENCE"
    return {"coverage": state, "coverage_detail": detail, "why": why,
            "bindable_count": len(bindable), "hitl_count": len(hitl),
            "not_bindable_count": len(denied),
            "rule": "NOT_ASSESSABLE ≠ UNSUPPORTED（前者缺证据，后者已被证明不适合）"}


def apply_hitl_decision(proposal: dict, *, actor: str, action: str, reason: str,
                        timestamp: str, evidence_refs: list | None = None) -> dict:
    """HITL 记录入口。**timestamp/actor 不进入 proposal identity/hash。**"""
    if action not in HITL_ACTIONS:
        raise ValueError("未知 HITL 动作：{}".format(action))
    rec = {"actor": actor, "action": action, "reason": reason, "timestamp": timestamp,
           "evidence_refs": sorted(evidence_refs or []), "proposal_id": proposal["proposal_id"],
           "proposal_hash": proposal["deterministic_hash"]}
    return {"record": rec,
            "recorded_outside_identity": True,
            "note": "人工记录可含 timestamp；proposal.deterministic_hash 不含 actor/timestamp"}


def proposal_identity(proposal: dict) -> str:
    """proposal 身份哈希（排除**派生/审计**字段：自身 hash、由 hash 派生的 id、HITL 审计与时间戳）。"""
    body = {k: v for k, v in proposal.items()
            if k not in ("deterministic_hash", "proposal_id", "hitl_audit", "timestamp", "actor")}
    return sha256_text(canonical(body))
