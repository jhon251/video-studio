"""Skeptic / 抬杠 Agent（V2 升级，内部 role 保持 critic）。

- 定位：红队。假设其他 Agent 都错了，主动找问题；只质疑，不裁决事实。
- 质疑必须指向具体 claim_id（issues[].claim_ids），不做泛泛整篇评价。
- 7 类攻击维度：时间 / 人物机构名称 / 数字 / 因果关系 / 过度推断 / 标题说法vs原始事实 / AI 幻觉。
- 规则引擎生成确定性攻击（离线可用），LLM 挑战报告与其合并。
- 质疑绝不直接改变 claim 的 fact 结论——处置经 verdict（PASS/REWORK/BLOCK/NEED_EVIDENCE）
  由 Orchestrator 执行，事实裁决归 Human Review。
"""

from __future__ import annotations

import json
import re

from ..base import Agent, register

CHALLENGE_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["PASS", "REWORK", "BLOCK", "NEED_EVIDENCE"]},
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "severity": {"type": "string", "enum": ["fatal", "major", "minor"]},
                    "category": {"type": "string", "enum": [
                        # V2 新增 7 类攻击维度
                        "time", "entity", "number", "causality", "over_inference",
                        "headline_gap", "hallucination",
                        # V1 保留类别（向后兼容既有产物与 mock）
                        "logic", "fact", "source", "narrative", "omission", "bias",
                        "redundancy", "clickbait", "copyright", "echo"]},
                    "claim_ids": {"type": "array"},       # V2：质疑指向具体 claim
                    "claim": {"type": "string"},
                    "challenge": {"type": "string"},
                    "required_action": {"type": "string", "enum": [
                        "rewrite", "evidence", "rollback", "consult_human"]},
                },
                "required": ["severity", "category", "claim", "challenge", "required_action"],
            },
        },
        "meta_note": {"type": "string"},
        "summary": {"type": "string"},
        "confidence": {"type": "number"},
        "note": {"type": "string"},
    },
    "required": ["verdict", "issues", "summary"],
}

_DIGIT = re.compile(r"\d{4}\s*年|\d+\s*例|\d+\s*个|\d+\s*亿|\d+\s*%")
_ENTITY = ("公司", "大学", "团队", "机构", "法院", "国家", "宪法", "医院", "研究院", "实验室")


@register
class CriticAgent(Agent):
    role = "critic"
    tier = "R"
    description = "Skeptic / 抬杠 Agent：红队式质疑，7 类攻击指向具体 claim；只找问题不裁决事实。"
    system_prompt = (
        "你是视频生产团队里的专职反对者（Skeptic / 抬杠 Agent），是系统的红队。"
        "假设其他 Agent 都错了，主动寻找：时间错误、人物/公司/机构名称错误、数字错误、"
        "因果关系错误、过度推断、'新闻标题说法'与'原始事实'的差异、AI 生成内容的幻觉。"
        "每条质疑必须指向具体 claim_id（issues[].claim_ids），不要泛泛评价整篇文案。"
        "你只产出挑战报告，绝不修改产物，绝不裁决事实真假——你的质疑不能直接改变任何"
        "claim 的事实结论。verdict 取值：PASS / REWORK（要求重做）/ BLOCK（拦截）/ "
        "NEED_EVIDENCE（要求补证据）。输出严格 JSON。"
    )
    output_schema = CHALLENGE_SCHEMA

    def run(self, engine, task: dict) -> None:
        super().run(engine, task)
        task = engine.db.get_task(task["task_id"])  # 重读产物列表
        artifact_id = task["artifacts"][-1]
        art = engine.db.get_artifact(artifact_id)
        with open(art["path"], encoding="utf-8") as fh:
            report = json.load(fh)

        # ---- V2：规则引擎确定性攻击（指向 claim_id），与 LLM 报告合并 ----
        rule_issues = self._rule_attacks(engine, task)
        if rule_issues:
            report.setdefault("issues", [])
            report["issues"].extend(rule_issues)
            report["summary"] = (report.get("summary", "") +
                                 f"（规则攻击 {len(rule_issues)} 条）").strip()
            art_path = art["path"]
            with open(art_path, "w", encoding="utf-8") as fh:
                json.dump(report, fh, ensure_ascii=False, indent=2)

        verdict = report.get("verdict", "PASS")
        target_refs = task["inputs"].get("target_artifacts", [])
        # V2 第五阶段：Skeptic 判定存在重大风险（fatal）→ 强制人工审核该 Claim。
        # 注意：只路由人工（status=NEEDS_HUMAN），绝不改变 claim 的 fact 结论。
        fatal_claim_ids = set()
        for issue in report.get("issues", []):
            if issue.get("severity") != "fatal":
                continue
            for cid in issue.get("claim_ids") or []:
                if engine.db.get_claim(cid) is not None:
                    fatal_claim_ids.add(cid)
        for cid in fatal_claim_ids:
            engine.db.update_claim(cid, human_review_required=True, status="NEEDS_HUMAN")
            engine.emit(task["project_id"], "SKEPTIC_FLAGGED", "critic", task["task_id"],
                        {"claim_id": cid, "severity": "fatal"}, human_visible=True)
        engine.emit(task["project_id"], "CHALLENGE_RAISED", "critic", task["task_id"],
                    {"verdict": verdict, "targets": target_refs,
                     "rule_attack_count": len(rule_issues)}, human_visible=True)
        if verdict == "BLOCK":
            for ref in target_refs:
                art2 = engine.db.get_artifact(ref)
                if art2 and art2["task_id"]:
                    engine.db.set_task_status(art2["task_id"], "BLOCKED",
                                              f"Critic BLOCK: {report.get('summary', '')[:200]}")
        elif verdict == "REWORK":
            target_task = None
            for ref in target_refs:
                art2 = engine.db.get_artifact(ref)
                if art2 and art2["task_id"]:
                    target_task = engine.db.get_task(art2["task_id"])
                    break
            if target_task is not None:
                engine.emit(task["project_id"], "TASK_ROLLED_BACK", "critic", target_task["task_id"],
                            {"reason": report.get("summary", "")[:200]})
                engine.rollback_to(target_task["task_id"])
        # NEED_EVIDENCE：不在此直接处置（第五阶段管线将触发证据补查任务）
        # 重要：任何 verdict 都不改变 claim 的 fact 结论

    def _rule_attacks(self, engine, task: dict) -> list[dict]:
        """基于 claim 数据的确定性攻击：保证离线可运行、质疑必有 claim_id 指向。"""
        project_id = task["project_id"]
        claim_ids = task["inputs"].get("target_claim_ids") or []
        if not claim_ids:
            claim_ids = [c["claim_id"] for c in engine.db.list_claims(project_id)]
        attacks = []
        for cid in claim_ids:
            claim = engine.db.get_claim(cid)
            if claim is None:
                continue
            text, risk, ctype = claim["text"], claim["risk"], claim["type"]
            evs = engine.db.evidence_for_claim(cid)
            if risk == "CRITICAL":
                attacks.append(self._issue(
                    "major", "over_inference", cid, text,
                    "绝对化表述（'第一/唯一/首次'类）属于最高风险断言",
                    "evidence", "请提供原始来源逐字佐证"))
            if not evs and risk in ("HIGH", "CRITICAL"):
                attacks.append(self._issue(
                    "major", "hallucination", cid, text,
                    "该断言目前没有任何证据支撑",
                    "evidence", "怀疑为无来源陈述，需要证据或来源补全"))
            if ctype == "PREDICTION" and risk == "CRITICAL":
                attacks.append(self._issue(
                    "major", "over_inference", cid, text,
                    "预测性结论与绝对化措辞混用，可能被观众当作已发生事实",
                    "consult_human", "建议人工复核表述边界"))
            if _DIGIT.search(text) and risk in ("HIGH", "CRITICAL"):
                attacks.append(self._issue(
                    "minor", "number", cid, text,
                    "含具体数字/年份，需与原始来源逐字核对",
                    "evidence", "请核对数字与来源一致性"))
            if (any(s in text for s in _ENTITY) or re.search(r"[A-Z][a-zA-Z]{2,}", text)) \
                    and risk in ("HIGH", "CRITICAL"):
                attacks.append(self._issue(
                    "minor", "entity", cid, text,
                    "含机构/组织名称，拼写与性质（官方/媒体/企业）需核实",
                    "evidence", "请核对名称与来源归属"))
        return attacks

    @staticmethod
    def _issue(severity, category, cid, text, claim_desc, action, challenge) -> dict:
        return {
            "severity": severity,
            "category": category,
            "claim_ids": [cid],
            "claim": f"[{cid}] {text[:60]}",
            "challenge": f"{claim_desc}。{challenge}。",
            "required_action": action,
        }
