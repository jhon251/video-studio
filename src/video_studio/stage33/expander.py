"""expander：确定性实现展开（Director 创意决策 → 具体 plan 字段）。

职责：时间分配（字符比例）、span、运动参数、构图锚点、图形/卡模板变体、母题映射、
climax 映射、策略表。全部由 seed 哈希派生，无随机、无时间依赖（字节级确定）。
"""
from __future__ import annotations

import hashlib
import json
import re

from video_studio.stage33 import schemas
from video_studio.stage33.planner_fallback import NUM_RE, split_beats
from video_studio.stage33.sanitizer import parse_narration


def split_n(text: str, n: int, dur: float) -> list[str]:
    """把句子确定性切成恰好 n 段（逐字覆盖原文；每段 ≥1.2s 的字符量）。"""
    pieces = split_beats(text)
    while len(pieces) > n:  # 合并最短相邻（绝不截断丢字）
        best = min(range(len(pieces) - 1),
                   key=lambda i: len(pieces[i]) + len(pieces[i + 1]))
        pieces[best:best + 2] = [pieces[best] + pieces[best + 1]]
    while len(pieces) < n:
        idx = max(range(len(pieces)), key=lambda i: len(pieces[i]))
        p = pieces[idx]
        ms = [m.start() for m in re.finditer(r"[，；。]", p)]
        cut = (ms[len(ms) // 2] + 1) if ms else len(p) // 2
        pieces[idx:idx + 1] = [p[:cut], p[cut:]]
    if dur > 0:
        min_chars = max(int(1.2 * len(text) / dur), 1)
        while len(pieces) > 1:
            small = [i for i, p in enumerate(pieces) if len(p) < min_chars]
            if not small:
                break
            i = small[0]
            if i == 0:
                pieces[0:2] = [pieces[0] + pieces[1]]
            else:
                pieces[i - 1:i + 1] = [pieces[i - 1] + pieces[i]]
        while len(pieces) < n and any(len(p) > min_chars * 2 for p in pieces):
            idx = max(range(len(pieces)), key=lambda i: len(pieces[i]))
            p = pieces[idx]
            ms = [m.start() for m in re.finditer(r"[，；。]", p)]
            cut = (ms[len(ms) // 2] + 1) if ms else len(p) // 2
            pieces[idx:idx + 1] = [p[:cut], p[cut:]]
    return pieces


ANCHORS = {
    "FULL_BLEED": (0.5, 0.5), "CENTER_CROP": (0.5, 0.5), "THIRDS_LEFT": (0.33, 0.5),
    "THIRDS_RIGHT": (0.67, 0.5), "INSET_FRAME": (0.5, 0.42), "SPLIT_H": (0.5, 0.5),
    "SPLIT_V": (0.5, 0.5), "UPPER_TITLE": (0.5, 0.28),
}


def _motion_params(motion_type: str, direction: str | None, dur: float) -> dict:
    n = max(int(dur * 25), 1)
    if motion_type == "SLOW_PUSH_IN":
        return {"zoompan": f"z='min(1.0+0.05*on/{n},1.06)':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2'"}
    if motion_type == "FOCAL_ZOOM":
        return {"zoompan": f"z='min(1.0+0.08*on/{n},1.08)':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2'"}
    if motion_type == "SLOW_PULL_OUT":
        return {"zoompan": f"z='max(1.08-0.08*on/{n},1.0)':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2'"}
    if motion_type == "PAN_H":
        x = f"(iw-iw/zoom)*on/{n}" if direction == "RIGHT" else f"(iw-iw/zoom)*(1-on/{n})"
        return {"zoompan": f"z='1.06':x='{x}':y='(ih-ih/zoom)/2'"}
    if motion_type == "PAN_V":
        y = f"(ih-ih/zoom)*(1-on/{n})" if direction == "UP" else f"(ih-ih/zoom)*on/{n}"
        return {"zoompan": f"z='1.06':x='(iw-iw/zoom)/2':y='{y}'"}
    if motion_type == "DIAGONAL_DRIFT":
        dx = direction if direction in ("LEFT", "RIGHT") else "RIGHT"
        dy = "UP" if direction == "UP" else "DOWN"
        x = f"(iw-iw/zoom)*on/{n}" if dx == "RIGHT" else f"(iw-iw/zoom)*(1-on/{n})"
        y = f"(ih-ih/zoom)*(1-on/{n})" if dy == "UP" else f"(ih-ih/zoom)*on/{n}"
        return {"zoompan": f"z='1.05':x='{x}':y='{y}'"}
    if motion_type == "HOLD_MICRO":
        return {"zoompan": "z='1.004+0.004*sin(on*0.06)':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2'"}
    if motion_type == "SOURCE_NATIVE":
        return {"zoompan": None}
    return {"zoompan": None}


def _graphic(expr: str, beat_text: str, types: list[str], seed: int, idx: int) -> dict | None:
    if expr == "DATA_GRAPHIC":
        numbers = [m.group(0) for m in NUM_RE.finditer(beat_text)]
        return {"graphic_type": "NUMBER_EMPHASIS",
                "variant": ["CENTER", "HORIZONTAL", "CORNER"][(seed + idx) % 3],
                "numbers": numbers, "title": beat_text,
                "truth_source": "NARRATION_VERBATIM",
                "source_tag": "依据：口播稿原文", "self_created": True}
    if expr == "SELF_CREATED_GRAPHIC":
        gt = "COMPARISON" if "CONTRAST" in types else "TYPO_COMPOSITION"
        return {"graphic_type": gt,
                "variant": ["CENTER", "HORIZONTAL", "CORNER"][(seed + idx) % 3],
                "numbers": [], "title": beat_text,
                "truth_source": "NARRATION_VERBATIM",
                "source_tag": "依据：口播稿原文", "self_created": True}
    if expr == "TEXT_CARD":
        layout = "CONTRAST_SPLIT" if "CONTRAST" in types else (
            "QUESTION" if "QUESTION" in types else "STATEMENT")
        return {"card_layout": layout,
                "variant": ["A", "B", "C"][(seed + idx) % 3],
                "numbers": [], "title": beat_text,
                "truth_source": "NARRATION_VERBATIM",
                "source_tag": "依据：口播稿原文", "self_created": True}
    return None


def build_draft(ctx: dict, director_out: dict, fingerprint: str) -> dict:
    """director_out={arc, shots:{sid:{beats:[...]}}} → plan draft（含时间/参数）。"""
    narration_shots = parse_narration(ctx["narration"])
    by_id = {s["shot_id"]: s["text"] for s in narration_shots}
    timing = {s["shot_id"]: s["timing"] for s in ctx["shots"] if s.get("timing")}
    seed = int(hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:8], 16)

    arc = director_out.get("arc", {})
    motifs_raw = arc.get("motifs", []) or []
    beats, decisions, motifs = [], [], []
    beat_counter = [0]
    beat_of_shot = {}

    def new_beat(sid, text, start, end):
        beat_counter[0] += 1
        bid = f"B{beat_counter[0]:03d}"
        beat_of_shot.setdefault(sid, []).append(bid)
        return bid, start, end

    for s in ctx["shots"]:
        sid = s["shot_id"]
        narration = by_id.get(sid, "")
        t0 = timing.get(sid, {}).get("start", 0.0)
        dur = timing.get(sid, {}).get("duration") or 4.0
        raw_beats = (director_out.get("shots", {}).get(sid, {}) or {}).get("beats", [])
        if not raw_beats:
            raw_beats = [{"beat_text": narration, "beat_types": ["INFO"], "intensity": "LOW",
                          "emphasis_target": None, "expression": "TEXT_CARD",
                          "semantic_role": "INFO", "source_material": None,
                          "composition": {"layout": "FULL_BLEED"},
                          "motion": {"motion_type": "HOLD_MICRO", "direction": None},
                          "transition_in": "HARD_CUT",
                          "narrative_purpose": "", "relation_to_previous": "",
                          "what_to_show": "", "why_this_expression": "", "motion_reason": "",
                          "fallback_reason": None, "motif_id": None}]
        total_chars = max(sum(len(b.get("beat_text", "")) for b in raw_beats), 1)
        # beat 文本确定性落地：LLM 只决定 beat 数量与逐 beat 创意决策，文本由 split_n 逐字切分
        pieces = split_n(narration, len(raw_beats), dur)
        total_chars = max(sum(len(p) for p in pieces), 1)
        cum = 0.0
        for i, piece in enumerate(pieces):
            rb = raw_beats[i] if i < len(raw_beats) else raw_beats[-1]
            text = piece
            bd = dur * len(text) / total_chars
            bd = min(max(bd, 0.4), dur - cum - 0.001 * (len(pieces) - i - 1))
            start = t0 + cum
            if i == len(pieces) - 1:
                end = t0 + dur
                bd = end - start
            else:
                end = start + bd
            cum += bd
            bid, bs, be = new_beat(sid, text, round(start, 3), round(end, 3))
            beats.append({
                "beat_id": bid, "shot_id": sid, "beat_text": text,
                "start": bs, "end": be, "duration": round(be - bs, 3),
                "beat_types": rb.get("beat_types", ["INFO"]),
                "intensity": rb.get("intensity", "LOW"),
                "emphasis_target": rb.get("emphasis_target"),
                "truth_dependency": {"source": "NARRATION_VERBATIM",
                                     "ref": f"{sid}:{text[:12]}"},
            })
            mt = rb.get("motion", {}).get("motion_type", "HOLD_MICRO")
            dr = rb.get("motion", {}).get("direction")
            layout = rb.get("composition", {}).get("layout", "FULL_BLEED")
            expr = rb.get("expression", "TEXT_CARD")
            g = _graphic(expr, text, beats[-1]["beat_types"], seed, i)
            decisions.append({
                "decision_id": f"D{beat_counter[0]:03d}", "beat_id": bid,
                "expression": expr,
                "semantic_role": rb.get("semantic_role", "INFO"),
                "source_material": rb.get("source_material"),
                "graphic": g,
                "composition": {"layout": layout, "anchor": ANCHORS.get(layout, (0.5, 0.5))},
                "motion": {"motion_type": mt, "direction": dr,
                           "params": _motion_params(mt, dr, be - bs)},
                "transition_in": rb.get("transition_in", "HARD_CUT"),
                "narrative_purpose": rb.get("narrative_purpose", ""),
                "relation_to_previous": rb.get("relation_to_previous", ""),
                "what_to_show": rb.get("what_to_show", ""),
                "why_this_expression": rb.get("why_this_expression", ""),
                "motion_reason": rb.get("motion_reason", ""),
                "fallback_reason": rb.get("fallback_reason"),
                "motif_id": rb.get("motif_id"),
                "decision_chain": [], "repaired_fields": [],
                "duration": round(be - bs, 3),
                "truth_dependency": {"source": "NARRATION_VERBATIM", "ref": f"{sid}:{text[:12]}"},
            })

    # 母题映射（anchor/callback shot → beat）
    for m in motifs_raw:
        a_shot, cb_shots = m.get("anchor_shot"), m.get("callback_shots") or []
        a_beat = (beat_of_shot.get(a_shot) or [None])[0]
        cb_beats = [(beat_of_shot.get(s) or [None])[0] for s in cb_shots]
        motifs.append({
            "motif_id": m.get("motif_id"), "kind": m.get("kind"),
            "description": m.get("description", ""),
            "anchor_beat": a_beat, "callback_beats": [b for b in cb_beats if b],
        })

    # climax 映射：climax_shot → 该镜 intensity 最高（并列取最后）的 beat
    climax_shot = arc.get("climax_shot")
    climax_beat = None
    if climax_shot:
        cbs = [b for b in beats if b["shot_id"] == climax_shot]
        if cbs:
            order = {"LOW": 0, "MED": 1, "HIGH": 2}
            climax_beat = max(cbs, key=lambda b: order.get(b["intensity"], 0))["beat_id"]

    phases = arc.get("phases", []) or []
    # 弧归一化：去重（同 phase+shot_ids 只留一次）；只剩 1 段时补 DEVELOPMENT 覆盖其余镜
    seen, uniq = set(), []
    for p in phases:
        key = (p.get("phase"), tuple(p.get("shot_ids", [])))
        if key in seen or not p.get("shot_ids"):
            continue
        seen.add(key)
        uniq.append(p)
    covered = {s for p in uniq for s in p.get("shot_ids", [])}
    all_ids = [s["shot_id"] for s in ctx["shots"]]
    if uniq and len({p["phase"] for p in uniq}) == 1 and covered != set(all_ids):
        rest = [s for s in all_ids if s not in covered]
        if rest:
            uniq.append({"phase": "DEVELOPMENT", "shot_ids": rest,
                         "note": "规则归一：其余镜次展开段"})
    # 弧结构补全（通用、主题无关）：首镜 HOOK、末镜 CONCLUSION、高潮前 ESCALATION
    if uniq and all_ids:
        first, last = all_ids[0], all_ids[-1]
        def _phase_of(sid):
            return next((p for p in uniq if sid in p.get("shot_ids", [])), None)
        if not any(p["phase"] == "HOOK" and first in p.get("shot_ids", []) for p in uniq):
            for p in uniq:
                if first in p.get("shot_ids", []):
                    p["shot_ids"] = [x for x in p["shot_ids"] if x != first]
            uniq.insert(0, {"phase": "HOOK", "shot_ids": [first], "note": "规则归一：开场"})
        if not any(p["phase"] == "CONCLUSION" and last in p.get("shot_ids", []) for p in uniq):
            for p in uniq:
                if last in p.get("shot_ids", []):
                    p["shot_ids"] = [x for x in p["shot_ids"] if x != last]
            uniq.append({"phase": "CONCLUSION", "shot_ids": [last], "note": "规则归一：收束"})
        if climax_shot and climax_shot in all_ids and \
                not any(p["phase"] in ("ESCALATION", "TURNING_POINT") for p in uniq):
            idx = all_ids.index(climax_shot)
            if idx > 1:
                pre = all_ids[max(0, idx - 2):idx]
                uniq.insert(len(uniq) - 1,
                            {"phase": "ESCALATION", "shot_ids": pre,
                             "note": "规则归一：高潮前加速"})
        uniq = [p for p in uniq if p.get("shot_ids")]
    phases = uniq

    # pacing 归一化：LLM 若照抄了系统提示片段，替换为通用说明
    pacing = arc.get("pacing_note", "") or ""
    if "escalation" in pacing or "开场 beat" in pacing or len(pacing) > 60:
        pacing = "由 arc 段与 climax_beat 驱动节奏（LLM pacing 说明缺失，规则归一）"

    # 母题兜底：无有效母题时注册通用首尾呼应（风格契约驱动，主题无关）
    if not motifs and len(beats) >= 2:
        motifs.append({
            "motif_id": "M-OPENING-CLOSING", "kind": "COMPOSITION",
            "description": "开场与结尾回收同一构图与风格契约主色，形成首尾呼应（规则兜底，主题无关）",
            "anchor_beat": beats[0]["beat_id"],
            "callback_beats": [beats[-1]["beat_id"]],
        })

    strategies = []
    for s in ctx["shots"]:
        sid = s["shot_id"]
        phase = next((p["phase"] for p in phases if sid in p.get("shot_ids", [])), "DEVELOPMENT")
        mood = {"HOOK": "NEUTRAL", "ESCALATION": "TENSE", "TURNING_POINT": "TENSE",
                "CONCLUSION": "HOPEFUL"}.get(phase, "NEUTRAL")
        strategies.append({
            "shot_id": sid, "shot_role": s["shot_role"],
            "visual_target_hint": s.get("duration_hint", ""),
            "arc_phase": phase, "section_mood": mood,
            "beat_plan": beat_of_shot.get(sid, []),
        })

    narrative_arc = {
        "phases": phases,
        "pacing_note": pacing,
        "climax_shot": climax_shot,
        "climax_beat": climax_beat,
        "whitespace_beats": [(beat_of_shot.get(s) or [None])[0]
                             for s in (arc.get("whitespace_shots") or [])],
        "callback_plan": [{"motif_id": m["motif_id"], "first_beat": m["anchor_beat"],
                           "callback_beats": m["callback_beats"]} for m in motifs],
    }
    return {
        "schema_version": "3.3-p1", "generator_version": "3.3-m2",
        "project": ctx.get("project", "coral"),
        "style_contract": dict(schemas.STYLE_CONTRACT),
        "narrative_arc": narrative_arc,
        "beats": beats, "decisions": decisions, "motifs": motifs,
        "strategies": strategies,
    }
