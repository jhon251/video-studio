# -*- coding: utf-8 -*-
"""6-B/M3 收尾核对（只读汇总）：基线完整性、守卫状态、M2 测试、电池/套件/批次、代码指纹、母版未被改写。

用法: python docs/regression_2x/phase6a_m3_final_check.py
产出: logs/phase6b_m3_final_check.json
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
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


out = {"stage": "6-B/M3"}

# ---- 1) 基线完整性：ZIP sha == manifest，且未新增/缺失 ----
baselines = {}
for tag in TAGS:
    z = BASE / "{}.zip".format(tag)
    m = BASE / "baseline_manifest_{}.json".format(tag)
    rec = {"zip_sha256": sha(z), "zip_bytes": z.stat().st_size,
           "zip_mtime": z.stat().st_mtime}
    if m.is_file():
        man = json.loads(m.read_text(encoding="utf-8"))
        rec["manifest_zip_sha256"] = man["zip_sha256"]
        rec["zip_matches_manifest"] = man["zip_sha256"] == rec["zip_sha256"]
        rec["manifest_file_count"] = man["file_count"]
    baselines[tag] = rec
    print("[baseline] {:44s} zip==manifest:{} files:{}".format(
        tag, rec.get("zip_matches_manifest"), rec.get("manifest_file_count")))
out["baselines"] = baselines

# ---- 2) 守卫状态（M2 版，含授权/未授权区分）----
g = json.loads((LOGS / "phase6b_m3_guard_check.json").read_text(encoding="utf-8"))
print("[guard] drifted:", g["guards_drifted"], "| 未授权:", g["unexpected_guard_drift"])
print("[guard] 工作树相对 r3 漂移:", g["tree_drift_vs_r3"], "| 缺失:", g["tree_missing_vs_r3"])
out["guard"] = {k: g[k] for k in ("guards_checked", "guards_drifted",
                                  "m2_authorized_guard_change", "unexpected_guard_drift",
                                  "tree_drift_vs_r3", "tree_missing_vs_r3",
                                  "r3_zip_unchanged_vs_manifest", "final_zip_unchanged")}

# ---- 3) M3 电池（25 步 + 冻结日志恢复；含 step2 外部逐项执行的口径）----
b = json.loads((LOGS / "phase6b_m3_regression_summary.json").read_text(encoding="utf-8"))
print("[battery] steps {} | rc!=0 {} | rc_pending {} | 外部执行 {} | 日志恢复 {} | 各步秒数和 {}s".format(
    b["steps_count"], b["rc_nonzero"], b.get("rc_pending"),
    b.get("steps_executed_externally"), b["frozen_logs_restored"], b.get("sum_steps_seconds")))
out["battery"] = {k: b.get(k) for k in ("steps_count", "rc_nonzero", "rc_pending",
                                        "steps_executed_externally", "all_rc_zero_raw",
                                        "frozen_logs_pre_count", "frozen_logs_changed",
                                        "frozen_logs_added", "frozen_logs_deleted",
                                        "frozen_logs_restored", "sum_steps_seconds",
                                        "seconds_this_launch")}
out["battery_steps"] = [{"step": r["step"], "rc": r["rc"], "seconds": r["seconds"],
                         "executed": r.get("executed", "battery")} for r in b["steps"]]
_ext = LOGS / "phase6b_m1_external_steps.json"
out["external_steps"] = (json.loads(_ext.read_text(encoding="utf-8"))
                         if _ext.is_file() else {"error": "缺少外部步骤记录"})

# ---- 4) step25 套件 + 批次 ----
s = json.loads((LOGS / "phase6b_m3_rerun" / "suites_summary.json").read_text(encoding="utf-8"))
bad = [x["suite"] for x in s if x["rc"] != 0]
print("[suites] {} 个 | rc=0 {} | rc!=0 {}".format(len(s), len(s) - len(bad), bad))
out["suites"] = {"total": len(s), "rc0": len(s) - len(bad), "failed": bad,
                 "ratios": {x["suite"]: x["ratios"] for x in s}}
bp_path = LOGS / "phase6b_m3_batch_items.json"
if bp_path.is_file():
    bp = json.loads(bp_path.read_text(encoding="utf-8"))
    ne = bp.get("unexpected") or []
    print("[batch] {} 项（逐项执行）| 符合预期 {} | 非预期 {}（环境项：{}）".format(
        bp["total"], bp["as_expected_count"], ne,
        list((bp.get("environment_pending") or {}) or
             (out.get("external_steps", {}).get("steps", {})
              .get("3a_regression_batch", {}) or {}).get("environment_pending", {}))))
    out["batch"] = {"total": bp["total"], "as_expected": bp["as_expected_count"],
                    "not_as_expected": ne,
                    "step_rc_equivalent": bp.get("step_rc_equivalent"),
                    "source": bp.get("source_of_items")}
    out["batch_environment_pending"] = (out.get("external_steps", {}).get("steps", {})
                                        .get("3a_regression_batch", {})
                                        .get("environment_pending", {}))
else:
    out["batch"] = {"error": "缺少 phase6b_m3_batch_items.json"}

# ---- 5) 代码指纹（M1 → M2 → M3 → 6-B/M3；本轮增量单独列出）----
subprocess.run([PY, "docs/regression_2x/phase5m_code_fingerprint.py", "6bm3"], cwd=str(ROOT),
               capture_output=True, text=True, encoding="utf-8", errors="replace")
m1 = json.loads((LOGS / "phase5m_code_fingerprint_now.json").read_text(encoding="utf-8"))
m2 = json.loads((LOGS / "phase5m_code_fingerprint_m2.json").read_text(encoding="utf-8"))
m3 = json.loads((LOGS / "phase5m_code_fingerprint_m3.json").read_text(encoding="utf-8"))
m4 = json.loads((LOGS / "phase5m_code_fingerprint_6bm1.json").read_text(encoding="utf-8"))
m5 = json.loads((LOGS / "phase5m_code_fingerprint_6bm2.json").read_text(encoding="utf-8"))
m6 = json.loads((LOGS / "phase5m_code_fingerprint_6bm3.json").read_text(encoding="utf-8"))


def _delta(a, b):
    return (sorted(k for k in a["files"] if k in b["files"] and a["files"][k] != b["files"][k]),
            sorted(k for k in b["files"] if k not in a["files"]),
            sorted(k for k in a["files"] if k not in b["files"]))


changed, added, removed = _delta(m5, m6)
print("[fingerprint] 6-B/M2 {} 文件 {} -> 6-B/M3 {} 文件 {}".format(
    m5["count"], m5["aggregate_sha256"][:16], m6["count"], m6["aggregate_sha256"][:16]))
print("[fingerprint] 6-B/M3 增量: 变化 {} 新增 {} 删除 {}".format(len(changed), len(added),
                                                                len(removed)))
out["fingerprint"] = {"m1": {"count": m1["count"], "aggregate_sha256": m1["aggregate_sha256"]},
                      "m2": {"count": m2["count"], "aggregate_sha256": m2["aggregate_sha256"]},
                      "m3": {"count": m3["count"], "aggregate_sha256": m3["aggregate_sha256"]},
                      "6bm1": {"count": m4["count"], "aggregate_sha256": m4["aggregate_sha256"]},
                      "6bm2": {"count": m5["count"], "aggregate_sha256": m5["aggregate_sha256"]},
                      "6bm3": {"count": m6["count"], "aggregate_sha256": m6["aggregate_sha256"]},
                      "6bm2_to_6bm3": {"changed": changed, "added": added, "removed": removed}}

# ---- 6) 历史母版未被改写 ----
v9 = {"path": str(V9_FILM.relative_to(ROOT)), "exists": V9_FILM.is_file()}
if V9_FILM.is_file():
    v9.update({"sha256": sha(V9_FILM), "bytes": V9_FILM.stat().st_size,
               "unchanged_vs_m1_record": (sha(V9_FILM) == V9_SHA
                                          and V9_FILM.stat().st_size == V9_BYTES)})
print("[master] v9 成片未被改写:", v9.get("unchanged_vs_m1_record"))
out["historical_masters"] = {"v9_film": v9}

# ---- 7) 本轮（6-B/M3）授权变更清单（源码侧；docs 侧脚本/报告另列）----
MODIFIED = ["src/video_studio/cli.py",
            "tests/maintenance_fixes_test.py",
            "tests/dq_truth_test.py"]
ADDED = ["src/video_studio/core/revision.py",
         "src/video_studio/ops/revision.py",
         "tests/fixtures/revision_proposal_truth_v1.json",
         "tests/revision_truth_test.py",
         "docs/regression_2x/PHASE6B_M3_REPORT.md",
         "docs/regression_2x/phase6b_m3_build_truth.py",
         "docs/regression_2x/phase6b_m3_v9_proposals.py",
         "docs/regression_2x/phase6b_m3_batch_items.py",
         "docs/regression_2x/phase6b_m3_battery.py",
         "docs/regression_2x/phase6b_m3_guard_check.py",
         "docs/regression_2x/phase6b_m3_final_check.py"]
stats = {}
for rel in MODIFIED + ADDED:
    p = ROOT / rel
    if p.is_file():
        stats[rel] = {"bytes": p.stat().st_size, "sha256": sha(p),
                      "lines": len(p.read_text(encoding="utf-8").splitlines())}
    else:
        stats[rel] = {"missing": True}
out["file_stats"] = stats
out["m2_source_changes"] = {"modified": MODIFIED, "added": ADDED}
for rel in MODIFIED + ADDED:
    s = stats[rel]
    print("[file] {:60s} {} lines {} bytes {}".format(
        rel, s.get("lines"), s.get("bytes"), str(s.get("sha256"))[:16]))

(LOGS / "phase6b_m3_final_check.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                                  encoding="utf-8")
print("json ->", LOGS / "phase6b_m3_final_check.json")
