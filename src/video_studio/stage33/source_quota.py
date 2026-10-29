"""source_quota (Stage 12.24): independent source-quota slice module.

Sits AFTER the frozen pool_precision.rerank and BEFORE the frozen gate: it
rebuilds ONLY the gate head-slice by reserving `quota` seats for non-Commons
source candidates (e.g. Pexels), taking the best Commons candidates by frozen
order for the remaining seats. Everything else — Commons ordering, gate,
V1, CV-2 — is untouched. This is harness-level slice construction, the same
layer where "gate depth 6" lives.

Production-safe usage is TWO-PASS: the standard pipeline runs first; only
beats that remain EMPTY get their slice re-opened with a quota. Ok beats are
never re-processed, so a Commons winner displaced inside a quota slice can
never lose banked material (12.23 canary S23-B02 showed single-pass quota
would push it to rank 11 — that is why two-pass is mandatory).
"""
from __future__ import annotations


def quota_slice(ordered_pool: list[dict], quota: int,
                source_flag: str = "src_pexels", depth: int = 6) -> dict:
    """Build the gate head-slice with `quota` seats reserved for source candidates.

    Returns {"head": [...], "trace": {...}}. Deterministic: Commons seats go to
    the top (depth-quota) Commons candidates in frozen rerank order; source
    seats to the top `quota` source candidates in frozen order. If fewer source
    candidates exist than quota, the freed seats revert to Commons order.
    """
    commons = [c for c in ordered_pool if not c.get(source_flag)]
    sources = [c for c in ordered_pool if c.get(source_flag)]
    q = max(0, min(quota, depth, len(sources)))
    head = commons[:depth - q] + sources[:q]
    trace = {
        "quota": quota, "depth": depth,
        "commons_seats": [c.get("title", "")[:56] for c in commons[:depth - q]],
        "source_seats": [c.get("title", "")[:56] for c in sources[:q]],
        "source_candidates_available": len(sources),
        "source_rank_in_frozen_order": [
            ordered_pool.index(c) + 1 for c in sources[:q]],
    }
    return {"head": head, "trace": trace}
