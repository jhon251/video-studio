# -*- coding: utf-8 -*-
"""6-B/M2 —— Human Review Bridge **只读编排**（`run.py review`）。

只读保证：
  · DQ 指标经 `ops.direction.build_direction_report`（`mode=ro` + `query_only`）现算，或由调用方传入；
  · 本编排**不写 DB、不写项目目录/产物、不改 timeline/素材/字幕/旁白/成片**；
  · 决策台账由**显式** `--decide`/`append_decision` 追加（append-only + 哈希链）；
    本编排自身只**读取**台账并把决策与 finding 一一对应；
  · `executed_actions` 恒为空列表 —— 本阶段禁止任何自动执行（REJECT 仅表示"建议需要修改"）。
"""
from __future__ import annotations

import json
from pathlib import Path

from ..core import direction as core_direction
from ..core import human_review as core_review
from . import direction as ops_direction

SCHEMA = "human-review-v1"


def build_review_report(project_id: str, db_path: Path, root: Path, config: dict,
                        film_task: str | None = None, film: str | None = None,
                        evidence_path: str | None = None, ledger_path: str | None = None,
                        policy: dict | None = None, measure_freeze: bool = False,
                        extra_items: list | None = None,
                        film_level_decision: dict | None = None) -> dict:
    """返回结构化只读审片闭环报告（DQ finding ↔ 人类决策 一一对应）。"""
    dq = ops_direction.build_direction_report(project_id, db_path, root, config,
                                              film_task=film_task, film=film,
                                              evidence_path=evidence_path, policy=policy,
                                              measure_freeze=measure_freeze)
    items = core_review.findings_from_direction(dq["metrics"], project_id,
                                                film_task=dq["inputs"].get("film_task"),
                                                source_evidence=evidence_path)
    for it in (extra_items or []):
        items.append(it)
    ledger = core_review.load_ledger(ledger_path) if ledger_path else []
    chain = core_review.verify_chain(ledger)
    summary = core_review.summarize_review(items, ledger, film_level=film_level_decision)
    # 台账链校验结果并入汇总（append-only 证明）
    summary["ledger"] = {"path": (str(ledger_path) if ledger_path else None),
                         "entries": chain["length"], "chain_ok": chain["ok"],
                         "chain_broken_at": chain["broken_at"], "chain_why": chain["why"]}
    return {"schema": SCHEMA, "kind": "human_review_bridge", "read_only": True,
            "enforced": False, "advisory": True, "executes_changes": False,
            "mode": "6-B/M2（DQ finding → 人工决策闭环；只读 + append-only；禁止自动执行）",
            "inputs": {"project_id": project_id, "film_task": dq["inputs"].get("film_task"),
                       "film": dq["inputs"].get("film"),
                       "evidence": evidence_path, "ledger": (str(ledger_path) if ledger_path
                                                             else None),
                       "dq_metrics": {k: v.get("state") for k, v in dq["metrics"].items()}},
            "dq": {"metrics": dq["metrics"], "summary": dq["summary"]},
            "items": items, "decisions": ledger, "summary": summary,
            "decision_vocabulary": list(core_review.DECISIONS),
            "decision_semantics": core_review.DECISION_SEMANTICS,
            "policy": {"unknown_requires_human": True,
                       "unknown_cannot_be_accepted": True,
                       "reject_means_recommendation_only": True,
                       "auto_execution": False,
                       "thresholds": {**(policy or core_direction.DEFAULT_POLICY)}}}


def write_report(report: dict, out_path: str | Path) -> Path:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def format_review(report: dict) -> str:
    s = report["summary"]
    inp = report["inputs"]
    L = ["Human Review Bridge（只读 + append-only；本阶段禁止自动执行）  project={} film={}".format(
        inp["project_id"], inp["film"]),
        "  DQ: {}".format(json.dumps(inp["dq_metrics"], ensure_ascii=False)),
        "  items={} decided={} 决策计数={}".format(
            s["items"], s["decided"], {k: v for k, v in s["decision_counts"].items() if v}),
        "  未决={} 孤儿决策={} 无锚点 item={} UNKNOWN 被 ACCEPT={}".format(
            len(s["unresolved"]), len(s["decisions_without_item"]),
            len(s["untraceable_items"]), len(s["unknown_accepted"])),
        "  台账: {} 条 | 链完整={} | 执行动作={}".format(
            s["ledger"]["entries"], s["ledger"]["chain_ok"], s["executed_actions"])]
    for r in s["rows"]:
        L.append("  {:<16s} {:<5s} {:<26s} {:<8s} {:<10s} {}".format(
            r["finding_id"], str(r["decision"]), str(r["kind"])[:26], str(r["metric"]),
            ("UNKNOWN" if r["unprovable"] else ""), str(r["provenance"])[:40]))
    return "\n".join(L)
