"""Global Reuse Ledger: per-CONTENT (not per-material_id) display accounting.

The ledger answers: "how many times has this visual content appeared in the
whole film, where, and in what function?" It is an explicit accumulator that
the reuse policy folds over; it never hides behind module-level state.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from video_studio.orchestration.schemas import LedgerEntry, DisplayKind


class GlobalReuseLedger:
    def __init__(self):
        self.rows: list[LedgerEntry] = []
        self.by_content: dict[str, list[LedgerEntry]] = {}

    # ---------- queries ----------
    def displays(self, content_id: str) -> list[LedgerEntry]:
        return self.by_content.get(content_id, [])

    def use_count(self, content_id: str) -> int:
        return len(self.displays(content_id))

    def borrow_count(self, content_id: str) -> int:
        return sum(1 for r in self.displays(content_id) if r.narrative_function == DisplayKind.BORROW.value)

    def min_gap_violation(self, content_id: str, start: float, end: float, min_gap_s: float) -> bool:
        """True if a display at [start,end] would be <min_gap_s from any existing display."""
        return any(abs(start - r.ts_start) < min_gap_s for r in self.displays(content_id))

    def same_chapter_display(self, content_id: str, chapter_id: int) -> bool:
        return any(r.chapter_id == chapter_id for r in self.displays(content_id))

    def adjacent_same(self, beat_id: str, content_id: str, order: list[str]) -> bool:
        """True if a neighbour beat (in `order`) already displays the same content."""
        if beat_id not in order:
            return False
        i = order.index(beat_id)
        for j in (i - 1, i + 1):
            if 0 <= j < len(order):
                for r in self.rows:
                    if r.beat_id == order[j] and r.content_id == content_id:
                        return True
        return False

    # ---------- mutation ----------
    def record(self, *, content_id: str, material_id: str, beat_id: str, chapter_id: int,
               ts_start: float, ts_end: float, asset_type: str, function: DisplayKind,
               source: str = "", callback_of: str | None = None) -> LedgerEntry:
        ds = self.displays(content_id)
        entry = LedgerEntry(
            content_id=content_id, material_id=material_id, beat_id=beat_id,
            chapter_id=chapter_id, ts_start=ts_start, ts_end=ts_end,
            asset_type=asset_type, narrative_function=function.value, source=source,
            callback_of=callback_of, reuse_count=len(ds),
            borrow_count=1 if function == DisplayKind.BORROW else 0,
            first_seen=ds[0].ts_start if ds else ts_start, last_seen=ts_start,
        )
        self.rows.append(entry)
        self.by_content.setdefault(content_id, []).append(entry)
        return entry

    # ---------- reporting ----------
    def summary(self) -> dict:
        dist: dict[int, int] = {}
        for cid in self.by_content:
            dist[self.use_count(cid)] = dist.get(self.use_count(cid), 0) + 1
        return {
            "contents": len(self.by_content),
            "displays": len(self.rows),
            "max_reuse": max(dist) if dist else 0,
            "reuse_distribution": {str(k): v for k, v in sorted(dist.items())},
            "borrows": sum(r.borrow_count for r in self.rows),
        }

    def content_report(self, content_id: str) -> dict:
        rs = self.displays(content_id)
        return {
            "content_id": content_id,
            "times": len(rs),
            "where": [{"beat": r.beat_id, "chapter": r.chapter_id,
                       "t": [round(r.ts_start, 2), round(r.ts_end, 2)],
                       "function": r.narrative_function} for r in rs],
            "functions": sorted({r.narrative_function for r in rs}),
        }
