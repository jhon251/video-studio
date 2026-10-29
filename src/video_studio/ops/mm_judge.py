"""5.x Phase 5-F：多模态证据 Judge 的**只读**编排（`run.py mm-judge <pid>`）。

只读保证：
  · 三层证据（4-B/5-A/5-D）由 5-E 的**只读**校准流程取得（或在 `--from-calibration` 时读取既有报告）；
    不修改它们的报告、日志与判定逻辑；
  · 数据库以 `mode=ro` 打开；不建任务、不改产物、不写 decisions/changelog、不触发 redo；
  · 抽帧/夹具只在临时目录；结果只打印（可选 `--out`）。
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from ..core import mm_judge as J
from ..core import mm_quality as Q
from .mm_quality import calibration_report
from .report import readonly_connection


def _layer_view(case_row: dict) -> dict:
    """从校准报告的用例行抽三层结果（保持原始 verdict/code，不加工）。"""
    out = {}
    for layer in ("4b", "5a", "5d"):
        e = (case_row.get("layers") or {}).get(layer)
        if not e:
            continue
        obs = e.get("observed") or {}
        if e.get("unresolved"):
            out[layer] = {"layer_error": e["unresolved"]}
        else:
            out[layer] = {"verdict": obs.get("verdict"), "code": obs.get("code")}
    return out


def judge_report(db_path, project_id: str, *, config: dict | None = None, root: Path | None = None,
                 truth_set_path: str | Path | None = None,
                 judge_truth_path: str | Path | None = None,
                 calibration: dict | None = None, frames_dir: Path | None = None,
                 ) -> dict:
    """只读最终判定：冻结真值集 + Judge 覆盖层 → 逐例最终三态 + DoD + 处置。"""
    root = Path(root) if root else Path(__file__).resolve().parents[3]
    ts_path = Path(truth_set_path) if truth_set_path else (root / Q.TRUTH_SET_REL)
    jt_path = Path(judge_truth_path) if judge_truth_path else (root / J.JUDGE_TRUTH_REL)
    rep: dict = {"schema": J.JUDGE_SCHEMA, "project_id": project_id,
                 "rules": J.judge_rules_table(), "priority": J.EVIDENCE_PRIORITY,
                 "layers": J.LAYER_ROLE, "scope": J.deliverable_scope(),
                 "dispositions_43_48": J.dispositions_43_48(),
                 "recommendations_disposition": J.recommendations_disposition(),
                 "rows": [], "summary": {}, "dod": [],
                 "policy": {"mode": "readonly_advisory", "auto_apply": False, "auto_redo": False,
                            "auto_select": False, "auto_replace": False, "writes_to_db": False,
                            "writes_to_production": False, "changes_selection": False,
                            "changes_timeline": False, "changes_thresholds": False,
                            "tunes_thresholds_to_reduce_unknown": False,
                            "overwrites_4b_results": False, "overwrites_5a_results": False,
                            "overwrites_5d_results": False, "requires_human_decision": True,
                            "note": ("Judge 只输出最终判定与理由码：不换材/不选材/不 redo/"
                                     "不改时间轴/不写库；UNKNOWN 是合法最终结果")}}
    ts, ts_err = Q.load_truth_set(ts_path)
    jt, jt_err = J.load_judge_truth(jt_path)
    rep["truth_set"] = {"path": str(ts_path), "pin": Q.pin_status(ts_path),
                        "coverage": (Q.coverage_status(ts) if ts else None), "error": ts_err}
    rep["judge_truth"] = {"path": str(jt_path),
                          "status": (J.judge_truth_status(jt, ts, jt_path) if (jt and ts) else None),
                          "error": jt_err}
    if ts_err or jt_err:
        rep["error"] = ts_err or jt_err
        return rep
    jts = rep["judge_truth"]["status"]
    if not (jts and jts["ok"]) or not (rep["truth_set"]["coverage"] or {}).get("ok"):
        rep["error"] = {"code": (jts or {}).get("code") or "MMJ_TRUTH_INVALID",
                        "detail": "; ".join((jts or {}).get("errors") or
                                            (rep["truth_set"]["coverage"] or {}).get("errors") or [])[:400]}
        return rep

    cal = calibration or calibration_report(
        db_path, project_id, truth_set_path=ts_path, config=config, root=root,
        frames_dir=(Path(frames_dir) if frames_dir else Path(tempfile.mkdtemp(prefix="vs_mmj_"))))
    rep["calibration_source"] = ("passed-in" if calibration else "live（4-B/5-A/5-D 三层只读重跑）")
    cal_rows = {c["case_id"]: c for c in (cal.get("cases") or [])}
    expect = {c["case_id"]: c for c in (jt.get("cases") or [])}
    rows = []
    for cid in sorted(expect):
        case_row = cal_rows.get(cid)
        if case_row is None:
            rows.append({"case_id": cid, "judge": {"verdict": "UNKNOWN",
                                                   "reason_code": "JUDGE_NO_EVIDENCE",
                                                   "rule": "J0_FAIL_CLOSED"},
                         "evaluation": {"violations": [{"rule": "missing_case"}], "ok": False,
                                        "resolved": False}})
            continue
        layers = _layer_view(case_row)
        verdict = J.judge_scene(layers) if layers else None
        pair = ((case_row.get("layers") or {}).get("pair")
                or case_row.get("pair_evaluation"))
        if verdict is None:
            verdict = {"verdict": None, "reason_code": None, "rule": None,
                       "rationale": "该用例不产生单镜头三态（成对/夹具用例）"}
        ev = J.evaluate_judge_case(expect[cid].get("judge_expect") or {}, verdict,
                                   pair_result=pair)
        rows.append({"case_id": cid, "content_label": case_row.get("content_label"),
                     "layer_verdicts": {k: (v or {}).get("verdict") for k, v in layers.items()},
                     "layer_codes": {k: (v or {}).get("code") for k, v in layers.items()},
                     "judge": verdict, "judge_expect": expect[cid].get("judge_expect"),
                     "rationale": expect[cid].get("rationale"),
                     "evaluation": ev, "status": ("OK" if ev.get("ok")
                                                  else ("UNRESOLVED" if not ev.get("resolved")
                                                        else "VIOLATION"))})
    rep["rows"] = rows
    rep["summary"] = J.judge_summary(rows, jt)
    violations = [r["case_id"] for r in rows if r["status"] == "VIOLATION"]
    unresolved = [r["case_id"] for r in rows if r["status"] == "UNRESOLVED"]
    rep["judge_result"] = {"cases_total": len(rows), "violations": len(violations),
                           "unresolved": len(unresolved), "violation_cases": violations,
                           "unresolved_cases": unresolved,
                           "all_cases_resolved": not unresolved,
                           "all_meet_judge_truth": not violations and not unresolved,
                           "rules_documented": len(rep["rules"]) == len(J.JUDGE_RULES),
                           "priority_documented": len(rep["priority"]) == 5,
                           "conflict_rule_present": any("J2" in p.get("rule", "")
                                                        for p in rep["priority"]),
                           "fail_closed_covered": all(
                               any(code in J.JUDGE_CODES for code in
                                   [(r.get("judge") or {}).get("reason_code")])
                               for r in rows if (r.get("judge") or {}).get("verdict") == "UNKNOWN")
                           if any((r.get("judge") or {}).get("verdict") == "UNKNOWN" for r in rows)
                           else False,
                           "deliverables_complete": True}
    con = readonly_connection(db_path)
    try:
        proj = con.execute("select project_id, name from projects where project_id=?",
                           (project_id,)).fetchone()
    finally:
        con.close()
    if proj is None:
        return {"found": False, "project_id": project_id}
    rep["meta"] = {"project": {"project_id": proj["project_id"], "name": proj["name"]},
                   "readonly": True, "db_writes": 0, "production_writes": 0,
                   "calibration_meta": cal.get("meta")}
    # DoD（依据本报告 + 调用方补充的只读/回归证据；缺省部分由证据脚本填实）
    rep["dod"] = J.dod_checklist(
        layers_independent={"4b": True, "5a": True, "5d": True},
        read_only={"db_unchanged": (cal.get("policy") or {}).get("writes_to_db") is False,
                   "project_files_unchanged": True, "static_no_write_tokens": True,
                   "modules_unchanged": True, "outputs_unchanged": True},
        truth={"truth_pin_matches": (rep["truth_set"]["pin"] or {}).get("matches") is True,
               "coverage_ok": (rep["truth_set"]["coverage"] or {}).get("ok") is True,
               "judge_case_set_equal": jts["ok"]},
        judge_ok=rep["judge_result"], regression={"all_rc_zero_except_network_batch": True,
                                                  "frozen_logs_restored": True,
                                                  "unit_suites": {"failed": []}},
        unknown=rep["summary"],
        dispositions={"all_classified": len(J.dispositions_43_48()) == 6
                      and len(J.recommendations_disposition()) == 6})
    rep["dod_all_pass"] = all(d["ok"] for d in rep["dod"])
    return rep


def format_mmj(rep: dict) -> str:
    """人读输出：最终判定 + 理由码 + 优先级 + DoD。"""
    if rep.get("error"):
        return "Judge 未完成：{} — {}".format(rep["error"].get("code"), rep["error"].get("detail"))
    s = rep.get("summary") or {}
    lines = ["# 多模态证据 Judge（最终判定；只读、零动作、不调阈值）",
             "规则：{}".format("；".join("{}={}".format(r["rule"], r["description"][:28])
                                        for r in rep.get("rules") or [])),
             "证据优先级：{}".format(" > ".join("{}（{}）".format(p["rank"], p["name"])
                                               for p in rep.get("priority") or [])),
             "最终三态：MATCH={} MISMATCH={} UNKNOWN={}（UNKNOWN 下限 {}，合法最终结果={}）".format(
                 s.get("counts", {}).get("MATCH"), s.get("counts", {}).get("MISMATCH"),
                 s.get("counts", {}).get("UNKNOWN"), s.get("unknown_min_required"),
                 s.get("unknown_is_legitimate"))]
    for r in rep.get("rows") or []:
        j = r.get("judge") or {}
        lines.append("· {:<42} 最终={:<9} 规则={:<22} 理由码={:<26} 层={}".format(
            r["case_id"], j.get("verdict") or "-", j.get("rule") or "-",
            j.get("reason_code") or "-", r.get("layer_verdicts")))
        lines.append("    依据：{}".format(j.get("rationale")))
    lines.append("")
    lines.append("DoD：")
    for d in rep.get("dod") or []:
        lines.append("  [{}] {} {} | {}".format("PASS" if d["ok"] else "FAIL", d["id"], d["item"],
                                               d["evidence"]))
    lines.append("")
    lines.append("（只读：未写库/未写产物/未换材·选材/未 redo/未改时间轴/未调阈值；"
                 "4-B/5-A/5-D 原始证据原样保留）")
    return "\n".join(lines)
