"""Conflict Detector Agent：发现同一 claim 的多证据冲突。

- 不裁决事实：所有冲突 human_review_required=true，claim 置 NEEDS_HUMAN 提交人工
- 检测规则（确定性）：
  1. 数值矛盾：两条证据摘录中的数字集合不一致（对称差非空）——提示"数值表述不一致"
  2. 可靠性冲突：reliability 相差 ≥2 级（仅作潜在冲突提示，不等同事实矛盾）
- **来源发布日期不同不构成冲突**（不同来源本就先后发布；日期差异由 recency_comparison
  如实记录，仅供人工参考）
- 建议（recommended）仅作参考：优先高可靠性，其次更新日期，无法判断则明示人工裁决
- 产出：conflicts 表 + conflict_report 产物 + CONFLICT_DETECTED 事件（human_visible）
"""

from __future__ import annotations

import re

from ..base import Agent, register

REL_ORDER = {"high": 3, "medium": 2, "low": 1, "unknown": 0}
_NUM = re.compile(r"\d+")


def _numbers(text: str) -> set[str]:
    return set(_NUM.findall(text or ""))


def _compare_authority(a: dict, b: dict) -> str:
    return (f"{a['source']}（{a['source_type']}/{a['reliability']}） vs "
            f"{b['source']}（{b['source_type']}/{b['reliability']}）")


def _compare_recency(a: dict, b: dict) -> str:
    da, db = a.get("publication_date"), b.get("publication_date")
    if da and db:
        return f"A {da} vs B {db}"
    if da or db:
        return f"仅一侧有日期（{'A' if da else 'B'}）"
    return "双方均无日期"


def _recommend(a: dict, b: dict) -> str:
    ra, rb = REL_ORDER.get(a["reliability"], 0), REL_ORDER.get(b["reliability"], 0)
    if ra != rb:
        winner = "A" if ra > rb else "B"
        return f"建议优先 {winner}（可靠性更高）；仍请人工确认"
    da, db = a.get("publication_date"), b.get("publication_date")
    if da and db and da != db:
        winner = "A" if da > db else "B"
        return f"建议优先 {winner}（日期更新）；仍请人工确认"
    return "无法自动判断，请人工裁决"


@register
class ConflictDetectorAgent(Agent):
    role = "conflict_detector"
    tier = "M"
    needs_llm = False
    description = "冲突检测：多源证据冲突识别，提交人工审核，不自行裁决。"

    def run(self, engine, task: dict) -> None:
        project_id = task["project_id"]
        claim_ids = task["inputs"].get("claim_ids") or []
        if not claim_ids:
            claim_ids = [c["claim_id"] for c in engine.db.list_claims(project_id)]

        conflicts = []
        for cid in claim_ids:
            evs = engine.db.evidence_for_claim(cid)
            if len(evs) < 2:
                continue
            for i in range(len(evs)):
                for j in range(i + 1, len(evs)):
                    a, b = evs[i], evs[j]
                    num_a, num_b = _numbers(a.get("excerpt")), _numbers(b.get("excerpt"))
                    # 仅当两侧摘录都含数字且数字集合不一致时，视为数值表述矛盾
                    value_conflict = bool(num_a) and bool(num_b) and bool(num_a ^ num_b)
                    rel_conflict = abs(REL_ORDER.get(a["reliability"], 0)
                                       - REL_ORDER.get(b["reliability"], 0)) >= 2
                    if not (value_conflict or rel_conflict):
                        continue
                    desc_parts = []
                    if value_conflict:
                        desc_parts.append(
                            f"数值表述不一致：A 含 [{', '.join(sorted(num_a))[:60]}] "
                            f"vs B 含 [{', '.join(sorted(num_b))[:60]}]")
                    if rel_conflict:
                        desc_parts.append("可靠性等级差异≥2（潜在冲突，非事实矛盾）")
                    from ...core.ids import new_id
                    conflict_id = new_id("f")
                    conflict = {
                        "conflict_id": conflict_id, "project_id": project_id, "claim_id": cid,
                        "source_a": a["evidence_id"], "source_b": b["evidence_id"],
                        "description": "；".join(desc_parts),
                        "authority_comparison": _compare_authority(a, b),
                        "recency_comparison": _compare_recency(a, b),
                        "recommended": _recommend(a, b),
                        "confidence": "High" if value_conflict and rel_conflict else "Medium",
                        "human_review_required": True,
                        "status": "OPEN",
                    }
                    engine.db.insert_conflict(conflict)
                    conflicts.append({k: v for k, v in conflict.items()
                                      if k not in ("project_id",)})
                    # 不裁决事实，只路由人工
                    engine.db.update_claim(cid, status="NEEDS_HUMAN", human_review_required=True)
                    engine.emit(project_id, "CONFLICT_DETECTED", self.role, task["task_id"],
                                {"claim_id": cid, "conflict_id": conflict_id}, human_visible=True)

        data = {
            "conflicts": conflicts,
            "summary": f"发现 {len(conflicts)} 处来源冲突，全部提交人工审核",
            "confidence": 1.0,
            "note": "冲突不自行裁决；人工决定后经 decide_claim 闭环",
        }
        aid = engine.write_artifact(task["project_id"], task["task_id"], "conflict_report",
                                    data, summary=data["summary"])
        engine.attach_artifact(task["task_id"], aid)
        engine.db.update_task(task["task_id"], confidence=1.0)
