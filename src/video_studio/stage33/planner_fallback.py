"""planner_fallback（v3-mvp）：确定性规则回退规划器（字节级确定）。

产出与 LLM 同构的 Visual Statement。原则同 v3：静止优先、锚点词 ≤12 字、
画面不重复字幕、无模板名、理由用注意力语言（模板生成，但语义合规）。
"""
from __future__ import annotations

import re

from video_studio.stage33 import schemas

NUM_RE = re.compile(schemas.NUM_RE_SRC)


def _strip(s: str) -> str:
    return re.sub(r"[，。；！？、\s\u3000]", "", s)


def detect_beat_types(text: str) -> list[str]:
    types = []
    if NUM_RE.search(text):
        types.append("DATA")
    if any(c in text for c in schemas.TIME_CUES):
        types.append("TIME_CHANGE")
    if any(c in text for c in schemas.CAUSE_CUES):
        types.append("CAUSE")
    if any(c in text for c in schemas.CONTRAST_CUES):
        types.append("CONTRAST")
    if any(c in text for c in schemas.ACTION_CUES):
        types.append("ACTION")
    if any(c in text for c in schemas.SPACE_CUES):
        types.append("SPACE_CHANGE")
    if any(c in text for c in schemas.CONCLUSION_CUES):
        types.append("CONCLUSION")
    if any(c in text for c in schemas.EMOTION_CUES):
        types.append("EMOTION")
    if not types:
        types = ["INFO"]
    return types[:3]


def split_beats(text: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"(?<=[，；。！？])", text) if p.strip()]
    if len(parts) > 3:
        merged, cur = [], ""
        for p in parts:
            if cur and len(cur) + len(p) > len(text) / 3 + 3:
                merged.append(cur)
                cur = p
            else:
                cur += p
        if cur:
            merged.append(cur)
        parts = merged
    parts = [p for p in parts if len(_strip(p)) >= 2]
    return parts[:3] if parts else [text]


def _target(text: str) -> str:
    m = NUM_RE.search(text)
    if m:
        return m.group(0)
    for cue in schemas.EMOTION_CUES + schemas.CONTRAST_CUES + schemas.ACTION_CUES:
        if cue in text:
            return cue
    return _strip(text)[:6]


def _intent_text(types: list[str]) -> str:
    if "CONTRAST" in types:
        return "并置反差：让两个相对项被同时看见"
    if "DATA" in types:
        return "呈现数量信息：让数字成为唯一焦点"
    if "CAUSE" in types or "EFFECT" in types:
        return "呈现因果：先因后果的注意力顺序"
    if "CONCLUSION" in types:
        return "收束：把信息压到唯一焦点"
    if "EMOTION" in types:
        return "情绪落地：用画面本身承载氛围"
    return "信息陈述：让焦点词先于整句被看见"


def _motion_for(text: str, target: str, types: list[str]) -> dict:
    if "SPACE_CHANGE" in types or any(c in text for lst in schemas.DIRECTION_LEXICON.values()
                                      for c in lst):
        d = "DOWN" if any(c in text for c in schemas.DIRECTION_LEXICON["DOWN"]) else (
            "UP" if any(c in text for c in schemas.DIRECTION_LEXICON["UP"]) else None)
        if d:
            return {"necessity": f"方向词要求视线跟随移动，删掉后「{target}」的空间语义将丢失",
                    "intent": "attention_shift", "describe": f"焦点词沿{d}方向平移一次"}
    return {"necessity": "静止即完整表达，删掉运动观众不会损失任何信息",
            "intent": "none", "describe": "保持绝对静止"}


def decide_shot(sid: str, narration: str, shot_role: str, candidates: list,
                arc_summary: dict, is_last_shot: bool) -> dict:
    beats = []
    pieces = split_beats(narration)
    for i, bt in enumerate(pieces):
        types = detect_beat_types(bt)
        target = _target(bt)
        mat = None
        if candidates:
            c = candidates[0]
            mat = c["material_id"]
        if mat:
            evidence = f"白名单素材 {mat}（{c.get('visual_description','')[:24]}）"
            layers = [
                {"role": "background", "content": "素材画面", "purpose": "提供真实语境"},
                {"role": "foreground", "content": f"锚点词「{target}」",
                 "purpose": "注意力焦点"}]
        else:
            evidence = f"口播原文数字/关键词「{target}」"
            layers = [
                {"role": "background", "content": "风格色块（弱化）", "purpose": "承载画面"},
                {"role": "foreground", "content": f"锚点词「{target}」",
                 "purpose": "注意力焦点"}]
        stages = [{"name": "enter", "action": f"锚点词「{target}」淡入", "purpose": "先让焦点出现"},
                  {"name": "hold", "action": "停留", "purpose": "与口播同步"}]
        if "CONTRAST" in types:
            stages.append({"name": "reveal", "action": "对比项同时可见",
                           "purpose": "并置反差"})
        rel = "none"
        if types:
            if "CONTRAST" in types:
                rel = "contrast"
            elif i > 0 or sid != "S01":
                rel = "continuation"
        beats.append({
            "beat_text": bt,
            "narrative_intent": _intent_text(types),
            "attention_target": target,
            "attention_path": f"第一眼看「{target}」，第二眼与口播语义对应",
            "visual_evidence": evidence,
            "evidence_material": mat,
            "visual_metaphor": (None if mat else
                                f"以原文词「{target}」为唯一焦点做最小构图演绎（无素材诚实降级）"),
            "composition": {"layers": layers},
            "shot_language": "固定机位观察",
            "temporal_behavior": {"stages": stages},
            "relation_to_previous": {"type": rel,
                                     "explain": f"规则回退：与上一镜按信息顺序{rel}承接"},
            "relation_to_next": {"type": "none", "explain": "由下一镜声明关系"},
            "graphic_layer": {"text": target[:12], "purpose": "焦点词，字幕已给全文"},
            "motion": _motion_for(bt, target, types),
            "audio_relationship": "VO 主导，画面静默配合",
            "director_note": f"以「{target}」为唯一焦点，画面不重复字幕，克制静止呈现。",
        })
    return {"shot_id": sid, "beats": beats}


def run_fallback(ctx: dict) -> dict:
    shots = ctx["shots"]
    flow, climax, best = [], None, -1
    for i, s in enumerate(shots):
        c = sum(NUM_RE.search(p) is not None for p in [s["narration"]])
        if c > best:
            best, climax = c, s["shot_id"]
        focus = _target(s["narration"])
        rel = "none" if i == 0 else "continuation"
        flow.append({"shot_id": s["shot_id"], "focus_hint": focus,
                     "relation_to_prev": rel, "relation_explain": "规则回退：信息顺序承接"})
    arc = {"flow": flow, "climax_shot": climax or shots[-1]["shot_id"],
           "release_shots": [shots[-1]["shot_id"]],
           "pacing_note": "规则回退：数据镜为高潮，末镜释放；全片静止优先"}
    results = {}
    for s in shots:
        sid = s["shot_id"]
        results[sid] = decide_shot(sid, s["narration"], s["shot_role"],
                                   s["whitelisted_candidates"], arc,
                                   is_last_shot=(sid == shots[-1]["shot_id"]))
    return {"arc": arc, "shots": results, "stats": {"fallback": True}}
