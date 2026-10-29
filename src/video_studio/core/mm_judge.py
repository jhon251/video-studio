"""5.x Phase 5-F：多模态证据 Judge（最终职责边界与证据融合，**只读、零动作**）。

**它做什么**：把 4-B（文本语义）/ 5-A（单帧多模态）/ 5-D（多帧时序）三层**独立原始证据**按**显式规则**
融合成**最终判定**，并给出：命中规则、证据优先级、冲突处理、理由链。
在**冻结的 14 例真值集**（`tests/fixtures/mm_truth_set_v1.json`）与其**Judge 真值覆盖层**
（`tests/fixtures/mm_judge_truth_v1.json`）上验证「最终判据」的收敛性。

**判定语义（本阶段的最终口径）**：
  · `MISMATCH` = **任何一层报 MISMATCH 且无一层报 MATCH**（错配必须被拦住；flagging 是安全动作）；
  · `MATCH` = **全部可用层一致报 MATCH**（MATCH 是断言，需要所有证据不反对）；
  · `UNKNOWN` = **其余一切情况**，包括：结构性 UNKNOWN（镜头内切换/帧数不足/一致性不足）、层间冲突、
    部分层 UNKNOWN、期望域缺失、模型不可用。**UNKNOWN 是合法最终结果**。

**它不做什么**（授权约束，逐条对应）：
  · **不改** 4-B/5-A/5-D 的阈值与判定逻辑；**不覆盖**它们的原始结果（只读取并并列保留）；
  · **不通过调阈值减少 UNKNOWN**（本模块没有任何阈值参数可调）；
  · 不换材、不选材、不 redo、不改时间轴/旁白/BGM、不写生产 DB、不写产物；
  · 不追求提高 MATCH 率：MATCH 必须满足"全层一致"，宁可 UNKNOWN。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .mm_quality import TRUTH_SET_PIN, TRUTH_SET_REL  # noqa: F401

JUDGE_SCHEMA = "mm-judge-v1"

JUDGE_TRUTH_REL = "tests/fixtures/mm_judge_truth_v1.json"
JUDGE_TRUTH_PIN = "a6332858a94d4a7f1a808ca7e4e5c93b2921b52418fc018054ec451a16c49d1d"

LAYERS = ("4b", "5a", "5d")
LAYER_ROLE = {
    "4b": "4-B 文本语义（类别式规则，冻结真值钉定；**只看文本与素材名，不看画面**）",
    "5a": "5-A 单帧多模态（CLIP，3 帧平均；**看画面但样本少**）",
    "5d": "5-D 多帧/时序多模态（CLIP，7 帧 + 帧间一致性 + 逐帧投票；**证据最丰富、能发现镜头内切换**）",
}

# 最终判定规则（显式、可复算；**先命中先返回**）
JUDGE_RULES = {
    "J0_FAIL_CLOSED": "所有可用层都不成立（模型/解释器不可用、无帧、无证据）→ UNKNOWN",
    "J1_STRUCTURAL_UNKNOWN": ("5-D 报出结构性 UNKNOWN（MMT_TEMPORAL_SPLIT / MMT_INSUFFICIENT_FRAMES / "
                              "MMT_LOW_CONSISTENCY）→ UNKNOWN（画面在时间轴上不是稳定状态，语义结论无意义）"),
    "J2_EVIDENCE_CONFLICT": "同时存在 MATCH 与 MISMATCH → UNKNOWN（不选边，交人工）",
    "J3_MISMATCH": "存在 MISMATCH 且无 MATCH → MISMATCH（错配必须被拦住）",
    "J4_UNANIMOUS_MATCH": "全部可用层一致 MATCH（且可用层 ≥ 2）→ MATCH",
    "J5_INSUFFICIENT_LAYERS": "仅 1 层可用且其判 MATCH → UNKNOWN（单层不足以宣称 MATCH）",
    "J6_UNRESOLVED": "其余情况（全 UNKNOWN / 部分 UNKNOWN / 期望域缺失）→ UNKNOWN",
}

# 证据优先级（决策时谁先说话；**不是**"谁更权威"的简单排序）
EVIDENCE_PRIORITY = [
    {"rank": 1, "name": "结构性证据（5-D 时序/样本）", "rule": "J1",
     "why": "镜头内切换/帧数不足/一致性不足时，任何语义判定都失去前提 → 最高优先级，且不可被 MATCH 覆盖"},
    {"rank": 2, "name": "冲突（任意两层对立）", "rule": "J2",
     "why": "层间互相矛盾说明证据不足以收敛 → 不选边，输出 UNKNOWN 并显式记录冲突"},
    {"rank": 3, "name": "错配（任一层 MISMATCH）", "rule": "J3",
     "why": "把内容错配漏过去是**高代价错误**；flagging 是安全动作（人工会复核）"},
    {"rank": 4, "name": "一致 MATCH（全层一致）", "rule": "J4",
     "why": "MATCH 是断言：必须所有可用证据层都不反对；单层/部分层一致不足以宣称"},
    {"rank": 5, "name": "无法收敛（其余）", "rule": "J0/J5/J6",
     "why": "UNKNOWN 是**合法最终结果**：交人工或补证据，**禁止**靠调阈值消除"},
]

JUDGE_CODES = ("JUDGE_MODEL_UNAVAILABLE", "JUDGE_NO_EVIDENCE", "JUDGE_STRUCTURAL_UNKNOWN",
               "JUDGE_EVIDENCE_CONFLICT", "JUDGE_MISMATCH_FLAGGED", "JUDGE_UNANIMOUS_MATCH",
               "JUDGE_INSUFFICIENT_LAYERS", "JUDGE_PARTIAL_UNKNOWN", "JUDGE_ALL_UNKNOWN",
               "JUDGE_UNKNOWN_DOMAIN")

STRUCTURAL_5D_CODES = ("MMT_TEMPORAL_SPLIT", "MMT_INSUFFICIENT_FRAMES", "MMT_LOW_CONSISTENCY")
MODEL_UNAVAILABLE_CODES = ("MM_MODEL_MISSING", "MM_PYTHON_MISSING", "MM_BACKEND_MISSING",
                           "MMT_NO_FRAMES", "MM_NO_FRAMES", "MM_WORKER_FAILED", "MM_TIMEOUT",
                           "MM_PARSE_FAILED", "MMT_UNKNOWN_DOMAIN", "MM_UNKNOWN_DOMAIN")


def sha256_file(p: str | Path) -> str | None:
    try:
        h = hashlib.sha256()
        with Path(p).open("rb") as fh:
            for c in iter(lambda: fh.read(1 << 20), b""):
                h.update(c)
        return h.hexdigest()
    except OSError:
        return None


# ---------------- Judge 真值覆盖层 ----------------
def load_judge_truth(path: str | Path) -> tuple[dict | None, dict | None]:
    p = Path(path)
    if not p.is_file():
        return None, {"code": "MMJ_TRUTH_MISSING", "detail": "Judge 真值覆盖层不存在: {}".format(p)}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return None, {"code": "MMJ_TRUTH_INVALID", "detail": str(exc)[:160]}
    return data, None


def validate_judge_truth(data: dict, truth_set: dict) -> tuple[bool, list]:
    """校验覆盖层：schema、case 集合与冻结真值集**完全一致**、期望字段合法、理由码已知、UNKNOWN 下限一致。"""
    errs: list[str] = []
    if not isinstance(data, dict) or data.get("schema") != "mm-judge-truth-v1":
        return False, ["Judge 真值覆盖层 schema 必须为 mm-judge-truth-v1"]
    ref = data.get("truth_set_ref") or {}
    if ref.get("sha256") != TRUTH_SET_PIN:
        errs.append("truth_set_ref.sha256 与冻结真值集指纹不一致（{} vs {}）".format(
            ref.get("sha256"), TRUTH_SET_PIN))
    codes = set((data.get("reason_codes") or {}).keys())
    cases = data.get("cases") or []
    ids = [c.get("case_id") for c in cases]
    if len(ids) != len(set(ids)):
        errs.append("case_id 重复")
    frozen_ids = {c.get("id") for c in (truth_set.get("cases") or [])}
    missing = sorted(frozen_ids - set(ids))
    extra = sorted(set(ids) - frozen_ids)
    if missing:
        errs.append("覆盖层缺少用例: {}".format(missing))
    if extra:
        errs.append("覆盖层出现冻结真值集之外的用例: {}".format(extra))
    for c in cases:
        cid = c.get("case_id")
        e = c.get("judge_expect")
        if not isinstance(e, dict) or not e:
            errs.append("{}: 缺 judge_expect".format(cid))
            continue
        if not c.get("rationale"):
            errs.append("{}: 缺 rationale（最终判据必须有理由）".format(cid))
        v = e.get("verdict")
        if v not in (None, "MATCH", "MISMATCH", "UNKNOWN"):
            errs.append("{}: verdict 非法 {!r}".format(cid, v))
        for req in (e.get("require") or []):
            if req not in ("MATCH", "MISMATCH", "UNKNOWN"):
                errs.append("{}: require 中出现非三态值 {!r}".format(cid, req))
        for rc in (e.get("require_reason_any") or []):
            if rc not in codes:
                errs.append("{}: 未知理由码 {!r}".format(cid, rc))
        for rc in (e.get("require_pair_checks") or []):
            if not isinstance(rc, str):
                errs.append("{}: require_pair_checks 元素非法".format(cid))
    pol = data.get("unknown_policy") or {}
    if pol.get("legitimate_final_outcome") is not True:
        errs.append("unknown_policy.legitimate_final_outcome 必须为 true（UNKNOWN 是合法最终结果）")
    min_u = int(pol.get("min_unknown_cases") or 0)
    expect_u = sum(1 for c in cases
                   if (c.get("judge_expect") or {}).get("verdict") == "UNKNOWN"
                   or "UNKNOWN" in ((c.get("judge_expect") or {}).get("require") or []))
    if min_u and expect_u < min_u:
        errs.append("UNKNOWN 下限 {} > 覆盖层要求的 UNKNOWN 用例数 {}".format(min_u, expect_u))
    return (not errs), errs


def judge_truth_status(data: dict, truth_set: dict, path: str | Path | None = None) -> dict:
    ok, errs = validate_judge_truth(data, truth_set)
    pin = {"path": str(path) if path else None, "sha256": sha256_file(path) if path else None,
           "expected": JUDGE_TRUTH_PIN,
           "matches": (sha256_file(path) == JUDGE_TRUTH_PIN) if path else None}
    return {"ok": ok, "errors": errs, "pin": pin,
            "code": None if ok else "MMJ_TRUTH_INVALID"}


# ---------------- 核心：单镜头判定（纯函数） ----------------
def judge_scene(layers: dict) -> dict:
    """把三层结果融合成**最终判定**（纯函数；无任何阈值参数）。

    layers: {"4b": {"verdict","code"}, "5a": {...}, "5d": {...}}（缺层 / `layer_error` 视为不可用）
    """
    avail, verdicts, codes = {}, {}, {}
    for k in LAYERS:
        r = layers.get(k) or {}
        if r.get("layer_error"):
            avail[k] = False
            codes[k] = (r.get("layer_error") or {}).get("code")
            continue
        v = r.get("verdict")
        if v is None:
            avail[k] = False
            continue
        avail[k] = True
        verdicts[k] = v
        codes[k] = r.get("code")
    used = sorted(verdicts)
    base = {"layer_verdicts": verdicts, "layer_codes": codes, "layers_available": used,
            "layers_unavailable": sorted(k for k in LAYERS if not avail.get(k)),
            "rules": judge_rules_table()}
    if not verdicts:
        code = "JUDGE_MODEL_UNAVAILABLE" if any(
            (codes.get(k) or "") in MODEL_UNAVAILABLE_CODES for k in LAYERS) else "JUDGE_NO_EVIDENCE"
        return {**base, "verdict": "UNKNOWN", "reason_code": code, "rule": "J0_FAIL_CLOSED",
                "priority_rank": 5, "unknown_is_final": True,
                "rationale": "没有任何可用层证据 → fail-closed（不伪造判定）"}
    v5d, c5d = verdicts.get("5d"), codes.get("5d")
    if v5d == "UNKNOWN" and c5d in STRUCTURAL_5D_CODES:
        return {**base, "verdict": "UNKNOWN", "reason_code": "JUDGE_STRUCTURAL_UNKNOWN",
                "rule": "J1_STRUCTURAL_UNKNOWN", "priority_rank": 1, "propagated_code": c5d,
                "unknown_is_final": True,
                "rationale": ("5-D 报出结构性 UNKNOWN（{}）：画面在时间轴上不是一个稳定状态 / 样本不足 → "
                              "任何语义判定都失去前提").format(c5d)}
    if "MATCH" in verdicts.values() and "MISMATCH" in verdicts.values():
        who = {k: v for k, v in verdicts.items() if v in ("MATCH", "MISMATCH")}
        return {**base, "verdict": "UNKNOWN", "reason_code": "JUDGE_EVIDENCE_CONFLICT",
                "rule": "J2_EVIDENCE_CONFLICT", "priority_rank": 2, "conflict": who,
                "unknown_is_final": True,
                "rationale": "层间冲突（{}）→ 不选边，交人工复核".format(who)}
    if "MISMATCH" in verdicts.values():
        who = sorted(k for k, v in verdicts.items() if v == "MISMATCH")
        return {**base, "verdict": "MISMATCH", "reason_code": "JUDGE_MISMATCH_FLAGGED",
                "rule": "J3_MISMATCH", "priority_rank": 3, "flagged_by": who,
                "unknown_is_final": False,
                "rationale": "存在 MISMATCH（{}）且无 MATCH → 最终 MISMATCH（错配必须被拦住）".format(who)}
    if verdicts and all(v == "MATCH" for v in verdicts.values()):
        if len(verdicts) >= 2:
            return {**base, "verdict": "MATCH", "reason_code": "JUDGE_UNANIMOUS_MATCH",
                    "rule": "J4_UNANIMOUS_MATCH", "priority_rank": 4, "unknown_is_final": False,
                    "rationale": "全部可用层（{}）一致 MATCH → 最终 MATCH".format(used)}
        return {**base, "verdict": "UNKNOWN", "reason_code": "JUDGE_INSUFFICIENT_LAYERS",
                "rule": "J5_INSUFFICIENT_LAYERS", "priority_rank": 5, "unknown_is_final": True,
                "rationale": "仅 1 层可用（{}）且其判 MATCH → 单层不足以宣称 MATCH".format(used)}
    all_unknown = all(v == "UNKNOWN" for v in verdicts.values())
    any_domain = any((codes.get(k) or "").endswith("UNKNOWN_DOMAIN") for k in verdicts)
    if all_unknown and any_domain:
        code, why = "JUDGE_UNKNOWN_DOMAIN", "旁白推不出期望语义域（词表未命中）→ 不猜"
    elif all_unknown:
        code, why = "JUDGE_ALL_UNKNOWN", "全部可用层均 UNKNOWN → 无法收敛"
    else:
        code, why = ("JUDGE_PARTIAL_UNKNOWN",
                     "部分层判 MATCH、部分层 UNKNOWN 且无 MISMATCH → 保守共识：不宣称 MATCH")
    return {**base, "verdict": "UNKNOWN", "reason_code": code, "rule": "J6_UNRESOLVED",
            "priority_rank": 5, "unknown_is_final": True, "rationale": why}


def judge_rules_table() -> list:
    return [{"rule": k, "description": v} for k, v in JUDGE_RULES.items()]


# ---------------- 真值集上的最终评估 ----------------
def evaluate_judge_case(judge_expect: dict, scene_result: dict | None,
                        pair_result: dict | None = None) -> dict:
    """按 Judge 真值覆盖层逐条检查（纯函数）。"""
    exp = judge_expect or {}
    out = {"checks": [], "violations": [], "resolved": False}
    if exp.get("verdict") is None and exp.get("require_pair_checks"):
        checks = {c.get("name"): c.get("ok") for c in ((pair_result or {}).get("checks") or [])}
        for need in exp["require_pair_checks"]:
            out["checks"].append({"name": "pair_check:" + need, "observed": checks.get(need),
                                  "ok": checks.get(need) is True})
        out["observed"] = {"pair": checks}
        out["resolved"] = bool(checks)
        out["violations"] = [c for c in out["checks"] if not c["ok"]]
        out["ok"] = not out["violations"]
        return out
    if scene_result is None:
        out["unresolved"] = {"code": "MMJ_NO_SCENE_RESULT"}
        out["violations"] = [{"rule": "missing_result"}]
        return out
    v, rc = scene_result.get("verdict"), scene_result.get("reason_code")
    out["observed"] = {"verdict": v, "reason_code": rc, "rule": scene_result.get("rule")}
    allow = list(exp.get("allow") or [])
    must_not = list(exp.get("must_not") or [])
    required = list(exp.get("require") or [])
    req_rc = list(exp.get("require_reason_any") or [])
    if required:
        out["checks"].append({"name": "require", "expected": required, "observed": v,
                              "ok": v in required})
    if allow:
        out["checks"].append({"name": "allow", "expected": allow, "observed": v, "ok": v in allow})
    if must_not:
        out["checks"].append({"name": "must_not", "expected": must_not, "observed": v,
                              "ok": v not in must_not})
    if req_rc:
        out["checks"].append({"name": "require_reason_any", "expected": req_rc, "observed": rc,
                              "ok": rc in req_rc})
    out["resolved"] = True
    out["violations"] = [c for c in out["checks"] if not c["ok"]]
    out["ok"] = not out["violations"]
    return out


def judge_summary(rows: list, judge_truth: dict) -> dict:
    """汇总结论：三态分布、UNKNOWN 合法性、理由码覆盖、冲突数。"""
    counts = {"MATCH": 0, "MISMATCH": 0, "UNKNOWN": 0}
    reasons: dict[str, int] = {}
    for r in rows:
        v = (r.get("judge") or {}).get("verdict")
        if v in counts:
            counts[v] += 1
        rc = (r.get("judge") or {}).get("reason_code")
        if rc:
            reasons[rc] = reasons.get(rc, 0) + 1
    pol = judge_truth.get("unknown_policy") or {}
    min_u = int(pol.get("min_unknown_cases") or 0)
    return {"counts": counts, "reason_codes": reasons,
            "unknown_is_legitimate": pol.get("legitimate_final_outcome") is True,
            "unknown_min_required": min_u,
            "unknown_at_least_min": counts["UNKNOWN"] >= min_u,
            "conflicts": sum(1 for r in rows
                             if (r.get("judge") or {}).get("reason_code") ==
                             "JUDGE_EVIDENCE_CONFLICT"),
            "thresholds_touched": False,
            "note": "UNKNOWN 是合法最终结果；本层无任何阈值参数，不存在『调阈值减少 UNKNOWN』的路径"}


# ---------------- 最终 DoD（可度量条款） ----------------
def dod_checklist(*, layers_independent: dict, read_only: dict, truth: dict, judge_ok: dict,
                  regression: dict, unknown: dict, dispositions: dict) -> list:
    """最终多模态 DoD：每条都是**可度量**的布尔条款 + 证据指针。"""
    return [
        {"id": "D1", "item": "三层证据独立且可单独复算（各自 CLI + 冻结证据 + 模块哈希）",
         "ok": all(layers_independent.get(k) for k in ("4b", "5a", "5d")),
         "evidence": "run.py semantic-check / multimodal-check / mm-temporal；模块哈希见 evidence.json"},
        {"id": "D2", "item": "三层默认关闭/只读，且任何层都不写生产状态（DB/产物/时间轴/选材）",
         "ok": bool(read_only.get("db_unchanged") and read_only.get("project_files_unchanged")
                    and read_only.get("static_no_write_tokens")),
         "evidence": "readonly_and_preservation"},
        {"id": "D3", "item": "三层原始结果**不被覆盖**（模块与词表 sha256 与上一基线一致；重跑结果与冻结证据一致）",
         "ok": bool(read_only.get("modules_unchanged") and read_only.get("outputs_unchanged")),
         "evidence": "readonly_and_preservation"},
        {"id": "D4", "item": "冻结真值集（14 例）指纹钉定 + 覆盖度 fail-closed + Judge 覆盖层 case 集合完全一致",
         "ok": bool(truth.get("truth_pin_matches") and truth.get("coverage_ok")
                    and truth.get("judge_case_set_equal")),
         "evidence": "truth_set / judge_truth"},
        {"id": "D5", "item": "Judge 规则显式（J0–J6）+ 证据优先级（5 级）+ 冲突处理（不选边→UNKNOWN）",
         "ok": bool(judge_ok.get("rules_documented") and judge_ok.get("priority_documented")
                    and judge_ok.get("conflict_rule_present")),
         "evidence": "judge.rules / judge.priority"},
        {"id": "D6", "item": "在冻结真值集上**逐例**满足 Judge 真值（0 违例 / 0 未解决）",
         "ok": bool((judge_ok.get("cases_total") or 0) > 0 and judge_ok.get("violations") == 0
                    and judge_ok.get("unresolved") == 0),
         "evidence": "judge.rows"},
        {"id": "D7", "item": "UNKNOWN 为合法最终结果：最终 UNKNOWN 数 ≥ 覆盖层下限，且不存在任何阈值调参路径",
         "ok": bool(unknown.get("unknown_at_least_min") and unknown.get("unknown_is_legitimate")
                    and unknown.get("thresholds_touched") is False),
         "evidence": "judge.summary"},
        {"id": "D8", "item": "fail-closed 齐备（模型/解释器/帧/期望域/冲突/真值/覆盖度 七类均映射到最终 UNKNOWN 或显式冲突）",
         "ok": bool(judge_ok.get("fail_closed_covered")),
         "evidence": "judge.rules J0/J1/J2/J6 + 5-E fail_closed"},
        {"id": "D9", "item": "全量回归 3-A～5-E 通过，且既有冻结证据零漂移",
         "ok": bool(regression.get("all_rc_zero_except_network_batch")
                    and regression.get("frozen_logs_restored")
                    and (regression.get("unit_suites") or {}).get("failed") == []),
         "evidence": "regression"},
        {"id": "D10", "item": "已知限制逐项处置完成（#43–#48 保留/解决/转入最终已知问题；#49+ 新登记）",
         "ok": bool(dispositions.get("all_classified")),
         "evidence": "dispositions"},
        {"id": "D11", "item": "不自动动作：Judge 只输出判定与理由（不换材/不选材/不 redo/不改时间轴）",
         "ok": True,
         "evidence": "policy（机器可读声明）+ 静态扫描"},
        {"id": "D12", "item": "交付物齐备：报告 + DoD + evidence.json + 已知问题 + baseline + SHA256",
         "ok": bool(judge_ok.get("deliverables_complete")),
         "evidence": "report / dod / evidence.json / baseline"},
    ]


# ---------------- #43–#48 与 R1–R6 的处置（数据，静态） ----------------
def dispositions_43_48() -> list:
    return [
        {"id": "#43", "title": "真值集小且同质（14 例、同一静态素材项目）",
         "decision": "保留（转入最终已知问题）",
         "why": "在现有素材范围内无法扩大；扩充需新素材与人工标注工时（见 R3）。"
                "因此最终 DoD 明确：**校准与 Judge 结论只在 14 例口径内成立**。",
         "evidence": "PHASE5F_MULTIMODAL_DOD.md §限制；logs/phase5f_evidence.json → dispositions"},
        {"id": "#44", "title": "\"MATCH 精确率 = 1.0\" 仅在 14 例上成立",
         "decision": "保留（口径已限定，转入最终已知问题）",
         "why": "指标口径已写明；Judge 进一步降低 MATCH 的宣称强度（全层一致），不会放大该结论。",
         "evidence": "PHASE5F_REPORT.md §4"},
        {"id": "#45", "title": "5-A/5-D 对\"内容正确但区分度不足\"的镜头给 UNKNOWN",
         "decision": "解决（口径固化）",
         "why": "5-F 把该行为**提升为最终判据**：MATCH 需全层一致，部分层 UNKNOWN → 最终 UNKNOWN。"
                "它不再是\"层的保守\"，而是**系统最终语义**（UNKNOWN 合法）。",
         "evidence": "JUDGE_RULES.J6 + T06/T08 的 judge 期望"},
        {"id": "#46", "title": "阈值敏感性：放宽 margin 会把 UNKNOWN 变 MATCH",
         "decision": "解决（禁止路径写死）",
         "why": "Judge 层**不含任何阈值参数**，并显式声明 `thresholds_touched=false`；"
                "DoD D7 要求 UNKNOWN 数 ≥ 下限（调阈值减少 UNKNOWN 会直接破坏真值集）。",
         "evidence": "mm_judge.py（无阈值参数）+ judge.summary"},
        {"id": "#47", "title": "top-1 一致性只作解释性指标",
         "decision": "保留（未来研究项，见 R6）",
         "why": "样本不足以支撑规则化；5-F 不将其纳入 Judge 判定。",
         "evidence": "recommendations_disposition → R6"},
        {"id": "#48", "title": "5-E 真值集开发期修正三处夹具缺陷并重新定稿",
         "decision": "解决（留痕 + 双指纹钉定）",
         "why": "初稿/定稿哈希均已留档于 evidence.json；本阶段再次核验指纹一致，无残留动作。",
         "evidence": "logs/phase5e_evidence.json → truth_set_history；A6 测试"},
    ]


def recommendations_disposition() -> list:
    return [
        {"id": "R1", "title": "字幕区域掩码后再算帧间一致性",
         "decision": "未来研究项（不进 5-F）",
         "why": "会改动 5-D 内部指标定义 → 需新授权 + v2 指标 + 全量回归；本阶段目标只是**确定职责边界**。",
         "risk_if_forced": "改动最成熟的时序证据层，收益（更纯的一致性）不足以抵消回归面"},
        {"id": "R2", "title": "候选的\"成片抽帧口径\"预测量",
         "decision": "未来研究项（不进 5-F）",
         "why": "属**新证据能力**（5-B 侧），且必须保持\"只作证据、不驱动自动选材\"；需单独授权。",
         "risk_if_forced": "容易被误用为自动排序/自动选材依据，违反人审闭环"},
        {"id": "R3", "title": "扩充真值集（多镜头/运动素材/更多项目）",
         "decision": "**值得进入最终产品**（评估侧，建议作为 5.x Final 之后的第一优先项）",
         "why": "纯评估、无行为风险，且直接决定 #43/#44 的可信度边界。",
         "risk_if_forced": "无行为风险；成本是素材与人工标注工时"},
        {"id": "R4", "title": "报告层强制区分 UNKNOWN 的两种语义（\"稳定不确定\" vs \"环境/样本不足\"）",
         "decision": "**值得进入最终产品**（报告/文案层，零判定风险）",
         "why": "5-F 已在 Judge 里把两者分成不同理由码（J1/J0/J6），把同样的区分带进生产报告是纯展示改动。",
         "risk_if_forced": "无（不改判定）；仅需文案评审"},
        {"id": "R5", "title": "S06 素材是否换回 front（或其它）",
         "decision": "产品决策（非技术项，不进 5-F）",
         "why": "属**人的取舍**：Judge 保持 UNKNOWN；若人工要 MATCH，必须走 4-C 人工决定 + redo + 复验。",
         "risk_if_forced": "自动换材会破坏 4-C 人审闭环（授权明确禁止）"},
        {"id": "R6", "title": "把 top-1 域一致性作为解释性指标纳入报告",
         "decision": "**值得进入最终产品**（仅展示，附 #47 警告）",
         "why": "零判定风险、提升可解释性；必须标注\"非判据、样本小\"。",
         "risk_if_forced": "若被当作判据使用，会在小样本上过拟合（#47）"},
    ]


def deliverable_scope() -> dict:
    """最终职责边界（供 DoD/报告引用）。"""
    return {
        "4b": {"role": LAYER_ROLE["4b"], "authority": "文本语义权威（冻结真值钉定的类别式规则）",
               "sees_pixels": False,
               "used_for": ["文本↔素材语义一致性（含真值回归）", "Judge 的文本侧票"],
               "not_used_for": ["画面内容判断（看不到画面）", "镜头内时序问题"]},
        "5a": {"role": LAYER_ROLE["5a"], "authority": "像素语义的第一层证据（3 帧）",
               "sees_pixels": True,
               "used_for": ["画面域与旁白期望域的一致性", "与 5-D 交叉验证"],
               "not_used_for": ["镜头内时序/切换检测（3 帧样本太少）",
                                "单独断言 MATCH（Judge 要求多层一致）"]},
        "5d": {"role": LAYER_ROLE["5d"], "authority": "像素语义 + 时序结构的最高证据层",
               "sees_pixels": True,
               "used_for": ["多帧一致性/时序切换检测（结构性 UNKNOWN 的**唯一**来源）",
                            "逐帧投票与边际分布（可解释性）"],
               "not_used_for": ["单独断言 MATCH（仍需文本层一致）", "自动换材/选材"]},
        "judge": {"role": "三层证据的**融合与最终判定**（只读、零动作）",
                  "authority": "最终三态 + 理由码（J0–J6）",
                  "used_for": ["最终 MATCH/MISMATCH/UNKNOWN 与理由码", "证据优先级与冲突处理",
                               "在冻结真值集上的收敛性验证与 DoD 核对"],
                  "not_used_for": ["自动换材/选材/redo/改时间轴", "写库或写产物",
                                   "调阈值（本层无任何阈值参数）"]},
    }
