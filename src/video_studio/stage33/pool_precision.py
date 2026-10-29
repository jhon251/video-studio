"""pool_precision (Stage 12.13): retrieval-side pool ordering for visual relevance.

12.12 diagnosis: 78/80 empty beats HAD candidates (pool avg 29.8), but the
frozen gate (correctly) rejected its first-6 slice — 70% genuinely off-topic
full-text noise. The fix is RETRIEVAL-SIDE: reorder the merged candidate pool
so visually-relevant candidates sit in the top slice the gate will see. The
gate itself (depth, thresholds, prompts) is NOT touched; material
qualification is NOT changed; T1/T2/T3 provenance is preserved.

Deterministic ordering only — no keyword blacklist (no content word is ever
banned; this is structural ranking), no shot-specific hardcode:

  1. structural media fit: when the intent hint asks for a photo
     (IMAGE/VIDEO), real-image files (IMG/SVG) rank before non-visual files
     (DOC/AUDIO). DOCUMENT-hint intents are left unconstrained, exactly like
     the frozen retrieval preference.
  2. lexical visibility: candidate title tokens overlapping the beat's own
     tier queries (precise weighted highest) — a deterministic, explainable
     relevance proxy. Ties keep the frozen retrieval rank (stable sort).
"""
from __future__ import annotations

from video_studio.stage33.retrieval_v15 import media_type


def _tokens(text: str) -> set[str]:
    return {w for w in "".join(c if c.isalnum() else " " for c in (text or "").lower()).split()
            if len(w) >= 3}


def rerank(merged: list[dict], tiers: dict, asset_type_hint: str) -> dict:
    """Return {"merged": reordered_pool, "rerank_trace"} — stable, provenance kept."""
    hint = (asset_type_hint or "IMAGE").upper()
    wants_image = hint in ("IMAGE", "VIDEO")

    q_tokens = {"precise": set(), "relaxed": set(), "counterpart": set()}
    for tier, qs in tiers.items():
        for q in qs or []:
            q_tokens[tier] |= _tokens(q)

    scored = []
    for idx, c in enumerate(merged):
        mt = media_type(c.get("title", ""))
        # structural fit (mime-level, not content-level)
        if wants_image and mt in ("DOC", "AUDIO"):
            structural = -4.0
        elif wants_image and mt in ("IMG", "SVG"):
            structural = 1.0
        else:
            structural = 0.0
        # lexical visibility against the beat's own queries
        t_tokens = _tokens(c.get("title", ""))
        overlap = sum(2.0 if tier == "precise" else 1.0
                      for tier in ("precise", "relaxed", "counterpart")
                      for _ in [1] if t_tokens & q_tokens[tier])
        scored.append({"idx": idx, "score": round(structural + overlap, 2),
                       "structural": structural, "overlap": round(overlap, 2),
                       "media_type": mt})
    order = sorted(range(len(merged)),
                   key=lambda i: (-scored[i]["score"], scored[i]["idx"]))
    trace = [{"title": merged[i].get("title", ""), **scored[i]} for i in order]
    return {"merged": [merged[i] for i in order], "rerank_trace": trace}
