"""HITL 审批服务：6 个强制闸门（topic/structure/script/materials/final_cut/publish）。

流程：任务产出后置 NEEDS_REVIEW → 人工三选一（Approve / Reject / Modify）
→ 写入 DecisionRecord 永久留痕 → 由 Engine.approve 推进状态机。
"""

from __future__ import annotations

from ..core.ids import new_id


class HITL:
    def __init__(self, engine, config: dict):
        self.engine = engine
        self.gates = set(config.get("hitl", {}).get("gates", []))
        self.auto_approve = config.get("hitl", {}).get("auto_approve", False)

    def is_gate(self, task_type: str) -> bool:
        return task_type in self.gates

    def pending_reviews(self, project_id: str) -> list[dict]:
        return [t for t in self.engine.db.list_tasks(project_id, "NEEDS_REVIEW")]

    def decide(self, task_id: str, state: str, comment: str = "") -> None:
        """state: approve | reject | modify"""
        state_map = {"approve": "APPROVED", "reject": "REJECTED", "modify": "CHANGES_REQUESTED"}
        if state not in state_map:
            raise ValueError(f"state 必须是 {list(state_map)} 之一")
        self.engine.approve(task_id, state_map[state], comment)

    # ============ V2：Claim 级人工审核闭环 ============

    def pending_claims(self, project_id: str) -> list[dict]:
        """待人工审核的 Claim 列表。"""
        return self.engine.db.list_claims(project_id, "NEEDS_HUMAN")

    def claim_context(self, claim_id: str) -> dict:
        """查看：Claim + 证据 + 冲突 + Skeptic 质疑 + 核查结论。"""
        engine, db = self.engine, self.engine.db
        claim = db.get_claim(claim_id)
        if claim is None:
            return {"claim_id": claim_id, "found": False}
        evidence = db.evidence_for_claim(claim_id)
        conflicts = [c for c in db.list_conflicts(claim["project_id"])
                     if c["claim_id"] == claim_id]
        # Skeptic 质疑：扫描 critic 产物中指向该 claim 的 issues
        skeptic_issues = []
        for t in db.list_tasks(claim["project_id"]):
            if t["agent_role"] != "critic":
                continue
            for art_id in t["artifacts"]:
                art = db.get_artifact(art_id)
                if art is None:
                    continue
                try:
                    with open(art["path"], encoding="utf-8") as fh:
                        import json as _json
                        report = _json.load(fh)
                    for issue in report.get("issues", []):
                        if claim_id in (issue.get("claim_ids") or []):
                            skeptic_issues.append(issue)
                except (OSError, ValueError):
                    pass
        # 核查结论：fact_check 产物中对应记录
        verification = None
        for t in db.list_tasks(claim["project_id"]):
            if t["agent_role"] != "fact_check":
                continue
            for art_id in t["artifacts"]:
                art = db.get_artifact(art_id)
                if art is None:
                    continue
                try:
                    with open(art["path"], encoding="utf-8") as fh:
                        import json as _json
                        for record in _json.load(fh).get("checks", []):
                            if record.get("claim_id") == claim_id:
                                verification = record
                except (OSError, ValueError):
                    pass
        return {
            "claim": claim,
            "evidence": evidence,
            "conflicts": conflicts,
            "skeptic_issues": skeptic_issues,
            "verification": verification,
        }

    def decide_claim(self, claim_id: str, decision: str, comment: str = "",
                     revised_text: str | None = None) -> dict:
        """decision: approve | reject | revise。

        approve → VERIFIED；reject → REJECTED 并重做 script+重建提取链（回到 script/verification）；
        revise → 更新文本回 UNVERIFIED 并重做 fact_check（重新核查）。
        全部决策写入 decisions 与 changelog（human_confirmed=true）。"""
        engine, db = self.engine, self.engine.db
        claim = db.get_claim(claim_id)
        if claim is None:
            raise ValueError(f"claim 不存在: {claim_id}")
        project_id = claim["project_id"]
        before_status = claim["status"]

        if decision == "approve":
            db.update_claim(claim_id, status="VERIFIED", human_review_required=False)
            after_status = "VERIFIED"
            reason = comment or "人工批准该声明"
            db.insert_decision({"decision_id": new_id("d"), "project_id": project_id,
                                "node": f"claim_{claim_id}", "made_by": "human",
                                "state": "APPROVED", "rationale": reason})
            db.insert_changelog(project_id, "claim", claim_id, "human", reason,
                                before_status, after_status, human_confirmed=True)
        elif decision == "reject":
            db.update_claim(claim_id, status="REJECTED", human_review_required=False)
            after_status = "REJECTED"
            reason = comment or "人工驳回该声明"
            db.insert_decision({"decision_id": new_id("d"), "project_id": project_id,
                                "node": f"claim_{claim_id}", "made_by": "human",
                                "state": "REJECTED", "rationale": reason})
            db.insert_changelog(project_id, "claim", claim_id, "human", reason,
                                before_status, after_status, human_confirmed=True)
            # 回到 script：重做脚本任务 + 重建声明提取链
            script_task = self._latest_task(project_id, "script")
            if script_task is not None:
                new_script = engine.redo(script_task["task_id"])
                engine.create_task(project_id, "claim_extract", "claim_extractor",
                                   dependencies=[new_script],
                                   inputs={"phase": "p2b_verification"})
        elif decision == "revise":
            if not revised_text or not revised_text.strip():
                raise ValueError("revise 需要 --text 提供修订后的表述")
            db.update_claim(claim_id, text=revised_text.strip(), status="UNVERIFIED",
                            human_review_required=False)
            after_status = "UNVERIFIED"
            reason = comment or "人工修订表述，需重新核查"
            db.insert_decision({"decision_id": new_id("d"), "project_id": project_id,
                                "node": f"claim_{claim_id}", "made_by": "human",
                                "state": "CHANGES_REQUESTED", "rationale": reason})
            db.insert_changelog(project_id, "claim", claim_id, "human", reason,
                                f"text={claim['text'][:60]}", f"text={revised_text.strip()[:60]}",
                                human_confirmed=True)
            # 重新核查：重做 fact_check 任务
            fc_task = self._latest_task(project_id, "fact_check")
            if fc_task is not None:
                engine.redo(fc_task["task_id"])
        else:
            raise ValueError("decision 必须是 approve | reject | revise")

        engine.emit(project_id, "CLAIM_REVIEWED", "human", None,
                    {"claim_id": claim_id, "decision": decision}, human_visible=True)
        return {"claim_id": claim_id, "decision": decision, "before": before_status,
                "after": after_status}

    def _latest_task(self, project_id: str, task_type: str) -> dict | None:
        tasks = [t for t in self.engine.db.list_tasks(project_id)
                 if t["task_type"] == task_type]
        return tasks[-1] if tasks else None
