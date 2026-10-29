# -*- coding: utf-8 -*-
"""6-A/M2 收尾核对（只读汇总）：基线完整性、守卫状态、M2 测试、电池/套件/批次、代码指纹、母版未被改写。

用法: python docs/regression_2x/phase6a_m2_final_check.py
产出: logs/phase6a_m2_final_check.json
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


out = {"stage": "6-A/M2"}

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
g = json.loads((LOGS / "phase6a_m2_guard_check.json").read_text(encoding="utf-8"))
print("[guard] drifted:", g["guards_drifted"], "| 未授权:", g["unexpected_guard_drift"])
print("[guard] 工作树相对 r3 漂移:", g["tree_drift_vs_r3"], "| 缺失:", g["tree_missing_vs_r3"])
out["guard"] = {k: g[k] for k in ("guards_checked", "guards_drifted",
                                  "m2_authorized_guard_change", "unexpected_guard_drift",
                                  "tree_drift_vs_r3", "tree_missing_vs_r3",
                                  "r3_zip_unchanged_vs_manifest", "final_zip_unchanged")}

# ---- 3) M2 电池（25 步 + 冻结日志恢复）----
b = json.loads((LOGS / "phase6a_m2_regression_summary.json").read_text(encoding="utf-8"))
print("[battery] steps {} | rc!=0 {} | 日志恢复 {} | 总耗时 {}s".format(
    b["steps_count"], b["rc_nonzero"], b["frozen_logs_restored"], b["total_seconds"]))
out["battery"] = {k: b[k] for k in ("steps_count", "rc_nonzero", "all_rc_zero_raw",
                                    "frozen_logs_pre_count", "frozen_logs_changed",
                                    "frozen_logs_added", "frozen_logs_deleted",
                                    "frozen_logs_restored", "total_seconds")}
out["battery_steps"] = [{"step": r["step"], "rc": r["rc"], "seconds": r["seconds"]}
                        for r in b["steps"]]

# ---- 4) step25 套件 + 批次 ----
s = json.loads((LOGS / "phase6a_m2_rerun" / "suites_summary.json").read_text(encoding="utf-8"))
bad = [x["suite"] for x in s if x["rc"] != 0]
print("[suites] {} 个 | rc=0 {} | rc!=0 {}".format(len(s), len(s) - len(bad), bad))
out["suites"] = {"total": len(s), "rc0": len(s) - len(bad), "failed": bad,
                 "ratios": {x["suite"]: x["ratios"] for x in s}}
bp_path = LOGS / "phase6a_m2_rerun" / "phase3a_regression_batch.json"
if bp_path.is_file():
    bp = json.loads(bp_path.read_text(encoding="utf-8"))
    ne = [x["name"] for x in bp if not x["as_expected"]]
    print("[batch] {} 项 | 符合预期 {} | 非预期 {}".format(
        len(bp), sum(1 for x in bp if x["as_expected"]), ne))
    out["batch"] = {"total": len(bp), "as_expected": sum(1 for x in bp if x["as_expected"]),
                    "not_as_expected": ne}
else:
    out["batch"] = {"error": "缺少 phase3a_regression_batch.json"}

# ---- 5) 代码指纹（M2 版 vs M1 版）----
subprocess.run([PY, "docs/regression_2x/phase5m_code_fingerprint.py", "m2"], cwd=str(ROOT),
               capture_output=True, text=True, encoding="utf-8", errors="replace")
m1 = json.loads((LOGS / "phase5m_code_fingerprint_now.json").read_text(encoding="utf-8"))
m2 = json.loads((LOGS / "phase5m_code_fingerprint_m2.json").read_text(encoding="utf-8"))
changed = sorted(k for k in m1["files"] if k in m2["files"] and m1["files"][k] != m2["files"][k])
added = sorted(k for k in m2["files"] if k not in m1["files"])
removed = sorted(k for k in m1["files"] if k not in m2["files"])
print("[fingerprint] M1 {} 文件 {} -> M2 {} 文件 {}".format(
    m1["count"], m1["aggregate_sha256"][:16], m2["count"], m2["aggregate_sha256"][:16]))
print("[fingerprint] 变化 {} 新增 {} 删除 {}".format(len(changed), len(added), len(removed)))
out["fingerprint"] = {"m1": {"count": m1["count"], "aggregate_sha256": m1["aggregate_sha256"]},
                      "m2": {"count": m2["count"], "aggregate_sha256": m2["aggregate_sha256"]},
                      "changed": changed, "added": added, "removed": removed}

# ---- 6) 历史母版未被改写 ----
v9 = {"path": str(V9_FILM.relative_to(ROOT)), "exists": V9_FILM.is_file()}
if V9_FILM.is_file():
    v9.update({"sha256": sha(V9_FILM), "bytes": V9_FILM.stat().st_size,
               "unchanged_vs_m1_record": (sha(V9_FILM) == V9_SHA
                                          and V9_FILM.stat().st_size == V9_BYTES)})
print("[master] v9 成片未被改写:", v9.get("unchanged_vs_m1_record"))
out["historical_masters"] = {"v9_film": v9}

# ---- 7) 本轮授权变更清单（源码侧；docs 侧脚本/报告另列）----
MODIFIED = ["src/video_studio/core/integrity.py",
            "src/video_studio/agents/editing/agent.py",
            "tests/narration_contract_test.py",
            "tests/bgm_ducking_test.py",
            "tests/pipeline_mock.py",
            "docs/regression_2x/run_ingest_test.py",
            "docs/regression_2x/run_all_tests.py",
            "docs/regression_2x/phase4f_evidence.py"]
ADDED = ["tests/integrity_gates_test.py",
         "docs/regression_2x/PHASE6A_M2_REPORT.md",
         "docs/regression_2x/phase6a_m2_battery.py",
         "docs/regression_2x/phase6a_m2_guard_check.py",
         "docs/regression_2x/phase6a_m2_agent_diff.py",
         "docs/regression_2x/phase6a_m2_final_check.py",
         "docs/regression_2x/phase6a_m2_v9_gate.py",
         "docs/regression_2x/phase6a_m2_legacy_probe.py",
         "docs/regression_2x/phase6a_m2_shortfilm_probe.py",
         "docs/regression_2x/phase6a_m2_interim_blocks.py",
         "docs/regression_2x/phase6a_m2_precheck.py",
         "docs/regression_2x/phase6a_m2_preserve_and_restore.py"]
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

(LOGS / "phase6a_m2_final_check.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                                  encoding="utf-8")
print("json ->", LOGS / "phase6a_m2_final_check.json")
