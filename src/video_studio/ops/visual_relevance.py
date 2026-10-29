# -*- coding: utf-8 -*-
"""P7-4：视觉相关性判定 **ops 入口**（**严格只读**：不写文件、零网络、零 LLM/VLM、无 DB 写入）。

用法：
  python -m video_studio.ops.visual_relevance build [--json]
  python -m video_studio.ops.visual_relevance verify PATH

只读消费（全部为既有产物）：
  P7-1 `visual_requirements.json`、P7-2 `asset_index.json`、生产 `render_output`（21 场景 +
  人工选材理由）、`phase6b_m2_review_ledger_v9.jsonl`（pair 级人类 REJECT）、
  `phase6e_review_ledger_r2.jsonl`（场景级人类判定，**仅记录不驱动候选决策**）、
  `phase6g_rebuild_proposals.json`（`forbidden_material` 人工明确否决）、
  `phase6g_exec_h5.json`（人工验收绑定）。
artifact 落盘 = `docs/regression_2x/phase7_p7_4_build.py`（ops 不得写文件）。
fail-closed：源缺失 / 校验失败 / hash 不一致 ⇒ 非零退出。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

from ..core import visual_relevance as VR
from ..core.mm_judge import judge_scene                                     # 只读：能力探测
from ..core.asset_candidate import UNKNOWN

DEFAULT_DB = r"C:\mp4agent\video-studio\projects\video_studio.db"
DEFAULT_TASK = "t_d0a54bdf1810"
DEFAULT_LOGS = r"C:\mp4agent\video-studio\docs\regression_2x\logs"
DEFAULT_OUT = r"C:\mp4agent\video-studio\docs\regression_2x\logs\visual_relevance.json"

#: 只有这些 `kind` 才是**语义相关性**判定（其它 DQ/结构类 finding 不构成相关性证据）
SEMANTIC_KINDS = ("semantic_mismatch_scenes", "asset_semantically_unrelated_imo_group_photo")
NON_RELEVANCE_KINDS_PREFIX = ("hook_", "unique_assets", "over_hold", "scene_changes",
                              "no_outro_keyword", "metric_state", "outro_card", "human_",
                              "distinct_assets", "long_hold")


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


def _jsonl(p) -> list[dict]:
    return [json.loads(x) for x in Path(p).read_text(encoding="utf-8").splitlines() if x.strip()]


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
    req_p = _require(L / "visual_requirements.json", "P7-1 requirements")
    idx_p = _require(L / "asset_index.json", "P7-2 asset_index")
    m2_p = _require(L / "phase6b_m2_review_ledger_v9.jsonl", "M2 人类判定台账")
    e6_p = _require(L / "phase6e_review_ledger_r2.jsonl", "6-E 人类判定台账")
    pkg_p = _require(L / "phase6g_rebuild_proposals.json", "6-G 提案包")
    h5_p = _require(L / "phase6g_exec_h5.json", "H5 报告")
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
    return {"requirements": _json(req_p), "index": _json(idx_p), "m2": _jsonl(m2_p),
            "e6": _jsonl(e6_p), "pkg": _json(pkg_p), "h5": _json(h5_p),
            "render": _json(ro_p),
            "sources": [{"role": r, "path": str(p), "sha256": sha256_file(p)}
                        for r, p in (("p7_1_visual_requirements", req_p),
                                     ("p7_2_asset_index", idx_p),
                                     ("m2_review_ledger", m2_p), ("e6_review_ledger", e6_p),
                                     ("rebuild_proposals", pkg_p), ("h5_report", h5_p),
                                     ("render_output", ro_p))]}


def build_human_evidence(src: dict) -> dict:
    """机器可读人类证据：**pair 级** 驱动决策；场景级仅记录。"""
    legacy = {}
    for c in src["index"].get("candidates") or []:
        for lid in c.get("legacy_asset_ids") or []:
            legacy[lid] = c["asset_id"]
    pos, neg, scene_signals, non_rel = {}, {}, [], []
    # 生产人工选材理由（21/21）
    for seg in src["render"].get("material_timeline") or []:
        sa = seg.get("selected_asset") or {}
        hs = seg.get("human_selection") or {}
        aid = legacy.get(sa.get("asset_id"), sa.get("asset_id"))
        if hs and aid:
            pos[(str(seg.get("scene_id")), aid)] = {
                "source": "material_timeline.human_selection",
                "decision": "SELECTED", "by": hs.get("decided_by"),
                "decision_id": hs.get("decision_id"), "reason": hs.get("reason")}
    # M2 台账：pair 级语义 REJECT（kind 属语义类且有 asset_id）
    for r in src["m2"]:
        kind = str(r.get("kind") or "")
        if kind in SEMANTIC_KINDS and r.get("asset_id") and r.get("scene_id"):
            aid = legacy.get(r["asset_id"], r["asset_id"])
            neg[(str(r["scene_id"]), aid)] = {
                "source": "phase6b_m2_review_ledger_v9", "decision": r.get("decision"),
                "kind": kind, "finding_id": r.get("finding_id"),
                "reason": r.get("reason")}
        elif kind.startswith(NON_RELEVANCE_KINDS_PREFIX) or r.get("decision") == "DEFER":
            non_rel.append({"source": "phase6b_m2_review_ledger_v9", "seq": r.get("seq"),
                            "kind": kind, "decision": r.get("decision"),
                            "why": "非语义相关性 finding/DEFER ⇒ 不作为相关性证据"})
    # 6-G forbidden_material：人工明确否决某 asset 作为某 scene 的素材
    for p in src["pkg"].get("proposals") or []:
        na = ((p.get("proposed_change") or {}).get("params") or {}).get("new_assets_needed")
        for sid, v in ((na or {}).get("per_scene") or {}).items():
            for fm in (v.get("forbidden_material") or []):
                aid = legacy.get(fm.get("asset_id"), fm.get("asset_id"))
                neg[(str(sid), aid)] = {"source": "phase6g_rebuild_proposals.forbidden_material",
                                        "decision": "REJECT", "reason": fm.get("why"),
                                        "proposal": p.get("label")}
    # 6-E 台账：场景级（asset_id 为空）⇒ 仅记录
    for r in src["e6"]:
        scene_signals.append({"source": "phase6e_review_ledger_r2", "seq": r.get("seq"),
                              "scene_id": r.get("scene_id"), "decision": r.get("decision"),
                              "kind": r.get("kind"), "reason": r.get("reason"),
                              "applies_to": "场景级信号（未指名 asset）⇒ **不驱动**候选决策，仅记录",
                              "is_semantic": str(r.get("kind") or "") in SEMANTIC_KINDS})
    # H5 人工验收绑定 ⇒ pair 级正向
    for sid, aid_legacy in (src["h5"].get("binding") or {}).items():
        aid = legacy.get(aid_legacy, aid_legacy)
        rec = (src["h5"].get("asset_records") or {}).get(sid) or {}
        pos[(str(sid), aid)] = {"source": "phase6g_exec_h5.human_acceptance",
                                "decision": "ACCEPTED_FOR_SCENE", "reason":
                                    src["h5"].get("human_decision"),
                                "license": rec.get("license"), "license_class":
                                    rec.get("license_class")}
    return {"positive": pos, "negative": neg, "scene_level_signals": scene_signals,
            "non_relevance_findings": non_rel}


def build(db: str = DEFAULT_DB, task_id: str = DEFAULT_TASK, logs: str = DEFAULT_LOGS) -> dict:
    src = load_sources(db, task_id, logs)
    hum = build_human_evidence(src)
    reqs = {r["scene_id"]: r for r in (src["requirements"].get("requirements") or [])}
    cands = {c["asset_id"]: c for c in (src["index"].get("candidates") or [])}
    timeline = src["render"].get("material_timeline") or []
    policy = dict(VR.POLICY)
    policy["index_artifact_hash"] = src["index"].get("artifact_hash")
    policy["requirements_artifact_hash"] = src["requirements"].get("artifact_hash")

    scene_results, all_dec = [], {d: 0 for d in VR.DECISIONS}
    for seg in timeline:
        sid = str(seg.get("scene_id"))
        req = reqs.get(sid)
        if req is None:
            raise SourceMissing("requirement 缺少场景 {}".format(sid))
        sel = seg.get("selected_asset") or {}
        sel_stable = next((c for c in cands.values() if c["sha256"] == sel.get("sha256")), None) \
            or next((c for c in cands.values() if sel.get("asset_id") in
                     (c.get("legacy_asset_ids") or [])), None)
        cres, dec_counts = [], {d: 0 for d in VR.DECISIONS}
        for aid in sorted(cands):
            r = VR.judge_candidate(requirement=req, candidate=cands[aid], index_asset=cands[aid],
                                   human_pair_evidence=hum, policy=policy,
                                   is_scene_current_asset=bool(
                                       sel_stable and sel_stable["asset_id"] == aid))
            dec_counts[r["decision"]] += 1
            all_dec[r["decision"]] += 1
            cres.append(r)
        best = next((d for d in VR.DECISION_PRECEDENCE if dec_counts[d] > 0), None)
        scene_results.append({
            "scene_id": sid, "requirement_id": req["requirement_id"],
            "current_asset_id": (sel_stable or {}).get("asset_id"),
            "current_asset_decision": next((c["decision"] for c in cres
                                            if c["is_scene_current_asset"]), None),
            "scene_candidate_count": len(cres),
            "relevant_candidate_count": dec_counts[VR.RELEVANT],
            "partial_candidate_count": dec_counts[VR.PARTIAL],
            "irrelevant_candidate_count": dec_counts[VR.IRRELEVANT],
            "not_assessable_candidate_count": dec_counts[VR.NOT_ASSESSABLE],
            "has_relevant_candidate": dec_counts[VR.RELEVANT] > 0,
            "has_assessable_candidate": (dec_counts[VR.RELEVANT] + dec_counts[VR.PARTIAL]
                                         + dec_counts[VR.IRRELEVANT]) > 0,
            "best_decision": best,
            "best_decision_note": "仅按固定 decision precedence 表示**判定状态**，"
                                  "**不代表**质量/审美排名",
            "candidate_results": cres})
    n_scenes = len(scene_results)
    with_rel = sum(1 for s in scene_results if s["has_relevant_candidate"])
    cur_rel = sum(1 for s in scene_results if s["current_asset_decision"] == VR.RELEVANT)
    cur_irr = sum(1 for s in scene_results if s["current_asset_decision"] == VR.IRRELEVANT)
    cur_na = sum(1 for s in scene_results if s["current_asset_decision"] == VR.NOT_ASSESSABLE)
    agg = {
        "scene_count": n_scenes, "candidate_count": len(cands),
        "pairs_evaluated": n_scenes * len(cands),
        "decision_counts": all_dec,
        "scenes_with_relevant_candidate": with_rel,
        "scenes_without_relevant_candidate": n_scenes - with_rel,
        "current_asset_decisions": {VR.RELEVANT: cur_rel, VR.IRRELEVANT: cur_irr,
                                    VR.NOT_ASSESSABLE: cur_na},
        "scenes_without_reliable_relevant_candidate": [s["scene_id"] for s in scene_results
                                                       if not s["has_relevant_candidate"]],
        "relevant_by_evidence_kind": {
            "human_recorded": sum(1 for s in scene_results for c in s["candidate_results"]
                                  if c["decision"] == VR.RELEVANT
                                  and c["confidence"] == "HUMAN_RECORDED"),
            "machine_visual": sum(1 for s in scene_results for c in s["candidate_results"]
                                  if c["decision"] == VR.RELEVANT
                                  and c["confidence"] != "HUMAN_RECORDED")},
        "headline": {
            "question": "当前 6-G 的 21 个 Scene 中，有多少能被现有资产**可靠**判为 RELEVANT？",
            "answer": "{}/{} 场景存在人工记录的可判 RELEVANT 候选；其中**机器视觉**判定 = 0"
                      "（视觉判定能力 NOT_AVAILABLE）".format(with_rel, n_scenes),
            "scenes_only_partial_or_not_assessable": [
                s["scene_id"] for s in scene_results
                if s["best_decision"] in (VR.PARTIAL, VR.NOT_ASSESSABLE)],
            "note": "未为提高 RELEVANT 数量而放宽任何标准；词面重叠只能得 PARTIAL",
        },
        "negative_constraint_coverage": {
            "scenes_with_negative_terms": sum(1 for s in scene_results
                                              if any((reqs[s["scene_id"]].get(f) or [])
                                                     for f in ("avoid_list", "concepts_neg"))),
            "pairs_with_unverified_negative_hits": sum(
                1 for s in scene_results for c in s["candidate_results"]
                if c["negative_conflicts"]),
            "pairs_with_verified_negative": sum(1 for s in scene_results
                                                for c in s["candidate_results"]
                                                if c["decision"] == VR.IRRELEVANT),
            "policy": "已验证负向 ⇒ IRRELEVANT；未验证（仅文件名词面命中）⇒ NOT_ASSESSABLE"
                      "（不静默忽略、也不凭文件名判负）"},
        "human_evidence_summary": {"pair_positive": len(hum["positive"]),
                                   "pair_negative": len(hum["negative"]),
                                   "scene_level_signals": len(hum["scene_level_signals"]),
                                   "non_relevance_findings": len(hum["non_relevance_findings"])},
        "human_evidence_detail": {"positive": [{"scene_id": k[0], "asset_id": k[1], **v}
                                               for k, v in sorted(hum["positive"].items())],
                                  "negative": [{"scene_id": k[0], "asset_id": k[1], **v}
                                               for k, v in sorted(hum["negative"].items())],
                                  "scene_level_signals": hum["scene_level_signals"]},
        "visual_judge_capability": VR.VISUAL_JUDGE_CAPABILITY,
        "judge_scene_probe": judge_scene({}),
    }
    art = VR.build_artifact(
        scene_results=scene_results, policy=policy, sources=src["sources"], aggregate=agg,
        requirements_snapshot={"artifact_hash": src["requirements"].get("artifact_hash"),
                               "requirements": len(reqs)},
        index_snapshot={"artifact_hash": src["index"].get("artifact_hash"),
                        "candidates": len(cands)})
    errs = VR.validate_artifact(art)
    if errs:
        raise ValueError("relevance artifact 校验失败：{}".format("; ".join(errs[:5])))
    return art


def verify(path: str, db: str = DEFAULT_DB, task_id: str = DEFAULT_TASK,
           logs: str = DEFAULT_LOGS) -> dict:
    old = _json(path)
    new = build(db, task_id, logs)
    if old.get("artifact_hash") != new.get("artifact_hash"):
        raise ValueError("verify 失败：artifact_hash 不一致")
    return {"ok": True, "artifact_hash": new["artifact_hash"],
            "pairs": new["aggregate"]["pairs_evaluated"]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="visual_relevance")
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
            art = build(a.db, a.task_id, a.logs)
            if a.json:
                print(json.dumps(art, ensure_ascii=False, indent=1))
                return 0
            ag = art["aggregate"]
            print("scenes={} candidates={} pairs={}".format(
                ag["scene_count"], ag["candidate_count"], ag["pairs_evaluated"]))
            print("decision_counts:", json.dumps(ag["decision_counts"], ensure_ascii=False))
            print("scenes_with_relevant_candidate={}/{} | machine_visual_relevant={}".format(
                ag["scenes_with_relevant_candidate"], ag["scene_count"],
                ag["relevant_by_evidence_kind"]["machine_visual"]))
            print("current_asset_decisions:", json.dumps(ag["current_asset_decisions"],
                                                         ensure_ascii=False))
            print("artifact_hash={}".format(art["artifact_hash"]))
            return 0
        r = verify(a.path, a.db, a.task_id, a.logs)
        print("verify OK:", json.dumps(r, ensure_ascii=False))
        return 0
    except Exception as exc:                                              # noqa: BLE001
        print("FAIL-CLOSED [{}]: {}".format(type(exc).__name__, exc), file=sys.stderr)
        return 2


if __name__ == "__main__":                                                 # pragma: no cover
    sys.exit(main())
