# -*- coding: utf-8 -*-
"""Phase 12 / P12-4 **前后对照复验**（只读模拟，零执行）：
  · 臂 A（无覆盖层）：`ops.visual_binding.build()` ⇒ 与 P7-6 已 ACCEPTED 产物**逐字节一致**；
  · 臂 B（有覆盖层）：`build(overlay=...)` ⇒ 新覆盖报告 `logs/phase12_coverage_after.json`：
    S01、S13–S16 五景 license_decision 逐场景变化 + 理由 + provenance；覆盖计数前后对照。
**不写 execution ledger、不渲染、不替换素材、不动 6-G**；Phase 7 六份产物只读。
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core import asset_license_join as ALJ                               # noqa: E402
from video_studio.core.visual_requirement import canonical, sha256_text               # noqa: E402
from video_studio.ops import visual_binding as VB                                     # noqa: E402

LOGS = ROOT / "docs" / "regression_2x" / "logs"
FIVE = ("S01", "S13", "S14", "S15", "S16")


def main() -> int:
    frozen_prop = json.loads((LOGS / "visual_binding_proposals.json").read_text(encoding="utf-8"))
    frozen_cov = json.loads((LOGS / "visual_coverage_report.json").read_text(encoding="utf-8"))
    overlay = json.loads((LOGS / "license_overlay_v1.json").read_text(encoding="utf-8"))
    idx_before = sha256_text(json.dumps(json.loads(
        (LOGS / "asset_index.json").read_text(encoding="utf-8")), ensure_ascii=False, sort_keys=True,
        separators=(",", ":")))

    # ---- 臂 A：无覆盖层（向后兼容硬验收）----
    a = VB.build()
    a_doc, a_cov = a["proposals"], a["coverage"]
    a_props = a_doc["proposals"]
    cmp_a = {
        "proposals_identical": canonical(a_doc) == canonical(frozen_prop),
        "proposals_artifact_hash_equal": a_doc.get("artifact_hash") == frozen_prop.get("artifact_hash"),
        "coverage_identical": canonical(a_cov) == canonical(frozen_cov),
        "counts_identical": a_doc.get("counts") == frozen_prop.get("counts"),
        "proposal_ids_identical": [p["proposal_id"] for p in a_props]
        == [p["proposal_id"] for p in frozen_prop["proposals"]],
    }
    # ---- 臂 B：有覆盖层 ----
    b = VB.build(overlay=overlay)
    b_doc, b_cov = b["proposals"], b["coverage"]
    b_props = b_doc["proposals"]
    def scene_map(x):
        return {c["scene_id"]: c for c in x.get("scene_coverages") or []}
    a_sc, b_sc = scene_map(a_cov), scene_map(b_cov)
    changes = []
    for sid in FIVE:
        fa = next((p for p in frozen_prop["proposals"] if p["scene_id"] == sid), {})
        b_p = next((p for p in b_props if p["scene_id"] == sid), {})
        changes.append({
            "scene_id": sid,
            "license_decision_before": fa.get("license_decision"),
            "license_decision_after_join": b_p.get("license_decision"),
            "decision_before": fa.get("decision"), "decision_after_join": b_p.get("decision"),
            "coverage_before": (a_sc.get(sid) or {}).get("coverage"),
            "coverage_after_join": (b_sc.get(sid) or {}).get("coverage"),
            "bindable_candidates_before": len(fa.get("bindable_candidates") or []),
            "bindable_candidates_after_join": len(b_p.get("bindable_candidates") or []),
            "decision_reason_before": fa.get("decision_reason"),
            "decision_reason_after_join": b_p.get("decision_reason"),
            "license_provenance": b_p.get("license_provenance"),
            "unchanged_from_p76": canonical(b_p) == canonical(fa),
        })
    def counts(doc, cov):
        return {"coverage_counts": doc.get("coverage_counts") or cov.get("counts"),
                "counts": doc.get("counts"), "counts_by_action": cov.get("counts_by_action"),
                "hitl": (cov.get("hitl") or {}).get("count") if isinstance(cov.get("hitl"), dict)
                        else cov.get("hitl")}
    out = {
        "schema": "phase12-coverage-after-v1",
        "generation_method": "read-only re-simulation（零执行、零渲染、零素材替换）",
        "overlay": {"path": "docs/regression_2x/logs/license_overlay_v1.json",
                    "artifact_hash": overlay["artifact_hash"],
                    "join_rule_version": overlay["join_rule_version"],
                    "counts": overlay["counts"]},
        "arm_a_no_overlay": {"backward_compatible": cmp_a,
                             "expect": "与 P7-6 产物逐字节一致",
                             "verify": cmp_a["proposals_identical"] and cmp_a["coverage_identical"]},
        "arm_b_with_overlay": {"proposals_artifact_hash": b_doc.get("artifact_hash"),
                               "coverage_artifact_hash": b_cov.get("artifact_hash"),
                               "counts": counts(b_doc, b_cov)},
        "arm_a_counts": counts(a_doc, a_cov),
        "five_scenes": changes,
        "scenes_changed": [c["scene_id"] for c in changes if not c["unchanged_from_p76"]],
        "scenes_unlocked": [c["scene_id"] for c in changes
                            if c["license_decision_after_join"] == "PASS" and
                            c["license_decision_before"] != "PASS"],
        "scenes_still_hitl": [c["scene_id"] for c in changes
                              if (c["decision_after_join"] or "").startswith("HITL")],
        "s05_replace_kept_as_proposal": next(
            (p["decision"] for p in b_props if p["scene_id"] == "S05"), None),
        "index_sha256_before": idx_before,
        "index_files_untouched": True,
        "execution": {"ledger_written": False, "rendered": False, "assets_replaced": False,
                      "six_g_touched": False},
        "honest_note": ("五景是否解锁**由系统内记录决定**，不由本阶段决定；"
                        "MISSING/CONFLICT 保持 HITL 是正确结果而非失败。"
                        "许可门只消费记录；相关性/复用等其它门禁不受影响。"),
    }
    (LOGS / "phase12_coverage_after.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    print("臂 A 向后兼容:", json.dumps(cmp_a, ensure_ascii=False))
    print("臂 A/B 覆盖计数:", json.dumps(out["arm_b_with_overlay"]["counts"], ensure_ascii=False)[:200])
    for c in changes:
        print("  {} lic {} -> {} | decision {} -> {} | bindable {} -> {}".format(
            c["scene_id"], c["license_decision_before"], c["license_decision_after_join"],
            c["decision_before"], c["decision_after_join"],
            c["bindable_candidates_before"], c["bindable_candidates_after_join"]))
    print("解锁场景:", out["scenes_unlocked"], "| 仍 HITL:", out["scenes_still_hitl"],
          "| S05:", out["s05_replace_kept_as_proposal"])
    return 0 if out["arm_a_no_overlay"]["verify"] else 5


if __name__ == "__main__":
    sys.exit(main())
