# -*- coding: utf-8 -*-
"""P7-6：绑定提案 + 覆盖闭环 **ops 入口**（**严格只读**：不写文件、零网络、零执行、无 DB 写入）。

用法：
  python -m video_studio.ops.visual_binding build [--json]
  python -m video_studio.ops.visual_binding verify PATH

只读消费 P7-1…P7-5 产物 + 生产 `render_output`（21 场景 + 人工选材理由）。
**不执行**：不修改 material timeline、不替换素材、不 rebuild/render、不写 ledger/register、
不改动 6-G。artifact 落盘 = `docs/regression_2x/phase7_p7_6_build.py`。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

from ..core import visual_acquisition as VA
from ..core import visual_binding as VB
from ..core.asset_candidate import UNKNOWN
from ..core.materials import license_block_reason, license_gate_applies
from ..core import asset_license_join as ALJ

DEFAULT_DB = r"C:\mp4agent\video-studio\projects\video_studio.db"
DEFAULT_TASK = "t_d0a54bdf1810"
DEFAULT_LOGS = r"C:\mp4agent\video-studio\docs\regression_2x\logs"
DEFAULT_OUT = r"C:\mp4agent\video-studio\docs\regression_2x\logs\visual_binding_proposals.json"
DEFAULT_COVERAGE_OUT = r"C:\mp4agent\video-studio\docs\regression_2x\logs\visual_coverage_report.json"
H5_REPORT = "phase6g_exec_h5.json"
DQ_RECOMPUTE = "phase6g_h5_dq_recompute.json"


class SourceMissing(RuntimeError):
    """必需输入缺失 ⇒ fail-closed。"""


def sha256_file(p) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def _json(p) -> dict:
    return json.loads(Path(p).read_text(encoding="utf-8"))


def _db_ro(db: str) -> sqlite3.Connection:
    con = sqlite3.connect("file:{}?mode=ro".format(Path(db).as_posix()), uri=True)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only=ON")
    return con


def _require(p: Path, what: str) -> Path:
    if not p.is_file():
        raise SourceMissing("{} 缺失：{}".format(what, p))
    return p


def load_sources(db: str = DEFAULT_DB, task_id: str = DEFAULT_TASK, logs: str = DEFAULT_LOGS):
    L = Path(logs)
    need = {"requirements": "visual_requirements.json", "index": "asset_index.json",
            "diversity": "asset_diversity.json", "relevance": "visual_relevance.json",
            "acquisition": "visual_acquisition.json", "h5": H5_REPORT, "dqd": DQ_RECOMPUTE}
    got = {k: _json(_require(L / v, k)) for k, v in need.items()}
    con = _db_ro(db)
    try:
        row = con.execute("select artifact_id,path from artifacts where type='render_output' "
                          "and task_id=? order by created_at desc limit 1", (task_id,)).fetchone()
        if not row:
            raise SourceMissing("render_output(task={}) 缺失".format(task_id))
        ro = dict(row)
    finally:
        con.close()
    ro_p = _require(Path(ro["path"]), "render_output")
    got["render"] = _json(ro_p)
    got["sources"] = [{"role": r, "path": str(p), "sha256": sha256_file(p)}
                      for r, p in [("p7_1_visual_requirements", L / need["requirements"]),
                                   ("p7_2_asset_index", L / need["index"]),
                                   ("p7_3_asset_diversity", L / need["diversity"]),
                                   ("p7_4_visual_relevance", L / need["relevance"]),
                                   ("p7_5_visual_acquisition", L / need["acquisition"]),
                                   ("h5_report", L / need["h5"]),
                                   ("existing_dq2_threshold_source", L / need["dqd"]),
                                   ("render_output", ro_p)]]
    return got


def _thresholds(dqd: dict) -> dict:
    th = (((dqd.get("DQ") or {}).get("after_H5") or {}).get("DQ-2") or {}).get("threshold") or {}
    v = th.get("min_unique_assets")
    return {"min_unique_assets": v if isinstance(v, int) else UNKNOWN,
            "status": "OK" if isinstance(v, int) else VB.NOT_ASSESSABLE,
            "source": "phase6g_h5_dq_recompute.json#DQ.after_H5.DQ-2.threshold（数据来源，未新造）"}


def build(db: str = DEFAULT_DB, task_id: str = DEFAULT_TASK, logs: str = DEFAULT_LOGS,
          overlay: dict | None = None) -> dict:
    """构建绑定提案。

    **Phase 12（P12-3）加法**：`overlay`（许可数据 join 增强覆盖层，默认 `None`）非空时，
    license 门禁消费 join 后的 `license`/`license_class`，并在候选与提案上留 `license_provenance`
    （记录 `source_of_record`）；`overlay=None` ⇒ **行为与 P7-6 逐字节一致**（向后兼容硬验收）。
    `core/materials.py` 语义与任何门禁阈值**均未改动**。
    """
    src = load_sources(db, task_id, logs)
    idx = {c["asset_id"]: c for c in (src["index"].get("candidates") or [])}
    legacy = {lid: c["asset_id"] for c in idx.values() for lid in (c.get("legacy_asset_ids") or [])}
    rel_scenes = {s["scene_id"]: s for s in src["relevance"].get("scene_results") or []}
    rel_by_asset = {s["scene_id"]: {c["asset_id"]: c for c in s["candidate_results"]}
                    for s in (src["relevance"].get("scene_results") or [])}
    acq = {d["scene_id"]: d for d in src["acquisition"].get("decisions") or []}
    thr = _thresholds(src["dqd"])
    primary = next((s for s in src["diversity"]["scopes"]
                    if s["scope"] == src["diversity"]["primary_scope"]),
                   src["diversity"]["scopes"][0])
    below = bool(isinstance(thr["min_unique_assets"], int)
                 and primary["A_asset_level"]["unique_perceptual_families"]
                 < thr["min_unique_assets"])
    # 复用统计（来自 P7-3 度量 + 生产 timeline；不重算 DQ）
    reuse = {}
    for seg in src["render"].get("material_timeline") or []:
        sa = seg.get("selected_asset") or {}
        aid = legacy.get(sa.get("asset_id"), sa.get("asset_id"))
        if aid:
            reuse[aid] = reuse.get(aid, 0) + 1
    sfam = {}
    for aid, c in idx.items():
        sf = VA.source_family_of(c) if hasattr(VA, "source_family_of") else None
        if sf is None:
            from ..core.asset_diversity import source_family_of as _sf
            sf = _sf(c)
        n = sum(1 for seg in (src["render"].get("material_timeline") or [])
                if legacy.get((seg.get("selected_asset") or {}).get("asset_id"),
                              (seg.get("selected_asset") or {}).get("asset_id")) in
                [a for a, cc in idx.items() if (_sf(cc) if False else True) and a == aid])
        sfam[aid] = {"family": sf, "count": reuse.get(aid, 0)}
    # 候选（注入 P7-5 风格许可判定，供门禁使用；不改 P7-2 数据）
    cands = []
    for aid, c in sorted(idx.items()):
        # Phase 12（P12-3，加法、默认关闭）：覆盖层仅替换 HAS_RECORD 资产的许可声明
        c_eff, prov = ALJ.apply_to_candidate(c, overlay) if overlay else (c, None)
        gate = license_gate_applies(c_eff, require_license=True)
        dec = VA.license_decision(c_eff.get("license"), c_eff.get("license_class"))["decision"]
        cc = dict(c_eff, license_gate_applies=gate, _license_decision=dec,
                  license_block_reason=(license_block_reason(c_eff, require_license=True)
                                        if gate else None))
        if prov is not None:
            cc["license_provenance"] = prov
            cc["index_license_class_before_join"] = c.get("license_class")
        cands.append(cc)
    policy = dict(VB.BINDING_POLICY)
    policy["source_snapshot"] = {s["role"]: s["sha256"] for s in src["sources"]}
    policy["existing_thresholds"] = thr
    policy["project_below_existing_threshold"] = below
    policy["h5_provenance"] = {
        "S05": {"replacement_asset_id": next(
            (aid for aid, c in idx.items()
             if "Russell_PM" in str(c.get("path"))), UNKNOWN),
            "evidence": "phase6g_exec_h5.json（人工已接受）+ M2 台账 REJECT（原素材）",
            "note": "P7-6 只据此生成提案；**不重新执行 H5**"},
        "S11": {"replacement_asset_id": next(
            (aid for aid, c in idx.items()
             if "LIPIcs" in str(c.get("path"))), UNKNOWN),
            "evidence": "phase6g_exec_h5.json（人工已接受）",
            "note": "P7-6 只据此生成提案；**不重新执行 H5**"}}
    proposals, coverages = [], []
    for seg in src["render"].get("material_timeline") or []:
        sid = str(seg.get("scene_id"))
        sa = seg.get("selected_asset") or {}
        prev = legacy.get(sa.get("asset_id"), sa.get("asset_id"))
        hs = seg.get("human_selection") or {}
        prev_ev = {"source": "render_output.material_timeline.human_selection",
                   "decision_id": hs.get("decision_id"), "decided_by": hs.get("decided_by"),
                   "reason": hs.get("reason"),
                   "evidence_refs": [x for x in (hs.get("decision_id"),) if x]}
        p = VB.propose(scene_id=sid,
                       requirement_id=(rel_scenes.get(sid) or {}).get("requirement_id"),
                       previous_asset_id=prev, previous_evidence=prev_ev, candidates=cands,
                       relevance_by_asset=rel_by_asset.get(sid, {}), reuse_stats=reuse,
                       source_family_reuse=sfam, project_below_existing_threshold=below,
                       acquisition=acq.get(sid, {}), policy=policy)
        cov = VB.coverage_of(p)
        p["coverage"] = cov["coverage"]
        if overlay:
            # Phase 12（P12-3，加法）：提案级 license_provenance（仅记录**已 join 到记录**的候选）
            prov_map = {c["asset_id"]: c["license_provenance"] for c in cands
                        if c.get("license_provenance")}
            if prov_map:
                p["license_provenance"] = {
                    "join_rule_version": overlay.get("join_rule_version"),
                    "overlay_artifact_hash": overlay.get("artifact_hash"),
                    "candidates": prov_map,
                    "note": "依据**系统内已记录的许可声明**（source_of_record 可回溯）；未记录者保持 UNKNOWN 走 HITL"}
        p["deterministic_hash"] = VB.proposal_identity(p)
        p["proposal_id"] = "bp-" + p["deterministic_hash"][:16]
        proposals.append(p)
        coverages.append({"scene_id": sid, "requirement_id": p["requirement_id"],
                          "previous_asset_id": prev, "proposed_action": p["decision"],
                          "candidate_id": p["candidate_id"], **cov})
    counts_action = {a: sum(1 for p in proposals if p["decision"] == a) for a in VB.ACTIONS}
    counts_cov = {c: sum(1 for x in coverages if x["coverage"] == c) for c in VB.COVERAGE_STATES}
    working = _working_timeline(src, proposals, legacy)
    coverage_report = {
        "schema": VB.COVERAGE_SCHEMA, "version": VB.VERSION,
        "generation_method": "deterministic-offline（只读消费 P7-1…P7-5；零执行）",
        "policy": policy, "sources": src["sources"],
        "scene_coverages": coverages, "counts": counts_cov,
        "counts_by_action": counts_action,
        "coverage_rules": {"COVERED": "存在 BINDABLE candidate",
                           "HITL_REQUIRED": "有候选但需人工确认（未被证明不适合）",
                           "UNSUPPORTED": "全部候选被可靠证明不适合",
                           "NOT_ASSESSABLE": "没有候选或需求缺必要证据通道",
                           "invariant": "**禁止**把 NOT_ASSESSABLE 归为 UNSUPPORTED"},
        "acquisition_integration": {
            "acquisition_needed_scenes": [d["scene_id"] for d in (src["acquisition"].get(
                "decisions") or []) if d.get("acquisition_needed")],
            "auto_live_fetch": False,
            "note": "P7-6 **不**触发任何 fetch；无候选场景记 ACQUISITION_REQUIRED",
            "p7_5_mode": src["acquisition"].get("mode")},
        "answers": _answers(proposals, coverages, counts_action, counts_cov, src),
        "execution": {"executed": False, "auto_executed": False,
                      "note": "proposal ≠ execution：未修改 timeline/素材/6-G，未 rebuild/render"},
        "working_timeline": working,
        "hitl": {"入口": "core.visual_binding.apply_hitl_decision（actor/decision/reason/timestamp/"
                         "evidence_refs）", "timestamp_in_identity": False,
                 "supported_actions": list(VB.HITL_ACTIONS), "applied": []},
        "artifact_hash": "",
    }
    coverage_report["artifact_hash"] = sha256_text_canonical(coverage_report)
    proposals_doc = {
        "schema": VB.SCHEMA, "version": VB.VERSION,
        "generation_method": "deterministic-offline（门禁 + 固定 policy；无评分排序）",
        "policy": policy, "sources": src["sources"], "proposals": proposals,
        "counts": counts_action, "coverage_counts": counts_cov,
        "gate_spec": VB.GATE_SPEC,
        "candidate_states": list(VB.CANDIDATE_STATES),
        "invariants": {"RELEVANT_neq_BINDABLE": True, "no_score_ranking": True,
                       "partial_never_promoted": True, "not_assessable_never_promoted": True,
                       "add_structurally_unavailable": not VB.BINDING_POLICY["add_slot"]["allowed"],
                       "no_auto_execution": True, "bound_not_reachable":
                           "BOUND 只能由未来执行阶段产生；P7-6 无该状态转移"},
        "execution": {"executed": False},
        "artifact_hash": "",
    }
    proposals_doc["artifact_hash"] = sha256_text_canonical(proposals_doc)
    return {"proposals": proposals_doc, "coverage": coverage_report}


def sha256_text_canonical(obj: dict) -> str:
    body = {k: v for k, v in obj.items() if k != "artifact_hash"}
    from ..core.visual_requirement import canonical as _c, sha256_text as _s
    return _s(_c(body))


def _working_timeline(src: dict, proposals: list, legacy: dict) -> dict:
    """P7_WORKING_TIMELINE：**隔离**的假设时间轴（不覆盖、不渲染、不进入 6-G）。"""
    by_scene = {p["scene_id"]: p for p in proposals}
    rows = []
    for seg in src["render"].get("material_timeline") or []:
        sid = str(seg.get("scene_id"))
        sa = seg.get("selected_asset") or {}
        prev = legacy.get(sa.get("asset_id"), sa.get("asset_id"))
        p = by_scene.get(sid) or {}
        applied = p.get("candidate_id") if p.get("decision") == VB.REPLACE else prev
        rows.append({"scene_id": sid, "start_s": seg.get("start_s"), "end_s": seg.get("end_s"),
                     "current_asset_id": prev, "proposed_action": p.get("decision"),
                     "proposed_asset_id": p.get("candidate_id"),
                     "working_asset_id": applied,
                     "changed": bool(applied != prev)})
    body = {"schema": VB.WORKING_TIMELINE_SCHEMA, "hypothetical": True, "authoritative": False,
            "isolation": {"base": "render_output.material_timeline（生产，read-only）",
                          "not_6g_frozen_timeline": True, "not_rendered": True,
                          "does_not_override": True, "scene_count_unchanged": True,
                          "scene_count": len(rows)},
            "applied_replacements": [{"scene_id": r["scene_id"], "from": r["current_asset_id"],
                                      "to": r["working_asset_id"]}
                                     for r in rows if r["changed"]],
            "rows": rows}
    from ..core.visual_requirement import canonical as _c, sha256_text as _s
    body["artifact_hash"] = _s(_c(body))
    return body


def _answers(proposals, coverages, ca, cc, src) -> dict:
    def q(k, v):
        return {k: v}
    asks = {}
    asks.update(q("1_scene_needs_visual_content", {
        "source": "P7-1 visual_requirements（visual_goal/expected_kind 可证明）",
        "per_scene_example": {"scene_id": proposals[0]["scene_id"],
                              "requirement_id": proposals[0]["requirement_id"]}}))
    asks.update(q("2_available_candidates", {"candidate_pool": len(
        (src["index"].get("candidates") or [])), "per_scene_pool": "同一 AssetIndex（8 候选）"}))
    asks.update(q("3_reliable_relevance_evidence", {"counts": src["relevance"]["aggregate"][
        "decision_counts"], "by_evidence_kind": src["relevance"]["aggregate"][
            "relevant_by_evidence_kind"]}))
    asks.update(q("4_partial_only", {"count": src["relevance"]["aggregate"]["decision_counts"][
        "PARTIAL"], "policy": "PARTIAL 不得自动绑定 ⇒ HITL"}))
    asks.update(q("5_irrelevant", {"count": src["relevance"]["aggregate"]["decision_counts"][
        "IRRELEVANT"], "policy": "IRRELEVANT ⇒ DENY（NOT_BINDABLE）"}))
    asks.update(q("6_not_assessable", {"count": src["relevance"]["aggregate"]["decision_counts"][
        VB.NOT_ASSESSABLE], "policy": "NOT_ASSESSABLE 不得自动绑定 ⇒ HITL；**不得**升级为 RELEVANT"}))
    asks.update(q("7_license_integrity_provenance", {
        "license_denied_gate": sum(1 for p in proposals for e in p["candidate_evaluations"]
                                   if e["blocking_code"] == "LICENSE_DENIED"),
        "license_hitl_gate": sum(1 for p in proposals for e in p["candidate_evaluations"]
                                 if e["blocking_code"] == "LICENSE_UNKNOWN_HITL"),
        "integrity_failures": sum(1 for p in proposals for e in p["candidate_evaluations"]
                                  if e["blocking_code"] == "INTEGRITY_FAILED"),
        "provenance_gaps": src["acquisition"]["project_signals"]["project_provenance_gaps"],
        "note": "P7-2 索引中外部资产的 license 记为 UNKNOWN（未 join attribution）⇒ 这些候选走 "
                "HITL，不得自动绑定"}))
    asks.update(q("8_reuse_diversity_policy", {
        "policy": VB.BINDING_POLICY["reuse_preferences"],
        "max_reuse_threshold": UNKNOWN, "threshold_status": VB.NOT_ASSESSABLE,
        "existing_dq2_threshold": src["acquisition"]["project_signals"]["diversity"],
        "project_below_existing_threshold": any(
            p["candidate_evaluations"] and any(
                g["gate"] == "reuse" and g["result"] == "HITL" for e in p["candidate_evaluations"]
                for g in e["gates"]) for p in proposals)}))
    asks.update(q("9_acquisition", src["acquisition"]["counts"]))
    asks.update(q("10_binding_proposals", {"actions": ca, "artifact": "visual_binding_proposals.json"}))
    asks.update(q("11_no_safe_candidate_reasons", {
        "NO_BINDING": ca[VB.NO_BINDING], "HITL_REQUIRED": ca[VB.HITL_REQUIRED],
        "coverage": cc, "rule": "无法通过必要门禁 ⇒ NOT_BINDABLE，而非强行选择"}))
    return asks


def verify(path: str, db: str = DEFAULT_DB, task_id: str = DEFAULT_TASK,
           logs: str = DEFAULT_LOGS) -> dict:
    old = _json(path)
    new = build(db, task_id, logs)
    key = "proposals" if "proposals" in old else "coverage"
    if old.get("artifact_hash") != new[key]["artifact_hash"]:
        raise ValueError("verify 失败：artifact_hash 不一致（{}）".format(key))
    return {"ok": True, "artifact_hash": new[key]["artifact_hash"],
            "proposals": len(new["proposals"]["proposals"])}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="visual_binding")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--db", default=DEFAULT_DB)
    b.add_argument("--task-id", default=DEFAULT_TASK)
    b.add_argument("--logs", default=DEFAULT_LOGS)
    b.add_argument("--json", action="store_true")
    v = sub.add_parser("verify")
    v.add_argument("path")
    v.add_argument("--db", default=DEFAULT_DB)
    v.add_argument("--task-id", default=DEFAULT_TASK)
    v.add_argument("--logs", default=DEFAULT_LOGS)
    a = ap.parse_args(argv)
    try:
        if a.cmd == "build":
            out = build(a.db, a.task_id, a.logs)
            if a.json:
                print(json.dumps(out, ensure_ascii=False, indent=1))
                return 0
            print("proposals={} actions={}".format(len(out["proposals"]["proposals"]),
                                                   json.dumps(out["proposals"]["counts"],
                                                              ensure_ascii=False)))
            print("coverage={}".format(json.dumps(out["coverage"]["counts"], ensure_ascii=False)))
            for p in out["proposals"]["proposals"]:
                print("  {} {} prev={} -> {} cov={}".format(
                    p["scene_id"], p["decision"], p["previous_asset_id"], p["candidate_id"],
                    p["coverage"]))
            print("proposals_hash={}".format(out["proposals"]["artifact_hash"]))
            print("coverage_hash={}".format(out["coverage"]["artifact_hash"]))
            return 0
        r = verify(a.path, a.db, a.task_id, a.logs)
        print("verify OK:", json.dumps(r, ensure_ascii=False))
        return 0
    except Exception as exc:                                              # noqa: BLE001
        print("FAIL-CLOSED [{}]: {}".format(type(exc).__name__, exc), file=sys.stderr)
        return 2


if __name__ == "__main__":                                                 # pragma: no cover
    sys.exit(main())
