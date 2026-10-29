# -*- coding: utf-8 -*-
"""6-B/M3 —— **Human-Approved Directorial Revision Proposal**（只生成方案；**禁止执行**）。

职责：
  1. 把 6-B/M2 中**已被人工 REJECT** 的 finding 转成**结构化、局部、可执行（在原则上）**的修改方案；
  2. 每个方案必须绑定：`finding_id` → **Human REJECT decision**（台账 seq + entry_sha256）→
     scene/asset/window → 原始 evidence，并显式给出 `proposed_change / affected_scope /
     expected_effect / constraints / risk / provenance`；
  3. **DEFER / UNKNOWN finding 只产出"待补证据项"**（`evidence_gaps`），绝不生成确定性修改方案；
  4. 方案必须**局部化**：超过 `max_scenes_per_proposal` / `max_share_of_film_per_proposal`
     的"全片级"改动一律**拒绝生成**（要求拆成批次），杜绝无依据的全片重构；
  5. **禁止执行**：本模块不修改素材 / timeline / 字幕 / 旁白 / config / 成片，
     不写 DB、不写产物、不派发任务；方案只写**append-only 方案登记表**（hash 链）供人工审批。

反虚构契约（代码级 guard）：
  · `affected_scope.scenes` 必须 ⊆ 真实 timeline 镜头集合；`affected_scope.assets` 必须 ⊆ 已知素材集合；
  · 需要新素材时**只能**声明 `new_assets_needed{count, semantic_spec, sourcing}`，
    **不得**虚构 asset_id；
  · `expected_effect` 必须带 `basis`（引用源 finding 的实测数值）与 `assumption`（不确定性说明）。
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "revision-proposal-v1"
READONLY = {"read_only": True, "enforced": False, "advisory": True, "executes_changes": False}
REQUIRED_FIELDS = ("proposal_id", "finding_id", "decision_ref", "affected_scope",
                   "proposed_change", "expected_effect", "constraints", "risk", "provenance")
CHANGE_ACTIONS = ("replace_asset", "add_asset", "split_scene", "adjust_hold", "reorder_scenes",
                  "insert_scene", "text_overlay", "add_outro_card", "add_visual_aid",
                  "no_change_evidence_gap")
DEFAULT_POLICY = {
    "max_scenes_per_proposal": 6,            # 单方案受影响镜头数上限（局部化硬约束）
    "max_share_of_film_per_proposal": 0.30,  # 单方案受影响时长占比上限
    "forbid_film_wide_rewrite": True,        # 禁止无依据的全片重构
    "require_human_approval": True,          # 任何方案执行前必须人工批准
    "max_assets_per_proposal": 6,
}
#: 执行方案时**必须**重跑的既有门禁/评估（写死在约束里，避免"改完不验"）
MUST_RERUN = ("PI-1..PI-6 生产完整性门禁", "DQ-1..DQ-8 导演质量只读诊断",
              "素材抽帧核验（min_corr/argmax）", "响度契约（−16 LUFS / TP）",
              "时长契约（timeline 权威）", "许可/署名台账")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha_text(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def proposal_id(finding_id: str, action: str, discriminator: str = "") -> str:
    return "rp-" + _sha_text("|".join([str(finding_id), str(action), str(discriminator)]))[:12]


def decision_ref(entry: dict) -> dict:
    """把 M2 台账里那条 **REJECT** 决策固化为可校验的引用（含链上 sha，防篡改）。"""
    return {"ledger_seq": entry.get("seq"), "decision": entry.get("decision"),
            "decided_by": entry.get("decided_by"), "decided_at": entry.get("decided_at"),
            "provenance": entry.get("provenance"),
            "entry_sha256": entry.get("entry_sha256"),
            "reject_means": "建议需要修改（M2 语义）；本阶段不执行"}


def make_proposal(finding: dict, decision_entry: dict, action: str, target: dict,
                  proposed_change: dict, affected_scope: dict, expected_effect: dict,
                  constraints: dict | None = None, risk: list | None = None,
                  policy: dict | None = None, known_scene_ids=None, known_asset_ids=None,
                  discriminator: str = "", evidence_refs: list | None = None,
                  label: str | None = None) -> dict:
    """构造一条**局部化**修改方案（校验：来源必须是人工 REJECT；范围必须可定位且不越界）。"""
    p = {**DEFAULT_POLICY, **(policy or {})}
    if not finding or not finding.get("finding_id"):
        raise ValueError("PROPOSAL_REQUIRES_FINDING: 缺少 finding_id")
    # 顺序有意为之：**先**判"不可证不得变成修改指令"（更强的守恒规则），再判"必须有人工 REJECT"
    if finding.get("unprovable"):
        raise ValueError("DEFER_MUST_NOT_BECOME_CHANGE: finding {} 属不可证（{}），"
                         "只能产出待补证据项".format(finding.get("finding_id"),
                                                finding.get("severity")))
    if not decision_entry or decision_entry.get("decision") != "REJECT":
        raise ValueError("PROPOSAL_REQUIRES_HUMAN_REJECT: finding {} 没有人工 REJECT 决策，"
                         "不得生成确定性修改方案".format(finding.get("finding_id")))
    if action not in CHANGE_ACTIONS:
        raise ValueError("非法 action: {!r}".format(action))
    scenes = list(affected_scope.get("scenes") or [])
    if known_scene_ids is not None:
        unknown = [s for s in scenes if s not in set(known_scene_ids)]
        if unknown:
            raise ValueError("SCOPE_UNKNOWN_SCENES: {}".format(unknown))
    assets = list(affected_scope.get("assets") or [])
    if known_asset_ids is not None:
        unknown_a = [a for a in assets if a not in set(known_asset_ids)]
        if unknown_a:
            raise ValueError("SCOPE_UNKNOWN_ASSETS: {}（需要新素材请用 new_assets_needed 声明，"
                             "不得虚构 asset_id）".format(unknown_a))
    if assets and len(assets) > p["max_assets_per_proposal"]:
        raise ValueError("SCOPE_TOO_MANY_ASSETS: {} > {}".format(len(assets),
                                                                p["max_assets_per_proposal"]))
    # 局部化硬约束：镜头数与时长占比
    if len(scenes) > p["max_scenes_per_proposal"]:
        raise ValueError("SCOPE_NOT_LOCAL: {} 个镜头 > 上限 {}（请拆成批次方案）".format(
            len(scenes), p["max_scenes_per_proposal"]))
    share = affected_scope.get("share_of_film")
    if share is not None and share > p["max_share_of_film_per_proposal"]:
        raise ValueError("SCOPE_NOT_LOCAL: 时长占比 {} > 上限 {}（禁止全片重构）".format(
            share, p["max_share_of_film_per_proposal"]))
    if p["forbid_film_wide_rewrite"] and affected_scope.get("film_wide"):
        raise ValueError("FILM_WIDE_REWRITE_FORBIDDEN: 必须给出局部范围与依据")
    if not (affected_scope.get("scenes") or affected_scope.get("assets")
            or affected_scope.get("window") or affected_scope.get("asset_class")):
        raise ValueError("SCOPE_NOT_LOCATABLE: 必须给出 scene / asset / window / asset_class")
    if not expected_effect.get("basis"):
        raise ValueError("EXPECTED_EFFECT_REQUIRES_BASIS: 必须引用源 finding 的实测数值")
    if not expected_effect.get("assumption"):
        raise ValueError("EXPECTED_EFFECT_REQUIRES_ASSUMPTION: 必须写明不确定性")

    pid = proposal_id(finding["finding_id"], action, discriminator)
    rec = {
        "schema": SCHEMA,
        "proposal_id": pid,
        "label": (label or discriminator or None),      # 人工可读标签（如 H1-hook-replace）
        "finding_id": finding["finding_id"],
        "metric": finding.get("metric"),
        "kind": finding.get("kind"),
        "severity": finding.get("severity"),
        "scene_id": finding.get("scene_id"),
        "asset_id": finding.get("asset_id"),
        "window": finding.get("window"),
        "original_evidence": finding.get("source_evidence"),
        "evidence_refs": list(evidence_refs or []),
        "decision_ref": decision_ref(decision_entry),
        "action": action,
        "target": target,
        "proposed_change": proposed_change,
        "affected_scope": {**affected_scope,
                           "locality_limits": {"max_scenes_per_proposal":
                                               p["max_scenes_per_proposal"],
                                               "max_share_of_film_per_proposal":
                                               p["max_share_of_film_per_proposal"]},
                           "not_touching": list(affected_scope.get("not_touching") or [])},
        "expected_effect": expected_effect,
        "constraints": {**(constraints or {}),
                        "must_rerun": list(MUST_RERUN),
                        "requires_human_approval": p["require_human_approval"],
                        "no_auto_execution": True,
                        "must_preserve": list(constraints.get("must_preserve")
                                              if constraints and constraints.get("must_preserve")
                                              else ["旁白文本", "字幕文本", "时间轴总时长",
                                                    "既有许可/署名台账"])},
        "risk": list(risk or []),
        "provenance": {"chain": ["DQ finding " + finding["finding_id"],
                                 "Human REJECT decision seq={}".format(
                                     decision_entry.get("seq")),
                                 "Revision proposal " + pid],
                       "source_evidence": finding.get("source_evidence"),
                       "decision_entry_sha256": decision_entry.get("entry_sha256"),
                       "generated_at": _now(),
                       "generator": "core/revision.py::make_proposal",
                       "human_decision_boundary": "方案由人工 REJECT 触发；执行权在人工，"
                                                  "本阶段不执行"},
        "status": "PROPOSED_AWAITING_HUMAN_APPROVAL",
        "approved": False,
        "executed": False,
        **READONLY,
    }
    missing = verify_proposal(rec)
    if missing:
        raise ValueError("方案缺少必需字段: {}".format(missing))
    return rec


def verify_proposal(rec: dict) -> list:
    bad = [k for k in REQUIRED_FIELDS if rec.get(k) in (None, "", [], {})]
    if rec.get("executed") is not False:
        bad.append("executed")
    if rec.get("executes_changes") is not False:
        bad.append("executes_changes")
    if (rec.get("decision_ref") or {}).get("decision") != "REJECT":
        bad.append("decision_ref.decision")
    return bad


def evidence_gap(finding: dict, decision_entry: dict | None, needed: str,
                 why: str, provenance: str) -> dict:
    """DEFER / UNKNOWN → **待补证据项**（明确"不生成修改方案"）。"""
    return {
        "schema": "revision-evidence-gap-v1",
        "gap_id": "eg-" + _sha_text(str(finding.get("finding_id")) + needed)[:12],
        "finding_id": finding.get("finding_id"),
        "metric": finding.get("metric"),
        "kind": finding.get("kind"),
        "severity": finding.get("severity"),
        "unprovable": True,
        "decision_ref": (decision_ref(decision_entry) if decision_entry else None),
        "needed_evidence": needed,
        "why": why,
        "no_proposed_change": True,
        "provenance": provenance,
        "status": "AWAITING_EVIDENCE",
        "executed": False,
        **READONLY,
    }


def summarize_proposals(rejects: list, proposals: list, gaps: list) -> dict:
    """汇总：REJECT 覆盖率、局部化统计、人工边界与零执行证明。"""
    covered_findings = {p["finding_id"] for p in (proposals or [])}
    reject_ids = {r["finding_id"] for r in (rejects or [])}
    cap_violations = []
    for p in (proposals or []):
        sc = p["affected_scope"]
        if len(sc.get("scenes") or []) > DEFAULT_POLICY["max_scenes_per_proposal"]:
            cap_violations.append(p["proposal_id"])
        if sc.get("film_wide"):
            cap_violations.append(p["proposal_id"])
    return {
        "schema": "revision-plan-v1",
        "rejects": len(reject_ids),
        "proposals": len(proposals or []),
        "rejects_covered": len(reject_ids & covered_findings),
        "rejects_uncovered": sorted(reject_ids - covered_findings),
        "evidence_gaps": len(gaps or []),
        "gap_findings": [g["finding_id"] for g in (gaps or [])],
        "locality_cap_violations": cap_violations,
        "all_local": not cap_violations,
        "actions": sorted({p["action"] for p in (proposals or [])}),
        "requires_human_approval": all(
            (p["constraints"] or {}).get("requires_human_approval") for p in (proposals or [])),
        "executed": [p["proposal_id"] for p in (proposals or []) if p.get("executed")],
        "executed_actions": [],            # 恒为空：本阶段禁止执行
        "executes_changes": False,
        **READONLY,
    }


# ---------------------------------------------------------------- append-only 方案登记
def _entry_sha(entry: dict) -> str:
    body = {k: v for k, v in entry.items() if k != "entry_sha256"}
    return _sha_text(json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":")))


def append_proposal(register_path: str | Path, rec: dict) -> dict:
    """把方案写入 **append-only** 登记表（hash 链）；只追加，绝不改写历史。"""
    p = Path(register_path)
    entries = load_register(p)
    prev = entries[-1]["entry_sha256"] if entries else ""
    out = dict(rec)
    out["seq"] = len(entries) + 1
    out["prev_sha256"] = prev
    out["register"] = {"append_only": True, "schema": SCHEMA}
    out["entry_sha256"] = _entry_sha(out)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(out, ensure_ascii=False) + "\n")
    return out


def load_register(register_path: str | Path) -> list:
    p = Path(register_path)
    if not p.is_file():
        return []
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


def verify_register_chain(entries: list) -> dict:
    prev = ""
    for i, e in enumerate(entries or [], start=1):
        if e.get("seq") != i:
            return {"ok": False, "length": len(entries), "broken_at": i, "why": "seq 不连续"}
        if e.get("prev_sha256") != prev:
            return {"ok": False, "length": len(entries), "broken_at": i,
                    "why": "prev_sha256 不符（历史被改写/插入）"}
        if e.get("entry_sha256") != _entry_sha(e):
            return {"ok": False, "length": len(entries), "broken_at": i,
                    "why": "entry_sha256 不匹配（条目被改写）"}
        prev = e["entry_sha256"]
    return {"ok": True, "length": len(entries or []), "broken_at": None, "why": None}
