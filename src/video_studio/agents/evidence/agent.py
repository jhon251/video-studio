"""Evidence Agent：证据登记、来源分级、Claim-Evidence 关联（离线可运行）。

- 输入：资料卡（source_cards 产物引用）、来源核查报告（可选，映射可靠性）、人工来源列表
- 遵循 V2 SearchProvider 接口的"证据候选"概念：本 Agent 只做登记与分级；
  在线检索由后续阶段的 fact_check 经 SearchProvider 提供候选后交回此处登记
- 产出：evidence 表 + evidence_index 产物 + EVIDENCE_INDEXED 事件
- 关联：按关键词重叠把证据链接到已有 claims，并回写 claim.source_count
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from ..base import Agent, register

RULES_PATH = Path(__file__).resolve().parents[4] / "config" / "factcheck_rules.json"

_KEYWORD = re.compile(r"[\u4e00-\u9fff]{2,}|[A-Za-z]{2,}")


def _load_rules() -> dict:
    try:
        return json.loads(RULES_PATH.read_text(encoding="utf-8"))
    except OSError:
        return {}


def _classify_source(source: str, rules: dict) -> str:
    hints = rules.get("source_type_hints", {})
    for s_type, words in hints.items():
        if any(w in source for w in words):
            return s_type
    return "unknown"


def _overlap_score(claim_text: str, evidence_text: str) -> int:
    claim_words = set(_KEYWORD.findall(claim_text))
    ev_text = evidence_text or ""
    return sum(1 for w in claim_words if w in ev_text)


@register
class EvidenceAgent(Agent):
    role = "evidence"
    tier = "-"
    needs_llm = False
    description = "证据管理：登记证据、来源分级、Claim-Evidence 关联（离线模式可运行）。"

    def run(self, engine, task: dict) -> None:
        rules = _load_rules()
        project_id = task["project_id"]
        grade_map = rules.get("reliability_from_grade", {})

        entries = []
        # 1) 来源核查报告 → 可信度映射（按 source 名匹配）
        grades: dict[str, str] = {}
        verify_ref = task["inputs"].get("source_verify_ref")
        verify_data = None
        if not verify_ref:
            verify_data = self._find_dep_output(engine, task, "source_verify_output")
        if verify_ref:
            art = engine.db.get_artifact(verify_ref)
            if art:
                try:
                    with open(art["path"], encoding="utf-8") as fh:
                        verify_data = json.load(fh)
                except (OSError, json.JSONDecodeError):
                    pass
        if verify_data:
            for item in verify_data.get("credibility", []):
                grades[item.get("source", "")] = item.get("grade", "")

        # 2) 资料卡 → 证据条目
        cards_ref = task["inputs"].get("source_cards_ref")
        cards_data = None
        if not cards_ref:
            cards_data = self._find_dep_output(engine, task, "research_output")
        if cards_ref:
            art = engine.db.get_artifact(cards_ref)
            if art:
                try:
                    with open(art["path"], encoding="utf-8") as fh:
                        cards_data = json.load(fh)
                except (OSError, json.JSONDecodeError):
                    pass
        if cards_data:
            for card in cards_data.get("source_cards", []):
                source = card.get("origin", "")
                entries.append({
                    "source": source,
                    "source_type": _classify_source(source, rules),
                    "publication_date": card.get("publication_date"),
                    "reliability": grade_map.get(grades.get(source, ""), "medium"),
                    "excerpt": (card.get("quote") or card.get("summary") or "")[:500],
                    "url": card.get("url"),
                    "added_by": self.role,
                    # 资料卡是摘要级引用，未做逐条论证判断 → 仅算部分支持
                    "support_level": card.get("support_level", "PARTIAL_SUPPORT"),
                })

        # 3) 人工来源 → 证据条目（added_by=human 只说明来源由人工提供，
        #    不代表直接支持 Claim：support_level 必须显式标注，未标注=未评估(NULL)，
        #    由 fact_check 按未评估保守处理，不得因此提高核查结论）
        for manual in task["inputs"].get("manual_sources", []) or []:
            if not isinstance(manual, dict) or not manual.get("source"):
                continue
            entries.append({
                "source": manual["source"],
                "source_type": manual.get("source_type") or _classify_source(manual["source"], rules),
                "publication_date": manual.get("publication_date"),
                "reliability": manual.get("reliability", "unknown"),
                "excerpt": (manual.get("excerpt") or "")[:500],
                "url": manual.get("url"),
                "added_by": manual.get("added_by", "human"),
                "support_level": manual.get("support_level"),
            })

        # 4) 登记（同项目同来源去重）
        existing = {e["source"] for e in engine.db.list_evidence(project_id)}
        registered = []
        for entry in entries:
            if entry["source"] in existing:
                continue
            from ...core.ids import new_id
            evidence_id = new_id("e")
            engine.db.insert_evidence({**entry, "evidence_id": evidence_id,
                                       "project_id": project_id, "task_id": task["task_id"]})
            registered.append(evidence_id)
            existing.add(entry["source"])

        # 5) 关联到已有 claims（关键词重叠）
        linked = 0
        for claim in engine.db.list_claims(project_id):
            if claim["status"] in ("FALSE", "UNSUPPORTED"):
                continue
            for evidence_id in registered:
                ev = engine.db.get_evidence(evidence_id)
                if _overlap_score(claim["text"], f"{ev['source']} {ev['excerpt'] or ''}") > 0:
                    engine.db.link_claim_evidence(claim["claim_id"], evidence_id)
                    linked += 1
            n = len(engine.db.evidence_for_claim(claim["claim_id"]))
            if n != claim["source_count"]:
                engine.db.update_claim(claim["claim_id"], source_count=n)

        data = {
            "registered": registered,
            "linked_count": linked,
            "summary": f"证据登记 {len(registered)} 条，关联 {linked} 处",
            "confidence": 1.0,
            "note": "离线模式：仅资料卡/来源核查/人工来源；在线检索候选由 fact_check 阶段接入",
        }
        aid = engine.write_artifact(task["project_id"], task["task_id"], "evidence_index",
                                    data, summary=data["summary"])
        engine.attach_artifact(task["task_id"], aid)
        engine.db.update_task(task["task_id"], confidence=1.0)
        engine.emit(task["project_id"], "EVIDENCE_INDEXED", self.role, task["task_id"],
                    {"registered": len(registered), "linked": linked})

    @staticmethod
    def _find_dep_output(engine, task, artifact_type: str) -> dict | None:
        """pipeline 接入：从依赖任务产物中回退查找资料（research/source_verify）。"""
        for dep in task.get("dependencies", []):
            dep_task = engine.db.get_task(dep)
            if dep_task is None:
                continue
            for art_id in dep_task.get("artifacts", []):
                art = engine.db.get_artifact(art_id)
                if art and art["type"] == artifact_type:
                    try:
                        with open(art["path"], encoding="utf-8") as fh:
                            return json.load(fh)
                    except (OSError, json.JSONDecodeError):
                        return None
        return None
