# -*- coding: utf-8 -*-
"""6-E 收尾核对（只读汇总）：基线完整性、守卫状态、套件、电池/批次、第二轮登记证据、
代码指纹，并证明 **本阶段未执行、未修改任何既有产物**。

用法: python docs/regression_2x/phase6e_final_check.py
产出: logs/phase6e_final_check.json
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
M6C = LOGS / "phase6c_batch.json"


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


out = {"stage": "6-E"}

# ---- 1) 基线 ----
baselines, zips = {}, sorted(p.name for p in BASE.glob("*.zip"))
for tag in TAGS:
    z = BASE / "{}.zip".format(tag)
    if not z.is_file():
        continue
    m = BASE / "baseline_manifest_{}.json".format(tag)
    rec = {"zip_sha256": sha(z), "zip_bytes": z.stat().st_size}
    if m.is_file():
        man = json.loads(m.read_text(encoding="utf-8"))
        rec["zip_matches_manifest"] = man["zip_sha256"] == rec["zip_sha256"]
        rec["manifest_file_count"] = man["file_count"]
    baselines[tag] = rec
    print("[baseline] {:44s} zip==manifest:{} files:{}".format(
        tag, rec.get("zip_matches_manifest"), rec.get("manifest_file_count")))
out["baselines"] = baselines
out["baseline_zips"] = zips
out["baseline_zip_count"] = len(zips)
out["no_new_baseline_or_tag"] = len(zips) == 4

# ---- 2) 守卫 ----
g = json.loads((LOGS / "phase6e_guard_check.json").read_text(encoding="utf-8"))
print("[guard] drifted:", g["guards_drifted"], "| 未授权:", g["unexpected_guard_drift"])
print("[guard] 工作树相对 r3 漂移:", g["tree_drift_vs_r3"], "| 缺失:", g["tree_missing_vs_r3"])
out["guard"] = {k: g[k] for k in ("guards_checked", "guards_drifted",
                                  "m2_authorized_guard_change", "unexpected_guard_drift",
                                  "tree_drift_vs_r3", "tree_missing_vs_r3",
                                  "r3_zip_unchanged_vs_manifest", "final_zip_unchanged")}

# ---- 3) 电池 ----
b = json.loads((LOGS / "phase6e_regression_summary.json").read_text(encoding="utf-8"))
print("[battery] steps {} | rc!=0 {} | rc_pending {} | 外部 {} | 日志恢复 {} | 秒数和 {}s".format(
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
_ext = LOGS / "phase6e_external_steps.json"
out["external_steps"] = (json.loads(_ext.read_text(encoding="utf-8")) if _ext.is_file()
                         else {"error": "缺少外部步骤记录"})

# ---- 4) 套件 + 批次 ----
s = json.loads((LOGS / "phase6e_rerun" / "suites_summary.json").read_text(encoding="utf-8"))
bad = [x["suite"] for x in s if x["rc"] != 0]
print("[suites] {} 个 | rc=0 {} | rc!=0 {}".format(len(s), len(s) - len(bad), bad))
out["suites"] = {"total": len(s), "rc0": len(s) - len(bad), "failed": bad,
                 "new_suites": [x["suite"] for x in s if x["suite"] == "directorial_round2_test"]}
bp_path = LOGS / "phase6e_batch_items.json"
if bp_path.is_file():
    bp = json.loads(bp_path.read_text(encoding="utf-8"))
    print("[batch] {} 项 | 符合预期 {} | 非预期 {}".format(
        bp["total"], bp["as_expected_count"], bp.get("unexpected") or []))
    out["batch"] = {"total": bp["total"], "as_expected": bp["as_expected_count"],
                    "not_as_expected": bp.get("unexpected") or [],
                    "step_rc_equivalent": bp.get("step_rc_equivalent"),
                    "source": bp.get("source_of_items")}
else:
    out["batch"] = {"error": "缺少 phase6e_batch_items.json"}

# ---- 5) 第二轮登记证据 ----
r2 = json.loads((LOGS / "phase6e_round2.json").read_text(encoding="utf-8"))
tf = json.loads((LOGS / "phase6e_truth_freeze.json").read_text(encoding="utf-8"))
out["round2"] = {"human_review": [(x["seq"], x["decision"], x["kind"], x["scene_id"])
                                  for x in r2["human_review_round2"]],
                 "review_chain": r2["review_chain"],
                 "proposals": [{"label": p["label"], "proposal_id": p["proposal_id"],
                                "action": p["action"],
                                "scenes": p["affected_scope"]["scenes"],
                                "window": p["affected_scope"]["window"],
                                "share_of_film": p["affected_scope"]["share_of_film"],
                                "needs_new_material": p["material_requirement"]["needs_new_material"],
                                "needs_new_content_self_created":
                                    p["material_requirement"]["needs_new_content_self_created"],
                                "asset_id": p["material_requirement"]["asset_id"],
                                "forbidden_material": p["material_requirement"]["forbidden_material"]}
                               for p in r2["proposals"]],
                 "register_chain": r2["register_chain"],
                 "retention_records": r2["retention_records"],
                 "conflict_pairs_internal": r2["conflict_matrix_6e"]["conflict_pair_count"],
                 "cross_batch_overlaps": r2["cross_batch_overlaps"],
                 "locality": r2["locality"],
                 "integrity": r2["integrity"],
                 "truth_canonical_sha256": tf["truth_canonical_sha256"]}
print("[6e] 审片 {} 条 | 提案 {} 条 | 内部冲突 {} | 跨批次重叠 {}".format(
    len(r2["human_review_round2"]), r2["proposal_count"],
    r2["conflict_matrix_6e"]["conflict_pair_count"], len(r2["cross_batch_overlaps"])))
print("[6e] 保留记录 {} | 未执行 {} | ffmpeg 调用 {} | C1–C4 未变 {}".format(
    [(x["kind"], x["scene_id"]) for x in r2["retention_records"]],
    r2["integrity"]["executed_anything"], r2["integrity"]["ffmpeg_invocations"],
    r2["integrity"]["c1_c4_sha_unchanged"]))
print("[truth] canonical sha256:", tf["truth_canonical_sha256"][:16])

# ---- 6) 代码指纹 ----
subprocess.run([PY, "docs/regression_2x/phase5m_code_fingerprint.py", "6e"], cwd=str(ROOT),
               capture_output=True, text=True, encoding="utf-8", errors="replace")
_LABELS = [("m1", "now"), ("m2", "m2"), ("m3", "m3"), ("6bm1", "6bm1"), ("6bm2", "6bm2"),
           ("6bm3", "6bm3"), ("6bm4", "6bm4"), ("6bm5", "6bm5"), ("6c", "6c"), ("6e", "6e")]
fps = {k: json.loads((LOGS / "phase5m_code_fingerprint_{}.json".format(lbl))
                     .read_text(encoding="utf-8")) for k, lbl in _LABELS}


def _delta(a, b):
    return (sorted(k for k in a["files"] if k in b["files"] and a["files"][k] != b["files"][k]),
            sorted(k for k in b["files"] if k not in a["files"]),
            sorted(k for k in a["files"] if k not in b["files"]))


changed, added, removed = _delta(fps["6c"], fps["6e"])
print("[fingerprint] 6-C {} 文件 {} -> 6-E {} 文件 {}".format(
    fps["6c"]["count"], fps["6c"]["aggregate_sha256"][:16],
    fps["6e"]["count"], fps["6e"]["aggregate_sha256"][:16]))
print("[fingerprint] 6-E 增量: 变化 {} 新增 {} 删除 {} | {} {}".format(
    len(changed), len(added), len(removed), changed, added))
out["fingerprint"] = {k: {"count": v["count"], "aggregate_sha256": v["aggregate_sha256"]}
                      for k, v in fps.items()}
out["fingerprint"]["6c_to_6e"] = {"changed": changed, "added": added, "removed": removed}

# ---- 7) 母版 + 候选完整性（本轮**未**修改）----
v = {"path": str(V9_FILM.relative_to(ROOT)), "exists": V9_FILM.is_file()}
if V9_FILM.is_file():
    v.update({"sha256": sha(V9_FILM), "bytes": V9_FILM.stat().st_size,
              "unchanged_vs_m1_record": (sha(V9_FILM) == V9_SHA
                                         and V9_FILM.stat().st_size == V9_BYTES)})
print("[master] v9 成片未被改写:", v.get("unchanged_vs_m1_record"))
m6c = json.loads(M6C.read_text(encoding="utf-8"))
cands = []
for c in m6c["candidates"]:
    p = ROOT / c["film"]
    cur = sha(p) if p.is_file() else None
    cands.append({"index": c["index"], "proposal_label": c["proposal_label"], "path": c["film"],
                  "exists": p.is_file(), "sha256_now": cur,
                  "sha256_recorded": c["film_sha256"], "unchanged": cur == c["film_sha256"]})
out["historical_masters"] = {"v9_film": v}
out["candidates_unchanged"] = cands
out["all_candidates_unchanged"] = all(c["unchanged"] for c in cands)
print("[candidates] 4 部候选均未被本轮修改:", out["all_candidates_unchanged"])
out["sandbox"] = {"root": "output/phase6b_m4_sandbox",
                  "output_dir_files": sorted(p.name for p in
                                             (ROOT / "output" / "phase6b_m4_sandbox" /
                                              "p_96efdc03e1aa_6c" / "output").rglob("*")
                                             if p.is_file())}

# ---- 8) 本轮变更清单（仅证据/测试脚本；**无成片**）----
MODIFIED = []
ADDED = ["tests/fixtures/directorial_round2_truth_v1.json",
         "tests/directorial_round2_test.py",
         "docs/regression_2x/PHASE6E_REPORT.md",
         "docs/regression_2x/phase6e_round2_proposals.py",
         "docs/regression_2x/phase6e_build_truth.py",
         "docs/regression_2x/phase6e_batch_items.py",
         "docs/regression_2x/phase6e_battery.py",
         "docs/regression_2x/phase6e_guard_check.py",
         "docs/regression_2x/phase6e_final_check.py"]
stats = {}
for rel in MODIFIED + ADDED:
    p = ROOT / rel
    stats[rel] = ({"bytes": p.stat().st_size, "sha256": sha(p),
                   "lines": len(p.read_text(encoding="utf-8").splitlines())}
                  if p.is_file() else {"missing": True})
out["file_stats"] = stats
out["file_changes"] = {"modified": MODIFIED, "added": ADDED}
out["no_source_change_this_stage"] = (changed == [] and removed == []
                                     and all(a.startswith("tests/") or a.startswith("docs/")
                                             for a in added))
for rel in MODIFIED + ADDED:
    s = stats[rel]
    print("[file] {:58s} {} lines {} bytes {}".format(
        rel, s.get("lines"), s.get("bytes"), str(s.get("sha256"))[:16]))

(LOGS / "phase6e_final_check.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                               encoding="utf-8")
print("json ->", LOGS / "phase6e_final_check.json")
