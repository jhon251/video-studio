# -*- coding: utf-8 -*-
"""6-B/M3 —— **Revision Proposal 只读编排**（`run.py revision-plan`）。

数据流（全程只读，唯一写盘是**显式** `--out` 报告与 **append-only** 方案登记表）：
  6-B/M2 闭环报告（review items + 人工决策台账） → 取 **REJECT** finding → 套用**人工撰写的方案模板**
  （`proposal_specs`）→ `core/revision.make_proposal` 校验/绑定（finding_id、decision_ref(seq+sha)、
  scene/asset/window、原始 evidence、局部化上限、expected_effect.basis/assumption）→ 汇总；
  **DEFER/UNKNOWN** finding → 只生成 `evidence_gaps`（无 proposed_change）。

禁止执行：本模块不修改素材 / timeline / 字幕 / 旁白 / config / 成片，不写 DB、不派发任务；
`executed_actions` 恒为空。
"""
from __future__ import annotations

import json
from pathlib import Path

from ..core import revision as core_revision
from .review import build_review_report

SCHEMA = "revision-plan-v1"


def _match_specs(specs: list, finding: dict) -> list:
    """返回**全部**匹配该 finding 的模板（允许同一类级 REJECT 拆成多个批次方案，如 H3a/H3b）。"""
    exact = [s for s in (specs or []) if s.get("finding_id") == finding.get("finding_id")]
    if exact:
        return exact
    return [s for s in (specs or [])
            if s.get("match") and all(finding.get(k) == v for k, v in s["match"].items())]


def build_revision_plan(project_id: str, db_path: Path, root: Path, config: dict,
                        film_task: str | None = None, film: str | None = None,
                        evidence_path: str | None = None, ledger_path: str | None = None,
                        review_report: dict | None = None, proposal_specs: list | None = None,
                        extra_items: list | None = None, policy: dict | None = None,
                        known_scene_ids=None, known_asset_ids=None,
                        measure_freeze: bool = False) -> dict:
    """返回结构化只读方案计划（含覆盖统计、局部化统计、人工边界与零执行证明）。"""
    review = review_report or build_review_report(
        project_id, db_path, root, config, film_task=film_task, film=film,
        evidence_path=evidence_path, ledger_path=ledger_path, extra_items=extra_items,
        measure_freeze=measure_freeze)
    items = {i["finding_id"]: i for i in review["items"]}
    decisions = review["decisions"]
    last_by_id = {}
    for d in decisions:
        last_by_id[d["finding_id"]] = d

    rejects = [it for fid, it in items.items()
               if (last_by_id.get(fid) or {}).get("decision") == "REJECT"]
    proposals, gap_specs_used, errors = [], [], []
    for it in sorted(rejects, key=lambda x: (str(x.get("metric")), str(x.get("kind")))):
        specs_for = _match_specs(proposal_specs, it)
        if not specs_for:
            continue                                   # 未给模板 ⇒ 保持未覆盖（如实报告）
        for spec in specs_for:
            try:
                proposals.append(core_revision.make_proposal(
                    it, last_by_id[it["finding_id"]], spec["action"], spec.get("target") or {},
                    spec["proposed_change"], spec["affected_scope"], spec["expected_effect"],
                    constraints=spec.get("constraints"), risk=spec.get("risk"), policy=policy,
                    known_scene_ids=known_scene_ids, known_asset_ids=known_asset_ids,
                    discriminator=spec.get("id", ""), label=spec.get("id"),
                    evidence_refs=spec.get("evidence_refs")))
                gap_specs_used.append(spec.get("id"))
            except Exception as exc:                                # noqa: BLE001
                errors.append({"finding_id": it["finding_id"], "spec": spec.get("id"),
                               "error": "{}: {}".format(type(exc).__name__, exc)})

    gaps = []
    for fid, it in sorted(items.items()):
        dec = last_by_id.get(fid)
        if it.get("unprovable"):
            gaps.append(core_revision.evidence_gap(
                it, dec,
                needed="人工/语义复核（例如人工抽帧判定或既有只读语义证据补充）",
                why="该 finding 状态为 {}（不可证）；按 6-B/M3 授权，**不得**生成确定性修改方案".format(
                    it.get("severity")),
                provenance="6-B/M3 policy: unprovable ⇒ evidence gap only"))
    summary = core_revision.summarize_proposals(rejects, proposals, gaps)
    summary["proposal_specs_unmatched"] = sorted(
        {s.get("id") for s in (proposal_specs or [])} - {g for g in gap_specs_used if g})
    summary["build_errors"] = errors
    return {"schema": SCHEMA, "kind": "directorial_revision_plan", "read_only": True,
            "enforced": False, "advisory": True, "executes_changes": False,
            "mode": "6-B/M3（人工 REJECT → 局部修改方案；只生成方案，禁止执行）",
            "inputs": {"project_id": project_id, "film_task": review["inputs"].get("film_task"),
                       "film": review["inputs"].get("film"), "evidence": evidence_path,
                       "ledger": (str(ledger_path) if ledger_path else None),
                       "review_items": len(review["items"]),
                       "decisions": len(decisions),
                       "policy": {**core_revision.DEFAULT_POLICY, **(policy or {})}},
            "rejects": [{"finding_id": i["finding_id"], "metric": i.get("metric"),
                         "kind": i.get("kind"), "scene_id": i.get("scene_id"),
                         "asset_id": i.get("asset_id"), "window": i.get("window"),
                         "decision_seq": (last_by_id.get(i["finding_id"]) or {}).get("seq"),
                         "provenance": (last_by_id.get(i["finding_id"]) or {}).get("provenance")}
                        for i in rejects],
            "proposals": proposals, "evidence_gaps": gaps, "summary": summary,
            "review": review}


def write_report(report: dict, out_path: str | Path) -> Path:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def format_plan(report: dict) -> str:
    s = report["summary"]
    L = ["Revision Plan（只生成方案，禁止执行）  project={} film={}".format(
        report["inputs"]["project_id"], report["inputs"]["film"]),
        "  REJECT finding={} 已覆盖={} 未覆盖={}".format(
            s["rejects"], s["rejects_covered"], s["rejects_uncovered"]),
        "  方案={} 待补证据项={} 局部化违规={} 动作类别={}".format(
            s["proposals"], s["evidence_gaps"], s["locality_cap_violations"], s["actions"]),
        "  人工批准要求={} 已执行={} executed_actions={}".format(
            s["requires_human_approval"], s["executed"], s["executed_actions"])]
    for p in report["proposals"]:
        sc = p["affected_scope"]
        L.append("  {:<14s} {:<20s} {:<16s} scenes={} assets={} win={}".format(
            p["proposal_id"], str(p["kind"])[:20], p["action"],
            len(sc.get("scenes") or []), len(sc.get("assets") or []), sc.get("window")))
    for g in report["evidence_gaps"]:
        L.append("  {:<14s} {:<20s} 待补证据（不生成修改方案）".format(
            g["gap_id"], str(g["kind"])[:20]))
    return "\n".join(L)
