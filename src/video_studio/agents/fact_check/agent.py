"""Fact Checker Agent（V2 升级）：逐 Claim 核查，证据驱动，离线可运行。

原则（不可违反）：
- 没有足够证据 → Unsupported（或其他不确定状态），绝不推断为 Confirmed，绝不乱判 False
- False 仅在"显式矛盾证据"（人工标注或高可靠来源直接否定）时标记，且必走人工
- 可靠性等级差 ≥2 只作为"潜在冲突"触发人工提示，不等同事实本身存在矛盾
- 搜索结果只是候选：经 Search → Fetch → Extract → Classify 后才可进入证据库
- 人工来源（added_by=human）只代表来源提供方，不等于支持关系：support_level 必须显式评估，
  未评估（NULL）按保守处理（UNEVALUATED_MANUAL），不得据此提高核查结论
- PREDICTION/OPINION/INFERENCE/UNKNOWN 按各自类型核查，不按"找不到来源"判错
- 科技/医疗/历史/法规领域的逻辑跳跃（新闻≠实现、宣传≠验证、论文≠商业化等）专项检查
- Agent 只产出判断建议；最终事实裁决权属于人类
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from ..base import Agent, register
from ...tools.search_provider import EvidenceCandidate, resolve_provider, OfflineProvider

RULES_PATH = Path(__file__).resolve().parents[4] / "config" / "factcheck_rules.json"
CONTRADICT_PREFIX = "【矛盾证据】"
REL_ORDER = {"high": 3, "medium": 2, "low": 1, "unknown": 0}

# 逻辑跳跃检查对：(信号A, 信号B, 风险说明)。A 与 B 同时出现即标记，需人工复核。
LOGIC_JUMPS = [
    ("报道", "已经实现", "新闻报道 ≠ 已经实现"),
    ("新闻", "已经实现", "新闻报道 ≠ 已经实现"),
    ("宣称", "实现", "企业宣传 ≠ 独立验证"),
    ("论文", "商业化", "论文 ≠ 已经商业化"),
    ("临床试验", "大规模应用", "临床试验 ≠ 大规模应用"),
    ("专利", "已经实现", "专利 ≠ 已经实现"),
    ("正在研发", "即将上市", "'正在研发' ≠ '即将上市'"),
    ("实验室", "商业产品", "实验室成果 ≠ 商业产品"),
    # V2.0 后补（用户指定）：科普类逻辑推导的确定性检测
    ("接线图", "不是意识", "「接线图≠意识」属推断表述，需标注为推断而非事实"),
    ("基本共识", "记忆", "「基本共识」为强表述，需核对是否学界普遍共识而非学派观点"),
    ("功耗", "小城", "「人脑功耗→一座小城」为估算性类比，需标注为估算而非测量事实"),
]


def _load_rules() -> dict:
    try:
        return json.loads(RULES_PATH.read_text(encoding="utf-8"))
    except OSError:
        return {}


def _classify_source(source: str, rules: dict) -> str:
    for s_type, words in rules.get("source_type_hints", {}).items():
        if any(w in source for w in words):
            return s_type
    return "unknown"


@register
class FactCheckAgent(Agent):
    role = "fact_check"
    tier = "R"
    needs_llm = False       # 规则引擎核查，保证离线确定性；LLM 复核为后续增强钩子
    description = "事实核查员：逐 Claim 找证据、给判断建议（结论只建议，最终裁决归人类）。"

    def run(self, engine, task: dict) -> None:
        rules = _load_rules()
        project_id = task["project_id"]
        claim_ids = task["inputs"].get("claim_ids") or []
        if not claim_ids:
            claim_ids = [c["claim_id"] for c in engine.db.list_claims(project_id)]

        provider = resolve_provider(engine.config)
        online = not isinstance(provider, OfflineProvider)
        provider_note = ("在线检索" if online else
                         "离线模式（无搜索 Key/未配置 provider，仅资料库与人工来源）")
        records = []

        for cid in claim_ids:
            claim = engine.db.get_claim(cid)
            if claim is None:
                continue
            records.append(self._check_claim(engine, task, claim, provider, online, rules))

        human_count = sum(1 for r in records if r["human_review_required"])
        verified = sum(1 for r in records if r["conclusion"] in ("Confirmed", "Mostly Confirmed"))
        data = {
            "checks": records,
            "provider": provider.name,
            "provider_note": provider_note,
            "summary": (f"核查 {len(records)} 条：Confirmed/Mostly {verified} 条，"
                        f"需人工 {human_count} 条（{provider_note}）"),
            "confidence": 1.0,
            "note": "结论为判断建议；人工审核后经 decide_claim 闭环（第五阶段）",
        }
        aid = engine.write_artifact(task["project_id"], task["task_id"], "claim_verification",
                                    data, summary=data["summary"])
        engine.attach_artifact(task["task_id"], aid)
        engine.db.update_task(task["task_id"], confidence=1.0)
        engine.emit(project_id, "CLAIMS_VERIFIED", self.role, task["task_id"],
                    {"checked": len(records), "human_flagged": human_count,
                     "provider": provider.name},
                    human_visible=human_count > 0)

    # ---------------- 单条核查 ----------------
    def _check_claim(self, engine, task, claim: dict, provider, online: bool, rules: dict) -> dict:
        cid = claim["claim_id"]

        # 非 FACT 类型：按类型核查
        if claim["type"] != "FACT":
            return self._check_non_fact(engine, task, claim)

        evs = engine.db.evidence_for_claim(cid)
        stats = None

        # 在线检索补充证据（搜索结果只作候选：预筛+fetch+讨论级提取通过才入库）
        if not evs and online:
            evs, stats = self._online_gather(engine, task, claim, provider, rules)

        conflicts = [c for c in engine.db.list_conflicts(claim["project_id"])
                     if c["claim_id"] == cid]
        # CONTRADICTS：支持关系上的反驳信号（旧【矛盾证据】前缀约定兼容保留）
        contradict = [e for e in evs
                      if (e.get("excerpt") or "").startswith(CONTRADICT_PREFIX)
                      or e.get("support_level") == "CONTRADICTS"]
        # 可用证据：只有 DIRECT / PARTIAL 参与结论综合；CONTEXT_ONLY/IRRELEVANT 不入库；
        # support_level 为 NULL = 未评估（added_by=human 不等于 DIRECT_SUPPORT），不得参与综合
        usable = [e for e in evs if e.get("support_level") in ("DIRECT_SUPPORT", "PARTIAL_SUPPORT")]
        unevaluated = [e for e in evs if not (e.get("support_level") or "").strip()]
        direct = [e for e in usable if e.get("support_level") == "DIRECT_SUPPORT"]
        strong = [e for e in direct if e["source_type"] in ("official", "academic")
                  and e["reliability"] == "high"]
        high = [e for e in usable if e["reliability"] == "high"]

        reasoning_parts, human = [], False
        verification_path = "DIRECT_SUPPORT" if direct else None

        # 1) 反驳性证据 → Disputed（禁止 CONTRADICTS→自动 False；是否 False 由人工裁决）
        if contradict:
            conclusion, confidence = "Disputed", "Medium"
            human = True
            verification_path = "CONTRADICTS"
            reasoning_parts.append("存在反驳性证据，不自动判 False，交人工定案")
        # 2) 已登记来源冲突 → Disputed（不裁决，交人工）
        elif conflicts:
            conclusion, confidence = "Disputed", "Medium"
            human = True
            verification_path = "CONFLICT"
            reasoning_parts.append("来源冲突已由冲突检测器登记，不自动裁决")
        # 3) 无可用证据 → Unsupported（绝不推断 Confirmed、绝不乱判 False；原因如实区分）
        elif not usable:
            conclusion, confidence = "Unsupported", "Low"
            human = True
            if evs and len(unevaluated) == len(evs):
                # 人工来源未评估支持关系：有来源 ≠ 有支持，不得因 added_by=human 提高结论
                verification_path = "UNEVALUATED_MANUAL"
                reasoning_parts.append(
                    "人工来源未评估支持关系（added_by=human 不等于 DIRECT_SUPPORT），"
                    "需按 reliability + relevance + support_level 人工判定")
            else:
                verification_path = self._no_evidence_path(stats, online)
                reasoning_parts.append(f"未找到可用证据（{verification_path}）")
                reasoning_parts.append("缺乏原始来源，需人工提供或确认")
        else:
            rels = [REL_ORDER.get(e["reliability"], 0) for e in usable]
            gap = max(rels) - min(rels)
            # 4) 可靠性差≥2：仅作潜在冲突提示，不等同事实矛盾，不自动裁决
            if gap >= 2 and not high:
                conclusion, confidence = "Unsupported", "Low"
                human = True
                verification_path = "RELIABILITY_GAP"
                reasoning_parts.append("证据可靠性普遍偏低（潜在冲突：仅提示，不等同事实矛盾）")
            elif gap >= 2:
                conclusion, confidence = "Mostly Confirmed", "Medium"
                human = True
                verification_path = "RELIABILITY_GAP"
                reasoning_parts.append("证据间存在可靠性差异（潜在冲突：仅提示，不等同事实矛盾）")
            else:
                # 5) 综合判断（support_level 只描述支持关系，结论由多因素综合）：
                #    support + reliability + source_count + diversity + type + risk
                diversity = len({e["source"] for e in usable})
                if direct and (strong or len(direct) >= 2 or (diversity >= 2 and high)):
                    conclusion, confidence = "Confirmed", "High" if high else "Medium"
                    verification_path = "DIRECT_SUPPORT"
                    reasoning_parts.append(f"{len(usable)} 条证据互相支持（direct {len(direct)}）"
                                           + ("，含官方/学术来源" if strong else ""))
                else:
                    conclusion, confidence = "Mostly Confirmed", "Medium"
                    verification_path = "PARTIAL_SUPPORT"
                    if not direct:
                        reasoning_parts.append("证据仅部分支持（PARTIAL_SUPPORT）")
                    # 不因搜索到证据就自动绕过 HIGH/CRITICAL 人工闸门
                    if claim["risk"] == "HIGH" and not direct:
                        human = True
                        reasoning_parts.append("HIGH 风险且仅有部分支持证据，保留人工审核")
                    if claim["risk"] == "CRITICAL" and not strong:
                        human = True
                        reasoning_parts.append("CRITICAL 绝对化表述缺乏强原始来源，需人工确认")

        # 7) 科技/医疗/历史/法规逻辑跳跃检查
        for sig_a, sig_b, warn in LOGIC_JUMPS:
            if sig_a in claim["text"] and sig_b in claim["text"]:
                human = True
                reasoning_parts.append(f"逻辑跳跃风险：{warn}")

        # 8) CRITICAL 一律保留人工入口
        if claim["risk"] == "CRITICAL" and not human and claim["type"] == "FACT":
            human = True
            reasoning_parts.append("CRITICAL 风险声明保留人工审核入口")

        status = "NEEDS_HUMAN" if human else ("UNSUPPORTED" if conclusion == "Unsupported"
                                              else ("DISPUTED" if conclusion == "Disputed" else "VERIFIED"))
        engine.db.update_claim(cid, status=status, conclusion=conclusion,
                               confidence=confidence,
                               source_count=len(evs),
                               human_review_required=human)
        return {
            "claim_id": cid,
            "conclusion": conclusion,
            "confidence": confidence,
            "evidence_refs": [e["evidence_id"] for e in evs],
            "reasoning": "；".join(reasoning_parts),
            "human_review_required": human,
            "verification_path": verification_path,
            "search_stats": stats,
        }

    @staticmethod
    def _no_evidence_path(stats: dict | None, online: bool) -> str:
        """区分"搜不到"与"没有证据"：SEARCH_FAILED / FETCH_FAILED /
        NO_RELEVANT_RESULT / NO_RELIABLE_SOURCE / INSUFFICIENT_EVIDENCE。"""
        if not online:
            return "NO_RELIABLE_SOURCE"
        if stats is None:
            return "NO_RELIABLE_SOURCE"
        if stats.get("search_failed") and stats.get("search_results", 0) == 0:
            return "SEARCH_FAILED"
        if stats.get("relevant", 0) == 0:
            return "NO_RELEVANT_RESULT"
        if stats.get("fetched", 0) == 0:
            return "FETCH_FAILED"
        if stats.get("usable", 0) == 0:
            return "INSUFFICIENT_EVIDENCE"
        return "NO_RELIABLE_SOURCE"

    def _check_non_fact(self, engine, task, claim: dict) -> dict:
        cid = claim["claim_id"]
        ctype = claim["type"]
        human = False
        if ctype == "PREDICTION":
            conclusion, confidence = "Mostly Confirmed", "Medium"
            reasoning = "按 PREDICTION 类型核查：预测性陈述，不适用事实来源判定"
            if claim["risk"] == "CRITICAL":
                human = True
                reasoning += "；预测与绝对化表述混用，需人工复核"
        elif ctype == "OPINION":
            conclusion, confidence = "Mostly Confirmed", "Low"
            reasoning = "按 OPINION 类型核查：观点类陈述，无需事实来源，不判对错"
        elif ctype == "INFERENCE":
            evs = engine.db.evidence_for_claim(cid)
            if evs:
                conclusion, confidence = "Mostly Confirmed", "Medium"
                reasoning = "按 INFERENCE 类型核查：推论存在前提证据"
            else:
                conclusion, confidence = "Unsupported", "Low"
                reasoning = "按 INFERENCE 类型核查：推论未找到前提证据（不判 False，仅标注）"
                human = claim["risk"] in ("HIGH", "CRITICAL")
        else:  # UNKNOWN
            conclusion, confidence = None, None
            reasoning = "按 UNKNOWN 类型核查：保留未知状态，不强行下结论"
        status = "NEEDS_HUMAN" if human else ("UNSUPPORTED" if conclusion == "Unsupported" else "VERIFIED")
        engine.db.update_claim(cid, status=status, conclusion=conclusion,
                               confidence=confidence, human_review_required=human)
        return {
            "claim_id": cid,
            "conclusion": conclusion,
            "confidence": confidence,
            "evidence_refs": [e["evidence_id"] for e in engine.db.evidence_for_claim(cid)],
            "reasoning": reasoning,
            "human_review_required": human,
            "verification_path": "TYPE_CHECKED",
        }

    def _online_gather(self, engine, task, claim: dict, provider, rules: dict) -> tuple[list[dict], dict]:
        """Search → Fetch → Extract → Classify 后登记证据并关联；任何异常降级离线。"""
        from ...core.ids import new_id
        # 精简关键词查询（数字/英文/中文词元，保序去重，前 8 个），提高检索相关性
        import re as _re
        tokens = list(dict.fromkeys(
            _re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z]{2,}|\d+", claim["text"])))[:8]
        query = " ".join(tokens) or claim["text"]
        # 回退链：主 provider 无结果时自动切 bing（免密钥双通道）
        from ...tools.search_provider import REGISTRY
        chain = [provider]
        if provider.name != "bing" and "bing" in REGISTRY:
            chain.append(REGISTRY["bing"])
        results, active = [], provider
        search_failed = 0
        chain_attempts = []          # 纯日志：逐 provider 尝试记录（不参与任何结论判定）
        for p in chain:
            try:
                got = p.search(query, max_results=3)
                chain_attempts.append({"provider": p.name, "results": len(got), "error": False})
                if got:
                    results, active = got, p
                    break
            except Exception:
                search_failed += 1
                chain_attempts.append({"provider": p.name, "results": 0, "error": True})
                continue
        stats = {
            "query": query, "provider": active.name, "chain": [p.name for p in chain],
            "chain_attempts": chain_attempts,
            "fell_back": 1 if active is not provider else 0,  # 纯日志：结果是否来自回退 provider
            "search_results": len(results), "search_failed": search_failed,
            "relevant": 0, "fetched": 0, "usable": 0, "rejected": {},
        }
        # 质量预过滤：URL/黑名单/关键词预筛（仅候选筛选，不证明语义支持）
        from ...tools.search_provider import filter_candidates, order_candidates
        q_rules = self._quality_rules()
        kept, rejected = filter_candidates(results, claim, q_rules)
        stats["rejected"].update(rejected)
        kept = order_candidates(kept, claim, q_rules)
        stats["relevant"] = len(kept)

        added = []
        for sr in kept[:3]:
            try:
                page = active.fetch(sr.url)
                if not page.ok:
                    stats["rejected"]["FETCH_FAILED"] = stats["rejected"].get("FETCH_FAILED", 0) + 1
                    continue
                stats["fetched"] += 1
                cand = active.extract_evidence(page, claim)
                if cand is None or not (cand.excerpt or "").strip():
                    stats["rejected"]["IRRELEVANT"] = stats["rejected"].get("IRRELEVANT", 0) + 1
                    continue
            except Exception:
                stats["rejected"]["EXCEPTION"] = stats["rejected"].get("EXCEPTION", 0) + 1
                continue
            level = cand.support_level or "DIRECT_SUPPORT"
            if level in ("CONTEXT_ONLY", "IRRELEVANT"):
                # 仅个别词出现/不构成讨论 → 不入库（讨论级判断门槛）
                stats["rejected"]["CONTEXT_ONLY"] = stats["rejected"].get("CONTEXT_ONLY", 0) + 1
                continue
            source = cand.source or sr.title or sr.url
            existing = {e["source"] for e in engine.db.list_evidence(claim["project_id"])}
            if source in existing:
                stats["rejected"]["DUPLICATE"] = stats["rejected"].get("DUPLICATE", 0) + 1
                continue
            evidence_id = new_id("e")
            excerpt = cand.excerpt
            if cand.contradicts and not excerpt.startswith(CONTRADICT_PREFIX):
                excerpt = CONTRADICT_PREFIX + excerpt
            engine.db.insert_evidence({
                "evidence_id": evidence_id, "project_id": claim["project_id"],
                "source": source,
                "source_type": cand.source_type or _classify_source(source, rules),
                "publication_date": cand.publication_date,
                "reliability": cand.reliability or "unknown",
                "excerpt": excerpt[:500], "url": sr.url,
                "added_by": self.role, "task_id": task["task_id"],
                "support_level": level,
            })
            engine.db.link_claim_evidence(claim["claim_id"], evidence_id)
            added.append(evidence_id)
            stats["usable"] += 1
        # 搜索日志：可追溯到具体 claim_id
        engine.emit(claim["project_id"], "SEARCH_EVIDENCE", self.role, task["task_id"],
                    {"claim_id": claim["claim_id"], **stats})
        return engine.db.evidence_for_claim(claim["claim_id"]), stats

    @staticmethod
    def _quality_rules() -> dict:
        import json
        from pathlib import Path
        try:
            return json.loads((Path(__file__).resolve().parents[4]
                               / "config" / "search_quality.json").read_text(encoding="utf-8"))
        except OSError:
            return {}
