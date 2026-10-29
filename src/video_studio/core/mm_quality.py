"""5.x Phase 5-E：多模态证据质量校准与可解释性（**只读评估层，不改任何判定逻辑**）。

**它做什么**：把 4-B（文本语义）/ 5-A（单帧 CLIP）/ 5-D（多帧时序）三层证据放到一个**冻结的小型真值集**
（`tests/fixtures/mm_truth_set_v1.json`，14 例）上并列评估，回答四个问题：
  1. 三层各自在**内容标签**（MATCH/MISMATCH/UNCERTAIN，来自人工/历史决定，不是模型输出）上表现如何？
  2. 每个判定的**证据等级**是什么（模型证据 / 规则推断 / 工程阈值 / UNKNOWN）？
  3. 判定离**决策边界**有多远（margin、top-k、投票、一致性）？阈值扰动会不会翻转结论？
  4. 层间是否**冲突**？样本/真值/模型不可用时是否 fail-closed？

**它不做什么**（授权约束）：
  · **不改** 5-A/5-D 的任何阈值或判定逻辑，**不调阈值**去提高通过率（敏感性只做**披露**）；
  · 不自动换材/选材/redo，不改时间轴/旁白/BGM，不写生产 DB、不写产物；
  · 不覆盖原结果：4-B/5-A/5-D 的报告与日志保持不变，本层只读取它们并**并列展示**；
  · 只**提出** 5-F 建议，**不实施**。

**fail-closed**：真值集缺失/非法/指纹不符、覆盖度不足、样本太少、模型不可用、层执行异常、层间冲突
→ 一律明确错误码 + 该用例记 `UNRESOLVED`，**绝不**给出"看起来通过"的结论。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

QUALITY_SCHEMA = "mm-quality-v1"

# 冻结真值集指纹（双向钉定：测试与证据脚本都会核对）
TRUTH_SET_REL = "tests/fixtures/mm_truth_set_v1.json"
TRUTH_SET_PIN = "7eb952f2797e180cf85bd84236414caf878cb617c0bc885031ef423fef1dca9e"
# 开发期首次校准运行前（含三处夹具缺陷）的草稿哈希 —— 仅作审计留痕，**不是**当前指纹
TRUTH_SET_DRAFT_SHA256 = "1a138555a25e46a15a67bbb910ad3c0fb2b993ce8264837b8299717b830999b3"

EVIDENCE_CLASSES = ("MODEL_EVIDENCE", "RULE_INFERENCE", "ENGINEERING_THRESHOLD", "UNKNOWN")

# 字段 → 证据等级（**明确区分**模型数值、规则推断、工程阈值、无法判定）
FIELD_CLASSES = {
    "domain_scores": "MODEL_EVIDENCE", "top_k": "MODEL_EVIDENCE",
    "expected_sim": "MODEL_EVIDENCE", "expected_sim_median": "MODEL_EVIDENCE",
    "expected_sim_min": "MODEL_EVIDENCE", "expected_sim_mean": "MODEL_EVIDENCE",
    "best_other_sim": "MODEL_EVIDENCE", "best_other_domain": "MODEL_EVIDENCE",
    "agg_domains": "MODEL_EVIDENCE", "vote_expected": "MODEL_EVIDENCE",
    "argmax_votes": "MODEL_EVIDENCE", "visual_stability_mean": "MODEL_EVIDENCE",
    "visual_stability_min": "MODEL_EVIDENCE", "adjacent_cos": "MODEL_EVIDENCE",
    "dispersion": "MODEL_EVIDENCE", "per_frame": "MODEL_EVIDENCE",
    "verdict": "RULE_INFERENCE", "rule_id": "RULE_INFERENCE", "code": "RULE_INFERENCE",
    "reason": "RULE_INFERENCE", "confidence": "RULE_INFERENCE",
    "delta": "RULE_INFERENCE", "median_margin": "RULE_INFERENCE", "margin": "RULE_INFERENCE",
    "min_sim": "ENGINEERING_THRESHOLD", "margin_threshold": "ENGINEERING_THRESHOLD",
    "min_vote_frac": "ENGINEERING_THRESHOLD", "min_stability_cos": "ENGINEERING_THRESHOLD",
    "split_cos": "ENGINEERING_THRESHOLD", "high_stability_cos": "ENGINEERING_THRESHOLD",
    "frames_per_scene": "ENGINEERING_THRESHOLD", "min_frames": "ENGINEERING_THRESHOLD",
    "unresolved": "UNKNOWN", "unavailable": "UNKNOWN",
}

MMQ_CODES = ("MMQ_TRUTH_MISSING", "MMQ_TRUTH_INVALID", "MMQ_TRUTH_PIN_MISMATCH",
             "MMQ_INSUFFICIENT_COVERAGE", "MMQ_INSUFFICIENT_SAMPLES", "MMQ_MODEL_UNAVAILABLE",
             "MMQ_LAYER_ERROR", "MMQ_EVIDENCE_CONFLICT", "MMQ_CASE_UNRESOLVED")

LAYERS = ("4b", "5a", "5d")
LAYER_NAMES = {"4b": "4-B 文本语义（类别式规则）", "5a": "5-A 单帧多模态（3 帧 CLIP）",
               "5d": "5-D 多帧/时序多模态（7 帧 CLIP + 时序一致性）"}


def evidence_class(field: str) -> str:
    """把报告字段映射到证据等级（未登记字段 → UNKNOWN，**不猜**）。"""
    return FIELD_CLASSES.get(str(field), "UNKNOWN")


def sha256_file(p: str | Path) -> str | None:
    try:
        h = hashlib.sha256()
        with Path(p).open("rb") as fh:
            for c in iter(lambda: fh.read(1 << 20), b""):
                h.update(c)
        return h.hexdigest()
    except OSError:
        return None


# ---------------- 真值集：加载 / 校验 / 覆盖度 / 指纹 ----------------
def load_truth_set(path: str | Path) -> tuple[dict | None, dict | None]:
    """读取真值集。失败返回 (None, {"code": MMQ_TRUTH_*})，**绝不**抛异常。"""
    p = Path(path)
    if not p.is_file():
        return None, {"code": "MMQ_TRUTH_MISSING", "detail": "真值集不存在: {}".format(p)}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return None, {"code": "MMQ_TRUTH_INVALID",
                      "detail": "真值集不是合法 JSON: {}".format(str(exc)[:160])}
    ok, errs, _cov = validate_truth_set(data)
    if not ok:
        return None, {"code": "MMQ_TRUTH_INVALID", "detail": "; ".join(errs[:6])}
    return data, None


def validate_truth_set(data: dict) -> tuple[bool, list, dict]:
    """结构 + 语义校验（纯函数）。返回 (ok, errors, coverage)。"""
    errs: list[str] = []
    if not isinstance(data, dict):
        return False, ["真值集顶层必须是对象"], {}
    schema = data.get("schema")
    if schema not in ("mm-truth-set-v1", "mm-truth-set-v2"):
        errs.append("schema 必须为 mm-truth-set-v1 或 mm-truth-set-v2，实际 {!r}".format(schema))
    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        return False, errs + ["cases 必须是非空数组"], {}
    req = data.get("coverage_requirements") or {}
    seen_ids = set()
    coverage: dict[str, int] = {}
    labels: dict[str, int] = {}
    for i, c in enumerate(cases):
        if not isinstance(c, dict):
            errs.append("case[{}] 不是对象".format(i))
            continue
        cid = c.get("id")
        if not cid:
            errs.append("case[{}] 缺 id".format(i))
        elif cid in seen_ids:
            errs.append("重复 case id: {}".format(cid))
        seen_ids.add(cid)
        if c.get("kind") not in ("real_artifact", "pair", "fixture", "probe"):
            errs.append("{}: kind 非法 {!r}".format(cid, c.get("kind")))
        if not c.get("content_label"):
            errs.append("{}: 缺 content_label".format(cid))
        if not c.get("content_label_provenance"):
            errs.append("{}: 缺 content_label_provenance（真值必须有出处）".format(cid))
        if not isinstance(c.get("expect"), dict) or not c["expect"]:
            errs.append("{}: 缺 expect".format(cid))
        else:
            for layer in c["expect"]:
                if layer not in list(LAYERS) + ["pair"]:
                    errs.append("{}: expect 层名非法 {!r}".format(cid, layer))
        if not isinstance(c.get("covers"), list) or not c["covers"]:
            errs.append("{}: 缺 covers 标注（用于覆盖度校验）".format(cid))
        for tag in c.get("covers") or []:
            coverage[tag] = coverage.get(tag, 0) + 1
        if c.get("content_label"):
            labels[c["content_label"]] = labels.get(c["content_label"], 0) + 1
    # 覆盖度要求
    for scene in req.get("scenes") or []:
        if not any(("scene:" + scene) in (c.get("covers") or []) for c in cases if isinstance(c, dict)):
            errs.append("覆盖度不足：缺少镜头 {}".format(scene))
    for lab in req.get("content_labels") or []:
        if not any(c.get("content_label") == lab for c in cases if isinstance(c, dict)):
            errs.append("覆盖度不足：缺少内容标签 {}".format(lab))
    for dim in req.get("dimensions") or []:
        if not any(("dim:" + dim) in (c.get("covers") or []) for c in cases if isinstance(c, dict)):
            errs.append("覆盖度不足：缺少维度 {}".format(dim))
    min_cases = int(req.get("min_cases") or 0)
    if min_cases and len(cases) < min_cases:
        errs.append("样本不足：{} 例 < min_cases {}".format(len(cases), min_cases))
    # ---- v2 扩展覆盖矩阵（多项目/多镜头/运动 LIMITATION 披露为必填）----
    if schema == "mm-truth-set-v2":
        mf = req.get("motion_footage") or {}
        if not isinstance(mf, dict) or "limitation" not in mf:
            errs.append("v2 必须披露 motion_footage 覆盖情况（limitation 字段）")
        if (req.get("scope") or "master") != "subset":
            projects = data.get("projects") or []
            if len(projects) < int(req.get("projects_min") or 0):
                errs.append("覆盖度不足：项目数 {} < projects_min {}".format(
                    len(projects), req.get("projects_min")))
            for pj in projects:
                if not any(("project:" + pj) in (c.get("covers") or []) for c in cases):
                    errs.append("覆盖度不足：缺少项目 {}".format(pj))
            ms = int(req.get("multi_shot_min") or 0)
            n_ms = sum(1 for c in cases if "dim:multi_shot" in (c.get("covers") or []))
            if n_ms < ms:
                errs.append("覆盖度不足：multi_shot 用例 {} < {}".format(n_ms, ms))
            if "dim:fail_closed" not in {t for c in cases for t in (c.get("covers") or [])}:
                errs.append("覆盖度不足：缺少 fail_closed 维度")
    for lab, n in (req.get("min_labeled_per_class") or {}).items():
        if labels.get(lab, 0) < int(n):
            errs.append("样本不足：标签 {} 只有 {} 例 < {}".format(lab, labels.get(lab, 0), n))
    coverage["_labels"] = labels           # type: ignore[assignment]
    coverage["_cases"] = len(cases)        # type: ignore[assignment]
    return (not errs), errs, coverage


def coverage_status(data: dict) -> dict:
    """覆盖度是否满足要求（供报告使用）。"""
    ok, errs, cov = validate_truth_set(data)
    insufficient = [e for e in errs if e.startswith(("覆盖度不足", "样本不足"))]
    return {"ok": ok and not insufficient, "errors": errs, "coverage": cov,
            "code": (None if ok else ("MMQ_INSUFFICIENT_COVERAGE" if insufficient
                                      else "MMQ_TRUTH_INVALID"))}


def pin_status(path: str | Path, expected: str = TRUTH_SET_PIN) -> dict:
    got = sha256_file(path)
    return {"path": str(path), "sha256": got, "expected": expected, "matches": got == expected}


# ---------------- 用例评估（纯函数） ----------------
def evaluate_layer(case: dict, layer: str, result: dict | None) -> dict:
    """把一个层的实际输出与真值集的 expect 比对（纯函数）。

    result: {"verdict","code","metrics":{...},"layer_error":{...}|None}
    """
    exp = (case.get("expect") or {}).get(layer)
    out = {"layer": layer, "expected": exp, "observed": None, "checks": [], "violations": [],
           "resolved": False, "evidence_class": evidence_class("verdict")}
    if exp is None:
        out["skipped"] = True
        return out
    if result is None or result.get("layer_error"):
        err = (result or {}).get("layer_error") or {"code": "MMQ_LAYER_ERROR", "detail": "无结果"}
        out["unresolved"] = err
        out["violations"].append({"rule": "layer_error", "code": err.get("code")})
        return out
    verdict, code = result.get("verdict"), result.get("code")
    out["observed"] = {"verdict": verdict, "code": code}
    allow = list(exp.get("allow") or [])
    must_not = list(exp.get("must_not") or [])
    req_codes = list(exp.get("require_code_any") or [])
    ban_codes = list(exp.get("require_not_code_any") or [])
    require_stability = exp.get("require_stability")
    out["checks"].append({"name": "allow", "expected": allow, "observed": verdict,
                          "ok": (verdict in allow) if allow else True})
    out["checks"].append({"name": "must_not", "expected": must_not, "observed": verdict,
                          "ok": (verdict not in must_not) if must_not else True})
    if req_codes:
        out["checks"].append({"name": "require_code_any", "expected": req_codes, "observed": code,
                              "ok": code in req_codes})
    if ban_codes:
        out["checks"].append({"name": "require_not_code_any", "expected": ban_codes,
                              "observed": code, "ok": code not in ban_codes})
    if require_stability:
        got_stab = ((result.get("metrics") or {}).get("stability") or {}).get("class")
        out["checks"].append({"name": "require_stability", "expected": require_stability,
                              "observed": got_stab, "ok": got_stab == require_stability})
    for chk in out["checks"]:
        if not chk["ok"]:
            out["violations"].append({"rule": chk["name"], "expected": chk["expected"],
                                      "observed": chk["observed"]})
    out["resolved"] = True
    out["ok"] = not out["violations"]
    return out


def boundary_distances(layer: str, result: dict | None) -> dict:
    """判定离**决策边界**有多远（纯函数；每条都标注证据等级）。"""
    if not result or result.get("layer_error"):
        return {}
    m = result.get("metrics") or {}
    out: dict = {"_classes": {}}
    def put(k, v, cls):
        out[k] = v
        out["_classes"][k] = cls
    if layer == "5a":
        exp, other = m.get("expected_sim"), m.get("best_other_sim")
        thr, margin = m.get("min_sim"), m.get("margin_threshold")
        if exp is not None and thr is not None:
            put("sim_above_min_sim", round(float(exp) - float(thr), 6), "MODEL_EVIDENCE")
        if exp is not None and other is not None and margin is not None:
            put("margin_above_threshold", round(abs(float(exp) - float(other)) - float(margin), 6),
                "MODEL_EVIDENCE")
            put("delta_vs_best_other", round(float(exp) - float(other), 6), "MODEL_EVIDENCE")
        put("topk_domains", [x.get("domain") for x in (m.get("top_k") or [])][:3], "MODEL_EVIDENCE")
        put("expected_in_top1", bool((m.get("top_k") or [{}])[0].get("domain") ==
                                    m.get("expected_domain")), "MODEL_EVIDENCE")
    if layer == "5d":
        med, margin = m.get("expected_sim_median"), m.get("margin_threshold")
        vote, vthr = m.get("vote_expected"), m.get("min_vote_frac")
        stab, sth = m.get("visual_stability_mean"), m.get("min_stability_cos")
        if med is not None and m.get("min_sim") is not None:
            put("sim_above_min_sim", round(float(med) - float(m["min_sim"]), 6), "MODEL_EVIDENCE")
        if med is not None and margin is not None:
            put("margin_above_threshold", round(abs(float(m.get("median_margin") or 0))
                                                - float(margin), 6), "MODEL_EVIDENCE")
        put("median_margin", m.get("median_margin"), "RULE_INFERENCE")
        if vote is not None and vthr is not None:
            put("vote_above_min_frac", round(float(vote) - float(vthr), 6), "MODEL_EVIDENCE")
        if stab is not None and sth is not None:
            put("stability_above_min", round(float(stab) - float(sth), 6), "MODEL_EVIDENCE")
        put("topk_domains", [x.get("domain") for x in (m.get("top_k") or [])][:3], "MODEL_EVIDENCE")
        put("expected_in_top1", bool((m.get("top_k") or [{}])[0].get("domain") ==
                                    m.get("expected_domain")), "MODEL_EVIDENCE")
        put("frames", m.get("frames"), "ENGINEERING_THRESHOLD")
    return out


def explain_chain(case: dict, layer: str, result: dict | None, evaluation: dict) -> list:
    """生成**可解释链**：模型证据 → 规则推断 → 工程阈值 → 结论（每步标注证据等级）。"""
    lines = []
    if result is None or result.get("layer_error"):
        err = (result or {}).get("layer_error") or {}
        return ["[UNKNOWN] {}: 层不可用（{}）→ 记 UNRESOLVED，不做任何判定".format(
            layer, err.get("code"))]
    m = result.get("metrics") or {}
    if layer == "5a":
        lines.append("[MODEL_EVIDENCE] 期望域={} 相似度={}；最强其它域={}({})；top-k={}".format(
            m.get("expected_domain"), m.get("expected_sim"), m.get("best_other_domain"),
            m.get("best_other_sim"), [x.get("domain") for x in (m.get("top_k") or [])][:3]))
        lines.append("[ENGINEERING_THRESHOLD] min_sim={} margin={}".format(
            m.get("min_sim"), m.get("margin_threshold")))
    elif layer == "5d":
        lines.append("[MODEL_EVIDENCE] 帧数={} 期望相似度(中位/最小)={}/{} 投票={} "
                     "一致性(mean/min)={}/{} top-k={}".format(
                         m.get("frames"), m.get("expected_sim_median"), m.get("expected_sim_min"),
                         m.get("vote_expected"), m.get("visual_stability_mean"),
                         m.get("visual_stability_min"),
                         [x.get("domain") for x in (m.get("top_k") or [])][:3]))
        lines.append("[ENGINEERING_THRESHOLD] min_sim={} margin={} min_vote_frac={} "
                     "min_stability_cos={} split_cos={}".format(
                         m.get("min_sim"), m.get("margin_threshold"), m.get("min_vote_frac"),
                         m.get("min_stability_cos"), m.get("split_cos")))
    else:
        lines.append("[RULE_INFERENCE] 4-B 类别式规则（无数值阈值）：verdict={} rule={}".format(
            result.get("verdict"), result.get("rule_id") or result.get("rule")))
    lines.append("[RULE_INFERENCE] 输出 verdict={} code={}".format(result.get("verdict"),
                                                                   result.get("code")))
    if evaluation.get("violations"):
        lines.append("[UNKNOWN] 与真值集不符：{}（如实记录，不调阈值消除）".format(
            evaluation["violations"]))
    else:
        lines.append("[RULE_INFERENCE] 与真值集期望一致")
    return lines


def aggregate(case_results: list) -> dict:
    """按层统计：violations / UNKNOWN / MATCH / MISMATCH / 精确率与召回（纯函数）。"""
    out = {}
    for layer in LAYERS:
        ev = [c["layers"].get(layer) for c in case_results if c["layers"].get(layer)]
        ev = [e for e in ev if not e.get("skipped")]
        resolved = [e for e in ev if e.get("resolved")]
        violations = [{"case_id": c["case_id"], "observed": e["observed"],
                       "violations": e["violations"]}
                      for c in case_results for e in [c["layers"].get(layer) or {}]
                      if e.get("violations")]
        verdicts = [(c["case_id"], (e.get("observed") or {}).get("verdict"),
                     c.get("content_label")) for c in case_results
                    for e in [c["layers"].get(layer) or {}] if e.get("resolved")]
        said_match = [x for x in verdicts if x[1] == "MATCH"]
        said_mismatch = [x for x in verdicts if x[1] == "MISMATCH"]
        content_match = [x for x in verdicts if x[2] == "MATCH"]
        content_mismatch = [x for x in verdicts if x[2] == "MISMATCH"]
        out[layer] = {
            "name": LAYER_NAMES[layer], "cases_with_expectation": len(ev),
            "resolved": len(resolved), "violations": violations,
            "violation_count": len(violations),
            "unknown_count": sum(1 for x in verdicts if x[1] == "UNKNOWN"),
            "match_count": len(said_match), "mismatch_count": len(said_mismatch),
            "match_precision_on_truth": (round(sum(1 for x in said_match if x[2] == "MATCH")
                                               / len(said_match), 6) if said_match else None),
            "mismatch_recall_on_truth": (round(sum(1 for x in content_mismatch
                                                   if x[1] == "MISMATCH")
                                               / len(content_mismatch), 6)
                                         if content_mismatch else None),
            "false_match_on_mismatch_cases": [x[0] for x in content_mismatch
                                              if x[1] == "MATCH"],
            "match_recall_on_truth": (round(sum(1 for x in content_match if x[1] == "MATCH")
                                            / len(content_match), 6) if content_match else None),
            "unknown_on_match_cases": [x[0] for x in content_match if x[1] == "UNKNOWN"],
        }
    return out


def detect_conflicts(case_results: list) -> list:
    """层间冲突：同一用例上出现 MATCH 与 MISMATCH 并存（纯函数）。"""
    conflicts = []
    for c in case_results:
        verdicts = {layer: ((c["layers"].get(layer) or {}).get("observed") or {}).get("verdict")
                    for layer in LAYERS}
        vals = {v for v in verdicts.values() if v in ("MATCH", "MISMATCH")}
        if len(vals) > 1:
            conflicts.append({"case_id": c["case_id"], "verdicts": verdicts,
                              "code": "MMQ_EVIDENCE_CONFLICT"})
    return conflicts


# ---------------- 阈值敏感性（只披露，不调参） ----------------
def sensitivity_rows(observations: list, matrix: dict) -> list:
    """对既有观测做阈值扰动复算（**不重跑模型、不修改任何配置**）。

    observations: [{"case_id","layer","kind":"5a"|"5d","payload":{...},"base_verdict":...}]
    matrix: {"margin": [+0.01, +0.02], "min_stability_cos": [+0.05, +0.10], ...}
    """
    import itertools
    from .multimodal import MM_DEFAULTS as MM5A, verdict_for_scene
    from .mm_temporal import MMT_DEFAULTS as MM5D, temporal_verdict
    keys = sorted(matrix)
    combos = []
    for values in itertools.product(*[matrix[k] for k in keys]):
        combos.append(dict(zip(keys, values)))
    rows = []
    for ob in observations:
        base = None
        variants = []
        for combo in combos:
            if ob["kind"] == "5a":
                s = {**MM5A}
                for k, val in combo.items():
                    if k in MM5A and isinstance(MM5A.get(k), (int, float)):
                        s[k] = round(float(MM5A[k]) + float(val), 6)
                v = verdict_for_scene(ob["payload"].get("domain_scores") or {},
                                      ob["payload"].get("expected_domain"), s)
                variants.append({"settings": combo, "verdict": v["verdict"], "code": v.get("code")})
            else:
                s = {**MM5D}
                for k, val in combo.items():
                    if k in s and isinstance(s.get(k), (int, float)):
                        s[k] = round(s[k] + val, 6)
                v = temporal_verdict(ob["payload"].get("metrics") or {},
                                     ob["payload"].get("expected_domain"), s)
                variants.append({"settings": combo, "verdict": v["verdict"], "code": v.get("code")})
        base_verdict = ob.get("base_verdict")
        flips = [v for v in variants if v["verdict"] != base_verdict]
        rows.append({"case_id": ob["case_id"], "layer": ob["layer"], "kind": ob["kind"],
                     "base_verdict": base_verdict, "variants": variants,
                     "flip_count": len(flips),
                     "flips": sorted({(json.dumps(v["settings"], sort_keys=True), v["verdict"])
                                      for v in flips})})
    return rows


# ---------------- 5-F 建议（只提出，不实施） ----------------
def recommendations() -> list:
    """下一阶段（5-F）建议清单 —— **仅建议**，本阶段不实施、不写配置、不改代码行为。"""
    return [
        {"id": "R1", "title": "字幕区域掩码后再算帧间一致性",
         "why": "整帧嵌入受烧录字幕影响（KNOWN_ISSUES #38：S06 侧视图 min 相邻余弦 0.814，其它镜头 ≥0.9977），"
                "掩码后一致性指标更纯粹，可减少 SPLIT/LOW_CONSISTENCY 的误报空间。",
         "cost": "中（需字幕时间轴 + 区域裁剪，2 帧/镜头各一次前向）",
         "risk": "改动 5-D 内部指标 → 必须新建 v2 指标定义并重跑真值集与全部回归",
         "implemented_in_5e": False},
        {"id": "R2", "title": "候选的\"成片抽帧口径\"预测量",
         "why": "5-B 用素材原图打分、5-A/5-D 用成片抽帧判定，口径不一致（#33：资产级更高的 side 在成片级更低）。"
                "若在候选阶段就按成片口径（裁切+叠字幕+缩放）预打分，可避免 5-C 那类'排序第一但替换后判定退化'。",
         "cost": "中（候选图片按成片参数合成后各跑一次 CLIP）",
         "risk": "属**新证据**，不得直接用于自动选材；仍需人工决定（4-C 闭环）",
         "implemented_in_5e": False},
        {"id": "R3", "title": "扩充真值集到多镜头/运动素材与更多项目",
         "why": "当前真值集 14 例全部来自**静态素材**项目（#42）；T1/T2 分支只能靠受控夹具覆盖，不可外推。",
         "cost": "高（需要新的真实素材/项目与人工标注工时）",
         "risk": "低（纯评估侧）",
         "implemented_in_5e": False},
        {"id": "R4", "title": "把 UNKNOWN 的两种语义在 UI/报告上强制区分",
         "why": "本阶段把 UNKNOWN 的 confidence 定义为\"这个 UNKNOWN 有多可靠\"（MEDIUM = 稳定地判不出来）；"
                "若不显式区分，读者容易把\"稳定不确定\"误读为\"模型坏了\"。",
         "cost": "低（仅报告/文案层）",
         "risk": "低；**不改判定**",
         "implemented_in_5e": False},
        {"id": "R5", "title": "S06 素材是否换回 front（或其它）",
         "why": "5-C 后 S06 的 5-A/5-D 均为 UNKNOWN（稳定歧义，边际 0.0061）；是否接受该退化属**产品取舍**。",
         "cost": "低（一次人工决定 + redo + 复验）",
         "risk": "中：换材会改变交付画面；**必须**人工决定，禁止自动执行",
         "implemented_in_5e": False},
        {"id": "R6", "title": "把「期望域是否 top-1」作为**解释性指标**纳入报告",
         "why": "5-E 真值集上：内容-MATCH 用例的期望域**全部**是 top-1，内容-MISMATCH 用例的 top-1 都是其它域"
                "（`wildlife`）；top-1 一致性与内容标签 100% 吻合，比 margin 更直观，适合作为**人读解释**。",
         "cost": "低（报告层加一列，不新增模型调用）",
         "risk": "**不得**作为判定规则：样本仅 14 例、且与 margin 规则高度相关（#47）；"
                 "若要变成规则，必须新授权 + 扩充真值集 + 重跑全部回归",
         "implemented_in_5e": False},
    ]
