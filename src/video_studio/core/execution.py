# -*- coding: utf-8 -*-
"""6-B/M4 —— **Human-Approved Directorial Revision Execution**（受控执行链；无自动批准、无自动扩大范围）。

职责与守恒规则（代码级）：
  1. **审批层**：每条 proposal 必须由人工明确 `APPROVE / REJECT`；审批绑定
     `proposal_id + proposal_sha256 + 人工身份 + 时间 + reason/provenance`；
  2. **只有 APPROVE 且 hash 匹配者**才允许进入执行 —— 未批准（`BLOCKED_UNAPPROVED`）、
     被拒（`BLOCKED_REJECTED`）、proposal 被改动（`BLOCKED_TAMPERED`）一律**阻断**；
  3. **proposal tamper guard**：执行前重算 `proposal_sha256` 并与审批里绑定的值比对；
  4. **fail-closed**：执行器抛错即记 `FAILED` + 原因，**不自动换方案、不自动扩大范围、不自动批准**；
  5. **局部化守恒**：沿用 6-B/M3 的 `max_scenes_per_proposal` / 占比上限，`film_wide` 直接拒绝；
  6. **素材守恒**：只能使用**真实存在且可验证**的素材；候选不存在 ⇒ `PENDING_HUMAN_ASSET`（不虚构、不占位替换）；
  7. **复核强制**：执行成功后必须调用调用方注入的 `recheck`（PI-1…PI-6，随后 DQ）并记录结果；
     PI FAIL/UNKNOWN ⇒ 结果按既有门禁处理（本层**不**提升、不绕过）；
  8. 审批与执行各有 **append-only + 哈希链**台账；本模块自身不写 DB、不派发任务、不改任何冻结产物。

执行器由调用方注入（`executors: {action: callable(ctx, proposal) -> {"outputs": [...], "steps": [...]}}`），
本模块只负责**门禁、审计、链校验与汇总**，保持 core 层无 ffmpeg/subprocess 依赖。
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

APPROVAL_DECISIONS = ("APPROVE", "REJECT")
REQUIRED_APPROVAL_FIELDS = ("approval_id", "proposal_id", "proposal_sha256", "decision",
                            "approved_by", "approved_at", "reason", "provenance")
EXECUTION_STATES = ("SUCCEEDED", "FAILED", "BLOCKED_UNAPPROVED", "BLOCKED_REJECTED",
                    "BLOCKED_TAMPERED", "BLOCKED_NOT_LOCAL", "PENDING_HUMAN_ASSET",
                    "UNSUPPORTED_ACTION")
POLICY = {
    "max_scenes_per_proposal": 6,          # 与 6-B/M3 保持一致（局部化守恒）
    "max_share_of_film_per_proposal": 0.30,
    "forbid_film_wide_rewrite": True,
    "require_approval": True,
    "no_auto_approval": True,
    "no_auto_scope_expansion": True,
    "require_pi_recheck": True,
    "require_dq_recheck": True,
}
READONLY = {"enforced": False, "advisory": True}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha_text(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def proposal_sha256(proposal: dict) -> str:
    """proposal 的**内容指纹**（用于 tamper guard：执行前必须重新校验）。"""
    body = {k: v for k, v in (proposal or {}).items()
            if k not in ("entry_sha256", "prev_sha256", "seq", "register")}
    return _sha_text(json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":")))


def approval_id(proposal_id: str, decision: str, approved_by: str) -> str:
    return "ap-" + _sha_text("|".join([str(proposal_id), str(decision), str(approved_by)]))[:12]


def make_approval(proposal: dict, decision: str, approved_by: str, reason: str, provenance,
                  at: str | None = None) -> dict:
    decision = str(decision or "").upper()
    if decision not in APPROVAL_DECISIONS:
        raise ValueError("非法审批值: {!r}（仅 {}）".format(decision, list(APPROVAL_DECISIONS)))
    rec = {
        "schema": "revision-approval-v1",
        "approval_id": approval_id(proposal.get("proposal_id"), decision, approved_by),
        "proposal_id": proposal.get("proposal_id"),
        "proposal_label": proposal.get("label"),
        "proposal_sha256": proposal_sha256(proposal),
        "finding_id": proposal.get("finding_id"),
        "decision_ref": proposal.get("decision_ref"),
        "decision": decision,
        "approved_by": approved_by,
        "approved_at": at or _now(),
        "reason": reason,
        "provenance": provenance,
        "auto_approved": False,
        **READONLY,
    }
    missing = [k for k in REQUIRED_APPROVAL_FIELDS if rec.get(k) in (None, "", [], {})]
    if missing:
        raise ValueError("审批缺少必需字段: {}".format(missing))
    return rec


def verify_approval(proposal: dict, approval: dict) -> dict:
    """校验审批与 proposal 的绑定关系（含 **tamper guard**）。"""
    if not approval:
        return {"ok": False, "code": "BLOCKED_UNAPPROVED", "why": "无审批记录"}
    if approval.get("decision") == "REJECT":
        return {"ok": False, "code": "BLOCKED_REJECTED", "why": "人工已 REJECT 该 proposal"}
    if approval.get("decision") != "APPROVE":
        return {"ok": False, "code": "BLOCKED_UNAPPROVED",
                "why": "审批值非法: {}".format(approval.get("decision"))}
    if approval.get("proposal_id") != proposal.get("proposal_id"):
        return {"ok": False, "code": "BLOCKED_TAMPERED", "why": "审批绑定的 proposal_id 不匹配"}
    cur = proposal_sha256(proposal)
    if approval.get("proposal_sha256") != cur:
        return {"ok": False, "code": "BLOCKED_TAMPERED",
                "why": "proposal 内容与审批时不一致（hash {} != {}）".format(
                    approval.get("proposal_sha256"), cur)}
    if not approval.get("approved_by") or not approval.get("reason"):
        return {"ok": False, "code": "BLOCKED_UNAPPROVED", "why": "审批缺人工身份/理由"}
    return {"ok": True, "code": "APPROVED", "why": None}


def verify_locality(proposal: dict, policy: dict | None = None) -> dict:
    """执行前复核 6-B/M3 的局部化限制（禁止 film-wide 与超范围）。"""
    p = {**POLICY, **(policy or {})}
    sc = (proposal or {}).get("affected_scope") or {}
    if p["forbid_film_wide_rewrite"] and sc.get("film_wide"):
        return {"ok": False, "code": "BLOCKED_NOT_LOCAL", "why": "film_wide 重构被禁止"}
    if len(sc.get("scenes") or []) > p["max_scenes_per_proposal"]:
        return {"ok": False, "code": "BLOCKED_NOT_LOCAL",
                "why": "{} 镜 > 上限 {}".format(len(sc.get("scenes") or []),
                                             p["max_scenes_per_proposal"])}
    share = sc.get("share_of_film")
    if share is not None and share > p["max_share_of_film_per_proposal"]:
        return {"ok": False, "code": "BLOCKED_NOT_LOCAL",
                "why": "时长占比 {} > 上限 {}".format(share,
                                                p["max_share_of_film_per_proposal"])}
    if not (sc.get("scenes") or sc.get("assets") or sc.get("window") or sc.get("asset_class")):
        return {"ok": False, "code": "BLOCKED_NOT_LOCAL", "why": "范围不可定位"}
    return {"ok": True, "code": "LOCAL_OK", "why": None}


def gate_execution(proposal: dict, approvals: list, policy: dict | None = None) -> dict:
    """执行门禁：人工身份 → 审批值 → hash 绑定 → 局部化。任一步不过即 fail-closed。"""
    p = {**POLICY, **(policy or {})}
    aps = [a for a in (approvals or []) if a.get("proposal_id") == proposal.get("proposal_id")]
    if p["require_approval"] and not aps:
        return {"allowed": False, "code": "BLOCKED_UNAPPROVED", "why": "该 proposal 未经人工审批",
                "approval": None, "proposal_sha256": proposal_sha256(proposal)}
    cur = aps[-1] if aps else None            # 最新审批生效（台账 append-only）
    av = verify_approval(proposal, cur)
    if not av["ok"]:
        return {"allowed": False, **av, "approval": cur,
                "proposal_sha256": proposal_sha256(proposal)}
    lv = verify_locality(proposal, p)
    if not lv["ok"]:
        return {"allowed": False, **lv, "approval": cur,
                "proposal_sha256": proposal_sha256(proposal)}
    return {"allowed": True, "code": "APPROVED", "why": None, "approval": cur,
            "proposal_sha256": proposal_sha256(proposal)}


def execute_proposal(proposal: dict, approvals: list, executors: dict, ctx: dict,
                     recheck=None, policy: dict | None = None) -> dict:
    """受控执行：门禁 → 执行器 → **强制 PI/DQ 复核** → 记录（失败一律 fail-closed）。"""
    p = {**POLICY, **(policy or {})}
    gate = gate_execution(proposal, approvals, p)
    base = {"schema": "revision-execution-v1", "proposal_id": proposal.get("proposal_id"),
            "proposal_label": proposal.get("label"), "finding_id": proposal.get("finding_id"),
            "action": proposal.get("action"), "executed_at": _now(),
            "proposal_sha256": gate.get("proposal_sha256"),
            "approval_ref": ({"approval_id": (gate.get("approval") or {}).get("approval_id"),
                              "approved_by": (gate.get("approval") or {}).get("approved_by"),
                              "decision": (gate.get("approval") or {}).get("decision"),
                              "approved_at": (gate.get("approval") or {}).get("approved_at")}
                             if gate.get("approval") else None),
            "auto_approved": False, "auto_scope_expansion": False, "auto_retry": False,
            "sandbox_only": True, **READONLY}
    if not gate["allowed"]:
        return {**base, "state": gate["code"], "why": gate["why"], "steps": [],
                "outputs": [], "recheck": None, "pi_gate_outcome": None}
    action = proposal.get("action")
    ex = (executors or {}).get(action)
    if ex is None:
        return {**base, "state": "UNSUPPORTED_ACTION",
                "why": "本阶段未实现该 action 的执行器（不模拟、不伪造执行结果）",
                "steps": [], "outputs": [], "recheck": None, "pi_gate_outcome": None}
    try:
        res = ex(ctx, proposal) or {}
    except Exception as exc:                                     # noqa: BLE001
        # fail-closed：记录失败原因，**不**自动换方案/换素材/扩大范围
        return {**base, "state": "FAILED",
                "why": "{}: {}".format(type(exc).__name__, str(exc)[:300]),
                "steps": [], "outputs": [], "recheck": None, "pi_gate_outcome": None}
    if res.get("pending"):
        # 需要真实素材/人工处理：**不**执行、不占位替换、不虚构
        return {**base, "state": res["pending"], "why": res.get("why"),
                "steps": res.get("steps") or [], "outputs": res.get("outputs") or [],
                "recheck": None, "pi_gate_outcome": None}
    # ---- 强制复核：PI-1…PI-6（随后 DQ）；PI FAIL/UNKNOWN 按既有门禁处理 ----
    recheck_res, pi_outcome = None, None
    if p["require_pi_recheck"] and recheck is not None:
        try:
            recheck_res = recheck(ctx, proposal, res)
            pi_outcome = (recheck_res or {}).get("pi_gate_outcome")
        except Exception as exc:                                 # noqa: BLE001
            return {**base, "state": "FAILED",
                    "why": "PI/DQ 复核失败（fail-closed）：{}: {}".format(type(exc).__name__,
                                                                       str(exc)[:200]),
                    "steps": res.get("steps") or [], "outputs": res.get("outputs") or [],
                    "recheck": None, "pi_gate_outcome": None}
    elif p["require_pi_recheck"]:
        return {**base, "state": "FAILED", "why": "缺少强制 PI 复核（require_pi_recheck=True）",
                "steps": res.get("steps") or [], "outputs": res.get("outputs") or [],
                "recheck": None, "pi_gate_outcome": None}
    return {**base, "state": "SUCCEEDED", "why": None,
            "steps": res.get("steps") or [], "outputs": res.get("outputs") or [],
            "recheck": recheck_res, "pi_gate_outcome": pi_outcome,
            "promoted": False,        # 永不自动提升：PI 门禁结果交既有门禁/人工处理
            # 6-C：执行证据随记录落盘（素材 provenance / 切分计划 / 音轨与时长核验 / 内存推演输入）
            # 6-E：新增自制视觉层证据（spec sha256 / overlay sha256 / 渲染文本 / 字体 / 安全区）
            "exec_evidence": {k: res.get(k) for k in
                              ("asset_evidence", "asset_verifications", "split_plan",
                               "cut_evidence", "duration_check", "audio_check",
                               "scene_projection", "visual_aid_evidence",
                               "visual_aid_spec_source") if res.get(k) is not None},
            "notes": res.get("notes")}


# ---------------------------------------------------------------- append-only 台账
def _entry_sha(entry: dict) -> str:
    body = {k: v for k, v in entry.items() if k != "entry_sha256"}
    return _sha_text(json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":")))


def _append(path, rec: dict, schema: str) -> dict:
    p = Path(path)
    entries = load_ledger(p)
    prev = entries[-1]["entry_sha256"] if entries else ""
    out = dict(rec)
    out["seq"] = len(entries) + 1
    out["prev_sha256"] = prev
    out["ledger"] = {"append_only": True, "schema": schema}
    out["entry_sha256"] = _entry_sha(out)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(out, ensure_ascii=False) + "\n")
    return out


def load_ledger(path) -> list:
    p = Path(path)
    if not p.is_file():
        return []
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


def append_approval(path, rec: dict) -> dict:
    return _append(path, rec, "revision-approval-v1")


def append_execution(path, rec: dict) -> dict:
    return _append(path, rec, "revision-execution-v1")


def verify_chain(entries: list) -> dict:
    prev = ""
    for i, e in enumerate(entries or [], start=1):
        if e.get("seq") != i:
            return {"ok": False, "length": len(entries), "broken_at": i, "why": "seq 不连续"}
        if e.get("prev_sha256") != prev:
            return {"ok": False, "length": len(entries), "broken_at": i,
                    "why": "prev_sha256 不符（历史被改写/插入）"}
        if e.get("entry_sha256") != _entry_sha(e):
            return {"ok": False, "length": len(entries), "broken_at": i,
                    "why": "entry_sha256 不匹配（条目被改写）"}
        prev = e["entry_sha256"]
    return {"ok": True, "length": len(entries or []), "broken_at": None, "why": None}


def summarize_executions(proposals: list, approvals: list, executions: list) -> dict:
    """汇总：审批覆盖、执行状态分布、**未批准/被拒/篡改是否真的没有执行**、PI 门禁结果、零自动化。"""
    by_pid = {}
    for e in executions or []:
        by_pid.setdefault(e.get("proposal_id"), []).append(e)
    ap_by_pid = {}
    for a in approvals or []:
        ap_by_pid.setdefault(a.get("proposal_id"), []).append(a)
    states = {}
    for e in executions or []:
        states[e["state"]] = states.get(e["state"], 0) + 1
    executed_pids = {e["proposal_id"] for e in (executions or []) if e["state"] == "SUCCEEDED"}
    approved_pids = {pid for pid, aps in ap_by_pid.items()
                     if aps and aps[-1].get("decision") == "APPROVE"}
    violated = sorted(executed_pids - approved_pids)          # 未批准却执行了（应恒为空）
    recheck_results = {e.get("proposal_id"): (e.get("pi_gate_outcome") or
                                              (e.get("recheck") or {}).get("pi_gate_outcome"))
                       for e in (executions or []) if e["state"] == "SUCCEEDED"}
    return {
        "schema": "revision-execution-summary-v1",
        "proposals": len(proposals or []),
        "approved": sorted(approved_pids), "rejected": sorted(
            pid for pid, aps in ap_by_pid.items() if aps and aps[-1].get("decision") == "REJECT"),
        "unapproved": sorted({p["proposal_id"] for p in (proposals or [])}
                             - set(ap_by_pid) - set()),
        "executions": len(executions or []), "state_counts": states,
        "executed_succeeded": sorted(executed_pids),
        "executed_without_approval": violated,        # 恒为空 = "未批准不得执行"成立
        "auto_approved": any(a.get("auto_approved") for a in (approvals or [])),
        "recheck_pi_outcomes": recheck_results,
        "promoted": [e["proposal_id"] for e in (executions or []) if e.get("promoted")],
        **READONLY,
    }


# ============================================================================
# 6-B/M5 —— 重叠/冲突检测 + 批量一致性 + 幂等（**只增不改**：M4 的常量与判定语义保持不变）
# ============================================================================
M5_STATES = ("BLOCKED_CONFLICT", "BLOCKED_ALREADY_EXECUTED")
# M5 **扩展**状态（不修改 M4 冻结的 `EXECUTION_STATES` 元组本身 ⇒ M4 真值集仍逐字一致）
ALL_EXECUTION_STATES = tuple(EXECUTION_STATES) + M5_STATES

# 冲突规则（全部为**阻断**型；设计取向 = 保守阻断 > 自动合并/自动排序）
OVERLAP_POLICY = {
    "block_on_scene_overlap": True,        # 共同 scene_id
    "block_on_window_overlap": True,       # window 区间有**正长度**交集
    "block_on_shared_asset": True,         # 共同 asset_id（保守；即使窗口不相交也阻断）
    "block_on_same_target": True,          # 同一 target（非空）
    "touch_is_overlap": False,             # 端点相接（t1==t0'）不算重叠
    "block_all_participants": True,        # 对称阻断：不由系统挑选"谁先谁后"
    "requires_human_reapproval": True,     # 冲突 ⇒ 必须人工重新批准
    "auto_merge": False,
    "auto_reorder": False,
    "auto_scope_expansion": False,
    "idempotent": True,                    # 同一 proposal_id + 同一 hash 不得重复执行
}
CONFLICT_KINDS = ("scene", "window", "asset", "target")


def _as_list(v) -> list:
    return list(v) if isinstance(v, (list, tuple, set)) else ([] if v in (None, "") else [v])


def _window_of(proposal: dict):
    """取 proposal 的窗口（顶层 / affected_scope），返回 (t0, t1) 或 None。"""
    sc = proposal.get("affected_scope") or {}
    w = proposal.get("window") or sc.get("window")
    if not w or not isinstance(w, (list, tuple)) or len(w) != 2:
        return None
    try:
        return (float(w[0]), float(w[1]))
    except (TypeError, ValueError):
        return None


def _target_identities(proposal: dict) -> list:
    """target 的**资源身份**集合（仅取具体资源键；class 级描述词不算身份，避免过度阻断）。"""
    target = proposal.get("target")
    out = []
    if isinstance(target, dict):
        for key, val in target.items():
            if key in ("scene_id", "scenes", "asset_id", "assets", "path", "slot"):
                for v in _as_list(val):
                    out.append("{}={}".format(key, v))
            elif key in ("window", "windows"):
                for w in (val if isinstance(val, (list, tuple)) and val and
                          isinstance(val[0], (list, tuple)) else [val]):
                    if isinstance(w, (list, tuple)) and len(w) == 2:
                        out.append("window={}-{}".format(w[0], w[1]))
    else:
        out = [str(t) for t in _as_list(target)]
    return sorted(set(out))


def proposal_footprint(proposal: dict) -> dict:
    """proposal 的**触碰足迹**：scenes / assets / windows / targets（用于重叠判定与矩阵）。"""
    sc = proposal.get("affected_scope") or {}
    w = _window_of(proposal)
    return {"proposal_id": proposal.get("proposal_id"), "label": proposal.get("label"),
            "action": proposal.get("action"),
            "scenes": sorted({str(s) for s in _as_list(sc.get("scenes"))}),
            "assets": sorted({str(a) for a in _as_list(sc.get("assets"))}),
            "asset_class": sc.get("asset_class"),
            "window": list(w) if w else None,
            "targets": _target_identities(proposal)}


def _window_intersection(a, b):
    """正长度交集才算重叠（端点相接不算；`touch_is_overlap=False`）。"""
    if not a or not b:
        return None
    lo, hi = max(a[0], b[0]), min(a[1], b[1])
    if hi - lo > 1e-9:
        return [round(lo, 3), round(hi, 3)]
    return None


def pair_conflict(a: dict, b: dict, policy: dict | None = None) -> dict | None:
    """判定两条 proposal 是否重叠/冲突；返回冲突明细或 None。"""
    p = {**OVERLAP_POLICY, **(policy or {})}
    fa, fb = proposal_footprint(a), proposal_footprint(b)
    kinds, detail = [], {}
    shared_scenes = sorted(set(fa["scenes"]) & set(fb["scenes"]))
    if p["block_on_scene_overlap"] and shared_scenes:
        kinds.append("scene")
        detail["shared_scenes"] = shared_scenes
    inter = _window_intersection(fa["window"], fb["window"])
    if p["block_on_window_overlap"] and inter:
        kinds.append("window")
        detail["window_intersection"] = inter
    shared_assets = sorted(set(fa["assets"]) & set(fb["assets"]))
    if p["block_on_shared_asset"] and shared_assets:
        kinds.append("asset")
        detail["shared_assets"] = shared_assets
    shared_targets = sorted(set(fa["targets"]) & set(fb["targets"]))
    if p["block_on_same_target"] and shared_targets:
        kinds.append("target")
        detail["shared_targets"] = shared_targets
    if not kinds:
        return None
    return {"a_id": fa["proposal_id"], "b_id": fb["proposal_id"], "a": fa["label"],
            "b": fb["label"], "kinds": kinds, "code": "CONFLICT_OVERLAP",
            "touching_only": bool(fa["window"] and fb["window"]
                                  and fa["window"][1] == fb["window"][0]),
            **detail}


def detect_conflicts(proposals: list, policy: dict | None = None) -> dict:
    """全对冲突检测：返回冲突对、按 proposal 归并、以及**冲突矩阵**（对称、含重叠种类）。"""
    ps = list(proposals or [])
    pairs = []
    for i, a in enumerate(ps):
        for b in ps[i + 1:]:
            c = pair_conflict(a, b, policy)
            if c:
                pairs.append(c)
    by_pid = {}
    for c in pairs:
        by_pid.setdefault(c["a_id"], []).append(c["b_id"])
        by_pid.setdefault(c["b_id"], []).append(c["a_id"])
    ids = [p.get("proposal_id") for p in ps]
    matrix = {}
    for p in ps:
        row = {}
        for q in ps:
            if p is q:
                row[q.get("proposal_id")] = None
                continue
            c = pair_conflict(p, q, policy)
            row[q.get("proposal_id")] = c["kinds"] if c else []
        matrix[p.get("proposal_id")] = row
    return {"schema": "revision-overlap-matrix-v1",
            "proposals": ids, "proposal_count": len(ps),
            "pair_count": len(ps) * (len(ps) - 1) // 2,
            "conflict_pair_count": len(pairs), "pairs": pairs,
            "conflicting_ids": sorted(by_pid), "conflict_with": by_pid,
            "matrix": matrix, "kinds": list(CONFLICT_KINDS),
            "policy": {**OVERLAP_POLICY, **(policy or {})},
            "note": "对称阻断：参与任一冲突的 proposal **全部**不执行，需人工重新批准；"
                    "**不**自动合并、**不**自动排序、**不**扩大范围；端点相接不算重叠。"}


def executed_ids(ledger_entries: list, proposal: dict) -> list:
    """幂等：台账里已 **SUCCEEDED** 且 proposal_sha256 相同的记录（同一方案不得重复执行）。"""
    cur = proposal_sha256(proposal)
    return [e.get("proposal_id") for e in (ledger_entries or [])
            if e.get("proposal_id") == proposal.get("proposal_id")
            and e.get("proposal_sha256") == cur and e.get("state") == "SUCCEEDED"]


def gate_batch(proposals: list, approvals: list, policy: dict | None = None,
               ledger_entries: list | None = None) -> dict:
    """批量门禁：先逐条审批/篡改/局部化判定，再对**可执行集合**做冲突与幂等判定。

    关键语义（fail-closed）：
      · 冲突只在**本来会执行**（个体门禁已通过）的 proposal 之间成立 ⇒ 被拒/未批准的方案
        不会把已批准方案拖住（避免假阻断）；
      · 参与冲突者**全部**被 `BLOCKED_CONFLICT`，并标记 `requires_human_reapproval=True`；
      · 已成功执行过的同一方案（同 id + 同 hash）⇒ `BLOCKED_ALREADY_EXECUTED`。
    """
    p = {**OVERLAP_POLICY, **(policy or {})}
    individual, admissible = {}, []
    for prop in (proposals or []):
        g = gate_execution(prop, approvals, None)
        individual[prop.get("proposal_id")] = g
        if g["allowed"]:
            admissible.append(prop)
    conflicts = detect_conflicts(admissible, p) if len(admissible) > 1 else \
        {"schema": "revision-overlap-matrix-v1", "proposals": [x.get("proposal_id")
                                                              for x in admissible],
         "conflict_pair_count": 0, "pairs": [], "conflicting_ids": [],
         "conflict_with": {}, "matrix": {x.get("proposal_id"): {x.get("proposal_id"): None}
                                        for x in admissible},
         "policy": p, "note": "可执行集合 ≤1 条：无需冲突判定"}
    ledger_entries = ledger_entries if ledger_entries is not None else []
    decisions = {}
    for prop in (proposals or []):
        pid = prop.get("proposal_id")
        g = individual.get(pid) or {}
        if not g.get("allowed"):
            decisions[pid] = {"code": g.get("code"), "allowed": False, "why": g.get("why"),
                              "executor_invoked": False, "source": "individual_gate"}
            continue
        if pid in conflicts["conflicting_ids"]:
            others = conflicts["conflict_with"].get(pid) or []
            decisions[pid] = {"code": "BLOCKED_CONFLICT", "allowed": False,
                              "why": "与已批准的其它方案在 scene/window/asset/target 上重叠：{}"
                                     .format(",".join(others)),
                              "conflict_with": others, "requires_human_reapproval":
                                  bool(p["requires_human_reapproval"]),
                              "executor_invoked": False, "source": "overlap_gate"}
            continue
        done = executed_ids(ledger_entries, prop)
        if p["idempotent"] and done:
            decisions[pid] = {"code": "BLOCKED_ALREADY_EXECUTED", "allowed": False,
                              "why": "同一 proposal（同 id + 同 hash）已成功执行过，禁止重复执行",
                              "executor_invoked": False, "source": "idempotency_gate"}
            continue
        decisions[pid] = {"code": "APPROVED", "allowed": True, "why": None,
                          "executor_invoked": True, "source": "individual_gate"}
    return {"schema": "revision-batch-gate-v1", "decisions": decisions,
            "admissible": [x.get("proposal_id") for x in admissible],
            "individual": {k: {"code": v.get("code"), "allowed": v.get("allowed")}
                           for k, v in individual.items()},
            "conflicts": conflicts,
            "blocked_conflict": sorted(k for k, v in decisions.items()
                                       if v["code"] == "BLOCKED_CONFLICT"),
            "blocked_already_executed": sorted(k for k, v in decisions.items()
                                               if v["code"] == "BLOCKED_ALREADY_EXECUTED"),
            "policy": p,
            "note": "批量门禁只做判定；执行由 execute_batch 完成，执行器仅在 allowed=True 时被调用。"}


def blocked_record(proposal: dict, code: str, why: str, extra: dict | None = None) -> dict:
    """为**未调用执行器**的 proposal 生成同 schema 记录（显式标注 executor_invoked=False）。"""
    return {"schema": "revision-execution-v1", "proposal_id": proposal.get("proposal_id"),
            "proposal_label": proposal.get("label"), "finding_id": proposal.get("finding_id"),
            "action": proposal.get("action"), "executed_at": _now(),
            "proposal_sha256": proposal_sha256(proposal), "approval_ref": None,
            "auto_approved": False, "auto_scope_expansion": False, "auto_retry": False,
            "sandbox_only": True, **READONLY,
            "state": code, "why": why, "steps": [], "outputs": [], "recheck": None,
            "pi_gate_outcome": None, "executor_invoked": False, **(extra or {})}


def execute_batch(proposals: list, approvals: list, executors: dict, ctx: dict,
                  recheck=None, policy: dict | None = None, ledger_entries: list | None = None,
                  ledger=None, lock=None) -> dict:
    """按**调用方给定顺序**批量执行：先 `gate_batch`，只有 allowed=True 才调用执行器。

    · 顺序 = 输入顺序（**不**由本模块排序/合并）；
    · `ledger` 给定时逐条 append（`lock` 提供时串行化"执行+落账"临界区，保证链连续）；
    · 冲突/幂等/个体门禁阻断者一律生成 `executor_invoked=False` 的记录。
    """
    gate = gate_batch(proposals, approvals, policy, ledger_entries)
    idem = gate["policy"]["idempotent"]
    records, appends = [], []
    for prop in (proposals or []):
        pid = prop.get("proposal_id")
        d = gate["decisions"].get(pid) or {}
        # 临界区（`lock` 给定时串行化）：**重新读取**台账 → 幂等复查 → 执行 → 落账
        with (lock if lock is not None else _NullLock()):
            live = load_ledger(ledger) if ledger is not None else list(ledger_entries or [])
            if not d.get("allowed"):
                rec = blocked_record(prop, d.get("code") or "BLOCKED_UNAPPROVED",
                                     d.get("why") or "",
                                     {k: d[k] for k in ("conflict_with",
                                                        "requires_human_reapproval", "source")
                                      if k in d})
            elif idem and executed_ids(live, prop):
                rec = blocked_record(prop, "BLOCKED_ALREADY_EXECUTED",
                                     "同一 proposal（同 id + 同 hash）已成功执行过，禁止重复执行",
                                     {"source": "idempotency_gate_live"})
            else:
                rec = execute_proposal(prop, approvals, executors, ctx, recheck=recheck)
                rec["executor_invoked"] = rec.get("state") in ("SUCCEEDED", "FAILED",
                                                               "PENDING_HUMAN_ASSET",
                                                               "UNSUPPORTED_ACTION")
            if ledger is not None:
                rec = append_execution(ledger, rec)
                appends.append(rec.get("seq"))
        records.append(rec)
    return {"schema": "revision-batch-execution-v1", "gate": gate, "records": records,
            "order": [r.get("proposal_id") for r in records],
            "appended_seq": appends,
            "states": {r.get("proposal_id"): r.get("state") for r in records},
            "executor_invocations": [r.get("proposal_id") for r in records
                                     if r.get("executor_invoked")],
            "note": "批量执行遵守：审批绑定、冲突对称阻断、幂等、fail-closed；不自动合并/排序/扩范围"}


class _NullLock:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False
