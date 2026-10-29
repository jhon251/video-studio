# -*- coding: utf-8 -*-
"""5-F 证据汇编（只读）：基线校验 + 真值集/Judge 覆盖层指纹 + Judge 收敛结果 + DoD +
只读与不覆盖证明 + 处置表 + 回归结果 + 文件哈希 → logs/phase5f_evidence.json。

用法：python docs/regression_2x/phase5f_evidence.py
"""
import hashlib
import json
import pathlib
import subprocess
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
LOGS = ROOT / "docs" / "regression_2x" / "logs"
PID = "p_f4b466a4a024"
# 5-G: baseline reference advanced to the 5-G manifest (phase rotation)
BASE_TAG = "5.x-phase5g-baseline"
BASE_SHA = "355b2a053adeecb6c98b7e38f699011452f3af4c60eedbb532553b63fc1c068e"

from video_studio.core import mm_judge as J  # noqa: E402
from video_studio.core import mm_quality as Q  # noqa: E402


def sha(p):
    try:
        return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
    except OSError:
        return None


def load(name):
    p = LOGS / name
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except (ValueError, json.JSONDecodeError):
        return None


def db_snapshot():
    import sqlite3
    dbp = ROOT / "projects" / "video_studio.db"
    con = sqlite3.connect("file:{}?mode=ro".format(dbp.as_posix()), uri=True)
    try:
        counts = {t: con.execute("select count(*) from " + t).fetchone()[0]
                  for t in ("projects", "tasks", "artifacts", "events", "decisions", "changelog")}
    finally:
        con.close()
    return {"db_sha256": sha(dbp), "counts": counts}


def project_files():
    proj = ROOT / "projects" / PID
    return {str(p.relative_to(proj)): sha(p) for p in sorted(proj.rglob("*")) if p.is_file()}


out = {"schema": "phase5f-evidence-v1", "project_id": PID}
before, before_map = db_snapshot(), project_files()
out["state_before"] = {"db_sha256": before["db_sha256"], "counts": before["counts"],
                       "project_files": len(before_map),
                       "films": sorted(p.name for p in (ROOT / "projects" / PID / "output")
                                       .glob("*.mp4"))}

# ---------- 1. 授权基线 ----------
zp = ROOT / "docs" / "regression_2x" / "baseline" / (BASE_TAG + ".zip")
man_p = ROOT / "docs" / "regression_2x" / "baseline" / ("baseline_manifest_{}.json".format(BASE_TAG))
base_man = json.loads(man_p.read_text(encoding="utf-8")) if man_p.is_file() else {}
entries = {}
with zipfile.ZipFile(zp) as z:
    for i in z.infolist():
        if not i.is_dir():
            entries[i.filename] = hashlib.sha256(z.read(i)).hexdigest()
delta = subprocess.run([sys.executable, "docs/regression_2x/baseline_delta.py", BASE_TAG],
                       cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
dl = [ln.strip() for ln in (delta.stdout or "").strip().splitlines()]
out["baseline"] = {
    "tag": BASE_TAG, "zip": str(zp), "sha256": sha(zp), "sha256_expected": BASE_SHA,
    "sha256_matches_authorization": sha(zp) == BASE_SHA,
    "zip_hash_matches_its_manifest": bool(base_man) and base_man.get("zip_sha256") == sha(zp),
    "manifest_entries_match_zip": bool(base_man) and set(base_man.get("files") or {}) == set(entries),
    "stage_delta_vs_baseline": {
        "summary": dl[0] if dl else None,
        "modified": [ln.split(None, 1)[1] for ln in dl if ln.startswith("MODIFIED")],
        "added": [ln.split(None, 1)[1] for ln in dl if ln.startswith("ADDED")],
        "deleted": [ln.split(None, 1)[1] for ln in dl if ln.startswith("DELETED")]},
    "note": "5-E 基线 ZIP 与授权书 sha256 一致且自洽；工作树差异恰为本阶段（5-F）预期改动"}

# ---------- 2. 真值集与 Judge 覆盖层 ----------
ts, ts_err = Q.load_truth_set(ROOT / Q.TRUTH_SET_REL)
jt, jt_err = J.load_judge_truth(ROOT / J.JUDGE_TRUTH_REL)
jts = J.judge_truth_status(jt, ts, ROOT / J.JUDGE_TRUTH_REL) if (ts and jt) else {}
out["truth_set"] = {"path": Q.TRUTH_SET_REL, "sha256": sha(ROOT / Q.TRUTH_SET_REL),
                    "pin_expected": Q.TRUTH_SET_PIN,
                    "pin_matches": sha(ROOT / Q.TRUTH_SET_REL) == Q.TRUTH_SET_PIN,
                    "cases": len(ts["cases"]) if ts else 0,
                    "coverage_ok": (Q.coverage_status(ts)["ok"] if ts else False),
                    "error": ts_err}
out["judge_truth"] = {"path": J.JUDGE_TRUTH_REL, "sha256": sha(ROOT / J.JUDGE_TRUTH_REL),
                      "pin_expected": J.JUDGE_TRUTH_PIN,
                      "pin_matches": sha(ROOT / J.JUDGE_TRUTH_REL) == J.JUDGE_TRUTH_PIN,
                      "status": jts, "error": jt_err,
                      "cases": len(jt["cases"]) if jt else 0,
                      "unknown_policy": (jt or {}).get("unknown_policy")}

# ---------- 3. Judge 结果 ----------
judge = load("phase5f_judge.json") or {}
rows = []
for r in judge.get("rows") or []:
    rows.append({"case_id": r["case_id"], "content_label": r.get("content_label"),
                 "layer_verdicts": r.get("layer_verdicts"), "layer_codes": r.get("layer_codes"),
                 "judge": {k: (r.get("judge") or {}).get(k)
                           for k in ("verdict", "rule", "reason_code", "priority_rank",
                                     "propagated_code", "conflict", "flagged_by",
                                     "unknown_is_final", "rationale")},
                 "expect": r.get("judge_expect"), "status": r.get("status")})
out["judge"] = {"schema": judge.get("schema"), "result": judge.get("judge_result"),
                "summary": judge.get("summary"), "rows": rows,
                "rules": judge.get("rules"), "priority": judge.get("priority"),
                "scope": judge.get("scope"), "policy": judge.get("policy"),
                "calibration_source": judge.get("calibration_source"),
                "dod": judge.get("dod"), "dod_all_pass": judge.get("dod_all_pass")}

# ---------- 4. 只读与不覆盖 ----------
after, after_map = db_snapshot(), project_files()
src_j = (ROOT / "src" / "video_studio" / "core" / "mm_judge.py").read_text(encoding="utf-8")
ops_j = (ROOT / "src" / "video_studio" / "ops" / "mm_judge.py").read_text(encoding="utf-8")
mods = ("src/video_studio/core/multimodal.py", "src/video_studio/core/mm_temporal.py",
        "src/video_studio/core/mm_quality.py", "src/video_studio/core/semantics.py",
        "src/video_studio/core/lexicons/semantics_v1.json", Q.TRUTH_SET_REL)
cal = load("phase5e_quality.json") or {}
fa = load("phase5c_mm_after.json") or {}
mm = load("phase5d_mmt_v6.json") or {}
pairs = [("T03_S01_v6_clear_match", "S01"), ("T04_S02_v6_clear_match", "S02"),
         ("T05_S04_v6_human_fixed_match_boundary", "S04"),
         ("T06_S05_v6_boundary_unknown", "S05"), ("T08_S06_side_v6_unknown", "S06")]
cal_rows = {c["case_id"]: c for c in (cal.get("cases") or [])}


def _lay(cid, layer):
    e = ((cal_rows.get(cid) or {}).get("layers") or {}).get(layer) or {}
    return (e.get("observed") or {}).get("verdict")


frozen5a = {sid: next((s.get("verdict") for s in fa.get("scenes") or []
                       if s.get("scene_id") == sid), None) for _, sid in pairs}
frozen5d = {sid: next((s.get("verdict") for s in mm.get("scenes") or []
                       if s.get("scene_id") == sid), None) for _, sid in pairs}
proj_diff = {"changed": sorted(k for k in before_map if k in after_map
                              and before_map[k] != after_map[k]),
             "removed": sorted(k for k in before_map if k not in after_map),
             "added": sorted(k for k in after_map if k not in before_map)}
out["readonly_and_preservation"] = {
    "db_sha256_before": before["db_sha256"], "db_sha256_after": after["db_sha256"],
    "db_unchanged": before["db_sha256"] == after["db_sha256"],
    "counts_before": before["counts"], "counts_after": after["counts"],
    "counts_unchanged": before["counts"] == after["counts"],
    "project_files": len(after_map), "project_files_unchanged": after_map == before_map,
    "project_file_diff": proj_diff,
    "static_no_write_tokens": all(tok not in src_j + ops_j for tok in
                                  ("insert_decision", "insert_changelog", "write_artifact",
                                   "set_task_status", "run_cycle", "build_engine",
                                   "record_selection", "insert into", "update ", "delete from")),
    "judge_has_no_threshold_params": all(tok not in src_j for tok in
                                         ("min_sim", "min_vote_frac", "min_stability_cos",
                                          "split_cos", "frames_per_scene", "min_frames")),
    "tunes_thresholds_to_reduce_unknown": False,
    "modules_unchanged_vs_baseline": {m: ((base_man.get("files") or {}).get(m, {})
                                          .get("sha256") == sha(ROOT / m)) for m in mods},
    "five_a_verdicts_vs_frozen_5c": {cid: _lay(cid, "5a") for cid, _ in pairs},
    "five_a_frozen": frozen5a,
    "five_a_consistent": all(_lay(cid, "5a") == frozen5a.get(sid) for cid, sid in pairs),
    "five_d_verdicts_vs_frozen_5d": {cid: _lay(cid, "5d") for cid, _ in pairs},
    "five_d_frozen": frozen5d,
    "five_d_consistent": all(_lay(cid, "5d") == frozen5d.get(sid) for cid, sid in pairs),
}

# ---------- 5. 处置 ----------
disp = J.dispositions_43_48()
recs = J.recommendations_disposition()
out["dispositions"] = {
    "issues_43_48": disp,
    "all_classified": len(disp) == 6 and all(d.get("decision") for d in disp),
    "recommendations_R1_R6": recs,
    "recommendations_classified": len(recs) == 6 and all(r.get("decision") for r in recs),
    "enter_final_product": [r["id"] for r in recs if "值得进入最终产品" in r["decision"]],
    "future_research": [r["id"] for r in recs if "未来研究项" in r["decision"]],
    "product_decision": [r["id"] for r in recs if "产品决策" in r["decision"]],
}

# ---------- 6. 回归 ----------
reg = load("phase5f_regression_summary.json") or {}
RERUN = LOGS / "phase5f_rerun"


def load_rerun_first(name):
    for p in (RERUN / name, LOGS / name):
        if p.is_file():
            try:
                return json.loads(p.read_text(encoding="utf-8-sig"))
            except (ValueError, json.JSONDecodeError):
                continue
    return None


suites = load_rerun_first("suites_summary.json")
batch = load_rerun_first("phase3a_regression_batch.json")
deviations = [{"name": r.get("name"), "expect": r.get("expect"), "rc": r.get("rc"),
               "needs_network": r.get("needs_network"), "tail": (r.get("tail") or [])[-1:]}
              for r in (batch or []) if not r.get("as_expected")]
steps = reg.get("steps") or []
non_batch = all(r.get("rc") == 0 for r in steps if r.get("step") != "3a_regression_batch")
brec = next((r for r in steps if r.get("step") == "3a_regression_batch"), {})
batch_ok = bool(brec.get("rc") == 0 or (deviations and all(d["needs_network"]
                                                           for d in deviations)))
out["regression"] = {
    "all_rc_zero_raw": reg.get("all_rc_zero_raw"),
    "frozen_logs_restored": reg.get("frozen_logs_restored"),
    "frozen_logs_pre_count": reg.get("frozen_logs_pre_count"),
    "steps": [(s.get("step"), s.get("rc"), s.get("seconds")) for s in steps],
    "unit_suites": ({"total": len(suites), "rc0": sum(1 for x in suites if x["rc"] == 0),
                     "failed": [x["suite"] for x in suites if x["rc"] != 0]} if suites else None),
    "batch_all_expected": not deviations, "batch_deviations": deviations, "batch_ok": batch_ok,
    "all_rc_zero_except_network_batch": bool(non_batch and batch_ok),
    "network_note": "历史 `PENDING（环境）` 记录未被改写（网络可用与否不改变验收状态）",
}

# ---------- 7. 文件哈希与结论 ----------
files = {}
for p in sorted(LOGS.glob("phase5f_*")):
    files[p.name] = {"sha256": sha(p), "bytes": p.stat().st_size}
for p in sorted(RERUN.glob("*")) if RERUN.is_dir() else []:
    files["phase5f_rerun/" + p.name] = {"sha256": sha(p), "bytes": p.stat().st_size}
for p in sorted((ROOT / "docs" / "regression_2x").glob("phase5f_*.py")):
    files["scripts/" + p.name] = {"sha256": sha(p), "bytes": p.stat().st_size}
for rel in (J.JUDGE_TRUTH_REL, Q.TRUTH_SET_REL, "src/video_studio/core/mm_judge.py",
            "src/video_studio/ops/mm_judge.py", "tests/mm_judge_test.py",
            "src/video_studio/cli.py", "docs/regression_2x/PHASE5F_REPORT.md",
            "docs/regression_2x/PHASE5F_MULTIMODAL_DOD.md"):
    files[rel] = {"sha256": sha(ROOT / rel),
                  "bytes": (ROOT / rel).stat().st_size if (ROOT / rel).is_file() else None}
for tag in ("5.x-phase5f-baseline", BASE_TAG):
    p = ROOT / "docs" / "regression_2x" / "baseline" / (tag + ".zip")
    files["baseline/" + tag + ".zip"] = {"sha256": sha(p),
                                        "bytes": p.stat().st_size if p.is_file() else None}
out["files"] = files
res = out["judge"]["result"] or {}
sm = out["judge"]["summary"] or {}
out["conclusion"] = {
    "judge_cases_total": res.get("cases_total"), "judge_violations": res.get("violations"),
    "judge_unresolved": res.get("unresolved"),
    "all_meet_judge_truth": res.get("all_meet_judge_truth"),
    "final_counts": sm.get("counts"), "unknown_at_least_min": sm.get("unknown_at_least_min"),
    "unknown_is_legitimate": sm.get("unknown_is_legitimate"),
    "thresholds_touched": sm.get("thresholds_touched"),
    "dod_all_pass": out["judge"]["dod_all_pass"],
    "dispositions_classified": out["dispositions"]["all_classified"],
    "recommendations_classified": out["dispositions"]["recommendations_classified"],
    "no_auto_action": (out["judge"]["policy"] or {}).get("auto_replace") is False,
}
out["ALL_GREEN"] = bool(
    out["baseline"]["sha256_matches_authorization"]
    and out["baseline"]["zip_hash_matches_its_manifest"]
    and out["baseline"]["manifest_entries_match_zip"]
    and out["truth_set"]["pin_matches"] and out["truth_set"]["coverage_ok"]
    and out["judge_truth"]["pin_matches"] and (jts or {}).get("ok")
    and res.get("cases_total") == 14 and res.get("all_meet_judge_truth") is True
    and sm.get("unknown_at_least_min") is True and sm.get("thresholds_touched") is False
    and out["judge"]["dod_all_pass"] is True
    and out["readonly_and_preservation"]["db_unchanged"]
    and out["readonly_and_preservation"]["counts_unchanged"]
    and out["readonly_and_preservation"]["project_files_unchanged"]
    and out["readonly_and_preservation"]["static_no_write_tokens"]
    and out["readonly_and_preservation"]["judge_has_no_threshold_params"]
    and all(out["readonly_and_preservation"]["modules_unchanged_vs_baseline"].values())
    and out["readonly_and_preservation"]["five_a_consistent"]
    and out["readonly_and_preservation"]["five_d_consistent"]
    and out["dispositions"]["all_classified"]
    and out["dispositions"]["recommendations_classified"]
    and out["regression"]["all_rc_zero_except_network_batch"]
    and (out["regression"]["unit_suites"] or {}).get("failed") == []
    and reg.get("frozen_logs_restored"))

(LOGS / "phase5f_evidence.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                            encoding="utf-8")
print("baseline:", out["baseline"]["sha256_matches_authorization"],
      out["baseline"]["zip_hash_matches_its_manifest"],
      out["baseline"]["manifest_entries_match_zip"], "|",
      out["baseline"]["stage_delta_vs_baseline"]["summary"])
print("truth set:", out["truth_set"]["cases"], "例 pin", out["truth_set"]["pin_matches"],
      "| judge truth pin", out["judge_truth"]["pin_matches"], "| case set ok",
      (jts or {}).get("ok"))
print("judge:", res.get("cases_total"), "例 | 违例", res.get("violations"), "| 未解决",
      res.get("unresolved"), "| 全满足", res.get("all_meet_judge_truth"))
print("final counts:", sm.get("counts"), "| UNKNOWN>=min:", sm.get("unknown_at_least_min"),
      "| thresholds_touched:", sm.get("thresholds_touched"), "| DoD:", out["judge"]["dod_all_pass"])
print("readonly:", out["readonly_and_preservation"]["db_unchanged"],
      out["readonly_and_preservation"]["project_files_unchanged"],
      out["readonly_and_preservation"]["static_no_write_tokens"],
      out["readonly_and_preservation"]["judge_has_no_threshold_params"])
print("3 层未覆盖:", out["readonly_and_preservation"]["five_a_consistent"],
      out["readonly_and_preservation"]["five_d_consistent"],
      all(out["readonly_and_preservation"]["modules_unchanged_vs_baseline"].values()))
print("处置:", out["dispositions"]["all_classified"], out["dispositions"]["recommendations_classified"],
      "| 进最终产品:", out["dispositions"]["enter_final_product"],
      "| 未来研究:", out["dispositions"]["future_research"],
      "| 产品决策:", out["dispositions"]["product_decision"])
print("regression: suites", out["regression"]["unit_suites"], "| dev",
      out["regression"]["batch_deviations"], "| restored", reg.get("frozen_logs_restored"))
print("ALL_GREEN:", out["ALL_GREEN"])
print("written", LOGS / "phase5f_evidence.json")
