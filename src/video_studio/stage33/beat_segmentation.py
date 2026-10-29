"""beat_segmentation (Stage 12.7): narration -> 2-4 Visual Beats.

Solves: one asset no longer covers a whole narration segment. Each beat gets
its own narration slice -> independent Visual Intent -> Query -> Retrieval ->
Gate -> V1 -> CV-2 downstream (the test drives those stages; this module only
segments and builds the timeline).

Design (no hard-rule shot fabrication):
  1) deterministic clause split of the narration (punctuation-attached),
  2) LLM groups clause indices into 1-4 ordered beats (2-4 for long narration,
     1 allowed for short), guided by: single asset <= 8-10 s,
  3) validation: every clause used exactly once, beats contiguous & ordered
     (beat text = verbatim concatenation, semantic continuity guaranteed),
  4) fallback (LLM failure): deterministic balanced chunking into
     N = clamp(round(duration/8), 1, 4) beats — recorded as fallback,
  5) timeline: beat duration = shot_duration * beat_chars / narration_chars;
     beats are contiguous by construction (no overlap, no gap).

This module does not touch intent/query/retrieval/gate/V1/CV-2 or any policy.
"""
from __future__ import annotations

import json
import re

SCHEMA_BEATS = {
    "type": "object",
    "properties": {
        "beats": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "clauses": {"type": "array", "items": {"type": "integer"}},
                    "focus": {"type": "string"},
                },
                "required": ["clauses"],
            },
        }
    },
    "required": ["beats"],
}

PROMPT_BEATS = (
    "你是视频分镜师。给定一段旁白被切分后的编号子句和该段音频时长，把子句按顺序分组为若干【视觉节拍】。"
    "只输出 JSON，禁止 Markdown、禁止解释。字段：\n"
    "  \"beats\": 对象数组，每个对象 {\"clauses\": [子句编号...], \"focus\": \"该节拍画面焦点(一句话)\"}\n"
    "规则：\n"
    "  - 子句必须按原顺序分组，每个子句恰好用一次，不能跳过或重复；\n"
    "  - 音频时长 {duration}s，单张素材停留不超过 8-10 秒：据此决定节拍数(通常 2-4 个)；"
    "音频超过 12 秒时至少 2 个节拍(除非只有 1 个子句)；"
    "旁白很短(音频<=8s)时可以是 1 个节拍，不要强行拆分；\n"
    "  - 每个节拍应是一个可独立成画的语义单元(主体+动作或场景切换)，保持旁白语义连续；\n"
    "  - focus 用中文一句话描述该节拍观众看到的画面。\n"
    "子句列表：\n{clauses}\n音频时长：{duration} 秒")


def split_clauses(narration: str) -> list[str]:
    """Deterministic clause split; each clause keeps its trailing punctuation."""
    parts = re.findall(r"[^，。！？；、…]*[，。！？；、…]+|[^，。！？；、…]+$", narration)
    return [p for p in (x.strip() for x in parts) if p]


def _balanced_fallback(clauses: list[str], duration: float) -> list[list[int]]:
    n_beats = max(1, min(4, round(duration / 8)))
    weights = [len(c) for c in clauses]
    total = sum(weights)
    out, cur, cur_w = [], [], 0.0
    target = total / n_beats
    for i, w in enumerate(weights):
        cur.append(i)
        cur_w += w
        if len(out) < n_beats - 1 and cur_w >= target and (len(weights) - i - 1) >= (n_beats - 1 - len(out)):
            out.append(cur)
            cur, cur_w = [], 0.0
    if cur:
        out.append(cur)
    return out


def _validate_groups(groups: list[list[int]], n_clauses: int) -> bool:
    if not groups or len(groups) > 4:
        return False
    flat = [i for g in groups for i in g]
    if sorted(flat) != list(range(n_clauses)):
        return False
    pos = 0
    for g in groups:  # ordered & contiguous
        if not g:
            return False
        for i in g:
            if i != pos:
                return False
            pos += 1
    return True


def segment_beats(narration: str, shot_duration_s: float, th) -> dict:
    clauses = split_clauses(narration)
    duration = max(1.0, float(shot_duration_s or 8.0))
    groups, focus, llm_status, fallback = None, [], "SKIPPED", False

    if th is not None and len(clauses) >= 2:
        cl_list = "\n".join(f"{i}: {c}" for i, c in enumerate(clauses))
        user = (PROMPT_BEATS.replace("{clauses}", cl_list)
                .replace("{duration}", f"{duration:.1f}"))
        res = th.hardened_call("deepseek-chat", "你是视频分镜师。", user,
                               SCHEMA_BEATS, repair_prompt=user, temperature=0.2)
        llm_status = res.get("status", "UNKNOWN")
        data = res.get("data") or {}
        cand = []
        for b in (data.get("beats") or []):
            idx = [int(x) for x in (b.get("clauses") or [])]
            cand.append({"clauses": idx, "focus": (b.get("focus") or "").strip()})
        cand = [c for c in cand if c["clauses"]]
        if cand and _validate_groups([c["clauses"] for c in cand], len(clauses)):
            groups = [c["clauses"] for c in cand]
            focus = [c["focus"] for c in cand]

    if groups is None:
        groups = _balanced_fallback(clauses, duration)
        focus = ["(fallback: deterministic balanced chunk)"] * len(groups)
        fallback = True

    beats = []
    total_chars = sum(len(clauses[i]) for g in groups for i in g)
    cursor = 0.0
    for k, g in enumerate(groups):
        text = "".join(clauses[i] for i in g)
        dur = duration * len(text) / max(1, total_chars)
        beats.append({
            "beat_id": f"B{k+1:02d}",
            "clause_indices": g,
            "narration": text,          # verbatim slice of the original
            "focus": focus[k] if k < len(focus) else "",
            "start": round(cursor, 2),
            "end": round(cursor + dur, 2),
            "duration": round(dur, 2),
        })
        cursor += dur

    # timeline validation (float-safe)
    problems = []
    if abs(cursor - duration) > 0.05:
        problems.append(f"coverage {cursor:.2f} != duration {duration:.2f}")
    for a, b in zip(beats, beats[1:]):
        if abs(a["end"] - b["start"]) > 0.02:
            problems.append(f"gap/overlap {a['beat_id']}->{b['beat_id']}")
    for b in beats:
        if b["duration"] <= 0:
            problems.append(f"{b['beat_id']} non-positive duration")

    return {"shot_duration_s": round(duration, 2),
            "clauses": clauses,
            "beats": beats,
            "n_beats": len(beats),
            "llm_status": llm_status,
            "fallback": fallback,
            "timeline_valid": not problems,
            "timeline_problems": problems,
            "max_single_asset_hold_s": round(max(b["duration"] for b in beats), 2)}
