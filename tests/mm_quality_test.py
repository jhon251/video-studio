"""5.x Phase 5-E 单测：多模态证据质量校准与可解释性（**只读评估层**）。

覆盖授权要求：
  A 冻结真值集：结构/语义校验、覆盖度、样本量、指纹钉定（改了真值集不更新指纹 → 必失败）
  B 评估逻辑：allow / must_not / require_code_any / require_not_code_any / require_stability；
    层不可用 → UNRESOLVED；边界距离；可解释链（模型证据→规则推断→工程阈值→结论）
  C 指标：精确率/召回/UNKNOWN/违例计数；层间冲突检测
  D 阈值敏感性：只披露不调参；**收紧**会使边界用例翻转、**放宽**会把 UNKNOWN 变 MATCH（必须被标注为"更松"）
  E **真实校准**：真实项目 + 真实 CLIP → 14/14 OK、0 冲突、fail-closed 齐备；与冻结证据一致、两次运行一致
  F 只读与不覆盖：DB/项目文件零变更；4-B/5-A/5-D 模块哈希未变；5-A/5-D 输出未被覆盖
  G 5-F 建议：仅建议、`implemented_in_5e=False`；报告声明 `changes_thresholds=False`

用法：python tests/mm_quality_test.py
"""
import hashlib
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core import mm_quality as Q  # noqa: E402
from video_studio.core.mm_quality import (TRUTH_SET_PIN, TRUTH_SET_REL,  # noqa: E402
                                          aggregate, boundary_distances, detect_conflicts,
                                          evaluate_layer, evidence_class, explain_chain,
                                          load_truth_set, pin_status, recommendations,
                                          sensitivity_rows, sha256_file, validate_truth_set)
from video_studio.ops.mm_quality import calibration_report, format_mmq  # noqa: E402

REAL_DB = ROOT / "projects" / "video_studio.db"
REAL_PID = "p_f4b466a4a024"
TRUTH = ROOT / TRUTH_SET_REL
FROZEN_CAL = ROOT / "docs" / "regression_2x" / "logs" / "phase5e_quality.json"
BASE_MANIFEST = (ROOT / "docs" / "regression_2x" / "baseline" /
                 "baseline_manifest_5.x-phase5d-baseline.json")
PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(("PASS  " if ok else "FAIL  ") + name + (" | " + str(detail)[:240] if detail else ""))


def sha(p: Path):
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()
    except OSError:
        return None


def project_state():
    con = sqlite3.connect(str(REAL_DB))
    counts = {t: con.execute("select count(*) from {}".format(t)).fetchone()[0]
              for t in ("tasks", "artifacts", "events", "decisions", "changelog")}
    con.close()
    proj = REAL_DB.parent / REAL_PID
    files = {str(p.relative_to(proj)): sha(p) for p in sorted(proj.rglob("*")) if p.is_file()}
    return {"db": sha(REAL_DB), "counts": counts, "files": files}


BEFORE = project_state()
TS = json.loads(TRUTH.read_text(encoding="utf-8"))

# ============ A. 冻结真值集 ============
print("== A. 冻结真值集（结构/覆盖度/指纹） ==")
ok, errs, cov = validate_truth_set(TS)
check("A1 真值集结构与语义合法（14 例；schema/kind/label/provenance/expect/covers 齐备）",
      ok and len(TS["cases"]) == 14 and not errs, {"errors": errs[:3], "cases": len(TS["cases"])})
check("A2 覆盖度满足要求（S04/S05/S06 + MATCH/MISMATCH/UNCERTAIN + 6 个维度）",
      Q.coverage_status(TS)["ok"] and cov["_cases"] == 14
      and all(cov.get("scene:" + s) for s in ("S04", "S05", "S06"))
      and all(cov.get("dim:" + d) for d in ("viewpoint_pair", "temporal_split",
                                            "threshold_boundary_near", "threshold_boundary_far",
                                            "fail_closed", "unknown_by_design")),
      {k: v for k, v in cov.items() if k.startswith(("scene:", "dim:"))})
bad = json.loads(json.dumps(TS))
bad["cases"] = [c for c in bad["cases"] if "scene:S05" not in (c.get("covers") or [])]
check("A3 覆盖度不足 → 必须 fail-closed（删掉 S05 覆盖 → MMQ_INSUFFICIENT_COVERAGE）",
      Q.coverage_status(bad)["code"] == "MMQ_INSUFFICIENT_COVERAGE"
      and not Q.coverage_status(bad)["ok"],
      [e for e in Q.coverage_status(bad)["errors"] if e.startswith("覆盖度")][:2])
bad2 = json.loads(json.dumps(TS))
bad2["cases"][0].pop("content_label_provenance")
ok2, errs2, _ = validate_truth_set(bad2)
check("A4 真值缺出处（content_label_provenance）→ 非法（真值必须有溯源）",
      not ok2 and any("content_label_provenance" in e for e in errs2), errs2[:2])
bad3 = json.loads(json.dumps(TS))
bad3["cases"].append(json.loads(json.dumps(bad3["cases"][0])))
check("A5 重复 case id → 非法", not validate_truth_set(bad3)[0]
      and any("重复 case id" in e for e in validate_truth_set(bad3)[1]))
check("A6 **指纹钉定**：实际文件 sha256 == 代码内 TRUTH_SET_PIN（改真值集不更新指纹必失败）",
      pin_status(TRUTH)["matches"] and sha256_file(TRUTH) == TRUTH_SET_PIN
      and Q.TRUTH_SET_DRAFT_SHA256 != TRUTH_SET_PIN,
      {"pin": TRUTH_SET_PIN[:16], "actual": (sha256_file(TRUTH) or "")[:16]})
miss, err = load_truth_set(ROOT / "tests" / "fixtures" / "__no_such__.json")
check("A7 真值集缺失 → (None, MMQ_TRUTH_MISSING)（不抛异常、不猜测）",
      miss is None and err["code"] == "MMQ_TRUTH_MISSING", err)
(tmp := Path(tempfile.mkdtemp(prefix="vs_mmq_bad_"))).joinpath("bad.json").write_text(
    "{not json", encoding="utf-8")
_m, _e = load_truth_set(tmp / "bad.json")
check("A8 真值集非法 JSON → MMQ_TRUTH_INVALID", _m is None and _e["code"] == "MMQ_TRUTH_INVALID",
      _e.get("detail"))

# ============ B. 评估逻辑 ============
print("\n== B. 评估逻辑（allow / must_not / code / stability / UNRESOLVED） ==")
case = {"id": "C", "expect": {"5d": {"allow": ["UNKNOWN"], "must_not": ["MATCH"],
                                      "require_code_any": ["MMT_TEMPORAL_SPLIT"]}}}
e_ok = evaluate_layer(case, "5d", {"verdict": "UNKNOWN", "code": "MMT_TEMPORAL_SPLIT"})
e_bad = evaluate_layer(case, "5d", {"verdict": "MATCH", "code": None})
check("B1 allow+must_not+require_code 三条检查齐备；符合 → ok=true / 违反 → violations 非空",
      e_ok["ok"] and not e_ok["violations"] and len(e_ok["checks"]) == 3
      and not e_bad["ok"] and len(e_bad["violations"]) == 3, e_bad["violations"])
e_err = evaluate_layer(case, "5d", {"layer_error": {"code": "MMQ_LAYER_ERROR", "detail": "x"}})
check("B2 层不可用 → UNRESOLVED（resolved=false、violations 记 layer_error），**不当作通过**",
      e_err.get("resolved") is False and e_err["violations"][0]["rule"] == "layer_error")
case_s = {"id": "S", "expect": {"5d": {"require_not_code_any": ["MMT_TEMPORAL_SPLIT"],
                                        "require_stability": "STABLE"}}}
e_s1 = evaluate_layer(case_s, "5d", {"verdict": "MISMATCH", "code": None,
                                     "metrics": {"stability": {"class": "STABLE"}}})
e_s2 = evaluate_layer(case_s, "5d", {"verdict": "UNKNOWN", "code": "MMT_TEMPORAL_SPLIT",
                                     "metrics": {"stability": {"class": "SPLIT"}}})
check("B3 require_not_code_any / require_stability：对照组（无语义断言）只看时序，不看 verdict",
      e_s1["ok"] and not e_s2["ok"] and len(e_s2["violations"]) == 2, e_s2["violations"])
bd = boundary_distances("5d", {"verdict": "UNKNOWN", "metrics": {
    "expected_domain": "xr_device",
    "expected_sim_median": 0.2249, "median_margin": 0.0061, "vote_expected": 1.0,
    "visual_stability_mean": 0.96892, "min_sim": 0.2, "margin_threshold": 0.02,
    "min_vote_frac": 0.6, "min_stability_cos": 0.75,
    "top_k": [{"domain": "xr_device", "sim": 0.2249}, {"domain": "vehicle", "sim": 0.2188}]}})
check("B4 边界距离：sim−min_sim、|边际|−阈值、投票−下限、一致性−下限 + top-k/是否 top1",
      bd["sim_above_min_sim"] == 0.0249 and bd["margin_above_threshold"] == -0.0139
      and bd["vote_above_min_frac"] == 0.4 and bd["stability_above_min"] == 0.21892
      and bd["expected_in_top1"] is True, bd)
check("B5 每条指标都标注证据等级（MODEL_EVIDENCE / RULE_INFERENCE / ENGINEERING_THRESHOLD）",
      bd["_classes"]["sim_above_min_sim"] == "MODEL_EVIDENCE"
      and bd["_classes"]["median_margin"] == "RULE_INFERENCE"
      and bd["_classes"]["frames"] == "ENGINEERING_THRESHOLD"
      and evidence_class("verdict") == "RULE_INFERENCE"
      and evidence_class("domain_scores") == "MODEL_EVIDENCE"
      and evidence_class("min_stability_cos") == "ENGINEERING_THRESHOLD"
      and evidence_class("something_unknown") == "UNKNOWN")
chain = explain_chain({"id": "C"}, "5d", {"verdict": "UNKNOWN", "code": "MMT_AMBIGUOUS",
                                          "metrics": {"frames": 7, "expected_sim_median": 0.2249,
                                                      "median_margin": 0.0061, "vote_expected": 1.0,
                                                      "visual_stability_mean": 0.969,
                                                      "min_sim": 0.2, "margin_threshold": 0.02,
                                                      "min_vote_frac": 0.6, "min_stability_cos": 0.75,
                                                      "split_cos": 0.5, "top_k": []}},
                     {"violations": []})
check("B6 可解释链四段式：模型证据 → 工程阈值 → 规则推断（结论）→ 是否与真值一致",
      len(chain) == 4 and chain[0].startswith("[MODEL_EVIDENCE]")
      and chain[1].startswith("[ENGINEERING_THRESHOLD]")
      and chain[2].startswith("[RULE_INFERENCE]")
      and chain[3].startswith("[RULE_INFERENCE]"), chain)

# ============ C. 指标与冲突 ============
print("\n== C. 指标 / 冲突检测 ==")
synth = [
    {"case_id": "S1", "content_label": "MATCH",
     "layers": {"5d": {"observed": {"verdict": "MATCH"}, "resolved": True, "violations": []}}},
    {"case_id": "S2", "content_label": "MISMATCH",
     "layers": {"5d": {"observed": {"verdict": "MISMATCH"}, "resolved": True, "violations": []}}},
    {"case_id": "S3", "content_label": "MATCH",
     "layers": {"5d": {"observed": {"verdict": "UNKNOWN"}, "resolved": True, "violations": []}}},
]
agg = aggregate(synth)["5d"]
check("C1 指标：MATCH 精确率 1.0（说 MATCH 的都真是 MATCH）、MISMATCH 召回 1.0、UNKNOWN 计数正确",
      agg["match_precision_on_truth"] == 1.0 and agg["mismatch_recall_on_truth"] == 1.0
      and agg["unknown_count"] == 1 and agg["match_count"] == 1
      and agg["unknown_on_match_cases"] == ["S3"], agg)
synth2 = [
    {"case_id": "S1", "content_label": "MATCH",
     "layers": {"5d": {"observed": {"verdict": "MATCH"}, "resolved": True, "violations": []},
                "5a": {"observed": {"verdict": "MISMATCH"}, "resolved": True, "violations": []}}},
    {"case_id": "S2", "content_label": "MATCH",
     "layers": {"5d": {"observed": {"verdict": "MATCH"}, "resolved": True, "violations": []},
                "5a": {"observed": {"verdict": "UNKNOWN"}, "resolved": True, "violations": []}}},
]
conf = detect_conflicts(synth2)
check("C2 层间冲突：同例 MATCH 与 MISMATCH 并存 → MMQ_EVIDENCE_CONFLICT；全一致 → 无冲突",
      len(conf) == 1 and conf[0]["case_id"] == "S1"
      and conf[0]["code"] == "MMQ_EVIDENCE_CONFLICT"
      and detect_conflicts(synth) == [], conf)

# ============ D. 阈值敏感性（只披露） ============
print("\n== D. 阈值敏感性（披露，不调参） ==")
obs = [{"case_id": "B1", "layer": "5d", "kind": "5d", "base_verdict": "UNKNOWN",
        "payload": {"expected_domain": "xr_device", "metrics": {
            "frames_used": 7, "expected_domain": "xr_device", "per_frame": [],
            "adjacent_cos": [0.99] * 6, "vote_expected": 1.0, "argmax_votes": {"xr_device": 7},
            "visual_stability_mean": 0.99, "visual_stability_min": 0.99, "dispersion": 0.0,
            "expected_sim_median": 0.2362, "expected_sim_min": 0.2362, "expected_sim_mean": 0.2362,
            "margin_median": 0.0171, "margin_min": 0.0171,
            "domains_aggregated": {"xr_device": 0.2362, "vehicle": 0.2191}}}}]
rows = sensitivity_rows(obs, {"margin": [-0.01, 0.0, 0.01]})
base = [v["verdict"] for v in rows[0]["variants"] if v["settings"]["margin"] == 0.0][0]
loose = [v["verdict"] for v in rows[0]["variants"] if v["settings"]["margin"] == -0.01][0]
tight = [v["verdict"] for v in rows[0]["variants"] if v["settings"]["margin"] == 0.01][0]
check('D1 边际 0.0171：基线 UNKNOWN；**放宽** margin −0.01 → MATCH（这就是「不能靠调阈值」的证据）',
      base == "UNKNOWN" and loose == "MATCH" and tight == "UNKNOWN",
      {"base": base, "margin-0.01": loose, "margin+0.01": tight})
check("D2 敏感性行记录每次扰动的完整 settings 与 verdict（可逐条复核）",
      len(rows[0]["variants"]) == 3 and all("settings" in v and "verdict" in v
                                            for v in rows[0]["variants"])
      and rows[0]["flip_count"] == 1, {"flips": rows[0]["flips"]})

# ============ E. 真实校准（真实 CLIP） ============
print("\n== E. 真实校准（真实项目 + 真实 CLIP） ==")
tmpdir = Path(tempfile.mkdtemp(prefix="vs_mmq_test_"))
cal = calibration_report(REAL_DB, REAL_PID, root=ROOT, frames_dir=tmpdir)
frozen = json.loads(FROZEN_CAL.read_text(encoding="utf-8-sig")) if FROZEN_CAL.is_file() else {}
status = (cal.get("evidence_classes") or {}).get("case_status_counts") or {}
check("E1 真值集指纹吻合且覆盖度通过（fail-closed 前置条件满足）",
      (cal.get("truth_set") or {}).get("pin", {}).get("matches") is True
      and (cal.get("truth_set") or {}).get("coverage", {}).get("ok") is True,
      {"pin": (cal.get("truth_set") or {}).get("pin", {}).get("sha256", "")[:16]})
check("E2 **14/14 用例满足真值集要求**（0 违例 / 0 UNRESOLVED / 0 冲突）",
      status.get("OK") == 14 and status.get("VIOLATION") == 0 and status.get("UNRESOLVED") == 0
      and not cal.get("conflicts"), {"status": status, "conflicts": cal.get("conflicts")})
m = cal.get("metrics") or {}
check("E3 MATCH 精确率 = 1.0（三层都没有把 MISMATCH 判成 MATCH；无误报）",
      all((m.get(k) or {}).get("match_precision_on_truth") == 1.0 for k in ("4b", "5a", "5d"))
      and not (m.get("4b") or {}).get("false_match_on_mismatch_cases"),
      {k: (m.get(k) or {}).get("match_precision_on_truth") for k in ("4b", "5a", "5d")})
check('E4 UNKNOWN 只出现在「内容为 MATCH 但证据弱」的用例上（T06/T08 等），且不得出现在 MISMATCH 用例上',
      set((m.get("5d") or {}).get("unknown_on_match_cases") or []) <=
      {"T05_S04_v6_human_fixed_match_boundary", "T06_S05_v6_boundary_unknown",
       "T08_S06_side_v6_unknown"}
      and not (m.get("5d") or {}).get("false_match_on_mismatch_cases"),
      (m.get("5d") or {}).get("unknown_on_match_cases"))
check("E5 fail-closed 齐备：真值/覆盖/模型不可用/冲突/未解决 五项状态都被记录",
      all(k in (cal.get("fail_closed") or {}) for k in
          ("truth_set_ok", "coverage_ok", "unresolved_cases", "conflicts",
           "model_unavailable_cases")) and (cal.get("fail_closed") or {})["all_cases_resolved"],
      cal.get("fail_closed"))
sens = cal.get("sensitivity") or {}
check('E6 敏感性只披露不调参：矩阵同时含「更松」与「更严」，且明确标注；S06(side) 永不翻转',
      sens.get("matrix", {}).get("margin", [None])[0] == -0.01
      and "更松" in (sens.get("note") or "")
      and "T08_S06_side_v6_unknown" in (sens.get("cases_never_flipping") or []),
      {"matrix": sens.get("matrix"), "never": sens.get("cases_never_flipping")})
def strip(rep):
    o = json.loads(json.dumps(rep))
    o.pop("meta", None)
    s = json.dumps(o, ensure_ascii=False, sort_keys=True)
    import re
    s = re.sub(r"[A-Za-z]:\\\\[^\"]*", "<P>", s)
    return s
cal2 = calibration_report(REAL_DB, REAL_PID, root=ROOT, frames_dir=tmpdir / "second")
check("E7 确定性：两次校准运行（剔除临时路径）逐字节一致", strip(cal) == strip(cal2),
      {"c1": status, "c2": (cal2.get("evidence_classes") or {}).get("case_status_counts")})
if frozen:
    same = all(((next((x for x in frozen["cases"] if x["case_id"] == c["case_id"]), {})
                 .get("layers") or {}).get(k, {}).get("observed")) ==
               ((c.get("layers") or {}).get(k, {}).get("observed"))
               for c in cal["cases"] for k in ("4b", "5a", "5d"))
    check("E8 与冻结证据一致：逐用例逐层的 verdict/code 与 logs/phase5e_quality.json 相同", same)

# ============ F. 只读与不覆盖 ============
print("\n== F. 只读 / 不覆盖 ==")
after = project_state()
check("F1 只读：真实 DB 字节与五张表行数在全部运行后与运行前一致",
      BEFORE["db"] == after["db"] and BEFORE["counts"] == after["counts"],
      {"before": BEFORE["counts"], "after": after["counts"]})
check("F2 只读：项目内所有文件（含 6 个成片）逐字节未变；未新增生产产物",
      BEFORE["files"] == after["files"]
      and len([k for k in after["files"] if k.endswith(".mp4")]) == 6,
      {"files": len(after["files"])})
src_q = (ROOT / "src" / "video_studio" / "core" / "mm_quality.py").read_text(encoding="utf-8")
ops_q = (ROOT / "src" / "video_studio" / "ops" / "mm_quality.py").read_text(encoding="utf-8")
check("F3 静态证明：校准层不写库/不写产物/不改阈值/不触发 redo（无写调用形态）",
      all(tok not in src_q + ops_q for tok in
          ("insert_decision", "insert_changelog", "write_artifact", "set_task_status",
           "run_cycle", "build_engine", "record_selection", "insert into", "update ",
           "delete from")) and 'changes_thresholds": False' in ops_q, "ok")
base = json.loads(BASE_MANIFEST.read_text(encoding="utf-8")) if BASE_MANIFEST.is_file() else {}
mods = ("src/video_studio/core/multimodal.py", "src/video_studio/core/mm_temporal.py",
        "src/video_studio/core/semantics.py", "src/video_studio/core/lexicons/semantics_v1.json")
same_mods = {mod: ((base.get("files") or {}).get(mod, {}).get("sha256") == sha(ROOT / mod))
             for mod in mods}
check("F4 **4-B/5-A/5-D 判定模块与词表未被本阶段改动**（sha256 与 5-D 基线一致）",
      all(same_mods.values()), same_mods)
fa_frozen = json.loads((ROOT / "docs" / "regression_2x" / "logs" / "phase5c_mm_after.json")
                       .read_text(encoding="utf-8-sig"))
mm_frozen = json.loads((ROOT / "docs" / "regression_2x" / "logs" / "phase5d_mmt_v6.json")
                       .read_text(encoding="utf-8-sig"))


def strip5(rep, keys):
    return json.dumps({"counts": rep.get("counts"),
                       "scenes": [{k: s.get(k) for k in keys} for s in rep.get("scenes") or []]},
                      ensure_ascii=False, sort_keys=True)


PAIRS_V6 = [("T03_S01_v6_clear_match", "S01"), ("T04_S02_v6_clear_match", "S02"),
            ("T05_S04_v6_human_fixed_match_boundary", "S04"),
            ("T06_S05_v6_boundary_unknown", "S05"), ("T08_S06_side_v6_unknown", "S06")]


def _cal_verdict(cid, layer):
    c = next((x for x in cal["cases"] if x["case_id"] == cid), {})
    return ((c.get("layers") or {}).get(layer) or {}).get("observed", {}).get("verdict")


def _frozen_verdict(rep, sid):
    return next((s for s in rep["scenes"] if s["scene_id"] == sid), {}).get("verdict")


same_5a = all(_cal_verdict(cid, "5a") == _frozen_verdict(fa_frozen, sid)
              for cid, sid in PAIRS_V6)
same_5d = all(_cal_verdict(cid, "5d") == _frozen_verdict(mm_frozen, sid)
              for cid, sid in PAIRS_V6)
check("F5 **5-A / 5-D 原始结果未被覆盖**：校准读到的判决与 5-C / 5-D 阶段的冻结证据逐镜头一致",
      same_5a and same_5d, {"5a": same_5a, "5d": same_5d})
pol = cal.get("policy") or {}
check("F6 报告显式声明：不写库/不改阈值/不自动换材选材 redo/不覆盖 4-B·5-A·5-D 结果",
      pol.get("writes_to_db") is False and pol.get("changes_thresholds") is False
      and pol.get("overwrites_5d_results") is False and pol.get("auto_replace") is False
      and pol.get("auto_redo") is False, {k: pol[k] for k in
                                          ("writes_to_db", "changes_thresholds", "auto_replace")})

# ============ G. 5-F 建议 ============
print("\n== G. 5-F 建议（仅建议） ==")
recs = recommendations()
check("G1 建议清单齐备（≥5 条）且每条都标注 `implemented_in_5e=False`（本阶段不实施）",
      len(recs) >= 5 and all(r.get("implemented_in_5e") is False for r in recs)
      and all(r.get("risk") for r in recs), {"n": len(recs), "ids": [r["id"] for r in recs]})
check("G2 校准报告内嵌同一份建议（报告与代码同源），且人读输出标注只读",
      (cal.get("recommendations_5f") or []) == recs
      and "不改任何判定逻辑" in format_mmq(cal), format_mmq(cal).splitlines()[0])

print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print("失败项:", FAIL)
sys.exit(1 if FAIL else 0)
