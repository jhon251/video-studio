# -*- coding: utf-8 -*-
"""5-C 证据汇总（只读）：把本阶段全部证据文件 + 关键结论汇编为单一机器可读文件。

产出：docs/regression_2x/logs/phase5c_evidence.json
用法：python docs/regression_2x/phase5c_evidence.py
"""
import hashlib
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
LOGS = ROOT / "docs" / "regression_2x" / "logs"
OUT = LOGS / "phase5c_evidence.json"
PID = "p_f4b466a4a024"


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


EV = {
    "before": load("phase5c_before.json"),
    "after": load("phase5c_after.json"),
    "compare": load("phase5c_compare.json"),
    "candidates_before": load("phase5c_candidates_before.json"),
    "candidates_after": load("phase5c_mmb_after.json"),
    "mm_before_v5": load("phase5c_mm_before_v5.json"),
    "mm_after_v6": load("phase5c_mm_after.json"),
    "semantic_after": load("phase5c_semantic_after.json"),
    "film_verify": load("phase5c_film_verify.json"),
    "append_only": load("phase5c_append_only.json"),
    "db_append_only": load("phase5c_db_append_only.json"),
    "failclosed": load("phase5c_failclosed.json"),
    "regression": load("phase5c_regression_summary.json"),
}
missing = [k for k, v in EV.items() if v is None]

cmpj = EV["compare"] or {}
fv = EV["film_verify"] or {}
mmb = EV["mm_before_v5"] or {}
mma = EV["mm_after_v6"] or {}
sem = EV["semantic_after"] or {}
reg = EV["regression"] or {}
db = EV["db_append_only"] or {}
fc = EV["failclosed"] or {}
ao = EV["append_only"] or {}

steps = reg.get("steps") or []
RERUN = LOGS / "phase5c_rerun"


def load_rerun_first(name):
    """回归产物优先读本轮输出（logs/phase5c_rerun/），否则读冻结日志。"""
    for p in (RERUN / name, LOGS / name):
        if p.is_file():
            try:
                return json.loads(p.read_text(encoding="utf-8-sig"))
            except (ValueError, json.JSONDecodeError):
                continue
    return None


suites = None
s = load_rerun_first("suites_summary.json")
if s:
    suites = {"total": len(s), "rc0": sum(1 for x in s if x["rc"] == 0),
              "failed": [x["suite"] for x in s if x["rc"] != 0],
              "ratios": {x["suite"]: x.get("ratios") for x in s},
              "source": "logs/phase5c_rerun/suites_summary.json"}
batch = load_rerun_first("phase3a_regression_batch.json")
real_chain = load_rerun_first("phase3a_real_chain.json")

key = {
    "human_decision": {
        "decision_id": (cmpj.get("new_decisions") or [{}])[0].get("decision_id"),
        "changelog_id": (cmpj.get("new_changelog") or [{}])[0].get("change_id"),
        "made_by": (cmpj.get("new_decisions") or [{}])[0].get("made_by"),
        "target": (cmpj.get("new_changelog") or [{}])[0].get("target_id"),
    },
    "versions": cmpj.get("version_chain_after"),
    "scene_change": cmpj.get("timeline_changed_scenes"),
    "only_s06_changed": cmpj.get("timeline_all_other_scenes_identical"),
    "old_versions_intact": {
        "old_render_output_artifacts_unchanged": cmpj.get("old_render_output_artifacts_unchanged"),
        "old_film_files_still_present": cmpj.get("old_film_files_still_present"),
        "db_append_only_pass": db.get("ALL_PASS"),
        "unexpected_modified_rows": db.get("unexpected_modified_task_rows"),
        "allowed_dependency_rewire_count": len(db.get("allowed_dependency_rewire") or []),
    },
    "film": {"path": fv.get("film"), "sha256": fv.get("film_sha256"), "bytes": fv.get("film_bytes"),
             "duration_s": fv.get("duration_s"), "streams": fv.get("streams"),
             "measured_lufs": fv.get("measured_lufs"),
             "measured_true_peak_dbtp": fv.get("measured_true_peak_dbtp"),
             "loudness_independent_ok": fv.get("loudness_independent_ok"),
             "all_scenes_corr_ok": fv.get("all_scenes_corr_ok"),
             "s06_side_vs_front": fv.get("s06_side_vs_front"),
             "s06_replacement_confirmed_in_pixels":
                 fv.get("s06_replacement_confirmed_in_pixels")},
    "semantics": {"4b_counts": sem.get("counts"), "4b_summary": sem.get("summary"),
                  "5a_before_counts": mmb.get("counts"), "5a_after_counts": mma.get("counts"),
                  "5a_before_scenes": [(s.get("scene_id"), s.get("verdict"), s.get("code"))
                                       for s in (mmb.get("scenes") or [])],
                  "5a_after_scenes": [(s.get("scene_id"), s.get("verdict"), s.get("code"))
                                      for s in (mma.get("scenes") or [])],
                  "5b_counts_after": (EV["candidates_after"] or {}).get("counts")},
    "gates": {"attribution_ok": (ao.get("D_attribution") or {}).get("ok"),
              "license_gate_ok": (ao.get("E_license_gate") or {}).get("ok"),
              "render_selfcheck_ok": (ao.get("F_render_selfcheck") or {}).get("ok"),
              "append_only_ok": (ao.get("A_append_only") or {}).get("ok"),
              "unauthorized_scenes_ok": (ao.get("C_unauthorized_scenes") or {}).get("ok")},
    "failclosed": {"ALL_PASS": fc.get("ALL_PASS"), "zero_writes_all": fc.get("zero_writes_all"),
                   "cases": [(c.get("id"), c.get("rc"), c.get("pass"),
                              c.get("codes_found")) for c in (fc.get("cases") or [])]},
    "regression": {"all_rc_zero_raw": reg.get("all_rc_zero"),
                   "all_rc_zero_except_network_batch": None,   # 见下方计算
                   "batch_deviations": None,
                   "batch_deviations_all_network": None,
                   "frozen_logs_restored": reg.get("frozen_logs_restored"),
                   "steps": [(s.get("step"), s.get("rc"), s.get("seconds")) for s in steps],
                   "unit_suites": suites,
                   "real_chain": {"verdict": (real_chain or {}).get("verdict"),
                                  "pass": (real_chain or {}).get("pass"),
                                  "fail": (real_chain or {}).get("fail")},
                   "batch_summary": (batch or {}).get("summary") if isinstance(batch, dict) else None},
    "missing_evidence_files": missing,
}
# 批次里唯一非预期项若是**依赖真实网络**的项，则属环境条件（冻结记录为 PENDING（环境）），
# 不计入"代码回归"；此处如实列出偏差项与其 needs_network 标记，不做任何隐藏。
b_rows = batch if isinstance(batch, list) else (batch or {}).get("rows") or []
deviations = [{"name": r.get("name"), "expect": r.get("expect"), "rc": r.get("rc"),
               "needs_network": r.get("needs_network"), "tail": (r.get("tail") or [])[-1:]}
              for r in b_rows if not r.get("as_expected")]
key["regression"]["batch_deviations"] = deviations
key["regression"]["batch_deviations_all_network"] = bool(
    deviations and all(d["needs_network"] for d in deviations))
non_batch_rc0 = all(r.get("rc") == 0 for r in steps if r.get("step") != "3a_regression_batch")
key["regression"]["all_rc_zero_except_network_batch"] = bool(
    non_batch_rc0 and key["regression"]["batch_deviations_all_network"])
key["ALL_GREEN"] = bool(
    not missing and key["only_s06_changed"] and db.get("ALL_PASS") and ao.get("ALL_PASS")
    and fc.get("ALL_PASS") and fv.get("loudness_independent_ok") and fv.get("all_scenes_corr_ok")
    and fv.get("s06_replacement_confirmed_in_pixels")
    and key["regression"]["all_rc_zero_except_network_batch"]
    and (suites or {}).get("rc0") == (suites or {}).get("total")
    and reg.get("frozen_logs_restored"))

files = {}
for p in sorted(LOGS.glob("phase5c_*")):
    files[p.name] = {"sha256": sha(p), "bytes": p.stat().st_size}
for p in sorted((LOGS / "phase5c_rerun").glob("*")) if (LOGS / "phase5c_rerun").is_dir() else []:
    files["phase5c_rerun/" + p.name] = {"sha256": sha(p), "bytes": p.stat().st_size}
for p in sorted((ROOT / "docs" / "regression_2x").glob("phase5c_*.py")):
    files["scripts/" + p.name] = {"sha256": sha(p), "bytes": p.stat().st_size}
files["PHASE5C_REPORT.md"] = {"sha256": sha(ROOT / "docs" / "regression_2x" / "PHASE5C_REPORT.md"),
                              "bytes": (ROOT / "docs" / "regression_2x" / "PHASE5C_REPORT.md")
                              .stat().st_size
                              if (ROOT / "docs" / "regression_2x" / "PHASE5C_REPORT.md").is_file()
                              else None}
for tag in ("5.x-phase5c-baseline", "5.x-phase5b-baseline"):
    zp = ROOT / "docs" / "regression_2x" / "baseline" / (tag + ".zip")
    files["baseline/" + tag + ".zip"] = {"sha256": sha(zp),
                                         "bytes": zp.stat().st_size if zp.is_file() else None}
for tag in ("5.x-phase5c", "5.x-phase5b"):
    for ext in (".zip", ".db", ".json"):
        p = ROOT / "docs" / "regression_2x" / "snapshots" / (tag + "-20260916" + ext)
        if p.is_file():
            files["snapshots/" + p.name] = {"sha256": sha(p), "bytes": p.stat().st_size}

out = {"project_id": PID, "schema": "phase5c-evidence-v1", "key": key, "files": files}
OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

print("missing evidence:", missing)
print("ALL_GREEN:", key["ALL_GREEN"])
print(json.dumps(key["human_decision"], ensure_ascii=False))
print("scene change:", json.dumps(key["scene_change"], ensure_ascii=False))
print("film:", fv.get("film_sha256", "")[:16], fv.get("measured_lufs"), fv.get("measured_true_peak_dbtp"))
print("semantics 4b:", key["semantics"]["4b_counts"], "5a before/after:",
      key["semantics"]["5a_before_counts"], key["semantics"]["5a_after_counts"])
print("regression: raw all_rc_zero =", key["regression"]["all_rc_zero_raw"],
      "| except-network-batch =", key["regression"]["all_rc_zero_except_network_batch"],
      "| batch deviations =", json.dumps(deviations, ensure_ascii=False)[:300])
print("frozen logs restored:", key["regression"]["frozen_logs_restored"],
      "| suites:", suites and (suites["rc0"], suites["total"]))
print("files hashed:", len(files))
print("written", OUT)
