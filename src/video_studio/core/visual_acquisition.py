# -*- coding: utf-8 -*-
"""P7-5：**受治理的视觉素材获取**（`visual-acquisition-request-v1`；默认 DRY_RUN，零网络）。

三层严格分离（**不得混淆**）
--------------------------
* **需求生成** ≠ **素材下载** ≠ **素材采用/绑定**
* 状态机：`REQUESTED`（需求需要新候选）→ `FETCHED`（provider 返回了文件）→
  `VERIFIED`（identity/decode/provenance/license/integrity 通过）→ `ACCEPTED`（相关性 + HITL 通过）。
  **`BOUND` 在 P7-5 明确禁止**（不得修改 material timeline）。

最重要的逻辑区分（P7-4 的教训）
------------------------------
`NOT_ASSESSABLE`（**无法证明相关**）**不得**自动等价于 `NO_RELEVANT_CANDIDATE`
（**没有相关素材**）。每个 reason code 都带 `deficiency_kind`，只有**可机器核查的缺口**
（素材池缺失 / 许可阻断 / 溯源缺口 / 多样性缺口）才算 `acquisition_needed = True`；
**验证能力缺口**（缺 VLM/视觉证据）不算"缺素材"，不得借此批量发起下载。

复用（**不新增协议**）：`tools/material_provider.py`（provider 接口 + `UrllibTransport`
HTTPS-only/禁跳转/流式 max_bytes + `PROVIDER_*` 错误码）、`core/supply.py`（准入限制/重试分类）、
`core/materials.py`（许可分类与语义）。
"""
from __future__ import annotations

from .asset_candidate import UNKNOWN
from .materials import classify_license, license_gate_applies
from .visual_requirement import canonical, sha256_text

SCHEMA = "visual-acquisition-request-v1"
PLAN_SCHEMA = "visual-acquisition-plan-v1"
VERSION = 1

DRY_RUN = "DRY_RUN"
LIVE_FETCH = "LIVE_FETCH"
MODES = (DRY_RUN, LIVE_FETCH)

#: 状态机（`BOUND` 在 P7-5 禁止）
REQUESTED = "REQUESTED"
FETCHED = "FETCHED"
VERIFIED = "VERIFIED"
ACCEPTED = "ACCEPTED"
BOUND = "BOUND"
STATE_MACHINE = {
    "states": [REQUESTED, FETCHED, VERIFIED, ACCEPTED, BOUND],
    "allowed_transitions": {REQUESTED: [FETCHED], FETCHED: [VERIFIED], VERIFIED: [ACCEPTED],
                            ACCEPTED: []},
    "forbidden_in_p7_5": [BOUND],
    "not_meaning": {REQUESTED: "**不是**『已找到素材』",
                    FETCHED: "**不是**『素材合法』",
                    VERIFIED: "**不是**『素材适合 Scene』",
                    ACCEPTED: "经相关性验证 + HITL 后允许进入项目资产池",
                    BOUND: "P7-5 **禁止执行**（不得修改 material timeline）"},
}

#: reason code → 缺口类型 → 是否需要获取（**先命中先返回**）
REASON_CODES = {
    "NO_RELEVANT_CANDIDATE": {
        "deficiency_kind": "POOL_ABSENCE", "acquisition_needed": True,
        "meaning": "有**可靠证据**表明现有候选中没有相关的（例如当前所用候选被人类判为不相关）",
        "guard": "必须附 absence_evidence_level；不得由 NOT_ASSESSABLE 推出本码"},
    "ONLY_PARTIAL_EVIDENCE": {
        "deficiency_kind": "VERIFICATION_CAPABILITY_GAP", "acquisition_needed": False,
        "meaning": "只有部分（词面）证据，关键视觉条件无法验证 ⇒ 属**验证能力**缺口",
        "guard": "获取新候选**不能**修复验证能力缺口 ⇒ 不得据此下载"},
    "NOT_ASSESSABLE_WITH_LOCAL_POOL": {
        "deficiency_kind": "VERIFICATION_CAPABILITY_GAP", "acquisition_needed": False,
        "meaning": "现有数据**无法证明**相关（≠ 没有相关素材）",
        "guard": "**严禁**把本码当作 NO_RELEVANT_CANDIDATE"},
    "INSUFFICIENT_DIVERSITY": {
        "deficiency_kind": "DIVERSITY_GAP", "acquisition_needed": True,
        "meaning": "P7-3 实测的唯一感知家族数低于**既有冻结** DQ-2 阈值（min_unique_assets=6）",
        "guard": "只复用既有阈值，不新造阈值"},
    "LICENSE_UNAVAILABLE": {
        "deficiency_kind": "LICENSE_BLOCK", "acquisition_needed": True,
        "meaning": "**被需要的**候选被许可门禁判为 DENY（RESTRICTED）⇒ 需获取许可已清的替代素材",
        "guard": "仅当 license_gate_applies=True 且判定为 DENY；UNKNOWN ⇒ 见 LICENSE_HITL_REQUIRED"},
    "LICENSE_HITL_REQUIRED": {
        "deficiency_kind": "HITL_CONFIRMATION_GAP", "acquisition_needed": False,
        "meaning": "许可信息不足（UNKNOWN）⇒ 需**人工确认**；不是『许可不可用』，更不是缺素材",
        "guard": "本码**不**产生获取请求（HITL ≠ acquisition）"},
    "REPLACEMENT_ALREADY_VERIFIED": {
        "deficiency_kind": "NONE", "acquisition_needed": False,
        "meaning": "现状所用候选被可靠证据判为不相关，但**已存在具备可靠正向证据的替代候选**"
                   "⇒ 属**采用/绑定**决策（P7-6），不属获取需求",
        "guard": "必须有替代候选的可靠正向证据；否则应判 NO_RELEVANT_CANDIDATE"},
    "PROVENANCE_INCOMPLETE": {
        "deficiency_kind": "PROVENANCE_GAP", "acquisition_needed": True,
        "meaning": "**被需要的**候选缺少可核验溯源（provider/source_id/source_url/license 证据）",
        "guard": "仅当许可门禁适用且许可为 ALLOW 时作主因；否则列入 secondary_signals（治理提示）"},
    "NO_ACQUISITION_NEEDED": {
        "deficiency_kind": "NONE", "acquisition_needed": False,
        "meaning": "现状已有可靠正向证据且无上述缺口",
        "guard": "仅在存在可靠正向证据时使用；不得用于回避 NOT_ASSESSABLE 的表达"},
}
NEGATIVE_NOT_ASSESSABLE_RULE = ("NOT_ASSESSABLE ⇒ acquisition_needed 必须为 False；"
                                "若判 NO_RELEVANT_CANDIDATE 必须给出 absence_evidence_level")

#: 许可治理（复用 core.materials 语义；**UNKNOWN 不得自动当允许**）
LICENSE_GOVERNANCE = {
    "ALLOW": {"license_classes": ["PUBLIC_DOMAIN", "FREE_ATTRIBUTION"],
              "meaning": "满足项目 license policy（署名义务按 attribution 记录）"},
    "HITL_REQUIRED": {"license_classes": ["UNKNOWN"],
                      "meaning": "许可信息不足/需人工确认 ⇒ **不得自动采用**"},
    "DENY": {"license_classes": ["RESTRICTED"],
             "meaning": "明确违反项目 license policy ⇒ 拒绝"},
    "rule": "ALLOW/HITL_REQUIRED/DENY 由 core.materials.classify_license + license_block_reason 机械判定；"
            "UNKNOWN **绝不**自动升级为 ALLOW",
}
LICENSE_BUDGET_CLASSES = ("PUBLIC_DOMAIN", "FREE_ATTRIBUTION", "RESTRICTED", "UNKNOWN")


def license_decision(license_text: str | None, license_class: str | None = None) -> dict:
    lc = license_class or classify_license(license_text)[0]
    if lc == "RESTRICTED":
        return {"decision": "DENY", "license_class": lc,
                "why": "RESTRICTED 不得入片（core.materials.license_block_reason）"}
    if lc in ("PUBLIC_DOMAIN", "FREE_ATTRIBUTION"):
        return {"decision": "ALLOW", "license_class": lc, "why": "许可已清（须记录 attribution）"}
    return {"decision": "HITL_REQUIRED", "license_class": lc or UNKNOWN,
            "why": "许可信息不足（UNKNOWN）⇒ 人工确认后才可采用"}


#: 预算（machine-readable；超预算一律 `BUDGET_EXCEEDED` fail-closed）
BUDGET_DEFAULTS = {
    "max_requests": 24,
    "max_candidates_per_request": 8,
    "max_bytes_per_candidate": 8 * 1024 * 1024,
    "max_total_bytes": 64 * 1024 * 1024,
    "max_provider_calls": 32,
    "max_retry": 2,
    "timeout_s": 20,
}


def check_budget(plan: dict, budget: dict | None = None) -> dict:
    """预算核算（fail-closed）：任一上限被触及 ⇒ `BUDGET_EXCEEDED`。"""
    b = {**BUDGET_DEFAULTS, **(budget or {})}
    reqs = len(plan.get("requests") or [])
    cand = sum(int(r.get("max_candidates") or 0) for r in (plan.get("requests") or []))
    calls = sum(int(r.get("provider_calls_planned") or 0) for r in (plan.get("requests") or []))
    est_bytes = sum(int(r.get("estimated_bytes") or 0) for r in (plan.get("requests") or []))
    checks = [
        {"name": "max_requests", "used": reqs, "limit": b["max_requests"]},
        {"name": "max_provider_calls", "used": calls, "limit": b["max_provider_calls"]},
        {"name": "max_total_bytes", "used": est_bytes, "limit": b["max_total_bytes"]},
    ]
    over = [c for c in checks if c["used"] > c["limit"]]
    for r in plan.get("requests") or []:
        if int(r.get("max_candidates") or 0) > b["max_candidates_per_request"]:
            over.append({"name": "max_candidates_per_request",
                         "request": r.get("request_id"),
                         "used": r.get("max_candidates"),
                         "limit": b["max_candidates_per_request"]})
        if int(r.get("estimated_bytes") or 0) > b["max_total_bytes"]:
            over.append({"name": "max_total_bytes(request)", "request": r.get("request_id")})
    return {"ok": not over, "code": None if not over else "BUDGET_EXCEEDED", "budget": b,
            "usage": {"requests": reqs, "candidates": cand, "provider_calls": calls,
                      "estimated_bytes": est_bytes},
            "checks": checks, "violations": over,
            "note": "超预算 ⇒ 立即停止（不重试、不降级）"}


#: fetch 安全边界（LIVE_FETCH 必须全部满足；任何一条不满足即拒绝）
FETCH_SAFETY = {
    "https_only": True, "redirects": "denied（禁跳转）",
    "content_type_validation": "必须与扩展名一致（mismatch ⇒ ASSET_EXT_MISMATCH）",
    "max_bytes_per_candidate": BUDGET_DEFAULTS["max_bytes_per_candidate"],
    "timeout_s": BUDGET_DEFAULTS["timeout_s"],
    "candidate_limit": BUDGET_DEFAULTS["max_candidates_per_request"],
    "provider_quota": "max_provider_calls={}".format(BUDGET_DEFAULTS["max_provider_calls"]),
    "totals": "max_total_bytes={}".format(BUDGET_DEFAULTS["max_total_bytes"]),
    "extension_content_match": "扩展名与 content-type 必须一致",
    "decode_validation": "下载后必须 PIL/ffprobe 可解码",
    "sha256": "下载后必须记录 path→bytes→sha256",
    "storage_boundary": "只允许写入 output/ 下的 staging 目录（禁写 src/docs/projects/baseline）",
    "forbidden": ["任意 URL 下载", "任意 redirect", "无限候选", "无限 bytes", "无限 provider retry",
                  "下载后直接绑定"],
}
ALLOWED_EXT = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".tif", ".tiff", ".bmp", ".mp4", ".webm")
CONTENT_TYPE_EXT = {"image/jpeg": (".jpg", ".jpeg"), "image/png": (".png",), "image/webp": (".webp",),
                    "image/gif": (".gif",), "image/tiff": (".tif", ".tiff"),
                    "image/bmp": (".bmp",), "video/mp4": (".mp4",), "video/webm": (".webm")}
STAGING_ROOT = "output/phase7_acquisition/staging"


class AcquisitionError(RuntimeError):
    def __init__(self, code: str, detail: str = ""):
        super().__init__("[{}] {}".format(code, detail))
        self.code = code
        self.detail = detail


def validate_fetch_url(url: str, policy: dict | None = None) -> dict:
    """URL 边界：仅 HTTPS、禁跳转（由 transport 保证）、扩展名允许、无内嵌凭据。"""
    p = {**FETCH_SAFETY, **(policy or {})}
    problems = []
    low = str(url or "").strip().lower()
    if not low:
        problems.append("EMPTY_URL")
    if p.get("https_only") and not low.startswith("https://"):
        problems.append("NON_HTTPS")
    if "@" in low.split("//")[-1].split("/")[0]:
        problems.append("URL_HAS_CREDENTIALS")
    ext = ""
    for e in ALLOWED_EXT:
        if low.split("?")[0].endswith(e):
            ext = e
            break
    if not ext:
        problems.append("EXT_NOT_ALLOWED")
    return {"ok": not problems, "problems": problems, "extension": ext or UNKNOWN,
            "code": None if not problems else "ASSET_URL_REJECTED",
            "policy": {"https_only": p["https_only"], "redirects": p["redirects"]}}


def validate_fetched_bytes(data: bytes, *, url: str, content_type: str | None,
                           max_bytes: int | None = None,
                           expected_sha256: str | None = None) -> dict:
    """下载后校验：字节上限 → content-type/扩展名一致 → sha256 → 可解码（fail-closed）。"""
    import hashlib
    import io
    lim = int(max_bytes or BUDGET_DEFAULTS["max_bytes_per_candidate"])
    out = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    if len(data) > lim:
        return {**out, "ok": False, "code": "ASSET_OVERSIZE", "why": ">{} bytes".format(lim)}
    u = validate_fetch_url(url)
    if not u["ok"]:
        return {**out, "ok": False, "code": u["code"], "why": u["problems"]}
    ct = (content_type or "").split(";")[0].strip().lower()
    allowed = CONTENT_TYPE_EXT.get(ct)
    if ct and allowed and u["extension"] not in allowed:
        return {**out, "ok": False, "code": "ASSET_EXT_MISMATCH",
                "why": "content-type {} ≠ 扩展名 {}".format(ct, u["extension"])}
    if expected_sha256 and out["sha256"] != expected_sha256:
        return {**out, "ok": False, "code": "ASSET_SHA_MISMATCH", "why": "sha256 不一致"}
    try:
        from PIL import Image
        with Image.open(io.BytesIO(data)) as im:
            out["decoded"] = {"format": im.format, "size": list(im.size)}
    except Exception as exc:                                              # noqa: BLE001
        return {**out, "ok": False, "code": "ASSET_UNDECODABLE",
                "why": "{}: {}".format(type(exc).__name__, str(exc)[:80])}
    return {**out, "ok": True, "code": None, "content_type": ct or UNKNOWN}


def staging_path(request_id: str, filename: str) -> str:
    """staging 路径（**仅允许 output/ 下**；写入由阶段脚本/显式 live 流程负责）。"""
    safe = "".join(c for c in str(filename) if c.isalnum() or c in "._-")[:120] or "candidate.bin"
    return "{}/{}/{}".format(STAGING_ROOT, str(request_id), safe)


def assert_storage_boundary(path: str) -> None:
    if not str(path).replace("\\", "/").startswith("output/"):
        raise AcquisitionError("STORAGE_BOUNDARY_VIOLATION", path)


# ------------------------------------------------------------------ request 构造
def build_request(*, requirement: dict, scene_evidence: dict, provider_policy: dict,
                  license_policy: dict, budget: dict, reason_code: str,
                  reason_detail: dict | None = None, max_candidates: int | None = None,
                  mode: str = DRY_RUN) -> dict:
    if reason_code not in REASON_CODES:
        raise AcquisitionError("UNKNOWN_REASON_CODE", reason_code)
    rc = REASON_CODES[reason_code]
    qs = [q for q in (requirement.get("queries_en") or [])]
    ladder = [list(step) for step in (requirement.get("query_ladder") or [])]
    needed = bool(rc["acquisition_needed"])
    req = {
        "schema": SCHEMA, "version": VERSION,
        "requirement_id": requirement.get("requirement_id"),
        "scene_id": requirement.get("scene_id"),
        "reason": {"code": reason_code, "deficiency_kind": rc["deficiency_kind"],
                   "meaning": rc["meaning"], "guard": rc.get("guard", UNKNOWN),
                   **({"detail": reason_detail} if reason_detail else {})},
        "acquisition_needed": needed,
        "required_evidence": ["identity(sha256)", "decode", "provenance(provider/source_id/source_url)",
                              "license(ALLOW or HITL 确认)", "integrity(尺寸/格式)",
                              "relevance(P7-4 判定，非本阶段)"],
        "queries_en": qs,
        "query_ladder": ladder,
        "fetchable": bool(qs or ladder),
        "blocked_reason": None if (qs or ladder) else "QUERY_UNAVAILABLE（P7-1 判定 queries_en "
                                                      "NOT_DERIVABLE ⇒ 不翻译、不编造查询）",
        "provider_policy": provider_policy,
        "allowed_source_types": provider_policy.get("allowed_source_types") or [],
        "license_policy": license_policy,
        "budget_policy": {**BUDGET_DEFAULTS, **(budget or {})},
        "max_candidates": int(max_candidates or BUDGET_DEFAULTS["max_candidates_per_request"]),
        "provider_calls_planned": 1 if (qs or ladder) else 0,
        "estimated_bytes": int(BUDGET_DEFAULTS["max_bytes_per_candidate"])
                           * int(max_candidates or BUDGET_DEFAULTS["max_candidates_per_request"]),
        "status": REQUESTED,
        "dry_run": mode == DRY_RUN,
        "mode": mode,
        "scene_local_evidence": scene_evidence,
        "not_assessable_is_not_absence": NEGATIVE_NOT_ASSESSABLE_RULE,
        "provenance": {"generation": "deterministic-offline",
                       "requirement_artifact": provider_policy.get("requirements_artifact_hash"),
                       "index_artifact": provider_policy.get("index_artifact_hash"),
                       "relevance_artifact": provider_policy.get("relevance_artifact_hash"),
                       "diversity_artifact": provider_policy.get("diversity_artifact_hash"),
                       "inputs_are_read_only": True},
    }
    req["request_id"] = "aq-" + sha256_text(canonical(req))[:16]
    req["deterministic_hash"] = sha256_text(canonical(req))
    return req


def build_plan(*, requirements: list[dict], scene_evidence: dict, provider_policy: dict,
               license_policy: dict, budget: dict, mode: str = DRY_RUN,
               project_signals: dict | None = None) -> dict:
    """对全部需求做 DRY-RUN 规划：只为**可机器核查的缺口**产生 request。"""
    if mode not in MODES:
        raise AcquisitionError("UNKNOWN_MODE", mode)
    requests, decisions = [], []
    for r in requirements:
        sid = r.get("scene_id")
        ev = (scene_evidence or {}).get(sid) or {}
        code, detail = decide_reason(ev, project_signals or {})
        row = {"scene_id": sid, "requirement_id": r.get("requirement_id"),
               "reason_code": code, "acquisition_needed": REASON_CODES[code]["acquisition_needed"],
               "deficiency_kind": REASON_CODES[code]["deficiency_kind"],
               "local_evidence": ev, "detail": detail}
        decisions.append(row)
        if row["acquisition_needed"]:
            requests.append(build_request(requirement=r, scene_evidence=ev,
                                          provider_policy=provider_policy,
                                          license_policy=license_policy, budget=budget,
                                          reason_code=code, reason_detail=detail, mode=mode))
    plan = {
        "schema": PLAN_SCHEMA, "version": VERSION, "mode": mode, "dry_run": mode == DRY_RUN,
        "generation_method": "deterministic-offline（DRY_RUN 零下载；LIVE_FETCH 需显式授权）",
        "state_machine": STATE_MACHINE,
        "reason_codes": REASON_CODES,
        "not_assessable_rule": NEGATIVE_NOT_ASSESSABLE_RULE,
        "license_governance": LICENSE_GOVERNANCE,
        "provider_policy": provider_policy,
        "fetch_safety": FETCH_SAFETY,
        "budget": {**BUDGET_DEFAULTS, **(budget or {})},
        "project_signals": project_signals or {},
        "decisions": decisions,
        "requests": requests,
        "counts": {"scenes": len(requirements), "requests": len(requests),
                   "acquisition_needed": sum(1 for d in decisions if d["acquisition_needed"]),
                   "not_assessable_not_absence": sum(
                       1 for d in decisions if d["reason_code"] == "NOT_ASSESSABLE_WITH_LOCAL_POOL"),
                   "by_reason": {c: sum(1 for d in decisions if d["reason_code"] == c)
                                 for c in sorted(REASON_CODES)}},
        "staging": {"root": STAGING_ROOT,
                    "policy": "新素材必须先进入 staging；**不**自动进入 AssetIndex accepted pool / "
                              "material timeline / render；ACCEPTED 需相关性 + HITL",
                    "writes_allowed_only_by": "阶段脚本或显式 LIVE_FETCH 流程（ops 只读）"},
        "live_fetch": {"implemented": True, "default_enabled": False,
                       "requires": ["--mode live", "--authorize-live", "--out-dir（output/ 下）",
                                    "已配置的真实 provider（默认 provider=none ⇒ PROVIDER_NOT_CONFIGURED）"],
                       "determinism": "LIVE_FETCH 受外部世界影响 ⇒ **不声称**同输入同结果确定性；"
                                      "每次 fetch 记录 request snapshot + provider response snapshot + sha256"},
        "bound_forbidden": "P7-5 **不修改 material timeline**（BOUND 状态不可达）",
    }
    plan["budget_check"] = check_budget(plan, budget)
    plan["artifact_hash"] = plan_hash(plan)
    return plan


def decide_reason(ev: dict, project_signals: dict) -> tuple[str, dict]:
    """reason code 决策（先命中先返回；**不得**由 NOT_ASSESSABLE 推出池缺失）。

    许可语义严格按治理：**DENY** ⇒ LICENSE_UNAVAILABLE（可获取替代）；
    **HITL_REQUIRED（UNKNOWN）** ⇒ 仅列为 secondary signal（需人工确认，不是缺素材）。
    """
    secondary = []
    lic = ev.get("current_asset_license") or {}
    if lic.get("decision") == "HITL_REQUIRED":
        secondary.append({"code": "LICENSE_HITL_REQUIRED", "license_class": lic.get("license_class"),
                          "why": "许可信息不足 ⇒ 人工确认（不产生获取请求）",
                          "license_gate_applies": lic.get("license_gate_applies")})
    if lic.get("license_gate_applies") and ev.get("provenance_incomplete_required"):
        secondary.append({"code": "PROVENANCE_INCOMPLETE",
                          "missing": ev["provenance_incomplete_required"],
                          "why": "许可门禁适用但溯源字段缺失 ⇒ 治理提示"})
    base = {"secondary_signals": secondary}
    if ev.get("current_asset_decision") == "IRRELEVANT":
        relevant_others = ev.get("other_candidates_relevant") or []
        if relevant_others:
            return "REPLACEMENT_ALREADY_VERIFIED", {
                **base, "current_asset_decision": "IRRELEVANT",
                "current_asset_evidence": ev.get("current_asset_evidence"),
                "alternative_candidates_with_reliable_positive_evidence": relevant_others,
                "note": "获取需求不成立（已有可靠替代）⇒ 属 P7-6 采用/绑定决策"}
        return "NO_RELEVANT_CANDIDATE", {
            **base, "current_asset_decision": "IRRELEVANT",
            "evidence": ev.get("current_asset_evidence"),
            "absence_evidence_level": "PROVEN_ABSENT"
            if all(o == "IRRELEVANT" for o in (ev.get("other_candidates_reliable") or ["IRRELEVANT"]))
            else "PARTIALLY_PROVEN",
            "caveat": "其余候选为 NOT_ASSESSABLE（**未能证明**）——不等于被证明不相关"}
    if lic.get("decision") == "DENY" and lic.get("license_gate_applies"):
        return "LICENSE_UNAVAILABLE", {**base, "license": lic,
                                       "why": "RESTRICTED ⇒ 需获取许可已清的替代素材"}
    if project_signals.get("diversity_below_existing_threshold"):
        return "INSUFFICIENT_DIVERSITY", {**base, "diversity": project_signals.get("diversity")}
    if ev.get("current_asset_decision") == "PARTIAL":
        return "ONLY_PARTIAL_EVIDENCE", {**base, "note": "词面证据；视觉条件未验证 ⇒ 验证能力缺口"}
    if ev.get("current_asset_decision") in ("NOT_ASSESSABLE", None):
        return "NOT_ASSESSABLE_WITH_LOCAL_POOL", {
            **base, "current_asset_decision": ev.get("current_asset_decision") or "NOT_ASSESSABLE",
            "why_not_acquisition": "无法证明相关 ≠ 没有相关素材（缺视觉判定能力，而非缺素材）"}
    return "NO_ACQUISITION_NEEDED", {**base,
                                     "current_asset_decision": ev.get("current_asset_decision")}


def plan_body(plan: dict) -> dict:
    return {k: v for k, v in plan.items() if k != "artifact_hash"}


def plan_hash(plan: dict) -> str:
    return sha256_text(canonical(plan_body(plan)))


def validate_plan(plan: dict) -> list[str]:
    errs = []
    if plan.get("schema") != PLAN_SCHEMA:
        errs.append("plan schema 非法")
    if plan.get("artifact_hash") != plan_hash(plan):
        errs.append("artifact_hash 不一致")
    if plan.get("mode") == DRY_RUN and plan.get("dry_run") is not True:
        errs.append("DRY_RUN 必须 dry_run=true")
    for d in plan.get("decisions") or []:
        if d["reason_code"] == "NOT_ASSESSABLE_WITH_LOCAL_POOL" and d["acquisition_needed"]:
            errs.append("{}: NOT_ASSESSABLE **不得**触发 acquisition".format(d["scene_id"]))
        if d["reason_code"] == "NO_RELEVANT_CANDIDATE":
            if not (d.get("detail") or {}).get("absence_evidence_level"):
                errs.append("{}: NO_RELEVANT_CANDIDATE 缺少 absence_evidence_level".format(
                    d["scene_id"]))
    for r in plan.get("requests") or []:
        if r.get("status") != REQUESTED:
            errs.append("新 request 状态必须是 REQUESTED")
        if r.get("status") == BOUND:
            errs.append("BOUND 在 P7-5 禁止")
    if not plan.get("budget_check", {}).get("ok", False):
        errs.append("BUDGET_EXCEEDED：{}".format(plan["budget_check"].get("violations")))
    tu = any(k in canonical(plan)[:400].lower() for k in ("created_utc", "generated_at"))
    if tu:
        errs.append("plan 含时间戳（破坏确定性）")
    return errs


def fetch_candidates(*, request: dict, transport, policy: dict | None = None) -> dict:
    """LIVE_FETCH 的**唯一**下载路径（transport 可注入；本阶段测试用 fake transport，零网络）。

    安全门（任一失败即 fail-closed，不重试、不降级、不落盘）：URL 边界 → 字节上限 →
    content-type/扩展名 → sha256 → 解码。
    """
    p = {**FETCH_SAFETY, **(policy or {})}
    out = {"request_id": request.get("request_id"), "fetched": [], "errors": []}
    if not request.get("dry_run") is False and request.get("mode") != LIVE_FETCH:
        raise AcquisitionError("LIVE_FETCH_NOT_AUTHORIZED",
                               "request.mode={}（默认 DRY_RUN 不得下载）".format(request.get("mode")))
    budget = request.get("budget_policy") or BUDGET_DEFAULTS
    n = 0
    for url in (request.get("fetch_urls") or []):
        if n >= int(request.get("max_candidates") or budget["max_candidates_per_request"]):
            out["errors"].append({"code": "CANDIDATE_LIMIT_REACHED",
                                  "why": "max_candidates={}".format(request.get("max_candidates"))})
            break
        u = validate_fetch_url(url, p)
        if not u["ok"]:
            out["errors"].append({"code": u["code"], "url": url, "why": u["problems"]})
            continue
        try:
            resp = transport.get(url, max_bytes=int(budget["max_bytes_per_candidate"]),
                                 timeout_s=float(budget["timeout_s"]))
        except Exception as exc:                                          # noqa: BLE001
            code = getattr(exc, "code", None) or "PROVIDER_DOWNLOAD_FAILED"
            out["errors"].append({"code": code, "url": url, "why": str(exc)[:120]})
            continue
        data = resp.get("data") if isinstance(resp, dict) else resp
        ctype = (resp or {}).get("content_type") if isinstance(resp, dict) else None
        v = validate_fetched_bytes(data, url=url, content_type=ctype,
                                   max_bytes=int(budget["max_bytes_per_candidate"]))
        if not v["ok"]:
            out["errors"].append({"code": v["code"], "url": url, "why": v.get("why")})
            continue
        sp = staging_path(request["request_id"], str(url).rsplit("/", 1)[-1] or "candidate.bin")
        assert_storage_boundary(sp)
        out["fetched"].append({"url": url, "sha256": v["sha256"], "bytes": v["bytes"],
                               "decoded": v.get("decoded"), "staging_path": sp,
                               "state": FETCHED,
                               "next": "VERIFY（identity/decode/provenance/license/integrity）"
                                       "→ LICENSE_GATE → RELEVANCE → HITL ⇒ 才可 ACCEPTED"})
        n += 1
    out["count"] = len(out["fetched"])
    out["state"] = FETCHED if out["fetched"] else REQUESTED
    out["no_auto_binding"] = "fetch 结果**不**进入 AssetIndex accepted pool / material timeline / render"
    return out
