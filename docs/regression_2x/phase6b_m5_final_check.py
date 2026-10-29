# -*- coding: utf-8 -*-
"""6-B/M5 收尾核对（只读汇总）：基线完整性、守卫状态、M5 套件、电池/批次、执行证据、
代码指纹、母版未被改写。

用法: python docs/regression_2x/phase6b_m5_final_check.py
产出: logs/phase6b_m5_final_check.json
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
LOGS = ROOT / "docs" / "regression_2x" / "logs"
BASE = ROOT / "docs" / "regression_2x" / "baseline"
PY = sys.executable
TAGS = ["5.x-post-final-maintenance-baseline", "5.x-post-final-maintenance-baseline-r2",
        "5.x-post-final-maintenance-baseline-r3", "5.x-final-baseline"]
V9_FILM = ROOT / "projects" / "p_96efdc03e1aa" / "output" / "t_d0a54bdf1810_draft.mp4"
V9_SHA = "22705c7d7ea20b40d91120146066b89ab2b5fa5c1a1cab18f5346d4c66497651"
V9_BYTES = 46761341


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


out = {"stage": "6-B/M5"}

# ---- 1) 基线完整性 ----
baselines = {}
for tag in TAGS:
    z = BASE / "{}.zip".format(tag)
    m = BASE / "baseline_manifest_{}.json".format(tag)
    rec = {"zip_sha256": sha(z), "zip_bytes": z.stat().st_size, "zip_mtime": z.stat().st_mtime}
    if m.is_file():
        man = json.loads(m.read_text(encoding="utf-8"))
        rec["manifest_zip_sha256"] = man["zip_sha256"]
        rec["zip_matches_manifest"] = man["zip_sha256"] == rec["zip_sha256"]
        rec["manifest_file_count"] = man["file_count"]
    baselines[tag] = rec
    print("[baseline] {:44s} zip==manifest:{} files:{}".format(
        tag, rec.get("zip_matches_manifest"), rec.get("manifest_file_count")))
out["baselines"] = baselines
out["baseline_zips"] = sorted(p.name for p in BASE.glob("*.zip"))

# ---- 2) 守卫状态 ----
g = json.loads((LOGS / "phase6b_m5_guard_check.json").read_text(encoding="utf-8"))
print("[guard] drifted:", g["guards_drifted"], "| 未授权:", g["unexpected_guard_drift"])
print("[guard] 工作树相对 r3 漂移:", g["tree_drift_vs_r3"], "| 缺失:", g["tree_missing_vs_r3"])
out["guard"] = {k: g[k] for k in ("guards_checked", "guards_drifted",
                                  "m2_authorized_guard_change", "unexpected_guard_drift",
                                  "tree_drift_vs_r3", "tree_missing_vs_r3",
                                  "r3_zip_unchanged_vs_manifest", "final_zip_unchanged")}

# ---- 3) M5 电池 ----
b = json.loads((LOGS / "phase6b_m5_regression_summary.json").read_text(encoding="utf-8"))
print("[battery] steps {} | rc!=0 {} | rc_pending {} | 外部执行 {} | 日志恢复 {} | 秒数和 {}s".format(
    b["steps_count"], b["rc_nonzero"], b.get("rc_pending"), b.get("steps_executed_externally"),
    b["frozen_logs_restored"], b.get("sum_steps_seconds")))
out["battery"] = {k: b.get(k) for k in ("steps_count", "rc_nonzero", "rc_pending",
                                        "steps_executed_externally", "all_rc_zero_raw",
                                        "frozen_logs_pre_count", "frozen_logs_changed",
                                        "frozen_logs_added", "frozen_logs_deleted",
                                        "frozen_logs_restored", "sum_steps_seconds",
                                        "seconds_this_launch")}
out["battery_steps"] = [{"step": r["step"], "rc": r["rc"], "seconds": r["seconds"],
                         "executed": r.get("executed", "battery")} for r in b["steps"]]
_ext = LOGS / "phase6b_m5_external_steps.json"
out["external_steps"] = (json.loads(_ext.read_text(encoding="utf-8")) if _ext.is_file()
                         else {"error": "缺少外部步骤记录"})

# ---- 4) step25 套件 + 批次 ----
s = json.loads((LOGS / "phase6b_m5_rerun" / "suites_summary.json").read_text(encoding="utf-8"))
bad = [x["suite"] for x in s if x["rc"] != 0]
print("[suites] {} 个 | rc=0 {} | rc!=0 {}".format(len(s), len(s) - len(bad), bad))
out["suites"] = {"total": len(s), "rc0": len(s) - len(bad), "failed": bad,
                 "m5_suites": [x["suite"] for x in s if "execution" in x["suite"]]}
bp_path = LOGS / "phase6b_m5_batch_items.json"
if bp_path.is_file():
    bp = json.loads(bp_path.read_text(encoding="utf-8"))
    print("[batch] {} 项 | 符合预期 {} | 非预期 {}".format(
        bp["total"], bp["as_expected_count"], bp.get("unexpected") or []))
    out["batch"] = {"total": bp["total"], "as_expected": bp["as_expected_count"],
                    "not_as_expected": bp.get("unexpected") or [],
                    "step_rc_equivalent": bp.get("step_rc_equivalent"),
                    "source": bp.get("source_of_items")}
else:
    out["batch"] = {"error": "缺少 phase6b_m5_batch_items.json"}

# ---- 5) M5 执行证据 ----
ev = {}
for name, key in (("phase6b_m5_truth_freeze.json", "truth_freeze"),
                  ("phase6b_m5_v9_execution.json", "v9_execution")):
    p = LOGS / name
    ev[key] = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {"error": name}
out["execution_evidence"] = ev
tf, v9 = ev["truth_freeze"], ev["v9_execution"]
sv = v9.get("summary") or {}
print("[truth] canonical sha256:", str(tf.get("truth_canonical_sha256"))[:16],
      "| cases conflict/asset/batch:", tf.get("conflict_case_count"), "/",
      tf.get("asset_case_count"), "/", tf.get("batch_case_count"))
print("[v9] state_counts:", json.dumps(sv.get("state_counts"), ensure_ascii=False))
print("[v9] executed:", sv.get("executed_succeeded"), "| blocked_conflict:",
      sv.get("blocked_conflict"), "| already_executed:", sv.get("blocked_already_executed"))
print("[v9] asset E2E replaced:", [(e["proposal_label"], e["asset_evidence"]["replaced"],
                                    e["asset_evidence"]["corr_new_mean"])
                                   for e in (v9.get("asset_e2e") or [])])
print("[v9] 无真实素材证据的成功者:", sv.get("succeeded_without_real_asset_evidence"),
      "| auto_approved:", sv.get("auto_approved"), "| promoted:", sv.get("promoted"))
out["execution_evidence_summary"] = {
    "truth_canonical_sha256": tf.get("truth_canonical_sha256"),
    "cases": [tf.get("conflict_case_count"), tf.get("asset_case_count"),
              tf.get("batch_case_count")],
    "v9_state_counts": sv.get("state_counts"),
    "v9_executed_succeeded": sv.get("executed_succeeded"),
    "v9_blocked_conflict": sv.get("blocked_conflict"),
    "v9_blocked_already_executed": sv.get("blocked_already_executed"),
    "v9_pending_human_asset": sv.get("pending_human_asset"),
    "v9_failed": sv.get("failed"),
    "v9_asset_e2e": [(e["proposal_label"], e["asset_evidence"]["asset_id"],
                      e["asset_evidence"]["replaced"], e["asset_evidence"]["corr_new_mean"])
                     for e in (v9.get("asset_e2e") or [])],
    "v9_ledger": sv.get("ledger"),
    "v9_read_only": v9.get("read_only_evidence"),
    "conflict_pairs_m5": len(((v9.get("conflict_matrices") or {}).get("m5_set") or {})
                             .get("pairs") or []),
    "conflict_pairs_m3": ((v9.get("conflict_matrices") or {}).get("m3_register_8") or {})
                         .get("conflict_pair_count"),
}

# ---- 6) 代码指纹（… → 6-B/M4 → 6-B/M5）----
subprocess.run([PY, "docs/regression_2x/phase5m_code_fingerprint.py", "6bm5"], cwd=str(ROOT),
               capture_output=True, text=True, encoding="utf-8", errors="replace")
_LABELS = [("m1", "now"), ("m2", "m2"), ("m3", "m3"), ("6bm1", "6bm1"), ("6bm2", "6bm2"),
           ("6bm3", "6bm3"), ("6bm4", "6bm4"), ("6bm5", "6bm5")]
fps = {k: json.loads((LOGS / "phase5m_code_fingerprint_{}.json".format(lbl))
                     .read_text(encoding="utf-8")) for k, lbl in _LABELS}


def _delta(a, b):
    return (sorted(k for k in a["files"] if k in b["files"] and a["files"][k] != b["files"][k]),
            sorted(k for k in b["files"] if k not in a["files"]),
            sorted(k for k in a["files"] if k not in b["files"]))


changed, added, removed = _delta(fps["6bm4"], fps["6bm5"])
print("[fingerprint] 6-B/M4 {} 文件 {} -> 6-B/M5 {} 文件 {}".format(
    fps["6bm4"]["count"], fps["6bm4"]["aggregate_sha256"][:16],
    fps["6bm5"]["count"], fps["6bm5"]["aggregate_sha256"][:16]))
print("[fingerprint] 6-B/M5 增量: 变化 {} 新增 {} 删除 {} | 变化={} 新增={}".format(
    len(changed), len(added), len(removed), changed, added))
out["fingerprint"] = {k: {"count": v["count"], "aggregate_sha256": v["aggregate_sha256"]}
                      for k, v in fps.items()}
out["fingerprint"]["6bm4_to_6bm5"] = {"changed": changed, "added": added, "removed": removed}

# ---- 7) 历史母版 ----
v = {"path": str(V9_FILM.relative_to(ROOT)), "exists": V9_FILM.is_file()}
if V9_FILM.is_file():
    v.update({"sha256": sha(V9_FILM), "bytes": V9_FILM.stat().st_size,
              "unchanged_vs_m1_record": (sha(V9_FILM) == V9_SHA
                                         and V9_FILM.stat().st_size == V9_BYTES)})
print("[master] v9 成片未被改写:", v.get("unchanged_vs_m1_record"))
out["historical_masters"] = {"v9_film": v}
sb = ROOT / "output" / "phase6b_m4_sandbox"
out["m5_sandbox"] = {"root": str(sb.relative_to(ROOT)), "exists": sb.is_dir(),
                     "outside_project_dir": "projects" not in sb.parts,
                     "boxes": sorted(p.name for p in sb.iterdir() if p.is_dir())}

# ---- 8) 本轮（6-B/M5）变更清单 ----
MODIFIED = ["src/video_studio/core/execution.py",
            "src/video_studio/ops/execution.py",
            "tests/maintenance_fixes_test.py",
            "docs/regression_2x/phase6b_m4_m8e_negctl.py"]
ADDED = ["tests/fixtures/execution_reliability_truth_v1.json",
         "tests/execution_reliability_test.py",
         "docs/regression_2x/PHASE6B_M5_REPORT.md",
         "docs/regression_2x/phase6b_m5_build_truth.py",
         "docs/regression_2x/phase6b_m5_execute_v9.py",
         "docs/regression_2x/phase6b_m5_batch_items.py",
         "docs/regression_2x/phase6b_m5_battery.py",
         "docs/regression_2x/phase6b_m5_guard_check.py",
         "docs/regression_2x/phase6b_m5_final_check.py"]
stats = {}
for rel in MODIFIED + ADDED:
    p = ROOT / rel
    stats[rel] = ({"bytes": p.stat().st_size, "sha256": sha(p),
                   "lines": len(p.read_text(encoding="utf-8").splitlines())}
                  if p.is_file() else {"missing": True})
out["file_stats"] = stats
out["m5_source_changes"] = {"modified": MODIFIED, "added": ADDED}
for rel in MODIFIED + ADDED:
    s = stats[rel]
    print("[file] {:60s} {} lines {} bytes {}".format(
        rel, s.get("lines"), s.get("bytes"), str(s.get("sha256"))[:16]))

(LOGS / "phase6b_m5_final_check.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                                 encoding="utf-8")
print("json ->", LOGS / "phase6b_m5_final_check.json")
