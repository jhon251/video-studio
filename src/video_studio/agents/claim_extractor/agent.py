"""Claim Extractor Agent：从文案中提取可核查的事实声明并结构化入库。

- 支持两条路径：文案已带 [CLAIM:xxx] 标记（沿用原 id 索引）；未带标记（规则切句+提取+标注）
- 规则引擎为核心（绝对化表述/风险分级/类型分类），离线可运行；LLM 复核由
  config/factcheck_rules.json 的 llm_assist 开关控制（默认关闭，后续阶段可开）
- 产出：claims 表 + claims_map 产物 + 内部标注稿（script_internal）
- 事件：CLAIMS_EXTRACTED（有 CRITICAL 时 human_visible）
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from ..base import Agent, register

RULES_PATH = Path(__file__).resolve().parents[4] / "config" / "factcheck_rules.json"
SENT_SPLIT = re.compile(r"[。！？!?；;]")
MARKER = re.compile(r"\[CLAIM:([A-Za-z0-9_\-]+)\]")


def load_rules() -> dict:
    try:
        return json.loads(RULES_PATH.read_text(encoding="utf-8"))
    except OSError:
        return {}


def _sentence_claims(narration: str) -> list[str]:
    """按句号/问号等切句，保留含可核查内容的句子。"""
    parts = SENT_SPLIT.split(narration)
    return [p.strip() for p in parts if len(p.strip()) >= 8]


def _classify(text: str, rules: dict) -> tuple[str, str, list[str]]:
    """返回 (type, risk, markers)。规则分级：
    CRITICAL：绝对化表述；HIGH：年份/数字/机构；MEDIUM：长陈述；LOW：普通描述。"""
    absolute = [w for w in rules.get("absolute_words", []) if w in text]
    if any(m in text for m in rules.get("prediction_markers", [])):
        ctype = "PREDICTION"
    elif any(m in text for m in rules.get("opinion_markers", [])):
        ctype = "OPINION"
    elif any(m in text for m in rules.get("unknown_markers", [])):
        ctype = "UNKNOWN"
    elif any(m in text for m in rules.get("inference_markers", [])):
        ctype = "INFERENCE"
    else:
        ctype = "FACT"
    if absolute:
        risk = "CRITICAL"
    elif any(re.search(p, text) for p in rules.get("high_risk_patterns", [])) \
            or any(s in text for s in rules.get("entity_suffixes", [])):
        risk = "HIGH"
    elif len(text) >= 20:
        risk = "MEDIUM"
    else:
        risk = "LOW"
    return ctype, risk, absolute


@register
class ClaimExtractorAgent(Agent):
    role = "claim_extractor"
    tier = "M"
    needs_llm = False
    description = "声明提取：从文案拆出可核查断言，类型/风险分级，识别绝对化表述。"

    def run(self, engine, task: dict) -> None:
        rules = load_rules()
        project_id = task["project_id"]
        script = self._load_script(engine, task)

        if script is None:
            data = {"claims": [], "summary": "未找到脚本产物，跳过提取", "confidence": 1.0,
                    "note": "script_ref 引用缺失"}
            self._finish(engine, task, data, critical=0)
            return

        segments = script.get("segments", [])
        # 全局计数保证 claim_id 跨项目唯一（主键为全局唯一；项目内序号会撞号）
        base = engine.db.conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0]
        seq = base + 1
        claims = []
        internal_segments = []
        for seg in segments:
            narration = seg.get("narration", "")
            if not isinstance(narration, str) or not narration.strip():
                internal_segments.append(seg)
                continue
            marked_ids = MARKER.findall(narration)
            if marked_ids:
                # 已带标记：按原 id 索引整段（标记归属的句子为 claim 文本）
                for raw_cid in marked_ids:
                    cid = raw_cid if str(raw_cid).startswith("c_") else f"c_{raw_cid}"
                    # 跨项目标记撞号防御：已占用则加项目后缀去重
                    if engine.db.get_claim(cid) is not None:
                        cid = f"{cid}_p{project_id[2:8]}"
                    snippet = self._text_around_marker(narration, cid)
                    ctype, risk, abs_words = _classify(snippet, rules)
                    claim = {
                        "claim_id": cid, "project_id": project_id, "task_id": task["task_id"],
                        "segment_ref": seg.get("chapter", ""), "text": snippet,
                        "type": ctype, "risk": risk, "markers": abs_words,
                        "status": "UNVERIFIED",
                        "human_review_required": risk == "CRITICAL",
                    }
                    engine.db.insert_claim(claim)
                    claims.append({k: v for k, v in claim.items()
                                   if k not in ("project_id", "task_id", "status")})
                internal_segments.append(seg)
                continue
            # 未带标记：切句提取 + 生成内部标注稿
            marked_narration = narration
            for sentence in _sentence_claims(narration):
                ctype, risk, abs_words = _classify(sentence, rules)
                cid = f"c_{seq:03d}"
                seq += 1
                claim = {
                    "claim_id": cid, "project_id": project_id, "task_id": task["task_id"],
                    "segment_ref": seg.get("chapter", ""), "text": sentence,
                    "type": ctype, "risk": risk, "markers": abs_words,
                    "status": "UNVERIFIED",
                    "human_review_required": risk == "CRITICAL",
                }
                engine.db.insert_claim(claim)
                claims.append({k: v for k, v in claim.items()
                               if k not in ("project_id", "task_id", "status")})
                marked_narration = marked_narration.replace(
                    sentence, f"[CLAIM:{cid}]{sentence}", 1)
            internal_segments.append({**seg, "narration": marked_narration})

        critical = sum(1 for c in claims if c["risk"] == "CRITICAL")
        data = {
            "claims": claims,
            "segments_internal": internal_segments,
            "summary": f"提取 {len(claims)} 条声明（CRITICAL {critical} 条）",
            "confidence": 1.0,
            "note": "规则引擎提取；llm_assist 开关控制 LLM 复核",
        }
        self._finish(engine, task, data, critical=critical)

    def _finish(self, engine, task, data: dict, critical: int) -> None:
        aid = engine.write_artifact(task["project_id"], task["task_id"], "claims_map",
                                    data, summary=data["summary"])
        engine.attach_artifact(task["task_id"], aid)
        engine.db.update_task(task["task_id"], confidence=data.get("confidence", 1.0))
        engine.emit(task["project_id"], "CLAIMS_EXTRACTED", self.role, task["task_id"],
                    {"count": len(data.get("claims", [])), "critical_count": critical},
                    human_visible=critical > 0)

    def _load_script(self, engine, task: dict) -> dict | None:
        ref = task["inputs"].get("script_ref")
        if ref:
            art = engine.db.get_artifact(ref)
        else:
            art = self._find_script_artifact(engine, task)
        if art is None:
            return None
        try:
            with open(art["path"], encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError):
            return None

    def _find_script_artifact(self, engine, task: dict):
        for dep in task.get("dependencies", []):
            dep_task = engine.db.get_task(dep)
            if dep_task is None:
                continue
            for art_id in dep_task.get("artifacts", []):
                art = engine.db.get_artifact(art_id)
                if art and art["type"] == "script_output":
                    return art
        return None

    @staticmethod
    def _text_around_marker(narration: str, cid: str) -> str:
        marker = f"[CLAIM:{cid}]"
        idx = narration.find(marker)
        if idx < 0:
            return narration[:80]
        rest = narration[idx + len(marker):]
        end = min(len(rest), rest.find("。") + 1 if "。" in rest else 80)
        return rest[:end].strip() or narration[:80]
