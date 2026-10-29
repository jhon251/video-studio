"""Global Reuse Policy (pure, deterministic, quality-eligible pools only).

Contract: the caller supplies beat specs whose candidate lists are ALREADY
quality-filtered (candidate-stage integrity gate + CV2). This module never
sees an un-gated asset. Selection order per beat type, with violation cascade:
pool switch -> HN (borrow with corner tag) -> BLANK card. No silent repeats.

Policy (EXP-VG frozen spec):
  EVIDENCE : unique content per beat; no adjacent same content; no content reuse
             unless registered callback (max +1 display); MD5/dHash dups are the
             same content by identity.
  VIZ      : per chart <=2 displays, in distinct chapters, not adjacent.
  HN/FALLBACK borrow: <=1 borrower per content; >=60s between any two displays
             of the same content; same-chapter borrow penalty added to distance.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from video_studio.orchestration.schemas import BeatSpec, Decision, DisplayKind
from video_studio.orchestration.global_reuse_ledger import GlobalReuseLedger


@dataclass
class ReusePolicyConfig:
    min_display_gap_s: float = 60.0
    viz_max_uses: int = 2
    viz_distinct_chapters: bool = True
    max_borrowers_per_content: int = 1
    same_chapter_borrow_penalty: float = 100.0
    callbacks: dict = field(default_factory=dict)   # content_id -> anchor beat_id (human-registered)
    # ---- beta-3' subject-anchor adjacency guard (narrow, manifest-driven) ----
    # family_ctx = {
    #   "guard": bool,                                   # enabled only via manifest
    #   "anchor_map": {token: [anchor_term, ...]},       # auditable map (first entry: ultrasound->超声)
    #   "domain_of": {content_id: domain},
    #   "map_tokens_of": {content_id: frozenset(tokens present in the title AND in anchor_map)},
    #   "anchored_of": {beat_id: frozenset(tokens whose anchor_term appears in the beat text)},
    # }
    family_ctx: dict = field(default_factory=dict)
    # ---- F-alpha: borrow-source preference (prefer sources not recently shown) --
    # Hard rules (<=2 displays, <=1 borrower, >=60s) are UNCHANGED: this only adds a
    # penalty term to the source score, so a legal-but-recent source is still used
    # when it is the only legal option.
    borrow_prefer_wide: bool = False
    borrow_wide_window_s: float = 120.0
    borrow_recent_penalty: float = 1000.0


def _eligible_sorted(cands):
    rank = {"VIZ_AUTHORIZED": -1, "USABLE": 0, "CONDITIONALLY_USABLE": 1}
    el = [c for c in cands if c.eligible]
    el.sort(key=lambda c: (rank.get(c.cv2_usability, 9), -c.cv2_fit, c.material_id))
    return el


def run_reuse_policy(beats: list[BeatSpec], config: ReusePolicyConfig | None = None) -> dict:
    """Fold beats (in timeline order) into decisions + ledger + audit log.

    Returns {"decisions": [Decision], "ledger": GlobalReuseLedger, "audit": [dict]}.
    """
    cfg = config or ReusePolicyConfig()
    ledger = GlobalReuseLedger()
    decisions: list[Decision] = []
    audit: list[dict] = []
    order = [b.beat_id for b in beats]
    pos = {b.beat_id: i for i, b in enumerate(beats)}
    viz_use: dict[str, int] = {}
    viz_chapters: dict[str, set] = {}
    decision_of: dict[str, Decision] = {}

    def neighbours(b: BeatSpec):
        i = pos[b.beat_id]
        for j in (i - 1, i + 1):
            if 0 <= j < len(beats):
                yield beats[j]

    def content_of_neighbor(b: BeatSpec):
        for nb in neighbours(b):
            d = decision_of.get(nb.beat_id)
            if d and d.content_id:
                yield d.content_id

    def record(dec: Decision, beat: BeatSpec, cand_material: str | None, content: str | None,
               function: DisplayKind, source: str = ""):
        if content and function != DisplayKind.BLANK:
            ledger.record(content_id=content, material_id=cand_material or content,
                          beat_id=beat.beat_id, chapter_id=beat.chapter_id,
                          ts_start=beat.start, ts_end=beat.end, asset_type="PHOTO",
                          function=function, source=source,
                          callback_of=dec.callback_of)
        decisions.append(dec)
        decision_of[beat.beat_id] = dec

    # ---------- PASS 1: EVIDENCE ----------
    for b in beats:
        if b.route != "EVIDENCE":
            continue
        picked = None
        for cand in _eligible_sorted(b.candidates):
            cid = cand.content_id
            if ledger.use_count(cid) > 0:
                continue                                  # uniqueness (or registered callback below)
            if cid in set(content_of_neighbor(b)):
                continue                                  # no adjacent same content
            # beta-3' subject-anchor adjacency guard: same domain AND a shared
            # mapped token that is anchored to the pair's subject text.
            fc = cfg.family_ctx or {}
            if fc.get("guard"):
                prev = beats[pos[b.beat_id] - 1] if pos[b.beat_id] > 0 else None
                dprev = decision_of.get(prev.beat_id) if prev is not None else None
                if dprev is not None and dprev.content_id:
                    d_here = fc["domain_of"].get(cid)
                    d_prev = fc["domain_of"].get(dprev.content_id)
                    if d_here and d_here == d_prev:
                        shared = (fc["map_tokens_of"].get(cid, frozenset())
                                  & fc["map_tokens_of"].get(dprev.content_id, frozenset()))
                        anchors = (fc["anchored_of"].get(b.beat_id, frozenset())
                                   | fc["anchored_of"].get(prev.beat_id, frozenset()))
                        hit = shared & anchors
                        if hit:
                            audit.append({"beat": b.beat_id, "action": "FAMILY_GUARD_SKIP",
                                          "material": cand.material_id,
                                          "vs_neighbor": prev.beat_id, "domain": d_here,
                                          "shared_anchor_tokens": sorted(hit)})
                            continue
            picked = cand
            break
        # registered callback: content already used exactly once AND registered -> allow +1
        if picked is None:
            for cand in _eligible_sorted(b.candidates):
                cid = cand.content_id
                if cfg.callbacks.get(cid) and ledger.use_count(cid) == 1:
                    if ledger.min_gap_violation(cid, b.start, b.end, cfg.min_display_gap_s):
                        continue
                    if cid in set(content_of_neighbor(b)):
                        continue
                    picked = cand
                    dec = Decision(beat_id=b.beat_id, action=DisplayKind.ANCHOR_CALLBACK,
                                   content_id=cid, material_id=cand.material_id,
                                   cls="CORRESPONDING", callback_of=cfg.callbacks[cid],
                                   reason="registered narrative anchor callback (+1 allowed)")
                    audit.append({"beat": b.beat_id, "action": "ANCHOR_CALLBACK", "content": cid})
                    record(dec, b, cand.material_id, cid, DisplayKind.ANCHOR_CALLBACK)
                    break
            if picked is not None:
                continue
        if picked is not None:
            _cls = "VIZ_STRUCTURAL" if getattr(picked, "viz", False) else "CORRESPONDING"
            dec = Decision(beat_id=b.beat_id, action=DisplayKind.EVIDENCE,
                           content_id=picked.content_id, material_id=picked.material_id,
                           cls=_cls,
                           reason=("narrow-authorized structural card (viz)" if _cls == "VIZ_STRUCTURAL"
                                   else "own-pool quality-eligible unique content"))
            record(dec, b, picked.material_id, picked.content_id, DisplayKind.EVIDENCE)
        else:
            dec = Decision(beat_id=b.beat_id, action=DisplayKind.BORROW, cls="FALLBACK",
                           reason="no quality-eligible unique own-pool candidate")
            audit.append({"beat": b.beat_id, "action": "NEEDS_BORROW"})
            record(dec, b, None, None, DisplayKind.EVIDENCE)  # ledger row written after borrow pass
            decisions.pop()                                    # defer actual row to borrow resolution
            decision_of.pop(b.beat_id, None)

    # ---------- PASS 2: VIZ ----------
    for b in beats:
        if b.route != "VIZ":
            continue
        chosen = None
        first_reason = None
        for cand in _eligible_sorted(b.candidates):
            cid = cand.content_id
            if viz_use.get(cid, 0) >= cfg.viz_max_uses:
                first_reason = first_reason or f"{cid}:cap"
                continue
            if cfg.viz_distinct_chapters and cid in viz_chapters and b.chapter_id in viz_chapters[cid]:
                first_reason = first_reason or f"{cid}:same_chapter"
                continue
            if cid in set(content_of_neighbor(b)):
                first_reason = first_reason or f"{cid}:adjacent"
                continue
            chosen = cand
            break
        if chosen is not None:
            cid = chosen.content_id
            viz_use[cid] = viz_use.get(cid, 0) + 1
            viz_chapters.setdefault(cid, set()).add(b.chapter_id)
            dec = Decision(beat_id=b.beat_id, action=DisplayKind.VIZ, content_id=cid,
                           material_id=chosen.material_id, cls="VISUALIZATION",
                           reason="chart within viz budget")
            if first_reason:
                audit.append({"beat": b.beat_id, "action": f"VIZ_POOL_SWITCH ({first_reason})"})
            record(dec, b, chosen.material_id, cid, DisplayKind.VIZ)
        else:
            dec = Decision(beat_id=b.beat_id, action=DisplayKind.BORROW, cls="FALLBACK",
                           demoted_from=DisplayKind.VIZ.value,
                           reason=f"no legal chart ({first_reason}) -> cascade to borrow")
            audit.append({"beat": b.beat_id, "action": "VIZ_DEMOTED_TO_BORROW", "reason": first_reason})
            record(dec, b, None, None, DisplayKind.VIZ)
            decisions.pop()
            decision_of.pop(b.beat_id, None)

    # ---------- PASS 3: borrow ledger (HN route + unresolved) ----------
    def borrow_legal(b: BeatSpec, cid: str) -> tuple[bool, str]:
        if ledger.borrow_count(cid) >= cfg.max_borrowers_per_content:
            return False, "borrower_cap"
        if ledger.min_gap_violation(cid, b.start, b.end, cfg.min_display_gap_s):
            return False, "min_60s_gap"
        return True, ""

    pending = [b for b in beats if b.beat_id not in decision_of]
    for b in sorted(pending, key=lambda x: pos[x.beat_id]):
        best = None
        # borrow sources: contents currently displayed as EVIDENCE / ANCHOR_CALLBACK / VIZ
        for j, b2 in enumerate(beats):
            d = decision_of.get(b2.beat_id)
            if not d or d.content_id is None or d.action in (DisplayKind.BLANK, DisplayKind.VIZ):
                continue
            cid = d.content_id
            ok, why = borrow_legal(b, cid)
            if not ok:
                continue
            pen = cfg.same_chapter_borrow_penalty if ledger.same_chapter_display(cid, b.chapter_id) else 0.0
            score = abs(pos[b.beat_id] - j) + pen
            if cfg.borrow_prefer_wide:
                recent = any(getattr(r, "narrative_function", "") == DisplayKind.EVIDENCE.value
                             and abs(b.start - r.ts_start) < cfg.borrow_wide_window_s
                             for r in ledger.displays(cid))
                if recent:
                    score += cfg.borrow_recent_penalty
                    audit.append({"beat": b.beat_id, "action": "BORROW_RECENT_EVIDENCE_PENALTY",
                                  "content": cid, "window_s": cfg.borrow_wide_window_s})
            if best is None or score < best[0]:
                best = (score, j, cid, d)
        if best is not None:
            _, j, cid, src = best
            cls = "HONEST_NEUTRAL" if b.route == "HN" else "FALLBACK"
            fn = DisplayKind.BORROW
            dec = Decision(beat_id=b.beat_id, action=fn, content_id=cid, material_id=src.material_id,
                           cls=cls, borrow_from=b2_beatid(beats, j),
                           reason=f"borrow ledger: nearest legal source at +{abs(pos[b.beat_id]-j)} beats")
            record(dec, b, src.material_id, cid, fn, source=src.material_id)
            audit.append({"beat": b.beat_id, "action": "BORROW", "from": src.beat_id,
                          "content": cid, "distance_beats": abs(pos[b.beat_id] - j)})
        else:
            dec = Decision(beat_id=b.beat_id, action=DisplayKind.BLANK, cls="BLANK_CARD",
                           content_id=f"BLANK_{b.beat_id}",
                           reason="no legal borrow source -> blank card (no silent repeat)")
            record(dec, b, None, f"BLANK_{b.beat_id}", DisplayKind.BLANK)
            audit.append({"beat": b.beat_id, "action": "BLANK_CARD"})

    return {"decisions": decisions, "ledger": ledger, "audit": audit}


def b2_beatid(beats, j):
    return beats[j].beat_id
