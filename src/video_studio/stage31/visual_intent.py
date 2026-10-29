"""Stage 3.1.2 视觉意图层（主题无关）。

- 镜号只是 ID，不再承载语义（SECTION_SHOTS/TOPIC_INTENTS 已删除）。
- 每镜意图由当前镜头口播文本动态推导（intent_extract），
  role/purpose/时长只做辅助（媒体偏好、关系类型），绝不注入主题。
- match_type（DIRECT/CONCEPTUAL/EMOTIONAL/RHYTHM）由 shot 的 role/visual_target 决定
  （这是分镜结构信息，不是主题先验）。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .intent_extract import extract


def _determine_match_type(shot: dict) -> tuple[str, str]:
    role = shot.get("role", "")
    beat = shot.get("beat", "")
    vt = shot.get("visual_target", "")
    refs = shot.get("evidence_refs", [])

    if role == "gap":
        return "SELF_MADE", "none"
    if role == "fact":
        return "EVIDENCE", "evidence"
    if role == "transition":
        return "RHYTHM", "broll"
    if role in ("conclusion", "conclusion_first") or beat in ("余韵收束", "收束回应", "先给结论"):
        return "EMOTIONAL", "broll"
    if role == "body":
        if "实拍素材" in vt:
            return "DIRECT", "broll"
        if refs and ("数据可视化" in vt or "概念动画" in vt or "证据截图" in vt):
            return "EVIDENCE", "evidence"
        if "数据可视化" in vt or "概念动画" in vt:
            return "CONCEPTUAL", "broll"
        return "CONCEPTUAL", "broll"
    if refs:
        return "EVIDENCE", "evidence"
    if "悬念相关快切" in str(shot.get("broll_requirement", "")):
        return "RHYTHM", "broll"
    if "快切素材" in vt or "大字标题卡" in vt or "数字卡" in vt:
        return "RHYTHM", "broll"
    return "CONCEPTUAL", "broll"


@dataclass
class VisualIntent:
    shot_id: str
    section: str
    role: str
    beat: str
    match_type: str
    material_kind: str
    subject: str
    action: str
    object: str
    environment: str
    concept: str
    visual_relationship: str
    mood: str
    temporal_context: str
    abstraction_level: str
    preferred_media_type: str
    camera_style: str
    preferred_duration: float
    avoid_list: list
    queries_en: list
    queries_zh: list
    query_ladder: list = field(default_factory=list)
    concepts_pos: list = field(default_factory=list)
    concepts_neg: list = field(default_factory=list)
    evidence_refs: list = field(default_factory=list)
    narration_note: str = ""
    rationale: str = ""
    narration: str = ""


def build_intents(shotlist_path: Path, v2_script_path: Path | None = None) -> list[VisualIntent]:
    data = json.loads(shotlist_path.read_text(encoding="utf-8"))
    scenes = data["scenes"]
    intents = []
    for sc in scenes:
        sid = sc["scene_id"]
        narration = sc.get("narration", "") or ""
        mtype, mkind = _determine_match_type(sc)
        ex = extract(narration, role=sc.get("role", "body"),
                     purpose=sc.get("visual_target", ""),
                     duration_hint=float(re.search(r"(\d+)", str(sc.get("duration_hint", "8s")))
                                         .group(1) if re.search(r"(\d+)", str(sc.get("duration_hint", "8s"))) else 8.0))
        ladder = [("literal", ex["search_queries"][0]),
                  ("conceptual", ex["search_queries"][1]),
                  ("metaphorical", ex["search_queries"][2])]
        flat = [q for _, qs in ladder for q in qs]
        dur_m = re.search(r"(\d+)", str(sc.get("duration_hint", "8s")))
        intents.append(VisualIntent(
            shot_id=sid, section="(动态意图)", role=sc.get("role", ""), beat=sc.get("beat", ""),
            match_type=mtype, material_kind=mkind,
            subject=ex["subject"], action=ex["action"], object=ex["object"],
            environment=ex["environment"], concept=ex["concept"],
            visual_relationship=ex["visual_relationship"], mood=ex["mood"],
            temporal_context=ex["temporal_context"],
            abstraction_level=ex["abstraction_level"],
            preferred_media_type=ex["preferred_media_type"],
            camera_style="按媒体类型自适应",
            preferred_duration=float(dur_m.group(1)) if dur_m else 8.0,
            avoid_list=list(ex["avoid_queries"]),
            queries_en=flat, queries_zh=[],
            query_ladder=ladder,
            concepts_pos=list(ex["concepts_positive"]),
            concepts_neg=list(ex["concepts_negative"]),
            evidence_refs=list(sc.get("evidence_refs", [])),
            narration_note=f"{sc.get('visual_target','')} / {sc.get('broll_requirement','')}",
            rationale=ex["rationale"],
            narration=narration,
        ))
    return intents


def intent_to_dict(v: VisualIntent) -> dict:
    return {
        "shot_id": v.shot_id, "role": v.role, "beat": v.beat,
        "match_type": v.match_type, "material_kind": v.material_kind,
        "subject": v.subject, "action": v.action, "object": v.object,
        "environment": v.environment, "concept": v.concept,
        "visual_relationship": v.visual_relationship, "mood": v.mood,
        "temporal_context": v.temporal_context,
        "abstraction_level": v.abstraction_level,
        "preferred_media_type": v.preferred_media_type,
        "camera_style": v.camera_style, "preferred_duration": v.preferred_duration,
        "avoid_list": v.avoid_list, "queries_en": v.queries_en,
        "query_ladder": v.query_ladder, "concepts_pos": v.concepts_pos,
        "concepts_neg": v.concepts_neg,
        "evidence_refs": v.evidence_refs, "narration_note": v.narration_note,
        "rationale": v.rationale, "narration": v.narration,
    }
