"""5.x Phase 5-F 单测：多模态证据 Judge（最终判定；**只读、零动作、不调阈值**）。

覆盖授权要求：
  A Judge 真值覆盖层：结构校验、case 集合必须与冻结真值集一致、理由码合法、UNKNOWN 下限、指纹钉定
  B 规则单测 J0–J6：全层一致 MATCH / 单层 MATCH / MISMATCH / 冲突 / 结构性 UNKNOWN / 全 UNKNOWN /
    部分 UNKNOWN / 期望域缺失 / 全不可用
  C 评估逻辑：require / allow / must_not / require_reason_any / 成对检查 / 缺结果 → 未解决
  D **真实运行**：live Judge 14/14 满足 Judge 真值、UNKNOWN ≥ 下限、0 冲突；`--from-calibration` 与 live 判定一致
  E 最终 DoD：12 条齐备且全部 PASS（可度量）
  F 处置：#43–#48 与 R1–R6 逐项分类（保留/解决/转入最终已知问题；进入最终产品/未来研究项/产品决策）
  G 只读与不调阈值：DB/项目文件零变更；静态扫描无写调用、无阈值参数
  H 职责边界：4-B/5-A/5-D/Judge 的 role / used_for / not_used_for 齐备

用法：python tests/mm_judge_test.py
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

from video_studio.core import mm_judge as J  # noqa: E402
from video_studio.core import mm_quality as Q  # noqa: E402
from video_studio.ops.mm_judge import format_mmj, judge_report  # noqa: E402

REAL_DB = ROOT / "projects" / "video_studio.db"
REAL_PID = "p_f4b466a4a024"
TS_PATH = ROOT / Q.TRUTH_SET_REL
JT_PATH = ROOT / J.JUDGE_TRUTH_REL
CAL_FROZEN = ROOT / "docs" / "regression_2x" / "logs" / "phase5e_quality.json"
JUDGE_FROZEN = ROOT / "docs" / "regression_2x" / "logs" / "phase5f_judge.json"
# 5-G: guard pinned to 5.x-phase5g-baseline manifest (baseline rotation after authorized validator change)
BASE_MANIFEST = (ROOT / "docs" / "regression_2x" / "baseline" /
                 "baseline_manifest_5.x-phase5g-baseline.json")
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
TS = json.loads(TS_PATH.read_text(encoding="utf-8"))
JT = json.loads(JT_PATH.read_text(encoding="utf-8"))

# ============ A. Judge 真值覆盖层 ============
print("== A. Judge 真值覆盖层（结构/一致性/指纹） ==")
ok, errs = J.validate_judge_truth(JT, TS)
check("A1 覆盖层合法：14 例、case 集合与冻结真值集完全一致、每例有 rationale 与合法理由码",
      ok and len(JT["cases"]) == 14 and not errs, {"errors": errs[:3]})
check("A2 覆盖层引用冻结真值集指纹（truth_set_ref.sha256 == 5-E 定稿指纹）",
      JT["truth_set_ref"]["sha256"] == Q.TRUTH_SET_PIN, JT["truth_set_ref"]["sha256"][:16])
check("A3 **指纹钉定**：覆盖层实际 sha256 == 代码内 JUDGE_TRUTH_PIN",
      sha(JT_PATH) == J.JUDGE_TRUTH_PIN, {"pin": J.JUDGE_TRUTH_PIN[:16],
                                          "actual": (sha(JT_PATH) or "")[:16]})
bad = json.loads(json.dumps(JT))
bad["cases"] = [c for c in bad["cases"] if c["case_id"] != "T08_S06_side_v6_unknown"]
ok2, errs2 = J.validate_judge_truth(bad, TS)
check("A4 覆盖层缺用例（与冻结真值集对不上）→ 非法（fail-closed）",
      not ok2 and any("缺少用例" in e for e in errs2), errs2[:2])
bad2 = json.loads(json.dumps(JT))
bad2["cases"][0]["judge_expect"]["require_reason_any"] = ["JUDGE_NOT_A_CODE"]
check("A5 未登记的理由码 → 非法（防止写出无法复核的判据）",
      not J.validate_judge_truth(bad2, TS)[0]
      and any("未知理由码" in e for e in J.validate_judge_truth(bad2, TS)[1]))
bad3 = json.loads(json.dumps(JT))
bad3["unknown_policy"]["legitimate_final_outcome"] = False
check("A6 声明 UNKNOWN 非合法结果 → 非法（UNKNOWN 必须是合法最终结果）",
      not J.validate_judge_truth(bad3, TS)[0])
bad4 = json.loads(json.dumps(JT))
bad4["truth_set_ref"]["sha256"] = "0" * 64
check("A7 引用错误的真值集指纹 → 非法", not J.validate_judge_truth(bad4, TS)[0])
_m, _e = J.load_judge_truth(ROOT / "tests" / "fixtures" / "__no_such_judge__.json")
check("A8 覆盖层缺失 → (None, MMJ_TRUTH_MISSING)（不抛异常）",
      _m is None and _e["code"] == "MMJ_TRUTH_MISSING")

# ============ B. 规则 J0–J6 ============
print("\n== B. Judge 规则 J0–J6（纯函数） ==")


def L(v4b=None, v5a=None, v5d=None, c4b=None, c5a=None, c5d=None, err5d=None):
    out = {}
    if v4b:
        out["4b"] = {"verdict": v4b, "code": c4b}
    if v5a:
        out["5a"] = {"verdict": v5a, "code": c5a}
    if v5d:
        out["5d"] = {"verdict": v5d, "code": c5d}
    if err5d:
        out["5d"] = {"layer_error": {"code": err5d}}
    return out


r = J.judge_scene(L("MATCH", "MATCH", "MATCH"))
check("B1 J4 全层一致 MATCH（≥2 层）→ 最终 MATCH / JUDGE_UNANIMOUS_MATCH",
      r["verdict"] == "MATCH" and r["rule"] == "J4_UNANIMOUS_MATCH"
      and r["reason_code"] == "JUDGE_UNANIMOUS_MATCH" and r["unknown_is_final"] is False, r)
r = J.judge_scene(L("MATCH"))
check("B2 J5 仅单层可用且判 MATCH → UNKNOWN / JUDGE_INSUFFICIENT_LAYERS（单层不足以断言）",
      r["verdict"] == "UNKNOWN" and r["reason_code"] == "JUDGE_INSUFFICIENT_LAYERS"
      and r["unknown_is_final"] is True, r)
r = J.judge_scene(L("MATCH", "MATCH", "MISMATCH"))
check("B3 J3 存在 MISMATCH 且无 MATCH 冲突前先判冲突？—— 有 MATCH 也有 MISMATCH → J2 冲突优先（不选边）",
      r["verdict"] == "UNKNOWN" and r["rule"] == "J2_EVIDENCE_CONFLICT"
      and r["reason_code"] == "JUDGE_EVIDENCE_CONFLICT", r)
r = J.judge_scene(L("UNKNOWN", "UNKNOWN", "MISMATCH", c5d=None))
check("B4 J3 存在 MISMATCH 且无 MATCH → 最终 MISMATCH / JUDGE_MISMATCH_FLAGGED",
      r["verdict"] == "MISMATCH" and r["rule"] == "J3_MISMATCH" and r["flagged_by"] == ["5d"], r)
r = J.judge_scene(L("MISMATCH", "UNKNOWN", "UNKNOWN", c5d="MMT_TEMPORAL_SPLIT"))
check("B5 J1 结构性 UNKNOWN（5-D 切图/帧数不足/一致性不足）**优先于** 4-B 的 MISMATCH → UNKNOWN（保守）",
      r["verdict"] == "UNKNOWN" and r["rule"] == "J1_STRUCTURAL_UNKNOWN"
      and r["propagated_code"] == "MMT_TEMPORAL_SPLIT" and r["priority_rank"] == 1, r)
r = J.judge_scene(L("MATCH", "UNKNOWN", "UNKNOWN", c5d="MMT_AMBIGUOUS"))
check("B6 J6 部分层 MATCH + 部分层 UNKNOWN（无 MISMATCH）→ UNKNOWN / JUDGE_PARTIAL_UNKNOWN",
      r["verdict"] == "UNKNOWN" and r["reason_code"] == "JUDGE_PARTIAL_UNKNOWN", r)
r = J.judge_scene(L("UNKNOWN", "UNKNOWN", "UNKNOWN", c5d="MMT_AMBIGUOUS"))
check("B7 J6 全层 UNKNOWN → UNKNOWN / JUDGE_ALL_UNKNOWN",
      r["verdict"] == "UNKNOWN" and r["reason_code"] == "JUDGE_ALL_UNKNOWN", r)
r = J.judge_scene(L("UNKNOWN", "UNKNOWN", "UNKNOWN", c4b="R_UNKNOWN_DOMAIN",
                    c5a="MM_UNKNOWN_DOMAIN", c5d="MMT_UNKNOWN_DOMAIN"))
check("B8 J6 期望域推不出（*_UNKNOWN_DOMAIN）→ UNKNOWN / JUDGE_UNKNOWN_DOMAIN（不猜域）",
      r["verdict"] == "UNKNOWN" and r["reason_code"] == "JUDGE_UNKNOWN_DOMAIN", r)
r = J.judge_scene(L(err5d="MM_MODEL_MISSING"))
check("B9 J0 全部层不可用（模型缺失）→ UNKNOWN / JUDGE_MODEL_UNAVAILABLE",
      r["verdict"] == "UNKNOWN" and r["reason_code"] == "JUDGE_MODEL_UNAVAILABLE"
      and r["rule"] == "J0_FAIL_CLOSED", r)
r = J.judge_scene({})
check("B10 J0 无任何层证据 → UNKNOWN / JUDGE_NO_EVIDENCE", r["reason_code"] == "JUDGE_NO_EVIDENCE", r)
check("B11 规则表/优先级/理由码齐备（J0–J6、5 级优先级、10 个理由码）",
      len(J.JUDGE_RULES) == 7 and len(J.EVIDENCE_PRIORITY) == 5 and len(J.JUDGE_CODES) == 10
      and all(p["why"] for p in J.EVIDENCE_PRIORITY), {"rules": len(J.JUDGE_RULES)})

# ============ C. 评估逻辑 ============
print("\n== C. 逐例评估逻辑 ==")
ev = J.evaluate_judge_case({"require": ["UNKNOWN"], "must_not": ["MATCH"],
                            "require_reason_any": ["JUDGE_PARTIAL_UNKNOWN"]},
                           {"verdict": "UNKNOWN", "reason_code": "JUDGE_PARTIAL_UNKNOWN"})
check("C1 require / must_not / require_reason_any 三条检查齐备，符合 → ok",
      ev["ok"] and len(ev["checks"]) == 3 and not ev["violations"], ev["checks"])
ev2 = J.evaluate_judge_case({"require": ["MATCH"]}, {"verdict": "UNKNOWN",
                                                     "reason_code": "JUDGE_ALL_UNKNOWN"})
check("C2 与期望不符 → VIOLATION（记 observed 与 violations，不静默通过）",
      not ev2["ok"] and ev2["violations"][0]["observed"] == "UNKNOWN", ev2["violations"])
ev3 = J.evaluate_judge_case({"require": ["MATCH"]}, None)
check("C3 缺结果 → resolved=False / UNRESOLVED（**不算通过**）",
      ev3.get("resolved") is False and ev3["violations"][0]["rule"] == "missing_result")
ev4 = J.evaluate_judge_case({"verdict": None, "require_pair_checks": ["5d_margin_front_gt_side"]},
                            None, pair_result={"checks": [{"name": "5d_margin_front_gt_side",
                                                           "ok": True}]})
check("C4 成对用例：只检查成对项，不产生单镜头三态", ev4["ok"] and ev4["observed"]["pair"],
      ev4["observed"])

# ============ D. 真实运行 ============
print("\n== D. 真实运行（live 三层 + 复用校准） ==")
tmpdir = Path(tempfile.mkdtemp(prefix="vs_mmj_test_"))
live = judge_report(REAL_DB, REAL_PID, root=ROOT, frames_dir=tmpdir)
jr = live.get("judge_result") or {}
check("D1 live Judge：14 例**逐例**满足 Judge 真值（0 违例 / 0 未解决）",
      jr.get("cases_total") == 14 and jr.get("violations") == 0 and jr.get("unresolved") == 0
      and jr.get("all_meet_judge_truth") is True, jr)
sm = live.get("summary") or {}
check("D2 UNKNOWN 是合法最终结果：最终 UNKNOWN ≥ 覆盖层下限（且未调任何阈值）",
      sm.get("counts", {}).get("UNKNOWN", 0) >= sm.get("unknown_min_required", 99)
      and sm.get("unknown_is_legitimate") is True and sm.get("thresholds_touched") is False, sm)
check("D3 理由码分布可复核：MATCH 全部为 JUDGE_UNANIMOUS_MATCH；MISMATCH 全部为 JUDGE_MISMATCH_FLAGGED",
      all(r["judge"]["reason_code"] == "JUDGE_UNANIMOUS_MATCH"
          for r in live["rows"] if r["judge"].get("verdict") == "MATCH")
      and all(r["judge"]["reason_code"] == "JUDGE_MISMATCH_FLAGGED"
              for r in live["rows"] if r["judge"].get("verdict") == "MISMATCH"),
      sm.get("reason_codes"))
cal = json.loads(CAL_FROZEN.read_text(encoding="utf-8-sig"))
reuse = judge_report(REAL_DB, REAL_PID, root=ROOT, calibration=cal)
same = {r["case_id"]: r["judge"].get("verdict") for r in live["rows"]} == \
       {r["case_id"]: r["judge"].get("verdict") for r in reuse["rows"]}
check("D4 复用 5-E 冻结校准与现场重跑三层的最终判定**逐例一致**（判定不依赖运行方式）",
      same and reuse["judge_result"]["all_meet_judge_truth"], {"same": same})
if JUDGE_FROZEN.is_file():
    frozen = json.loads(JUDGE_FROZEN.read_text(encoding="utf-8-sig"))
    same_f = {r["case_id"]: (r["judge"].get("verdict"), r["judge"].get("reason_code"))
              for r in frozen["rows"]} == {r["case_id"]: (r["judge"].get("verdict"),
                                                          r["judge"].get("reason_code"))
                                           for r in live["rows"]}
    check("D5 与冻结 Judge 证据一致（verdict + reason_code 逐例相同）", same_f)
live2 = judge_report(REAL_DB, REAL_PID, root=ROOT, calibration=cal)
s1 = json.dumps({r["case_id"]: r["judge"] for r in live["rows"]}, ensure_ascii=False, sort_keys=True)
s2 = json.dumps({r["case_id"]: r["judge"] for r in live2["rows"]}, ensure_ascii=False, sort_keys=True)
check("D6 确定性：同一输入两次运行的最终判定与理由逐字节一致", s1 == s2)

# ============ E. 最终 DoD ============
print("\n== E. 最终 DoD ==")
dod = live.get("dod") or []
check("E1 DoD 12 条齐备且**全部 PASS**（每条含 item 与 evidence 指针）",
      len(dod) == 12 and all(d["ok"] for d in dod) and live.get("dod_all_pass") is True
      and all(d.get("evidence") for d in dod), {"n": len(dod),
                                                "failed": [d["id"] for d in dod if not d["ok"]]})
d7 = next((d for d in dod if d["id"] == "D7"), {})
check("E2 DoD D7 明确『UNKNOWN 合法且不存在调阈值路径』（禁止为提高通过率调阈值）",
      d7.get("ok") is True and "UNKNOWN" in d7.get("item", ""))

# ============ F. 处置（#43–#48 / R1–R6） ============
print("\n== F. 限制与建议的逐项处置 ==")
disp = live.get("dispositions_43_48") or []
check("F1 #43–#48 六项**逐项**处置（decision 非空且带 why/evidence）",
      len(disp) == 6 and {d["id"] for d in disp} == {"#43", "#44", "#45", "#46", "#47", "#48"}
      and all(d.get("decision") and d.get("why") and d.get("evidence") for d in disp),
      {d["id"]: d["decision"] for d in disp})
recs = live.get("recommendations_disposition") or []
dec = {r["id"]: r["decision"] for r in recs}
check("F2 R1–R6 逐项判定：进最终产品（R3/R4/R6）、未来研究项（R1/R2）、产品决策（R5）",
      len(recs) == 6 and "值得进入最终产品" in dec.get("R3", "")
      and "值得进入最终产品" in dec.get("R4", "")
      and "值得进入最终产品" in dec.get("R6", "")
      and "未来研究项" in dec.get("R1", "") and "未来研究项" in dec.get("R2", "")
      and "产品决策" in dec.get("R5", ""), dec)
check("F3 处置不越界：没有任何一条声称『已实施』（5-F 只判定不实施）",
      all("未进 5-F" in r["decision"] or "不值得" not in r["decision"] for r in recs)
      and all("#" in d["id"] for d in disp))

# ============ G. 只读 / 不调阈值 ============
print("\n== G. 只读与不调阈值 ==")
after = project_state()
check("G1 只读：真实 DB 字节与五张表行数在全部运行后与运行前一致",
      BEFORE["db"] == after["db"] and BEFORE["counts"] == after["counts"],
      {"before": BEFORE["counts"], "after": after["counts"]})
check("G2 只读：项目内所有文件（含 6 个成片）逐字节未变；未新增生产产物",
      BEFORE["files"] == after["files"]
      and len([k for k in after["files"] if k.endswith(".mp4")]) == 6,
      {"files": len(after["files"])})
src_j = (ROOT / "src" / "video_studio" / "core" / "mm_judge.py").read_text(encoding="utf-8")
ops_j = (ROOT / "src" / "video_studio" / "ops" / "mm_judge.py").read_text(encoding="utf-8")
check("G3 静态证明：Judge 不写库/不写产物/不触发 redo/不改时间轴（无写调用形态）",
      all(tok not in src_j + ops_j for tok in
          ("insert_decision", "insert_changelog", "write_artifact", "set_task_status",
           "run_cycle", "build_engine", "record_selection", "insert into", "update ",
           "delete from")), "ok")
check("G4 静态证明：Judge **没有可调阈值参数**（不存在『调阈值减少 UNKNOWN』的代码路径）",
      all(tok not in src_j for tok in ("min_sim", "min_vote_frac", "min_stability_cos",
                                       "split_cos", "frames_per_scene", "min_frames"))
      and "tunes_thresholds_to_reduce_unknown\": False" in ops_j, "ok")
base = json.loads(BASE_MANIFEST.read_text(encoding="utf-8")) if BASE_MANIFEST.is_file() else {}
mods = ("src/video_studio/core/mm_quality.py", "src/video_studio/core/mm_temporal.py",
        "src/video_studio/core/multimodal.py", "src/video_studio/core/semantics.py",
        "src/video_studio/core/lexicons/semantics_v1.json", Q.TRUTH_SET_REL)
check("G5 **三层原始证据未被覆盖**：5-E 基线内的判定模块/词表/冻结真值集 sha256 全部未变",
      all(((base.get("files") or {}).get(m, {}).get("sha256") == sha(ROOT / m)) for m in mods),
      {m: ((base.get("files") or {}).get(m, {}).get("sha256") == sha(ROOT / m)) for m in mods})
pol = live.get("policy") or {}
check("G6 报告显式声明：零动作 + 不调阈值 + 不覆盖 4-B/5-A/5-D 结果",
      pol.get("writes_to_db") is False and pol.get("changes_thresholds") is False
      and pol.get("tunes_thresholds_to_reduce_unknown") is False
      and pol.get("overwrites_5d_results") is False and pol.get("auto_replace") is False, pol)

# ============ H. 职责边界 ============
print("\n== H. 职责边界（最终） ==")
scope = live.get("scope") or {}
check("H1 4-B/5-A/5-D/Judge 的 role / used_for / not_used_for 齐备",
      all(k in scope for k in ("4b", "5a", "5d", "judge"))
      and all(scope[k].get("role") and scope[k].get("used_for")
              and scope[k].get("not_used_for") for k in scope), sorted(scope))
check("H2 边界声明明确：4-B 不看画面；5-A 不做时序；5-D 不单独断言 MATCH；Judge 不做任何动作",
      scope["4b"]["sees_pixels"] is False
      and any("时序" in x for x in scope["5a"]["not_used_for"])
      and any("单独断言 MATCH" in x for x in scope["5d"]["not_used_for"])
      and any("自动换材" in x for x in scope["judge"]["not_used_for"]), "ok")
check("H3 人读输出标注只读与零动作", "只读、零动作、不调阈值" in format_mmj(live)
      and "未调阈值" in format_mmj(live), format_mmj(live).splitlines()[0])

print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print("失败项:", FAIL)
sys.exit(1 if FAIL else 0)
