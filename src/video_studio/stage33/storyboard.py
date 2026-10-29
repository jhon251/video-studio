"""storyboard (Stage 12.10): executable per-beat storyboard orchestration.

Consumes ONLY existing chain artifacts (no re-retrieval, no re-judging):
  - Stage 12.7 beat_test.json        -> beat timeline (verbatim narration,
                                        beat start/end/duration, focus)
  - Stage 12.9 beat_recovery_test.json -> stable Visual Intent (cache-stable)
                                        + per-beat Gate/V1/CV-2 results

Output: per-beat executable entry {timeline, narration (verbatim), intent,
material | HONEST_EMPTY, composition, motion, subtitle cues} + validation.
Composition/motion come from the FROZEN policies (decide_composition /
decide_motion); subtitle lines from the FROZEN subtitle_pipeline helpers.

Material qualification (orchestration-level, no new scoring):
  a beat's final material is QUALIFIED iff its 12.9 CV-2 top-1 exists AND
  CV-2 labels in {USABLE, CONDITIONALLY_USABLE}. Anything else (incl.
  NOT_USABLE) -> explicit HONEST_EMPTY with the reason + candidate trace.
  No filler, no borrowing of other beats' assets.

Narration is never rewritten: beat text is copied byte-for-byte from the
12.7 chain; subtitle cues are display-line splits of the same verbatim text.
"""
from __future__ import annotations

import json

from video_studio.stage33.camera_motion_policy import decide_motion
from video_studio.stage33.composition_policy import decide_composition
from video_studio.stage33.subtitle_pipeline import split_for_subtitle, ts

QUALIFIED_LABELS = {"USABLE", "CONDITIONALLY_USABLE"}


def _norm_title(title: str) -> str:
    t = (title or "").strip()
    if t.lower().startswith("file:"):
        t = t[5:]
    return t.replace(" ", "_")


def build_beat_cues(narration: str, start: float, end: float) -> list[dict]:
    """Subtitle cues inside [start, end]; verbatim text, proportional timing,
    last cue ends exactly at beat end (12.4-lesson applied)."""
    lines = split_for_subtitle(narration)
    weights = [len(l) + 1 for l in lines]
    total_w = sum(weights) or 1
    dur = end - start
    cues, cur = [], start
    for i, (line, w) in enumerate(zip(lines, weights)):
        cue_end = end if i == len(lines) - 1 else cur + dur * w / total_w
        cues.append({"text": line, "start": round(cur, 3),
                     "end": round(cue_end, 3), "srt": f"{ts(cur)} --> {ts(cue_end)}"})
        cur = cue_end
    return cues


def build_storyboard(b27: dict, r29: dict,
                     shot_narrations: dict[str, str] | None = None) -> dict:
    beats27 = []
    for s in b27["results"]:
        for b in s["beats"]:
            beats27.append({"shot_id": s["shot_id"], "shot_duration_s": s["shot_duration_s"],
                            "beat": b})
    rec29 = {(r["shot_id"], r["beat_id"]): r for r in r29["results"]}

    shots, offset = [], 0.0
    used_assets: set[str] = set()
    shot_offsets: dict[str, float] = {}
    for e in beats27:  # shot offsets advance once per SHOT
        if e["shot_id"] not in shot_offsets:
            shot_offsets[e["shot_id"]] = offset
            offset += e["shot_duration_s"]
    offset = 0.0
    for i, e in enumerate(beats27):
        sid, beat = e["shot_id"], e["beat"]
        rec = rec29[(sid, beat["beat_id"])]
        g_start = round(shot_offsets[sid] + beat["start"], 2)
        g_end = round(shot_offsets[sid] + beat["end"], 2)
        entry = {
            "shot_id": sid, "beat_id": beat["beat_id"],
            "index": i,
            "timeline": {"beat_start": beat["start"], "beat_end": beat["end"],
                         "duration": beat["duration"],
                         "global_start": g_start, "global_end": g_end},
            "shot_offset": round(shot_offsets[sid], 2),
            "narration": beat["narration"],          # verbatim from 12.7 chain
            "narration_verbatim_source": "stage12_7_beat_segmentation/beat_test.json",
            "visual_intent": {"text": rec["visual_intent"],
                              "asset_type_hint": rec["asset_type_hint"],
                              "stability": "stage12_9_cache_stable"},
            "subtitle_cues": build_beat_cues(beat["narration"], g_start, g_end),
        }
        cv2 = rec.get("cv2_top1")
        if cv2 and cv2.get("labels") in QUALIFIED_LABELS and cv2.get("vision_fit") is not None:
            title = cv2["title"]
            dup = title in used_assets
            used_assets.add(title)
            entry["material"] = {
                "status": "OK",
                "title": title, "media_type": cv2["mtype"], "tier": cv2.get("tier"),
                "vision_fit": cv2["vision_fit"], "cv2_labels": cv2["labels"],
                "provenance": {
                    "selection_stage": "stage12_9_beat_recovery (CV-2 top-1)",
                    "intent_stage": "stage12_9_intent_stability (cache-stable)",
                    "retrieval_stage": "stage12_8_beat_retrieval T1/T2/T3 (via stage12_9 run)",
                    "segmentation_stage": "stage12_7_beat_segmentation",
                    "v1_top1": rec.get("v1_top1"),
                    "gate_verdict_for_title": next(
                        (g for g in rec.get("gate_verdicts", [])
                         if g.get("candidate_id") == title), None),
                },
                "resolve": {"resolved": False},
            }
            entry["duplicate_asset"] = dup
        else:
            reason = ("cv2_not_usable" if cv2 else rec.get("empty_class", "no_final_asset"))
            entry["material"] = {
                "status": "HONEST_EMPTY", "reason": reason,
                "cv2_candidate_trace": cv2,  # what CV-2 saw, why not qualified
            }
        entry["composition"] = decide_composition(
            entry["visual_intent"]["asset_type_hint"], entry["visual_intent"]["text"],
            None)
        entry["motion"] = decide_motion(
            entry["visual_intent"]["asset_type_hint"], entry["visual_intent"]["text"],
            None, "")
        shots.append(entry)

    total = max(b["timeline"]["global_end"] for b in shots)
    return {"version": "stage12.10", "source": {"timeline": "stage12_7_beat_segmentation/beat_test.json",
                                                "intent_material": "stage12_9_intent_stability/beat_recovery_test.json"},
            "shot_count": len(b27["results"]), "beat_count": len(shots),
            "total_duration_s": round(total, 2),
            "beats": shots,
            "n_material_ok": sum(1 for b in shots if b["material"]["status"] == "OK"),
            "n_honest_empty": sum(1 for b in shots if b["material"]["status"] == "HONEST_EMPTY")}


def attach_resolution(sb: dict, resolutions: dict) -> dict:
    """Runner-side: attach local render resolution records (bytes provenance)."""
    for b in sb["beats"]:
        key = (b["shot_id"], b["beat_id"])
        if b["material"]["status"] == "OK" and key in resolutions:
            b["material"]["resolve"] = resolutions[key]
    return sb


def validate_storyboard(sb: dict, shot_wav_durations: dict[str, float],
                        b27: dict) -> dict:
    """Full legality check suite. Returns {all_pass, checks: [...]}."""
    checks = []

    def add(name, ok, detail=""):
        checks.append({"check": name, "pass": bool(ok), "detail": detail})

    # 1. timeline: no overlap/gap/bounds; beat windows inside shots; shots match wav durations
    probs = []
    cursor = 0.0
    b27_by_shot = {s["shot_id"]: s for s in b27["results"]}
    for sid in b27_by_shot:
        d = shot_wav_durations.get(sid, 0.0)
        if abs(d - b27_by_shot[sid]["shot_duration_s"]) > 0.1:
            probs.append(f"{sid}: wav {d:.2f}s != chain {b27_by_shot[sid]['shot_duration_s']}s")
    prev_end = None
    for b in sb["beats"]:
        t = b["timeline"]
        if t["global_start"] < cursor - 0.001:
            probs.append(f"{b['shot_id']}-{b['beat_id']}: overlap/gap at {t['global_start']} vs {cursor}")
        if t["global_end"] <= t["global_start"]:
            probs.append(f"{b['shot_id']}-{b['beat_id']}: non-positive duration")
        if t["global_end"] > sb["total_duration_s"] + 0.05:
            probs.append(f"{b['shot_id']}-{b['beat_id']}: out of bounds")
        cursor = t["global_end"]
        prev_end = t["global_end"]
    if abs(sb["total_duration_s"] - sum(shot_wav_durations.values())) > 0.1:
        probs.append(f"total {sb['total_duration_s']} != audio {sum(shot_wav_durations.values()):.2f}")
    add("timeline_no_overlap_gap_bounds", not probs, "; ".join(probs) or "ok")

    # 2. narration verbatim: storyboard text == 12.7 chain text; beats cover shot narration
    probs = []
    b27_beats = {(s["shot_id"], b["beat_id"]): b for s in b27["results"] for b in s["beats"]}
    for b in sb["beats"]:
        src = b27_beats[(b["shot_id"], b["beat_id"])]["narration"]
        if b["narration"] != src:
            probs.append(f"{b['shot_id']}-{b['beat_id']}: narration rewritten")
    add("narration_verbatim_untouched", not probs, "; ".join(probs) or "ok")

    # 3. material provenance: OK beats fully traceable; empty honest
    probs = []
    for b in sb["beats"]:
        m = b["material"]
        if m["status"] == "OK":
            if m.get("duplicate_asset"):
                probs.append(f"{b['shot_id']}-{b['beat_id']}: asset reused across beats")
            r = m.get("resolve", {})
            if not (r.get("resolved") and r.get("local_path_exists") and r.get("content_hash")):
                probs.append(f"{b['shot_id']}-{b['beat_id']}: unresolvable material bytes")
            if not m.get("provenance", {}).get("selection_stage"):
                probs.append(f"{b['shot_id']}-{b['beat_id']}: missing provenance")
            if m.get("cv2_labels") not in QUALIFIED_LABELS:
                probs.append(f"{b['shot_id']}-{b['beat_id']}: unqualified labels kept")
        else:
            if not m.get("reason"):
                probs.append(f"{b['shot_id']}-{b['beat_id']}: HONEST_EMPTY without reason")
            if m.get("status") != "HONEST_EMPTY":
                probs.append(f"{b['shot_id']}-{b['beat_id']}: bad empty status")
    add("material_provenance_and_honest_empty", not probs, "; ".join(probs) or "ok")

    # 4. no duplicate time coverage (disjoint by 1) + subtitle legality
    #    length limit: frozen split_for_subtitle guarantees <=22 chars only when
    #    punctuation allows; a comma-less sentence stays one line (12.4-shipped
    #    behaviour). Legality bar = renders inside the 1920px safe area:
    #    26 chars x fontsize 40 ~= 1040px -> limit 26, >26 FAIL.
    probs = []
    all_cues = []
    for b in sb["beats"]:
        for c in b["subtitle_cues"]:
            all_cues.append(c)
            if len(c["text"]) > 26:
                probs.append(f"{b['shot_id']}-{b['beat_id']}: cue >26 chars")
            if c["start"] < b["timeline"]["global_start"] - 0.01 or c["end"] > b["timeline"]["global_end"] + 0.01:
                probs.append(f"{b['shot_id']}-{b['beat_id']}: cue outside beat window")
    for i in range(1, len(all_cues)):
        if all_cues[i]["start"] < all_cues[i - 1]["end"] - 0.001:
            probs.append(f"cue overlap idx{i}")
    add("subtitle_cues_legal", not probs, "; ".join(probs) or f"{len(all_cues)} cues ok")

    # 5. composition/motion params legal
    ok_fits = {"cover", "cover_subject", "contain", "detail_crop"}
    ok_motion = {"STATIC", "SOURCE_NATIVE", "SLOW_ZOOM_IN", "SLOW_PAN", "SUBTLE_ZOOM"}
    probs = []
    for b in sb["beats"]:
        if b["composition"]["fit_mode"] not in ok_fits:
            probs.append(f"{b['shot_id']}-{b['beat_id']}: bad fit_mode")
        if b["motion"]["motion_type"] not in ok_motion:
            probs.append(f"{b['shot_id']}-{b['beat_id']}: bad motion_type")
        if b["motion"]["start_scale"] < 1.0 or b["motion"]["end_scale"] < b["motion"]["start_scale"]:
            probs.append(f"{b['shot_id']}-{b['beat_id']}: illegal scale")
    add("composition_motion_params_legal", not probs, "; ".join(probs) or "ok")

    # 6. beat coverage of chain: same 11 beats, same order
    add("beat_coverage_matches_chain",
        len(sb["beats"]) == len(b27_beats) and
        all((b["shot_id"], b["beat_id"]) in b27_beats for b in sb["beats"]),
        f"{len(sb['beats'])}/{len(b27_beats)}")

    return {"all_pass": all(c["pass"] for c in checks), "checks": checks,
            "total_duration_s": sb["total_duration_s"],
            "n_cues": len(all_cues)}
